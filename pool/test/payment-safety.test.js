'use strict';
// Copyright (c) 2026 The WAM Coin developers
// Distributed under the MIT software license, see COPYING.
//
// ---------------------------------------------------------------------------
// The two ways a payment run loses the pool operator's money.
//
// Both were found by reading the payment path rather than by anything going
// wrong, which is the only way either would ever have been found: each needs a
// coincidence of timing that is rare per run and certain over years.
//
//   1. Two runs overlapping. processPayments is on a setInterval. A run that
//      takes longer than the interval -- a slow daemon, two hundred outputs, a
//      wallet rescan -- is still between reading balances and clearing them
//      when the next tick starts. Both read the same balances, both build the
//      same batch, both call sendmany. Everyone is paid twice out of the
//      pool's own wallet and no log line looks wrong.
//
//   2. A crash between sendmany returning and the balances being cleared. The
//      coins are gone, the balances still say they are owed, and the next run
//      pays them again. The window is milliseconds; this project lost power
//      twice in one day.
//
// The fix for the second is not to close the window -- it cannot be closed
// without a transaction across two systems -- but to leave evidence in it, and
// to refuse to pay until a human has looked. A pool that pauses is a support
// ticket. A pool that pays twice is money.
// ---------------------------------------------------------------------------

const assert = require('assert');
const EventEmitter = require('events');
const ShareProcessor = require('../lib/shareProcessor');

let pass = 0;
const fail = [];
const quiet = { info() {}, warn() {}, error() {}, debug() {} };

async function test(name, fn) {
    try { await fn(); pass++; console.log(`  \x1b[32mok\x1b[0m    ${name}`); }
    catch (e) { fail.push(name); console.log(`  \x1b[31mFAIL\x1b[0m  ${name}\n        ${e.message}`); }
}

/** Enough of ioredis to drive the payment path. */
function fakeRedis(initial = {}) {
    const hashes = { 'wam:balances': { ...initial } };
    const strings = {};
    const lists = {};
    const r = {
        calls: [],
        async hgetall(k) { return { ...(hashes[k] || {}) }; },
        async get(k) { return strings[k] ?? null; },
        async set(k, v) { strings[k] = v; r.calls.push(['set', k]); },
        async del(k) { delete strings[k]; r.calls.push(['del', k]); },
        _strings: strings,
        // multi() and pipeline() do the same work here, and the difference is
        // recorded rather than simulated: a fake cannot lose a connection
        // halfway, so it cannot show that a pipeline applies some commands and
        // drops the rest. What it CAN hold down is that the money commit asks
        // redis for a transaction and not a batch, which is the whole of the
        // fix. The real guarantee lives in redis, not here.
        multi() { r.calls.push(['multi']); return r.pipeline(); },
        pipeline() {
            const ops = [];
            const p = {
                hincrby(k, f, by) { ops.push(['hincrby', k, f, by]); return p; },
                hincrbyfloat(k, f, by) { ops.push(['hincrbyfloat', k, f, by]); return p; },
                hset(k, f, v) { ops.push(['hset', k, f, v]); return p; },
                hdel(k, f) { ops.push(['hdel', k, f]); return p; },
                lpush(k, v) { (lists[k] = lists[k] || []).unshift(v); return p; },
                ltrim() { return p; },
                del(k) { ops.push(['del', k]); return p; },
                async exec() {
                    for (const [op, k, f, by] of ops) {
                        if (op === 'hincrby') {
                            hashes[k] = hashes[k] || {};
                            hashes[k][f] = String((parseInt(hashes[k][f] || '0', 10)) + by);
                        } else if (op === 'del') {
                            delete strings[k];
                            r.calls.push(['del', k]);
                        }
                    }
                    return [];
                }
            };
            return p;
        }
    };
    return r;
}

function fakeDaemon(onSendMany) {
    return {
        sent: [],
        async getBalance() { return 1000000; },
        async cmd(method, params) {
            if (method !== 'sendmany') return null;
            this.sent.push(params[1]);
            if (onSendMany) await onSendMany(params[1]);
            return `txid-${this.sent.length}`;
        }
    };
}

function make(redis, daemon, cfg = {}) {
    const sp = new ShareProcessor(redis, daemon, {
        redisPrefix: 'wam', rewardMode: 'pplns', minimumPayoutWam: 1, ...cfg
    }, quiet);
    Object.setPrototypeOf(sp, ShareProcessor.prototype);
    if (!(sp instanceof EventEmitter)) { /* constructed fine */ }
    return sp;
}

(async () => {
    console.log('\n=== two payment runs must not overlap ===');

    await test('a second tick during a slow run pays nobody twice', async () => {
        // The real scenario: one ShareProcessor, one setInterval, and a run
        // that is still inside sendmany when the next tick fires.
        const redis = fakeRedis({ addr1: '500000000', addr2: '300000000' });
        let release;
        const held = new Promise((r) => { release = r; });

        const daemon = fakeDaemon(() => held);   // sendmany hangs until released
        const sp = make(redis, daemon);

        const first = sp.processPayments();      // enters, blocks in sendmany
        await new Promise((r) => setImmediate(r));
        const second = sp.processPayments();     // the next interval tick

        // The second call must return at once, having done nothing. Without the
        // guard it walks into sendmany and blocks on the same promise, so the
        // test would hang rather than fail -- and a hang is a bad way to learn
        // that a pool pays twice. Race it against a timer so the failure says
        // what happened.
        const verdict = await Promise.race([
            second.then(() => 'returned'),
            new Promise((r) => setTimeout(() => r('blocked'), 1500))
        ]);
        assert.strictEqual(verdict, 'returned',
            'the second run entered the payment path instead of skipping; '
            + 'without the guard both runs call sendmany and everyone is paid twice');

        release();
        await first;

        assert.strictEqual(daemon.sent.length, 1,
            `sendmany was called ${daemon.sent.length} times; must be exactly 1`);
    });

    await test('the guard is released after a failure, not left stuck', async () => {
        const redis = fakeRedis({ addr1: '500000000' });
        const daemon = fakeDaemon(() => { throw new Error('daemon exploded'); });
        const sp = make(redis, daemon);
        await sp.processPayments();
        assert.strictEqual(sp.paying, false,
            'a thrown error left the pool unable to ever pay again');
    });

    console.log('\n=== a crash mid-payment must not pay twice ===');

    await test('an intent record is written before the money moves', async () => {
        const redis = fakeRedis({ addr1: '500000000' });
        let atSendTime = null;
        const daemon = fakeDaemon(async () => {
            atSendTime = await redis.get('wam:payment:inflight');
        });
        const sp = make(redis, daemon);
        await sp.processPayments();
        assert.ok(atSendTime, 'nothing recorded the intent before sendmany');
        const rec = JSON.parse(atSendTime);
        assert.ok(rec.payouts.addr1, 'the record does not name who was being paid');
    });

    await test('it is cleared once balances are cleared', async () => {
        const redis = fakeRedis({ addr1: '500000000' });
        const sp = make(redis, fakeDaemon());
        await sp.processPayments();
        assert.strictEqual(await redis.get('wam:payment:inflight'), null,
            'a completed run left a marker that will pause the next start-up');
    });

    await test('a REFUSED sendmany clears it, so one RPC error does not halt the pool', async () => {
        const redis = fakeRedis({ addr1: '500000000' });
        // As daemon.js now classifies it: the node parsed the request and said
        // no, so no transaction exists.
        const daemon = fakeDaemon(() => {
            const e = new Error('Insufficient funds');
            e.ambiguous = false;
            throw e;
        });
        const sp = make(redis, daemon);
        await sp.processPayments();
        assert.strictEqual(await redis.get('wam:payment:inflight'), null,
            'a definite refusal left the pool paused');
        assert.notStrictEqual(sp.paused, true,
            'a definite refusal must not pause the pool');
    });

    // ---- the four findings, each failing on the code as it was -------------
    //
    // Reported by dang150296 (Urriki1502), 2026-10-03. Every one of these
    // passes trivially against the old shareProcessor if you remove the fix,
    // except that it does not: each was run against the old code first and
    // each failed. That is the only reason to believe they test anything.

    await test('an UNKNOWN sendmany outcome keeps the intent and pauses', async () => {
        const redis = fakeRedis({ addr1: '500000000' });
        const daemon = fakeDaemon(() => {
            const e = new Error('RPC timeout calling sendmany');
            e.ambiguous = true;
            throw e;
        });
        const sp = make(redis, daemon);
        await sp.processPayments();
        assert.ok(await redis.get('wam:payment:inflight'),
            'a timeout deleted the only evidence that the money may have moved');
        assert.strictEqual(sp.paused, true,
            'the pool kept paying after an outcome it could not determine');
    });

    await test('an unclassified error is treated as unknown, not as a refusal', async () => {
        const redis = fakeRedis({ addr1: '500000000' });
        const daemon = fakeDaemon(() => { throw new Error('something nobody classified'); });
        const sp = make(redis, daemon);
        await sp.processPayments();
        assert.ok(await redis.get('wam:payment:inflight'),
            'an error of unknown provenance was assumed harmless');
        assert.strictEqual(sp.paused, true, 'uncertainty did not stop the pool');
    });

    await test('the money commit is a transaction, not a batch', async () => {
        const redis = fakeRedis({ addr1: '500000000' });
        const sp = make(redis, fakeDaemon());
        await sp.processPayments();
        assert.ok(redis.calls.some(([op]) => op === 'multi'),
            'balances, journal and intent were committed as a pipeline, which ' +
            'redis may apply only in part');
    });

    await test('payments are paused until the start-up check has finished', async () => {
        const redis = fakeRedis({ addr1: '500000000' });
        let release;
        const held = new Promise((r) => { release = r; });
        // A redis that hangs on the one GET startupReconcile makes.
        const slow = { ...redis, async get(k) { await held; return redis.get(k); } };
        const daemon = fakeDaemon();
        const sp = make(slow, daemon);
        sp.start();
        assert.strictEqual(sp.paused, true,
            'the payment timer was armed before the unfinished-run check answered');
        await sp.processPayments();
        assert.strictEqual(daemon.sent.length, 0,
            'the pool paid while the check that prevents double payment was still running');
        sp.stop();
        release();
    });

    await test('a start-up check that throws leaves payments paused', async () => {
        const redis = fakeRedis({ addr1: '500000000' });
        const broken = { ...redis, async get() { throw new Error('redis is down'); } };
        const daemon = fakeDaemon();
        const sp = make(broken, daemon);
        sp.start();
        await new Promise((r) => setImmediate(r));
        assert.strictEqual(sp.paused, true,
            'a failed check released payments instead of holding them');
        await sp.processPayments();
        assert.strictEqual(daemon.sent.length, 0, 'the pool paid anyway');
        sp.stop();
    });

    await test('a surviving record pauses payments until a human clears it', async () => {
        const redis = fakeRedis({ addr1: '500000000' });
        await redis.set('wam:payment:inflight', JSON.stringify({
            startedAt: Date.now(), total: 500000000, payouts: { addr1: 500000000 }
        }));
        const daemon = fakeDaemon();
        const sp = make(redis, daemon);
        const ok = await sp.startupReconcile();
        assert.strictEqual(ok, false, 'reconcile did not report a problem');
        await sp.processPayments();
        assert.strictEqual(daemon.sent.length, 0,
            'the pool paid again over an unfinished previous run');
    });

    await test('no record means a clean start', async () => {
        const redis = fakeRedis({ addr1: '500000000' });
        const sp = make(redis, fakeDaemon());
        assert.strictEqual(await sp.startupReconcile(), true);
        assert.notStrictEqual(sp.paused, true);
    });

    console.log('\n' + '='.repeat(66));
    if (fail.length === 0) {
        console.log(`\x1b[32m${pass} passed\x1b[0m`);
    } else {
        console.log(`\x1b[31m${fail.length} failed\x1b[0m, ${pass} passed`);
        fail.forEach((f) => console.log(`  - ${f}`));
    }
    console.log('='.repeat(66));
    process.exit(fail.length === 0 ? 0 : 1);
})();

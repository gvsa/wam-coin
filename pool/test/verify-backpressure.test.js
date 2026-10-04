'use strict';
// Copyright (c) 2026 The WAM Coin developers
// Distributed under the MIT software license, see COPYING.
//
// ===========================================================================
//  Verification work is bounded, because the sender's cost is not
// ===========================================================================
//
//      node pool/test/verify-backpressure.test.js
//
//  WHAT WAS WRONG
//
//  randomx.hash() queues a Napi::AsyncWorker on the libuv threadpool, and that
//  worker's first act is to wait on a condition variable until one of vmCount
//  RandomX VMs is free. A waiting worker is a BLOCKED THREADPOOL THREAD, and
//  node's default pool is four threads for the whole process -- shared with
//  dns, fs and crypto.
//
//  Nothing bounded how many could be queued. Anyone able to open a socket and
//  send syntactically valid submissions could park every threadpool thread in
//  cv.wait and stall everything else the pool does, having spent nothing:
//  sending a share is bytes, verifying one is milliseconds of a scarce VM.
//
//  SECURITY.md calls denial of service that costs the attacker less than the
//  victim the interesting kind. This is that.
//
//  Reported by dang150296 (Urriki1502), 2026-10-04.
//
//  WHAT IS TESTED HERE
//
//  The counter and the refusal, driven through the real processShare with
//  RandomX replaced by a hash that never finishes until released. The native
//  addon is not needed and neither is a node.
// ===========================================================================

const assert = require('assert');
const Module = require('module');

// Stand in for the native addon before jobManager pulls it in. It is not built
// on every machine, and this test is about the queue rather than the hashing.
const gate = { pending: 0, release: null, slow: true };
const origResolve = Module._resolveFilename;
const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
    if (request === '../native' || request === './native' || /native$/.test(request)) {
        return {
            hash: () => {
                gate.pending++;
                if (!gate.slow) { gate.pending--; return Promise.resolve(Buffer.alloc(32, 0xff)); }
                return new Promise((resolve) => {
                    const prev = gate.release;
                    gate.release = () => {
                        if (prev) prev();
                        gate.pending--;
                        resolve(Buffer.alloc(32, 0xff));
                    };
                });
            },
            configure: () => {},
            seedForHeight: () => Buffer.alloc(32)
        };
    }
    return origLoad(request, parent, isMain);
};
void origResolve;

const JobManager = require('../lib/jobManager');

const GRN = '\x1b[32m', RED = '\x1b[31m', BLD = '\x1b[1m', OFF = '\x1b[0m';
let pass = 0;
const fail = [];

async function test(name, fn) {
    try { await fn(); pass++; console.log(`  ${GRN}ok${OFF}    ${name}`); }
    catch (e) { fail.push(name); console.log(`  ${RED}FAIL${OFF}  ${name}\n        ${e.message}`); }
}

const quiet = { info() {}, warn() {}, error() {}, debug() {} };

(async () => {
    console.log(`\n${BLD}the verification queue has a bottom${OFF}`);

    await test('the bound is sized from the VM count, with a floor', () => {
        const a = new JobManager({}, { randomxVmCount: 16 }, quiet);
        const b = new JobManager({}, { randomxVmCount: 1 }, quiet);
        const c = new JobManager({}, { maxPendingVerifications: 7 }, quiet);
        assert.strictEqual(a._maxVerifying, 64, '16 VMs should allow 64 in flight');
        assert.strictEqual(b._maxVerifying, 32, 'the floor of 32 is gone');
        assert.strictEqual(c._maxVerifying, 7, 'the config override is ignored');
    });

    // A job with just enough on it for processShare to reach the hash. Writing
    // the guard's condition out again in the test would prove only that I can
    // retype it; this drives the real function.
    function fakeJob() {
        return {
            height: 100,
            curTime: Math.floor(Date.now() / 1000) - 10,
            seedHash: 'ab'.repeat(32),
            nBits: '1f00ffff',
            coinbaseValue: 5000000000,
            distributableValue: 4750000000,
            devFeeAmount: 250000000,
            claims: new Set(),
            registerSubmit(...a) {
                const k = a.join(':');
                if (this.claims.has(k)) return false;
                this.claims.add(k); return true;
            },
            releaseSubmit(...a) { this.claims.delete(a.join(':')); },
            serializeCoinbase: () => Buffer.alloc(100),
            computeMerkleRoot: () => Buffer.alloc(32),
            serializeHeader: () => Buffer.alloc(80)
        };
    }

    function submission(nonce) {
        return {
            jobId: 'j1',
            extranonce1: Buffer.from('aabbccdd', 'hex'),
            extranonce2Hex: '00000000',
            nTimeHex: Math.floor(Date.now() / 1000).toString(16).padStart(8, '0'),
            nonceHex: nonce,
            workerName: 'w.1',
            difficulty: 0.00001,
            ipAddress: '127.0.0.1'
        };
    }

    await test('processShare refuses once the queue is full, and counts it', async () => {
        const jm = new JobManager({}, { maxPendingVerifications: 3 }, quiet);
        jm.validJobs.set('j1', fakeJob());
        gate.slow = true;

        // Three submissions that will sit inside randomx.hash and never return.
        const held = [
            jm.processShare(submission('00000001')),
            jm.processShare(submission('00000002')),
            jm.processShare(submission('00000003'))
        ];
        await new Promise((r) => setImmediate(r));
        assert.strictEqual(jm._verifying, 3, 'the in-flight count is not tracking');

        // The fourth must be turned away rather than queued behind them.
        const fourth = await jm.processShare(submission('00000004'));
        assert.strictEqual(fourth.valid, false, 'a fourth was queued on a queue of three');
        // _reject returns { valid:false, error:[code, message, null] }.
        const [code, message] = fourth.error;
        assert.strictEqual(code, 20, 'the wrong reject code');
        assert.match(message, /queue full/,
            'the miner is not told why, so he cannot know to resend');
        assert.strictEqual(jm.stats.verifyRejected, 1,
            'the refusal was not counted, so a flood is invisible to an operator');

        // And the slot it refused is not lost: releasing one lets work through.
        if (gate.release) gate.release();
        await new Promise((r) => setImmediate(r));
        assert.ok(jm._verifying < 3, 'a finished verification did not free its slot');
        void held;
    });

    await test('an ordinary share is not refused while the queue has room', async () => {
        const jm = new JobManager({}, { maxPendingVerifications: 8 }, quiet);
        jm.validJobs.set('j1', fakeJob());
        gate.slow = false;

        const r = await jm.processShare(submission('0000000a'));
        assert.ok(!r.error || !/queue full/.test(r.error[1]),
            'a single share on an empty queue was refused as if the pool were '
            + 'flooded; the bound is too tight to mine against');
        assert.strictEqual(jm.stats.verifyRejected, 0);
        assert.strictEqual(jm._verifying, 0, 'the slot was not released');
    });

    await test('BUSY is told apart from UNAVAILABLE', () => {
        // Both mean "send it again" and they need opposite responses from an
        // operator: one is redis failing, the other is the pool saturated.
        const src = require('fs').readFileSync(require.resolve('../lib/jobManager'), 'utf8');
        assert.ok(/BUSY:\s*\[\d+, '[^']*queue full/.test(src),
            'there is no distinct code for a full verification queue');
        assert.ok(/UNAVAILABLE:\s*\[\d+, '[^']*not recorded/.test(src),
            'the two resubmit cases have been collapsed into one');
    });

    await test('the counter is released whether hashing succeeds or throws', () => {
        const src = require('fs').readFileSync(require.resolve('../lib/jobManager'), 'utf8');
        const tail = src.slice(src.indexOf('this._verifying++'));
        const fin = tail.indexOf('} finally {');
        const dec = tail.indexOf('this._verifying--');
        assert.ok(fin > -1 && dec > fin && dec - fin < 60,
            'the in-flight count is not decremented in a finally; one throw and '
            + 'the queue leaks a slot for the life of the process');
    });

    console.log();
    if (!fail.length) {
        console.log(`${GRN}${BLD}${pass} passed${OFF}`);
    } else {
        console.log(`${RED}${BLD}${fail.length} failed${OFF}, ${pass} passed`);
        fail.forEach((f) => console.log(`  - ${f}`));
    }
    process.exit(fail.length ? 1 : 0);
})();

'use strict';
// Copyright (c) 2026 The WAM Coin developers
// Distributed under the MIT software license, see COPYING.
//
// ===========================================================================
//  A dropped connection must not become a second payment
// ===========================================================================
//
//      node pool/test/daemon-money-failover.test.js
//
//  WHAT WAS WRONG
//
//  daemon.cmd() walked every configured daemon and retried the same call on
//  the next one whenever the first threw. sendmany was not exempt.
//
//  A node that receives sendmany, signs it, broadcasts it, and then loses the
//  connection before the reply arrives is, from the pool's side, identical to
//  a node that never received anything: both are a rejected promise. The pool
//  then sent the same batch to the second daemon. Two transactions, one
//  payment round, out of the operator's own wallet -- with no attacker, no
//  race in our code, and nothing in the logs that looks wrong.
//
//  Reported by dang150296 (Urriki1502) on 2026-10-03 as "generic daemon
//  failover for money-moving RPCs". Confirmed, fixed, and held down here.
//
//  WHAT THE FIX IS NOT
//
//  It is not "never fail over on sendmany". A connection that was refused
//  outright proves the request never ran, and an operator with two nodes
//  should still be paid when one of them is simply down. The line is drawn at
//  what the error proves, not at the method name alone -- so three of the
//  cases below check that the safe failover still happens.
// ===========================================================================

const assert = require('assert');
const DaemonInterface = require('../lib/daemon.js');

const quiet = { info() {}, warn() {}, error() {}, debug() {} };

let pass = 0;
const fail = [];

async function test(name, fn) {
    try { await fn(); pass++; console.log(`  \x1b[32mok\x1b[0m    ${name}`); }
    catch (e) { fail.push(name); console.log(`  \x1b[31mFAIL\x1b[0m  ${name}\n        ${e.message}`); }
}

/**
 * A DaemonInterface whose transport is scripted per daemon.
 *
 * `script` is one entry per configured daemon: either a value to resolve, or
 * an Error to reject with. Every attempt is recorded, which is the whole point
 * -- the question these tests ask is "was the second node asked at all".
 */
function harness(script) {
    const d = new DaemonInterface(
        script.map((_, i) => ({ host: `h${i}`, port: 9554, user: 'u', password: 'p' })),
        quiet);
    d.attempts = [];
    d._request = async (daemon, method) => {
        d.attempts.push(`${daemon.host}:${method}`);
        const outcome = script[daemon.index];
        if (outcome instanceof Error) throw outcome;
        return outcome;
    };
    for (const x of d.daemons) x.online = true;
    return d;
}

function err(message, ambiguous, code) {
    const e = new Error(message);
    if (ambiguous !== undefined) e.ambiguous = ambiguous;
    if (code) e.code = code;
    return e;
}

(async () => {
    console.log('\n=== a money RPC whose outcome is unknown stops at one daemon ===');

    await test('a timeout on sendmany is not retried elsewhere', async () => {
        const d = harness([err('RPC timeout calling sendmany', true), 'txid-2']);
        await assert.rejects(() => d.cmd('sendmany', ['', { addr: 1 }]));
        assert.deepStrictEqual(d.attempts, ['h0:sendmany'],
            'the batch was sent to a second node after the first went quiet');
    });

    await test('the rejection still says the outcome was unknown', async () => {
        const d = harness([err('socket hang up', true), 'txid-2']);
        await d.cmd('sendmany', ['', {}]).then(
            () => assert.fail('resolved'),
            (e) => assert.strictEqual(e.ambiguous, true,
                'the caller cannot tell a refusal from a lost answer'));
    });

    await test('a real connection dropped mid-reply is classified as unknown', async () => {
        // The classifier lives in _request, which the harness replaces, so this
        // one uses the real thing against a real socket. A server that takes
        // the request and then destroys the connection is precisely the node
        // that broadcast and could not tell us.
        const http = require('http');
        const server = http.createServer((req, res) => {
            req.on('data', () => {});
            req.on('end', () => res.socket.destroy());
        });
        await new Promise((r) => server.listen(0, '127.0.0.1', r));
        const port = server.address().port;

        const d = new DaemonInterface(
            [{ host: '127.0.0.1', port, user: 'u', password: 'p' },
             { host: '127.0.0.1', port, user: 'u', password: 'p' }], quiet);
        d.daemons.forEach((x) => { x.online = true; });

        try {
            await d.cmd('sendmany', ['', {}]).then(
                () => assert.fail('a destroyed connection resolved'),
                (e) => assert.strictEqual(e.ambiguous, true,
                    'a dropped reply was read as proof that nothing was sent'));
        } finally {
            server.close();
        }
    });

    console.log('\n=== but a refusal, and a node that is simply down, still fail over ===');

    await test('a node that refused the spend does not block the second node', async () => {
        // The node parsed the request and said no: nothing was broadcast, so
        // asking another node is safe. Availability is preserved exactly where
        // it can be.
        const d = harness([err('Method not found', false), 'txid-2']);
        assert.strictEqual(await d.cmd('sendmany', ['', {}]), 'txid-2');
        assert.deepStrictEqual(d.attempts, ['h0:sendmany', 'h1:sendmany']);
    });

    await test('a connection that was refused still fails over', async () => {
        const d = harness([err('connect ECONNREFUSED', false, 'ECONNREFUSED'), 'txid-2']);
        assert.strictEqual(await d.cmd('sendmany', ['', {}]), 'txid-2');
        assert.deepStrictEqual(d.attempts, ['h0:sendmany', 'h1:sendmany'],
            'an operator with a spare node was not paid because the first was down');
    });

    await test('a read-only call fails over on any error, as before', async () => {
        const d = harness([err('RPC timeout', true), { blocks: 11000 }]);
        assert.deepStrictEqual(await d.cmd('getblockchaininfo'), { blocks: 11000 });
        assert.deepStrictEqual(d.attempts,
            ['h0:getblockchaininfo', 'h1:getblockchaininfo'],
            'the fix was applied too widely and ordinary failover is gone');
    });

    console.log('\n=== the list itself ===');

    await test('every RPC that creates a new spend is guarded', async () => {
        for (const m of ['sendmany', 'sendtoaddress', 'sendfrom', 'send', 'sendall']) {
            assert.ok(DaemonInterface.MONEY_RPCS.has(m), `${m} is not guarded`);
        }
    });

    await test('sendrawtransaction is deliberately NOT guarded', async () => {
        // Rebroadcasting the same signed transaction is idempotent -- same
        // txid, same outputs -- and a recovery path needs to be able to do it
        // on whichever node answers.
        assert.ok(!DaemonInterface.MONEY_RPCS.has('sendrawtransaction'));
        const d = harness([err('RPC timeout', true), 'txid']);
        assert.strictEqual(await d.cmd('sendrawtransaction', ['hex']), 'txid');
    });

    await test('when every daemon fails, one unknown makes the whole outcome unknown', async () => {
        // Not the last error's flag: a first node that might have executed the
        // call is enough, however definite the second node's refusal was.
        const d = harness([err('RPC timeout', true), err('Method not found', false)]);
        await d.cmd('getblockchaininfo').then(
            () => assert.fail('resolved'),
            (e) => assert.strictEqual(e.ambiguous, true,
                'uncertainty was lost because only the last failure was read'));
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

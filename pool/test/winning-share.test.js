'use strict';
// Copyright (c) 2026 The WAM Coin developers
// Distributed under the MIT software license, see COPYING.
//
// ===========================================================================
//  The share that found the block must be paid by that block
// ===========================================================================
//
//      node pool/test/winning-share.test.js
//
//  WHAT WAS WRONG
//
//  processShare submitted the block and only then emitted 'share':
//
//      if (isBlockCandidate) await this._submitBlock(...);   // emits 'block'
//      credited = true;
//      this.emit('share', share);
//
//  The 'block' listener snapshots the PPLNS window and the round and then
//  resets the round. So the winning share was not in the snapshot of its own
//  block's payout -- it was still unrecorded when the snapshot was taken, and
//  landed in the NEXT round, to be paid at the next block's rate to whoever
//  was mining by then.
//
//  The miner who found the block is the one the ordering short-changed, and
//  nothing about it is visible: the share is credited, the block is paid, and
//  the arithmetic is simply off by one round for one miner.
//
//  Reported by dang150296 (Urriki1502), 2026-10-04.
//
//  WHY TWO ASSERTIONS AND NOT ONE
//
//  Emitting in the right order is not enough. Both listeners were
//  fire-and-forget promises, so recordBlock's reads could still finish before
//  recordShare's writes. The first test here fixes the order things START in;
//  the second fixes the order they FINISH in, by making a slow share record
//  block a fast block record -- which is exactly the race that an ordering
//  "guaranteed" by emit order alone would lose.
// ===========================================================================

const assert = require('assert');
const EventEmitter = require('events');

const GRN = '\x1b[32m', RED = '\x1b[31m', BLD = '\x1b[1m', OFF = '\x1b[0m';
let pass = 0;
const fail = [];

async function test(name, fn) {
    try { await fn(); pass++; console.log(`  ${GRN}ok${OFF}    ${name}`); }
    catch (e) { fail.push(name); console.log(`  ${RED}FAIL${OFF}  ${name}\n        ${e.message}`); }
}

/** The wiring server.js uses, lifted out so it can be driven without a pool. */
function wire(jobManager, processor, log) {
    let accounting = Promise.resolve();
    const inOrder = (what, fn) => {
        accounting = accounting.then(fn).catch((err) => log.push(`${what}: ${err.message}`));
    };
    jobManager.on('share', (s) => inOrder('a share', () => processor.recordShare(s)));
    jobManager.on('block', (s) => inOrder(`block ${s.height}`, () => processor.recordBlock(s)));
    return () => accounting;
}

/** A processor that records what it saw, and how slowly. */
function fakeProcessor(shareDelayMs = 0) {
    return {
        window: [],
        snapshots: [],
        async recordShare(s) {
            if (shareDelayMs) await new Promise((r) => setTimeout(r, shareDelayMs));
            this.window.push(s.id);
        },
        async recordBlock(s) {
            // What recordBlock really does first: read the window, then reset.
            this.snapshots.push({ height: s.height, window: [...this.window] });
            this.window = [];
        }
    };
}

(async () => {
    console.log(`\n${BLD}the winning share is inside its own block's payout${OFF}`);

    await test('the share is emitted before the block it found', async () => {
        const jm = new EventEmitter();
        const p = fakeProcessor();
        const settled = wire(jm, p, []);

        // The order processShare now uses: credit the share, then submit.
        const share = { id: 'winner', height: 101 };
        jm.emit('share', share);
        jm.emit('block', share);
        await settled();

        assert.strictEqual(p.snapshots.length, 1, 'the block was not recorded');
        assert.ok(p.snapshots[0].window.includes('winner'),
            'the share that found block 101 was not in block 101\'s payout -- it ' +
            'was pushed into the next round');
    });

    await test('a slow share record still lands before the block snapshot', async () => {
        // The half that emit order alone does not fix. recordShare takes 40ms;
        // recordBlock takes none. Without the chain the snapshot is taken
        // first and the winner is lost exactly as before.
        const jm = new EventEmitter();
        const p = fakeProcessor(40);
        const settled = wire(jm, p, []);

        const share = { id: 'winner', height: 102 };
        jm.emit('share', share);
        jm.emit('block', share);
        await settled();

        assert.ok(p.snapshots[0].window.includes('winner'),
            'the block snapshot overtook a slow share write');
    });

    await test('the old order loses the winner, which is why this exists', async () => {
        // Emitting block first, as processShare did before 2026-10-04.
        const jm = new EventEmitter();
        const p = fakeProcessor();
        const settled = wire(jm, p, []);

        const share = { id: 'winner', height: 103 };
        jm.emit('block', share);
        jm.emit('share', share);
        await settled();

        assert.ok(!p.snapshots[0].window.includes('winner'),
            'the fault no longer reproduces, so this test proves nothing');
        assert.deepStrictEqual(p.window, ['winner'],
            'the winning share should have been left in the next round');
    });

    await test('one failed record does not stop every later one', async () => {
        const jm = new EventEmitter();
        const log = [];
        const p = fakeProcessor();
        let first = true;
        const orig = p.recordShare.bind(p);
        p.recordShare = async function (s) {
            if (first) { first = false; throw new Error('redis went away'); }
            return orig(s);
        };
        const settled = wire(jm, p, log);

        jm.emit('share', { id: 'lost', height: 104 });
        jm.emit('share', { id: 'later', height: 104 });
        jm.emit('block', { id: 'later', height: 104 });
        await settled();

        assert.strictEqual(log.length, 1, 'the failure was not reported');
        assert.ok(p.snapshots[0].window.includes('later'),
            'one rejected promise poisoned the chain and stopped all accounting');
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

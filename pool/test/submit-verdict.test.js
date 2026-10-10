'use strict';
// Copyright (c) 2026 The WAM Coin developers
// Distributed under the MIT software license, see COPYING.
//
// ===========================================================================
//  What the node meant is decided once, and only once
// ===========================================================================
//
//      node pool/test/submit-verdict.test.js
//
//  WHAT WAS WRONG
//
//  `submitblock` reports four different situations down one string channel,
//  and two of them are not failures. From src/rpc/mining.cpp:
//
//  wam:quote-begin
//      if (!new_block && accepted) return "duplicate";
//      if (!sc->found)             return "inconclusive";
//      return BIP22ValidationResult(sc->state);
//  wam:quote-end
//
//  "duplicate" means the node already had the block. "inconclusive" means it
//  processed it and named no fault -- a real refusal always comes back with a
//  reason. Neither costs anybody a coin.
//
//  That was read wrongly in three separate places, each found separately:
//
//    * the miner counted a lost race as a block that went missing, and told
//      solo miners "do not leave it running". One of them stopped a working
//      miner on 2026-10-03.
//    * drainSpool treated "duplicate" as settled and dropped the entry
//      without paying, so a block on the chain was never credited. Found by
//      dang150296 against bb6d521.
//    * the live submit path logged, at ERROR, until 2026-10-10:
//
//  wam:quote-begin
//      block 17169 REJECTED: inconclusive
//          the block is kept for inspection ... the node read it and refused it
//  wam:quote-end
//
//      for two of OUR OWN miners solving height 17169 seventy milliseconds
//      apart. The first was accepted, recorded and paid to 36 workers. The
//      second arrived 28ms later and was told the node already had one.
//
//  Patching the third would have left a fourth. The vocabulary lives in
//  daemon.js, every caller asks it for a verdict, and the last test in this
//  file refuses the words anywhere else.
// ===========================================================================

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const { SUBMIT, classifySubmit } = require('../lib/daemon');
const { outcomeOf } = require('./outcome');

// Stand in for the native RandomX addon, which is not built on every machine
// and has nothing to do with reading a node's answer. Installed before
// jobManager is loaded, the same way verify-backpressure.test.js does it.
const Module = require('module');
const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
    if (/native$/.test(request)) {
        return { hash: async () => Buffer.alloc(32, 0xff),
                 configure: () => {}, seedForHeight: () => Buffer.alloc(32),
                 stats: () => ({}) };
    }
    return origLoad(request, parent, isMain);
};

const GRN = '\x1b[32m', RED = '\x1b[31m', BLD = '\x1b[1m', OFF = '\x1b[0m';
let pass = 0;
const fail = [];

async function test(name, fn) {
    try { await fn(); pass++; console.log(`  ${GRN}ok${OFF}    ${name}`); }
    catch (e) { fail.push(name); console.log(`  ${RED}FAIL${OFF}  ${name}\n        ${e.message}`); }
}

const ANSWERED = [{ ok: true, daemon: 'node' }];
const SILENT = [{ ok: false, error: 'ECONNREFUSED', daemon: 'node' }];

// Every string this node can return, taken from src/rpc/mining.cpp rather
// than from memory. A word that is not in this table is not classified, and
// an unclassified word must fall to REFUSED -- the safe side.
// wam:quote-begin
const VOCABULARY = [
    ['duplicate',                     SUBMIT.ALREADY_HAVE, 'the node already had it'],
    ['inconclusive',                  SUBMIT.ALREADY_HAVE, 'processed, no fault named'],
    ['duplicate-inconclusive',        SUBMIT.ALREADY_HAVE, 'known, and inconclusive'],
    ['inconclusive-not-best-prevblk', SUBMIT.ALREADY_HAVE, 'builds on a side branch'],
    ['duplicate-invalid',             SUBMIT.REFUSED,      'known AND bad'],
    ['high-hash',                     SUBMIT.REFUSED,      'a named fault'],
    ['bad-txns-inputs-missingorspent', SUBMIT.REFUSED,     'a named fault'],
    ['time-too-old',                  SUBMIT.REFUSED,      'a named fault'],
    ['bad-cb-amount',                 SUBMIT.REFUSED,      'a named fault'],
];
// wam:quote-end

(async () => {
console.log(`\n${BLD}what the node meant, decided once${OFF}\n`);

await test('a node that took it is accepted', () => {
    assert.strictEqual(classifySubmit(true, [], ANSWERED), SUBMIT.ACCEPTED);
});

for (const [word, want, why] of VOCABULARY) {
    await test(`"${word}" -> ${want} (${why})`, () => {
        const got = classifySubmit(false, [`node: ${word}`], ANSWERED);
        assert.strictEqual(got, want,
            `"${word}" was read as ${got}; it means ${why}`);
    });
}

await test('silence is not a refusal -- it is retried', () => {
    assert.strictEqual(classifySubmit(false, ['node: ECONNREFUSED'], SILENT),
        SUBMIT.UNANSWERED,
        'a node that never answered would have its block thrown away');
});

await test('a word nobody has seen before falls to refused, not to harmless', () => {
    // The safe side: treating an unknown fault as "nothing to worry about"
    // is how a genuinely bad block gets dropped in silence.
    assert.strictEqual(
        classifySubmit(false, ['node: some-future-reason'], ANSWERED),
        SUBMIT.REFUSED);
});

await test('duplicate-invalid is not rescued by the word duplicate', () => {
    // It contains "duplicate" and it is the one member of the family that is
    // a fault. Test order decides this, and getting it backwards turns a
    // known-bad block into "the node already has it".
    assert.strictEqual(
        classifySubmit(false, ['node: duplicate-invalid'], ANSWERED),
        SUBMIT.REFUSED);
});

await test('one daemon answering duplicate while another is silent still counts', () => {
    const mixed = [{ ok: true, daemon: 'a' }, { ok: false, error: 'EHOSTDOWN', daemon: 'b' }];
    assert.strictEqual(
        classifySubmit(false, ['a: duplicate', 'b: EHOSTDOWN'], mixed),
        SUBMIT.ALREADY_HAVE,
        'a block one node already has is not resubmitted forever because '
        + 'another node was down');
});

await test('the vocabulary exists in exactly one file', () => {
    // The guard. Three sites read these words differently, each fixed
    // separately, and the fourth would have been written the same way.
    const dir = path.join(__dirname, '..', 'lib');
    const offenders = [];
    const files = fs.readdirSync(dir).filter((f) => f.endsWith('.js'))
        .concat(['../server.js']);
    for (const f of files) {
        if (f === 'daemon.js') continue;
        const p = path.join(dir, f);
        if (!fs.existsSync(p)) continue;
        const lines = fs.readFileSync(p, 'utf8').split('\n');
        lines.forEach((line, i) => {
            if (/wam:quote-/.test(line)) return;
            if (/\binconclusive\b|duplicate-invalid/.test(line)) {
                offenders.push(`${f}:${i + 1}`);
            }
        });
    }
    assert.deepStrictEqual(offenders, [],
        'the node\'s submit vocabulary is being read outside daemon.js, at '
        + offenders.join(', ') + ' -- that is the fourth place it drifts');
});

await test('a verdict is attached to every submit result', () => {
    const src = fs.readFileSync(require.resolve('../lib/daemon'), 'utf8');
    assert.match(src, /verdict:\s*classifySubmit\(/,
        'submitBlock does not carry a verdict, so every caller has to decide '
        + 'for itself what the node meant');
});

// The behaviour, driven through the real _submitBlock.
//
// The first version of this test read the source for the string
// `verdict === SUBMIT.ALREADY_HAVE`, and when the live branch was disabled on
// purpose to see the test fail, it passed -- the same string lives in
// drainSpool. A test that greps for a phrase tests that the phrase is in the
// file. This one runs the function and looks at what it did.
function jobFixture() {
    return {
        height: 17169,
        coinbaseValue: 5000000000,
        distributableValue: 4750000000,
        devFeeAmount: 250000000,
        serializeBlock: () => Buffer.alloc(200),
    };
}

async function runSubmit(outcome) {
    const JobManager = require('../lib/jobManager');
    const quiet = { info() {}, warn() {}, error() {}, debug() {} };
    const logged = [];
    const jm = new JobManager({ submitBlock: async () => outcome }, {}, quiet);
    for (const level of ['info', 'warn', 'error']) {
        jm.log[level] = (m) => logged.push(`${level}: ${m}`);
    }
    jm.refreshTemplate = async () => {};
    const rejected = [];
    jm.on('blockRejected', (s) => rejected.push(s));
    const share = { worker: 'w.1' };
    await jm._submitBlock(jobFixture(), Buffer.alloc(80), Buffer.alloc(100), share);
    return { jm, share, logged, rejected };
}

await test('a lost race is not logged as a rejection, and is counted apart', async () => {
    const { jm, share, logged, rejected } = await runSubmit(
        outcomeOf(false, ['node: inconclusive'],
                  [{ ok: true, error: null, result: 'inconclusive' }]));

    assert.strictEqual(share.blockAccepted, false, 'it did not become the tip');
    assert.strictEqual(share.blockStale, true,
        'a lost race is not marked as such, so nothing downstream can tell');
    assert.strictEqual(jm.stats.blocksStale, 1,
        'a lost race is not counted, so an operator cannot tell "we lost two '
        + 'races" from "we made two bad blocks"');
    assert.strictEqual(rejected.length, 0,
        'blockRejected was emitted for a block the node did not reject');

    const text = logged.join('\n');
    assert.ok(!/REJECTED/.test(text),
        `a lost race was logged as a rejection:\n${text}`);
    assert.ok(!/refused/i.test(text),
        `the log says the node refused a block it did not refuse:\n${text}`);
    assert.ok(!/^error:/m.test(text),
        `ordinary proof of work was logged at ERROR:\n${text}`);
});

await test('a block the node really refuses is still an error, and still rejected', async () => {
    const { share, logged, rejected } = await runSubmit(
        outcomeOf(false, ['node: bad-txnmrklroot'],
                  [{ ok: true, error: null, result: 'bad-txnmrklroot' }]));

    assert.strictEqual(share.blockAccepted, false);
    assert.ok(!share.blockStale, 'a refused block was marked as a lost race');
    assert.strictEqual(rejected.length, 1,
        'a genuinely refused block no longer emits blockRejected');
    const text = logged.join('\n');
    assert.ok(/REJECTED/.test(text) && /refused/i.test(text),
        `a real refusal stopped saying so:\n${text}`);
});

console.log();
if (!fail.length) {
    console.log(`${GRN}${BLD}${pass} passed: the node is read the same way everywhere${OFF}\n`);
} else {
    console.log(`${RED}${BLD}${fail.length} failed${OFF}, ${pass} passed`);
    fail.forEach((f) => console.log(`  - ${f}`));
}
process.exit(fail.length ? 1 : 0);
})();

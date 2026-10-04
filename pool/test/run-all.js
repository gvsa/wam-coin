#!/usr/bin/env node
'use strict';
// Copyright (c) 2026 The WAM Coin developers
// Distributed under the MIT software license, see COPYING.
//
// ===========================================================================
//  Run every test in this directory -- which `npm test` did not
// ===========================================================================
//
//      node pool/test/run-all.js          (or: npm test, from pool/)
//
//  WHY THIS EXISTS
//
//  package.json said:
//
//      "test": "node test/rewards.test.js"
//
//  One file out of fourteen. It printed "ALL 53 TESTS PASSED" and exited 0
//  while payment-safety.test.js was failing three assertions on the same
//  checkout -- because nothing ran it. The payout tests, the maturation
//  tests, the API redaction tests and the block-count tests were all outside
//  what `npm test` meant by "test".
//
//  scripts/preflight.sh does loop over pool/test/*.test.js, so the gate before
//  a release was never blind. But `npm test` is what a contributor runs, what
//  an editor's test button runs, and what anybody reaches for after changing
//  one line -- and it answered for a thirteenth of the suite with the full
//  confidence of a green tick.
//
//  Found on 2026-10-03 while fixing the pool payout path: the fix broke two
//  fakes in files `npm test` does not read, and `npm test` stayed green.
//
//  A glob here rather than a list, for the reason this project keeps
//  rediscovering: a list of file names goes stale the next time somebody adds
//  one, silently, and in exactly the direction that hides a failure.
// ===========================================================================

const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const DIR = __dirname;
const files = fs.readdirSync(DIR)
    .filter((f) => f.endsWith('.test.js'))
    .sort();

if (files.length === 0) {
    console.error('no *.test.js files found in ' + DIR);
    process.exit(2);
}

const RED = '\x1b[31m', GRN = '\x1b[32m', BLD = '\x1b[1m', OFF = '\x1b[0m';
const failed = [];

for (const f of files) {
    const r = spawnSync(process.execPath, [path.join(DIR, f)], {
        stdio: ['ignore', 'pipe', 'pipe'], encoding: 'utf8'
    });
    const out = (r.stdout || '') + (r.stderr || '');
    if (r.status === 0) {
        console.log(`${GRN}ok${OFF}    ${f}`);
    } else {
        failed.push(f);
        console.log(`${RED}FAIL${OFF}  ${f}`);
        // The whole output, not a tail: a failure nobody can read is a
        // failure nobody acts on.
        console.log(out.split('\n').map((l) => '      ' + l).join('\n'));
    }
}

console.log();
if (failed.length === 0) {
    console.log(`${GRN}${BLD}all ${files.length} test file(s) passed${OFF}`);
} else {
    console.log(`${RED}${BLD}${failed.length} of ${files.length} test file(s) failed${OFF}`);
    failed.forEach((f) => console.log(`  - ${f}`));
}
process.exit(failed.length === 0 ? 0 : 1);

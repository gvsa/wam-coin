'use strict';
// Copyright (c) 2026 The WAM Coin developers
// Distributed under the MIT software license, see COPYING.
//
// A submitblock outcome in the shape daemon.js returns, with the verdict
// produced by the real classifier rather than written in by hand.
//
// block-spool.test.js carried hand-made outcomes until 2026-10-10. When the
// reading of the node's answer moved into daemon.js, those fakes went on
// asserting their own idea of it and three tests failed for the right reason.
// A fake that disagrees with the thing it stands in for tests nothing, so
// there is one builder and both files use it.
//
// Not named *.test.js on purpose: test/run-all.js runs everything that is,
// and this has no assertions of its own.

const { classifySubmit } = require('../lib/daemon');

function outcomeOf(accepted, reasons, results) {
    return {
        accepted,
        reasons,
        results,
        verdict: classifySubmit(accepted, reasons, results)
    };
}

module.exports = { outcomeOf };

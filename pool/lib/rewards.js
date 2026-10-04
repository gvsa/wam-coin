'use strict';
// Copyright (c) 2026 The WAM Coin developers
// Distributed under the MIT software license, see COPYING.
//
// ===========================================================================
//  Reward distribution -- PPLNS and PROP
// ===========================================================================
//
//  Deliberately pure functions over plain data: no Redis, no sockets, no
//  clock. Money splitting is the one part of a pool that absolutely must be
//  unit-testable in isolation, and it is tested in test/rewards.test.js.
//
//  ---------------------------------------------------------------------------
//  WHERE THE 5% TREASURY FEE IS ALREADY GONE
//  ---------------------------------------------------------------------------
//  `blockValue` passed in here is BlockTemplate.distributableValue, i.e.
//
//      coinbasevalue - devfee.amount
//
//  The treasury output was paid by the coinbase itself under consensus rule
//  WAM-1. The pool never holds it, never forwards it, and must never count it
//  as revenue. Passing the raw coinbasevalue in here would over-distribute by
//  5% and drain the pool's wallet over time -- so the functions below reject a
//  caller that looks like it made that mistake.
//
//  ---------------------------------------------------------------------------
//  PPLNS vs PROP
//  ---------------------------------------------------------------------------
//  PROP  : split a block among the shares submitted since the last block.
//          Simple and intuitive, but vulnerable to pool hopping -- a miner who
//          only mines the early part of each round earns above their fair
//          share at everyone else's expense.
//
//  PPLNS : split a block among the last N units of difficulty submitted,
//          regardless of round boundaries. Hopping stops being profitable
//          because leaving means forfeiting a share of every block that lands
//          before your work ages out of the window.
//
//  Default is PPLNS with N = 2 x network difficulty, the industry norm.

const { COIN } = require('./constants');

/**
 * Integer-safe proportional split.
 *
 * Every amount is in base units (watoshi). The remainder from integer division
 * is handed to the largest contributor rather than being dropped, so
 * sum(payouts) === amount exactly. Losing dust on every block silently
 * accumulates into a real balance discrepancy over thousands of blocks.
 *
 * @param {Map<string, number>} weights worker -> weight (any positive scale)
 * @param {number} amount base units to split
 * @returns {Map<string, number>} worker -> base units
 */
function splitProportionally(weights, amount) {
    const payouts = new Map();
    if (amount <= 0 || weights.size === 0) return payouts;

    let totalWeight = 0;
    for (const w of weights.values()) {
        if (w > 0) totalWeight += w;
    }
    if (totalWeight <= 0) return payouts;

    let distributed = 0;
    let largestWorker = null;
    let largestWeight = -1;

    for (const [worker, weight] of weights) {
        if (weight <= 0) continue;
        const share = Math.floor((amount * weight) / totalWeight);
        payouts.set(worker, share);
        distributed += share;
        if (weight > largestWeight) {
            largestWeight = weight;
            largestWorker = worker;
        }
    }

    const remainder = amount - distributed;
    if (remainder > 0 && largestWorker !== null) {
        payouts.set(largestWorker, payouts.get(largestWorker) + remainder);
    }

    return payouts;
}

/**
 * Take the most recent shares totalling `windowDifficulty` units of work.
 *
 * @param {Array<{worker,difficulty}>} shares newest first
 * @param {number} windowDifficulty
 * @returns {{weights: Map<string, number>, used: number, covered: number}}
 */
/**
 * How much work the PPLNS window covers. ONE definition, used by everyone.
 *
 * THE WINDOW AND THE BUFFER THAT FEEDS IT WERE COMPUTED SEPARATELY, AND THEY
 * DISAGREED BY A FACTOR OF TEN.
 *
 * This value decides how far back a block's payout reaches.
 * shareProcessor._pplnsBufferSize() decides how many shares are read out of
 * redis to satisfy it. They were two expressions in two files, and only one
 * of them had the `Math.max(1, ...)` floor -- so on 2026-10-04, with network
 * difficulty 0.003889 and a multiplier of 2:
 *
 *     the window asked for    difficulty 1        (the floor won)
 *     the buffer was sized for difficulty 0.00778 (the floor was absent)
 *     shares read             10,000
 *     shares needed           100,000
 *
 * The window was silently truncated to a tenth of what it asked for, and what
 * fell off the end was the OLDEST work -- so the miners it underpaid were the
 * ones who had been there longest.
 *
 * Reported by dang150296 (Urriki1502) as a PPLNS window mismatch, 2026-10-04.
 *
 * Two expressions of one quantity will disagree eventually; that is not a
 * thing to be careful about, it is a thing to stop doing. Both callers use
 * this, and pool/test/rewards.test.js holds them to it.
 *
 * AND THE FLOOR IS GONE, WHICH IS THE OTHER HALF OF THE SAME FAULT.
 *
 * It was `Math.max(1, networkDifficulty * pplnsMultiplier)`. A floor of 1 is
 * inherited reasoning from chains whose difficulty is in the billions, where
 * it can never bind. WAM's is 0.0039, so it bound always and was the only
 * thing deciding the window -- 129 times the rule this project publishes in
 * docs/POOL_OPERATOR.md and on the pool page:
 *
 *     window = multiplier x networkDifficulty
 *
 * That rule is what miners are told, and it is also right: multiplier x
 * network difficulty is "this many blocks' worth of work", which is what
 * PPLNS means everywhere. The floor was undocumented behaviour overriding
 * documented behaviour, which is the one thing this project does not do.
 *
 * No floor is needed for the degenerate case either. A networkDifficulty of
 * zero gives a window of zero, selectPplnsWindow then selects nothing, and
 * computeBlockRewards already falls back to the round's own contributions --
 * which is the correct answer when there is no difficulty to measure against.
 *
 * WHAT THIS CHANGES FOR MINERS, STATED RATHER THAN DISCOVERED: the window was
 * effectively the last 10,000 shares, because that is where the redis list was
 * trimmed. It is now about two blocks' worth of pool work. Payouts follow
 * recent work more closely and are less smoothed across a long tail. That is
 * what "2x network difficulty" has always said on the pool's own page.
 */
function pplnsWindowDifficulty(networkDifficulty, pplnsMultiplier) {
    const d = Number(networkDifficulty);
    const m = Number(pplnsMultiplier);
    if (!Number.isFinite(d) || !Number.isFinite(m) || d <= 0 || m <= 0) return 0;
    return d * m;
}

function selectPplnsWindow(shares, windowDifficulty) {
    const weights = new Map();
    let covered = 0;
    let used = 0;

    for (const share of shares) {
        if (covered >= windowDifficulty) break;

        // The share that straddles the window edge counts only for the part
        // that fits, otherwise the window silently grows past N.
        const remaining = windowDifficulty - covered;
        const credited = Math.min(share.difficulty, remaining);

        weights.set(share.worker, (weights.get(share.worker) || 0) + credited);
        covered += credited;
        used++;
    }

    return { weights, used, covered };
}

/**
 * Compute a block's payouts.
 *
 * @param {object} args
 *   mode              'pplns' | 'prop'
 *   blockValue        base units available to miners (devfee already removed)
 *   poolFeePercent    the POOL operator's fee, distinct from the chain's 5%
 *   shares            newest-first [{worker, difficulty}] (pplns)
 *   roundContributions Map worker -> difficulty (prop)
 *   networkDifficulty used to size the pplns window
 *   pplnsMultiplier   window = multiplier x networkDifficulty (default 2)
 *   coinbaseValue     optional: the FULL coinbase, used only for a sanity check
 *   devFeeAmount      optional: the consensus treasury amount, for the same check
 */
function computeBlockRewards(args) {
    const {
        mode = 'pplns',
        blockValue,
        poolFeePercent = 0,
        shares = [],
        roundContributions = new Map(),
        networkDifficulty = 1,
        pplnsMultiplier = 2,
        coinbaseValue = null,
        devFeeAmount = null
    } = args;

    // Zero is legal. Past the end of the emission schedule the subsidy is
    // exactly zero, and a block mined from an empty mempool distributes
    // nothing at all. Everyone is paid nothing, which is arithmetically fine
    // and is the correct answer; PPLNS shares live in a rolling window and are
    // not consumed by the round, so nobody loses credit for it either.
    //
    // Rejecting it means the pool stops accounting for blocks the moment the
    // subsidy runs out -- at height 6,600,000 on mainnet, and at height 4,950
    // on regtest, which is where this was found.
    if (!Number.isFinite(blockValue) || blockValue < 0) {
        throw new Error(
            `blockValue must be a non-negative number of base units, got ${blockValue}`);
    }

    // Guard against the single most damaging misuse of this function: handing
    // it the raw coinbasevalue instead of the distributable value.
    if (coinbaseValue !== null && devFeeAmount !== null) {
        const expected = coinbaseValue - devFeeAmount;
        if (blockValue !== expected) {
            throw new Error(
                `blockValue (${blockValue}) does not equal coinbaseValue - devFeeAmount ` +
                `(${coinbaseValue} - ${devFeeAmount} = ${expected}). The consensus treasury ` +
                'output must never be distributed to miners.');
        }
    }

    if (poolFeePercent < 0 || poolFeePercent >= 100) {
        throw new Error(`poolFeePercent must be in [0, 100), got ${poolFeePercent}`);
    }

    // The pool operator's own fee, taken from what is left after the chain's
    // treasury output. These two fees are completely independent.
    const poolFee = Math.floor((blockValue * poolFeePercent * 100) / 10000);
    const minerPot = blockValue - poolFee;

    let weights;
    let windowInfo = null;

    if (mode === 'prop') {
        weights = new Map(roundContributions);
    } else {
        const windowDifficulty = pplnsWindowDifficulty(networkDifficulty, pplnsMultiplier);
        windowInfo = selectPplnsWindow(shares, windowDifficulty);
        weights = windowInfo.weights;

        // Early in a pool's life, or right after a lucky block, there may be
        // less work in the buffer than the window asks for. Paying out only
        // `covered/window` of the block would strand the rest; instead the
        // whole block goes to whoever actually did the work.
        if (weights.size === 0) {
            weights = new Map(roundContributions);
        }
    }

    const payouts = splitProportionally(weights, minerPot);

    const totalPaid = [...payouts.values()].reduce((a, b) => a + b, 0);
    if (totalPaid !== minerPot && payouts.size > 0) {
        throw new Error(`payout accounting error: distributed ${totalPaid} of ${minerPot}`);
    }

    return {
        mode,
        blockValue,
        poolFee,
        minerPot,
        payouts,
        totalPaid,
        workers: payouts.size,
        window: windowInfo
            ? { requested: pplnsWindowDifficulty(networkDifficulty, pplnsMultiplier),
                covered: windowInfo.covered,
                sharesUsed: windowInfo.used }
            : null
    };
}

/**
 * Effective hashrate from a set of shares over a time span.
 *
 * hashrate = (sum of share difficulties x 2^32) / seconds
 *
 * The 2^32 is not a fudge factor: constants.DIFF1 is 2^224 - 1, so a share of
 * difficulty 1 is one hash in 2^256 / 2^224 = 2^32. The two numbers are one
 * decision expressed twice, and they have to move together.
 */
function estimateHashrate(shares, windowSeconds) {
    if (!shares.length || windowSeconds <= 0) return 0;
    const totalDifficulty = shares.reduce((sum, s) => sum + s.difficulty, 0);
    return (totalDifficulty * 4294967296) / windowSeconds;
}

function formatHashrate(hs) {
    const units = ['H/s', 'kH/s', 'MH/s', 'GH/s', 'TH/s'];
    let i = 0;
    while (hs >= 1000 && i < units.length - 1) { hs /= 1000; i++; }
    return `${hs.toFixed(2)} ${units[i]}`;
}

function formatWam(baseUnits) {
    return (baseUnits / COIN).toFixed(8);
}

module.exports = {
    splitProportionally,
    pplnsWindowDifficulty,
    selectPplnsWindow,
    computeBlockRewards,
    estimateHashrate,
    formatHashrate,
    formatWam
};

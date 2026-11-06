'use strict';
// Copyright (c) 2026 The WAM Coin developers
// Distributed under the MIT software license, see COPYING.
//
// ===========================================================================
//  fakeAtomic.js -- one definition of the atomic claim for the test doubles
// ===========================================================================
//
//  WHY THIS FILE EXISTS
//
//  Six test files build their own Redis double, each knowing the subset of
//  commands its own test needs. On 2026-10-12 the pool started requiring one
//  more -- wamClaimAndRecord, the script that moves a block out of
//  blocks:pending and records the evidence in the same breath -- and all six
//  stopped at the constructor with the same message.
//
//  That is the guard working: pool/lib/atomic.js refuses a client that cannot
//  run the script, because a fallback to the two-command version is the
//  defect reachable by configuration. But six copies of the fix would be six
//  chances to write it differently, in doubles whose whole job is to behave
//  like the thing they stand in for.
//
//  So the command has one definition here, and two shapes:
//
//    attachAtomic      -- the real behaviour, over the double's own store
//    attachUnsupported -- a method that THROWS when called
//
//  The second is for doubles that do not model blocks:pending at all. A stub
//  that quietly returned 1 would let a test pass while proving nothing, which
//  is the failure this project has been bitten by more than once: a check
//  that could not look, reporting that it had looked. If one of those tests
//  ever does reach maturation, it stops and says the double is the problem.
// ===========================================================================

const { CLAIM_AND_RECORD_NAME } = require('../lib/atomic');

/**
 * Give a double the real command, over the maps it already uses.
 *
 * @param fake  the double
 * @param hash  (key) => Map, the double's own hash store
 * @param list  (key) => Array, the double's own list store
 *
 * Atomic for free: there is no await inside, so nothing can interleave
 * between the delete and the push. That is exactly the property the Lua
 * script buys on a real server.
 */
function attachAtomic(fake, hash, list) {
    if (typeof hash !== 'function' || typeof list !== 'function') {
        throw new Error('attachAtomic needs the double\'s hash and list accessors');
    }
    fake[CLAIM_AND_RECORD_NAME] =
        async (pendingKey, listKey, field, evidence) => {
            if (!hash(pendingKey).delete(field)) return 0;
            list(listKey).unshift(evidence);
            return 1;
        };
    return fake;
}

/**
 * Give a double a command that refuses to pretend.
 *
 * @param why  what this double does not model, in the error a reader sees
 */
function attachUnsupported(fake, why) {
    fake[CLAIM_AND_RECORD_NAME] = async () => {
        throw new Error(
            `${CLAIM_AND_RECORD_NAME} was called on a double that does not ` +
            `model it: ${why}. Nothing was asserted. Use attachAtomic from ` +
            'pool/test/fakeAtomic.js with this double\'s own stores, rather ' +
            'than trusting whatever this call would have returned.');
    };
    return fake;
}

module.exports = { attachAtomic, attachUnsupported, CLAIM_AND_RECORD_NAME };

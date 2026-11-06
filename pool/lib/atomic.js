'use strict';
// Copyright (c) 2026 The WAM Coin developers
// Distributed under the MIT software license, see COPYING.
//
// ===========================================================================
//  atomic.js -- the one state change that must not be interruptible
// ===========================================================================
//
//  WHY THIS FILE EXISTS
//
//  A block this pool found exists in exactly one place between finding it and
//  paying for it: the blocks:pending field that holds its payout table. The
//  round's shares -- the raw record of who did the work -- are deleted in the
//  same breath that writes it:
//
//      pipe.hset(this.k('blocks:pending'), share.blockHash, ...)
//      pipe.del(this.k('round'));           // PROP round closes here
//
//  So that one field is not a copy of anything. It is the only surviving
//  statement of what every miner in the round is owed, and nothing anywhere
//  can reconstruct it.
//
//  Maturation then moved the block out of pending in two separate commands:
//  HDEL first, because the delete is what makes exactly one caller the
//  winner, and LPUSH of the evidence second. Between those two awaits the
//  block belonged to no state at all -- deleted from pending, absent from
//  maturing, not credited -- and a crash, a dropped connection or a Redis
//  failover in that window destroyed the payout table outright. The coins sat
//  in the pool's wallet and nobody, not the pool and not an operator by hand,
//  could say whose they were.
//
//  The code knew about the window and argued for it:
//
//      Losing a credit is recoverable; paying it twice is not, so the
//      order is deliberate.
//
//  The second half is true. The first half was not, and that is the whole
//  defect: a deliberate trade-off resting on a premise that the line
//  deleting blocks:round had already falsified. There was no recovery to
//  fall back on.
//
//  Reported by Smooth Jazz Crypto (@smoothjazcrypto) on 2026-10-12 against 87ac8f0, with the fix: make the
//  transition one server-side operation. Redis runs a script to completion
//  before anything else, so there is no window to crash in. The same shape
//  was in _orphan, which this covers too -- found while fixing this one, not
//  reported.
//
//  WHY NOT MULTI/EXEC
//
//  MULTI/EXEC is atomic in execution but cannot branch: the "exactly one
//  winner" rule depends on reading what HDEL returned and only then writing
//  the evidence, and inside a transaction that return value is not available
//  until the whole thing has run. WATCH with a retry loop would work and is
//  more moving parts than a four-line script.
//
//  WHY NO FALLBACK
//
//  defineAtomicCommands throws if the client cannot take the script. A
//  fallback to the two-command version would be the defect, back again,
//  reachable by configuration -- and silent, because the window only opens
//  when something else is already going wrong.
// ===========================================================================

/**
 * Move one field out of a hash and record it in a list, or do neither.
 *
 * KEYS[1]  the hash holding the claim      (blocks:pending)
 * KEYS[2]  the list that keeps the evidence (blocks:maturing, blocks:orphaned)
 * ARGV[1]  the field                        (the block hash)
 * ARGV[2]  the evidence                     (the record, serialised)
 *
 * Returns 1 if this caller claimed it, 0 if somebody else already had.
 *
 * HDEL first so the return value decides, exactly as the two-command version
 * did -- the difference is that nothing can run between the two lines.
 */
const CLAIM_AND_RECORD = `
if redis.call('HDEL', KEYS[1], ARGV[1]) ~= 1 then
  return 0
end
redis.call('LPUSH', KEYS[2], ARGV[2])
return 1
`;

/** The name the pool calls it by, on the client and on any test double. */
const CLAIM_AND_RECORD_NAME = 'wamClaimAndRecord';

/**
 * Teach an ioredis client the scripts this pool needs, once.
 *
 * Idempotent: a client that already has the command is left alone, so a
 * second ShareProcessor over the same client is not an error.
 */
function defineAtomicCommands(redis) {
    if (!redis) {
        throw new Error('defineAtomicCommands: no redis client');
    }
    if (typeof redis[CLAIM_AND_RECORD_NAME] === 'function') {
        return redis;
    }
    if (typeof redis.defineCommand !== 'function') {
        throw new Error(
            `this redis client has neither ${CLAIM_AND_RECORD_NAME} nor ` +
            'defineCommand, so the pending-to-evidence transition cannot be ' +
            'made atomic. Refusing to run: the two-command version loses a ' +
            "block's entire payout table if it is interrupted between them, " +
            'and the round shares that would rebuild it are already gone.');
    }
    redis.defineCommand(CLAIM_AND_RECORD_NAME, {
        numberOfKeys: 2,
        lua: CLAIM_AND_RECORD
    });
    return redis;
}

module.exports = {
    defineAtomicCommands,
    CLAIM_AND_RECORD,
    CLAIM_AND_RECORD_NAME
};

# What privacy threat model makes sense for WAM?

*Opening post for the GitHub discussion asked for in #general-chat. Written in
answer to dang150296's comparison of Monero, Zcash and Dash.*

You asked the question in the right order. Most privacy discussions pick a
technology and reason backwards to a threat; yours starts where it should.

Two facts about this chain narrow the answer, and neither is visible from
outside, so they are worth putting on the table before anybody argues about
ring signatures.

## What the chain already has and nobody is using

SegWit and Taproot are active from block 1. Not deployed later, not waiting
on miner signalling — `chainparams.cpp` sets both as always-active buried
deployments, so every block this chain has ever had enforces them. Every
address the wallet hands out is bech32m: `wam1p…`.

That means key-path Taproot spends, descriptor wallets, and the node's
existing Tor support are all present today and essentially unused.

It also means the largest practical privacy loss on this chain right now is
address reuse, which costs nothing to stop and needs no consensus change, no
research and no proposal.

## Two properties that constrain the base layer

WAM has two properties that the three models you compared do not all have.
Any shielded design trades at least one of them away, and that trade should
be stated before it is made, not discovered afterwards.

**Auditable supply.** The 22,000,000 cap and the 5% treasury rule are
enforced in consensus and are publicly countable by anyone running a node,
because amounts are transparent. The treasury rule is checked from block 1
onward, which is why a node that disagrees about it forks itself off
immediately rather than quietly.

Both Monero and Zcash have had supply-integrity bugs that survived for a
long time, and in both cases the reason is structural rather than careless:
the flaw hides inside the machinery that hides the amounts, so the usual
check — add up the coins and compare with the schedule — is not available.
A chain whose claim is auditable monetary discipline pays for shielding with
exactly that claim.

**Native atomic swaps.** They are HTLCs in Bitcoin script. A shielded output
cannot take part in a swap with a counterparty coin that does not understand
it, and that is every coin we would want to swap with. Shielding the base
layer removes non-custodial exchange — which is the reason the listing work
has gone to Block DX, BasicSwap and Bisq rather than to custodial venues.

Neither of these is an argument that privacy does not matter. They are the
bill, and it should be read.

## The threat model, concretely, for this chain today

The realistic adversary right now is not commercial chain analysis. The chain
is weeks old and small; nobody is selling analysis of it, and by the time
somebody is, the answer chosen today will have been rewritten anyway.

The exposures that exist today are network-level and operational:

* **node IPs** — on a network this size, observing which node first relays a
  transaction is a better deanonymiser than anything on-chain, and it needs
  no cryptography to defeat, only Tor
* **the pool's payout pattern** — regular payouts from one address to a fixed
  set of addresses is a public map of who mines here
* **the explorer** — a public explorer makes address clustering trivial for
  anyone merely curious, which is a far lower bar than a chain-analysis firm

Those three are real, present, and fixable at the wallet and node layer.
None of them needs a consensus change.

## A suggested ordering

1. Stop reusing addresses. Document it. It is the whole of the low-hanging
   fruit.
2. Document Tor for node operators. The node already supports it.
3. Look at PayJoin or a wallet-layer coinjoin, where nothing in consensus
   moves and the guarantee is honest about being weaker.
4. Treat base-layer shielding as needing, in this order: a written threat
   model, a comparison of existing designs, a testnet prototype, external
   review — and only then a proposal. Which is what you said.

## One question to add to your list

If amounts become private, how does anyone verify the 22M cap and the 5%
treasury rule **without trusting us**?

That is not rhetorical and it is not a veto. Zcash's turnstile accounting and
Monero's audit work are both attempts at it, and neither gives what a
transparent chain gives for free. But it has to be answered before the rest
of the list, not after — because if the answer is "trust the developers",
then the privacy upgrade has quietly replaced the property this chain was
built for.

## The research that would help most right now

Narrower than the three-way comparison, and both answerable without touching
consensus:

* What does Taproot already give us that we are not using?
* What does a wallet-layer coinjoin cost on a chain with this block time and
  this fee market?

Either would be a real contribution, and neither requires anybody's
permission to start.

---

*Nothing here is a decision. The chain has no roadmap commitment on privacy,
and this document does not create one. It is an attempt to put the two
constraints on the table so the discussion is about trades rather than
preferences.*

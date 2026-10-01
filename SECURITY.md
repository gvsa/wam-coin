# Reporting a security issue

**Email: wam.coin.official@proton.me**

Please do not open a public issue for a security problem. Do not post it in the
Discord, and do not describe it on a forum. A consensus bug that is public
before it is fixed is a bug every node on the network is exposed to at once.

You will get an acknowledgement. If you do not hear anything within 72 hours,
send the mail again — assume it was lost, not ignored.

---

## What counts

Anything that would let someone:

* create WAM outside the emission schedule, or spend coins they do not own
* make honest nodes disagree about which chain is valid
* crash or stall a node from the network, or from a crafted block or transaction
* take a block reward that the treasury rule reserves, or bypass the time locks
  on the founder reserve
* steal from a mining pool built on `pool/`, or from a miner running `miner/`

Also worth reporting, though less urgent: a way to make the node leak
information about its wallet or its peers, and anything in `scripts/` that
could expose a private key.

Denial of service that requires more resources than it costs the attacker is
interesting. A report that amounts to "I sent 10 Gbit/s at it" is not.

## What to send

Enough to reproduce it. A patch is welcome but not required — a clear
description of the mechanism is worth more than a proof of concept we cannot
follow. If you have exploit code, send it; it will not be published.

State whether you want to be credited, and how.

## What happens next

**The published tiers, paid in mainnet WAM.** These were announced before
launch, on BitcoinTalk and in the channels:

| | |
|---|---|
| Inflation beyond the 22,000,000 cap, or a way past the treasury rule | 50,000 WAM |
| A consensus split, or a remote crash of nodes | 15,000 WAM |
| Theft of funds held by software in this project | 12,500 WAM |
| Credit without entitlement — paying out coins nobody earned | 10,000 WAM |
| Bulk deanonymisation of miners or users | 2,500 WAM |
| Denial of service against the pool, the explorer or a seed | 1,000 WAM |
| Hardening, a misconfiguration, or a document that misleads | 250 WAM |

They are a floor and not a ceiling: a finding that matters more than its rung
can be paid more than its rung, and if that happens it will be said plainly
that it was a judgement and not a tier.

**What changed on 1 October 2026, and what did not.** The table above was
three rows, and its top row held three different things at one price:
a consensus split, inflation past the cap, and theft of pool funds. They are
not one thing. Coins created out of nothing cannot be taken back without a
reorganisation nobody would accept; pool funds are bounded and can be
replaced. So the top rung now names only the one that cannot be undone, and
keeps its number. **No published amount was reduced.** The middle rung rose
from 10,000 to 15,000, deanonymisation rose from 1,000 to 2,500, and the
classes that previously had no rung of their own now have one — which tells a
reviewer where to look, and that brings more reports rather than fewer.

**Findings already accepted keep the classification they were given.** The
10,000 and the 1,000 below were judged under the three-row table and are not
re-read against this one.

**One payment per root cause, not per symptom.** Three reports that are three
faces of one state machine are one finding, which is how the 10,000 below was
handled. And the amount follows the impact, not the effort: one line that
reveals an inflation bug is worth the top rung, and a month of reading that
finds nothing is worth thanks.

**What does not qualify**, said rather than left to be discovered: a
theoretical bug with no demonstrated path; anything that needs the operator's
own key or physical access; software this project did not write; social
engineering; and denial of service by raw volume, which anybody can do to
anything.

This file said the opposite of all of it until 2026-09-14 — "there is no bug
bounty" — while three other places in the repository said "there is a bounty"
and linked here. A reviewer followed our own sentence to our own file and found
it contradicted. He was right and the file was wrong.

**Nothing has been paid yet.** Between 14 and 15 September this paragraph
claimed the opposite: that 1,000 WAM had already been paid to the reviewer who
found the pool API leaking payout addresses, bought from a miner at a price the
miners set in public, with the offers, the price and the transaction published.
None of that had happened. Mainnet did not exist when the sentence was written,
so there were no mainnet coins to pay with and no price for anyone to have set.
It was written here in error and stood for a day, including on
wamcoin.org/security.

## Where the money comes from

**The operating treasury** — 5% of every block subsidy for heights 1 to
400,000, paid by consensus rule WAM-1 and designated in the whitepaper for
listings, audits and infrastructure.

    WdMMqW1DcgWZ6HtyJuEMdce6QkKg4raGmE

Check it rather than believe it, from any node:

    wam-cli scantxoutset start '["addr(WdMMqW1DcgWZ6HtyJuEMdce6QkKg4raGmE)"]'

At height 4,989 that returned 4,788 unspent outputs totalling 11,972.49400520
WAM. One output per block, and it accrues 1,800 WAM per day.

**It has moved once.** This paragraph said "the treasury has never moved a
coin since block 1", and that was true until 2026-09-22, when 500 WAM went to
a GLEEC maintainer so he could run an atomic-swap test on a pull request he
had opened and fixed himself. Not a listing fee — none was asked for and none
was paid. Every coin that leaves the treasury is recorded with its amount, its
reason and its transaction id in
[docs/TREASURY_LEDGER.md](docs/TREASURY_LEDGER.md), and the balance above can
be checked against the chain with the command above rather than believed.

**The source changed, and this is the record of it.** The announcement on
BitcoinTalk said the tiers would be paid "from the founder reserve". That
reserve is locked by consensus until 2027-09-15 — five outputs of 400,000 WAM
behind OP_CHECKLOCKTIMEVERIFY in the genesis coinbase, readable with
`wam-cli getblock $(wam-cli getblockhash 0) 2` — so it cannot pay anything
today, and the founder has committed in public not to pay from it in any case.
Until 17 September this file said the new source "has not yet been decided"
while the project was telling a reviewer by email that it was the treasury. He
found the contradiction and asked for the public reference. He was right to.

**The ceiling, and it is a number rather than a feeling.** The treasury is
750,000 WAM over its entire life — 2.5 WAM a block to height 200,000 and 1.25
to height 400,000 — and then nothing, ever. It also has to keep this network
running, which comes first, because a chain with no nodes has nothing worth
securing.

**This programme's share of it is one eighth: 93,750 WAM, for the whole life
of the programme.** 11,000 of that is already committed to the two findings
below. One of every class in the table above comes to 91,250, so the table is
payable even if every class is found — which is the test a promise has to
pass before it is made.

**When the eighth is spent, the programme closes and this file says so.** It
is not left open and unfunded. The ceiling can be raised later by announcement
and will never be lowered for a finding already accepted.

**Priority is the order of validation** — first validated, first paid. A rule
rather than a judgement, because the alternative is a queue whose order the
payer decides.

## Accepted findings

**10,000 WAM — pool accounting, accepted 16 September 2026, unpaid.**

Three related reports: the same pending block could mature more than once,
crediting miner balances twice out of the pool operator's own wallet, plus two
further manifestations of the same accounting fault. Found before launch and
fixed in `pool/lib/shareProcessor.js`; held down by
`pool/test/maturation-claim.test.js`.

Classified at 10,000 and not at 50,000, with the reasoning in full because a
tier decision without one is just a number: the 50,000 rung says *theft of
pool funds*, and nobody took the funds. The money left the operator's wallet
twice to legitimate miners, and the trigger was an operator restart during a
maturation check rather than anything an attacker could cause — which the
reporter stated himself before we did. It is a loss of pool funds, not a theft
of them, and stretching our own published word would cost more than the
difference. Nor is it the base rung: three reports in the money path, before
launch, which would have drained the operator's wallet with nothing in the logs
looking wrong. 10,000 is a judgement on severity rather than a reading of the
rung's wording, and is recorded as such.

**1,000 WAM — the pool API leak, accepted 13 September 2026, unpaid.** Three of
four `/api/*` endpoints returned every miner's full payout address while the
pool's own page said otherwise. Fixed at the response boundary in
`pool/lib/api.js`; held down by `pool/test/api-redaction.test.js`.

When each is paid, the amount, the reason for the amount and the transaction id
are published here, and nothing is announced before it exists.

Alongside it, and worth more in most cases: a real answer from someone who
read your report, credit in the release notes in whatever name you choose, and
a fix.

For anything that affects consensus or funds, the fix is written and tested
before it is described publicly. Once it is released, the report is published
in full, including the timeline and the name of whoever found it.

## Scope

This repository: the node (`src/`), the reference miner (`miner/`), the mining
pool (`pool/`), the explorer (`explorer/`), and the tooling in `scripts/`.

WAM is a fork of Bitcoin Core v28.1. A vulnerability in unmodified upstream code
should go to [Bitcoin Core's security process](https://bitcoincore.org/en/contact/)
first — they maintain it, and every fork including this one benefits from
disclosure to them. Send it here too if you believe WAM's changes make it worse.

## The signing key

Its fingerprint goes here — on this line, in this file, in this repository,
and in no other place:

```
4BD4 A8D3 AFD4 3F5C BCB5  00E2 3798 462F E00A DBA4
```

```
WAM Coin (release signing) <wam.coin.official@proton.me>
RSA 4096 · created 2026-09-03 · expires 2031-09-02
```

The public key is [SIGNING-KEY.asc](SIGNING-KEY.asc) in this repository.

**Anyone quoting a WAM fingerprint from anywhere other than this file is
quoting an invention.** Not from an email, not from a chat message, not from a
forum post, and not from a copy of this repository hosted somewhere else.
Check it at https://wamcoin.org/security/, over HTTPS, on a domain this
project controls -- not on a service that can take it away.

### What it signs, and what that is worth

Every release carries `SHA256SUMS` and `SHA256SUMS.asc`. The first lists the
hash of each file; the second is a signature over that list.

A checksum file on its own protects against a corrupted download and nothing
else: whoever can replace the binary can replace the list beside it, and both
will agree. The signature is what a stranger cannot forge without this key.

To check a download:

```
gpg --import SIGNING-KEY.asc
gpg --verify SHA256SUMS.asc SHA256SUMS
curl -LO https://wamcoin.org/downloads/v0.1.11/SHA256SUMS.asc
curl -LO https://wamcoin.org/verify_release.sh
curl -LO https://wamcoin.org/SIGNING-KEY.asc
bash verify_release.sh .
```

or run [scripts/verify_release.sh](scripts/verify_release.sh), which does the
three and refuses to say "ok" unless all three pass.

`gpg --verify` printing `Good signature` with a `WARNING: This key is not
certified with a trusted signature` is the normal and expected result. It
means the signature is genuine and that you have not personally vouched for
the key — which nobody should, on first contact. The fingerprint above is what
you check instead.

### The key is not on any server this project runs

It was generated on the founder's own machine and exists in two places: that
machine, and an offline backup. No node, no seed, no pool and no build server
has ever held it. A server that is compromised cannot be used to sign a
release, which is the entire point of keeping it off them.

A revocation certificate was created in the same session and is stored apart
from the key. If this fingerprint ever changes, or a revocation is published,
treat every release signed after that moment as untrusted until this file
says otherwise.

### CHANNELS.txt

[CHANNELS.txt](CHANNELS.txt) lists the project's official channels, and a list
of accounts that vouch for each other is only as strong as the weakest of
them: take one, repoint it at three impostors, and the mutual linking now
argues *for* the attacker. A detached signature over CHANNELS.txt removes
that. The reader stops needing to trust any account and only needs the one
fingerprint above.

## PGP mail

Mail is accepted in plain text. The key above is for signing releases; if you
need to encrypt a report before sending it, say so in a first message with no
details.

---

*Last reviewed: 2026-08-11*

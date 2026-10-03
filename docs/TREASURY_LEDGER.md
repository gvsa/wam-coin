# Treasury ledger

Every coin that leaves the treasury, with the amount, the reason and the
transaction id. Nothing else belongs here and nothing is left out of it.

`docs/TREASURY_CUSTODY.md` promised this and named what it must contain:
*every sweep: the transaction id, the amount, the resulting balance · monthly:
what was spent and on what, in one short note · never: a key, a descriptor, or
a photograph of any part of either.*

**The address, so nothing here needs to be taken on trust:**

    WdMMqW1DcgWZ6HtyJuEMdce6QkKg4raGmE

Check any line below against your own node:

    wam-cli getrawtransaction <txid> true
    wam-cli scantxoutset start '["addr(WdMMqW1DcgWZ6HtyJuEMdce6QkKg4raGmE)"]'

The second command answers with the balance as the chain holds it. If it
disagrees with the last line of this table, this file is wrong and the chain
is right.

---

## The arithmetic anyone can repeat

Consensus rule WAM-1 pays the treasury 5% of the block subsidy — 2.5 WAM per
block at the current subsidy — once per block, for heights 1 to 400,000. So
the balance at any height is:

    2.5 × height  −  everything in the table below

At height 4,989 that is `2.5 × 4989 − 500 − 0.00599480 = 11,972.49400520`,
which is what `scantxoutset` returns. Two independent routes to the same
number, to the last decimal place.

---

## Spends

| date | amount | to | reason | txid |
|---|---|---|---|---|
| 2026-09-22 | **500.00000000 WAM** | `WgsySSWQr1tRyjwj3S53XbiVz9yEUCCK9t` | Coin for an atomic-swap test on GLEEC PR #2034, at the maintainer's own request. Not a listing fee: none was asked for and none was paid, and the decision to merge is his. | txid `ac06a7af6d87eed56fda28898e483d67b1033365f4d5f744e59ec5f80b5f0605` |
| 2026-10-01 | **10.00000000 WAM** | `WcQCFiCzwikQTTmPeafn73e3asC32ofyLr` | Security bounty to chovy, accepted 16 September 2026: the pool accounting finding — the same pending block could mature more than once, crediting miner balances twice out of the operator's own wallet, plus two further manifestations of the same fault. Classified at 10,000 WAM under the tiers published at the time. Paid in nine transactions because consensus pays the treasury 2.5 WAM per block, so its balance is thousands of small outputs: 10,000 in one transaction would be about 4,000 inputs and 590 KB, six times the standard size limit, which no node would relay. 1 of 9 — the test payment, sent first and confirmed received before the rest. | txid `871e0f9e6e431ba2bae5a35777a8f739c83b8ceafc55a4fe94c5317a3262b5bd` |
| 2026-10-01 | **1248.75000000 WAM** | `WcQCFiCzwikQTTmPeafn73e3asC32ofyLr` | Same bounty, 2 of 9. | txid `a52d1d2f77ca2160d3126aaa41d1dc2a3ede4d23acf6661f0d7cd51b58b69f51` |
| 2026-10-01 | **1248.75000000 WAM** | `WcQCFiCzwikQTTmPeafn73e3asC32ofyLr` | Same bounty, 3 of 9. | txid `7f34f4e1e07e01b12595a6d74bf511003f06422d2e26e1b51a04948840d3f1d4` |
| 2026-10-01 | **1248.75000000 WAM** | `WcQCFiCzwikQTTmPeafn73e3asC32ofyLr` | Same bounty, 4 of 9. | txid `b0031f8c0ee779e2d2d4a20d30c763b0b482d6b7b3c55386264395eec78a13af` |
| 2026-10-01 | **1248.75000000 WAM** | `WcQCFiCzwikQTTmPeafn73e3asC32ofyLr` | Same bounty, 5 of 9. | txid `1692852e9ce0063b77b1ec81924017dfce1406fda5a68cb80e70c57196b39899` |
| 2026-10-01 | **1248.75000000 WAM** | `WcQCFiCzwikQTTmPeafn73e3asC32ofyLr` | Same bounty, 6 of 9. | txid `390d112403b914545f721d4328b032c7ae2d7a019ff7b96948ca7da16575e9fc` |
| 2026-10-01 | **1248.75000000 WAM** | `WcQCFiCzwikQTTmPeafn73e3asC32ofyLr` | Same bounty, 7 of 9. | txid `1bfef00cf093fdbdfb04e23f3d2c2ed261fec4160db06a09598117425501ca04` |
| 2026-10-01 | **1248.75000000 WAM** | `WcQCFiCzwikQTTmPeafn73e3asC32ofyLr` | Same bounty, 8 of 9. | txid `e8ace6f3a2a951e24be887d7a10b8773e9b4269e4911dd5ce43256d95029a666` |
| 2026-10-02 | **1248.75000000 WAM** | `WcQCFiCzwikQTTmPeafn73e3asC32ofyLr` | Same bounty, 9 of 9. | txid `7c87c49a9bd35d0b75d4271febb3cb864d104068285bafbc4ab8f6b59ae19fa3` |

Fee paid on that transaction: `0.00599480 WAM`, on 202 inputs and 29,974
bytes. The treasury is paid one output per block and never consolidated, so a
500 WAM spend is 202 of them.

**Balance after it:** `11,972.49400520 WAM` in 4,788 unspent outputs, at
height 4,989.

---

## What this was, and what it was not

The transaction above is the **first movement of the treasury since block 1**.
Until 2026-09-22 every coin WAM-1 had ever paid it was still sitting where it
arrived — 4,946 outputs, none of them spent, which anybody could and did
verify.

It was not a payment for a listing. The rule against those is in
`docs/LISTING_PACKAGE.md` and has not changed: this project does not pay a
platform to be listed. What was sent is the coin needed to *run* a test — a
maintainer who holds none of a coin cannot trade it against anything — and he
asked for it himself, in public, on a pull request he had opened and fixed on
his own initiative.

## How it was signed

The treasury is a single key until the 2-of-3 arrangement exists, so the key
never touched a networked machine:

1. the transaction was built on the node, where the chain is
2. it was signed on a machine with its network interface switched off
3. the signature was carried back and broadcast

`scripts/treasury_spend.py` does the three steps and refuses to send a signed
transaction whose destination, amount, change address, input count or fee
disagrees with the plan it was built from.

## Still outstanding

**The first sweep to a 2-of-3 address is due 2026-09-29**, fourteen days after
launch, as `docs/TREASURY_CUSTODY.md` states. It has not happened. Until it
does, this balance sits behind one key, and that is written here rather than
left for someone to notice.

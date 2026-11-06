# Where every listing request stands

Measured from the GitHub API on 2026-09-19, and the three rows that moved
re-measured on 2026-10-30, not recalled. Nine requests were opened; this is
what became of them and what, if anything, is owed.

| repo | # | state | what happened |
|---|---|---|---|
| satoshilabs/slips | 2051 | **merged** | coin type 5718349 and prefixes wam/twam/wamrt, 26 August |
| blocknetdx/blockchain-configuration-files | 197 → 199 → **200** | **open** | 197 superseded by 199 when the first account closed; 199 went down with the account that pushed it; recovered and reopened as #200 on 30 October |
| MetacoSA/NBitcoin | 1362 → **1369** | **open** | opened 19 October, went down with the account that pushed it, recovered and reopened as #1369 on 30 October |
| KomodoPlatform/coins | 21, 23 | gone, not reopened | the obsolete mirror. Its maintainer confirmed on 1 October that GLEEC's registry replaced it, and WAM is already merged there |
| GLEECBTC/coins | 1975 → **2034** | **MERGED 2026-09-22** | cipig fixed the conflicts himself, opened #2034, ran the first WAM swap and merged it. WAM is live on dex.gleec.com. #1975 closed as superseded |
| GLEECBTC/coins | **2077** | **MERGED 2026-10-30** | the merged entry's `links.github` started answering 404 when the account that pushed it was suspended. One line, opened 13:05Z and merged by cipig at 13:20Z |
| basicswap/basicswap | 701 | closed | "Mainnet is scheduled for 2026-09-15" — a deferral, not a refusal |
| bisq-network/bisq | 8030 | closed | he could not find the project — only the BEP-20 gaming token — and the ticker conflicts with it |
| haveno-dex/haveno | 2528 | closed | "We only consider coins with market traction / price" — the only market condition anyone set |
| bisq #8028, haveno #2527 | | closed | replaced by our own later PRs, no comments, not refusals |

## A suspended account takes its pull requests down — and the venue keeps the commits

On 29 October 2026 the account that had pushed every one of these submissions
was suspended. A suspended account's pull requests return 404 to everyone, in
other people's repositories, merged ones included, and GitHub's search refuses
the author outright (HTTP 422, *the listed users cannot be searched*). Two
reviews that were open — blocknetdx #199 and NBitcoin #1362 — simply vanished
from the world while the maintainers were still looking at them.

What survived: **a pull request's commits live in the repository it was opened
against, not in the fork it was pushed from.** GitHub keeps them under
`refs/pull/<n>/head`, and that ref outlives the fork's deletion and its owner's
suspension.

    git clone https://github.com/blocknetdx/blockchain-configuration-files.git
    git fetch origin refs/pull/199/head:pr199

Both came back whole — every commit, message and author — so the resubmissions
are the same commits pushed from `wamcoin-Project`, not rewrites from memory.
Checked before trusting them: each branch still merged cleanly onto the current
master, and the Block DX conf files were byte for byte what `integration/blockdx/`
holds. The only thing added was one commit naming v0.1.11 and v0.1.12 in the
manifest, both shipped since #199 was opened.

Merged work was never at risk: the lines stay in the files whatever becomes of
the author. `slip-0044.md`, `slip-0173.md` and GLEEC's `coins` all still carry
WAM.

**Actions are disabled on both forks.** No build of this project runs on GitHub
again, so a fork carrying somebody else's workflows gets them switched off
before a branch is pushed to it.

## GLEEC is done — merged 2026-09-22, and WAM is live on dex.gleec.com

**The first listing this project has ever had, and it is non-custodial.** WAM
appears in the assets list at dex.gleec.com between Venice Token and Waves,
with no price beside it while Waves shows $0.28 and Worldcoin $0.46. That is
not an oversight.

What happened, in order: cipig fixed the conflicts in #1975 himself rather
than asking us to, opened **#2034** under his own name, added the coinpaprika
and livecoinwatch ids nobody had asked for, requested coin for a swap test,
ran the first WAM swap ever — 249.68 WAM against Litecoin, completed in
10m31s — argued the confirmation depth down from 60 on measured grounds, set
it to 15, merged, and closed #1975 as superseded.

No listing fee was asked for and none was paid. 500 WAM went to him for the
swap test, at his request, recorded in docs/TREASURY_LEDGER.md with its txid.

`gleec-2034.txt` was the reply and it has been sent. `gleec-1975.txt` is dead.

## And a merged entry goes stale on its own — #2077, merged in fifteen minutes

The entry cipig merged carries `links.github`, and on 2026-10-29 the account
it named was suspended. So the one venue where WAM actually trades was
sending anyone who pressed *source* to a 404, and nothing on our side would
have noticed: it was `scripts/check_listing_entry.py` in the sweep that said
so, comparing the live file at `GLEECBTC/coins/master/coins` against ours.

[`#2077`](https://github.com/GLEECBTC/coins/pull/2077) is the fix, and it is
one line in a file of 772 entries — `wamcoin-core-dev` → `wamcoin-Project`.
Nothing else moved: `rpcport`, the prefixes, `required_confirmations` 15 and
the derivation path are all as merged in #2034. Actions were disabled on the
fork before the branch was pushed, and it inherited two workflows; zero runs.

**Opened 13:05Z, approved and merged by cipig at 13:20Z** — fifteen minutes,
the third time he has merged for this project. The live file now reads
`wamcoin-Project` and the URL answers 200. That speed is the argument for
sending the one-line request rather than asking in a comment and waiting:
the comment route took from 25 September to 1 October, and this took a
quarter of an hour.

**A listing is not a thing you finish.** Every entry in every registry holds
URLs that were true on the day they were merged, and the maintainer who
merged them has no way to know when one of ours dies. The check that compares
them is the only thing that does, and it is ours to run.

## How it got there (kept for the next one)

`gleec-1975.txt` is dead. cipig did not ask us to fix the conflicts in #1975
-- he fixed them, opened **#2034** under his own name, and added the
coinpaprika and livecoinwatch ids that were never in our submission. He then
pointed KomodoPlatform/coins#21 at it. A maintainer did our work for us,
unpaid, for a coin with no price.

What he asked for: some WAM to `WgsySSWQr1tRyjwj3S53XbiVz9yEUCCK9t`, so he can
test a swap and then merge. **The address was checked against our own node --
valid mainnet P2PKH, version byte 73.** It is not a listing fee and does not
touch [[no-listing-fees-ever]]: a swap cannot be tested by somebody holding
none of the coin. The amount, the wallet and the sending are the founder's,
and the reply goes out only after the coins do.

His entry matches ours field for field except one: `required_confirmations` is
**4** where we publish **60**. That is not an error. 60 means two hours per
swap, which is a real cost to anyone trading it, and he is balancing
something real. `gleec-2034.txt` gives him the number and the measurement and
leaves the decision on his side of the fence -- saying nothing would make the
paragraph we put in every other submission worthless, and it is his users who
carry the risk, not ours.

## The one that is our fault

**GLEEC #1975.** cipig asked on 30 August: *"What about the 2 electrums? Do we
need to wait till 15.09.?"* He was told yes. 15.09 came, the servers moved to
mainnet, and nobody went back to him. Four days of an open request waiting on
a date that had already passed. `gleec-1975.txt` is the reply and it should go
first.

## The one worth reopening

**BasicSwap.** The closure had exactly one stated reason and it was the launch
date. Nothing was said about the coin, the code or the policy.
`basicswap-701-reopen.txt` reports that the condition is met and does not
argue with anything.

## Bisq: it was not a policy refusal, and this file said it was

Read whole rather than summarised, both of HenrikJannsen's comments turn on
one thing -- he could not find us.

> I do not see any project related to WAM but an existing coin
> [coingecko.com/en/coins/wam]. Bisq did not add new altcoins anymore, though
> with the BIP110 hardfork there might be case to reconsider that.
> -- 22 August

> I fear the request will not get support and as the ticker symbol conflicts
> thats another issue. As far I am aware the BIP110 Blake based fork coin
> will not have replay protection and therefor will not get added to Bisq as
> well as it would put users at risk. I will close that issue.
> -- 29 August

Three things this file got wrong on 19 September and are corrected here:

**"Bisq does not add new altcoins" was not the final word.** It is qualified
in the same sentence -- *"though with the BIP110 hardfork there might be case
to reconsider that"*.

**The objection that repeats in both comments is the identity collision.**
First he cannot find a project, only the BEP-20 gaming token; then the ticker
conflicts -- with that same token.

**And the flat "will not get added" is not about WAM at all.** It is about the
BIP110 Blake fork coin, a different project, refused for having no replay
protection. Attributing that sentence to us was a misreading.

What changed since 29 August is exactly the thing he could not find:

| | |
|---|---|
| a live chain | mainnet since 2026-09-15, height 3,777, 45 peers |
| an identity that is not the gaming token | SLIP-0044 coin type **5718349**, SLIP-0173 prefixes wam / twam / wamrt, merged 26 August |
| something to run | signed releases for Linux, Windows and macOS |
| something to check it with | a public explorer, and a concentration figure published whether it flatters us or not |

`bisq-new.txt` is written on that basis. It leads with what can be verified,
and it addresses the ticker head-on instead of hoping nobody mentions it --
because that part has not changed and pretending otherwise would be the
fastest way to deserve a third closure.

## The one that should NOT be reopened

**Haveno** closed #2528 with "we only consider coins with market traction /
price". Of every request this project has opened, that is the only one that
asked for a market, and WAM has none by design: this project does not pay for
listings, does not arrange a price, and says so in public. Reopening asks a
maintainer to make an exception to the single criterion he named, and the
answer would be the same.

(#2527 is not a refusal; it has no comments and was replaced by #2528 the
next day. The same is true of bisq #8028, replaced by #8030.)

It becomes worth revisiting when the reason itself changes -- a market that
exists because people want the coin, not because we arranged one.

## All six, ready. The founder picks the day.

A dormant request dies of silence, not of refusal. Three of these are open
and nobody has said no; two people are waiting on something that has already
happened, and one maintainer said he would call and has not yet. A short
message that the chain is live is what revives them.

Send in this order. Each stands alone -- skipping one does not break another.

| | file | where | why now |
|---|---|---|---|
| 1 | `gleec-2034.txt` | comment on **#2034** | he opened it himself and is waiting on WAM for the swap test. `gleec-1975.txt` is superseded |
| 2 | `blockdx-197.txt` | comment on the open PR | the entry moved to v0.1.9, as promised in that thread in August |
| 3 | `komodo-21.txt` | comment on the open PR | open since 29 August with zero comments — give a reviewer a reason to look |
| 4 | `basicswap-701-reopen.txt` | **new** PR | closed for one reason, the launch date, and it has passed |
| 5 | `bisq-new.txt` | **new** PR | closed because he could not find the project; now he can |
| 6 | `haveno-2528.txt` | comment on the closed PR | asks for nothing. Send only if the record there is worth updating |

Every figure in all six was measured at one moment, 2026-09-20T11:04:47Z:
height 3,777, 45 peers, 188,850 WAM mined, 225 kH/s over the last 120 blocks,
and both Electrum servers answering at that same height. **If they are sent
more than a day or two later, re-measure first** — a stale number in a public
thread costs more than it saves, and two different dates inside one message
cost more still. `scripts/check_post_text.py` must pass before any of them goes out.

**The hashrate figure needs more care than the others**, because it does not
drift, it swings: measured over the last five days it roughly doubles between
the quietest hour of the night and the busiest of the morning, and it halved
in a single day when machines were switched off. Quote it with the window it
was measured over, and quote the low end of the day rather than the peak —
the depths it justifies are set against the worst hour, not the best one.

## The message must not describe a change the request does not contain

Checked on 2026-09-20, before any of these went out, and two of the six were
describing work that had never been pushed:

| | what the draft said | what the request actually held |
|---|---|---|
| KomodoPlatform/coins #21 | `required_confirmations` is 60 | it was **20** |
| blocknetdx #197 | the entry moved to `wam--v0.1.9` | it was still **v0.1.6** |

Both were last updated on 6 September, so none of the v0.1.9 work had reached
them. A maintainer reading "60, where most coins here are 3" and then finding
20 in the diff does not conclude that the message is out of date. He
concludes the numbers are not to be trusted, and that is the one thing a
project nobody has heard of cannot afford.

Pushed to both branches on 2026-09-20 and verified through the GitHub API
afterwards: #21 now shows 60, and #197 shows `wam--v0.1.9.conf` in both
directories with the manifest entry to match. GLEEC #1975 already carried 60
and needed nothing.

**So before sending any of these, read the request's own diff, not the
draft.** The draft says what we mean; only the diff says what is there.

**Why the confirmation paragraph is there at all.** `required_confirmations`
is 60 in our entry where most coins in those files carry 3, and
`Confirmations=60` in the Block DX conf where the default is 0. A reviewer
who finds an unusual number without an explanation assumes either a mistake
or something being hidden. Naming it first, with the reason and the promise
to lower it, turns the oddest value in the submission into the one that shows
the work was done.

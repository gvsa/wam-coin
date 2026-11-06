# NBitcoin — what a submission needs, and how this one was recovered

[`MetacoSA/NBitcoin`](https://github.com/MetacoSA/NBitcoin) is the C# Bitcoin
library that BTCPay Server and a long tail of .NET wallets build on. A coin is
added to it as one network definition plus one registration; nothing else in
the library needs to know the coin exists.

| From here | To there |
|---|---|
| the network definition | `NBitcoin.Altcoins/WAM.cs` |
| two lines | `NBitcoin.Altcoins/AltcoinNetworkSets.cs` |

110 lines in total. The genesis entries are the raw blocks the nodes serve,
and the hashes in the commit message were verified against them rather than
copied out of `chainparams.cpp` comments.

## This directory exists because the first submission was not written down

`#1362` was opened by hand on 19 October 2026 and left nothing behind here:
no files, no notes, no row in `scripts/prepare_listing_pr.sh`. When the GitHub
account it was pushed from was suspended on 29 October, the pull request went
with it, and this repository could not say what had been submitted.

Everything in `integration/` exists to stop exactly that, and this venue was
the one that skipped it.

## A suspended account does not take the commits with it

The thing that saved this one: **a pull request's commits live in the
repository it was opened against, not in the fork it was pushed from.** GitHub
keeps them under `refs/pull/<n>/head`, and that ref survives the fork being
deleted or its owner being suspended.

    git clone https://github.com/MetacoSA/NBitcoin.git
    git fetch origin refs/pull/1362/head:pr1362

That returned commit `81fff83` whole -- both files, the message, the author --
so the resubmission is the same commit pushed from a new fork, not a rewrite
from memory. Checked before trusting it: the branch still merges cleanly onto
master, which had moved 11 commits in the meantime.

The same trick recovered `blocknetdx/blockchain-configuration-files#199`
(`refs/pull/199/head` -> `fb525bc`, two commits, three files) and
`KomodoPlatform/coins#23`, which is not being reopened -- that repository is
the obsolete mirror, confirmed by its maintainer on 1 October 2026, and WAM is
already merged and live in the registry that replaced it.

**Write it down before pushing it, and if that was not done, ask the venue's
own repository what it was given.**

## Where it stands

Reopened as [`#1369`](https://github.com/MetacoSA/NBitcoin/pull/1369) on
30 October 2026, from `wamcoin-Project/NBitcoin`, branch `add-wam-coin`,
commit `81fff83` unchanged.

This venue stays manual. `scripts/prepare_listing_pr.sh` stages a venue by
copying whole files into place, and two of these lines are a patch into the
middle of `AltcoinNetworkSets.cs`, which a copy cannot express. Adding a row
for it would give the script a path that half works, which is worse than no
row at all. Actions are disabled on the fork.

add WAM Coin

Two files, 110 lines: NBitcoin.Altcoins/WAM.cs, and two lines in
AltcoinNetworkSets.cs. Nothing else is touched.

This replaces #1362, opened on 19 October. It was pushed from a GitHub account
that has since been suspended, and a suspended account takes its pull request
down with it. The commit here is the same commit: it was fetched back out of
this repository's own refs/pull/1362/head and pushed from the project's new
organisation, so the diff is byte for byte what was there. It still merges
cleanly onto master.

WAM is a Bitcoin Core v28.1 fork with RandomX proof of work, two-minute blocks
and a 22,000,000 cap. Mainnet opened on 15 September 2026 and stood at height
31,072 with 90 peers when this was written.

Registered in SLIP-0044 as coin type 5718349, and in SLIP-0173 with the
prefixes wam / twam / wamrt -- satoshilabs/slips#2051, merged 26 August 2026.

Every value here is taken from the running chain rather than from the source
comments: the three genesis entries are the raw blocks the nodes serve, and
their hashes verify as

  mainnet  d8d3debea987b62a0934c3980d62bffbb6e16aa797d19891d4fcc9b9fb11d7e9
  testnet  ce81c20a59a9586946d46177317658575b9d1c1fc07912b5488ab76202f59bcb
  regtest  b88f3d262f285e38e184f50bf3eea1c8e615486ae67d3d9eaf0976fbd6d3d30d

Source:   https://gitlab.com/WAMCoin/wam-coin
          https://github.com/wamcoin-Project/wam-coin
          https://gitea.com/WAMCoin/wam-coin
Explorer: https://explorer.wamcoin.org

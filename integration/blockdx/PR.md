Add WAM Coin (WAM)

WAM Coin is a Bitcoin Core v28.1 fork using RandomX proof of work. Its RPC
surface, transaction format, script language and SegWit are Bitcoin's, so
XBridge needs only the usual three files.

  xbridge-confs/wam--v0.1.10.conf
  wallet-confs/wam--v0.1.10.conf
  manifest-latest.json                 (one entry)

This replaces #199, opened on 28 September. It was pushed from a GitHub
account that has since been suspended, and a suspended account takes its pull
request down with it. The commits here are the same commits: they were fetched
back out of this repository's own refs/pull/199/head and pushed from the
project's new organisation, so the two conf files are byte for byte what was
there. The manifest's versions list is the only thing added, and only to name
releases that have shipped since.

Values were taken from bitcoin--v0.17.0.conf rather than from a general idea of
what XBridge wants, and three of them are judgements worth stating:

GetNewKeySupported and ImportWithNoScanSupported are false, following Bitcoin
v0.17 rather than Litecoin v0.15. Those flags describe a wallet that hands out
a raw private key and imports one without a rescan, which descriptor wallets in
Core 28 do not do. Claiming otherwise would fail at the first swap rather than
at review.

MinTxFee 10000 and FeePerByte 10 follow Litecoin rather than Bitcoin's
12000/60, because those reflect a fee market this chain does not have. Ten
satoshis a byte is ten times what a WAM node requires to relay.

Confirmations is 15. The first commit said 60, which is the depth this project
publishes for an exchange deposit; this file describes a swap, and at a
120-second target 60 of them is a two-hour swap. Of the 247 coins here, 245 use
0 and one uses 1, so 15 is still the most cautious entry in the file by a wide
margin. It is the number the Komodo maintainer arrived at after running an
actual swap on this chain. The network has also grown since that argument was
made: 5,400-6,100 H/s in early September, 589 kH/s over the last 120 blocks
today. Happy to use 0 like everyone else if that is what you would rather see.

dir_name_linux and conf_name were read off a running node (~/.wam, wam.conf)
rather than assumed from the coin's name.

The chain is live. Mainnet opened at 00:00 UTC on 15 September 2026 and stood
at height 31,072 with 90 peers when this was written. SLIP-0044 coin type
5718349 and the SLIP-0173 prefixes wam / twam / wamrt were merged into
satoshilabs/slips on 26 August 2026.

Source:   https://gitlab.com/WAMCoin/wam-coin
          https://github.com/wamcoin-Project/wam-coin
          https://gitea.com/WAMCoin/wam-coin
Explorer: https://explorer.wamcoin.org
Releases: https://wamcoin.org/downloads/

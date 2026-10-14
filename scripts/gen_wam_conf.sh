#!/usr/bin/env bash
# Copyright (c) 2026 The WAM Coin developers
# Distributed under the MIT software license, see COPYING.
#
# ===========================================================================
#  gen_wam_conf.sh -- the example configuration, generated from the binary
# ===========================================================================
#
#      bash scripts/gen_wam_conf.sh <dir holding wamd>
#
#  WHY THIS EXISTS
#
#  Asked on 2026-10-13 by an operator running his own node and pool: could we
#  ship a wam.conf listing the parameters and their safe values, the way the
#  pool ships config.example.json. We shipped none. The release tarball is
#  binaries and documents, and upstream's share/examples/bitcoin.conf was
#  never renamed, never adapted and never packaged -- so every operator
#  configured a WAM node by guessing, or by reading a Bitcoin file.
#
#  What it cost, the same week and to the same person: his service read its
#  configuration from ~/ instead of ~/.wam/, so wamd ran on defaults for
#  everything and on a datadir he did not intend. He found it himself. The
#  first section below exists because of that hour.
#
#  GENERATED, NOT WRITTEN
#
#  The option list comes from `wamd -help`, so it cannot drift from the
#  binary: an option added upstream appears here the next time a release is
#  cut, and one removed disappears. A hand-written list goes stale the first
#  time somebody adds a flag and nobody remembers this file.
#
#  What is NOT generated is the first section -- the handful of settings an
#  operator actually has to decide, with the values this project recommends
#  and the reason for each. A hundred and twenty-nine commented-out options
#  tell a reader nothing about what to do; that section is the answer to the
#  question he actually asked.
#
#  scripts/check_example_conf.py fails if the committed file stops matching
#  what the binary prints.
# ===========================================================================

set -u
export LC_ALL=C

BIN_DIR="${1:-}"
[ -n "$BIN_DIR" ] || { echo "usage: $0 <dir holding wamd>" >&2; exit 2; }
WAMD="$BIN_DIR/wamd"
[ -x "$WAMD" ] || { echo "error: $WAMD is not here or not executable" >&2; exit 2; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT/share/examples"
OUT="$OUT_DIR/wam.conf"
mkdir -p "$OUT_DIR"

VERSION="$("$WAMD" -version 2>/dev/null | head -1)"

{
cat <<'HEADER'
##
## wam.conf -- the WAM Coin node's configuration file.
##
## Generated from the node's own help output by scripts/gen_wam_conf.sh.
## Every option the binary accepts is listed further down, commented out.
##
## WHERE THIS FILE GOES. One file, inside the data directory, whatever chain
## the node is on:
##
##     ~/.wam/wam.conf
##
## Not ~/wam.conf. A file there is never read: the node starts anyway, on
## defaults for everything, and says nothing about it -- which is how an
## operator spent an hour in October 2026 chasing a setting the node had
## never seen. -conf= is relative to the data directory, not to where you
## are standing.
##
## Settings that differ per chain go in a SECTION of this same file, not in a
## second file:
##
##     server=1
##     [main]
##     rpcport=9554          # p2p 9555
##     [test]
##     rpcport=19554         # p2p 19555
##     [regtest]
##     rpcport=29554         # p2p 29555
##
## Check what it actually loaded rather than assuming:
##
##     wam-cli -chain=main getrpcinfo
##     wamd -chain=main -printtoconsole        (the first lines name the file)
##
##
## ---------------------------------------------------------------------------
## THE SETTINGS YOU ACTUALLY HAVE TO DECIDE
## ---------------------------------------------------------------------------
##
## Everything below this block has a default that works. These are the ones
## worth a decision, with what this project runs and why.

## Accept RPC at all. Without it wam-cli cannot talk to the node and neither
## can a pool, an explorer or a wallet.
#server=1

## RPC credentials. Prefer the cookie file the node writes in the datadir --
## it rotates on every restart and never appears in a config file. Set these
## two only when something else must read them, and never reuse a password.
#rpcuser=
#rpcpassword=

## Who may connect. The default is localhost only, which is what you want.
## rpcallowip opens the port to a network; rpcbind decides which interface it
## listens on. Setting either without a firewall in front of it is how nodes
## are taken. If a pool or explorer runs on another host, prefer an SSH
## tunnel over opening the port.
#rpcbind=127.0.0.1
#rpcallowip=127.0.0.1/32

## How many RPC requests may wait, and how many are served at once.
## Raise the queue -- not the threads -- if you see
##
##     WARNING: request rejected because http work queue depth exceeded
##
## That warning means the request was REFUSED, not delayed: whatever called
## the node got an error. It usually appears while the node is restarting,
## when the workers are not busy but waiting for the block index to load, so
## more threads would only wait alongside them. 64 and 4 is a comfortable
## pair for a node with a pool or an explorer on it.
#rpcworkqueue=64
#rpcthreads=4

## Keep the full transaction index. Required by the explorer, by any wallet
## that looks up a transaction it did not send, and by getrawtransaction for
## an arbitrary txid. It cannot be combined with prune.
#txindex=1

## BIP-158 block filters. A light client or a scanning wallet needs these to
## find its own transactions without downloading every block twice.
#blockfilterindex=1

## Memory for the UTXO cache, in MiB. More is faster during a sync and makes
## no difference once caught up. 450 is the default; 2000 is reasonable on a
## machine with 8 GB.
#dbcache=450

## Accept inbound connections. Leave it on: a node that only dials out takes
## from the network without giving back, and WAM has few enough nodes that it
## is noticeable.
#listen=1

## Peers to reach on a first start. The node also asks the DNS seeds, and
## these are only a help if DNS is blocked where you are.
#addnode=seed1.wamcoin.org
#addnode=seed2.wamcoin.org
#addnode=seed3.wamcoin.org

##
## ---------------------------------------------------------------------------
## EVERY OPTION THE BINARY ACCEPTS
## ---------------------------------------------------------------------------
##
## Below is generated from the node's help. Uncomment what you need.
##
HEADER

printf '## Generated from: %s\n##\n\n' "$VERSION"

# Parse `wamd -help`, the same shape upstream's generator uses: a line that
# starts with two spaces and a dash is an option; the indented lines under it
# are its help text. Options become `#name=` with the help above them.
"$WAMD" -help \
  | sed  '1,/Print this help message and exit/d' \
  | sed -E 's/^[[:space:]]{2}\-/#/'              \
  | sed -E 's/^[[:space:]]{7}/# /'               \
  | sed -E '/^#$/d'                              \
  | sed -E 's/[[:space:]]+$//'
} > "$OUT"

LINES="$(wc -l < "$OUT")"
OPTS="$(grep -cE '^#[a-z]' "$OUT" || true)"
printf 'wrote %s\n  %s lines, %s option(s), from %s\n' \
       "${OUT#"$ROOT"/}" "$LINES" "$OPTS" "$VERSION"

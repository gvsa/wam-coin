#!/usr/bin/env python3
# Copyright (c) 2026 The WAM Coin developers
# Distributed under the MIT software license, see COPYING.
#
# ===========================================================================
#  test_rename_messages.py -- the coin's name in the text a person reads
# ===========================================================================
#
#      python3 scripts/test/test_rename_messages.py
#
#  WHY THIS EXISTS
#
#  On 2026-09-26 the first graphical wallet this project ever built was
#  started and looked at. The window said WAM Coin, the splash carried the W,
#  the About box named this repository -- and the debug console, which is one
#  menu away and is where a person goes when something is wrong, answered
#
#      help validateaddress
#      Return information about the given bitcoin address.
#
#  Fifty such strings were left: "The Bitcoin address", "the bitcoin address
#  to receive", "you will receive less bitcoins than you enter", "the newly
#  generated bitcoin to". Each one names another coin while describing this
#  one's money, and each one is read by a person, not by a program.
#
#  WHAT IT GUARDS, IN BOTH DIRECTIONS
#
#  The renaming runs inside quoted C++ literals only, because the header of
#  rename_binaries.py records what a blind search and replace does here: it
#  renames #include "bitcoind.h" and the build stops. So this checks that the
#  prose IS rewritten and that code is NOT -- a rule that only fires one way
#  is half a rule.
#
#  Argument NAMES are never touched and there is a case for that below. A
#  renamed argument breaks every client that ever sent one, and no wording is
#  worth that.
# ===========================================================================

import importlib.util
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]

spec = importlib.util.spec_from_file_location(
    "rename_binaries", REPO / "scripts" / "rename_binaries.py")
rb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rb)

GRN = "\033[32m"; RED = "\033[31m"; OFF = "\033[0m"

failures = 0
checks = 0


def rewrites(src, want):
    """The prose a person reads must name this coin."""
    global failures, checks
    checks += 1
    got = rb.rename_message_strings(src)
    if want in got:
        print(f"  {GRN}ok{OFF}    {got}")
    else:
        failures += 1
        print(f"  {RED}FAIL{OFF}  {got}\n          wanted to contain {want!r}")


def untouched(src):
    """Code is not prose. Renaming it stops the build, or worse, does not."""
    global failures, checks
    checks += 1
    got = rb.rename_message_strings(src)
    if got == src:
        print(f"  {GRN}ok{OFF}    unchanged: {src}")
    else:
        failures += 1
        print(f"  {RED}FAIL{OFF}  changed code: {src}\n          became {got}")


print("\nthe coin's name in the text a person reads")

# Every one of these is a real string from Bitcoin Core's RPC help, and every
# one of them appeared in the first wallet build.
rewrites('"The Bitcoin address (only if a well-defined address exists)"',
         "WAM address")
rewrites('"The bitcoin address to receive the payment"', "WAM address")
rewrites('"Return information about the given bitcoin address."', "WAM address")
rewrites('"Invalid Bitcoin address: "', "Invalid WAM address")
rewrites('"you will receive less bitcoins than you enter"', "less WAM than")
rewrites('"Send the newly generated bitcoin to this address"',
         "generated WAM to")

# And the program names, which this has rewritten since August.
rewrites('"Make sure the bitcoind server is running"', "wamd server")
rewrites('"Use \\"bitcoin-cli -help\\" for more info."', "wam-cli -help")

print()

# The other direction. These are code, and the header of rename_binaries.py
# exists because a blind replace over them breaks the build.
untouched('#include "bitcoind.h"')
untouched('LIBBITCOIN_COMMON="libbitcoin_common.a"')
untouched('"bitcoinsomething"')
untouched('"bitcoin.conf"')

print(f"\n  {checks} check(s), {failures} failure(s)\n")
sys.exit(1 if failures else 0)

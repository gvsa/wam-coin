#!/usr/bin/env python3
# Copyright (c) 2026 The WAM Coin developers
# Distributed under the MIT software license, see COPYING.
"""
===============================================================================
 check_published_endpoints.py -- a host:port we publish must answer
===============================================================================

     python3 scripts/check_published_endpoints.py

 WHY THIS EXISTS

 On 15 September 2026, the day mainnet opened, the mining guide sent miners to
 pool.wamcoin.org:13333 -- a port that had stopped existing at 00:00 UTC when
 the testnet pool was converted. It was found by a person, two days later.

 On 8 October 2026 the same shape came back from the other direction. The
 "Which pool" section of docs/MINE.md names three stratum endpoints, two of
 them run by other people, and says:

 <!-- wam:quote-begin -->
     All three answered when this page was last checked; if one does not
     answer for you, try another.
 <!-- wam:quote-end -->

 wam.ariabrain.com:3333 refuses the connection -- measured from the laptop
 and from all three seeds, in three countries, so it is not a block on one
 address. Its website is up and the pool is still listed there, which is why
 nobody noticed: the page a reader sees is not the port a miner dials.

 The sentence is the fault, not the pool. "When this page was last checked"
 is a claim with no checker behind it, so it decays silently, and the person
 who pays for it is a stranger who followed our instructions and got
 "connection refused" from the first thing this project told him to try.

 WHAT THIS DOES

 It finds every host:port on the pages a stranger reads, and dials each one.
 A stratum port must also answer mining.subscribe, because a port that
 accepts a connection and says nothing is not a pool a miner can use.

 Quotation marks are honoured (scripts/lib/quoted.py): docs/REHEARSALS.md
 quotes a rehearsal log that names the old testnet port, and a record of what
 happened in September is not an instruction for today.

 EXIT CODES, this project's convention

     0  every published endpoint answered
     1  some answered and some did not -- a published endpoint is dead
     2  NOTHING answered, which is far more likely to be this machine's
        network than every pool in the world going down at once. A check
        that cannot ask has not learned that the answer is no.
===============================================================================
"""

from __future__ import annotations

import json
import pathlib
import re
import socket
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "lib"))
import quoted  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

RED = "\033[31m"; GRN = "\033[32m"; YEL = "\033[33m"; BLD = "\033[1m"; OFF = "\033[0m"

# The pages a stranger lands on, and the documents they are generated from --
# both, because fixing one without the other means the next build undoes it.
TARGETS = ["site/*.html", "site/*/*.html", "site/CHANNELS.txt", "CHANNELS.txt",
           "docs/MINE.md", "docs/START_HERE.md", "docs/START_HERE_AR.md",
           "docs/POOL_OPERATOR.md", "README.md"]

# A port served over TLS answers a TLS handshake, not a JSON line. Proving
# something listens is all this check needs from those.
TLS_PORTS = {50001, 50002, 50004, 51001, 51002, 51004, 443}

ENDPOINT = re.compile(r"\b([a-z0-9][a-z0-9.-]*\.[a-z]{2,})[:\s]*:(\d{2,5})\b")

# Names reserved by RFC 2606 and RFC 6761 exist so documentation can show a
# host that is guaranteed never to resolve. README.md uses pool.example.org
# in the line that tells an operator what to put in his own config, and a
# check that dials it is reporting that the standard works.
EXAMPLE = re.compile(r"(^|\.)(example\.(com|org|net)|invalid|test|localhost)$")

TIMEOUT = 12


def published():
    """{(host, port): [where it is published]}, quotations excluded."""
    found = {}
    for pattern in TARGETS:
        for path in sorted(ROOT.glob(pattern)):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT).as_posix()
            text = quoted.strip_quoted(
                path.read_text(encoding="utf-8", errors="replace"))
            for host, port in ENDPOINT.findall(text):
                host = host.rstrip(".")
                if EXAMPLE.search(host):
                    continue
                key = (host, int(port))
                found.setdefault(key, [])
                if rel not in found[key]:
                    found[key].append(rel)
    return found


def dial(host, port):
    """(ok, what happened). A stratum port must say something back."""
    try:
        with socket.create_connection((host, port), timeout=TIMEOUT) as s:
            if port in TLS_PORTS:
                return True, "listening (TLS, handshake not attempted)"
            s.sendall(json.dumps({"id": 1, "method": "mining.subscribe",
                                  "params": ["wam-endpoint-check"]}).encode()
                      + b"\n")
            s.settimeout(TIMEOUT)
            try:
                reply = s.recv(512).decode("utf-8", "replace").strip()
            except socket.timeout:
                # Not a failure on its own: a server may wait for a different
                # first message. It is still reachable, which is the question
                # a miner is asking.
                return True, "open, silent to mining.subscribe"
            if '"result"' in reply or '"method"' in reply:
                return True, "answers stratum"
            return True, f"open, replied {reply[:40]!r}"
    except OSError as e:
        return False, type(e).__name__


def main() -> int:
    print(f"\n{BLD}every host:port this project publishes answers{OFF}\n")

    found = published()
    if not found:
        print(f"  {YEL}no endpoint was found on any page -- this is not a "
              f"pass{OFF}\n")
        return 2

    dead = []
    alive = 0
    for (host, port), where in sorted(found.items()):
        ok, why = dial(host, port)
        label = f"{host}:{port}"
        if ok:
            alive += 1
            print(f"  {GRN}ok{OFF}    {label:<34} {why}")
        else:
            dead.append((label, why, where))
            print(f"  {RED}FAIL{OFF}  {label:<34} {why}")
            for w in where:
                print(f"          published in {w}")

    print()
    if dead and alive == 0:
        print(f"  {YEL}nothing answered at all -- that is this machine's "
              f"network, not the world's{OFF}")
        print(f"  {YEL}A check that could not ask has not learned that the "
              f"answer is no.{OFF}\n")
        return 2
    if dead:
        print(f"  {RED}{len(dead)} published endpoint(s) do not answer{OFF}")
        print("  A stranger who followed our page dialled this and got")
        print("  nothing. Either take it off the page, or say beside it that")
        print("  it is not answering and when that was measured.")
        print()
        print("  Third-party pools are theirs to run and ours to stop naming")
        print("  while they are down. The page is the thing we control.\n")
        return 1
    print(f"  {GRN}{BLD}all {alive} published endpoints answered{OFF}\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(2)

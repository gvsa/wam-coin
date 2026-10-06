#!/usr/bin/env python3
# Copyright (c) 2026 The WAM Coin developers
# Distributed under the MIT software license, see COPYING.
"""
===============================================================================
 check_mirrors.py -- the three homes must hold the same project
===============================================================================

     python3 scripts/check_mirrors.py

 WHY THIS EXISTS

 Every announcement this project makes carries three repositories, because on
 2026-09-24 one company suspended the account that held the only copy anybody
 outside could reach, and the repository, every release download and
 wamcoin.org went dark in the same hour. Git is distributed and we were using
 it as though it were not.

 A reader is told he may clone from any of the three. So all three have to be
 the same project, and on 2026-10-06 they were not: GitHub had a ruleset
 requiring changes to main to arrive through a pull request, and had been
 silently refusing the push for a commit. ship.sh is right to continue -- a
 second copy being unreachable must never stop the deploy -- but it says so
 in one line, once, in the middle of a successful ship. Nothing asked
 afterwards, so the only reason it was noticed is that somebody read that
 line. That is not a check; that is luck.

 What it costs: a reader who clones the mirror gets an older tree while
 everything he was shown says the three are the same. He then verifies a
 signature, reads a document, or builds a binary that does not match what the
 project is telling him about. Nobody is lying to him and he is misled all
 the same.

 WHAT THIS DOES

 It asks every remote other than origin for its main and its tags, and
 compares them to origin's. Tags matter as much as the branch: a mirror
 missing a release tag cannot be used to check out the release it names.

 EXIT CODES, this project's convention

     0  every mirror holds origin's main, and every tag origin has
     1  a mirror is behind, ahead, or missing tags -- the three differ
     2  the question could not be put to one of them, and nothing was
        learned about it. A remote that cannot be reached is not a remote
        that agrees.
===============================================================================
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

RED = "\033[31m"; GRN = "\033[32m"; YEL = "\033[33m"; BLD = "\033[1m"; OFF = "\033[0m"


def git(*args, timeout=90):
    return subprocess.run(["git", "-C", str(ROOT), *args],
                          capture_output=True, text=True, timeout=timeout)


def refs(remote):
    """{ref: sha} for the branches and tags a remote holds, or None.

    None means the question could not be put -- no network, no key, a
    repository that has been renamed or suspended. It is deliberately not an
    empty dict: an empty dict compares equal to nothing and would read as a
    mirror that holds no tags, which is a finding rather than a silence.
    """
    try:
        out = git("ls-remote", "--heads", "--tags", remote)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"  {YEL}??{OFF}    {remote:<10} could not be asked ({e})")
        return None
    if out.returncode != 0:
        why = (out.stderr or "").strip().splitlines()
        print(f"  {YEL}??{OFF}    {remote:<10} could not be asked "
              f"({why[-1][:70] if why else 'git ls-remote failed'})")
        return None
    found = {}
    for line in out.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2 and not parts[1].endswith("^{}"):
            found[parts[1]] = parts[0]
    return found


def main() -> int:
    print(f"\n{BLD}the three homes hold the same project{OFF}\n")

    remotes = [r for r in git("remote").stdout.split() if r]
    if "origin" not in remotes:
        print(f"  {YEL}there is no origin to compare against{OFF}\n")
        return 2

    canonical = refs("origin")
    if canonical is None:
        print(f"\n  {YEL}origin could not be read -- nothing was compared, "
              f"and this is not a pass{OFF}\n")
        return 2

    head = canonical.get("refs/heads/main")
    tags = {r for r in canonical if r.startswith("refs/tags/")}
    print(f"  {GRN}ok{OFF}    {'origin':<10} main {head[:12] if head else '?'}"
          f", {len(tags)} tag(s)")

    behind, unasked = [], []
    for remote in remotes:
        if remote == "origin":
            continue
        got = refs(remote)
        if got is None:
            unasked.append(remote)
            continue
        theirs = got.get("refs/heads/main")
        missing = sorted(t.rsplit("/", 1)[-1] for t in tags - set(got))
        if theirs == head and not missing:
            print(f"  {GRN}ok{OFF}    {remote:<10} main {theirs[:12]}, "
                  f"every tag origin has")
            continue
        behind.append(remote)
        print(f"  {RED}FAIL{OFF}  {remote:<10} "
              + (f"main {theirs[:12]} -- origin has {head[:12]}"
                 if theirs != head else f"main {theirs[:12]}"))
        if missing:
            print(f"        missing tag(s): {', '.join(missing[:6])}"
                  + (f" and {len(missing) - 6} more" if len(missing) > 6 else ""))

    print()
    if behind:
        print(f"  {RED}{len(behind)} mirror(s) are not this project's main{OFF}")
        print("  Every announcement tells a reader he may clone any of them.")
        print("  A mirror that is behind hands him an older tree while")
        print("  everything he was shown says the three are the same.")
        print()
        print("  ship.sh reports a mirror it could not push to and continues,")
        print("  which is right -- and it says it once, in the middle of a")
        print("  ship that worked. Read that line, or read this check.")
        print()
        print("  To push one by hand:   WAM_SHIP=1 git push <remote> main --tags")
        print("  If it is refused for a rule rather than a key, the rule is in")
        print("  that host's settings and no command here can satisfy it.")
        print()
        return 1
    if unasked:
        print(f"  {YEL}{len(unasked)} mirror(s) could not be asked: "
              f"{', '.join(unasked)}{OFF}")
        print(f"  {YEL}A remote that cannot be reached is not one that "
              f"agrees.{OFF}\n")
        return 2
    print(f"  {GRN}{BLD}all {len(remotes)} homes hold the same main and the "
          f"same tags{OFF}\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.TimeoutExpired:
        print(f"\n  {YEL}a remote did not answer in time -- nothing was "
              f"learned about it{OFF}\n")
        sys.exit(2)
    except KeyboardInterrupt:
        sys.exit(2)

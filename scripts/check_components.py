#!/usr/bin/env python3
# Copyright (c) 2026 The WAM Coin developers
# Distributed under the MIT software license, see COPYING.
"""
===============================================================================
 check_components.py -- the manifest describes this repository, or it is
                        a second place to be wrong
===============================================================================

     python3 scripts/check_components.py [--release vX.Y.Z]

 WHY THIS EXISTS

 scripts/lib/components.py says what this project ships, what version each
 train is on, and where that version lives. Two scripts already read it
 instead of knowing the answer by heart, and more will.

 A manifest nobody verifies is worse than no manifest. It is believed
 because it is central, and a central file that has drifted is wrong in
 every place that trusts it at once. So this asks the repository whether
 the manifest is telling the truth about it.

 WHAT IT CHECKS

 Every train names a file that exists and carries the version pattern it
 claims. Every component is on a train that is defined and has at least one
 archive and one word a reader would know it by. And with --release, every
 archive name the manifest would produce for that version is actually in the
 published release -- which is the question that matters on the day: does
 this file describe what we shipped, or what we meant to ship?

 EXIT CODES, this project's convention

     0  the manifest describes this repository
     1  it does not
     2  it could not be read, so nothing was compared
===============================================================================
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

RED = "\033[31m"; GRN = "\033[32m"; YLW = "\033[33m"; BLD = "\033[1m"; OFF = "\033[0m"


def published_assets(tag):
    """The file names a release actually carries, or None if it cannot ask."""
    try:
        out = subprocess.run(
            ["gh", "release", "view", tag, "--repo", "wamcoin-core-dev/wam-coin",
             "--json", "assets"],
            capture_output=True, text=True, timeout=120, encoding="utf-8",
            errors="replace")
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    try:
        return {a["name"] for a in json.loads(out.stdout).get("assets", [])}
    except (ValueError, KeyError, TypeError):
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--release", help="also check a published release carries "
                                      "every archive the manifest names")
    a = ap.parse_args()

    print(f"\n{BLD}the manifest describes this repository{OFF}\n")

    try:
        import components
    except ImportError as e:
        print(f"  {YLW}scripts/lib/components.py could not be imported "
              f"({e}), so nothing was checked.{OFF}\n")
        return 2

    problems = components.check(ROOT)
    for p in problems:
        print(f"  {RED}FAIL{OFF}  {p}")

    if not problems:
        for name, t in components.TRAINS.items():
            v = components.train_version(ROOT, name)
            print(f"  {GRN}ok{OFF}    train {name:<6} v{v}  from {t['source']}")
        names = [c["name"] for c in components.COMPONENTS]
        print(f"  {GRN}ok{OFF}    ships {', '.join(names)}")
        print(f"  {GRN}ok{OFF}    runs  {len(components.SERVICES)} service(s), "
              f"none of them versioned")

    if a.release:
        assets = published_assets(a.release)
        if assets is None:
            print(f"  {YLW}--{OFF}    could not read release {a.release}, so "
                  f"the archive names were NOT compared")
        else:
            want = components.archive_names(a.release)
            missing = [n for n in want if n not in assets]
            for n in missing:
                print(f"  {RED}FAIL{OFF}  {a.release} does not carry {n}, "
                      f"which the manifest says it ships")
            problems.extend(missing)
            if not missing:
                print(f"  {GRN}ok{OFF}    {a.release} carries all "
                      f"{len(want)} archive(s) the manifest names")

    print()
    if problems:
        print(f"  {RED}{BLD}the manifest and the repository disagree{OFF}")
        print("  Everything that reads it is now wrong in the same way at")
        print("  once, which is the cost of having one place for an answer.\n")
        return 1
    print(f"  {GRN}{BLD}it describes what is actually here{OFF}\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(2)

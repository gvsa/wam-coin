#!/usr/bin/env python3
# Copyright (c) 2026 The WAM Coin developers
# Distributed under the MIT software license, see COPYING.
"""
===============================================================================
 check_badges.py -- a badge states a fact, so the fact is checked
===============================================================================

     python3 scripts/check_badges.py

 WHY THIS EXISTS

 The badges at the top of README.md are the first thing a developer reads,
 and each one is a claim: this builds, this is the current release, this many
 people have downloaded it, this is the licence. A badge nobody checks is a
 claim nobody checks, printed where it is believed fastest.

 The first version of the release badge said **no releases** over a project
 with twelve of them. Every WAM release is tagged v0.* and the workflow marks
 those as prereleases, and shields.io's github/v/release ignores prereleases
 unless asked. It was caught by fetching the badge and reading it rather than
 by looking at the markdown, which looked perfect.

 WHAT THIS CHECKS

 Every badge image in README.md answers, and the two that carry a value say
 what this repository actually holds: the newest tag, and a licence GitHub
 itself detects. A badge that cannot be fetched is a broken image at the top
 of the page a stranger lands on.

 EXIT CODES, this project's convention

     0  every badge answers and says something true
     1  one does not
     2  the network or the repository could not be read, so nothing was
        compared
===============================================================================
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import quoted  # noqa: E402  -- needs the path above

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

RED = "\033[31m"; GRN = "\033[32m"; YLW = "\033[33m"; BLD = "\033[1m"; OFF = "\033[0m"

BADGE = re.compile(r"\[!\[([^\]]*)\]\((https://[^)]+)\)\]")
TIMEOUT = 30


def fetch(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "wam-badge-check"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError, ValueError) as e:
        return None, str(e)


def newest_tag():
    try:
        out = subprocess.run(["git", "tag", "--sort=-v:refname"], cwd=ROOT,
                             capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    tags = [t for t in out.stdout.split() if re.fullmatch(r"v\d+\.\d+\.\d+", t)]
    return tags[0] if tags else None


def main() -> int:
    print(f"\n{BLD}every badge answers, and says something true{OFF}\n")

    readme = ROOT / "README.md"
    if not readme.is_file():
        print(f"  {YLW}README.md is not here, so nothing was checked.{OFF}\n")
        return 2

    # Quotation marks are honoured, as in every other text-scanning check
    # here. A document that QUOTES a badge line -- this one does, in its own
    # header -- must not be read as carrying that badge.
    text = quoted.strip_quoted(readme.read_text(encoding="utf-8",
                                                errors="replace"))
    badges = BADGE.findall(text.split("\n##", 1)[0])
    if not badges:
        print(f"  {YLW}no badge was found at the top of README.md -- this is "
              f"not a pass, it is nothing to check.{OFF}\n")
        return 2

    bad = []
    for label, url in badges:
        status, body = fetch(url)
        if status != 200:
            bad.append((label, f"did not answer ({body[:60]})"))
            print(f"  {RED}FAIL{OFF}  {label:<16} {body[:50]}")
            continue

        # The two that carry a value are read, not just pinged. A badge that
        # renders is not a badge that is true: the release one answered 200
        # and said "no releases" over a repository with twelve.
        note = ""
        if "/v/release" in url:
            tag = newest_tag()
            if tag is None:
                note = "  (no tag here to compare with)"
            elif tag.lstrip("v") in body:
                note = f"  says {tag}"
            else:
                bad.append((label, f"does not say {tag}"))
                print(f"  {RED}FAIL{OFF}  {label:<16} this repository's newest "
                      f"tag is {tag} and the badge does not say so")
                if "no releases" in body:
                    print("          it says \"no releases\" -- add "
                          "&include_prereleases, because every")
                    print("          release here is tagged v0.* and those are "
                          "marked prerelease")
                continue
        elif "licence-" in url or "license-" in url:
            note = "  (a stated licence, not a detected one -- see below)"

        print(f"  {GRN}ok{OFF}    {label:<16} answers{note}")

    # GitHub's own sidebar is a separate claim from the badge, and it is the
    # one a developer actually looks at. It reads a file that holds the
    # licence text and nothing else; COPYING here also names the upstream
    # projects, which is correct and makes the detector give up and print
    # "Other" -- which reads as an unclear licence on a project that has a
    # clear one. LICENSE exists for the detector; COPYING stays as it is.
    lic = ROOT / "LICENSE"
    if not lic.is_file():
        bad.append(("LICENSE", "is missing"))
        print(f"  {RED}FAIL{OFF}  {'LICENSE':<16} is not here, so GitHub's "
              f"sidebar will read \"Other\"")
    else:
        body = lic.read_text(encoding="utf-8", errors="replace")
        extra = [w for w in ("Bitcoin Core", "RandomX", "THIRD-PARTY") if w in body]
        if "MIT License" not in body:
            bad.append(("LICENSE", "does not open with the MIT text"))
            print(f"  {RED}FAIL{OFF}  {'LICENSE':<16} does not hold the MIT "
                  f"licence text")
        elif extra:
            bad.append(("LICENSE", "holds more than the licence"))
            print(f"  {RED}FAIL{OFF}  {'LICENSE':<16} also mentions "
                  f"{', '.join(extra)} -- the detector needs this file to hold "
                  f"the licence and nothing else. That belongs in COPYING.")
        else:
            print(f"  {GRN}ok{OFF}    {'LICENSE':<16} holds the MIT text alone, "
                  f"so the sidebar can read it")

    print()
    if bad:
        print(f"  {RED}{BLD}{len(bad)} badge claim(s) are not true{OFF}")
        print("  A badge is read in the first second and believed in the")
        print("  second one. One that lies is worse than one that is absent.\n")
        return 1
    print(f"  {GRN}{BLD}all {len(badges)} badge(s) answer, and the licence is "
          f"detectable{OFF}\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(2)

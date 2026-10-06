#!/usr/bin/env python3
# Copyright (c) 2026 The WAM Coin developers
# Distributed under the MIT software license, see COPYING.
#
# ===========================================================================
#  check_site_published.py -- is the live site the site in this repository?
# ===========================================================================
#
#      python3 scripts/check_site_published.py
#
#  WHY THIS EXISTS
#
#  On 15 September 2026, the day mainnet opened, two corrections were made to
#  site/ on main, committed, pushed, and reported as published:
#
#    - SECURITY: the page claimed a bounty had already been paid. Nothing had.
#    - the mining guide sent miners to port 13333, which had stopped existing
#      at 00:00 UTC when the testnet pool was converted.
#
#  Neither reached wamcoin.org. At the time GitHub Pages served the gh-pages
#  branch, generated from site/ by a script that was never run. So for two
#  days the live site told the world a payment had been made that had not, and
#  told miners to connect to a dead port -- while the repository, every commit
#  message, and everything said to the founder were correct.
#
#  It was found by an outside security researcher asking, by email, for the
#  transaction id of the payment the page claimed.
#
#  WHAT PUBLISHES THE SITE NOW, because this file told the wrong story for
#  eight days after it stopped being true
#
#  On 2026-09-24 GitHub suspended the account and wamcoin.org returned 404 to
#  everybody. The domain was moved onto machines this project owns, and nginx
#  serves /opt/wam/site straight from the deployed checkout -- see
#  deploy/nginx/wamcoin.org.conf. Deploying is therefore publishing, and
#  `bash scripts/ship.sh` is the whole act.
#
#  This header, and the advice printed when a page differs, still named the
#  gh-pages branch and the script that generated it. On 2026-10-02 that advice
#  was followed: the script pushed a gh-pages branch to GitLab, which serves
#  nothing, while the live page had already been published by the deploy. The
#  script is gone. A check whose failure message names a command that cannot
#  fix the failure is worse than one that says nothing, because it sends the
#  reader away satisfied.
#
#  check_published_claims.py compares documents to consensus. audit_repo.sh
#  compares files to each other. check_deployed_code.sh compares the servers
#  to origin/main. Nothing compared the LIVE WEBSITE to the repository, and a
#  correction that is committed but not published is worse than no correction:
#  it makes everyone who reads the commit believe the lie is gone.
#
#  EXIT CODES, this project's convention
#
#      0  every page checked is byte-identical to site/ in this repository
#      1  a live page differs -- the world is reading something else
#      2  the question could not be put (no network, a page 404s)
# ===========================================================================

import glob
import hashlib
import os
import sys
import urllib.error
import urllib.request

RED = "\033[31m"; GRN = "\033[32m"; YEL = "\033[33m"; BLD = "\033[1m"; OFF = "\033[0m"

BASE = os.environ.get("WAM_SITE", "https://wamcoin.org")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(HERE, "site")


# Files that are not pages and are still read: the channel list a stranger
# downloads to find us, and the signature he checks it against. They are
# published by the same deploy and were compared by nothing.
FILES = ["CHANNELS.txt", "CHANNELS.txt.asc", "sitemap.xml", "robots.txt"]


def pages():
    """Everything the site serves, found rather than listed.

    This was a hand-written list of six pages. The site had nine, and the
    three it did not know about were /start-ar/, /build/ and /rehearsals/ --
    so the Arabic start page, the one page a reader who cannot read the
    others depends on, could have been stale on the live site for any length
    of time and this check would have said the live site is this repository.
    A list of what to check is a list that stops being true the day somebody
    adds a page, and nothing makes a noise when it does.
    """
    out = []
    for path in sorted(glob.glob(os.path.join(SITE, "**", "index.html"),
                                 recursive=True)):
        rel = os.path.relpath(path, SITE).replace(os.sep, "/")
        out.append((rel, "/" + rel[:-len("index.html")]))
    for name in FILES:
        if os.path.exists(os.path.join(SITE, name)):
            out.append((name, "/" + name))
    return out


def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "wam-site-check",
        # Pages sits behind a CDN. Without this a cached copy can answer for
        # minutes after a publish, and the check would then be measuring the
        # cache rather than the site.
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def main():
    print(f"\n{BLD}is the live site the site in this repository?{OFF}")
    print(f"  {BASE}\n")

    differ, unreadable, same = [], [], 0

    found = pages()
    if not found:
        print(f"  {YEL}no page was found under site/ -- this is not a pass{OFF}\n")
        return 2

    for rel, path in found:
        local_path = os.path.join(SITE, rel.replace("/", os.sep))
        if not os.path.exists(local_path):
            continue
        with open(local_path, "rb") as fh:
            want = fh.read()

        try:
            got = fetch(BASE.rstrip("/") + path)
        except Exception as e:
            print(f"  {YEL}??{OFF}    {path:<16} could not be read ({e})")
            unreadable.append(path)
            continue

        if hashlib.sha256(got).digest() == hashlib.sha256(want).digest():
            print(f"  {GRN}ok{OFF}    {path:<16} matches site/{rel}")
            same += 1
        else:
            print(f"  {RED}FAIL{OFF}  {path:<16} DIFFERS from site/{rel}")
            print(f"        live {len(got)} bytes, repo {len(want)} bytes")
            differ.append(path)

    print()
    if differ:
        print(f"  {RED}{len(differ)} live page(s) are not what this repository says{OFF}")
        print("  nginx serves site/ from the deployed checkout, so a page that")
        print("  differs means the hosts are not on this commit:")
        print("      bash scripts/ship.sh        # push and deploy, then verify")
        print("  A correction that is committed but not deployed is worse than")
        print("  none: everyone reading the commit believes it is fixed.\n")
        return 1
    if unreadable and same == 0:
        print(f"  {YEL}nothing could be read -- this is not a pass{OFF}\n")
        return 2
    if unreadable:
        print(f"  {YEL}{same} page(s) match; {len(unreadable)} could not be read{OFF}\n")
        return 2
    print(f"  {GRN}all {same} page(s) live are byte-identical to this repository{OFF}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

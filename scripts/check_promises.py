#!/usr/bin/env python3
# Copyright (c) 2026 The WAM Coin developers
# Distributed under the MIT software license, see COPYING.
"""
===============================================================================
 check_promises.py -- a page may not promise something about itself forever
===============================================================================

     python3 scripts/check_promises.py

 WHY THIS EXISTS

 Until 4 October 2026 the front page said:

     The founder mines too -- same software, same public pool ... and the
     addresses he mines to will be published here ... His share of the hash
     rate will be large at launch and is meant to fall; it will be published
     so you can watch it fall rather than take his word for it.

 He has never mined, and holds no WAM. The paragraph was written before
 launch, in the future tense, describing a plan -- and it was still there
 nineteen days after launch, now reading as a statement of what is happening.
 A reader asked the founder how many machines the project runs and quoted
 numbers back at him from pages in the same condition.

 The sentence being wrong is not the fault. The fault is that a page can
 promise to publish something, the date can pass, and nothing notices. The
 rehearsals page had the same shape on the same day: present tense from
 September, read in October.

 WHAT THIS DOES

 It finds, on the pages a stranger actually reads, sentences in which the page
 promises something about ITSELF -- "will be published here", "will be listed
 here", "will appear below". Each one is a debt the page owes its reader, and
 a debt with no due date is the kind that is never paid.

 It cannot know whether a promise has been kept; nothing can read a page and
 see an intention. So each one must be either fulfilled and rewritten in the
 past tense, removed, or -- if it is genuinely still ahead and still meant --
 marked as a quotation with a date beside it, which puts a person's name on
 the delay instead of letting silence carry it.

 It is deliberately narrow. "will be" in general is ordinary English and
 flagging it would make this noise. What is flagged is a promise whose subject
 is the page in front of the reader.
===============================================================================
"""

from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "lib"))
import quoted  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent

# This prints Arabic, and the founder runs it on Windows where the console
# encoding is cp1252 and raises on the first Arabic letter. A check that
# crashes while reporting a finding has reported nothing.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

RED = "\033[31m"; GRN = "\033[32m"; BLD = "\033[1m"; OFF = "\033[0m"

# The pages a stranger lands on, and the documents they are generated from.
# Both, because fixing the page without the source means the next build undoes
# it -- which this project has done before.
TARGETS = ["site/*.html", "site/*/*.html",
           "docs/START_HERE.md", "docs/START_HERE_AR.md", "docs/MINE.md",
           "WHITEPAPER.md", "README.md"]

EXCLUDE_DIRS = ("build/", "node_modules/", ".git/", "depends/")

# A promise the page makes about itself. The anchor is the place -- "here",
# "below", "on this page" -- because that is what makes it a debt rather than
# a description of the world.
# wam:quote-begin
PROMISES = [
    re.compile(r"will be (published|listed|shown|added|announced|named)[^.<]{0,40}"
               r"\b(here|below|on this page)\b", re.I),
    re.compile(r"will (appear|be found)[^.<]{0,30}\b(here|below)\b", re.I),
    re.compile(r"(ستُنشر|سيُنشر|ستُذكر|سيُذكر|ستُضاف|سيُضاف)[^.<]{0,30}(هنا|أدناه)", re.I),
]
# wam:quote-end

# A PROMISE IS A DEBT. AN OFFER IS NOT.
#
# "start one, say so and it will be listed here beside ours" matches every
# pattern above and owes nobody anything: it is an invitation, and it stays
# true for as long as it stands, whether or not anyone takes it up. Nothing
# ages about it.
#
# What ages is a promise where we are the only actor and the reader waits:
# "the addresses he mines to will be published here". That one had a due date
# whether or not it said so.
#
# The separator is whether the sentence asks the reader to do something first.
# It is imperfect -- an offer phrased without a condition would be read as a
# debt, and the answer to that is to phrase it with one.
# wam:quote-begin
CONDITIONAL = re.compile(
    r"\b(if |when you|should you|say so|tell us|let us know|ask us|"
    r"send us|إن |إذا |فأخبرنا|أخبرنا|من يُنشئ|ومن أراد)", re.I)
# wam:quote-end


def files():
    seen = []
    for pat in TARGETS:
        for p in sorted(ROOT.glob(pat)):
            rel = p.relative_to(ROOT).as_posix()
            if any(rel.startswith(d) for d in EXCLUDE_DIRS):
                continue
            if p.is_file() and rel not in seen:
                seen.append(rel)
    return seen


def main() -> int:
    scanned = files()
    hits = []

    offers = []
    for rel in scanned:
        text = quoted.strip_quoted(
            (ROOT / rel).read_text(encoding="utf-8", errors="replace"))
        lines = text.splitlines()
        for n, line in enumerate(lines, 1):
            for rx in PROMISES:
                m = rx.search(line)
                if not m:
                    continue
                # The condition may sit on the line before, because these are
                # wrapped paragraphs and a sentence spans lines.
                context = (lines[n - 2] if n >= 2 else "") + " " + line
                row = (rel, n, m.group(0).strip(), line.strip()[:110])
                (offers if CONDITIONAL.search(context) else hits).append(row)
                break

    print()
    print(f"{BLD}no page promises something about itself and then forgets{OFF}")
    print(f"  pages: {len(scanned)}")
    print()

    for rel, n, found, line in hits:
        print(f"  {RED}FAIL{OFF}  {rel}:{n}")
        print(f"          {BLD}{found}{OFF}")
        print(f"          {line}")

    for rel, n, found, line in offers:
        print(f"  {GRN}offer{OFF} {rel}:{n}  \"{found}\" — conditional on the "
              f"reader acting, so nothing is owed")

    if not hits:
        if offers:
            print()
        print(f"  {GRN}ok{OFF}    nothing is owed to a reader by a page that "
              f"cannot pay it")
        print()
        print(f"  {GRN}{BLD}every promise on a published page has been kept "
              f"or withdrawn{OFF}")
        print()
        return 0

    print()
    print(f"  {RED}{len(hits)} promise(s) a page makes about itself{OFF}")
    print()
    print("  Each is a debt to whoever reads it. Do one of three things:")
    print("    * it happened  -- rewrite it in the past tense, with the date")
    print("    * it will not  -- take the sentence out")
    print("    * still ahead  -- mark it as a quotation with the date it is")
    print("                     due, so a person owns the delay")
    print()
    print("  The front page said the founder's mining addresses 'will be")
    print("  published here' for nineteen days after a launch he did not mine.")
    print()
    return 1


if __name__ == "__main__":
    sys.exit(main())

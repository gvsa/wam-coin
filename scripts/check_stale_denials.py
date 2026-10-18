#!/usr/bin/env python3
# Copyright (c) 2026 The WAM Coin developers
# Distributed under the MIT software license, see COPYING.
"""
===============================================================================
 check_stale_denials.py -- a page may not deny what has since become true
===============================================================================

     python3 scripts/check_stale_denials.py

 WHY THIS EXISTS

 This project keeps writing sentences that say something does not exist, and
 they keep becoming false without anybody editing them.

 CHANNELS.txt says it best, in a paragraph it wrote about itself:

 <!-- wam:quote-begin -->
     That sentence used to name each platform it was denying, and it went out
     of date three times in two days -- once denying a Reddit account that was
     ours. A list of what does not exist has to be rewritten every time
     something does; a rule does not.
 <!-- wam:quote-end -->

 It then went out of date again. On 2026-10-15 it still read "no exchange
 listing, ... no wallet app", when WAM had been in the Komodo / GLEEC registry
 since 22 September and wam-qt had shipped with v0.1.11. The same day, four
 other live documents were found saying the same kind of thing:

     site/index.html        "there is no market to buy it on", eight lines
                            below its own sentence saying one venue merged it
     docs/START_HERE.md     "There is no price and no exchange. Nothing can
                            be sold"
     docs/MINE.md           "no exchange and nothing to sell them on"
     docs/LISTING_PACKAGE.md  "The chain has not launched" -- a month after
                            mainnet opened, in the document handed to venues

 THE DISTINCTION THIS CHECKS

 A sentence about what THIS PROJECT does is a rule, and it stays true because
 we keep it: "this project sets no price", "no presale", "he promises nothing".
 Those are not denials of fact and are not flagged.

 A sentence about what THE WORLD does is a claim, and we have no standing to
 make it: whether a venue lists the coin, whether somebody sells it, whether
 a market exists anywhere. We do not own the coin and do not control who
 trades it. A miner selling what he mined is his business, and a page of ours
 saying it cannot be done is both false and an instruction we have no right
 to give.

 EXIT CODES, this project's convention

     0  no live document denies a fact
     1  one does
     2  the documents could not be read
===============================================================================
"""

from __future__ import annotations

import pathlib
import re
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

# What a stranger reads today. Posts already sent are excluded on purpose: a
# record of what was said on a day is a quotation of that day, and rewriting
# it would be the dishonest half of this. integration/*/PR.md is the same --
# those PRs were submitted before mainnet and say so.
LIVE = ["site/*.html", "site/*/*.html", "site/CHANNELS.txt", "CHANNELS.txt",
        "README.md", "SECURITY.md", "WHITEPAPER.md", "docs/*.md"]

# Each entry: (pattern, what is wrong with it).
#
# These are denials about the world. None of them is a rule this project can
# keep, so none of them can be relied on to stay true.
DENIALS = [
    (r"\bnot listed on any (exchange|venue)\b",
     "whether a venue lists the coin is the venue's decision, not ours"),
    (r"\bno exchange listing\b",
     "whether a venue lists the coin is the venue's decision, not ours"),
    (r"\bthere is no (market|exchange)\b",
     "a market is made by the people trading, not by this project"),
    (r"\bno market to (buy|sell|trade) it\b",
     "a market is made by the people trading, not by this project"),
    (r"\bnothing (can be|may be) sold\b",
     "what a miner does with what he mined is his business"),
    (r"\bnothing to sell (them|it) on\b",
     "what a miner does with what he mined is his business"),
    (r"\bcannot be (bought|sold|traded)\b",
     "what a miner does with what he mined is his business"),
    (r"\bthe chain has not launched\b",
     "mainnet opened at 00:00 UTC on 15 September 2026"),
    (r"\bno wallet app\b",
     "wam-qt has shipped since v0.1.11, for three platforms"),
    (r"لا سوق\b",
     "a market is made by the people trading, not by this project"),
    (r"\bغير مدرجة?\b",
     "whether a venue lists the coin is the venue's decision, not ours"),
    (r"لا يوجد سعر ولا منصّة",
     "whether a venue lists the coin is the venue's decision, not ours"),
    (r"لا شيء يُباع",
     "what a miner does with what he mined is his business"),
    (r"لم تنطلق (الشبكة|السلسلة)",
     "mainnet opened at 00:00 UTC on 15 September 2026"),
    # THESE FOUR WERE MISSED, AND THE FRONT PAGE CARRIED ONE FOR TWO DAYS
    # AFTER THIS FILE WAS WRITTEN TO CATCH EXACTLY THEM.
    #
    # Under the heading "Trading", first screen, in both languages: WAM has
    # no price and cannot be bought with money on an exchange. A claim about
    # other people's venues and other people's money, on the page a newcomer
    # reads first, two days after six others like it were taken out.
    #
    # The patterns above were written from the sentences that were in front
    # of me rather than from the shape they share, so the shape got through
    # in words I had not happened to see.
    (r"\bthere is no price\b",
     "whether anyone prices it is not ours to state"),
    (r"\bcannot be bought\b|\bnot bought with money\b",
     "what somebody buys with his own money is his business"),
    (r"سعر لها\b",
     "whether anyone prices it is not ours to state"),
    (r"لا تُشترى|لا يُشترى|لا تُباع",
     "what somebody buys or sells with his own money is his business"),
]

COMPILED = [(re.compile(p, re.IGNORECASE), why) for p, why in DENIALS]

# "He promises nothing to anyone -- no return, no appreciation, no exchange
# listing" is a rule about what this project undertakes, not a claim that no
# venue lists the coin. It stays true however many venues list it, because
# keeping it costs us nothing but silence. The distinction this whole check
# rests on is which side of the sentence the subject is on, and a promise is
# always on ours.
RULE_FORM = re.compile(r"\b(promis\w*|undertak\w*|guarantee\w*|يَعِد|وعد)\b",
                       re.IGNORECASE)

# AND A SENTENCE SCOPED TO OUR OWN PAGE IS A RULE TOO, NOT A CLAIM.
#
# "There is no price on this page and there never will be" is something this
# project keeps, and keeping it costs nothing but silence. Losing a true
# sentence to a check written for the false ones would be the same error in
# the other direction. The test does not change: whose behaviour does the
# sentence describe?
OUR_SCOPE = re.compile(r"(on this page|in this file|هذه الصفحة|هذا الملفّ)",
                       re.IGNORECASE)


def main() -> int:
    print(f"\n{BLD}no live page denies what has since become true{OFF}\n")

    files = []
    for pattern in LIVE:
        files.extend(sorted(p for p in ROOT.glob(pattern) if p.is_file()))
    if not files:
        print(f"  {YEL}no document matched, so nothing was checked.{OFF}\n")
        return 2

    findings = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        # Quotation marks are honoured, as everywhere else in this project:
        # CHANNELS.txt and docs/LISTING_PACKAGE.md both quote the wording
        # they replaced, and a record of a fixed sentence is not the sentence.
        text = quoted.strip_quoted(
            path.read_text(encoding="utf-8", errors="replace"))
        for n, line in enumerate(text.splitlines(), 1):
            if RULE_FORM.search(line) or OUR_SCOPE.search(line):
                continue
            for rx, why in COMPILED:
                m = rx.search(line)
                if m:
                    findings.append((rel, n, m.group(0), why, line.strip()))

    if findings:
        for rel, n, hit, why, line in findings[:12]:
            print(f"  {RED}FAIL{OFF}  {rel}:{n}  {BLD}{hit}{OFF}")
            print(f"          {line[:88]}")
            print(f"          {why}")
        if len(findings) > 12:
            print(f"          ... and {len(findings) - 12} more")
        print()
        print(f"  {RED}{BLD}{len(findings)} live sentence(s) deny something "
              f"this project does not control{OFF}")
        print("  Say what this project does instead: \"this project sets no")
        print("  price and runs no market\" is a rule we keep. \"There is no")
        print("  market\" is a claim about other people, and it was false the")
        print("  day somebody offered to buy.\n")
        return 1

    print(f"  {GRN}{BLD}{len(files)} live document(s), none of them denying a "
          f"fact{OFF}\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(2)

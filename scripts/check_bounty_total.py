#!/usr/bin/env python3
# Copyright (c) 2026 The WAM Coin developers
# Distributed under the MIT software license, see COPYING.
"""
===============================================================================
 check_bounty_total.py -- what the pages say has been paid, against the ledger
===============================================================================

     python3 scripts/check_bounty_total.py

 WHY THIS EXISTS

 Four places state how much this project has paid in bounties, and to how
 many people:

     SECURITY.md          "21,250 WAM to four people", in prose
     SECURITY.md          one PAID entry per payment, with txid and rung
     site/index.html      "21,250 WAM has been paid against it so far"  (en)
     site/index.html      the same sentence in Arabic
     site/index.html      "an organic exchange has happened four times"

 They are edited by different hands at different moments and nothing made
 them move together, so on 2026-10-13 they stopped agreeing with each other:
 the footer said 21,000 WAM, which was correct and included three payments,
 while the paragraph above it said the exchange had happened "twice" and
 named two. Both sentences were on the same page, visible at the same time,
 and the number in one contradicted the count in the other for two days. The
 founder found it by reading his own front page.

 That is the same mechanism as scripts/set_version.py: a figure that lives in
 two kinds of place, moved by hand, with nothing asking whether the copies
 agree. The answer is the same -- make something ask.

 WHAT THIS DOES

 It adds up the PAID entries in SECURITY.md, and requires every published
 figure to match that sum: the total, the number of people, and the count in
 the "organic exchange" sentence. An unpaid or unclaimed entry is counted as
 neither, because it has not been paid.

 It does not verify the payments themselves against the chain. That is
 scripts/check_treasury_ledger.py, which checks every row and the balance
 identity to the atom. This checks that the prose agrees with the ledger;
 that checks that the ledger agrees with the chain.

 EXIT CODES, this project's convention

     0  every published figure matches the paid entries
     1  one does not
     2  the entries could not be read, so nothing was compared
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

# A bounty heading: "**10,000 WAM — <what>, accepted <date>, PAID <date>.**"
#
# The word "paid" is what makes it count, and it is matched case-insensitively
# with "un" excluded: this file has written PAID, "first instalment paid",
# "not claimed" and "unpaid", and a check keyed to one spelling found three
# payments out of four on its first run. The lookbehind is the whole of the
# difference between counting "unpaid" and not.
ENTRY = re.compile(r"^\*\*([\d,]+) WAM\s*[—-]\s*(.+?)\*\*", re.MULTILINE | re.DOTALL)
PAID = re.compile(r"(?<![a-z])(?<!un)paid\b", re.IGNORECASE)

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

COUNT_WORDS = {1: ("once", "مرّة"), 2: ("twice", "مرّتين"),
               3: ("three times", "ثلاث مرّات"), 4: ("four times", "أربع مرّات"),
               5: ("five times", "خمس مرّات"), 6: ("six times", "ستّ مرّات"),
               7: ("seven times", "سبع مرّات"), 8: ("eight times", "ثماني مرّات")}

PEOPLE_WORDS = {1: ("one person", "شخص واحد"), 2: ("two people", "شخصين"),
                3: ("three people", "ثلاثة أشخاص"), 4: ("four people", "أربعة أشخاص"),
                5: ("five people", "خمسة أشخاص"), 6: ("six people", "ستّة أشخاص"),
                7: ("seven people", "سبعة أشخاص"), 8: ("eight people", "ثمانية أشخاص")}


def paid_entries(text):
    """[(amount_in_wam, heading)] for every entry whose heading says PAID."""
    out = []
    for m in ENTRY.finditer(text):
        heading = " ".join(m.group(2).split())
        if not PAID.search(heading):
            continue
        out.append((int(m.group(1).replace(",", "")), heading))
    return out


def fmt(n):
    return "{:,}".format(n)


def main() -> int:
    print(f"\n{BLD}what the pages say has been paid, against the ledger{OFF}\n")

    sec = ROOT / "SECURITY.md"
    index = ROOT / "site" / "index.html"
    for p in (sec, index):
        if not p.is_file():
            print(f"  {YEL}{p.relative_to(ROOT)} is not here, so nothing was "
                  f"compared.{OFF}\n")
            return 2

    # Quotation marks are honoured, as in every other text-scanning check
    # here: this file quotes the wording it replaced more than once, and a
    # quoted "21,000 WAM" is a record of what the page used to say, not a
    # claim the page is making now.
    sec_text = quoted.strip_quoted(sec.read_text(encoding="utf-8", errors="replace"))
    entries = paid_entries(sec_text)
    if not entries:
        print(f"  {YEL}no PAID entry was found in SECURITY.md -- either the "
              f"heading format changed or nothing has been paid. Nothing was "
              f"compared.{OFF}\n")
        return 2

    total = sum(a for a, _ in entries)
    count = len(entries)

    print(f"  {count} paid entr{'y' if count == 1 else 'ies'} in SECURITY.md, "
          f"{fmt(total)} WAM in all")
    for amount, heading in entries:
        print(f"      {fmt(amount):>7} WAM   {heading[:64]}")
    print()

    bad = []

    # 1. The prose total in SECURITY.md.
    if not re.search(r"\b%s WAM\b" % re.escape(fmt(total)), sec_text):
        bad.append(("SECURITY.md", f"does not state the total {fmt(total)} WAM"))
    else:
        print(f"  {GRN}ok{OFF}    SECURITY.md states {fmt(total)} WAM")

    # 2. The number of people, in SECURITY.md's prose.
    want_people = PEOPLE_WORDS.get(count)
    if want_people and not any(w in sec_text for w in want_people):
        bad.append(("SECURITY.md",
                    f"does not say the money went to {want_people[0]}"))
    elif want_people:
        print(f"  {GRN}ok{OFF}    SECURITY.md says {want_people[0]}")

    # 3. The front page, both languages. Its own digits may be Arabic-Indic.
    page = quoted.strip_quoted(
        index.read_text(encoding="utf-8", errors="replace")).translate(ARABIC_DIGITS)
    found = (re.findall(r"([\d,]+) WAM has been paid", page)
             + re.findall(r"([\d,]+) WAM[،,]? بكلّ مبلغ", page))
    stated = set(found)
    if not stated:
        bad.append(("site/index.html",
                    "states no paid total at all -- the sentence that carried "
                    "it has moved or gone"))
    elif stated != {fmt(total)}:
        bad.append(("site/index.html",
                    "says %s, and the ledger adds up to %s"
                    % (", ".join(sorted(stated)), fmt(total))))
    else:
        print(f"  {GRN}ok{OFF}    site/index.html states {fmt(total)} WAM, in "
              f"{len(found)} sentence(s)")

    # 4. The "organic exchange has happened N times" count, which is the one
    #    that went stale while the total beside it stayed right.
    want_count = COUNT_WORDS.get(count)
    if want_count:
        for word in want_count:
            if word not in page:
                bad.append(("site/index.html",
                            "does not say the exchange has happened %r -- that "
                            "sentence counts the same payments" % word))
        if not any((w, ) for w in want_count if w not in page):
            print(f"  {GRN}ok{OFF}    site/index.html counts the exchange "
                  f"{want_count[0]}, in both languages")

    print()
    if bad:
        for where, why in bad:
            print(f"  {RED}FAIL{OFF}  {where}: {why}")
        print()
        print(f"  {RED}{BLD}a published figure does not match the paid "
              f"entries{OFF}")
        print("  These numbers are read by people deciding whether to trust the")
        print("  bounty table at all. Two of them disagreeing on the same page")
        print("  is worse than either one being out of date alone.\n")
        return 1

    print(f"  {GRN}{BLD}every published figure matches the ledger{OFF}\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(2)

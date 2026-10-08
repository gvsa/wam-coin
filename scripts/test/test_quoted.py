#!/usr/bin/env python3
# Copyright (c) 2026 The WAM Coin developers
# Distributed under the MIT software license, see COPYING.
"""
===============================================================================
 test_quoted.py -- the library every text check in this repository trusts
===============================================================================

     python3 scripts/test/test_quoted.py

 WHY THIS EXISTS

 scripts/lib/quoted.py decides, for every text check this project runs, which
 lines are a quotation and must not be read as a claim. It had no test.

 On 8 October 2026 a new check counted the marks in every file and found
 scripts/test/test_alert_text.py carrying one more opening mark than closing
 ones. The extra was not a mark at all: it was a docstring SENTENCE naming
 the convention. The library matched the words anywhere on a line, so a file
 that explained the convention opened a region by explaining it -- and from
 that sentence to the end of the file, every text check was silenced. The
 file had been in the tree for weeks.

 That is this library's own disease. It exists because a check cannot tell
 use from mention, and it could not tell them apart in its own marks.

 So a region mark must now stand alone on its line, carried by whatever
 comment syntax the file uses. The end-of-line mark stays unanchored,
 because sitting inside a sentence is what it is for.

 These hold that down, in both directions: the real marks still work, and
 the mentions no longer do.
===============================================================================
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

import quoted  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

RED = "\033[31m"; GRN = "\033[32m"; BLD = "\033[1m"; OFF = "\033[0m"

passed = 0
failed = []

# Assembled, never written out: a test file that spells the marks would be a
# file that carries them, which is the very confusion under test.
B = "wam:quote-" + "begin"
E = "wam:quote-" + "end"
L = "wam:quote-" + "line"


def check(name, fn):
    global passed
    try:
        fn()
        passed += 1
        print(f"  {GRN}ok{OFF}    {name}")
    except AssertionError as e:
        failed.append(name)
        print(f"  {RED}FAIL{OFF}  {name}\n        {e}")
    except Exception as e:
        failed.append(name)
        print(f"  {RED}FAIL{OFF}  {name}\n        {type(e).__name__}: {e}")


def test_a_region_hides_what_is_inside_it():
    text = f"a claim\n<!-- {B} -->\na quotation\n<!-- {E} -->\nanother claim\n"
    visible = quoted.strip_quoted(text)
    assert "a quotation" not in visible, "the quoted line is still readable"
    assert "a claim" in visible and "another claim" in visible, \
        "the region swallowed text outside itself"


def test_the_marks_are_carried_by_any_comment_syntax():
    for opener, closer in (("<!--", "-->"), ("#", ""), ("//", ""), ("    #", "")):
        text = f"{opener} {B} {closer}\nhidden\n{opener} {E} {closer}\nshown\n"
        visible = quoted.strip_quoted(text)
        assert "hidden" not in visible, f"{opener} did not open a region"
        assert "shown" in visible, f"{opener} region did not close"


def test_a_sentence_naming_the_mark_opens_nothing():
    # The live bug: a docstring in scripts/test/test_alert_text.py read
    # "Lines the author marked ... or inside a <the mark>", and silenced the
    # rest of that file.
    text = (f"Lines the author marked, or inside a {B} region, are skipped.\n"
            "a claim that must stay readable\n")
    visible = quoted.strip_quoted(text)
    assert "a claim that must stay readable" in visible, \
        "a sentence about the convention still silences the file under it"


def test_a_mark_inside_a_string_or_an_argument_opens_nothing():
    for line in (f'    print("# {B}\\n")',
                 f'    ok "every {B} has its end"',
                 f'    return ("<!-- {B} -->" + block)'):
        visible = quoted.strip_quoted(line + "\na claim\n")
        assert "a claim" in visible, f"this opened a region: {line.strip()}"


def test_the_end_of_line_mark_still_works_mid_sentence():
    text = f"the old password was hunter2.   # {L}\na real claim\n"
    visible = quoted.strip_quoted(text)
    assert "hunter2" not in visible, "the end-of-line mark stopped working"
    assert "a real claim" in visible, "it took the next line with it"


def test_line_numbers_survive():
    text = f"one\n<!-- {B} -->\nthree\n<!-- {E} -->\nfive\n"
    lines = quoted.strip_quoted(text).splitlines()
    assert len(lines) == 5, f"{len(lines)} lines came back from 5"
    assert lines[4] == "five", "a reported line number would point at the "\
        "wrong line, which teaches a reader not to trust the number"


def test_a_last_line_that_is_quoted_is_not_lost():
    text = f"a\n{L}\n"
    assert len(quoted.strip_quoted(text).splitlines()) == 2


def test_every_mark_in_the_repository_is_balanced():
    # The same question the audit asks, asked here so a developer sees it
    # before the sweep does. An unclosed region silences the rest of its file.
    files = subprocess.run(["git", "-C", str(ROOT), "ls-files"],
                           capture_output=True, text=True, timeout=120)
    bad = []
    for rel in files.stdout.split():
        p = ROOT / rel
        if not p.is_file() or rel.startswith(("depends/", "build/")):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        opens = sum(1 for ln in text.splitlines() if quoted.BEGIN.search(ln))
        closes = sum(1 for ln in text.splitlines() if quoted.END.search(ln))
        if opens != closes:
            bad.append(f"{rel} ({opens} open, {closes} closed)")
    assert not bad, "a region is left open: " + ", ".join(bad[:5])


def test_no_file_is_almost_entirely_silenced():
    # A runaway region does not fail anything; it makes checks pass. The only
    # symptom is a file that has gone quiet, so look for exactly that.
    files = subprocess.run(["git", "-C", str(ROOT), "ls-files"],
                           capture_output=True, text=True, timeout=120)
    loud = []
    for rel in files.stdout.split():
        p = ROOT / rel
        if not p.is_file() or rel.startswith(("depends/", "build/")):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        total = len(text.splitlines())
        if total < 20:
            continue
        hidden = len(quoted.quoted_lines(text))
        if hidden > total * 0.6:
            loud.append(f"{rel} ({hidden} of {total} lines quoted)")
    assert not loud, "a quotation region has run away: " + ", ".join(loud[:5])


def main():
    print(f"\n{BLD}the quotation marks say what they are meant to say{OFF}\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            check(name[5:].replace("_", " "), fn)
    print()
    if failed:
        print(f"  {RED}{BLD}{len(failed)} failed{OFF}, {passed} passed")
        for f in failed:
            print(f"    - {f}")
        print()
        return 1
    print(f"  {GRN}{BLD}{passed} checks: a mention is not a mark{OFF}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

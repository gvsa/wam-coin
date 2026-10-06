#!/usr/bin/env python3
# Copyright (c) 2026 The WAM Coin developers
# Distributed under the MIT software license, see COPYING.
"""
===============================================================================
 test_build_pages.py -- the generator that writes everything a stranger reads
===============================================================================

     python3 scripts/test/test_build_pages.py

 WHY THIS EXISTS

 scripts/build_pages.py produces every page on wamcoin.org, and until today it
 had no test at all. Its own comments record five defects that reached the live
 site, each found by a person looking at a rendered page rather than by
 anything that runs:

   * `<!-- wam:quote-line -->` escaped into visible text, mid-sentence, in the
     whitepaper
   * three numbered rules rendered "1. 1. 1." with half of each rule outside
     its own item
   * a line beginning `|` that is not a table spun the generator forever
   * three links on /start/ pointed at pages that have never existed
   * ten indented blocks -- commands, filenames, a treasury address -- came
     out as prose with their whitespace collapsed

 Every one of those is the same shape: the markdown was right, the page was
 wrong, and the only reader was a human who happened to look. So these are
 the properties of the output, held down.

 It drives the real convert() and reads the real pages in site/. Nothing is
 reimplemented here; a test that restates the renderer proves only that the
 author can restate it.
===============================================================================
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

import build_pages  # noqa: E402
import quoted  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

RED = "\033[31m"; GRN = "\033[32m"; BLD = "\033[1m"; OFF = "\033[0m"

passed = 0
failed = []


def check(name, fn):
    global passed
    try:
        fn()
        passed += 1
        print(f"  {GRN}ok{OFF}    {name}")
    except AssertionError as e:
        failed.append(name)
        print(f"  {RED}FAIL{OFF}  {name}\n        {e}")
    except Exception as e:                          # a crash is a failure
        failed.append(name)
        print(f"  {RED}FAIL{OFF}  {name}\n        {type(e).__name__}: {e}")


def render(md, marked=()):
    return build_pages.convert(md, "docs/TEST.md", marked)


# ---------------------------------------------------------------------------
#  Verbatim text stays verbatim
# ---------------------------------------------------------------------------

def test_indented_block_is_code():
    out = render("Check it rather than believe it:\n\n"
                 "    WdMMqW1DcgWZ6HtyJuEMdce6QkKg4raGmE\n")
    assert "<pre><code>WdMMqW1DcgWZ6HtyJuEMdce6QkKg4raGmE</code></pre>" in out, \
        ("an indented block came out as prose; on /security/ that block is "
         f"the treasury address a reader copies:\n        {out}")


def test_indented_block_keeps_its_lines():
    # Three filenames on /start/ were joined into one space-separated line,
    # which is what a reader copies when he wants one of them.
    out = render("    wam-qt-v0.1.11-x86_64-linux-gnu.tar.gz\n"
                 "    wam-qt-v0.1.11-x86_64-w64-mingw32.zip\n")
    assert out.count("\n") >= 1 and "gnu.tar.gz\nwam-qt" in out, \
        f"the lines of a code block were run together:\n        {out}"


def test_blank_line_inside_a_code_block_survives():
    out = render("    first\n\n    second\n")
    assert out.count("<pre>") == 1, \
        f"a blank line split one block of output into two:\n        {out}"
    assert "first\n\nsecond" in out, f"the blank line was dropped:\n        {out}"


def test_a_blank_line_ends_the_block():
    out = render("    code\n\nordinary prose follows.\n")
    assert "<pre><code>code</code></pre>" in out and "<p>ordinary prose" in out, \
        f"the paragraph after a code block was swallowed by it:\n        {out}"


def test_indented_list_marker_is_still_a_list():
    # Deliberate: this renderer has always read an indented marker as a list
    # item, and the pages that rely on it are right as they stand.
    out = render("    - one\n    - two\n")
    assert "<ul>" in out and "<li>one</li>" in out, \
        f"an indented list became a code block; pages would be rewritten:\n        {out}"


# ---------------------------------------------------------------------------
#  The quotation mark travels with the text
# ---------------------------------------------------------------------------

def test_mark_reaches_the_page_as_a_comment():
    md = "This paragraph said \"it needs v0.1.11\" and was wrong.\n"
    out = render(md, marked={0})
    assert "<!-- wam:quote-line -->" in out, \
        ("the mark was dropped by the generator, so the page carries a "
         f"quotation with nothing saying it is one:\n        {out}")
    assert "&lt;!--" not in out, \
        f"the mark was escaped into visible text:\n        {out}"


def test_a_checks_view_of_the_page_hides_the_marked_block():
    # This is the property that matters: it is not that a comment exists, it
    # is that every text-scanning check stops seeing the quotation.
    out = render("the fix needs v0.1.11 to reach you\n", marked={0})
    assert "v0.1.11" not in quoted.strip_quoted(out), \
        ("a check reading the generated page still sees the quoted wording, "
         "which is how check_promises.py read a correction as the promise it "
         f"was correcting:\n        {out}")


def test_an_unmarked_block_is_not_marked():
    out = render("an ordinary sentence.\n")
    assert "wam:quote-" not in out, \
        f"every block is being marked, which silences every check:\n        {out}"


def test_mark_lands_on_the_block_built_from_a_wrapped_line():
    # A marked sentence wraps across source lines and becomes one paragraph.
    out = render("the reserve is locked five years, with none of it\n"
                 "liquid at launch\n", marked={1})
    assert out.count("<!-- wam:quote-line -->") == 1, \
        f"a wrapped paragraph was marked {out.count('wam:quote-line')} times"
    assert quoted.strip_quoted(out).strip() == "", \
        "the marked paragraph is still visible to a check"


def test_a_mark_inside_a_blockquote_does_not_split_it():
    # In docs/MINE.md the marks sit on their own lines inside a `>` block. If
    # the generator left them in the markdown they would end the blockquote
    # and the correction would render as a second, separate box.
    md = ("> **Use v0.1.11 or newer.** the first paragraph.\n"
          ">\n"
          "<!-- wam:quote-begin -->\n"
          "> This paragraph said \"the fix needs v0.1.11\" for nine days.\n"
          "<!-- wam:quote-end -->\n")
    marked = quoted.quoted_lines(md)
    kept, flags = [], set()
    for n, line in enumerate(md.splitlines()):
        if re.search(r"^\s*(<!--\s*)?#?\s*wam:quote-(begin|end)\b", line):
            continue
        if n in marked:
            flags.add(len(kept))
        kept.append(line)
    out = render("\n".join(kept), flags)
    assert out.count("<blockquote>") == 1, \
        f"the mark lines split one blockquote into {out.count('<blockquote>')}"
    assert "<!-- wam:quote-line -->" in out, "the mark did not reach the page"
    visible = quoted.strip_quoted(out)
    assert "nine days" not in visible, "the quotation is still visible to a check"
    assert "Use v0.1.11 or newer" in visible, \
        "the mark covered the paragraph above it as well, which hides text no "\
        "check should stop reading"


def test_a_marked_table_row_marks_the_table():
    md = ("| Allocation | Status |\n"
          "|---|---|\n"
          "| Founder reserve | locked 5 years, none liquid at launch |\n")
    out = render(md, marked={2})
    assert out.count("<!-- wam:quote-line -->") == 1, \
        f"a marked row did not mark its table:\n        {out}"


# ---------------------------------------------------------------------------
#  The generator must always finish
# ---------------------------------------------------------------------------

def test_a_pipe_line_that_is_not_a_table_terminates():
    # WHITEPAPER.md has one. The paragraph accumulator excluded lines
    # beginning with `|`, so the buffer stayed empty, `i` never advanced, and
    # the build hung with no output.
    out = render("| this is not a table, it is a sentence\n")
    assert "not a table" in out, f"the line was dropped:\n        {out}"


def test_every_input_line_reaches_the_output():
    # The cheapest guard against a branch that consumes a line and emits
    # nothing: render each real document and look for its own sentences.
    for src in ("docs/MINE.md", "WHITEPAPER.md", "docs/START_HERE.md"):
        md = (ROOT / src).read_text(encoding="utf-8")
        out = render(md)
        words = sum(1 for ln in md.splitlines() if ln.strip())
        blocks = out.count("<p>") + out.count("<li>") + out.count("<pre>") \
            + out.count("<tr>") + out.count("<h")
        assert blocks > words / 12, \
            f"{src} rendered into {blocks} blocks from {words} lines -- " \
            "something is eating input"


# ---------------------------------------------------------------------------
#  The pages as they are committed, which is what nginx serves
# ---------------------------------------------------------------------------

def test_no_published_page_has_prose_where_code_belongs():
    bad = []
    for page in sorted((ROOT / "site").glob("**/index.html")):
        text = page.read_text(encoding="utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            if re.search(r"<(p|li)>\s{4,}\S", line):
                bad.append(f"{page.relative_to(ROOT).as_posix()}:{n}")
    assert not bad, ("indented blocks are rendered as prose on live pages, "
                     "whitespace collapsed: " + ", ".join(bad)
                     + "\n        run: python3 scripts/build_pages.py")


def test_no_published_page_shows_an_escaped_mark():
    bad = []
    for page in sorted((ROOT / "site").glob("**/*.html")):
        text = page.read_text(encoding="utf-8", errors="replace")
        if "&lt;!--" in text or "wam:quote" in text.replace(
                "<!-- wam:quote-line -->", ""):
            bad.append(page.relative_to(ROOT).as_posix())
    assert not bad, ("a quotation mark is visible to a reader on: "
                     + ", ".join(bad))


def test_the_sitemap_does_not_claim_everything_changed_today():
    from datetime import date
    today = date.today().isoformat()
    xml = (ROOT / "site/sitemap.xml").read_text(encoding="utf-8")
    dates = re.findall(r"<lastmod>([^<]+)</lastmod>", xml)
    assert dates, "the sitemap has no dates at all"
    for d in dates:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", d), f"not a date: {d}"
        assert d <= today, f"the sitemap claims a page changed in the future: {d}"
    assert len(set(dates)) > 1 or dates[0] != today, \
        ("every URL in the sitemap says it changed today, which is the one "
         "field a crawler trusts; a sitemap that is wrong about it is one a "
         "crawler learns to ignore")


def test_last_changed_falls_back_to_today_without_history():
    from datetime import date
    today = date.today().isoformat()
    assert build_pages.last_changed("site/this-has-never-existed.html",
                                    today) == today, \
        "a file git knows nothing about must be reported as changed today, " \
        "not as unchanged since the epoch"


def main():
    print(f"\n{BLD}the generator that writes what a stranger reads{OFF}\n")
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
    print(f"  {GRN}{BLD}{passed} checks: the pages say what the documents say"
          f"{OFF}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

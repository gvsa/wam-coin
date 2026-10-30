#!/usr/bin/env python3
# Copyright (c) 2026 The WAM Coin developers
# Distributed under the MIT software license, see COPYING.
#
# ===========================================================================
#  check_wrapping.py -- does the text render the way it was written?
# ===========================================================================
#
#      python3 scripts/check_wrapping.py
#
#  WHY THIS EXISTS
#
#  On 2026-10-30 a correction was posted to a pool operator's #wam channel.
#  It had been written here, read before sending, and every fact in it was
#  right. It came out looking like this on a phone:
#
# wam:quote-begin
#      2. The network panel reads "0 peers". The same
#         page shows a block two
#      minutes old at height 31,202 and 545 KH/s, so that
#         field is reading
#      wrong, not the network.
# wam:quote-end
#
#  Nothing was wrong with the words. The text was hard-wrapped at 72 columns,
#  the way every file in this repository is, and Discord does NOT join those
#  lines the way standard markdown does: a single newline is a line break
#  there. So 72-column lines are emitted as 72-column lines, a phone wraps
#  them AGAIN at about 46, and the reader gets long line, short remainder,
#  long line. Inside a numbered item it is worse: the continuation renders at
#  a different indent from the marker's text, so the sentence visibly breaks
#  in half.
#
#  The founder saw it before this script did, in the channel, after sending.
#
#  WHAT IT ENFORCES
#
#  Prose in a text destined for a newline-preserving channel is not wrapped
#  by hand. One paragraph, one line; let the client wrap it to whatever width
#  the reader is holding.
#
#  Inside a ``` fence the opposite is true -- there the bytes are respected
#  and the wrap is the author's, so fences are skipped entirely. Commands,
#  link blocks and hashes keep their shape.
#
#  WHICH CHANNELS, AND WHY NOT THE REST
#
#  Discord, Telegram and X all preserve a single newline, so all three fail
#  the same way and all three are checked.
#
#  reddit.txt is NOT checked, and not because it is safe. Reddit's markdown
#  does the OPPOSITE -- old Reddit JOINS lines separated by one newline, so a
#  carefully wrapped paragraph arrives as one block. That is a different rule
#  with a different fix and it needs its own measurement first; writing it
#  here from a guess is how a check starts crying wolf.
#
#  bitcointalk.txt is not checked either. It is BBCode, read mostly on a
#  desktop where a 72-column block renders as the tidy block it looks like
#  here. The fault this script exists for is a phone fault.
#
#  WHAT IT CANNOT CATCH, SAID PLAINLY
#
#  It reads the files in this repository. The text actually pasted into a
#  channel is whatever was in the clipboard, and nothing here can see that.
#  A post composed in the Discord box, or edited after being copied out, is
#  invisible to every script this project has.
#
#  Exit 0 all good, 1 something would render wrong, 2 the check could not run.
# ===========================================================================

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import quoted  # noqa: E402  -- needs the path above

GRN, RED, YLW, BLD, OFF = "\033[32m", "\033[31m", "\033[33m", "\033[1m", "\033[0m"

# The channels that preserve a single newline. See the header for the two
# that are deliberately absent.
CHANNELS = ("discord.txt", "telegram.txt", "x.txt")

# ALREADY SENT, AND THEREFORE NOT EDITABLE.
#
# Every text in these directories was published before this check existed.
# posts/ is an archive: those files are what this project actually told
# people, on the day it told them, and editing one so a check passes would
# make this repository disagree with what is on Discord, Telegram and X.
# check_channels.py carries the same rule for the same reason.
#
# So they are named here rather than fixed. The list is five directories and
# it is not allowed to rot: a name in it that no longer exists FAILS this
# check, because a forgiveness nobody can see the subject of is just a hole.
PUBLISHED = (
    "posts/preannounce",
    "posts/v0.1.8",
    "posts/v0.1.9",
    "posts/v0.1.10",
    "posts/bounty-address-validation",
)

# A line is "wrapped" when it is long, stops mid-sentence, and has more text
# directly underneath it.
#
# The length floor is what keeps this quiet. A short line is a decision -- a
# URL on its own, a `Site        wamcoin.org` row, a heading -- and none of
# those come near the wrap column. Only a line that reaches it was put there
# by a margin rather than by a person.
MIN_WRAP = 64

# Ends a sentence, a clause or a block, so the break after it is intended.
# A comma, a dash or a bare word at the end is a margin talking.
ENDS = re.compile(r"[.!?:;؟؛)\]\"'`*>]\s*$")

LIST_MARK = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s+")
BARE_URL = re.compile(r"^\s*\S+://\S+\s*$")


def wrapped_lines(text):
    """[(line number, the line)] for every hand-wrapped prose line.

    Quoted regions are blanked first, with their line numbers kept. A post
    that SHOWS badly wrapped text -- which is how this fault was reported in
    the first place -- would otherwise be failed for the quotation and not
    for its own prose. check_mentions.py refused this script on its first
    sweep for exactly that, before any such post existed to prove it.
    """
    lines = quoted.strip_quoted(text).split("\n")
    out, fence = [], False
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            fence = not fence
            continue
        if fence or not line.strip():
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if not nxt.strip() or nxt.strip().startswith("```"):
            continue
        if LIST_MARK.match(nxt) or BARE_URL.match(line):
            continue
        if len(line.rstrip()) < MIN_WRAP or ENDS.search(line):
            continue
        out.append((i + 1, line.rstrip()))
    return out


def tracked():
    out = subprocess.run(["git", "ls-files", "posts"], cwd=str(ROOT),
                         capture_output=True, text=True)
    if out.returncode != 0:
        return None
    return [p.replace("\\", "/") for p in out.stdout.split()
            if p.rsplit("/", 1)[-1] in CHANNELS]


def main():
    print(f"\n{BLD}does the text render the way it was written?{OFF}")

    files = tracked()
    if files is None:
        print(f"  {RED}FAIL{OFF}  git could not list posts/ -- this proves nothing")
        print()
        return 2
    if not files:
        print(f"  {RED}FAIL{OFF}  no channel text was found -- this proves nothing")
        print()
        return 2

    # The forgiveness list is checked before it is used.
    gone = [d for d in PUBLISHED if not (ROOT / d).is_dir()]
    if gone:
        print(f"  {RED}FAIL{OFF}  PUBLISHED names {len(gone)} director(y/ies) that "
              f"are not here")
        for d in gone:
            print(f"          {d}")
        print("        A text is exempt because it was already sent. If the")
        print("        directory is gone the exemption is forgiving nothing,")
        print("        and the next new post inherits a hole. Edit the list.")
        print()
        return 1

    bad, exempt, clean = {}, 0, 0
    for rel in files:
        if any(rel.startswith(d + "/") for d in PUBLISHED):
            exempt += 1
            continue
        try:
            text = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        hits = wrapped_lines(text)
        if hits:
            bad[rel] = hits
        else:
            clean += 1

    print(f"  {GRN}ok{OFF}    {len(PUBLISHED)} director(ies) of already-sent text "
          f"are exempt ({exempt} files)")

    if bad:
        total = sum(len(v) for v in bad.values())
        print(f"  {RED}FAIL{OFF}  {total} hand-wrapped line(s) in {len(bad)} text(s)")
        for rel, hits in sorted(bad.items()):
            print(f"          {rel}")
            for n, line in hits[:3]:
                print(f"            :{n}  {line[:58]}...")
            if len(hits) > 3:
                print(f"            ... and {len(hits) - 3} more")
        print()
        print("        Discord, Telegram and X keep a single newline, so these")
        print("        go out at this width and the phone wraps them again:")
        print("        long line, short remainder, long line.")
        print("        One paragraph, one line. Keep the wrap inside ``` only.")
        print()
        return 1

    if clean == 0:
        print(f"  {YLW}!!{OFF}    every channel text here was already sent -- "
              f"nothing new to check")
        print()
        return 0

    print(f"  {GRN}ok{OFF}    {clean} unsent text(s) wrap nothing by hand")
    print()
    print(f"  {GRN}{BLD}what we wrote is what the reader will see{OFF}\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(2)

#!/usr/bin/env python3
# Copyright (c) 2026 The WAM Coin developers
# Distributed under the MIT software license, see COPYING.
"""
Does the part of the release note the BOT ACTUALLY SENDS name everything new?

    python3 scripts/test/test_announcement_covers_release.py [posts/vX/TAG_MESSAGE.txt]

WHY THIS EXISTS

v0.1.11 shipped the first graphical wallet this project ever built. The tag
message described it, with its three file names, under "WHAT ELSE IS IN IT".

bots/announce.js posts the first whole paragraphs that fit in twelve lines,
and nothing else, the moment the release is published. The miner fix was
first and the wallet was below it. So what reached Telegram and Discord was
two paragraphs about a mining defect and then "Full notes at the link below".

Nobody in the channels was told a wallet existed. A community member filled
that silence by building one of his own and posting a download link in the
chat, and the founder had to stop it and say publicly that it was not ours.
That is what an omission costs: not a missing sentence, but somebody else
answering the question in our place.

docs/RELEASING.md already says to render what the bot would send before
tagging, and it was rendered. It was read for SHAPE -- whole paragraphs, no
sentence cut in half -- and not for COVERAGE. "Remember to put the important
thing first" is not a mechanism, so this is the mechanism.

WHAT IT CHECKS

If the release carries an artefact of a kind, the twelve lines the bot sends
must contain a word a reader would recognise it by. Nothing more clever: the
failure was not subtle.

Exit 0 all good, 1 something new is unannounced, 2 the check could not run.
"""
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
GRN, RED, YLW, BLD, OFF = "\033[32m", "\033[31m", "\033[33m", "\033[1m", "\033[0m"

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

# An artefact a reader acts on, and the words that would tell him it is there.
# The archive prefix is what package_release.sh and package_platform.sh name
# the file, so this list cannot drift away from what is actually shipped.
KINDS = [
    ("wam-qt",    ("wallet", "wam-qt", "graphical")),
    ("wam-miner", ("miner", "mine", "wam-miner")),
    ("wam-coin",  ("node", "wamd", "wam-coin")),
]


def bot_text(tag_message: pathlib.Path) -> str:
    """Exactly what bots/announce.js would send, rendered by that same file."""
    script = """
    const A = require('./bots/announce.js');
    const { toDiscord } = require('./bots/lib/markup.js');
    const txt = require('fs').readFileSync(process.argv[1], 'utf8');
    const body = txt.split('-'.repeat(78))[1].replace(/^\\n+/, '');
    console.log(toDiscord(A.releaseMessage({ tag: 'v0.0.0', name: 'render',
      url: 'https://wamcoin.org/downloads/', body, prerelease: true })));
    """
    out = subprocess.run(["node", "-e", script, str(tag_message)],
                         cwd=ROOT, capture_output=True, text=True)
    if out.returncode != 0:
        print(f"  {RED}could not render{OFF}  {out.stderr.strip()[:200]}")
        sys.exit(2)
    return out.stdout


def main() -> int:
    if len(sys.argv) > 1:
        notes = [pathlib.Path(sys.argv[1])]
    else:
        # THE NEWEST ONE, AND ONLY IT.
        #
        # This is a gate on what is about to be announced, not an audit of
        # what already was. v0.1.11's wallet is below the fold and always will
        # be -- the message was sent, and editing the file now would be
        # rewriting the record of what the channels actually received. A check
        # that fails for ever on something nobody can change is a check people
        # learn to skip, and the next real failure goes with it.
        found = sorted((ROOT / "posts").glob("v*/TAG_MESSAGE.txt"),
                       key=lambda q: [int(n) for n in
                                      re.findall(r"\d+", q.parent.name)])
        notes = found[-1:]
    if not notes:
        print("  no TAG_MESSAGE.txt to check")
        return 0

    bad = 0
    for note in notes:
        version = note.parent.name
        sent = bot_text(note).lower()
        # The whole note, to know what the release actually contains. The file
        # names are the evidence; the prose around them is not.
        whole = note.read_text(encoding="utf-8").lower()

        print(f"\n{BLD}{version}{OFF}  what the bot sends is "
              f"{len(sent.splitlines())} lines")

        for prefix, words in KINDS:
            shipped = re.search(rf"{re.escape(prefix)}-v[0-9]", whole)
            if not shipped:
                continue
            if any(w in sent for w in words):
                print(f"  {GRN}ok{OFF}    {prefix} ships, and the sent part "
                      f"says so")
            else:
                print(f"  {RED}FAIL{OFF}  {prefix} ships and the part the bot "
                      f"SENDS never mentions it")
                print(f"        It is in the notes, below the twelve lines "
                      f"the bot cuts at.")
                print(f"        A reader in the channels is not told it "
                      f"exists, and somebody")
                print(f"        else will answer the question in our place.")
                bad += 1

    print()
    if bad:
        print(f" {RED}{BLD}{bad} thing(s) shipped unannounced{OFF}\n")
        return 1
    print(f" {GRN}{BLD}everything shipped is named in what the bot "
          f"actually sends{OFF}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

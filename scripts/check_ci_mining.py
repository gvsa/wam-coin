#!/usr/bin/env python3
# Copyright (c) 2026 The WAM Coin developers
# Distributed under the MIT software license, see COPYING.
#
# ===========================================================================
#  check_ci_mining.py -- nothing of ours hashes on somebody else's machine
# ===========================================================================
#
#      python3 scripts/check_ci_mining.py
#
#  WHY THIS EXISTS
#
#  On 2026-09-24 a step in platform-build.yml mined two regtest blocks on a
#  GitHub runner. The account was suspended within the hour, and with it went
#  the repository, every release download, raw.githubusercontent.com and
#  wamcoin.org -- all 404 to the public, on a release day.
#
#  The chain was worthless and the intent was a correctness proof. Neither is
#  visible to an abuse detector, and GitHub's terms forbid mining on their
#  runners whatever the chain is worth.
#
#  The step was changed the same day: `--check` builds a block and hashes
#  nothing, `--solo` mines and runs only on hardware this project owns. That
#  fix has held for five weeks and nothing enforces it. One `--solo` typed
#  back into a workflow by somebody who does not know this story, and the
#  third account goes the way of the first.
#
#  WHAT THIS IS NOT
#
#  It is NOT an objection to building on hosted CI. Building is what CI is
#  for, every serious project does it, and this project did it for v0.1.8
#  through v0.1.12 without trouble. The line is not between our machines and
#  theirs -- it is between work and PROOF OF WORK.
#
#  On 2026-10-31 that distinction was lost here: an unexplained suspension was
#  read as "builds caused it", a rule was built on the reading, and the whole
#  release pipeline was nearly deleted. The answer was in this repository the
#  whole time, written in the comment above the very step that caused it.
#
#  WHERE IT LOOKS
#
#  Every CI definition, not only GitHub's. The repository is published at
#  three companies and any of them can be given a pipeline; a guard that
#  reads one vendor's directory is a guard against one vendor.
#
#  COMMENTS ARE NOT STEPS
#
#  These files explain the incident at length, so they are full of the words
#  this check looks for. Whole-line comments are stripped before the search,
#  and the `wam:quote-` marks are honoured for anything else -- a check that
#  fires on the paragraph explaining why it exists is a check that gets
#  deleted.
#
#  Exit 0 all good, 1 something would hash on a runner, 2 it could not run.
# ===========================================================================

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import quoted  # noqa: E402  -- needs the path above

GRN, RED, YLW, BLD, OFF = "\033[32m", "\033[31m", "\033[33m", "\033[1m", "\033[0m"

# Any vendor's pipeline, because the repository lives at three companies.
CI_GLOBS = (
    ".github/workflows/*.yml", ".github/workflows/*.yaml",
    ".gitea/workflows/*.yml", ".gitea/workflows/*.yaml",
    ".forgejo/workflows/*.yml", ".forgejo/workflows/*.yaml",
    ".gitlab-ci.yml", ".gitlab/ci/*.yml",
    ".woodpecker.yml", ".woodpecker/*.yml",
    ".circleci/config.yml", "azure-pipelines.yml", "Jenkinsfile",
    ".drone.yml", ".travis.yml", "appveyor.yml",
)

# Each is a way to compute proof of work, or to tell a node to.
#
# `--solo` is ours. The generate RPCs are Core's, and a workflow calling one
# is mining on the runner whichever binary it uses. The third group is the
# off-the-shelf miners an intruder would reach for, which is a different
# problem with the same ending: the account.
HASHES = (
    (r"--solo\b", "--solo mines; CI gets --check, which hashes nothing"),
    (r"\bgeneratetoaddress\b", "generatetoaddress mines blocks"),
    (r"\bgeneratetodescriptor\b", "generatetodescriptor mines blocks"),
    (r"\bsetgenerate\b", "setgenerate mines blocks"),
    (r"(?<![-\w])-generate\b", "-generate mines blocks"),
    (r"\b(?:xmrig|cpuminer|ethminer|nbminer|t-rex|lolminer)\b",
     "that is a miner, and not one of ours"),
)

# THE MINER MAY BE NAMED. IT MAY NOT BE RUN WITHOUT A HARMLESS FLAG.
#
# The first version of this matched the word anywhere on a line, and on its
# first run it reported six findings, every one of them a filename:
#
# wam:quote-begin
#     ls -l bin/wam-miner.exe
#     for n in wamd wam-cli wam-miner; do
#     for a in out/release/wam-miner-*.tar.gz
# wam:quote-end
#
# Packaging steps naming an artefact. That is the mention-against-use fault
# this repository keeps a library for, committed inside a guard written about
# not repeating mistakes -- caught by running it rather than by trusting it.
#
# An invocation is the name followed by whitespace and a flag. A filename is
# followed by a quote, a semicolon, a hyphen or the end of the line, and a
# loop word is followed by `;` or `do`. So the space and the dash are the
# whole distinction, and they are enough.
MINER = re.compile(r"(?<![\w-])[\w./$\"'-]*wam-miner(?:\.exe)?[\"']?\s+-")
MINER_OK = re.compile(r"--check\b|--self-test\b|--help\b|--version\b")

COMMENT = re.compile(r"^\s*#")


def steps_only(text):
    """The file with whole-line comments and quoted regions removed.

    Line numbers survive both, so a finding still names the real line.
    """
    kept = []
    skip = quoted.quoted_lines(text)
    for i, line in enumerate(text.splitlines()):
        kept.append("" if (i in skip or COMMENT.match(line)) else line)
    return kept


def ci_files():
    tracked = subprocess.run(["git", "ls-files"], cwd=str(ROOT),
                             capture_output=True, text=True)
    if tracked.returncode != 0:
        return None
    have = {p.replace("\\", "/") for p in tracked.stdout.split()}
    out = []
    for pat in CI_GLOBS:
        out += [p for p in have if pathlib.PurePosixPath(p).match(pat)]
    return sorted(set(out))


def main():
    print(f"\n{BLD}does anything of ours hash on somebody else's machine?{OFF}")

    files = ci_files()
    if files is None:
        print(f"  {RED}FAIL{OFF}  git could not list the tree -- this proves nothing")
        print()
        return 2
    if not files:
        print(f"  {YLW}!!{OFF}    no CI definition in the tree -- nothing to check")
        print()
        return 0

    findings = []
    for rel in files:
        try:
            text = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for n, line in enumerate(steps_only(text), 1):
            if not line.strip():
                continue
            for pat, why in HASHES:
                if re.search(pat, line):
                    findings.append((rel, n, line.strip(), why))
            if MINER.search(line) and not MINER_OK.search(line):
                findings.append((rel, n, line.strip(),
                                 "the miner runs here with neither --check "
                                 "nor --self-test"))

    if findings:
        print(f"  {RED}FAIL{OFF}  {len(findings)} step(s) would compute proof of "
              f"work on a hosted runner")
        for rel, n, line, why in findings[:8]:
            print(f"          {rel}:{n}")
            print(f"            {line[:66]}")
            print(f"            -- {why}")
        if len(findings) > 8:
            print(f"          ... and {len(findings) - 8} more")
        print()
        print("        This is the one thing that has actually cost this")
        print("        project an account: two regtest blocks on a GitHub")
        print("        runner on 2026-09-24, suspended within the hour, the")
        print("        site and every download 404 on a release day.")
        print("        Build on CI. Hash on hardware we own --")
        print("        scripts/test/test_platform_solo.sh is where it goes.")
        print()
        return 1

    print(f"  {GRN}ok{OFF}    {len(files)} CI definition(s), none of them hash")
    print()
    print(f"  {GRN}{BLD}CI builds; our own machines do the proof of work{OFF}\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(2)

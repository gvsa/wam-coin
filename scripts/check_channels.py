#!/usr/bin/env python3
"""Does the canonical channel list actually name everything that is ours?

    python3 scripts/check_channels.py
    python3 scripts/check_channels.py --offline    # skip the reachability pass

WHY THIS EXISTS

CHANNELS.txt has one job: tell a reader which accounts and hosts are ours,
so that everything else claiming to be WAM can be dismissed. A channel that
is ours and missing from the file does not merely go unlisted -- the file
says "There are no others", so the omission actively brands our own
property an impostor's, and hands anyone who wants to discredit it a
quotation from our own repository.

That has now happened twice.

  Revision 2, 21 August   the explorer, the pool and the Electrum server
                          were live and unlisted
  Revision 3, 4 September the BitcoinTalk announcement thread, up since
                          14 August -- three days after revision 1 -- and
                          the contact address published in SECURITY.md

Revision 2's own note explains the failure exactly, and it happened again a
fortnight later, because the fix was a person remembering and the person did
not. This is the check that does the remembering.

WHAT IT ENFORCES

  1. The two copies -- CHANNELS.txt and site/CHANNELS.txt -- are identical.
     They drifted for a fortnight: the repository root sat at revision 1
     while the site served revision 2, so "the canonical list" named two
     different sets of channels depending on where you read it.

  2. Every URL and address the project publishes about ITSELF, anywhere in
     the documentation, appears in the list. This is the direction that
     catches the real bug: something becomes ours, gets written about, and
     never reaches the file.

  3. Every listed channel resolves. A dead entry in an anti-impersonation
     list is worse than no entry, because a squatter can take the name.

WHAT IT CANNOT CATCH, SAID PLAINLY

It would NOT have caught the BitcoinTalk omission it was written for.

The thread URL appeared nowhere in this repository -- that is precisely why
nobody noticed it for three weeks -- and rule 2 can only compare the list
against what the repository already says somewhere else. A channel that
exists solely in the founder's browser is invisible to any script.

So this catches the case where a channel is written about but unlisted (the
explorer, the pool and the Electrum server, August 21), and the case where
the two copies drift (which had already happened, silently, for a
fortnight). The remaining case -- a channel created and never written down
at all -- has no automated answer, and pretending otherwise would be worse
than the gap. The answer to that one is a habit: a channel is not created
until it is in this file.

Exit 0 all good, 1 something is wrong, 2 the check could not run.
"""

import argparse
import pathlib
import re
import socket
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CANON = ROOT / "CHANNELS.txt"
MIRROR = ROOT / "site" / "CHANNELS.txt"

GRN, RED, YLW, BLD, OFF = "\033[32m", "\033[31m", "\033[33m", "\033[1m", "\033[0m"

# Where we talk about ourselves. Scanning the whole tree would drown the
# check in third-party URLs quoted in build notes and integration docs.
SOURCES = [
    "README.md", "SECURITY.md", "WHITEPAPER.md", "CONTRIBUTING.md",
    "docs/START_HERE.md", "docs/START_HERE_AR.md", "docs/LISTING_PACKAGE.md",
    "docs/POOL_OPERATOR.md", "site/index.html",
    "posts/launch.txt",
]
SOURCES += [str(p.relative_to(ROOT)) for p in (ROOT / "posts").rglob("*.txt")
            if p.name != "launch.txt"]

# AND THE WORKFLOWS, WHICH WRITE THE PAGE A STRANGER ACTUALLY READS.
#
# This list held documents, on the reasoning that documents are where we talk
# about ourselves. release.yml is not a document and it talks about us to more
# people than any of them: it composes the release notes, including the five
# commands that tell a reader how to verify what he just downloaded.
#
# On 2026-09-27 the draft notes for v0.1.11 told everybody to fetch
# SHA256SUMS, SHA256SUMS.asc, verify_release.sh and SIGNING-KEY.asc from
# github.com/wam-coin-official -- the account suspended on 24 September.
# Four dead URLs, in the one block whose entire purpose is to let somebody
# distrust us and check for himself.
#
# Thirty-two files were corrected that day and this one was not, because the
# check that finds them could not see it. A guard that reads only the places
# the fault was already fixed is not a guard.
SOURCES += [str(p.relative_to(ROOT))
            for p in (ROOT / ".github" / "workflows").glob("*.yml")]

# Hosts and handles that are ours. A URL is "ours" if it sits on one of
# these, which is what makes the omission direction checkable at all.
OURS = re.compile(
    r"""(?xi)
    (?: https?://(?:[a-z0-9-]+\.)*wamcoin\.org [^\s"'<>)\]]*
      | https?://(?:www\.)?gitlab\.com/WAMCoin [^\s"'<>)\]]*
      | https?://(?:www\.)?github\.com/wam-coin-official [^\s"'<>)\]]*
      | https?://t\.me/wam_coin[^\s"'<>)\]]*
      | https?://(?:www\.)?x\.com/WAMCoinCore[^\s"'<>)\]]*
      | https?://discord\.gg/[A-Za-z0-9]+
      | https?://bitcointalk\.org/index\.php\?topic=\d+[^\s"'<>)\]]*
      | https?://(?:www\.)?youtube\.com/@[A-Za-z0-9._-]+[^\s"'<>)\]]*
      | https?://(?:www\.|old\.)?reddit\.com/user/[A-Za-z0-9_-]+[^\s"'<>)\]]*
      | https?://bsky\.app/profile/[A-Za-z0-9._-]+[^\s"'<>)\]]*
      | https?://(?:www\.)?tiktok\.com/@[A-Za-z0-9._-]+[^\s"'<>)\]]*
      | https?://(?:www\.)?twitch\.tv/[A-Za-z0-9_]+[^\s"'<>)\]]*
      | [A-Za-z0-9._%+-]+@proton\.me
    )
    """)

# Trailing punctuation that belongs to the sentence, not the URL.
TRIM = ".,;:)]}>\"'`*"


def identity(u):
    """Reduce a URL to the CHANNEL it belongs to, not the page it points at.

    A channel is an account, a host or a thread -- something that can be
    impersonated and therefore has to be listed. Every path underneath one
    is the same channel:

        gitlab.com/WAMCoin/wam-coin/-/tags/v0.1.9
        gitlab.com/WAMCoin/wam-coin/-/blob/main/SECURITY.md
        gitlab.com/WAMCoin/wam-coin.git
                                    -> gitlab.com/WAMCoin

    GitHub is still matched, because CHANNELS.txt still names it and the
    signature over that file is only as good as the bytes it covers. It
    stops being a channel of ours the day that file is updated and
    re-signed with the offline key.

        wamcoin.org/og-card.png     -> wamcoin.org

    The first version of this compared whole URLs and reported nine
    "missing channels", every one of them a page inside a channel that was
    already listed. A check that cries wolf nine times out of nine gets
    ignored, which is exactly how the omission it exists to catch survived
    three weeks in the first place.
    """
    u = u.strip().rstrip(TRIM)
    low = u.lower()
    if "@" in low and "://" not in low:
        return low
    low = re.sub(r"^https?://", "", low)
    low = re.sub(r"^www\.", "", low)

    m = re.match(r"bitcointalk\.org/index\.php\?topic=(\d+)", low)
    if m:
        return f"bitcointalk.org/topic/{m.group(1)}"
    m = re.match(r"github\.com/([a-z0-9-]+)", low)
    if m:
        return f"github.com/{m.group(1)}"
    # A YouTube channel is its handle, and everything under it -- /videos,
    # /shorts, a single video -- is the same channel.
    m = re.match(r"youtube\.com/(@[a-z0-9._-]+)", low)
    if m:
        return f"youtube.com/{m.group(1)}"
    # old.reddit.com and www.reddit.com are the same account. Reddit answers
    # 403 to anything that is not a browser, which the reachability pass
    # already tolerates -- only 404 and 410 mean an account is gone.
    m = re.match(r"(?:old\.)?reddit\.com/user/([a-z0-9_-]+)", low)
    if m:
        return f"reddit.com/user/{m.group(1)}"
    # These three were invisible to this check until 10 September. The site
    # named a Bluesky, a TikTok and a Twitch account; CHANNELS.txt did not,
    # and said "There are no others" -- so our own signed list called three
    # of our own accounts impostors, and this check reported ok, because a
    # URL whose shape it does not recognise is a URL it never sees. It is the
    # third time in two days the list has been behind what exists, and the
    # first two were caught by a person, not by this.
    m = re.match(r"bsky\.app/profile/([a-z0-9._-]+)", low)
    if m:
        return f"bsky.app/profile/{m.group(1)}"
    m = re.match(r"(?:www\.)?tiktok\.com/(@[a-z0-9._-]+)", low)
    if m:
        return f"tiktok.com/{m.group(1)}"
    m = re.match(r"(?:www\.)?twitch\.tv/([a-z0-9_]+)", low)
    if m:
        return f"twitch.tv/{m.group(1)}"
    m = re.match(r"(t\.me|x\.com|discord\.gg)/([a-z0-9_-]+)", low)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    # Everything else is identified by its host: one host, one channel.
    return low.split("/")[0]


def find(text):
    """{channel identity: one URL that was written for it}"""
    out = {}
    for m in OURS.finditer(text):
        raw = m.group(0).rstrip(TRIM)
        out.setdefault(identity(raw), raw)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true",
                    help="skip the reachability pass")
    args = ap.parse_args()

    print()
    print(f"{BLD}does the canonical list name everything that is ours?{OFF}")

    if not CANON.exists():
        print(f"  {RED}FAIL{OFF}  {CANON} is missing")
        return 2
    if not MIRROR.exists():
        print(f"  {RED}FAIL{OFF}  {MIRROR} is missing")
        return 2

    canon_text = CANON.read_text(encoding="utf-8")
    bad = 0
    could_not_ask = 0

    # ---- 1. one list, not two ---------------------------------------
    if canon_text != MIRROR.read_text(encoding="utf-8"):
        print(f"  {RED}FAIL{OFF}  the two copies of the canonical list differ")
        print("        CHANNELS.txt and site/CHANNELS.txt must be identical.")
        print("        They drifted once already: the root sat at revision 1")
        print("        while the site served revision 2.")
        print("        Fix:  cp CHANNELS.txt site/CHANNELS.txt")
        bad += 1
    else:
        print(f"  {GRN}ok{OFF}    both copies of the list are identical")

    listed = find(canon_text)
    print(f"  {GRN}ok{OFF}    {len(listed)} channels listed")

    # A name the list explicitly DISOWNS is accounted for, not missing.
    #
    # When github.com/wam-coin-official was suspended on 2026-09-24, every
    # archive of a post that had ever linked it -- the launch announcement,
    # the pre-announcements, the v0.1.8 texts -- was suddenly reported as "a
    # channel of ours not in the list". Those archives are the record of what
    # was published on the day and must not be edited; doing so would make
    # this repository disagree with what is on BitcoinTalk.
    #
    # And the file does not ignore that name. It carries a section that sets
    # the name apart and says nothing appearing there should be trusted, which
    # is the opposite of the silent omission this check exists to catch. So a
    # host the file names in that section counts as handled.
    #
    # It is matched on the host, not the URL: the section cannot list every
    # path that was ever linked, and the danger being checked for belongs to
    # the account, not to one page under it.
    #
    # THE MARK IS THE HEADING'S STEM, NOT ITS CLAIM. It was "IS NO LONGER
    # OURS" until 2026-09-25, when the founder corrected the claim itself: a
    # suspended account keeps its name, the name stays with our email, and it
    # may yet come back -- so the file now says the name is LOCKED, AND STILL
    # OURS. The heading changed, this check stopped finding the section it was
    # looking for, and six archived posts were instantly reported as channels
    # of ours missing from the list. A check hooked to a sentence that is
    # allowed to be rewritten fails the moment somebody improves the wording,
    # and blames the file for it.
    DISOWN_MARK = "THE NAME THAT IS"
    disowned = set()
    if DISOWN_MARK in canon_text:
        tail = canon_text.split(DISOWN_MARK, 1)[1]
        # Prose names a host without a scheme -- "github.com/wam-coin-official
        # is not ours any more" -- and the URL matcher requires one, so the
        # first version of this found nothing it was looking for and reported
        # wamcoin.org, which is mentioned in the same paragraph. The scheme is
        # supplied here so the same matcher can be used on prose.
        tail = re.sub(r"(?<![/@.\w])((?:www\.)?(?:github|gitlab)\.com/[A-Za-z0-9._-]+)",
                      r"https://\1", tail)
        for u in find(tail):
            disowned.add(u)
        if disowned:
            print(f"  {GRN}ok{OFF}    {len(disowned)} name(s) the list disowns "
                  f"by name: {', '.join(sorted(disowned))}")

    # ---- 2. nothing of ours is missing from it ----------------------
    missing = {}
    scanned = 0
    for rel in dict.fromkeys(SOURCES):
        p = ROOT / rel
        if not p.exists():
            continue
        scanned += 1
        for u, raw in find(p.read_text(encoding="utf-8", errors="replace")).items():
            if u not in listed and u not in disowned:
                missing.setdefault(raw, []).append(rel)

    if missing:
        print(f"  {RED}FAIL{OFF}  {len(missing)} channel(s) of ours are not in "
              f"the list")
        print("        The list says \"There are no others\", so anything")
        print("        missing is branded an impostor's by our own file.")
        for u, where in sorted(missing.items()):
            print(f"          {u}")
            print(f"            published in: {', '.join(sorted(set(where)))}")
        bad += 1
    else:
        print(f"  {GRN}ok{OFF}    nothing of ours is published outside the list "
              f"({scanned} documents scanned)")

    # ---- 2b. and nothing DISOWNED is handed to somebody as a command ----
    #
    # The check above forgives a disowned name, and it must: this project
    # writes about the account it lost, and saying "that one is not us" is the
    # point of the file. But forgiveness was being applied to the whole text,
    # and a name inside a curl line is not being written about. It is being
    # handed to a reader as a place to fetch from.
    #
    # v0.1.11's draft release notes did exactly that: four curl lines pointing
    # at the suspended account, composed by release.yml, in the block whose
    # only purpose is to let a stranger verify the download without trusting
    # us. Every one of them answers 404. A reader who tried would conclude the
    # release cannot be checked, which is the worst thing this project can say
    # about itself by accident.
    # Two exclusions, and both are corrections to the first version of this.
    #
    # A name that is IN the list is not disowned, whatever paragraph it also
    # appears in. The disown parser reads the tail of a section and takes the
    # URLs in it, and that section explains where the downloads are -- so it
    # was calling wamcoin.org, this project's own site, a name we disown.
    #
    # And posts/ is an archive. Those files are what was actually sent, on the
    # day it was sent, and several were published before the account died.
    # Editing them so a check passes would be falsifying the record of what
    # this project told people. A reader of an archive is reading history; a
    # reader of a release note is being given a command to run.
    live = disowned - set(listed)
    FETCH = re.compile(r"^[^\n]*\b(?:curl|wget|git\s+clone)\b[^\n]*$", re.M)
    served = {}
    for rel in dict.fromkeys(SOURCES):
        if rel.replace("\\", "/").startswith("posts/"):
            continue
        p = ROOT / rel
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")

        # A workflow is machine input, never narrative, so ANY occurrence in
        # one is use. A line-based scan missed the case this was written for:
        # release.yml assigns the host to BASE and RAW on their own lines and
        # the curl lines say "$BASE". There was no dead name on any line with
        # curl on it, and four dead curl commands came out the other end.
        if rel.replace("\\", "/").startswith(".github/workflows/"):
            for dead in live:
                if dead in text:
                    served.setdefault(rel, set()).add(dead)
            continue

        for line in FETCH.findall(text):
            for dead in live:
                if dead in line:
                    served.setdefault(rel, set()).add(dead)

    if served:
        print(f"  {RED}FAIL{OFF}  a name the list disowns is used as a place to "
              f"download from")
        for rel, names in sorted(served.items()):
            print(f"          {rel}: {', '.join(sorted(names))}")
        print("        Writing about a dead name is honest. Telling somebody")
        print("        to fetch from it is handing them a 404 and calling it")
        print("        verification.")
        bad += 1
    elif live:
        print(f"  {GRN}ok{OFF}    no disowned name is used as a download source")

    # ---- 3. every listed channel still answers ----------------------
    if args.offline:
        print(f"  {YLW}skipped{OFF}  reachability (--offline)")
    else:
        dead = []
        unreachable = []
        # Fetch what the file actually WROTE, never the normalised form.
        # The first version fetched the lowercased identity and reported
        # wamcoin.org/CHANNELS.txt dead: the host is case-sensitive, the
        # file exists, and `channels.txt` does not. The check invented a
        # 404 for a file it was itself sitting next to.
        for u, url in sorted(listed.items()):
            if "@" in u and "/" not in u:
                continue                      # an address, nothing to fetch
            if not url.lower().startswith("http"):
                url = "https://" + url
            req = urllib.request.Request(url, method="GET",
                                         headers={"User-Agent": "wam-channel-check"})
            try:
                with urllib.request.urlopen(req, timeout=25) as r:
                    if r.status >= 400:
                        dead.append((u, f"HTTP {r.status}"))
            except urllib.error.HTTPError as e:
                # 403 is Cloudflare or a forum refusing a bare client, not a
                # dead channel. Only 404 and 410 mean the thing is gone.
                if e.code in (404, 410):
                    dead.append((u, f"HTTP {e.code}"))
            except (urllib.error.URLError, socket.timeout, OSError) as e:
                # NOT dead. A timeout, a DNS failure or a reset connection
                # means the question never arrived -- it says nothing about
                # whether the channel exists.
                #
                # These went into the same list as a 404, so on 7 September
                # one slow request put
                #
                #   the channel list names all of us   FAIL
                #         1 listed channel(s) do not answer
                #
                # on the launch panel, under a heading that reads "the
                # canonical list is not canonical" -- which a person takes to
                # mean somebody can squat one of our names. The same request
                # answered normally a minute later. This project has been here
                # before, in check_bots.py, where a single timed-out request
                # on a Libyan connection reported that announcements to a
                # healthy channel were silently going nowhere.
                unreachable.append((u, str(getattr(e, "reason", e))[:60]))

        if dead:
            print(f"  {RED}FAIL{OFF}  {len(dead)} listed channel(s) do not answer")
            print("        A dead entry is worse than no entry: the name is")
            print("        free for somebody else to take.")
            for u, why in dead:
                print(f"          {u}  --  {why}")
            bad += 1
        elif unreachable:
            print(f"  {YLW}!!{OFF}    {len(unreachable)} listed channel(s) could not "
                  f"be reached -- not the same as dead")
            for u, why in unreachable:
                print(f"          {u}  --  {why}")
            could_not_ask += len(unreachable)
        else:
            print(f"  {GRN}ok{OFF}    every listed channel answers")

    print()
    if bad:
        print(f"  {RED}{BLD}the canonical list is not canonical{OFF}")
        print()
        return 1
    if could_not_ask:
        # 2, this project's code for "the check could not run". Not 1, which
        # would say the list is wrong; not 0, which would say every channel
        # was confirmed alive when some were never asked.
        print(f"  {YLW}the list is consistent, but {could_not_ask} channel(s) "
              f"were not reached{OFF}")
        print(f"  Nothing here says they are dead. Run it again on a better "
              f"connection\n  before treating it as a finding.")
        print()
        return 2
    print(f"  {GRN}{BLD}the list names everything that is ours, and nothing "
          f"dead{OFF}")
    print()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(2)

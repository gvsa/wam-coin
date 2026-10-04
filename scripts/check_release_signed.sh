#!/bin/bash
# ===========================================================================
#  check_release_signed.sh -- is what the world can download actually signed?
# ===========================================================================
#
#      bash scripts/check_release_signed.sh            # the latest release
#      bash scripts/check_release_signed.sh v0.1.6
#
#  It asks GitHub what the release actually carries, downloads SHA256SUMS and
#  its signature, and verifies them against the fingerprint in SECURITY.md.
#
#  WHY IT ASKS GITHUB AND NOT THE WORKING TREE
#
#  Everything else here can be true while the published release is not. The
#  signing key can be present, package_release.sh can sign correctly, the
#  local files can verify perfectly -- and the asset uploaded to GitHub two
#  weeks ago can still be the unsigned one, because uploading is a manual
#  step and manual steps get half-done.
#
#  What a stranger downloads is the only thing that matters, so that is what
#  this reads.
# ===========================================================================

set -uo pipefail
cd "$(dirname "$0")/.."

GRN=$'\033[32m'; RED=$'\033[31m'; YLW=$'\033[33m'; BLD=$'\033[1m'; OFF=$'\033[0m'
REPO="${WAM_REPO:-wamcoin-core-dev/wam-coin}"
EXPECT="4BD4A8D3AFD43F5CBCB500E23798462FE00ADBA4"

fails=0
ok()   { printf '  %sok%s    %s\n' "$GRN" "$OFF" "$1"; }
bad()  { printf '  %sFAIL%s  %s\n' "$RED" "$OFF" "$1"; fails=$((fails+1)); }
warn() { printf '  %s!!%s    %s\n' "$YLW" "$OFF" "$1"; }

echo
echo "${BLD}can a stranger prove the download is ours?${OFF}"

command -v curl >/dev/null 2>&1 || { warn "curl is not installed"; echo; exit 2; }
command -v gpg  >/dev/null 2>&1 || { warn "gpg is not installed"; echo; exit 2; }

# The fingerprint in this script must be the one in SECURITY.md. Two copies of
# a fingerprint is two chances to publish the wrong one.
#
# Compared with every space removed from both sides. gpg prints a fingerprint
# in five-group blocks with a DOUBLE space in the middle, and the first version
# of this check rebuilt it with single spaces and then reported that the two
# files disagreed -- about two identical fingerprints. A check that cries
# about a correct file is how a person learns to skip its output.
norm() { printf '%s' "$1" | tr -d '[:space:]' | tr 'a-f' 'A-F'; }
if [ -f SECURITY.md ] && printf '%s' "$(norm "$(cat SECURITY.md)")" | grep -q "$(norm "$EXPECT")"; then
    ok "the fingerprint here matches SECURITY.md"
else
    bad "this script and SECURITY.md name different fingerprints"
fi

# WHERE THE DOWNLOADS ARE, WHICH IS NOT GITHUB ANY MORE.
#
# This asked api.github.com, and on 2026-09-26 the sweep reported "could not
# check" twice: sixty unauthenticated calls an hour is the whole budget, and
# a sweep spends them. So the one check that proves a stranger can verify our
# release was silenced by somebody else's rate limit.
#
# Every post, every page and CHANNELS.txt send people to wamcoin.org for the
# downloads. That is served from machines this project owns, it has no rate
# limit, and it is where the person this check speaks for will actually go.
# GitHub is one of three mirrors of the SOURCE; it is not where a wallet is
# fetched from, and a check must ask the place the reader will go.
#
# Overridable so the failure paths can be tested against a server that misbehaves
# on purpose -- see scripts/test/test_release_check_silence.sh. Nothing in
# production sets it; the default is the only address a reader is ever sent to.
DOWNLOADS="${WAM_DOWNLOADS:-https://wamcoin.org/downloads}"

TAG="${1:-}"
if [ -z "$TAG" ]; then
    # sort -V, or v0.1.9 wins over v0.1.10 in every other order.
    TAG="$(curl -sS --max-time 25 "$DOWNLOADS/" 2>/dev/null \
           | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | sort -V -u | tail -1)"
fi

if [ -z "$TAG" ]; then
    warn "wamcoin.org/downloads did not list any version"
    echo; exit 2
fi

tag="$TAG"

# NOT ASKED IS NOT ANSWERED NO.
#
# This read the body and nothing else. An nginx error page has a body, so the
# empty-string guard below never fired for one: the page was parsed for href=
# links, none were found, and the check concluded that SHA256SUMS IS NOT
# PUBLISHED -- which release_watch.py sends to Telegram and Discord as
# "the release DOES NOT VERIFY ... being told the signature is not valid".
#
# On the night of 2026-10-03 that went out twice, at 12:05 and at 03:29, and
# recovered at 12:16 and 03:39. Ten minutes each time, with nobody touching
# anything, because ten minutes is the watcher's interval: one failed poll
# alarms, the next one clears it. Nothing was ever wrong with the release. The
# founder saw the pattern before the cause and said so: a half-finished upload
# does not repair itself twice in a night.
#
# So: the status code is read, the body is checked for being our index at all,
# and a transient failure is retried before anything is concluded. Only a page
# that genuinely IS the listing may be used to say a file is missing from it.
#
# Exit 2 throughout, never 1. The watcher treats 2 as "could not ask" and says
# nothing, which is the correct behaviour when we do not know -- and the same
# distinction the pool payout path needed on the same day.
index=""
http=""
for attempt in 1 2 3; do
    body="$(curl -sS --max-time 25 -w '\n%{http_code}' "$DOWNLOADS/$tag/" 2>/dev/null)"
    http="${body##*$'\n'}"
    body="${body%$'\n'*}"
    if [ "$http" = "200" ] && printf '%s' "$body" | grep -q 'href="wam-'; then
        index="$body"
        break
    fi
    [ "$attempt" -lt 3 ] && sleep 5
done

if [ -z "$index" ]; then
    if [ "$http" = "200" ]; then
        # 200, but not our directory listing: a proxy page, a holding page, a
        # truncated response. Whatever it is, the absence of a name in it
        # proves nothing about the release.
        warn "wamcoin.org/downloads/$tag/ answered 200 but did not look like the"
        warn "download index -- no release archive is linked in it. Not reading"
        warn "a missing name out of a page that is not the list."
    else
        warn "wamcoin.org/downloads/$tag/ did not answer (HTTP ${http:-none}, 3 tries)"
    fi
    echo; exit 2
fi
names="$(printf '%s' "$index" | grep -oE 'href="[^"]+"' | cut -d'"' -f2)"
echo "  release: $tag"

for want in SHA256SUMS SHA256SUMS.asc; do
    if printf '%s\n' "$names" | grep -qx "$want"; then
        ok "$want is published"
    else
        bad "$want is NOT published -- the download cannot be verified by anyone"
    fi
done
[ "$fails" -gt 0 ] && { echo; printf '  %s%d problem(s)%s\n\n' "$RED" "$fails" "$OFF"; exit 1; }

T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
base="$DOWNLOADS/$tag"

# The same distinction as above, one level down and with sharper teeth.
#
# `curl -o` writes whatever arrives, including a 502 page, and gpg then
# verifies an HTML error document against a signature and says no. That path
# reports "the published signature does not verify" -- the single most
# alarming sentence this project can send -- because a web server hiccupped
# for one second. The release would be untouched and perfect throughout.
#
# Retried, status-checked, and anything but a clean 200 exits 2.
fetch() {
    local url="$1" out="$2" code
    for attempt in 1 2 3; do
        code="$(curl -sSL --max-time 40 -o "$out" -w '%{http_code}' "$url" 2>/dev/null)"
        [ "$code" = "200" ] && [ -s "$out" ] && return 0
        [ "$attempt" -lt 3 ] && sleep 5
    done
    warn "$url did not download (HTTP ${code:-none}, 3 tries)"
    return 1
}

fetch "$base/SHA256SUMS"     "$T/SHA256SUMS"     || { echo; exit 2; }
fetch "$base/SHA256SUMS.asc" "$T/SHA256SUMS.asc" || { echo; exit 2; }

# An empty keyring, so this proves what a stranger's machine would prove and
# not what ours happens to trust already.
gpg --homedir "$T" --batch --quiet --import SIGNING-KEY.asc 2>/dev/null
out="$(gpg --homedir "$T" --status-fd 1 --verify "$T/SHA256SUMS.asc" "$T/SHA256SUMS" 2>/dev/null)"

if printf '%s' "$out" | grep -q "GOODSIG"; then
    got="$(printf '%s' "$out" | grep -m1 "VALIDSIG" | awk '{print $3}')"
    if [ "$got" = "$EXPECT" ]; then
        ok "the published SHA256SUMS is signed by the published key"
    else
        bad "signed by $got, not by $EXPECT"
    fi
else
    bad "the published signature does not verify"
fi

echo
if [ "$fails" -eq 0 ]; then
    echo "  ${GRN}anyone downloading this release can prove it is ours${OFF}"
else
    echo "  ${RED}$fails problem(s) -- a downloader cannot tell this from a fake${OFF}"
fi
echo
exit $(( fails > 0 ))

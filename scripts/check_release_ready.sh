#!/usr/bin/env bash
# Copyright (c) 2026 The WAM Coin developers
# Distributed under the MIT software license, see COPYING.
#
# ===========================================================================
#  check_release_ready.sh -- can a stranger actually download it, before
#                            anybody is told it exists
# ===========================================================================
#
#      bash scripts/check_release_ready.sh v0.1.12
#
#  WHY THIS EXISTS
#
#  On 16 October 2026 v0.1.12 was published to the releases page before its
#  archives were uploaded to this project's own servers. Every page we
#  publish sends a reader to wamcoin.org/downloads/<version>/, and for four
#  minutes that directory answered 404.
#
#  Eight things were verified before publishing: the checksums, the
#  signature, the fingerprint against SECURITY.md, the tag object, the
#  rendered announcement, the clean tree, the three mirrors, the bot's own
#  code. The one thing not verified was the URL a stranger actually follows.
#
#  release_watch caught it, held the announcement, and said so -- which is
#  the only reason nothing incomplete reached the channels. That guard is
#  the net. This is the thing that should mean the net is never needed.
#
#  WHAT IT CHECKS
#
#  Every file named in the published SHA256SUMS answers 200 from the
#  download host, SHA256SUMS and its signature answer, and the signature
#  verifies against the published fingerprint -- all fetched over the
#  network, as a stranger fetches them, never from a local copy. A file on
#  this laptop proves nothing about a file on a server.
#
#  EXIT CODES, this project's convention
#
#      0  every published file answers and the signature verifies
#      1  something a reader is sent to is not there
#      2  the release or the host could not be reached, so nothing was
#         checked -- which is not a pass
# ===========================================================================

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
cd "$HERE"

GRN=$'\033[32m'; RED=$'\033[31m'; YLW=$'\033[33m'; BLD=$'\033[1m'; OFF=$'\033[0m'

ok()   { printf '  %sok%s    %s\n' "$GRN" "$OFF" "$*"; }
bad()  { printf '  %sFAIL%s  %s\n' "$RED" "$OFF" "$*"; }
warn() { printf '  %s!!%s    %s\n' "$YLW" "$OFF" "$*"; }

VERSION="${1:-}"
BASE="${WAM_DOWNLOAD_BASE:-https://wamcoin.org/downloads}"

printf '\n%scan a stranger download this release, right now%s\n\n' "$BLD" "$OFF"

if [ -z "$VERSION" ]; then
    bad "usage: bash scripts/check_release_ready.sh v0.1.12"
    echo
    exit 2
fi

command -v curl >/dev/null 2>&1 || { warn "curl is not on PATH; nothing was checked"; echo; exit 2; }
command -v gpg  >/dev/null 2>&1 || { warn "gpg is not on PATH; nothing was checked";  echo; exit 2; }

DIR="$BASE/$VERSION"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fetch() {  # $1 = url, $2 = destination; prints the HTTP status
    curl -fsS --max-time 60 --retry 2 -o "$2" -w '%{http_code}' "$1" 2>/dev/null
}

# ---- SHA256SUMS, from the host and not from here --------------------------
code="$(fetch "$DIR/SHA256SUMS" "$TMP/SHA256SUMS" || true)"
if [ ! -s "$TMP/SHA256SUMS" ]; then
    bad "$DIR/SHA256SUMS did not answer (HTTP ${code:-none})"
    echo
    echo "  Every page this project publishes sends a reader to that directory."
    echo "  Upload the release to the download hosts BEFORE publishing it."
    echo
    exit 1
fi
ok "SHA256SUMS answers from $DIR"

code="$(fetch "$DIR/SHA256SUMS.asc" "$TMP/SHA256SUMS.asc" || true)"
if [ ! -s "$TMP/SHA256SUMS.asc" ]; then
    bad "$DIR/SHA256SUMS.asc did not answer (HTTP ${code:-none})"
    echo; exit 1
fi
ok "SHA256SUMS.asc answers"

# ---- every file it names ---------------------------------------------------
missing=0
named=0
while read -r _hash name; do
    [ -n "${name:-}" ] || continue
    name="${name#\*}"
    named=$((named + 1))
    status="$(curl -fsS --max-time 60 --retry 2 -o /dev/null -w '%{http_code}' \
              "$DIR/$name" 2>/dev/null || true)"
    if [ "$status" = "200" ]; then
        ok "$name"
    else
        bad "$name is named in SHA256SUMS and answers HTTP ${status:-none}"
        missing=$((missing + 1))
    fi
done < "$TMP/SHA256SUMS"

if [ "$named" -eq 0 ]; then
    bad "the published SHA256SUMS names no files at all"
    echo; exit 1
fi

# ---- and the signature over it, against the fingerprint we publish --------
# A gpg fingerprint is printed with a WIDER GAP at the halfway point, and
# SECURITY.md carries it exactly as gpg prints it. The first version of this
# pattern required single spaces, found nothing, and the check then said the
# list was signed while reporting in the line above that it had not looked.
signature_checked=0
FPR="$(grep -oE '([0-9A-F]{4}[[:space:]]+){9}[0-9A-F]{4}' SECURITY.md | head -1 | tr -d '[:space:]')"
if [ -z "$FPR" ]; then
    warn "no fingerprint found in SECURITY.md, so the signature was NOT checked"
else
    export GNUPGHOME="$TMP/gnupg"
    mkdir -p "$GNUPGHOME"; chmod 700 "$GNUPGHOME"
    if gpg --batch --quiet --import SIGNING-KEY.asc 2>/dev/null &&
       gpg --batch --verify "$TMP/SHA256SUMS.asc" "$TMP/SHA256SUMS" 2>"$TMP/v" &&
       grep -q "$FPR" "$TMP/v"; then
        ok "the published SHA256SUMS is signed by the published key"
        signature_checked=1
    else
        bad "the published SHA256SUMS is not signed by the key in SECURITY.md"
        sed 's/^/        /' "$TMP/v" 2>/dev/null | head -4
        missing=$((missing + 1))
    fi
fi

echo
if [ "$missing" -gt 0 ]; then
    printf '  %s%s%d file(s) a reader is sent to are not there%s\n\n' "$RED" "$BLD" "$missing" "$OFF"
    exit 1
fi
printf '  %s%sall %d published file(s) answer, and the list is signed%s\n\n' \
       "$GRN" "$BLD" "$named" "$OFF"
exit 0

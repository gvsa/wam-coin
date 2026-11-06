#!/bin/bash
# Copyright (c) 2026 The WAM Coin developers
# Distributed under the MIT software license, see COPYING.
#
# ===========================================================================
#  A check that could not ask must never answer "no"
# ===========================================================================
#
#      bash scripts/test/test_release_check_silence.sh
#
#  WHAT HAPPENED
#
#  On the night of 2026-10-03 the channels were told twice that the published
#  release DOES NOT VERIFY:
#
#      ALARM  the release on the GitHub releases page DOES NOT VERIFY.
#      FAIL  SHA256SUMS is NOT published -- the download cannot be verified
#            by anyone
#
#  12:05, recovered 12:16. 03:29, recovered 03:39. Ten minutes each, which is
#  exactly the watcher's polling interval, with nobody touching anything. The
#  release was correct the whole time.
#
#  check_release_signed.sh read the body of wamcoin.org/downloads/<tag>/ and
#  never looked at the status code. An nginx error page has a body, so the
#  empty-body guard did not fire; the page was parsed for href= links, none
#  were found, and "no SHA256SUMS in this page" became "SHA256SUMS is not
#  published". The same hole sat one level down, where a 502 written into
#  SHA256SUMS by `curl -o` is then handed to gpg, which correctly refuses to
#  verify HTML -- reported as "the published signature does not verify".
#
#  The founder saw it before the cause: a half-finished upload does not repair
#  itself twice in one night. He was right, and he said not to patch it.
#
#  WHAT THIS HOLDS DOWN
#
#  The distinction, not the symptom. exit 1 means "I asked and the answer is
#  bad" and release_watch.py broadcasts it. exit 2 means "I could not ask" and
#  it says nothing. Every way of failing to ask must produce 2.
#
#  A false alarm here is worse than silence: it tells our own channel, in our
#  own voice, that our release is forged.
# ===========================================================================

set -uo pipefail
cd "$(dirname "$0")/../.."

GRN=$'\033[32m'; RED=$'\033[31m'; BLD=$'\033[1m'; OFF=$'\033[0m'
pass=0; fail=0

# python3 on the hosts, python on the founder's Windows machine where it is
# the only name on PATH. A test that only runs in one of the two places is a
# test that silently stops running in the other.
#
# ASKED TO RUN, NOT ASKED IF IT EXISTS. On Windows, PATH carries
# AppData/Local/Microsoft/WindowsApps/python3 -- an App Execution Alias that
# resolves, exits 0 and prints nothing at all. `command -v python3` says yes
# and every later line gets nothing, so this test reported "the fake server
# never started" three times while python was installed and working under its
# other name. Presence is not function, which is the same mistake this whole
# file exists to hold down.
PY=""
for cand in python3 python; do
    command -v "$cand" >/dev/null 2>&1 || continue
    [ "$("$cand" -c 'print(1+1)' 2>/dev/null)" = "2" ] && { PY="$cand"; break; }
done
[ -n "$PY" ] || { echo "no working python interpreter on PATH"; exit 2; }

FAKE="scripts/test/fake_downloads_server.py"
[ -f "$FAKE" ] || { echo "$FAKE is not here"; exit 2; }

run_case() {
    local name="$1" mode="$2" want="$3" port code pid tmp

    # A temp file rather than coproc: coproc's NAME_PID is not set the same way
    # across bash versions, and this test must not be the thing that fails.
    tmp="$(mktemp)"
    "$PY" "$FAKE" "$mode" > "$tmp" 2>/dev/null &
    pid=$!

    port=""
    for _ in $(seq 1 50); do
        port="$(head -n1 "$tmp" 2>/dev/null)"
        [ -n "$port" ] && break
        sleep 0.1
    done
    if [ -z "$port" ]; then
        printf '  %sFAIL%s  %s -- the fake server never started\n' "$RED" "$OFF" "$name"
        fail=$((fail+1)); kill "$pid" 2>/dev/null; rm -f "$tmp"; return
    fi

    WAM_DOWNLOADS="http://127.0.0.1:$port/downloads" \
        bash scripts/check_release_signed.sh v0.1.11 >/dev/null 2>&1
    code=$?

    kill "$pid" 2>/dev/null
    wait "$pid" 2>/dev/null
    rm -f "$tmp"

    if [ "$code" = "$want" ]; then
        printf '  %sok%s    %s (exit %s)\n' "$GRN" "$OFF" "$name" "$code"
        pass=$((pass+1))
    else
        printf '  %sFAIL%s  %s -- wanted exit %s, got %s\n' \
            "$RED" "$OFF" "$name" "$want" "$code"
        fail=$((fail+1))
    fi
}

echo
echo "${BLD}could not ask is not an answer of no${OFF}"

run_case "a 503 on the listing is silence, not an alarm"         index-503          2
run_case "a 200 that is not our listing is silence"              index-200-not-ours 2
run_case "a 502 on SHA256SUMS is silence, not 'does not verify'" download-502       2

echo
if [ "$fail" -eq 0 ]; then
    echo "  ${GRN}${BLD}every way of failing to ask exits 2${OFF}"
else
    echo "  ${RED}${BLD}$fail case(s) would alarm the channels over a hiccup${OFF}"
fi
echo
exit $(( fail > 0 ))

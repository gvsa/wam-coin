#!/usr/bin/env bash
# Copyright (c) 2026 The WAM Coin developers
# Distributed under the MIT software license, see COPYING.
#
# ===========================================================================
#  check_binary_hardening.sh -- the published binaries, read rather than trusted
# ===========================================================================
#
#      bash scripts/check_binary_hardening.sh [binary|tarball|directory ...]
#
#  WHY THIS EXISTS
#
#  On 2026-10-12 dang150296 (Urriki1502) ran readelf over the published
#  v0.1.11 Linux release and found that wamd requests an executable stack:
#
#      wam-cli  wam-tx  wam-util  wam-wallet     GNU_STACK RW
#      wamd                                      GNU_STACK RWE
#
#  One binary of five, and it is the only one that links librandomx.a.
#  RandomX ships hand-written assembly carrying no .note.GNU-stack section,
#  and a linker that meets one object without that note marks the whole
#  output RWE. It was never needed -- RandomX takes executable memory from
#  mmap with PROT_EXEC, never from the stack -- so the release gave away a
#  protection every other program in it had, for nothing.
#
#  The release had been signed, published, downloaded and mirrored. What it
#  had not been is READ. This project checks what its documents say, what its
#  seeds answer, what its claims match and what its tests prove; nothing
#  looked at the properties of the files people actually download and run.
#  So the finding came from a stranger with readelf, which is the most
#  expensive way to learn it.
#
#  WHAT THIS CHECKS, AND WHY EACH ONE
#
#  executable stack   FAILS.  A stack marked executable is the condition a
#                     stack-overflow exploit needs in order to run the bytes
#                     it just wrote. Nothing we ship needs it.
#  RELRO              warns.  Without it the relocation table stays writable
#                     and a single arbitrary write becomes control flow.
#  PIE                warns.  Without it the addresses are the same on every
#                     machine and ASLR protects nothing.
#  stack canary       warns.  Reported rather than failed because it is a
#                     compiler default we do not set per-binary.
#  FORTIFY_SOURCE     warns.  Same.
#
#  Only the first fails, because only the first is certainly wrong wherever
#  it appears. The rest are reported so that a release is never published
#  without somebody having seen them.
#
#  EXIT CODES, this project's convention
#
#      0  no shipped binary asks for an executable stack
#      1  one does
#      2  there was nothing to read, or no readelf -- so nothing was checked
# ===========================================================================

set -u

GRN=$'\033[32m'; RED=$'\033[31m'; YLW=$'\033[33m'; BLD=$'\033[1m'; OFF=$'\033[0m'

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d 2>/dev/null || echo /tmp/wam-hardening-$$)"
trap 'rm -rf "$WORK"' EXIT

PASS=0; FAIL=0; WARN=0; READ=0

command -v readelf >/dev/null 2>&1 || {
    printf '\n  %sreadelf is not installed, so nothing was read -- this is not a pass%s\n\n' "$YLW" "$OFF"
    exit 2
}

# ---------------------------------------------------------------------------
# What to read. Arguments win; otherwise the newest published Linux tarball
# this machine holds, which is the artefact strangers actually download.
# ---------------------------------------------------------------------------
TARGETS=()
if [ "$#" -gt 0 ]; then
    TARGETS=("$@")
else
    # EVERY LINUX ARTEFACT IN THE NEWEST RELEASE, NOT THE NEWEST ARTEFACT.
    #
    # The first version of this sorted by date and took `head -1`, so it read
    # one tarball and printed a verdict about the release. On its first run
    # that tarball happened to be wam-qt -- and wamd, the binary the finding
    # was about, was never read. A check that looks at one of several files
    # and reports on all of them is the same fault as a check that could not
    # look and said nothing was wrong.
    for d in /var/www/wam-downloads "$ROOT/dist" "$ROOT/release"; do
        [ -d "$d" ] || continue
        newest="$(find "$d" -name '*x86_64-linux-gnu.tar.gz' -printf '%T@ %h\n' \
                  2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)"
        [ -n "$newest" ] || continue
        while IFS= read -r t; do
            [ -n "$t" ] && TARGETS+=("$t")
        done < <(find "$newest" -maxdepth 1 -name '*x86_64-linux-gnu.tar.gz' \
                 2>/dev/null | sort)
    done
fi

if [ "${#TARGETS[@]}" -eq 0 ]; then
    printf '\n  %sno published Linux tarball and no path given, so nothing was\n'  "$YLW"
    printf '  read -- this is not a pass. Point it at one:%s\n' "$OFF"
    printf '      bash scripts/check_binary_hardening.sh path/to/release.tar.gz\n\n'
    exit 2
fi

# ---------------------------------------------------------------------------
# Expand each target into a list of ELF files.
# ---------------------------------------------------------------------------
FILES=()
for t in "${TARGETS[@]}"; do
    if [ -d "$t" ]; then
        while IFS= read -r f; do FILES+=("$f"); done \
            < <(find "$t" -type f -perm -u+x 2>/dev/null)
    elif [[ "$t" == *.tar.gz || "$t" == *.tgz ]]; then
        sub="$WORK/$(basename "$t" .tar.gz)"
        mkdir -p "$sub"
        tar xzf "$t" -C "$sub" 2>/dev/null || {
            printf '  %sFAIL%s  %s could not be unpacked\n' "$RED" "$OFF" "$t"
            FAIL=$((FAIL+1)); continue; }
        while IFS= read -r f; do FILES+=("$f"); done \
            < <(find "$sub" -type f -perm -u+x 2>/dev/null)
    elif [ -f "$t" ]; then
        FILES+=("$t")
    else
        printf '  %sFAIL%s  %s is not here\n' "$RED" "$OFF" "$t"
        FAIL=$((FAIL+1))
    fi
done

printf '\n%swhat the published binaries actually ask the kernel for%s\n\n' "$BLD" "$OFF"
printf '  reading: %s\n\n' "${TARGETS[*]}"
printf '  %-14s %-6s %-8s %-5s %-7s %s\n' binary stack relro pie canary fortify
printf '  %s\n' '----------------------------------------------------------------'

for f in "${FILES[@]}"; do
    # Only ELF files; a tarball carries READMEs and signatures too.
    head -c 4 "$f" 2>/dev/null | grep -q $'\x7fELF' || continue
    READ=$((READ+1))
    name="$(basename "$f")"

    hdr="$(readelf -lW "$f" 2>/dev/null)"
    dyn="$(readelf -dW "$f" 2>/dev/null)"
    sym="$(readelf -sW "$f" 2>/dev/null)"
    typ="$(readelf -hW "$f" 2>/dev/null | grep -i '^\s*Type:')"

    stackflags="$(printf '%s' "$hdr" | awk '/GNU_STACK/{print $7}' | head -1)"
    [ -z "$stackflags" ] && stackflags='none'

    if printf '%s' "$hdr" | grep -q 'GNU_RELRO'; then
        if printf '%s' "$dyn" | grep -q 'BIND_NOW\|FLAGS.*NOW'; then
            relro=full
        else
            relro=partial
        fi
    else
        relro=none
    fi

    if printf '%s' "$typ" | grep -qi 'DYN'; then pie=yes; else pie=no; fi
    if printf '%s' "$sym" | grep -q '__stack_chk_fail'; then canary=yes; else canary=no; fi
    if printf '%s' "$sym" | grep -q '_chk@\|_chk$'; then fortify=yes; else fortify=no; fi

    mark=''
    case "$stackflags" in
        *E*) mark="  ${RED}<- executable stack${OFF}"; FAIL=$((FAIL+1)) ;;
        none) mark="  ${YLW}<- no GNU_STACK at all${OFF}"; WARN=$((WARN+1)) ;;
        *)   PASS=$((PASS+1)) ;;
    esac
    [ "$relro" = none ] && { mark="$mark  ${YLW}no relro${OFF}"; WARN=$((WARN+1)); }
    [ "$pie" = no ]     && { mark="$mark  ${YLW}not pie${OFF}"; WARN=$((WARN+1)); }

    printf '  %-14s %-6s %-8s %-5s %-7s %-7s%b\n' \
        "$name" "$stackflags" "$relro" "$pie" "$canary" "$fortify" "$mark"
done

echo
if [ "$READ" -eq 0 ]; then
    printf '  %snot one ELF file was found in what was given, so nothing was\n' "$YLW"
    printf '  checked -- this is not a pass%s\n\n' "$OFF"
    exit 2
fi

if [ "$FAIL" -gt 0 ]; then
    printf '  %s%s%d binary/binaries ask for an executable stack%s\n' "$RED" "$BLD" "$FAIL" "$OFF"
    echo
    echo '  Nothing this project ships needs one. If it is wamd, the cause is'
    echo '  RandomX assembly with no .note.GNU-stack section, and the fix is in'
    echo '  scripts/fetch-upstream.sh -- rebuild librandomx.a after it runs,'
    echo '  because the note has to be in the objects inside a static archive.'
    echo
    exit 1
fi

printf '  %s%s%d binary/binaries read, none asks for an executable stack%s' \
    "$GRN" "$BLD" "$READ" "$OFF"
[ "$WARN" -gt 0 ] && printf ' (%d warning(s) above)' "$WARN"
echo
echo
exit 0

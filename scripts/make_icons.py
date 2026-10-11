#!/usr/bin/env python3
# Copyright (c) 2026 The WAM Coin developers
# Distributed under the MIT software license, see COPYING.
#
# ===========================================================================
#  make_icons.py -- build the Windows .ico and macOS .icns from the brand mark
# ===========================================================================
#
#      python3 scripts/make_icons.py            # write brand/generated/
#      python3 scripts/make_icons.py --check    # verify they exist and match
#
#  WHY THIS EXISTS
#
#  patch_upstream.py replaced exactly one of the GUI's icon files:
#
#      brand/generated/wam-icon-1024.png  ->  src/qt/res/icons/bitcoin.png
#
#  and src/Makefile.qt.include ships three more that it did not touch:
#
#      qt/res/icons/bitcoin.ico           the Windows taskbar and .exe icon
#      qt/res/icons/bitcoin_testnet.ico   the same, for a testnet node
#      qt/res/icons/bitcoin.icns          the macOS application bundle
#
#  So every Windows and macOS build this project has published carried
#  Bitcoin's B on the window, the taskbar, the dock and the executable itself
#  -- on a wallet holding somebody's coins, which is the one place a wrong
#  logo is not cosmetic. A user who checks that he is running what he thinks
#  he is running has been shown the wrong answer since v0.1.8.
#
#  The mark is generated rather than committed as a binary blob nobody can
#  diff, and --check is what stops the two drifting apart again.
#
#  THE TESTNET VARIANT
#
#  Upstream distinguishes testnet by hue, so that a person cannot confuse the
#  window holding real money with the one holding none. That distinction is
#  worth more than brand purity, so the testnet icon is the same mark rotated
#  in hue -- recognisably WAM, unmistakably not mainnet.
# ===========================================================================

import argparse
import struct
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Pillow is required: python3 -m pip install Pillow", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "brand" / "generated" / "wam-icon-1024.png"
OUT = ROOT / "brand" / "generated"

# What Windows actually asks for. 16 and 32 are the two that matter -- the
# taskbar and the file listing -- and they are the two a naive downscale
# ruins, so they are resampled from the full-resolution master rather than
# from an intermediate.
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]

# macOS icns entries. The PNG-based types (ic07 and up) are read by every
# macOS since 10.7; the older ic08/ic09 are included because the Finder still
# reaches for them in some views.
ICNS_TYPES = [
    (b"icp4", 16),
    (b"icp5", 32),
    (b"icp6", 64),
    (b"ic07", 128),
    (b"ic08", 256),
    (b"ic09", 512),
    (b"ic10", 1024),
    (b"ic11", 32),    # 16pt @2x
    (b"ic12", 64),    # 32pt @2x
    (b"ic13", 256),   # 128pt @2x
    (b"ic14", 512),   # 256pt @2x
]

GRN = "\033[32m"; RED = "\033[31m"; OFF = "\033[0m"


def load_master():
    # 1, NOT 2. THE TWO MEAN OPPOSITE THINGS TO WHOEVER READS THIS.
    #
    # This project's convention is 0 pass, 1 a finding, 2 could not look --
    # and these two are findings. A missing brand mark and a master of the
    # wrong size are both real: the wallet would ship with no icon of its own.
    # Pillow being absent, above, is the other case entirely, and it is the
    # only exit 2 here.
    #
    # They were all 2 until 2026-10-12, and scripts/preflight.sh judged this
    # script by "did it exit zero". So on every machine without Pillow -- which
    # is every seed -- preflight reported "the GUI icons are missing or
    # malformed, Windows and macOS would ship Bitcoin's logo", permanently,
    # about four icons that were present and correct. A launch-readiness check
    # that is always red about the same thing is one an operator learns to
    # scroll past, which is worse than not having it.
    if not SOURCE.exists():
        print(f"{RED}the brand mark is missing: {SOURCE}{OFF}", file=sys.stderr)
        sys.exit(1)
    im = Image.open(SOURCE).convert("RGBA")
    if im.size != (1024, 1024):
        print(f"{RED}expected a 1024x1024 master, found {im.size}{OFF}", file=sys.stderr)
        sys.exit(1)
    return im


def scaled(master, size):
    # LANCZOS, and always from the master. Chaining downscales through
    # intermediates is what turns a crisp rim into grey mush at 16 pixels.
    return master.resize((size, size), Image.LANCZOS)


def write_ico(master, path, hue_shift=0):
    im = hue_rotate(master, hue_shift) if hue_shift else master
    # Pillow writes a proper multi-image .ico when given sizes, and embeds
    # PNG for the 256 entry as Windows expects.
    im.save(path, format="ICO", sizes=[(s, s) for s in ICO_SIZES])


def write_icns(master, path):
    """Write an icns by hand: a header, then one PNG-typed entry per size.

    Pillow can write icns only where the platform supplies the encoder, which
    is not the case on Windows or on a Linux runner. The container is simple
    enough to emit directly and this keeps the same file being produced on
    every machine that builds a release.
    """
    entries = []
    for kind, size in ICNS_TYPES:
        from io import BytesIO
        buf = BytesIO()
        scaled(master, size).save(buf, format="PNG")
        data = buf.getvalue()
        entries.append(kind + struct.pack(">I", len(data) + 8) + data)

    body = b"".join(entries)
    path.write_bytes(b"icns" + struct.pack(">I", len(body) + 8) + body)


def hue_rotate(im, degrees):
    """Rotate hue, keeping the alpha channel untouched."""
    import colorsys
    rgb = im.convert("RGBA")
    px = rgb.load()
    out = Image.new("RGBA", rgb.size)
    op = out.load()
    shift = (degrees % 360) / 360.0
    for y in range(rgb.size[1]):
        for x in range(rgb.size[0]):
            r, g, b, a = px[x, y]
            if a == 0:
                op[x, y] = (r, g, b, a)
                continue
            h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
            nr, ng, nb = colorsys.hls_to_rgb((h + shift) % 1.0, l, s)
            op[x, y] = (round(nr * 255), round(ng * 255), round(nb * 255), a)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="verify the generated files exist and are well formed")
    args = ap.parse_args()

    ico = OUT / "wam-icon.ico"
    ico_t = OUT / "wam-icon-testnet.ico"
    icns = OUT / "wam-icon.icns"

    if args.check:
        bad = 0
        for p, want in ((ico, "ICO"), (ico_t, "ICO"), (icns, None)):
            if not p.exists():
                print(f"  {RED}FAIL{OFF}  {p.name} has not been generated")
                bad += 1
                continue
            if want == "ICO":
                try:
                    im = Image.open(p)
                    sizes = sorted({s[0] for s in im.info.get("sizes", {im.size})})
                    missing = [s for s in (16, 32, 256) if s not in sizes]
                    if missing:
                        print(f"  {RED}FAIL{OFF}  {p.name} is missing sizes {missing}")
                        bad += 1
                    else:
                        print(f"  {GRN}ok{OFF}    {p.name}  sizes {sizes}")
                except Exception as e:
                    print(f"  {RED}FAIL{OFF}  {p.name} does not open as an icon: {e}")
                    bad += 1
            else:
                head = p.read_bytes()[:4]
                if head != b"icns":
                    print(f"  {RED}FAIL{OFF}  {p.name} is not an icns container")
                    bad += 1
                else:
                    print(f"  {GRN}ok{OFF}    {p.name}  {p.stat().st_size:,} bytes")
        if bad:
            print(f"\n  {RED}run: python3 scripts/make_icons.py{OFF}\n")
            return 1
        print()
        return 0

    master = load_master()
    print(f"  master  {SOURCE.relative_to(ROOT)}  {master.size[0]}x{master.size[1]}")

    write_ico(master, ico)
    print(f"  {GRN}wrote{OFF}   {ico.relative_to(ROOT)}  sizes {ICO_SIZES}")

    write_ico(master, ico_t, hue_shift=150)
    print(f"  {GRN}wrote{OFF}   {ico_t.relative_to(ROOT)}  the same mark, hue-rotated")

    write_icns(master, icns)
    print(f"  {GRN}wrote{OFF}   {icns.relative_to(ROOT)}  "
          f"{len(ICNS_TYPES)} entries, {icns.stat().st_size:,} bytes")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

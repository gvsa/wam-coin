#!/usr/bin/env python3
# Copyright (c) 2026 The WAM Coin developers
# Distributed under the MIT software license, see COPYING.
"""
Replace Bitcoin's user-visible wording in the Qt GUI with WAM's.

    python3 scripts/rebrand_qt.py --tree build/wam-core [--check]

WHY THIS IS A SCRIPT AND NOT A PATCH SET
----------------------------------------
Everywhere else in this project, upstream is modified through anchored
transformations in patch_upstream.py: one edit, one anchor, one reason. That
works because those edits are surgical.

This is not surgical. There are roughly ninety occurrences of "Bitcoin" in the
GUI's user-visible text, spread across twelve .ui files and a dozen sources,
and every one of them says the same thing for the same reason. Ninety anchors
would be ninety chances to drift out of date with upstream, to guard a change
nobody needs to read individually.

WHAT IT DOES NOT TOUCH
----------------------
Only text a user can read is rewritten:

  * the contents of <string> elements in .ui files
  * the contents of tr("...") and QT_TRANSLATE_NOOP("...", "...")
  * the BIP21 URI scheme, which must not stay "bitcoin:" -- a WAM payment QR
    code that a Bitcoin wallet offers to pay is a way to lose money

Identifiers keep their names. BitcoinUnits, BitcoinGUI, BitcoinAddressValidator
and the rest stay exactly as upstream wrote them, because renaming a class
changes no one's experience and guarantees a painful merge at the next release.
Comments are left alone for the same reason.

The script is idempotent: running it twice changes nothing the second time,
which is what lets the build call it unconditionally.
"""

import argparse
import re
import sys
import unicodedata
from pathlib import Path

# Applied in order, inside user-visible strings only. Order matters: the URI
# forms have to be rewritten before the bare word, or "bitcoin://" becomes
# "WAM://" and stops being a scheme at all.
PHRASES = [
    ('bitcoin:BC1', 'wam:wam1'),
    ('bitcoin://', 'wam://'),
    ('bitcoin:', 'wam:'),
    ('the bitcoin network', 'the WAM network'),
    ('the Bitcoin network', 'the WAM network'),
    ('Bitcoin network', 'WAM network'),
    ('bitcoin network', 'WAM network'),
    ('Bitcoin address', 'WAM address'),
    ('bitcoin address', 'WAM address'),
    ('Bitcoin Core', 'WAM Coin'),
    ('spend bitcoins', 'spend WAM'),
    ('bitcoins', 'WAM'),
    ('Bitcoins', 'WAM'),
    # Shouting, which translators do in warnings. The Spanish wallet's
    # encrypt-wallet notice said "PERDERÁS TODOS TUS BITCOINS" -- and it
    # survived the first pass, because the table knew two capitalisations and
    # not the third. Found by reading the compiled catalogue rather than the
    # source, which is the only place it shows.
    ('BITCOINS', 'WAM'),
    ('BITCOIN', 'WAM'),
    ('Bitcoin', 'WAM'),
    # Last, and only ever inside a <string> element or a tr() call, so it can
    # never reach bitcoin.qrc, :/icons/bitcoin, or the BitcoinAmountField class.
    ('bitcoin', 'WAM'),
]

# The BIP21 scheme. Not user-visible text, but changing it is the whole point:
# a receive QR code carrying "bitcoin:wam1..." invites a Bitcoin wallet to try
# to pay it.
SCHEME_EDITS = [
    ('src/qt/guiutil.cpp',
     'uri.scheme() != QString("bitcoin")',
     'uri.scheme() != QString("wam")'),
    ('src/qt/guiutil.cpp',
     'QString ret = QString("bitcoin:%1")',
     'QString ret = QString("wam:%1")'),
    ('src/qt/paymentserver.cpp',
     'const QString BITCOIN_IPC_PREFIX("bitcoin:");',
     'const QString BITCOIN_IPC_PREFIX("wam:");'),

    # THE FIRST WINDOW A NEW USER EVER SEES, AND IT DESCRIBED ANOTHER CHAIN.
    #
    # The founder opened the first Windows build on 2026-09-26 and the welcome
    # dialog told him the program would download "the full Bitcoin block chain
    # (4 GB) starting with the earliest transactions in 2009", and warned that
    # the sync "is very demanding and may expose hardware problems". WAM's
    # chain is about five megabytes and eleven days old, and syncs in four
    # minutes.
    #
    # The chain's name is handled by the phrase table above. These two are
    # not text substitutions: the year is a number in the source, and the
    # warning is simply false here -- a sentence written for a 600 GB chain,
    # frightening people away from a download smaller than a photograph.
    ('src/qt/intro.cpp', '.arg(2009)', '.arg(2026)'),
    ('src/qt/forms/intro.ui',
     'This initial synchronisation is very demanding, and may expose hardware '
     'problems with your computer that had previously gone unnoticed. Each '
     'time you run %1, it will continue downloading where it left off.',
     'The whole chain is small and takes a few minutes on an ordinary '
     'machine. Each time you run %1, it continues where it left off.'),
]

# The content class is [^<]*, not .*?, and that is the whole safety argument.
# Qt .ui files contain self-closing <string/> elements. A dot-matches-newline
# pattern treats one of those as an opening tag and then runs to the *next*
# </string>, swallowing every element in between -- which on the first attempt
# rewrote <header>qt/bitcoinamountfield.h</header> into wamamountfield.h and a
# widget named openBitcoinConfButton into openWAMConfButton. The build stopped,
# which was lucky; a rename that still compiled would have been worse.
#
# Forbidding '<' in the content makes crossing an element boundary impossible:
# a self-closing tag simply finds no match.
UI_STRING = re.compile(r'(<string[^>]*>)([^<]*)(</string>)')
TR_CALL = re.compile(r'(\btr\(\s*")((?:[^"\\]|\\.)*)(")')
NOOP_CALL = re.compile(r'(QT_TRANSLATE_NOOP\(\s*"[^"]*"\s*,\s*")((?:[^"\\]|\\.)*)(")')

# THE TRANSLATIONS, WHICH ARE 123 FILES AND WERE SAYING BITCOIN IN ALL OF THEM.
#
# The English was rebranded from the first week. The catalogues under
# src/qt/locale were not, and every one of them ships inside the wallet. In
# Spanish -- the language of a man who has been running a node for this chain
# since August -- the first Windows build said:
#
#     Ingresa una dirección de Bitcoin (p. ej., %1)
#     Estas son tus direcciones de Bitcoin para enviar pagos
#
# So anybody whose system is not English saw another coin's name on every
# screen, and none of the checks could see it because they all read English.
#
# Both halves of each entry are rewritten, and that is deliberate. <source> is
# the LOOKUP KEY: Qt matches it against the literal in the C++, and the C++ has
# already been rebranded here. Rewriting the translation alone would leave the
# key spelling "Bitcoin", the lookup would miss, and every rebranded string
# would silently fall back to English -- a translation file that exists and
# does nothing. The same table is applied to both, so the two stay in step.
#
# <name> is untouched on purpose: those are C++ class names (BitcoinGUI,
# BitcoinAmountField), not words anybody reads.
MESSAGE = re.compile(r'[ \t]*<message[^>]*>.*?</message>\n?', re.S)
TS_SOURCE = re.compile(r'(<source>)([^<]*)(</source>)')
TS_TRANSLATION = re.compile(r'(<translation[^>]*>)([^<]*)(</translation>)')
TS_NUMERUS = re.compile(r'(<numerusform>)([^<]*)(</numerusform>)')


# THE SPELLINGS A TABLE CANNOT LIST.
#
# The table above knows Bitcoin, bitcoin, Bitcoins, bitcoins, BITCOIN and
# BITCOINS. It does not know BİTCOİN -- Azerbaijani, with the Turkish dotted
# capital I, U+0130 -- which is how bitcoin_az.ts shouted at the reader that
# forgetting his passphrase would lose him BÜTÜN BİTCOİNLƏRİNİZİ.
#
# Chasing spellings one at a time is how the capital form was missed in the
# first pass and this one in the second. So the last step is a rule rather
# than a list: the word, in any case, with either dotted or dotless i in
# either position, and a trailing s or not.
#
# It is safe for the same reason the table is: rewrite() is only ever applied
# to the CONTENTS of a <string>, a <source>, a <translation>, a
# <numerusform> or a tr() call. It never sees a class name, an #include or a
# makefile variable.
BITCOIN_ANY = re.compile(r'[Bb][İIiı][Tt][Cc][Oo][İIiı][Nn][Ss]?')


# THE NINETY-FIVE CATALOGUES THE LATIN RULE CANNOT READ.
#
# The rule above is written in Latin letters, so it sees the coin's name only
# where the name is spelled in Latin letters. On 2026-09-27 the founder opened
# the Windows wallet in Arabic, went to the send tab, and the address field
# said:
#
#     ادخل عنوان محفطة البتكوين (مثال wam1p35yvjel7srp783ztf8v6jd)
#
# The address was ours. The sentence around it was not. Measured across the
# tree: 95 of the 123 catalogues carry at least one translation of a coin-name
# string that contains no Latin "bitcoin" at all -- 954 strings in total, none
# of which any check could see, because every check was written in Latin too.
#
# These spellings were not typed from memory. They were extracted from the
# catalogues: for each language, the character runs that appear in many
# translations OF coin-name strings and in none of the others. Stems rather
# than whole words, so inflections and glued articles are caught too -- Arabic
# writes البتكوين, Russian declines, Persian splits the word with a zero-width
# non-joiner.
#
# A wrong guess in this table costs nothing: it simply never matches. Only a
# MISSING spelling would matter, and nothing here is trusted to be complete --
# see strip_foreign_names() below, which catches whatever this list forgets.
SCRIPT_NAMES = [
    # Cyrillic: Russian, Ukrainian, Belarusian, Bulgarian, Serbian, Macedonian,
    # Kazakh, Mongolian, Uzbek. Every combination of и/і and й/и/ї is in use.
    re.compile(r'[Бб][ИиІі][Тт][Кк][Оо][ЙйИиЇїІі]?[Нн]'),
    # Latin, but not spelled the way the Latin rule expects: Turkmen and Uzbek
    # write bitkoin, Esperanto coined Bitmono, and the Faroese catalogue has a
    # typo -- Bicoin -- that shipped for years because nobody greps for it.
    re.compile(r'[Bb][Ii][Tt][Kk][Oo][Ii][Nn]'),
    re.compile(r'[Bb]itmono?'),
    re.compile(r'[Bb]icoin'),
    # Arabic script: Arabic, Persian, Kurdish, Urdu. Persian and Kurdish use
    # the Farsi yeh and keheh, which are different codepoints from the Arabic
    # ones, so the two families cannot share a pattern.
    # The optional ال is Arabic's definite article, glued to the front of the
    # word as Arabic always glues it. Without it the send field would have
    # read "ادخل عنوان محفظة الWAM" -- an Arabic article stuck to a Latin word,
    # which is how a machine writes and not how a person does.
    re.compile(r'(?:ال)?ب[يی]?ت‌?\s?[كک][وۆ][يی]?[ين]ن?'),
    re.compile(r'بٹ\s?[كک]وا?[ئي]ن'),
    # Hebrew, Greek, Armenian, Georgian, Amharic, Thai.
    re.compile(r'ביטקוי?ין'),
    re.compile(r'[Μμ]πίτκοι?[νϊ]ν?'),
    re.compile(r'[Բբ][իի][թտ][քկ]ո[իի]ն'),
    re.compile(r'ბიტკოინ'),
    re.compile(r'ቢትኮይን'),
    re.compile(r'บิ[ตท]คอย'),
    # Han, kana, hangul. No word breaks, so these are written out whole.
    re.compile(r'比特[币幣]'),
    re.compile(r'ビットコイン'),
    re.compile(r'비트코인'),
    # The Indic scripts. Several spell it with a zero-width non-joiner inside
    # the word, which is why ‌ appears rather than a plain concatenation.
    re.compile(r'बिटक[ॉोौ]?[इाीॅ]?इ?न'),
    re.compile(r'বিটকয়ে?ি?ন'),
    re.compile(r'બિટકો[ઈઇ]ન'),
    re.compile(r'ਬਿਟਕ[ੁੋ]ਆ?[ਇਿ]ਨ'),
    re.compile(r'ବିଟକଇନ'),
    re.compile(r'ಬಿಟ್‌?ಕಾಯಿನ್'),
    re.compile(r'బిట్‌?కాయిన్'),
    re.compile(r'பிட்‌?க[ோா]ய[ிீ]ன்'),
    re.compile(r'ബിറ്റ്‌?കോയി[ൻന]'),
    re.compile(r'බිට්‌?කොයින්'),
]


def rewrite(text: str) -> str:
    for old, new in PHRASES:
        text = text.replace(old, new)
    text = BITCOIN_ANY.sub('WAM', text)
    for pattern in SCRIPT_NAMES:
        text = pattern.sub('WAM', text)
    return text


def process_ui(path: Path) -> int:
    original = path.read_text(encoding='utf-8')
    changed = UI_STRING.sub(lambda m: m.group(1) + rewrite(m.group(2)) + m.group(3), original)
    if changed == original:
        return 0
    path.write_text(changed, encoding='utf-8')
    return sum(1 for _ in re.finditer('WAM', changed)) - sum(1 for _ in re.finditer('WAM', original))


def process_source(path: Path) -> int:
    original = path.read_text(encoding='utf-8')
    changed = original
    for pattern in (TR_CALL, NOOP_CALL):
        changed = pattern.sub(lambda m: m.group(1) + rewrite(m.group(2)) + m.group(3), changed)
    if changed == original:
        return 0
    path.write_text(changed, encoding='utf-8')
    return 1


# READING A WORD IN A SCRIPT NOBODY HERE CAN READ.
#
# The table above is a list, and every list of spellings in this file has been
# incomplete so far: the capital form was missed in the first pass, the
# Azerbaijani dotted i in the second, every non-Latin script in the third. A
# fourth list would be a fourth guess.
#
# So the last step is not a list. Unicode names its own characters, and the
# name carries the sound: ARABIC LETTER BEH, DEVANAGARI LETTER TTA, HANGUL
# SYLLABLE KO, GEORGIAN LETTER NAR. Take the first letter of each and a word
# turns into its consonant skeleton -- and every language on earth borrowed
# this particular word by sound, so every one of them spells it b-t-k-n:
#
#     بتكوين      BEH TEH KAF WAW YEH NOON        B T K W Y N
#     비트코인      BI TEU KO IN                    B T K I N
#     ბიტკოინ     BAN IN TAR KAN O IN NAR         B I T K O I N
#     ቢትኮይን       BI TI KO YA NA                  B T K Y N
#
# Nothing is guessed and nothing is language-specific. A catalogue for a
# language nobody here has heard of, added by upstream next year, is caught by
# the same rule on the day it arrives.
#
# The blast radius is deliberately small: this runs only inside a translation
# whose ENGLISH names the coin, so a word that merely sounds like bitcoin in
# an unrelated sentence is never seen, let alone touched.
SKELETON = re.compile(r'B[_A-Z]{0,3}T[_A-Z]{0,3}[KCQ][_A-Z]{0,4}N')
_NAMED_AS = ('LETTER', 'SYLLABLE', 'SYLLABICS', 'CHARACTER')
# Qualifiers, not the sound: HEBREW LETTER FINAL NUN is a nun, and reading
# the qualifier instead would have made it an f.
_QUALIFIER = ('FINAL', 'SMALL', 'CAPITAL', 'DOTLESS', 'WITH', 'INITIAL',
              'MEDIAL', 'ISOLATED', 'TALL', 'BROAD', 'LONG', 'SHORT',
              # Sinhala names the aspiration before it names the letter:
              # SINHALA LETTER ALPAPRAANA BAYANNA is a b, and reading the
              # first word made it an l.
              'ALPAPRAANA', 'MAHAAPRAANA', 'SANYAKA', 'TWO', 'THREE')
_VOWELS = 'AEIOU'


def skeleton(text: str):
    """The consonants of how the text is pronounced, and where each came from.

    Returns the skeleton and, for every position in it, the index of the
    character in `text` that produced it -- because a match has to be given
    back as a span of the original, not of the skeleton. One character can
    contribute two consonants (HANGUL SYLLABLE IN is an n as well as a vowel),
    so the two strings are not the same length and the map is not optional.

    '_' is a vowel, a space or a mark: it fills a gap but matches nothing.
    '#' is punctuation, and stops a match from running across it.
    """
    marks, origin = [], []
    for index, ch in enumerate(text):
        piece = '#'
        # Vowel signs, viramas and the zero-width joiners that the Indic and
        # Arabic scripts write inside a word. They carry no consonant and they
        # are not a word boundary either: scoring them as punctuation is what
        # made बिटकॉइन and بیت‌کوین invisible to the first version of this.
        if ch.isspace() or unicodedata.category(ch)[0] in 'MC':
            piece = '_'
        else:
            try:
                words = unicodedata.name(ch).split()
            except ValueError:
                words = []
            for i, word in enumerate(words):
                if word not in _NAMED_AS:
                    continue
                rest = [w for w in words[i + 1:] if w not in _QUALIFIER]
                if rest:
                    # The FIRST consonant of the name and no more. ARABIC
                    # LETTER BEH is a b; reading it as "bh" put a consonant
                    # between the b and the t that no ear hears, and pushed
                    # the n out of reach of the pattern.
                    sound = [c for c in rest[0] if c not in _VOWELS]
                    piece = sound[0] if sound else '_'
                break
            else:
                piece = '_' if ch.isalpha() else '#'
        marks.append(piece)
        origin.extend([index] * len(piece))
    return ''.join(marks), origin


def rewrite_by_sound(text: str) -> str:
    """Replace whatever in `text` is pronounced bitcoin, whatever its script."""
    marks, origin = skeleton(text)
    result, cursor = [], 0
    for m in SKELETON.finditer(marks):
        start = origin[m.start()]
        end = origin[m.end() - 1] + 1
        if start < cursor:
            continue
        # No word-boundary test on purpose. Arabic glues its article to the
        # front -- البتكوين is the-bitcoin, one word -- and Turkic and Finnic
        # languages glue their cases to the back. A boundary test would let
        # exactly those through.
        result.append(text[cursor:start])
        result.append('WAM')
        cursor = end
    result.append(text[cursor:])
    return ''.join(result)


def still_named(text: str) -> bool:
    """Does this still call the coin something else -- spelled, or sounded?"""
    if any(p.search(text) for p in SCRIPT_NAMES):
        return True
    return rewrite_by_sound(text) != text


def foreign_names(text: str):
    """Translations that still call the coin something else. Any script.

    The test needs no knowledge of the language, which is the point of it.
    After rewriting, a string whose ENGLISH names the coin has "WAM" in it.
    Its translation therefore must too -- if it does not, the translator's
    word for the coin is still sitting there in a script this file cannot
    read, and it will be what the user sees.

    Empty translations are not a fault: Qt falls back to the source, and the
    source has been rebranded.
    """
    for m in MESSAGE.finditer(text):
        chunk = m.group(0)
        src = TS_SOURCE.search(chunk)
        if not src or 'WAM' not in src.group(2):
            continue
        for out in re.finditer(r'<(translation[^>]*|numerusform)>([^<]*)</', chunk):
            body = out.group(2)
            if body.strip() and 'WAM' not in body:
                yield src.group(2), body


def process_ts(path: Path) -> tuple:
    """One translation catalogue: the key and the translation, together.

    Returns (rewritten, dropped): whether the file changed, and how many
    translations had to be given up because they still named another coin.
    """
    original = path.read_text(encoding='utf-8')
    changed = original
    for pattern in (TS_SOURCE, TS_TRANSLATION, TS_NUMERUS):
        changed = pattern.sub(
            lambda m: m.group(1) + rewrite(m.group(2)) + m.group(3), changed)

    # Then the same strings again, by sound rather than by spelling -- but
    # only the ones whose English names the coin, and only if the table left
    # them without a WAM in them. See rewrite_by_sound().
    caught = [0]

    def by_sound(m):
        chunk = m.group(0)
        if not any(True for _ in foreign_names(chunk)):
            return chunk
        def one(t):
            body = t.group(2)
            if not body.strip() or 'WAM' in body:
                return t.group(0)
            fixed = rewrite_by_sound(body)
            if fixed != body:
                caught[0] += 1
            return t.group(1) + fixed + t.group(3)
        for pattern in (TS_TRANSLATION, TS_NUMERUS):
            chunk = pattern.sub(one, chunk)
        return chunk

    changed = MESSAGE.sub(by_sound, changed)

    if changed == original:
        return 0, caught[0]
    path.write_text(changed, encoding='utf-8')
    return 1, caught[0]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--tree', required=True, help='path to the Bitcoin Core checkout')
    ap.add_argument('--check', action='store_true',
                    help='report what is left without changing anything')
    args = ap.parse_args()

    # This script now prints Arabic, Hebrew and Khmer when it reports. A
    # Windows console is cp1252 by default and raises on the first one of
    # them, which would stop a build over the wording of a message about
    # wording. The output is a report; a character it cannot draw is worth a
    # question mark, not a traceback.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')

    tree = Path(args.tree)
    qt = tree / 'src' / 'qt'
    if not qt.is_dir():
        print(f'error: no src/qt under {tree}', file=sys.stderr)
        return 2

    if args.check:
        stale = []
        for path in sorted(list(qt.glob('forms/*.ui')) + list(qt.glob('*.cpp'))):
            text = path.read_text(encoding='utf-8')
            hits = [m.group(2) for m in UI_STRING.finditer(text)] if path.suffix == '.ui' \
                else [m.group(2) for m in TR_CALL.finditer(text)]
            for hit in hits:
                if re.search(r'[Bb]itcoin', hit):
                    stale.append((path.name, hit[:70]))

        # AND THE TRANSLATIONS, WHICH ARE MOST OF WHAT A PERSON READS.
        #
        # This block read forms/*.ui and *.cpp and nothing else, so it would
        # have reported "no user-visible string says Bitcoin" while 123
        # catalogues inside the same wallet said exactly that in 123
        # languages. A check that looks only where the fault was already
        # fixed is not a check.
        #
        # <name> is skipped here as it is in the rewriting pass: class names.
        for path in sorted((qt / 'locale').glob('*.ts')):
            text = path.read_text(encoding='utf-8')
            for pattern in (TS_SOURCE, TS_TRANSLATION, TS_NUMERUS):
                for m in pattern.finditer(text):
                    if re.search(r'[Bb]itcoin', m.group(2), re.IGNORECASE):
                        stale.append((path.name, m.group(2)[:70]))
                        break

            # AND THE NAME IN A SCRIPT THIS FILE CANNOT SPELL.
            #
            # Grepping for "Bitcoin" is an English test, and the wallet is not
            # in English for most of the people who open it.
            #
            # The test is not "does the translation contain WAM": plenty of
            # honest translations never name the coin at all -- Chinese says
            # 付款目的地址, the address to pay to, and is perfectly correct.
            # Failing on those would fail every build for no fault. What is
            # asked instead is whether the sentence still NAMES another coin,
            # by any of the known spellings or by sound.
            for src, body in foreign_names(text):
                if still_named(body):
                    stale.append((path.name, f'{src[:34]} -> {body[:34]}'))

        if stale:
            print(f'{len(stale)} user-visible strings still say Bitcoin:')
            for name, hit in stale[:20]:
                print(f'  {name}: {hit}')
            return 1
        print('ok    no user-visible string in the GUI says Bitcoin')
        return 0

    touched = 0

    for path in sorted(qt.glob('forms/*.ui')):
        if process_ui(path):
            touched += 1
            print(f'  ui      {path.name}')

    for path in sorted(list(qt.glob('*.cpp')) + list(qt.glob('*.h'))):
        if process_source(path):
            touched += 1
            print(f'  source  {path.name}')

    # The catalogues. 123 of them ship inside the wallet, and until 2026-09-26
    # every one of them said Bitcoin -- see the comment on TS_SOURCE.
    locales = sorted((qt / 'locale').glob('*.ts'))
    changed_locales = 0
    dropped_total = 0
    for path in locales:
        rewritten, dropped = process_ts(path)
        changed_locales += rewritten
        dropped_total += dropped
    if changed_locales:
        touched += changed_locales
        print(f'  locale  {changed_locales} of {len(locales)} translation file(s)')
    if dropped_total:
        print(f'  locale  {dropped_total} translation(s) named the coin in '
              f'their own script and were rewritten by sound')

    for rel, old, new in SCHEME_EDITS:
        path = tree / rel
        if not path.is_file():
            print(f'  warning: {rel} not found', file=sys.stderr)
            continue
        text = path.read_text(encoding='utf-8')
        if new in text:
            continue
        if old not in text:
            print(f'  warning: could not find the URI scheme in {rel}', file=sys.stderr)
            continue
        path.write_text(text.replace(old, new), encoding='utf-8')
        touched += 1
        print(f'  scheme  {rel}')

    print(f'\n{touched} files rewritten' if touched else '\nnothing to do; already rebranded')
    return 0


if __name__ == '__main__':
    sys.exit(main())

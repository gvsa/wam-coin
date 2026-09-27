#!/usr/bin/env python3
# Copyright (c) 2026 The WAM Coin developers
# Distributed under the MIT software license, see COPYING.
"""
Rename the built programs from Bitcoin's names to WAM's.

    python3 scripts/rename_binaries.py --tree build/wam-core [--check]

    bitcoind -> wamd        bitcoin-tx     -> wam-tx       bitcoin-qt -> wam-qt
    bitcoin-cli -> wam-cli  bitcoin-util   -> wam-util
                            bitcoin-wallet -> wam-wallet

  plus  bitcoin.conf -> wam.conf,  bitcoind.pid -> wamd.pid, and the data
  directory on all three platforms: ~/.wam, %LOCALAPPDATA%\WAM, and
  ~/Library/Application Support/WAM

WHY THIS IS DELICATE
--------------------
Automake derives a program's variable prefix from its name, so `bitcoind` owns
`bitcoind_SOURCES`, `bitcoind_LDADD` and the rest. Renaming the program without
renaming those leaves automake looking for sources that no target declares.

But the same token is also a *filename*:

    bitcoind_SOURCES = $(bitcoin_daemon_sources) init/bitcoind.cpp
    ^^^^^^^^ rename this                        ^^^^^^^^^^^^^^^^^^ never this

A blind search and replace renames the source file too and the build stops --
if you are lucky. The rule that separates them is position: an automake variable
prefix is at the start of a line, a filename never is. Every rewrite below is
anchored to the start of a line or to an exact, unique string.

This script is idempotent, and `--check` reports what is left without touching
anything.
"""

import argparse
import re
import sys
from pathlib import Path

PROGRAMS = [
    ('bitcoind', 'wamd', 'bitcoind', 'wamd'),
    ('bitcoin-cli', 'wam-cli', 'bitcoin_cli', 'wam_cli'),
    ('bitcoin-tx', 'wam-tx', 'bitcoin_tx', 'wam_tx'),
    ('bitcoin-util', 'wam-util', 'bitcoin_util', 'wam_util'),
    ('bitcoin-wallet', 'wam-wallet', 'bitcoin_wallet', 'wam_wallet'),
]

# (path, old, new). Exact strings, each unique in its file.
EXACT = [
    ('src/Makefile.qt.include', 'bin_PROGRAMS += qt/bitcoin-qt', 'bin_PROGRAMS += qt/wam-qt'),
    ('src/Makefile.qt.include', 'qt/bitcoin-qt$(EXEEXT)', 'qt/wam-qt$(EXEEXT)'),
    ('src/Makefile.qt.include', '$(qt_bitcoin_qt_OBJECTS)', '$(qt_wam_qt_OBJECTS)'),

    ('src/common/args.cpp',
     'const char * const BITCOIN_CONF_FILENAME = "bitcoin.conf";',
     'const char * const BITCOIN_CONF_FILENAME = "wam.conf";'),
    ('src/common/args.cpp', 'return pathRet / ".bitcoin";', 'return pathRet / ".wam";'),

    # THE OTHER TWO BRANCHES OF THE SAME FUNCTION.
    #
    # The line above was here from the beginning and the two below were not,
    # so from the first Windows build on 12 September until v0.1.10 a WAM node
    # stored its chain in a folder called Bitcoin:
    #
    #     Windows   %LOCALAPPDATA%\Bitcoin   (or %APPDATA%\Bitcoin if it existed)
    #     macOS     ~/Library/Application Support/Bitcoin
    #
    # Found by reading the published binaries rather than the source, which is
    # the only way it could have been found: the source renames Linux one line
    # up, so it reads as done.
    #
    # It destroys nothing. A node opened on another chain's datadir prints
    # "Incorrect or no genesis block found. Wrong datadir for network?" and
    # shuts down before writing, and that was measured, not assumed. What it
    # costs is every Windows and macOS user who also runs Bitcoin Core: their
    # WAM node refuses to start and the message does not say -datadir.
    #
    # The legacy Roaming check is kept in the shape upstream wrote it, so a
    # datadir that already exists under the WAM name is never moved.
    ('src/common/args.cpp',
     'fs::path legacy_path = GetSpecialFolderPath(CSIDL_APPDATA) / "Bitcoin";',
     'fs::path legacy_path = GetSpecialFolderPath(CSIDL_APPDATA) / "WAM";'),
    ('src/common/args.cpp',
     'return GetSpecialFolderPath(CSIDL_LOCAL_APPDATA) / "Bitcoin";',
     'return GetSpecialFolderPath(CSIDL_LOCAL_APPDATA) / "WAM";'),
    ('src/common/args.cpp',
     'return pathRet / "Library/Application Support/Bitcoin";',
     'return pathRet / "Library/Application Support/WAM";'),

    # The comment above the function names the three paths. Left saying
    # Bitcoin, it is the thing a reader checks against, and it would say
    # the code is still wrong.
    ('src/common/args.cpp',
     '//   old: C:\\Users\\Username\\AppData\\Roaming\\Bitcoin',
     '//   old: C:\\Users\\Username\\AppData\\Roaming\\WAM'),
    ('src/common/args.cpp',
     '//   new: C:\\Users\\Username\\AppData\\Local\\Bitcoin',
     '//   new: C:\\Users\\Username\\AppData\\Local\\WAM'),
    ('src/common/args.cpp',
     '// macOS: ~/Library/Application Support/Bitcoin',
     '// macOS: ~/Library/Application Support/WAM'),
    ('src/common/args.cpp',
     '// Unix-like: ~/.bitcoin',
     '// Unix-like: ~/.wam'),

    ('src/init.cpp',
     'static const char* BITCOIN_PID_FILENAME = "bitcoind.pid";',
     'static const char* BITCOIN_PID_FILENAME = "wamd.pid";'),

    # The functional framework writes the node's config file by name, and the
    # node now looks for wam.conf. Miss one of these and the node still starts
    # -- it simply never reads the file, so it never sees `regtest=1` and comes
    # up on MAINNET, inside a test, reaching for seed1.wamcoin.org. The failure
    # surfaces sixty seconds later as "unable to connect to bitcoind", which
    # points at everything except the cause.
    ('test/functional/test_framework/test_node.py',
     'self.bitcoinconf = self.datadir_path / "bitcoin.conf"',
     'self.bitcoinconf = self.datadir_path / "wam.conf"'),
    ('test/functional/test_framework/util.py',
     'write_config(os.path.join(datadir, "bitcoin.conf"), n=n, chain=chain, disable_autoconnect=disable_autoconnect)',
     'write_config(os.path.join(datadir, "wam.conf"), n=n, chain=chain, disable_autoconnect=disable_autoconnect)'),
    ('test/functional/test_framework/util.py',
     'with open(os.path.join(datadir, "bitcoin.conf"), \'a\', encoding=\'utf8\') as f:',
     'with open(os.path.join(datadir, "wam.conf"), \'a\', encoding=\'utf8\') as f:'),
    ('test/functional/test_framework/util.py',
     'if os.path.isfile(os.path.join(datadir, "bitcoin.conf")):',
     'if os.path.isfile(os.path.join(datadir, "wam.conf")):'),
    ('test/functional/test_framework/util.py',
     'with open(os.path.join(datadir, "bitcoin.conf"), \'r\', encoding=\'utf8\') as f:',
     'with open(os.path.join(datadir, "wam.conf"), \'r\', encoding=\'utf8\') as f:'),

    # The functional framework's binary table. The KEY is the filename on disk;
    # the first value is the attribute the tests read (self.options.bitcoind),
    # which must not move or every test that starts a node stops compiling.
    # Getting this backwards on the first attempt renamed the attribute and left
    # the filename alone -- the script's own warning is what caught it.
    ('test/functional/test_framework/test_framework.py',
     '"bitcoind": ("bitcoind", "BITCOIND"),',
     '"wamd": ("bitcoind", "BITCOIND"),'),
    ('test/functional/test_framework/test_framework.py',
     '"bitcoind": ("wamd", "BITCOIND"),',
     '"wamd": ("bitcoind", "BITCOIND"),'),
    ('test/functional/test_framework/test_framework.py',
     '"bitcoin-cli": ("bitcoincli", "BITCOINCLI"),',
     '"wam-cli": ("bitcoincli", "BITCOINCLI"),'),
    ('test/functional/test_framework/test_framework.py',
     '"bitcoin-util": ("bitcoinutil", "BITCOINUTIL"),',
     '"wam-util": ("bitcoinutil", "BITCOINUTIL"),'),
    ('test/functional/test_framework/test_framework.py',
     '"bitcoin-wallet": ("bitcoinwallet", "BITCOINWALLET"),',
     '"wam-wallet": ("bitcoinwallet", "BITCOINWALLET"),'),
]


def rename_makefile_am(text):
    """bin_PROGRAMS entries and line-start variable prefixes only."""
    for prog_old, prog_new, var_old, var_new in PROGRAMS:
        text = re.sub(rf'^(\s*bin_PROGRAMS\s*\+?=\s*){re.escape(prog_old)}$',
                      rf'\g<1>{prog_new}', text, flags=re.MULTILINE)
        text = re.sub(rf'^{re.escape(var_old)}_', f'{var_new}_', text, flags=re.MULTILINE)
    return text


def rename_qt_include(text):
    return re.sub(r'^qt_bitcoin_qt_', 'qt_wam_qt_', text, flags=re.MULTILINE)


# Files whose C++ string literals are read by a person: usage text, error
# messages, RPC help. Found by asking which files contain a quoted literal
# mentioning bitcoind or bitcoin-cli, not by guessing.
MESSAGE_FILES = [
    'src/bitcoin-cli.cpp',
    'src/bitcoind.cpp',
    'src/txdb.cpp',
    'src/rpc/blockchain.cpp',
    'src/rpc/external_signer.cpp',
    'src/rpc/node.cpp',
    'src/rpc/util.cpp',
    'src/wallet/wallet.cpp',
    'src/wallet/rpc/backup.cpp',
    'src/wallet/rpc/wallet.cpp',
    'src/wallet/external_signer_scriptpubkeyman.cpp',

    # THE RPC HELP, WHICH IS READ BY PEOPLE AND NOT ONLY BY PROGRAMS.
    #
    # Added 2026-09-26, after the first graphical wallet was built and its
    # debug console -- Help, Debug window, Console -- answered `help
    # validateaddress` with "Return information about the given bitcoin
    # address". Every one of these strings is a description or an error
    # message: argument NAMES are untouched, because a renamed argument
    # breaks every client that ever sent one.
    'src/common/signmessage.cpp',
    'src/rpc/mining.cpp',
    'src/rpc/output_script.cpp',
    'src/rpc/rawtransaction.cpp',
    'src/rpc/rawtransaction_util.cpp',
    'src/rpc/signmessage.cpp',
    'src/wallet/rpc/addresses.cpp',
    'src/wallet/rpc/coins.cpp',
    'src/wallet/rpc/encrypt.cpp',
    'src/wallet/rpc/signmessage.cpp',
    'src/wallet/rpc/spend.cpp',
    'src/wallet/rpc/transactions.cpp',
]

# A quoted C++ string literal, escapes included.
_LITERAL = re.compile(r'"(?:[^"\\\n]|\\.)*"')

# Inside a literal, these are still code or paths and must not be touched:
# an include or a source name, and the automake variable prefixes.
_LEAVE_ALONE = re.compile(r'\.(h|cpp|py|am)\b|_SOURCES|_LDADD|_CPPFLAGS')


def rename_message_strings(text):
    """Rename the binaries where a person reads them, and nowhere else.

    A user who ran the release on 5 September and mistyped a flag was told

        Make sure the bitcoind server is running ...
        Use "bitcoin-cli -help" for more info.

    by a program called wam-cli, about a daemon called wamd. The first thing
    a stranger sees when something goes wrong is the name of a different coin.

    PROGRAMS above renames build targets and automake variables; EXACT covers
    a handful of individual lines. Neither touches message text, because a
    blind search and replace over these files renames #include "bitcoind.h"
    and the build stops -- the reason the header of this script gives for not
    doing it that way.

    So this rewrites only inside double-quoted literals, and skips any literal
    that is a filename or a makefile variable.
    """
    def fix(m):
        s = m.group(0)
        if _LEAVE_ALONE.search(s):
            return s
        s = s.replace('bitcoin-cli', 'wam-cli')
        s = re.sub(r'\bbitcoind\b', 'wamd', s)

        # THE COIN'S NAME IN PROSE, NOT ONLY THE PROGRAM'S.
        #
        # "The Bitcoin address", "the bitcoin address to receive", "you will
        # receive less bitcoins than you enter", "the newly generated bitcoin
        # to". Every one of those is what a person reads in the wallet's debug
        # console or in `wam-cli help`, and every one of them names another
        # coin while describing this one's money.
        #
        # Still only inside quoted literals, and still behind _LEAVE_ALONE, so
        # an #include or a makefile variable cannot be caught by it. The word
        # boundaries matter: `bitcoins` must not turn `bitcoinsomething` into
        # anything, and a bare `bitcoin` is only rewritten where it is plainly
        # the money -- before " to " or " address".
        s = re.sub(r'\b[Bb]itcoin address\b', 'WAM address', s)
        s = re.sub(r'\b[Bb]itcoins\b', 'WAM', s)
        s = re.sub(r'\bbitcoin\b(?= to\b)', 'WAM', s)
        return s

    return _LITERAL.sub(fix, text)


def apply_message_strings(tree, report):
    touched = 0
    for rel in MESSAGE_FILES:
        path = tree / rel
        if not path.is_file():
            report(f'  skip    {rel} (not present)')
            continue
        text = path.read_text(encoding='utf-8')
        new = rename_message_strings(text)
        if new != text:
            path.write_text(new, encoding='utf-8')
            n = len(_LITERAL.findall(text)) and sum(
                1 for a, b in zip(_LITERAL.findall(text), _LITERAL.findall(new)) if a != b)
            report(f'  strings {rel}  ({n} literal(s))')
            touched += 1
    return touched


# ---------------------------------------------------------------------------
# THE WINDOWS VERSION RESOURCE -- what the operating system says about us.
#
# Found on 2026-09-27, by the founder double-clicking the first Windows wallet
# this project ever built. Windows Firewall asked him whether to allow it and
# named it:
#
#     WAM Coin (GUI node for Bitcoin)
#     Publisher: Bitcoin
#
# That is the single most trust-sensitive sentence a Windows user ever reads
# about a program, and it told him the publisher was another project. The same
# strings are in the file's Properties dialog, and every Windows binary we
# ship carries one: the node, the CLI, the tx and util tools, the wallet tool
# and the GUI.
#
# None of it was reachable before. These .rc files compile only on Windows, so
# no Linux build, no test and no check here had ever produced them -- and the
# GUI's resource was never built at all until this week.
#
# PACKAGE_NAME is already ours; what is left is the prose around it.
RC_EDITS = [
    ('VALUE "CompanyName",        "Bitcoin"',
     'VALUE "CompanyName",        "WAM Coin"'),
    ('PACKAGE_NAME " (GUI node for Bitcoin)"',
     'PACKAGE_NAME " (graphical wallet and node)"'),
    ('"bitcoind (Bitcoin node with a JSON-RPC server)"',
     '"wamd (WAM node with a JSON-RPC server)"'),
    ('"bitcoin-cli (JSON-RPC client for " PACKAGE_NAME ")"',
     '"wam-cli (JSON-RPC client for " PACKAGE_NAME ")"'),
    ('"bitcoin-tx (CLI Bitcoin transaction editor utility)"',
     '"wam-tx (CLI WAM transaction editor utility)"'),
    ('"bitcoin-util (CLI Bitcoin utility)"',
     '"wam-util (CLI WAM utility)"'),
    ('"bitcoin-wallet (CLI tool for " PACKAGE_NAME " wallets)"',
     '"wam-wallet (CLI tool for " PACKAGE_NAME " wallets)"'),
]


def apply_rc(tree, report):
    """Every .rc under src/, including the GUI's own under src/qt/res."""
    touched = 0
    paths = sorted(list((tree / 'src').glob('*.rc')) +
                   list((tree / 'src' / 'qt' / 'res').glob('*.rc')))
    for path in paths:
        text = path.read_text(encoding='utf-8')
        new = text
        for old, rep in RC_EDITS:
            new = new.replace(old, rep)
        if new != text:
            path.write_text(new, encoding='utf-8')
            report(f'  rc      {path.name}')
            touched += 1
    if not paths:
        report('  skip    no .rc files in this tree')
    return touched


def apply_exact(tree, report):
    touched = 0
    for rel, old, new in EXACT:
        path = tree / rel
        if not path.is_file():
            report(f'  skip    {rel} (not present)')
            continue
        text = path.read_text(encoding='utf-8')
        if new in text:
            continue
        if old not in text:
            report(f'  WARN    {rel}: could not find {old[:50]!r}')
            continue
        path.write_text(text.replace(old, new), encoding='utf-8')
        report(f'  exact   {rel}')
        touched += 1
    return touched


def check(tree, report):
    """Report anything that would still build under Bitcoin's name."""
    problems = []

    am = (tree / 'src' / 'Makefile.am').read_text(encoding='utf-8')
    for prog_old, _new, var_old, _vn in PROGRAMS:
        if re.search(rf'^\s*bin_PROGRAMS\s*\+?=\s*{re.escape(prog_old)}$', am, re.MULTILINE):
            problems.append(f'Makefile.am still builds a program named {prog_old}')
        if re.search(rf'^{re.escape(var_old)}_', am, re.MULTILINE):
            problems.append(f'Makefile.am still declares {var_old}_* variables')

    qt = (tree / 'src' / 'Makefile.qt.include').read_text(encoding='utf-8')
    if 'bin_PROGRAMS += qt/bitcoin-qt' in qt:
        problems.append('Makefile.qt.include still builds qt/bitcoin-qt')

    for rel, old, _new in EXACT:
        path = tree / rel
        if path.is_file() and old in path.read_text(encoding='utf-8'):
            problems.append(f'{rel} still contains {old[:48]}')

    # The one that fails silently: a node that cannot find its config file
    # starts anyway, on the wrong chain.
    for rel in ('test/functional/test_framework/util.py',
                'test/functional/test_framework/test_node.py'):
        path = tree / rel
        if path.is_file() and '"bitcoin.conf"' in path.read_text(encoding='utf-8'):
            problems.append(f'{rel} still writes bitcoin.conf; the node reads wam.conf '
                            'and would start on mainnet inside a test')

    if problems:
        report(f'{len(problems)} things still carry Bitcoin\'s name:')
        for p in problems:
            report(f'  {p}')
        return 1

    report('ok    every built program, the config file and the datadir say WAM')
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--tree', required=True)
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()

    tree = Path(args.tree)
    if not (tree / 'src' / 'Makefile.am').is_file():
        print(f'error: no src/Makefile.am under {tree}', file=sys.stderr)
        return 2

    report = print

    if args.check:
        return check(tree, report)

    touched = 0

    am_path = tree / 'src' / 'Makefile.am'
    before = am_path.read_text(encoding='utf-8')
    after = rename_makefile_am(before)
    if after != before:
        # A source filename must never move. If one did, the count of
        # "bitcoind.cpp" style tokens would drop, so refuse and say so.
        for filename in ('bitcoind.cpp', 'bitcoin-cli.cpp', 'bitcoin-tx.cpp',
                         'bitcoin-util.cpp', 'bitcoin-wallet.cpp', 'bitcoind-res.rc'):
            if before.count(filename) != after.count(filename):
                print(f'error: the rewrite would have moved the source file {filename}. '
                      'Refusing to write.', file=sys.stderr)
                return 1
        am_path.write_text(after, encoding='utf-8')
        report('  am      src/Makefile.am')
        touched += 1

    qt_path = tree / 'src' / 'Makefile.qt.include'
    before = qt_path.read_text(encoding='utf-8')
    after = rename_qt_include(before)
    if after != before:
        if before.count('init/bitcoin-qt.cpp') != after.count('init/bitcoin-qt.cpp'):
            print('error: the rewrite would have moved init/bitcoin-qt.cpp. Refusing.',
                  file=sys.stderr)
            return 1
        qt_path.write_text(after, encoding='utf-8')
        report('  qt      src/Makefile.qt.include')
        touched += 1

    touched += apply_exact(tree, report)
    touched += apply_message_strings(tree, report)
    touched += apply_rc(tree, report)

    report(f'\n{touched} files rewritten' if touched else '\nnothing to do; already renamed')
    return 0


if __name__ == '__main__':
    sys.exit(main())

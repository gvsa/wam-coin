#!/usr/bin/env python3
# Copyright (c) 2026 The WAM Coin developers
# Distributed under the MIT software license, see COPYING.
"""
===============================================================================
 check_address_agreement.py -- the pool, the miner and the node, on one list
===============================================================================

     python3 scripts/check_address_agreement.py [--node HOST] [--count N]

 WHY THIS EXISTS

 "Which script pays this address" is answered three times in this project, in
 three languages:

     pool/lib/util.js      addressToScript      JavaScript
     miner/src/address.h   AddressToScript      C++
     wam-core              DecodeDestination    C++, and it is consensus

 Nothing compared them. On 2026-09-19 the miner was fixed to decode base58
 before guessing whether an address looked like somebody else's bech32. The
 pool was not, and went on refusing about one valid base58 address in twenty
 -- including this project's own treasury address -- until a reader outside
 the project found it on 2026-10-15, twenty-six days later.

 The same silence hid a second disagreement: the miner gave regtest the
 version bytes 100 and 196, Bitcoin's numbers, where kernel/chainparams.cpp
 gives it 65 and 128. Every legacy regtest address the node handed out was
 refused by the miner, and no gate noticed, because the regtest gates mine to
 a wamrt1... address that never reaches a version byte.

 Both are the same fault: one decision, three copies, no comparison. Fixing
 the copies does not fix that. This does.

 WHAT THIS DOES

 Generates addresses for every network and both base58 types, adds the fixed
 vectors that have bitten us, and asks each implementation what script pays
 them. A disagreement is a finding, and so is one implementation refusing an
 address another accepts.

 The miner is C++, so a small driver is compiled against miner/src/address.h
 in a temporary directory. No file is added to the miner for this.

 The node is asked only when --node names one, and only about the network it
 is actually on: it is the authority the other two are copies of, so when it
 is reachable its answer decides which of them is wrong.

 EXIT CODES, this project's convention

     0  every implementation present agreed on every address
     1  they did not agree
     2  fewer than two implementations could be asked, so nothing was
        compared. A check that could not ask has not learned that the
        answer is yes.
===============================================================================
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

RED = "\033[31m"; GRN = "\033[32m"; YEL = "\033[33m"; BLD = "\033[1m"; OFF = "\033[0m"

B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

# From kernel/chainparams.cpp. These are the authority when no node is
# reachable, and they are checked against a reachable one.
#
# The key is "bech32" and not "hrp" because that is what pool/lib/util.js
# reads. Spelled "hrp", the pool silently skipped its own bech32 branch and
# called every wam1... address a segwit address for 'wam' -- which this check
# then reported as the miner and the pool disagreeing. The check was wrong,
# not the pool, and the shape of this dict is part of the check.
NETWORKS = {
    "mainnet": {"pubkey": 73, "script": 135, "bech32": "wam"},
    "testnet": {"pubkey": 65, "script": 128, "bech32": "twam"},
    "regtest": {"pubkey": 65, "script": 128, "bech32": "wamrt"},
}

# Addresses that have cost this project something, kept by name so that a
# regression is reported as the thing it is rather than as a random failure.
FIXED = [
    ("mainnet", "WdMMqW1DcgWZ6HtyJuEMdce6QkKg4raGmE",
     "the treasury, refused by the pool's pattern guess until 2026-10-15"),
    ("mainnet", "WaM1eGQr6YgwTPrX3G6n2UZLVwWa8W9Qgb",
     "base58 that lower-cases to wam1..., refused by prefix until 2026-10-15"),
    ("mainnet", "wam1qrulaxxlqf65madsmhqrevf467r6qmgdrxhf9yw",
     "a real miner's bech32 address"),
    ("mainnet", "WWWEvpC98mfzjRMZHtaRaucMjopqH2viQz", "the founder's address"),
    ("regtest", "TCpSQcu85CJB5jMxqTU96BMawXYJQfNpFB",
     "regtest P2PKH, refused by the miner's wrong version byte until 2026-10-15"),
    ("regtest", "tZ7SSTgGoZVNc39RNtTDe5W9bJmjCPTU6n",
     "regtest P2SH, same"),
]


def b58encode(raw: bytes) -> str:
    n = int.from_bytes(raw, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = B58[r] + out
    for byte in raw:
        if byte:
            break
        out = "1" + out
    return out


def make_address(version: int, seed: int) -> str:
    h = hashlib.sha256(b"wam-address-agreement-%d" % seed).digest()[:20]
    payload = bytes([version]) + h
    checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    return b58encode(payload + checksum)


# --- the three implementations ----------------------------------------------

POOL_DRIVER = r"""
'use strict';
const { addressToScript } = require(process.argv[2]);
const out = [];
for (const line of JSON.parse(require('fs').readFileSync(process.argv[3], 'utf8'))) {
    const net = line.net, address = line.address;
    try {
        out.push({ net, address, script: addressToScript(address, net).toString('hex') });
    } catch (e) {
        out.push({ net, address, error: e.message });
    }
}
process.stdout.write(JSON.stringify(out));
"""

MINER_DRIVER = r"""
#include <cstdio>
#include <fstream>
#include <sstream>
#include <string>
#include "address.h"
using namespace wam;
int main(int argc, char** argv) {
    std::ifstream in(argv[1]);
    std::string line;
    while (std::getline(in, line)) {
        if (line.empty()) continue;
        const size_t tab = line.find('\t');
        const std::string net = line.substr(0, tab);
        const std::string address = line.substr(tab + 1);
        try {
            const Bytes s = AddressToScript(address, NetParamsFor(net));
            std::string hex;
            static const char* d = "0123456789abcdef";
            for (uint8_t c : s) { hex += d[c >> 4]; hex += d[c & 15]; }
            std::printf("ok\t%s\n", hex.c_str());
        } catch (const std::exception& e) {
            std::printf("err\t%s\n", e.what());
        }
    }
    (void)argc; return 0;
}
"""


def ask_pool(cases, work):
    node_bin = shutil.which("node")
    if not node_bin:
        return None, "no node binary"
    drv = work / "pool_driver.js"
    drv.write_text(POOL_DRIVER, encoding="utf-8")
    inp = work / "cases.json"
    inp.write_text(json.dumps(
        [{"net": NETWORKS[n], "address": a} for n, a, _ in cases]), encoding="utf-8")
    util = (ROOT / "pool" / "lib" / "util.js").as_posix()
    try:
        r = subprocess.run([node_bin, str(drv), util, str(inp)],
                           capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as e:
        return None, str(e)
    if r.returncode != 0:
        return None, (r.stderr or "").strip()[:200]
    rows = json.loads(r.stdout)
    return [row.get("script") or ("ERR: " + row["error"]) for row in rows], None


def ask_miner(cases, work):
    cxx = next((c for c in ("g++", "clang++", "c++") if shutil.which(c)), None)
    if not cxx:
        return None, "no C++ compiler"
    src = work / "miner_driver.cpp"
    src.write_text(MINER_DRIVER, encoding="utf-8")
    inc = ROOT / "miner" / "src"
    exe = work / ("miner_driver.exe" if os.name == "nt" else "miner_driver")
    build = subprocess.run([cxx, "-std=c++17", "-O1", "-I", str(inc),
                            "-o", str(exe), str(src)],
                           capture_output=True, text=True, timeout=600)
    if build.returncode != 0:
        return None, (build.stderr or "").strip().splitlines()[-1][:200]
    inp = work / "cases.tsv"
    inp.write_text("".join("%s\t%s\n" % (n, a) for n, a, _ in cases),
                   encoding="utf-8")
    r = subprocess.run([str(exe), str(inp)], capture_output=True, text=True,
                       timeout=300)
    if r.returncode != 0:
        return None, (r.stderr or "").strip()[:200]
    out = []
    for line in r.stdout.splitlines():
        kind, _, rest = line.partition("\t")
        out.append(rest if kind == "ok" else "ERR: " + rest)
    if len(out) != len(cases):
        return None, "driver answered %d of %d" % (len(out), len(cases))
    return out, None


CLI = ("wam-cli -chain=main -conf=/root/.wam-mainnet/wam.conf "
       "-datadir=/root/.wam-mainnet")


def ask_node(cases, host, work):
    """The node answers only for its own chain, so other networks are skipped.

    `--node local` runs wam-cli here rather than over ssh, which is what the
    check needs when it is already running on the machine holding the node.
    """
    local = host in ("local", "localhost", "-")
    base = [] if local else ["ssh", "-o", "BatchMode=yes",
                             "-o", "ConnectTimeout=15", host]

    def run(command, stdin=None):
        if local:
            return subprocess.run(["bash", "-c", command] if stdin is None
                                  else ["bash", "-s"],
                                  input=stdin, capture_output=True, text=True,
                                  timeout=600)
        return subprocess.run(base + [command if stdin is None else "bash -s"],
                              input=stdin, capture_output=True, text=True,
                              timeout=600)

    probe = run("%s getblockchaininfo" % CLI)
    if probe.returncode != 0:
        return None, None, (probe.stderr or "").strip().splitlines()[-1:][0][:160] \
            if probe.stderr.strip() else "no answer"
    chain = json.loads(probe.stdout).get("chain")
    net = {"main": "mainnet", "test": "testnet", "regtest": "regtest"}.get(chain)
    if net is None:
        return None, None, "unknown chain %r" % chain

    wanted = [(i, a) for i, (n, a, _) in enumerate(cases) if n == net]
    if not wanted:
        return None, net, "no %s address in the list" % net

    script = "\n".join("%s validateaddress %s" % (CLI, a) for _, a in wanted)
    r = run(None, stdin=script)
    answers = {}
    decoder = json.JSONDecoder()
    text, pos = r.stdout, 0
    for i, _ in wanted:
        while pos < len(text) and text[pos] in " \r\n\t":
            pos += 1
        if pos >= len(text):
            break
        obj, pos = decoder.raw_decode(text, pos)
        answers[i] = (obj.get("scriptPubKey") if obj.get("isvalid")
                      else "ERR: the node calls it invalid")
    return answers, net, None


# --- reporting ---------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--node", help="ssh host running a mainnet wamd")
    ap.add_argument("--count", type=int, default=400,
                    help="generated addresses per network and type (default 400)")
    a = ap.parse_args()

    print(f"\n{BLD}the pool, the miner and the node agree on every address{OFF}\n")

    cases = list(FIXED)
    for net, v in NETWORKS.items():
        for version in (v["pubkey"], v["script"]):
            for i in range(a.count):
                cases.append((net, make_address(version, hash((net, version, i)) & 0xffffff),
                              "generated"))

    with tempfile.TemporaryDirectory(prefix="wam-addr-") as tmp:
        work = pathlib.Path(tmp)
        pool, pool_why = ask_pool(cases, work)
        miner, miner_why = ask_miner(cases, work)
        node, node_net, node_why = (None, None, "not asked")
        if a.node:
            node, node_net, node_why = ask_node(cases, a.node, work)

    for name, got, why in (("pool  ", pool, pool_why), ("miner ", miner, miner_why)):
        if got is None:
            print(f"  {YEL}--{OFF}    {name} could not be asked: {why}")
        else:
            print(f"  {GRN}ok{OFF}    {name} answered for all {len(cases)} addresses")
    if a.node:
        if node is None:
            print(f"  {YEL}--{OFF}    node   could not be asked: {node_why}")
        else:
            print(f"  {GRN}ok{OFF}    node   answered for {len(node)} {node_net} "
                  f"address(es)")

    present = [x for x in (pool, miner) if x is not None] + ([] if node is None else [1])
    if len(present) < 2:
        print(f"\n  {YEL}fewer than two implementations could be asked, so nothing "
              f"was compared.{OFF}")
        print(f"  {YEL}A check that could not ask has not learned that the answer "
              f"is yes.{OFF}\n")
        return 2

    findings = []
    for i, (net, address, note) in enumerate(cases):
        answers = {}
        if pool is not None:
            answers["pool"] = pool[i]
        if miner is not None:
            answers["miner"] = miner[i]
        if node is not None and i in node:
            answers["node"] = node[i]
        # The question is which script pays this address, so a refusal is one
        # answer however it is worded. Three implementations in two languages
        # will never phrase a refusal identically, and a refusal for a clumsy
        # reason is an editorial problem, not a disagreement about money.
        decisions = {("refused" if v.startswith("ERR: ") else v)
                     for v in answers.values()}
        if len(decisions) > 1:
            findings.append((net, address, note, answers))

    print()
    if findings:
        for net, address, note, answers in findings[:10]:
            print(f"  {RED}FAIL{OFF}  {net} {address}")
            print(f"          {note}")
            for who, what in sorted(answers.items()):
                print(f"          {who:<6} {what[:96]}")
        if len(findings) > 10:
            print(f"          ... and {len(findings) - 10} more")
        print()
        print(f"  {RED}{BLD}{len(findings)} address(es) are answered differently "
              f"by different parts of this project{OFF}")
        print("  The node is consensus. Where it answered, it is right and the")
        print("  other two are copies that have drifted. Where it did not, the")
        print("  disagreement is still a bug: one of them is paying a script")
        print("  the other would not.\n")
        return 1

    asked = ", ".join(k for k, v in (("pool", pool), ("miner", miner),
                                     ("node", node)) if v is not None)
    print(f"  {GRN}{BLD}{asked} agree on all {len(cases)} addresses{OFF}\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(2)

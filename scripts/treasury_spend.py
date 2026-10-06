#!/usr/bin/env python3
# Copyright (c) 2026 The WAM Coin developers
# Distributed under the MIT software license, see COPYING.
"""
Spend from the treasury without the key ever touching a networked machine.

    ONLINE   python3 scripts/treasury_spend.py plan --to <addr> --amount 500
    OFFLINE  python3 scripts/treasury_spend.py sign --in plan.json
    ONLINE   python3 scripts/treasury_spend.py broadcast --in signed.json

WHY THIS EXISTS

The treasury is one key until the 2-of-3 arrangement exists, and it holds
every coin WAM-1 has ever paid it -- 12,322 WAM at height 4,929, rising by
1,800 a day. Importing that key into a wallet on a machine with a network
interface, to move 500 WAM, risks the whole balance to save an afternoon.

So the transaction is built where the chain is, signed where the key is, and
broadcast back where the chain is. Three files cross between them and none of
them contains a key.

WHAT IT REFUSES TO DO

It does not read, store, log or transmit the private key. `sign` prompts for
it, holds it in memory for one call, and never writes it anywhere -- not to
the plan, not to the signed file, not to a log.

It does not trust the file it is given. `broadcast` decodes the signed
transaction and compares its outputs against the plan before sending: the
destination, the amount, the change address and the fee. A file altered
between the two machines is refused with the difference named, not sent.

It does not guess the fee. The plan states it, `broadcast` recomputes it from
the decoded transaction, and a disagreement stops everything.

THE SHAPE OF A TREASURY SPEND

WAM-1 pays the treasury once per block: 2.5 WAM, one output, every block
since height 1 and never spent. So 500 WAM is not one input, it is 201 of
them, and the transaction is about 30 KB. That is well inside the 100 KB
standard limit but it is not something a person can assemble by hand, which
is the other reason this file exists.

Coinbase outputs need 100 confirmations before they can move. Outputs younger
than that are excluded, and the reason is printed rather than assumed.
"""

import argparse
import base64
import decimal
import getpass
import hashlib
import json
import os
import subprocess
import sys
import urllib.request

TREASURY = "WdMMqW1DcgWZ6HtyJuEMdce6QkKg4raGmE"
COINBASE_MATURITY = 100
# 0.0002 WAM/kvB is what the node estimates and 20,000 sat/kvB is the wallet's
# own fallback; a 30 KB transaction pays well under a hundredth of a coin
# either way. Stated here rather than estimated so the two machines agree.
FEERATE_PER_KVB = 0.0002


def die(msg):
    sys.stderr.write("error: %s\n" % msg)
    raise SystemExit(1)


class Rpc:
    """Talks to a node over HTTP, reading credentials from its wam.conf."""

    def __init__(self, conf, host="127.0.0.1", port=9554):
        creds = {}
        try:
            for line in open(conf, encoding="utf-8"):
                if "=" in line and not line.lstrip().startswith("#"):
                    k, v = line.split("=", 1)
                    creds[k.strip()] = v.strip()
        except OSError as e:
            die("cannot read %s: %s" % (conf, e))
        if "rpcuser" not in creds or "rpcpassword" not in creds:
            die("%s has no rpcuser/rpcpassword" % conf)
        self.auth = base64.b64encode(
            ("%s:%s" % (creds["rpcuser"], creds["rpcpassword"])).encode()).decode()
        self.url = "http://%s:%d/" % (host, port)

    def call(self, method, params=None):
        body = json.dumps({"jsonrpc": "1.0", "id": "treasury",
                           "method": method, "params": params or []})
        req = urllib.request.Request(
            self.url, data=body.encode(),
            headers={"Authorization": "Basic " + self.auth,
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                out = json.load(r)
        except Exception as e:
            die("%s: %s" % (method, e))
        if out.get("error"):
            die("%s: %s" % (method, out["error"].get("message", out["error"])))
        return out["result"]


def wam(x):
    """Coins, printed the way the node prints them."""
    return "%.8f" % x


# ---------------------------------------------------------------------------
#  Reading a transaction, in whole numbers
# ---------------------------------------------------------------------------
#
#  Everything below compares a decoded transaction against a plan, and a
#  comparison is only worth making if it is exact. Coins are decimal and
#  binary floating point is not, so every value crossing one of these checks
#  is converted to atoms -- whole numbers -- through Decimal, and compared as
#  integers. 0.1 + 0.2 is a famous example; the one that matters here is that
#  two values printed identically can differ.
#
#  The construction arithmetic in cmd_plan is still float, and is left that
#  way deliberately for now: rewriting what COMPUTES the amounts at the same
#  time as adding the checks that verify them would mean neither is watching
#  the other. These checks are exact, so float drift in the plan is caught
#  here rather than carried through.

COIN = decimal.Decimal(100000000)


def _atoms(value, what="amount"):
    """A coin value as whole atoms, or death. Never silently rounded."""
    try:
        d = decimal.Decimal(str(value)) * COIN
    except (decimal.InvalidOperation, ValueError, TypeError):
        die("%s is not a number: %r" % (what, value))
    if not d.is_finite() or d != d.to_integral_value() or d < 0:
        die("%s must be positive with at most 8 decimals: %r" % (what, value))
    return int(d)


def _outpoints(vins, where):
    """The exact inputs, in order, refusing anything ambiguous."""
    points = []
    for v in vins:
        if not isinstance(v, dict) or "txid" not in v or "vout" not in v:
            die("an input in %s cannot be read" % where)
        if "coinbase" in v:
            die("%s spends a coinbase directly, which this never does" % where)
        points.append((str(v["txid"]), int(v["vout"])))
    if len(set(points)) != len(points):
        die("%s spends the same output twice" % where)
    return points


def _outputs(tx, where):
    """(address, atoms) for every output, refusing one we cannot name.

    An output whose scriptPubKey carries no single address used to be skipped
    -- `if addr:` -- so a payment to a raw script was invisible to the check
    that looks for unexpected recipients. Invisible is the one thing an output
    in a treasury transaction may not be.
    """
    out = []
    for o in tx.get("vout", []):
        spk = o.get("scriptPubKey")
        if not isinstance(spk, dict):
            die("an output in %s cannot be read" % where)
        addr = spk.get("address")
        if not isinstance(addr, str) or not addr:
            die("%s has an output that pays no single address -- refusing to "
                "judge a transaction whose recipients cannot all be named" % where)
        out.append((addr, _atoms(o.get("value"), "an output value")))
    return out


def _verify_against_plan(plan, tx, where):
    """Does this transaction do exactly what the plan says, to the atom?

    Inputs in the same order, outputs exactly destination plus change, and the
    fee equal to inputs minus outputs. Anything else dies.
    """
    want_in = _outpoints(plan.get("inputSet", []), "the plan")
    if not want_in:
        die("the plan does not name the outputs it spends -- it was written "
            "by an older version of this script. Re-run `plan`.")
    if _outpoints(tx.get("vin", []), where) != want_in:
        die("%s does not spend the inputs the plan approved, or spends them "
            "in a different order" % where)

    amount = _atoms(plan["amount"], "the amount")
    change = _atoms(plan["change"], "the change")
    fee = _atoms(plan["fee"], "the fee")
    total_in = _atoms(plan["inputTotal"], "the input total")

    want_out = [(plan["to"], amount)]
    if change:
        want_out.append((TREASURY, change))
    got_out = _outputs(tx, where)
    if sorted(got_out) != sorted(want_out):
        die("%s does not pay exactly what the plan says. It pays: %s" %
            (where, ", ".join("%s to %s" % (wam(a / 1e8), ad) for ad, a in got_out)))

    if total_in - sum(a for _, a in got_out) != fee:
        die("%s does not conserve value: inputs minus outputs is not the "
            "fee the plan states" % where)


# ---------------------------------------------------------------------------
# plan -- runs where the chain is
# ---------------------------------------------------------------------------

def cmd_plan(args):
    rpc = Rpc(args.conf, port=args.port)
    tip = rpc.call("getblockcount")

    print("scanning the treasury's unspent outputs (this takes a minute)...")
    scan = rpc.call("scantxoutset", ["start", ["addr(%s)" % TREASURY]])
    if not scan.get("success"):
        die("the scan did not complete")

    utxos = scan.get("unspents", [])
    # Spendable at depth 101, not 100. Consensus rejects a coinbase spent
    # earlier than (COINBASE_MATURITY + 1) confirmations -- Core's own wallet
    # computes max(0, (COINBASE_MATURITY + 1) - depth) -- so a selection that
    # stops at 100 can put an output in the plan that the network will not
    # accept, and the failure arrives at broadcast, after the key has already
    # been used on the offline machine. Every treasury output is a coinbase.
    mature = [u for u in utxos if tip - u["height"] + 1 > COINBASE_MATURITY]
    young = len(utxos) - len(mature)

    # AND NOT THE ONES AN UNCONFIRMED TRANSACTION HAS ALREADY SPENT.
    #
    # scantxoutset reads the UTXO SET, which is the chain and nothing else. A
    # transaction sitting in the mempool has spent its inputs as far as the
    # network is concerned and not at all as far as this scan is concerned.
    #
    # On 2026-10-02 the bounty was being paid in eight parts. Part one was
    # broadcast and was still unconfirmed when part two was planned, so the
    # scan offered the same 501 outputs again, the planner took them in the
    # same order, and the result was byte-identical to part one -- the same
    # txid. The founder signed it on the offline machine before anything
    # noticed, and the node refused it at broadcast. No money moved and none
    # could have, but the key had been used for nothing.
    #
    # So the mempool is read and its spent outpoints are removed. Waiting two
    # minutes for a confirmation would also have worked and is the wrong fix:
    # it makes correctness depend on somebody being patient.
    spent = set()
    for txid in rpc.call("getrawmempool") or []:
        try:
            entry = rpc.call("getrawtransaction", [txid, True])
        except SystemExit:
            raise
        except Exception as e:
            # IT USED TO `continue`, AND THAT IS THE WHOLE BUG.
            #
            # This loop exists to find outputs an unconfirmed transaction has
            # already spent, so they are not selected twice. A transaction we
            # fail to read contributes nothing to `spent` -- so its inputs stay
            # in `mature` and can be chosen, which is exactly the duplicate
            # spend this loop was added to prevent. One failed read and the
            # defence is silently off.
            #
            # An incomplete picture of the mempool is not a picture of an empty
            # mempool. Found by dang150296 (Urriki1502), 2026-10-04, and it is
            # the same fault as the pool's payout path and the release watcher
            # on the same days: could not ask, read as nothing there.
            die("cannot read mempool transaction %s (%s). The mempool picture "
                "would be incomplete, and an incomplete picture is how an "
                "already-spent output gets selected. Nothing was planned."
                % (txid, e))
        if not isinstance(entry, dict) or not isinstance(entry.get("vin"), list):
            die("mempool transaction %s came back in a shape this cannot "
                "read. Nothing was planned." % txid)
        for vin in entry["vin"]:
            if "coinbase" in vin:
                continue
            if "txid" not in vin or "vout" not in vin:
                die("an input of mempool transaction %s cannot be read. "
                    "Nothing was planned." % txid)
            spent.add((vin["txid"], vin["vout"]))
    if spent:
        before = len(mature)
        mature = [u for u in mature if (u["txid"], u["vout"]) not in spent]
        held = before - len(mature)
        if held:
            print("  in the mempool      %d output(s) already spent by an "
                  "unconfirmed transaction, left out" % held)

    print("  height              %d" % tip)
    print("  outputs             %d, totalling %s WAM" %
          (len(utxos), wam(float(scan["total_amount"]))))
    print("  spendable now       %d (%d are at or under %d confirmations)" %
          (len(mature), young, COINBASE_MATURITY))

    # Oldest first: it spends the coins that have been there longest and keeps
    # the output count falling rather than leaving a tail of dust behind.
    mature.sort(key=lambda u: u["height"])

    target = float(args.amount)
    chosen, got = [], 0.0
    for u in mature:
        chosen.append(u)
        got += float(u["amount"])
        # Over-collect by one input's worth so the fee is always covered.
        if got >= target + 3.0:
            break
    if got < target:
        die("the treasury has only %s WAM spendable and %s was asked for"
            % (wam(got), wam(target)))

    # Size, then fee. 148 bytes per P2PKH input, 34 per output, 10 overhead.
    size = len(chosen) * 148 + 2 * 34 + 10
    fee = round(FEERATE_PER_KVB * size / 1000.0, 8)
    change = round(got - target - fee, 8)
    if change < 0:
        die("the chosen inputs do not cover the amount and the fee")

    inputs = [{"txid": u["txid"], "vout": u["vout"]} for u in chosen]
    outputs = [{args.to: target}]
    # A change output below the dust threshold cannot be created, and
    # dropping it silently would pay the difference to miners.
    if change >= 0.00000546:
        outputs.append({TREASURY: change})
    else:
        fee = round(fee + change, 8)
        change = 0.0

    raw = rpc.call("createrawtransaction", [inputs, outputs])

    # signrawtransactionwithkey needs the scriptPubKey and amount of every
    # input, because the offline machine has no chain to look them up in.
    prevtxs = [{"txid": u["txid"], "vout": u["vout"],
                "scriptPubKey": u["scriptPubKey"], "amount": float(u["amount"])}
               for u in chosen]

    plan = {
        "network": "mainnet",
        "from": TREASURY,
        "to": args.to,
        "amount": target,
        "change": change,
        "fee": fee,
        "inputs": len(chosen),
        # THE EXACT OUTPUTS, NOT JUST HOW MANY OF THEM.
        #
        # `inputs` is a count, and a count proves nothing: a transaction
        # spending 201 entirely different outputs matches 201. Both machines
        # after this one compare against this list, in this order.
        "inputSet": inputs,
        "inputTotal": round(got, 8),
        "sizeBytes": size,
        "plannedAtHeight": tip,
        "unsignedHex": raw,
        "prevtxs": prevtxs,
        "reason": args.reason,
    }
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(plan, f, indent=2)

    print()
    print("=" * 66)
    print(" READ THIS BEFORE YOU SIGN IT")
    print("=" * 66)
    print("  paying             %s WAM" % wam(target))
    print("  to                 %s" % args.to)
    print("  from               %s  (the treasury)" % TREASURY)
    print("  inputs             %d, totalling %s WAM" % (len(chosen), wam(got)))
    print("  change back        %s WAM" % wam(change))
    print("  fee                %s WAM  (%d bytes)" % (wam(fee), size))
    print("  reason             %s" % args.reason)
    print()
    print("  written to         %s" % args.out)
    print()
    print("  Carry that file to the air-gapped machine and run:")
    print("      python3 scripts/treasury_spend.py sign --in %s" %
          os.path.basename(args.out))
    print("=" * 66)


# ---------------------------------------------------------------------------
# sign -- runs where the key is, with no network
# ---------------------------------------------------------------------------

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _cli_base(args):
    """The wam-cli invocation the offline machine uses, without the method."""
    cli = [args.cli, "-chain=main", "-rpcconnect=%s" % args.rpcconnect,
           "-rpcport=%d" % args.port]
    if args.rpcuser:
        cli += ["-rpcuser=%s" % args.rpcuser, "-rpcpassword=%s" % args.rpcpassword]
    return cli + ["-stdin"]


def _offline_decode(args, raw_hex):
    """Decode a transaction on the signing machine, before anything is approved.

    The node's own parser, not one written here. A transaction decoder is
    exactly the kind of code that looks simple and has edge cases measured in
    consensus failures, and this machine is already about to ask the same node
    to sign -- so the dependency is not new, only used one call earlier.
    """
    proc = subprocess.run(_cli_base(args) + ["decoderawtransaction"],
                          input=raw_hex + "\n", capture_output=True, text=True)
    if proc.returncode != 0:
        die("the transaction in the plan could not be decoded: %s"
            % (proc.stderr.strip() or proc.stdout.strip()))
    try:
        return json.loads(proc.stdout)
    except ValueError as e:
        die("the decoded transaction could not be read: %s" % e)


# The private key's own arithmetic, checked before the key is used.
#
# This proved the base58check checksum and stopped there, which catches a
# mistyped character and nothing else. A key with a sound checksum can still be
# for another network, carry the wrong payload shape, or hold a scalar outside
# the curve's order -- and each of those fails at the node, after the key has
# been typed, on the one machine where retrying costs a walk to another room.
WAM_WIF_VERSION = 190            # mainnet, consensus; see chainparams.cpp
SECP256K1_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141


def _wif_problem(s):
    """None if this is a usable WAM mainnet private key, else why not.

    Pure arithmetic and two hashes. No node, no network, and the string does
    not leave this function.
    """
    if any(c not in _B58 for c in s):
        return "it contains a character that is not base58"
    n = 0
    for c in s:
        n = n * 58 + _B58.index(c)
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    raw = bytes(len(s) - len(s.lstrip("1"))) + raw
    if len(raw) < 5:
        return "it is too short to be a key"
    body, check = raw[:-4], raw[-4:]
    if hashlib.sha256(hashlib.sha256(body).digest()).digest()[:4] != check:
        return ("its own checksum does not match, which means a mistyped or "
                "missing character")
    if body[0] != WAM_WIF_VERSION:
        return ("it is a private key for another network -- version byte %d, "
                "and WAM mainnet is %d" % (body[0], WAM_WIF_VERSION))
    payload = body[1:]
    if len(payload) == 33:
        if payload[-1] != 1:
            return "its compressed-key marker is wrong"
        payload = payload[:-1]
    elif len(payload) != 32:
        return "its payload is %d bytes, and a key is 32" % len(payload)
    scalar = int.from_bytes(payload, "big")
    if not 1 <= scalar < SECP256K1_N:
        return "the number in it is not a valid secp256k1 private key"
    return None


def cmd_sign(args):
    plan = json.load(open(args.infile, encoding="utf-8"))

    # READ THE TRANSACTION BEFORE SHOWING ANYTHING, AND LONG BEFORE THE KEY.
    #
    # What this used to do: print plan["to"], plan["amount"] and the rest --
    # which are text fields in a JSON file -- ask the operator to type the
    # destination back, and then sign plan["unsignedHex"], which nothing had
    # decoded or compared against any of it.
    #
    # So the ceremony confirmed the LABEL and signed the PARCEL. If the two
    # ever disagreed -- a tampered file, a corrupted stick, a bug in `plan` --
    # the operator would read the correct address on screen, type it back
    # carefully, and sign something else. This file crosses an air gap on
    # removable media, which is precisely the journey the gap exists to make
    # safe, and this was the one place that trusted a label across it.
    #
    # Decoding needs the node, which this machine has -- it is about to ask it
    # to sign. Doing it first costs one RPC call and means the transaction is
    # read by something before it is approved by someone.
    #
    # Found by dang150296 (Urriki1502), 2026-10-04.
    decoded = _offline_decode(args, plan["unsignedHex"])
    _verify_against_plan(plan, decoded, "the unsigned transaction")

    print("=" * 66)
    print(" WHAT YOU ARE ABOUT TO SIGN")
    print("=" * 66)
    print("  paying       %s WAM" % wam(plan["amount"]))
    print("  to           %s" % plan["to"])
    print("  from         %s" % plan["from"])
    print("  change back  %s WAM" % wam(plan["change"]))
    print("  fee          %s WAM" % wam(plan["fee"]))
    print("  reason       %s" % plan.get("reason", "(none given)"))
    print("  verified             the bytes to be signed decode to exactly this")
    print("=" * 66)
    if input("  type the destination address again to confirm: ").strip() != plan["to"]:
        die("that is not the address in the plan; nothing was signed")

    # The key is read from the terminal, used once, and never written down.
    # getpass keeps it off the screen and out of the shell's history.
    # A TYPO IS CAUGHT HERE, NOT BY THE NODE, AND IT COSTS ONE RETRY.
    #
    # The key is typed by hand, from somewhere that is not on this machine,
    # into a prompt that shows nothing. Fifty-two characters, and one wrong
    # one used to end the run with "Invalid private key" from the node -- so
    # the whole command had to be started again, the address retyped, for a
    # single letter.
    #
    # A WIF carries its own base58check checksum, so a typo is detectable
    # right here with no node, no network and no key ever leaving this
    # function. Three tries, then it gives up rather than looping for ever.
    #
    # It does not prove the key is the TREASURY's -- that needs secp256k1 and
    # is the node's job. It proves the key is a key, which is what a typo
    # breaks.
    wif = ""
    for attempt in range(3):
        wif = getpass.getpass("  treasury private key (WIF, not echoed): ").strip()
        if not wif:
            die("no key was given")
        why = _wif_problem(wif)
        if why is None:
            break
        left = 2 - attempt
        if left:
            print("  that key cannot be used: %s. %d try/tries left."
                  % (why, left))
        else:
            die("three unusable keys; nothing was signed")

    # EVERYTHING GOES DOWN STDIN, NOTHING ON THE COMMAND LINE.
    #
    # Two reasons, and the first one is fatal on Windows. The transaction is
    # 29,974 bytes, which is 59,948 hex characters, and cmd.exe stops at
    # 8,191 for the whole line -- so the earlier version of this could not
    # run there at all. It failed with "the command line is too long" and the
    # founder was the one who noticed.
    #
    # The second is worse and was invisible: the key was an argv element, so
    # it sat in the process list where any program on the machine could read
    # it. wam-cli -stdin takes the arguments one per line instead, which
    # keeps the key out of argv entirely.
    cli = _cli_base(args) + ["signrawtransactionwithkey"]

    payload = "\n".join([plan["unsignedHex"],
                          json.dumps([wif]),
                          json.dumps(plan["prevtxs"])]) + "\n"
    proc = subprocess.run(cli, input=payload, capture_output=True, text=True)
    del wif, payload
    if proc.returncode != 0:
        die("signing failed: %s" % (proc.stderr.strip() or proc.stdout.strip()))

    res = json.loads(proc.stdout)
    if not res.get("complete"):
        die("the transaction is not fully signed: %s" %
            json.dumps(res.get("errors", []))[:400])

    out = dict(plan)
    out["signedHex"] = res["hex"]
    out.pop("prevtxs", None)          # no longer needed, and it is bulky
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=2)

    print()
    print("  signed, and the key was not written anywhere.")
    print("  carry %s back and run:" % args.out)
    print("      python3 scripts/treasury_spend.py broadcast --in %s" %
          os.path.basename(args.out))


# ---------------------------------------------------------------------------
# broadcast -- runs where the chain is, and checks before it sends
# ---------------------------------------------------------------------------

def cmd_broadcast(args):
    signed = json.load(open(args.infile, encoding="utf-8"))
    rpc = Rpc(args.conf, port=args.port)

    # DECODE WHAT IS ACTUALLY THERE, not what the file claims.
    #
    # Between the two machines a file can be edited, swapped or corrupted.
    # The only defence is to read the transaction itself and compare it
    # against the plan, field by field, before it is sent anywhere.
    tx = rpc.call("decoderawtransaction", [signed["signedHex"]])

    # The same exact check the signer now makes, on the signed bytes this
    # time. Inputs in the approved order, outputs to the atom, fee conserved.
    # What follows it is the human-readable report, which stays because a
    # person should still see what is about to happen in words.
    _verify_against_plan(signed, tx, "the signed transaction")

    # AND ARE THOSE INPUTS STILL THERE?
    #
    # Everything above compares the transaction to the plan. Nothing asked the
    # chain whether the outputs the plan selected are still unspent -- and
    # between planning, carrying the file to another room, signing it and
    # carrying it back, they can stop being. A transaction spending one that
    # is gone is rejected by every node, after the key has been used.
    #
    # gettxout with include_mempool=true is the question, asked for every
    # input immediately before the send rather than once at the start.
    missing = []
    live_total = 0
    for txid, vout in _outpoints(signed.get("inputSet", []), "the plan"):
        entry = rpc.call("gettxout", [txid, vout, True])
        if not entry:
            missing.append("%s:%d" % (txid, vout))
        else:
            live_total += _atoms(entry.get("value"), "a live input value")
    if missing:
        die("%d of the inputs this spends are no longer unspent -- the first "
            "is %s. Nothing was sent; re-run `plan`." % (len(missing), missing[0]))
    if live_total != _atoms(signed["inputTotal"], "the input total"):
        die("the inputs are worth %s WAM on the chain now, and the plan said "
            "%s. Nothing was sent." % (wam(live_total / 1e8), wam(signed["inputTotal"])))

    paid = {}
    for o in tx["vout"]:
        addr = o["scriptPubKey"].get("address")
        if addr:
            paid[addr] = round(paid.get(addr, 0.0) + float(o["value"]), 8)

    want_to = round(float(signed["amount"]), 8)
    want_change = round(float(signed["change"]), 8)

    problems = []
    if signed["to"] not in paid:
        problems.append("it does not pay %s at all" % signed["to"])
    elif paid[signed["to"]] != want_to:
        problems.append("it pays %s WAM to %s, the plan said %s"
                        % (wam(paid[signed["to"]]), signed["to"], wam(want_to)))
    if want_change > 0:
        if paid.get(TREASURY, 0.0) != want_change:
            problems.append("change is %s WAM, the plan said %s"
                            % (wam(paid.get(TREASURY, 0.0)), wam(want_change)))
    for addr in paid:
        if addr not in (signed["to"], TREASURY):
            problems.append("it pays an address in neither the plan nor the "
                            "treasury: %s" % addr)
    if len(tx["vin"]) != signed["inputs"]:
        problems.append("it spends %d inputs, the plan said %d"
                        % (len(tx["vin"]), signed["inputs"]))

    total_out = round(sum(paid.values()), 8)
    fee = round(float(signed["inputTotal"]) - total_out, 8)
    if abs(fee - float(signed["fee"])) > 0.00000001:
        problems.append("the fee works out at %s WAM, the plan said %s"
                        % (wam(fee), wam(signed["fee"])))

    print("=" * 66)
    print(" WHAT THE SIGNED TRANSACTION ACTUALLY DOES")
    print("=" * 66)
    for addr, amt in sorted(paid.items(), key=lambda kv: -kv[1]):
        tag = "  <- the destination" if addr == signed["to"] else \
              "  <- back to the treasury" if addr == TREASURY else "  <- UNEXPECTED"
        print("  %s WAM  %s%s" % (wam(amt), addr, tag))
    print("  fee                %s WAM" % wam(fee))
    print("  inputs             %d" % len(tx["vin"]))
    print("  txid               %s" % tx["txid"])
    print("=" * 66)

    if problems:
        print()
        for p in problems:
            print("  MISMATCH  %s" % p)
        die("the signed transaction does not match the plan. Nothing was sent.")

    print("  every field matches the plan.")
    if not args.yes:
        if input("  type SEND to broadcast it: ").strip() != "SEND":
            die("not sent")

    txid = rpc.call("sendrawtransaction", [signed["signedHex"]])
    print()
    print("  broadcast. txid %s" % txid)
    print()
    print("  Publish it: the amount, the reason and this txid. That is the")
    print("  promise in SECURITY.md and in docs/TREASURY_CUSTODY.md, and this")
    print("  is the treasury's first movement since block 1.")


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="build the unsigned transaction (online)")
    p.add_argument("--to", required=True)
    p.add_argument("--amount", required=True, type=float)
    p.add_argument("--reason", required=True,
                   help="one line, and it will be published with the txid")
    p.add_argument("--conf", default="/root/.wam-mainnet/wam.conf")
    p.add_argument("--port", type=int, default=9554)
    p.add_argument("--out", default="treasury-plan.json")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("sign", help="sign it where the key is (offline)")
    p.add_argument("--in", dest="infile", default="treasury-plan.json")
    p.add_argument("--out", default="treasury-signed.json")
    p.add_argument("--cli", default="wam-cli")
    p.add_argument("--rpcconnect", default="127.0.0.1")
    p.add_argument("--port", type=int, default=9554)
    p.add_argument("--rpcuser", default="")
    p.add_argument("--rpcpassword", default="")
    p.set_defaults(func=cmd_sign)

    p = sub.add_parser("broadcast", help="check it, then send it (online)")
    p.add_argument("--in", dest="infile", default="treasury-signed.json")
    p.add_argument("--conf", default="/root/.wam-mainnet/wam.conf")
    p.add_argument("--port", type=int, default=9554)
    p.add_argument("--yes", action="store_true", help="skip the typed confirmation")
    p.set_defaults(func=cmd_broadcast)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

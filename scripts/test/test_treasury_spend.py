#!/usr/bin/env python3
# Copyright (c) 2026 The WAM Coin developers
# Distributed under the MIT software license, see COPYING.
"""
===============================================================================
 test_treasury_spend.py -- the first tests this script has ever had
===============================================================================

     python3 scripts/test/test_treasury_spend.py

 WHY THIS EXISTS

 scripts/treasury_spend.py moves more coin per run than anything else in this
 project, holds the treasury's private key in memory while it signs, and on
 2026-10-04 had no automated test of any kind. The mining pool has fourteen
 test files. The script that spends the treasury had none, and it is the only
 money path here that a person operates by hand, from two machines, with a
 file carried between them.

 It had already been wrong twice in a fortnight -- it selected outputs that an
 unconfirmed transaction had already spent, and it accepted a mistyped WIF
 because nothing checked the checksum -- and both were found by a person, in
 use, not by anything that runs.

 WHAT IS TESTED HERE, AND WHAT IS NOT

 Everything below is a pure function: no node, no network, no key. That is the
 half that can be tested without a chain, and it is also the half every one of
 the findings landed in -- reading a transaction, comparing it to a plan, and
 judging a private key.

 The three commands themselves need a node and an operator, and the regtest
 rehearsal in docs/REHEARSALS.md is what exercises those. This does not
 replace it; it makes the arithmetic and the refusals provable without it.
===============================================================================
"""

import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import treasury_spend as T  # noqa: E402

GRN = "\033[32m"; RED = "\033[31m"; BLD = "\033[1m"; OFF = "\033[0m"

passed = 0
failed = []


def check(name, fn):
    global passed
    try:
        fn()
        passed += 1
        print("  %sok%s    %s" % (GRN, OFF, name))
    except AssertionError as e:
        failed.append(name)
        print("  %sFAIL%s  %s\n        %s" % (RED, OFF, name, e))
    except SystemExit as e:
        # die() raises SystemExit, which is NOT an Exception and so was not
        # caught here. One refusal inside a check ended the entire run at
        # that line: the checks before it printed, the ones after it never
        # ran, and the output read like a short pass.
        failed.append(name)
        print("  %sFAIL%s  %s\n        it refused: %s" % (RED, OFF, name, e))
    except Exception as e:                       # noqa: BLE001
        failed.append(name)
        print("  %sFAIL%s  %s\n        unexpected %s: %s"
              % (RED, OFF, name, type(e).__name__, e))


def dies(fn, because=""):
    """The script refuses by calling die(), which raises SystemExit."""
    try:
        fn()
    except SystemExit:
        return
    raise AssertionError("it was accepted, and it should not have been. " + because)


def b58(payload: bytes) -> str:
    """base58check-encode, so a test key can be built rather than pasted."""
    raw = payload + hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    n = int.from_bytes(raw, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = T._B58[r] + out
    return "1" * (len(raw) - len(raw.lstrip(b"\x00"))) + out


def wif_for(scalar: int, version=T.WAM_WIF_VERSION, marker=1, width=32) -> str:
    body = bytes([version]) + scalar.to_bytes(width, "big")
    if marker is not None:
        body += bytes([marker])
    return b58(body)


# A key that is a key. Scalar 1 is the canonical throwaway: it is valid
# arithmetic and belongs to nobody's wallet here, which is the point -- this
# tests the parser, and a parser must never be tested with a real key.
GOOD_WIF = wif_for(1)




def accepts(name, fn):
    """It must go through without complaint."""
    def run():
        fn()
    check(name, run)


def refuses(name, fn, because=""):
    """It must call die(), which raises SystemExit."""
    def run():
        dies(fn, because)
    check(name, run)


# ---------------------------------------------------------------------------
print()
print("%sa private key is checked before it is used%s" % (BLD, OFF))


def key_ok():
    why = T._wif_problem(GOOD_WIF)
    assert why is None, "a well-formed key was rejected: %s" % why


def key_bad(name, wif, expect=None):
    def run():
        why = T._wif_problem(wif)
        assert why is not None, "it was accepted"
        if expect:
            assert expect in why, "refused for the wrong reason: %s" % why
    check(name, run)


check("a well-formed WAM mainnet key is accepted", key_ok)

mistyped = GOOD_WIF[:-2] + ("A" if GOOD_WIF[-2] != "A" else "B") + GOOD_WIF[-1]
key_bad("one mistyped character is caught by the checksum", mistyped, "checksum")

# Bitcoin mainnet is 128; WAM is 190. A key with a perfect checksum for another
# chain used to pass every check here and fail at the node, after it had been
# typed by hand on the machine where retrying costs a walk to another room.
key_bad("a key for another network is refused, by its version byte",
        wif_for(1, version=128), "another network")
key_bad("a wrong compressed marker is refused", wif_for(1, marker=2), "marker")
key_bad("a zero scalar is refused", wif_for(0), "secp256k1")
key_bad("a scalar at the curve order is refused", wif_for(T.SECP256K1_N), "secp256k1")
key_bad("a payload of the wrong length is refused",
        wif_for(1, width=31, marker=None), "32")


# ---------------------------------------------------------------------------
print()
print("%smoney is whole numbers, or it is refused%s" % (BLD, OFF))


def atoms_exact():
    got = T._atoms("1248.75")
    assert got == 124875000000, "1248.75 became %d atoms" % got


def atoms_tenth():
    # The value binary floating point cannot hold. Decimal can.
    got = T._atoms("0.3")
    assert got == 30000000, "0.3 became %d atoms" % got


check("a plain coin value converts exactly", atoms_exact)
check("a value floating point cannot hold still converts exactly", atoms_tenth)
refuses("a ninth decimal is refused, not rounded away",
        lambda: T._atoms("1.000000001"))
refuses("a negative value is refused", lambda: T._atoms("-1.0"))
refuses("text that is not a number is refused", lambda: T._atoms("five hundred"))


# ---------------------------------------------------------------------------
print()
print("%sa transaction is compared to the plan, not to its own labels%s" % (BLD, OFF))

TO = "WcQCFiCzwikQTTmPeafn73e3asC32ofyLr"
TREASURY = T.TREASURY

PLAN = {
    "to": TO,
    "amount": "1000.00000000",
    "change": "248.00000000",
    "fee": "0.00400000",
    "inputTotal": "1248.00400000",
    "inputSet": [{"txid": "a" * 64, "vout": 0},
                 {"txid": "b" * 64, "vout": 1}],
}

GOOD_OUT = [(TO, "1000.00000000"), (TREASURY, "248.00000000")]


def tx_for(outs, ins=None):
    ins = PLAN["inputSet"] if ins is None else ins
    return {"vin": [dict(i) for i in ins],
            "vout": [{"value": v, "scriptPubKey": {"address": a}} for a, v in outs]}


def verify(plan=PLAN, tx=None):
    T._verify_against_plan(plan, tx if tx is not None else tx_for(GOOD_OUT), "test")


accepts("a transaction that matches the plan exactly is accepted", verify)

refuses("a changed destination is refused",
        lambda: verify(tx=tx_for([("WrOnGaDdReSs11111111111111111111111", "1000.00000000"),
                                  (TREASURY, "248.00000000")])))

refuses("a changed amount is refused",
        lambda: verify(tx=tx_for([(TO, "1000.00000001"),
                                  (TREASURY, "247.99999999")])))

refuses("an extra output nobody planned is refused",
        lambda: verify(tx=tx_for(GOOD_OUT +
                                 [("WsOmEoNeElSe1111111111111111111111", "1.0")])))

refuses("an output paying no address at all is refused, not skipped",
        lambda: verify(tx={
            "vin": [dict(i) for i in PLAN["inputSet"]],
            "vout": [{"value": "1000.00000000", "scriptPubKey": {"address": TO}},
                     {"value": "248.00000000", "scriptPubKey": {"asm": "OP_RETURN"}}]}))

# The count was all the broadcaster ever checked, and two inputs is two inputs
# however different they are.
refuses("different inputs with the same count are refused",
        lambda: verify(tx=tx_for(GOOD_OUT, ins=[{"txid": "c" * 64, "vout": 0},
                                                {"txid": "d" * 64, "vout": 1}])),
        "two entirely different inputs matched a count of two")

refuses("the approved inputs in a different order are refused",
        lambda: verify(tx=tx_for(GOOD_OUT, ins=list(reversed(PLAN["inputSet"])))))

refuses("the same input spent twice is refused",
        lambda: verify(tx=tx_for(GOOD_OUT,
                                 ins=[PLAN["inputSet"][0], PLAN["inputSet"][0]])))

refuses("a transaction that does not conserve value is refused",
        lambda: verify(plan=dict(PLAN, inputTotal="1248.40400000")),
        "0.4 WAM appeared from nowhere and nothing noticed")

refuses("a plan that does not name its inputs is refused",
        lambda: verify(plan={k: v for k, v in PLAN.items() if k != "inputSet"}),
        "a plan written by the old script was accepted")


# ---------------------------------------------------------------------------
print()
print("%sone payment in parts, and no coin offered twice%s" % (BLD, OFF))


class FakeRpc:
    """A node that answers createrawtransaction and nothing else.

    _plan_part needs exactly one RPC call and no chain, so the selection and
    the fee arithmetic are testable without either."""

    def __init__(self):
        self.calls = 0

    def call(self, method, params=None):
        assert method == "createrawtransaction", method
        self.calls += 1
        return "00" * 10


def treasury_pool(n, start_height=1):
    """n of the 2.5 WAM coinbase outputs the treasury is actually made of."""
    return [{"txid": "%064x" % i, "vout": 0, "amount": 2.5,
             "height": start_height + i,
             "scriptPubKey": "76a914" + "00" * 20 + "88ac"}
            for i in range(n)]


def outpoints(plan):
    return {(i["txid"], i["vout"]) for i in plan["inputSet"]}


def parts_are_disjoint():
    pool = treasury_pool(4200)
    rpc = FakeRpc()
    built = [T._plan_part(rpc, pool, 1248.75, TO, "r", 100, i, 8)
             for i in range(1, 9)]
    assert rpc.calls == 8, rpc.calls
    seen = set()
    for plan in built:
        here = outpoints(plan)
        assert not (here & seen), "two parts spend the same output"
        seen |= here
    assert len(seen) == sum(p["inputs"] for p in built)


def pool_is_consumed():
    pool = treasury_pool(4200)
    before = len(pool)
    plan = T._plan_part(FakeRpc(), pool, 1248.75, TO, "r", 100, 1, 8)
    assert len(pool) == before - plan["inputs"], (len(pool), plan["inputs"])


def every_part_pays_its_amount():
    pool = treasury_pool(4200)
    rpc = FakeRpc()
    for i in range(1, 9):
        plan = T._plan_part(rpc, pool, 1248.75, TO, "r", 100, i, 8)
        assert plan["amount"] == 1248.75, plan["amount"]
        assert plan["to"] == TO
        # value is conserved: what came in is what went out, plus the fee
        total = round(plan["amount"] + plan["change"] + plan["fee"], 8)
        assert total == round(plan["inputTotal"], 8), (total, plan["inputTotal"])


def a_short_pool_is_refused():
    # eight parts of 1248.75 need about 4,000 outputs; 600 is one part's worth
    pool = treasury_pool(600)
    rpc = FakeRpc()
    T._plan_part(rpc, pool, 1248.75, TO, "r", 100, 1, 8)
    dies(lambda: T._plan_part(rpc, pool, 1248.75, TO, "r", 100, 2, 8),
         "the second part was planned out of coins that are not there")


check("eight parts cut from one scan share no output", parts_are_disjoint)
check("a part removes what it spends from the pool", pool_is_consumed)
check("every part pays its amount and conserves value",
      every_part_pays_its_amount)
check("a part that cannot be funded is refused, not shrunk",
      a_short_pool_is_refused)


def named(i, n):
    return T._part_name("treasury-plan.json", i, n)


def parts_are_named():
    assert named(2, 8) == "treasury-plan-2of8.json", named(2, 8)
    assert named(8, 8) == "treasury-plan-8of8.json", named(8, 8)
    assert T._part_name("x", 1, 2) == "x-1of2.json", T._part_name("x", 1, 2)


check("the parts are named so a person can see which is which",
      parts_are_named)


# --- the signer will not use one key on two different payments -------------

def plan_with(to=TO, ins=None, n=0):
    return {"to": to, "amount": 1248.75,
            "inputSet": ins if ins is not None
            else [{"txid": "%064x" % (n * 10 + k), "vout": 0} for k in range(3)]}


def batch_ok():
    assert T._batch_problem(["a.json", "b.json"],
                            [plan_with(n=1), plan_with(n=2)]) is None


def batch_two_destinations():
    why = T._batch_problem(["a.json", "b.json"],
                           [plan_with(n=1),
                            plan_with(to=TREASURY, n=2)])
    assert why and "different addresses" in why, why


def batch_shared_outpoint():
    shared = [{"txid": "c" * 64, "vout": 0}]
    why = T._batch_problem(["a.json", "b.json"],
                           [plan_with(ins=shared), plan_with(ins=shared)])
    assert why and "both spend" in why, why


def batch_nameless_inputs():
    why = T._batch_problem(["a.json", "b.json"],
                           [plan_with(n=1), {"to": TO}])
    assert why and "does not name the outputs" in why, why


check("two parts to one address with distinct coins are one payment", batch_ok)
check("two parts to different addresses are refused as one signing",
      batch_two_destinations)
check("two parts spending the same coin are refused before the key is asked",
      batch_shared_outpoint)
check("a part that names no inputs is refused, not skipped",
      batch_nameless_inputs)

# ---------------------------------------------------------------------------
print()
print("=" * 66)
if not failed:
    print("  %s%s%d checks passed%s" % (GRN, BLD, passed, OFF))
else:
    print("  %s%s%d failed%s, %d passed" % (RED, BLD, len(failed), OFF, passed))
    for f in failed:
        print("    - %s" % f)
print("=" * 66)
print()
sys.exit(1 if failed else 0)

'use strict';
// Copyright (c) 2026 The WAM Coin developers
// Distributed under the MIT software license, see COPYING.
//
// ---------------------------------------------------------------------------
// A checksum decides whether an address is ours. A prefix only suggests.
//
// Until 2026-10-15 addressToScript asked "does this look like somebody else's
// bech32?" before trying to decode anything. That question is a guess: it
// asks whether there is a '1' with only bech32 characters after it, and about
// one valid base58 address in twenty says yes by chance. This project's own
// treasury address is one of them -- WdMMqW1DcgWZ6HtyJuEMdce6QkKg4raGmE
// lower-cases to a '1' followed by 27 characters that all happen to be in the
// bech32 alphabet -- so the pool called it a segwit address for 'wdmmqw'.
//
// A miner whose address matched was disconnected at mining.authorize, with a
// message telling him his own address belonged to another chain. An operator
// whose poolAddress matched could not start his pool at all.
//
// The miner has decoded before guessing since 2026-09-19. The pool had not.
//
// These tests hold the order down, in both directions: a valid address is
// never refused by a pattern, and a foreign segwit address is still named
// rather than reported as "invalid base58 character".
// ---------------------------------------------------------------------------

const assert = require('assert');
const crypto = require('crypto');
const { validateAddress, addressToScript } = require('../lib/util');
const { ADDRESS_VERSIONS } = require('../lib/constants');

let pass = 0;
const fail = [];

function test(name, fn) {
    try { fn(); pass++; console.log(`  \x1b[32mok\x1b[0m    ${name}`); }
    catch (e) { fail.push(name); console.log(`  \x1b[31mFAIL\x1b[0m  ${name}\n        ${e.message}`); }
}

const MAIN = ADDRESS_VERSIONS.mainnet;

// --- a base58 encoder, so the sweep below generates addresses rather than
//     reading them from the code it is testing -------------------------------
const B58 = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';

function b58encode(buf) {
    let n = 0n;
    for (const b of buf) n = n * 256n + BigInt(b);
    let s = '';
    while (n > 0n) { s = B58[Number(n % 58n)] + s; n /= 58n; }
    for (const b of buf) { if (b === 0) s = '1' + s; else break; }
    return s;
}

function makeAddress(version) {
    const payload = Buffer.concat([Buffer.from([version]), crypto.randomBytes(20)]);
    const checksum = crypto.createHash('sha256')
        .update(crypto.createHash('sha256').update(payload).digest())
        .digest().subarray(0, 4);
    return b58encode(Buffer.concat([payload, checksum]));
}

console.log('\n\x1b[1ma valid address is never refused by a pattern\x1b[0m');

// The address the guess used to refuse, and the reason it refused it. Kept
// first because it is the one that proves the point without any statistics:
// consensus rule WAM-1 checks this address in every single block.
test('the treasury address is accepted', () => {
    const r = validateAddress('WdMMqW1DcgWZ6HtyJuEMdce6QkKg4raGmE', MAIN);
    assert.ok(r.ok, `refused: ${r.reason}`);
    assert.strictEqual(r.kind, 'base58');
    assert.strictEqual(addressToScript('WdMMqW1DcgWZ6HtyJuEMdce6QkKg4raGmE', MAIN)
        .toString('hex'), '76a914a101cf17c209638136abe19e14dc4e1c9987370f88ac');
});

// The sweep. 20,000 per network and script type is enough to catch a 5% fault
// many times over while staying inside a test run: the old code refused ~1,000
// of each of these six groups.
//
// Addresses beginning with the network's hrp are excluded and tested
// separately below, because the node refuses those and this pool must agree
// with the node. They are about 1 in 1,700.
for (const [net, v] of Object.entries(ADDRESS_VERSIONS)) {
    for (const [kind, version] of [['P2PKH', v.pubkey], ['P2SH', v.script]]) {
        test(`${net} ${kind}: 20,000 generated addresses, none refused`, () => {
            const refused = [];
            let skipped = 0;
            for (let i = 0; i < 20000; i++) {
                const a = makeAddress(version);
                if (a.slice(0, v.bech32.length).toLowerCase() === v.bech32) {
                    skipped++;
                    continue;
                }
                const r = validateAddress(a, v);
                if (!r.ok && refused.length < 3) refused.push(`${a} -- ${r.reason}`);
                else if (!r.ok) refused.push(null);
            }
            assert.strictEqual(refused.length, 0,
                `${refused.length} refused, e.g.\n        ` +
                refused.filter(Boolean).join('\n        '));
            assert.ok(skipped < 200,
                `${skipped} addresses began with the hrp -- that is far more ` +
                'than the ~1 in 1,700 expected, so something is wrong with ' +
                'this test rather than with the pool');
        });
    }
}

console.log('\n\x1b[1mand what must be refused still is\x1b[0m');

// The guess exists for a real reason and must keep working. Pasting a Bitcoin
// address into a WAM pool is a routine mistake and deserves a routine answer,
// not "invalid base58 character '0'".
for (const [a, who] of [
    ['bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4', 'bc'],
    ['ltc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4', 'ltc'],
    ['bc1p5cyxnuxmeuwuvkwfem96lqzszd02n6xdcjrs20cac6yqjjwudpxqkedrcr', 'bc'],
]) {
    test(`a ${who}1 address is refused and named`, () => {
        const r = validateAddress(a, MAIN);
        assert.ok(!r.ok, 'accepted a foreign segwit address');
        assert.match(r.reason, new RegExp(`segwit address for '${who}'`),
                     `the miner is told nothing useful: ${r.reason}`);
    });
}

test('a Bitcoin legacy address is refused by version byte, not by pattern', () => {
    const r = validateAddress('1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa', MAIN);
    assert.ok(!r.ok, 'accepted a Bitcoin P2PKH address');
    assert.match(r.reason, /version byte 0/,
                 `decoded cleanly, so say so: ${r.reason}`);
});

// Falling through to base58check must not make a mistyped wam1 address
// acceptable -- and the message must be the bech32 decoder's, not a base58
// complaint about an address the sender never meant to be base58.
test('a mistyped wam1 address is refused, and told it is bech32', () => {
    const r = validateAddress('wam1qrulaxxlqf65madsmhqrevf467r6qmgdrxhf9yx', MAIN);
    assert.ok(!r.ok, 'accepted a mistyped bech32 address');
    assert.match(r.reason, /bech32/, `wrong message: ${r.reason}`);
});

test('a real wam1 address is still accepted as bech32', () => {
    const a = 'wam1qrulaxxlqf65madsmhqrevf467r6qmgdrxhf9yw';
    const r = validateAddress(a, MAIN);
    assert.ok(r.ok, `refused: ${r.reason}`);
    assert.strictEqual(r.kind, 'bech32');
    assert.strictEqual(addressToScript(a, MAIN).toString('hex'),
                       '00141f3fd31be04ea9beb61bb8079626baf0f40da1a3');
});

test('a testnet address is refused by a mainnet pool', () => {
    const r = validateAddress('twam1qrulaxxlqf65madsmhqrevf467r6qmgdrxhnxymw', MAIN);
    assert.ok(!r.ok, 'accepted a testnet address on mainnet');
});

test('an empty address is refused without throwing', () => {
    assert.strictEqual(validateAddress('', MAIN).ok, false);
    assert.strictEqual(validateAddress(null, MAIN).ok, false);
});

// --- agreeing with the node, which is the thing that pays -------------------
//
// key_io.cpp, DecodeDestination:
//
//     is_bech32 = ToLower(str.substr(0, hrp.size())) == hrp
//
// Three characters, case-insensitive, and no '1' required. When they match,
// the node never tries base58 -- so these two addresses, both valid
// base58check for mainnet, are ones a mainnet node calls invalid. Checked
// against a real node with `wam-cli validateaddress`.
//
// Accepting them here would be worse than refusing a good address: a miner
// would authorize, mine, accrue a balance, and then every sendmany carrying
// him would fail and take the rest of the batch with it. He is told now,
// while he can still generate another address.
for (const [a, prefix] of [['WaM1eGQr6YgwTPrX3G6n2UZLVwWa8W9Qgb', 'WaM'],
                           ['WamP6fzPxQAmriTpSnHmNUX25MZwmiw8bS', 'Wam']]) {
    test(`base58 beginning '${prefix}' is refused, as the node refuses it`, () => {
        const r = validateAddress(a, MAIN);
        assert.ok(!r.ok, 'accepted an address the node cannot parse or pay');
        assert.match(r.reason, /valid base58check, but it begins with/,
                     `the miner must be told what is actually wrong: ${r.reason}`);
    });
}

console.log(`\n  ${pass} passed, ${fail.length} failed\n`);
process.exit(fail.length ? 1 : 0);

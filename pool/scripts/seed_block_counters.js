#!/usr/bin/env node
// Copyright (c) 2026 The WAM Coin developers
// Distributed under the MIT software license, see COPYING.
//
// ===========================================================================
//  seed_block_counters.js -- set the pool's block counters from the chain
// ===========================================================================
//
//      node pool/scripts/seed_block_counters.js [--config pool/config.json]
//      node pool/scripts/seed_block_counters.js --dry-run
//
//  WHY THIS EXISTS
//
//  The dashboard read BLOCKS FOUND from a redis list that is trimmed at 5000
//  entries, so on 1 October 2026 it had said 5000 for two days while blocks
//  kept arriving. shareProcessor.js now keeps blocks:confirmed:count, which
//  nothing trims -- but a counter that starts at zero on a pool that has
//  already found more than five thousand blocks would show the old number for
//  months before overtaking it.
//
//  So the counter is seeded once, and not from redis: redis is a cache and
//  the trimmed list is exactly the thing that lost the answer. THE CHAIN IS
//  THE RECORD. Every block this pool found pays its reward to the pool's own
//  address in the coinbase, and that is still there, in every block, for
//  anybody to count -- including somebody who does not believe this number.
//
//  Orphans cannot come from the chain, because an orphan is precisely a block
//  that is not on it. That counter is seeded from the list, which is capped
//  at 1000 and nowhere near it.
// ===========================================================================

'use strict';

const fs = require('fs');
const path = require('path');
const http = require('http');
const Redis = require('ioredis');

const args = process.argv.slice(2);
const dryRun = args.includes('--dry-run');
const cfgIdx = args.indexOf('--config');
const cfgPath = cfgIdx >= 0 ? args[cfgIdx + 1]
                            : path.join(__dirname, '..', 'config.json');

const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
const poolAddress = cfg.poolAddress;
// The config names it `daemons`, an array, and the prefix is a
// top-level `redisPrefix` -- read from a running pool's own file
// rather than assumed. The first version guessed `daemon` and
// `redis.prefix` and failed with "socket hang up", which is what
// guessing a shape looks like from the outside.
const d = (cfg.daemons && cfg.daemons[0]) || cfg.daemon || {};

function rpc(method, params = []) {
    return new Promise((resolve, reject) => {
        const body = JSON.stringify({ jsonrpc: '1.0', id: 'seed', method, params });
        const req = http.request({
            host: d.host || '127.0.0.1',
            port: d.port,
            method: 'POST',
            auth: `${d.user}:${d.password}`,
            headers: { 'Content-Type': 'text/plain',
                       'Content-Length': Buffer.byteLength(body) }
        }, (res) => {
            let out = '';
            res.on('data', (c) => { out += c; });
            res.on('end', () => {
                try {
                    const j = JSON.parse(out);
                    if (j.error) return reject(new Error(j.error.message));
                    resolve(j.result);
                } catch (e) { reject(e); }
            });
        });
        req.on('error', reject);
        req.write(body);
        req.end();
    });
}

(async () => {
    if (!poolAddress) throw new Error(`no poolAddress in ${cfgPath}`);
    const tip = await rpc('getblockcount');
    process.stdout.write(
        `counting blocks paid to ${poolAddress}\n  chain tip ${tip}\n`);

    let found = 0;
    let firstHeight = null;
    let lastHeight = null;

    for (let h = 1; h <= tip; h++) {
        const hash = await rpc('getblockhash', [h]);
        // verbosity 2 gives the coinbase outputs without a second call.
        const block = await rpc('getblock', [hash, 2]);
        const coinbase = block.tx && block.tx[0];
        if (!coinbase) continue;
        const paysUs = (coinbase.vout || []).some((o) => {
            const a = o.scriptPubKey && o.scriptPubKey.address;
            return a === poolAddress;
        });
        if (paysUs) {
            found++;
            if (firstHeight === null) firstHeight = h;
            lastHeight = h;
        }
        if (h % 1000 === 0) {
            process.stdout.write(`  ...${h}/${tip}  found ${found}\n`);
        }
    }

    process.stdout.write(
        `\n  ${found} block(s) on this chain pay the pool address\n` +
        `  first ${firstHeight}   last ${lastHeight}\n`);

    const prefix = cfg.redisPrefix || (cfg.redis && cfg.redis.prefix) || '';
    const key = (k) => (prefix ? `${prefix}:${k}` : k);
    const redis = new Redis(cfg.redis || {});

    const listLen = await redis.llen(key('blocks:confirmed'));
    const orphanLen = await redis.llen(key('blocks:orphaned'));
    const maturing = await redis.llen(key('blocks:maturing'));
    const pending = Object.keys(await redis.hgetall(key('blocks:pending'))).length;
    const existing = parseInt(await redis.get(key('blocks:confirmed:count')) || '0', 10);

    process.stdout.write(
        `  redis: confirmed list ${listLen}, counter ${existing}, ` +
        `orphans ${orphanLen}, maturing ${maturing}, pending ${pending}\n`);

    // CONFIRMED IS NOT THE SAME QUESTION AS FOUND.
    //
    // The chain count is every block this pool ever found that is on the
    // chain. blocks:confirmed:count is the narrower thing the dashboard calls
    // BLOCKS FOUND: the ones that reached maturity and were paid out. The
    // blocks still maturing are on the chain and not yet confirmed, and
    // shareProcessor will increment the counter for each of them when it
    // does confirm -- so seeding with the chain total would count those twice
    // and leave the number permanently high by however many were in flight on
    // the day this ran.
    const confirmedSeed = found - maturing - pending;

    // The chain count is authoritative, with one exception: it cannot be
    // lower than what the list still holds, and if it is, something is wrong
    // with the address or the chain being asked -- so it stops rather than
    // writing a number that would make the dashboard lie in the other
    // direction.
    if (found < listLen) {
        process.stdout.write(
            `\n  REFUSING: the chain says ${found} and redis still holds ` +
            `${listLen} confirmed records.\n  That cannot both be true. ` +
            `Check poolAddress and which network this node is on.\n`);
        await redis.quit();
        process.exit(1);
    }

    process.stdout.write(
        `  confirmed seed = ${found} - ${maturing} maturing - ${pending} ` +
        `pending = ${confirmedSeed}
`);

    if (dryRun) {
        process.stdout.write(`\n  --dry-run: nothing was written\n`);
    } else {
        await redis.set(key('blocks:confirmed:count'), String(found));
        await redis.set(key('blocks:orphaned:count'), String(orphanLen));
        process.stdout.write(
            `\n  wrote blocks:confirmed:count = ${found}\n` +
            `  wrote blocks:orphaned:count  = ${orphanLen}\n`);
    }
    await redis.quit();
})().catch((e) => {
    process.stderr.write(`seed_block_counters: ${e.message}\n`);
    process.exit(1);
});

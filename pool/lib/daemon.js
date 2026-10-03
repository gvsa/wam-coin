'use strict';
// Copyright (c) 2026 The WAM Coin developers
// Distributed under the MIT software license, see COPYING.
//
// JSON-RPC client for wamd, with failover across a list of daemons.
//
// Design notes:
//  * `cmd()` targets the first responsive daemon; `cmdAll()` broadcasts. Block
//    submission uses cmdAll deliberately -- if one node is wedged, a found
//    block must not be lost because of it.
//  * Errors are never swallowed. A pool that hides RPC failures ends up
//    silently mining stale templates.

const http = require('http');
const https = require('https');
const EventEmitter = require('events');

// ---------------------------------------------------------------------------
//  Did the call happen, or do we not know?
// ---------------------------------------------------------------------------
//
//  Every RPC failure is one of two things, and treating them alike is how a
//  pool pays twice. `err.ambiguous` is the distinction, set at the point where
//  the evidence is, and nowhere else: a caller cannot recover it later from an
//  error message.
//
//    definite  the request provably did not execute -- the node refused it,
//              or the connection was never made
//    unknown   it may have executed and the answer was lost
//
//  Socket errors that prove nothing reached the node. ECONNREFUSED and
//  EHOSTUNREACH mean no TCP session existed; ENOTFOUND and EAI_AGAIN mean the
//  name never resolved; ECONNRESET is deliberately NOT here, because a reset
//  can arrive after the request was delivered and acted on.
const NEVER_REACHED_THE_NODE = new Set([
    'ECONNREFUSED', 'EHOSTUNREACH', 'ENETUNREACH', 'ENOTFOUND', 'EAI_AGAIN'
]);

function definite(err) { err.ambiguous = false; return err; }
function unknown(err)  { err.ambiguous = true;  return err; }

class DaemonInterface extends EventEmitter {
    /**
     * @param {Array<{host,port,user,password,ssl?}>} daemons
     * @param {object} logger scoped logger
     */
    constructor(daemons, logger) {
        super();
        if (!Array.isArray(daemons) || daemons.length === 0) {
            throw new Error('at least one daemon must be configured');
        }
        this.daemons = daemons.map((d, i) => ({ ...d, index: i, online: false }));
        this.log = logger;
        this.rpcId = 0;
    }

    /**
     * Probe every daemon; resolves once at least one answers getblockchaininfo.
     *
     * Waits rather than failing on the first attempt. A node that is starting
     * takes a minute or two to load its block index and wallets, and answers
     * ECONNREFUSED or RPC_IN_WARMUP (-28) throughout -- so at boot the pool
     * used to exit immediately, systemd restarted it, and the two raced until
     * the node happened to win. With StartLimitBurst=5 that race can end with
     * systemd giving up permanently, leaving the pool down after every reboot
     * until somebody notices and runs reset-failed by hand.
     *
     * Refusing to run without a node is still right; doing it in under a
     * second was not. A node that is booting appears within a minute, and one
     * that is misconfigured never appears -- only elapsed time tells them
     * apart, so this spends the time and then says which case it was.
     */
    async init(waitSeconds = 180) {
        const deadline = Date.now() + waitSeconds * 1000;
        let attempt = 0;
        let announcedWait = false;

        for (;;) {
            attempt++;
            const results = await Promise.allSettled(
                this.daemons.map((d) => this._request(d, 'getblockchaininfo', []))
            );

            let lastReason = '';
            results.forEach((r, i) => {
                const d = this.daemons[i];
                d.online = r.status === 'fulfilled';
                if (d.online) {
                    const info = r.value;
                    this.log.info(`daemon ${d.host}:${d.port} online -- chain=${info.chain} ` +
                                  `blocks=${info.blocks} difficulty=${info.difficulty}`);
                } else {
                    lastReason = r.reason.message;
                    // Only the first failure is an error; the rest are a wait.
                    if (attempt === 1) {
                        this.log.error(`daemon ${d.host}:${d.port} unreachable: ${lastReason}`);
                    }
                }
            });

            if (this.daemons.some((d) => d.online)) return;

            if (Date.now() >= deadline) {
                throw new Error(
                    `no wamd instance became reachable within ${waitSeconds}s ` +
                    `(${attempt} attempts, last: ${lastReason}) -- refusing to start. ` +
                    'Check that wamd is running and that rpcuser/rpcpassword match.');
            }

            if (!announcedWait) {
                announcedWait = true;
                this.log.warn(`waiting up to ${waitSeconds}s for a daemon ` +
                              '(this is normal while a node loads its block index)');
            }
            await new Promise((r) => setTimeout(r, 3000));
        }
    }

    /**
     * Call the first online daemon, failing over on error.
     *
     * MONEY RPCs DO NOT GET GENERIC FAILOVER. A call that creates a new spend
     * is not safe to repeat anywhere, and "the first daemon threw" does not
     * mean "the first daemon did nothing": a node that receives sendmany,
     * signs, broadcasts, and then loses the connection before answering looks
     * from here exactly like a node that never got the request. Retrying that
     * on the next daemon is a second payment out of the operator's wallet,
     * caused by a dropped TCP connection and nothing else.
     *
     * So for the methods in MONEY_RPCS this fails over only on an error that
     * proves the request was never executed -- the connection was refused, the
     * host did not resolve, authentication was rejected -- and stops dead on
     * anything that leaves the outcome unknown. Delayed pay is the safe
     * failure here; paying twice is the unsafe one.
     *
     * Reported by dang150296 (Urriki1502) on 2026-10-03 as "generic daemon
     * failover for money-moving RPCs", and confirmed against this function.
     */
    async cmd(method, params = []) {
        const ordered = [...this.daemons.filter((d) => d.online),
                         ...this.daemons.filter((d) => !d.online)];
        const guarded = DaemonInterface.MONEY_RPCS.has(method);
        let lastError;
        let anyAmbiguous = false;
        for (const d of ordered) {
            try {
                const result = await this._request(d, method, params);
                if (!d.online) {
                    d.online = true;
                    this.log.info(`daemon ${d.host}:${d.port} recovered`);
                }
                return result;
            } catch (err) {
                lastError = err;
                anyAmbiguous = anyAmbiguous || Boolean(err.ambiguous);
                if (d.online) {
                    d.online = false;
                    this.log.warn(`daemon ${d.host}:${d.port} failed on ${method}: ${err.message}`);
                }
                if (guarded && err.ambiguous) {
                    this.log.error(
                        `${method} on ${d.host}:${d.port} ended with an unknown outcome ` +
                        `(${err.message}). NOT retrying on another daemon: the call may ` +
                        'already have moved coins.');
                    throw err;
                }
            }
        }
        const e = new Error(
            `all daemons failed for ${method}: ${lastError && lastError.message}`);
        // The caller decides what to do about uncertainty, so it has to survive
        // this wrapper. Unknown beats definite when the attempts disagree: one
        // daemon that might have executed the call is enough to make the whole
        // outcome unknown, so this is any-of and not the last one's flag.
        e.ambiguous = anyAmbiguous;
        e.code = lastError && lastError.code;
        throw e;
    }

    /** Broadcast to every daemon and return each outcome. */
    async cmdAll(method, params = []) {
        const settled = await Promise.allSettled(
            this.daemons.map((d) => this._request(d, method, params))
        );
        return settled.map((r, i) => ({
            daemon: `${this.daemons[i].host}:${this.daemons[i].port}`,
            ok: r.status === 'fulfilled',
            result: r.status === 'fulfilled' ? r.value : null,
            error: r.status === 'rejected' ? r.reason.message : null
        }));
    }

    _request(daemon, method, params) {
        return new Promise((resolve, reject) => {
            const body = JSON.stringify({
                jsonrpc: '2.0',
                id: ++this.rpcId,
                method,
                params
            });

            const auth = Buffer.from(`${daemon.user}:${daemon.password}`).toString('base64');
            const transport = daemon.ssl ? https : http;

            // Wallet routing. A node with more than one wallet loaded rejects
            // every wallet RPC sent to '/' with "wallet file not specified",
            // so `sendmany` fails and miners never get paid -- on a node that
            // otherwise looks perfectly healthy. Bitcoin Core serves node RPCs
            // on the wallet endpoint too, so when a wallet is named we can send
            // everything there and keep one code path.
            const path = daemon.wallet
                ? `/wallet/${encodeURIComponent(daemon.wallet)}`
                : '/';

            const req = transport.request({
                host: daemon.host,
                port: daemon.port,
                method: 'POST',
                path,
                headers: {
                    'Content-Type': 'application/json',
                    'Content-Length': Buffer.byteLength(body),
                    'Authorization': `Basic ${auth}`
                },
                timeout: daemon.timeout || 15000
            }, (res) => {
                const chunks = [];
                res.on('data', (c) => chunks.push(c));
                res.on('end', () => {
                    const text = Buffer.concat(chunks).toString('utf8');

                    if (res.statusCode === 401) {
                        // Rejected before the method ran. Definite.
                        return reject(definite(new Error(
                            'RPC authentication failed (401) -- ' +
                            'rpcuser/rpcpassword in config.json do not match wam.conf')));
                    }

                    let parsed;
                    try {
                        parsed = JSON.parse(text);
                    } catch {
                        // Something answered and it was not wamd's JSON-RPC --
                        // a proxy, a load balancer, an error page. Whether the
                        // node behind it ran the method is not knowable here.
                        return reject(unknown(new Error(
                            `non-JSON reply (HTTP ${res.statusCode}): ${text.slice(0, 200)}`)));
                    }

                    if (parsed.error) {
                        // The node parsed the request and refused it. For a
                        // spend that means no transaction exists. Definite.
                        const e = new Error(parsed.error.message || JSON.stringify(parsed.error));
                        e.code = parsed.error.code;
                        return reject(definite(e));
                    }
                    resolve(parsed.result);
                });
            });

            req.on('error', (err) => {
                // NEVER_REACHED_THE_NODE are failures of the connection
                // itself, before any byte of the request could be processed:
                // nothing ran, so a spend did not happen. Everything else --
                // a reset or a broken pipe mid-flight above all -- means the
                // request may have arrived and been executed, and only the
                // answer was lost.
                reject(NEVER_REACHED_THE_NODE.has(err.code)
                    ? definite(err) : unknown(err));
            });
            req.on('timeout', () => {
                // The worst case and the whole reason for this distinction.
                // The node may be signing and broadcasting at this instant.
                req.destroy(unknown(new Error(`RPC timeout calling ${method}`)));
            });
            req.end(body);
        });
    }

    // -----------------------------------------------------------------------
    // Typed convenience wrappers
    // -----------------------------------------------------------------------

    getBlockTemplate() {
        return this.cmd('getblocktemplate', [{ rules: ['segwit'] }]);
    }

    getBlockchainInfo() { return this.cmd('getblockchaininfo'); }
    getMiningInfo()     { return this.cmd('getmininginfo'); }
    getBlockHash(h)     { return this.cmd('getblockhash', [h]); }
    getBlock(hash, v)   { return this.cmd('getblock', v === undefined ? [hash] : [hash, v]); }
    getBalance()        { return this.cmd('getbalance'); }
    validateAddress(a)  { return this.cmd('validateaddress', [a]); }

    /** Submit to every daemon; a block is too valuable to send to just one. */
    async submitBlock(hexData) {
        const results = await this.cmdAll('submitblock', [hexData]);

        // submitblock returns null on success and a reject-reason string
        // otherwise -- an inverted convention that is very easy to misread.
        const accepted = results.filter((r) => r.ok && (r.result === null || r.result === undefined));
        const rejected = results.filter((r) => !accepted.includes(r));

        return {
            accepted: accepted.length > 0,
            reasons: rejected.map((r) => `${r.daemon}: ${r.error || r.result}`),
            results
        };
    }
}

// Calls that create a NEW spend, and so must never be repeated blindly. Not a
// list of wallet RPCs: `getbalance` and `listtransactions` are wallet calls
// and are perfectly safe to retry anywhere. The test is whether running it
// twice can move coins twice.
//
// `sendrawtransaction` is deliberately absent. Rebroadcasting the same signed
// transaction is idempotent by construction -- same txid, same outputs -- and
// is exactly what a recovery path is supposed to do.
DaemonInterface.MONEY_RPCS = new Set([
    'sendmany', 'sendtoaddress', 'sendfrom', 'send', 'sendall'
]);

module.exports = DaemonInterface;

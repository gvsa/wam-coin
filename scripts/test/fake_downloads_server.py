#!/usr/bin/env python3
# Copyright (c) 2026 The WAM Coin developers
# Distributed under the MIT software license, see COPYING.
"""
A wamcoin.org/downloads that misbehaves on purpose.

    python3 scripts/test/fake_downloads_server.py <mode>

Prints the port it bound to on the first line, then serves until killed. Used
by test_release_check_silence.sh to prove that check_release_signed.sh answers
"could not ask" (exit 2) rather than "the release is not signed" (exit 1) when
the server it is reading does not actually answer.

Modes:
    ok                  a normal listing and normal downloads
    index-503           the per-tag listing returns 503 with an error page
    index-200-not-ours  200, but the body is not our listing at all
    download-502        the listing is fine; SHA256SUMS returns 502

It lives in its own file rather than inside a shell string because a Python
program quoted into bash is a Python program nobody can run on its own when it
breaks -- which is what happened on the first attempt at this test.
"""

import http.server
import socketserver
import sys

MODE = sys.argv[1] if len(sys.argv) > 1 else "ok"

GOOD_INDEX = b"""<html><body>
<a href="SHA256SUMS">SHA256SUMS</a>
<a href="SHA256SUMS.asc">SHA256SUMS.asc</a>
<a href="wam-v0.1.11-x86_64-linux-gnu.tar.gz">wam-v0.1.11-x86_64-linux-gnu.tar.gz</a>
</body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path

        # Tag discovery always works: this test is about the per-tag page and
        # the two downloads.
        if path == "/downloads/":
            return self._send(200, b'<a href="v0.1.11/">v0.1.11/</a>')

        if path == "/downloads/v0.1.11/":
            if MODE == "index-503":
                return self._send(
                    503, b"<html><head><title>503 Service Temporarily "
                         b"Unavailable</title></head><body><center><h1>503"
                         b"</h1></center></body></html>")
            if MODE == "index-200-not-ours":
                return self._send(200, b"<html><body>nothing here</body></html>")
            return self._send(200, GOOD_INDEX)

        if path.endswith("SHA256SUMS") or path.endswith("SHA256SUMS.asc"):
            if MODE == "download-502":
                return self._send(
                    502, b"<html><body><h1>502 Bad Gateway</h1></body></html>")
            return self._send(200, b"nothing verifiable\n")

        return self._send(404, b"not found")


socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", 0), Handler) as srv:
    print(srv.server_address[1], flush=True)
    srv.serve_forever()

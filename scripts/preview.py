#!/usr/bin/env python3
from __future__ import annotations

import http.server
import socketserver
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
PORT = 8765


class PreviewServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class PreviewHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SITE), **kwargs)


def main() -> int:
    from scripts.radar_render import build_site

    build_site(ROOT / "content", SITE)
    with PreviewServer(("127.0.0.1", PORT), PreviewHandler) as server:
        print(f"Serving http://127.0.0.1:{PORT}")
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

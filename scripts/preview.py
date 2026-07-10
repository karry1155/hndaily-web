#!/usr/bin/env python3
from __future__ import annotations

import http.server
from functools import partial
import socketserver
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
PORT = 8765


def main() -> int:
    from scripts.radar_render import build_site
    build_site(ROOT / "content", SITE)
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
    with socketserver.TCPServer(("127.0.0.1", PORT), handler) as httpd:
        print(f"Serving http://127.0.0.1:{PORT}")
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

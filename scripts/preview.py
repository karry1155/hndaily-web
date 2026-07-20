#!/usr/bin/env python3
from __future__ import annotations

import http.server
import json
import socketserver
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
PORT = 8765
MAX_GOLD_PAYLOAD_BYTES = 2_000_000


class PreviewServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class PreviewHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SITE), **kwargs)

    def _json_response(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/evaluation-gold":
            self._json_response(404, {"error": "unknown endpoint"})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if not 0 < content_length <= MAX_GOLD_PAYLOAD_BYTES:
                raise ValueError("payload size is invalid")
            content_type = self.headers.get("Content-Type", "")
            if "application/json" not in content_type:
                raise ValueError("Content-Type must be application/json")
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            from scripts.radar_gold_review import ROOT as PROJECT_ROOT, save_gold_payload
            path = save_gold_payload(payload)
            self._json_response(
                200,
                {"status": "saved", "path": str(path.relative_to(PROJECT_ROOT))},
            )
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._json_response(400, {"error": str(exc)})
        except OSError as exc:
            self._json_response(500, {"error": str(exc)})


def main() -> int:
    from scripts.radar_render import build_site
    build_site(ROOT / "content", SITE)
    with PreviewServer(("127.0.0.1", PORT), PreviewHandler) as httpd:
        print(f"Serving http://127.0.0.1:{PORT}")
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

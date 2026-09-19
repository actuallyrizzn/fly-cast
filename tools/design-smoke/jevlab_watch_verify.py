#!/usr/bin/env python3
"""Open the jevlab watch page at desktop and phone widths. Bounded child server.

Run:  /tmp/flycast-pytest/bin/python tools/design-smoke/jevlab_watch_verify.py
"""

from __future__ import annotations

import http.server
import shutil
import socket
import socketserver
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WATCH = ROOT / "tools" / "jevlab" / "watch"
OUT = Path("/tmp/jevlab-watch-smoke")
OUT.mkdir(parents=True, exist_ok=True)


def _serve(directory: Path) -> tuple[socketserver.TCPServer, str]:
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

        def log_message(self, format, *args):  # noqa: A003
            return

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = socketserver.TCPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}/"


def main() -> int:
    from playwright.sync_api import sync_playwright

    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp)
        for name in ("index.html", "watch.js", "watch.css"):
            shutil.copy(WATCH / name, dest / name)
        shutil.copy(WATCH / "fixture-state.json", dest / "state.json")
        server, url = _serve(dest)
        shots = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                for width, height, tag in ((1600, 900, "desktop"), (390, 844, "phone")):
                    page = browser.new_page(viewport={"width": width, "height": height})
                    page.goto(url, wait_until="networkidle")
                    page.wait_for_timeout(500)
                    path = OUT / f"watch-{tag}.png"
                    page.screenshot(path=str(path), full_page=True)
                    shots.append(path)
                    page.close()
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
        for path in shots:
            print(path, path.stat().st_size)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""On-screen overlay — latest guarded line for the laptop.

State lives in a JSON file. A tiny HTTP server serves the page + state.
No Twitch, no stream — local browser only.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

OVERLAY_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Fly Cast</title>
<style>
  :root {
    --bg: #0b1020;
    --fg: #f4f0e6;
    --muted: #9aa3b5;
    --mode: #7ec8e3;
    --warn: #e8b86d;
  }
  * { box-sizing: border-box; }
  html, body {
    margin: 0; height: 100%;
    background: radial-gradient(1200px 600px at 20% 0%, #162038 0%, var(--bg) 55%);
    color: var(--fg);
    font-family: "Segoe UI", "Helvetica Neue", sans-serif;
  }
  .wrap {
    min-height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    padding: 6vh 5vw 8vh;
    gap: 0.75rem;
  }
  .brand {
    letter-spacing: 0.18em;
    text-transform: uppercase;
    font-size: 0.75rem;
    color: var(--muted);
  }
  .line {
    font-size: clamp(1.6rem, 4.5vw, 3.2rem);
    line-height: 1.15;
    font-weight: 600;
    max-width: 28ch;
    text-shadow: 0 2px 24px rgba(0,0,0,0.45);
  }
  .meta {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
    font-size: 0.95rem;
    color: var(--muted);
  }
  .mode { color: var(--mode); font-weight: 600; }
  .status.warn { color: var(--warn); }
  .cues { opacity: 0.85; }
</style>
</head>
<body>
  <div class="wrap">
    <div class="brand">Fly Cast</div>
    <div class="line" id="line">Waiting for events…</div>
    <div class="meta">
      <span class="mode" id="mode">mode: —</span>
      <span class="status" id="status">status: starting</span>
      <span class="cues" id="cues"></span>
    </div>
  </div>
  <script>
    async function tick() {
      try {
        const r = await fetch('/state.json', { cache: 'no-store' });
        if (!r.ok) throw new Error('bad');
        const s = await r.json();
        const line = document.getElementById('line');
        const mode = document.getElementById('mode');
        const status = document.getElementById('status');
        const cues = document.getElementById('cues');
        line.textContent = s.line || '(silent)';
        mode.textContent = 'mode: ' + (s.mode || '—');
        status.textContent = 'status: ' + (s.status || 'unknown');
        status.className = 'status' + (s.status && s.status !== 'live' ? ' warn' : '');
        cues.textContent = s.cues ? ('cues: ' + s.cues) : '';
      } catch (e) {
        document.getElementById('status').textContent = 'status: events-missing';
        document.getElementById('status').className = 'status warn';
      }
    }
    tick();
    setInterval(tick, 400);
  </script>
</body>
</html>
"""


@dataclass
class OverlayState:
    line: str = ""
    mode: str = "silent"  # picked | wrote | silent
    status: str = "events-missing"  # live | events-missing | hands-offline | silent
    cues: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_state_path() -> Path:
    return Path.home() / "fly-cast" / "overlay_state.json"


def write_state(path: Path, state: OverlayState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_state(path: Path) -> OverlayState:
    if not path.is_file():
        return OverlayState()
    data = json.loads(path.read_text(encoding="utf-8"))
    return OverlayState(
        line=str(data.get("line", "")),
        mode=str(data.get("mode", "silent")),
        status=str(data.get("status", "events-missing")),
        cues=str(data.get("cues", "")),
    )


def make_handler(state_path: Path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:  # quiet
            return

        def do_GET(self) -> None:  # noqa: N802
            if self.path in ("/", "/index.html"):
                body = OVERLAY_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path.startswith("/state.json"):
                st = read_state(state_path)
                body = json.dumps(st.to_dict()).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(404)
            self.end_headers()

    return Handler


@dataclass
class OverlayServer:
    state_path: Path
    host: str = "127.0.0.1"
    port: int = 0
    _httpd: ThreadingHTTPServer | None = None
    _thread: threading.Thread | None = None

    def start(self) -> tuple[str, int]:
        handler = make_handler(self.state_path)
        self._httpd = ThreadingHTTPServer((self.host, self.port), handler)
        host, port = self._httpd.server_address[:2]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return str(host), int(port)

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None

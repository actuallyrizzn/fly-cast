#!/usr/bin/env python3
"""Design smoke: overlay at phone + desktop widths. Ephemeral server only.

Run:  . .venv/bin/activate && python tools/design-smoke/verify.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

OUT = ROOT / "artifacts" / "overlay-smoke"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    from playwright.sync_api import sync_playwright

    from flycast.overlay import OverlayServer, OverlayState, write_state

    state_path = OUT / "state.json"
    write_state(
        state_path,
        OverlayState(
            line="Streak going.",
            mode="picked",
            status="live",
            cues="STREAK 8",
        ),
    )
    srv = OverlayServer(state_path=state_path, host="127.0.0.1", port=0)
    host, port = srv.start()
    url = f"http://{host}:{port}/"
    shots: list[Path] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            for name, w, h in (("mobile", 390, 844), ("desktop", 1280, 800)):
                page = browser.new_page(viewport={"width": w, "height": h})
                page.goto(url, wait_until="commit", timeout=15000)
                page.wait_for_selector("#line")
                page.wait_for_function(
                    "() => document.getElementById('line').textContent && document.getElementById('line').textContent !== 'Waiting for events…'"
                )
                path = OUT / f"overlay-{name}.png"
                page.screenshot(path=str(path), full_page=True)
                shots.append(path)
                page.close()
            # events-missing status
            write_state(
                state_path,
                OverlayState(line="", mode="silent", status="events-missing", cues=""),
            )
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(url, wait_until="commit", timeout=15000)
            page.wait_for_function(
                "() => document.getElementById('status').textContent.includes('events-missing')"
            )
            path = OUT / "overlay-events-missing.png"
            page.screenshot(path=str(path), full_page=True)
            shots.append(path)
            page.close()
            browser.close()
    finally:
        srv.stop()

    for pth in shots:
        assert pth.is_file() and pth.stat().st_size > 1000, pth
        print(f"ok {pth}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

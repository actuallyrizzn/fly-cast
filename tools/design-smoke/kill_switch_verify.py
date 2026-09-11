#!/usr/bin/env python3
"""Prove STOP file silences guarded output and overlay.

Run:  . .venv/bin/activate && python tools/design-smoke/kill_switch_verify.py
Writes screenshots under artifacts/overlay-smoke/kill-*.png
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

    from flycast.guard import Guard
    from flycast.overlay import OverlayServer, OverlayState, write_state

    stop = OUT / "STOP"
    if stop.exists():
        stop.unlink()
    state_path = OUT / "kill-state.json"
    log_path = OUT / "kill-lines.jsonl"
    if log_path.exists():
        log_path.unlink()

    guard = Guard(stop_path=stop, log_path=log_path)
    r1 = guard.check("On time.", cues="HIT STRUM", mode="picked", destination="overlay")
    assert r1.allowed, r1
    write_state(
        state_path,
        OverlayState(line=r1.filtered, mode=r1.mode, status="live", cues="HIT STRUM"),
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
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(url, wait_until="commit", timeout=15000)
            page.wait_for_function("() => document.getElementById('line').textContent.includes('On time')")
            before = OUT / "kill-before.png"
            page.screenshot(path=str(before), full_page=True)
            shots.append(before)

            stop.write_text("1\n", encoding="utf-8")
            r2 = guard.check("Streak going.", cues="STREAK 8", mode="picked", destination="overlay")
            assert not r2.allowed and r2.reason == "kill_switch", r2
            write_state(
                state_path,
                OverlayState(line="", mode="silent", status="silent", cues="STREAK 8"),
            )
            page.wait_for_function(
                "() => document.getElementById('status').textContent.includes('silent')"
            )
            after = OUT / "kill-after.png"
            page.screenshot(path=str(after), full_page=True)
            shots.append(after)
            browser.close()
    finally:
        srv.stop()
        if stop.exists():
            stop.unlink()

    for pth in shots:
        assert pth.is_file() and pth.stat().st_size > 1000, pth
        print(f"ok {pth}")
    print("PASS kill_switch → overlay silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

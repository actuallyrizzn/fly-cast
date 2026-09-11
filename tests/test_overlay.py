"""Unit tests for overlay state + HTTP."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from flycast.overlay import OverlayServer, OverlayState, read_state, write_state


def test_write_read_state(tmp_path: Path):
    path = tmp_path / "state.json"
    write_state(path, OverlayState(line="Missed it.", mode="picked", status="live", cues="MISS"))
    st = read_state(path)
    assert st.line == "Missed it."
    assert st.mode == "picked"
    assert st.status == "live"


def test_read_missing(tmp_path: Path):
    st = read_state(tmp_path / "nope.json")
    assert st.status == "events-missing"
    assert st.mode == "silent"


def test_overlay_http(tmp_path: Path):
    path = tmp_path / "state.json"
    write_state(path, OverlayState(line="On time.", mode="picked", status="live", cues="HIT STRUM"))
    srv = OverlayServer(state_path=path, host="127.0.0.1", port=0)
    host, port = srv.start()
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/") as r:
            html = r.read().decode("utf-8")
        assert "Fly Cast" in html
        with urllib.request.urlopen(f"http://{host}:{port}/state.json") as r:
            data = json.loads(r.read().decode("utf-8"))
        assert data["line"] == "On time."
        assert data["mode"] == "picked"
    finally:
        srv.stop()

"""Live mouth → overlay tests."""

from __future__ import annotations

import json
from pathlib import Path

from flycast.cli import main
from flycast.live import run_follow, run_once
from flycast.overlay import read_state

ROOT = Path(__file__).resolve().parents[1]
EVENTS = ROOT / "examples" / "fly_hero" / "fixtures" / "events_midtempo.jsonl"


def test_run_once_updates_overlay(tmp_path: Path):
    state = tmp_path / "state.json"
    log = tmp_path / "lines.jsonl"
    lines = run_once(
        EVENTS,
        state_path=state,
        stop_path=tmp_path / "STOP",
        line_log=log,
    )
    assert lines
    st = read_state(state)
    assert st.status == "live"
    assert st.mode == "picked"
    assert st.line
    assert log.is_file()
    row = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert row["destination"] == "overlay"


def test_run_follow_appends(tmp_path: Path):
    events = tmp_path / "events.jsonl"
    events.write_text(
        '{"t":1.0,"cue":"SONG_START","detail":""}\n'
        '{"t":2.0,"cue":"MISS","detail":"green"}\n',
        encoding="utf-8",
    )
    state = tmp_path / "state.json"
    lines = run_follow(
        events,
        state_path=state,
        stop_path=tmp_path / "STOP",
        max_seconds=3.0,
        print_lines=False,
        from_start=True,
    )
    assert any("MISS" in ln for ln in lines), lines
    assert read_state(state).status == "live"


def test_cli_live_once(tmp_path: Path):
    state = tmp_path / "state.json"
    assert (
        main(
            [
                "live",
                str(EVENTS),
                "--state-path",
                str(state),
                "--stop-path",
                str(tmp_path / "STOP"),
                "--line-log",
                str(tmp_path / "log.jsonl"),
            ]
        )
        == 0
    )
    assert read_state(state).line


def test_run_once_kill_switch(tmp_path: Path):
    stop = tmp_path / "STOP"
    stop.write_text("1\n", encoding="utf-8")
    state = tmp_path / "state.json"
    lines = run_once(
        EVENTS,
        state_path=state,
        stop_path=stop,
    )
    assert lines
    assert all("[silent]" in ln and "kill_switch" in ln for ln in lines), lines
    assert read_state(state).mode == "silent"

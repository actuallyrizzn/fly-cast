"""Replay recorded Fly Hero events into mouth reactions."""

from __future__ import annotations

from pathlib import Path

from flycast.replay import replay

ROOT = Path(__file__).resolve().parents[1]


def test_replay_fixture_produces_lines():
    lines = replay(ROOT / "fixtures" / "events_midtempo.jsonl")
    assert lines
    assert any("SONG_START" in ln for ln in lines)
    assert any("[picked]" in ln for ln in lines)


def test_replay_missing_idle():
    lines = replay(Path("/no/such/events.jsonl"))
    assert "idle" in lines[0]

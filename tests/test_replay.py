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


def test_replay_with_guard(tmp_path: Path):
    from flycast.guard import Guard

    g = Guard(stop_path=tmp_path / "STOP", log_path=tmp_path / "lines.jsonl")
    lines = replay(ROOT / "fixtures" / "events_midtempo.jsonl", guard=g)
    assert lines
    assert any("[picked]" in ln for ln in lines)
    assert (tmp_path / "lines.jsonl").is_file()


def test_replay_kill_switch_silences(tmp_path: Path):
    from flycast.guard import Guard

    stop = tmp_path / "STOP"
    stop.write_text("1\n", encoding="utf-8")
    g = Guard(stop_path=stop)
    lines = replay(ROOT / "fixtures" / "events_midtempo.jsonl", guard=g)
    assert lines
    assert all("[silent]" in ln for ln in lines)

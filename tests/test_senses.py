"""Fly Cast senses — parse / idle when missing."""

from __future__ import annotations

from pathlib import Path

from flycast.senses import load_events, parse_line

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "events_midtempo.jsonl"


def test_load_fixture():
    events = load_events(FIXTURE)
    cues = [e.cue for e in events]
    assert cues[0] == "SONG_START"
    assert "SCORE" in cues
    assert events[-1].as_prompt_event().cue == "SCORE"


def test_missing_file():
    assert load_events(Path("/no/such/events.jsonl")) == []


def test_parse_bad():
    assert parse_line("") is None
    assert parse_line('{"t":1}') is None

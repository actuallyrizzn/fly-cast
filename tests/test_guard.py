"""Table-driven safety guard tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from flycast.guard import Guard

CASES = [
    # id, text, kwargs overrides, expected allowed, reason_substr
    ("ok_plain", "Missed it.", {}, True, "ok"),
    ("strip_url", "see https://evil.example/x now", {}, True, "ok"),
    ("block_suicide", "consider suicide later", {}, False, "blocklist"),
    ("block_kys", "go kys please", {}, False, "blocklist"),
    ("block_porn", "free porn here", {}, False, "blocklist"),
    ("block_slur", "you nigger", {}, False, "blocklist"),
    ("empty", "   ", {}, False, "empty"),
    ("url_only", "https://spam.example/path", {}, False, "empty"),
    ("extra_block", "hello BADTOKEN world", {"extra_blocklist": ("badtoken",)}, False, "blocklist"),
]


@pytest.mark.parametrize(
    "case_id,text,overrides,allowed,reason_sub",
    CASES,
    ids=[c[0] for c in CASES],
)
def test_guard_table(tmp_path: Path, case_id, text, overrides, allowed, reason_sub):
    g = Guard(
        stop_path=tmp_path / "STOP",
        log_path=tmp_path / "lines.jsonl",
        max_len=120,
        min_interval_s=0.0,
        **overrides,
    )
    result = g.check(text, cues="MISS green", mode="picked", destination="overlay")
    assert result.allowed is allowed
    assert reason_sub in result.reason
    if allowed:
        assert "http" not in result.filtered.lower()
        assert "www." not in result.filtered.lower()
        assert result.filtered
    else:
        assert result.filtered == ""
        assert result.mode == "silent"


def test_kill_switch(tmp_path: Path):
    stop = tmp_path / "STOP"
    g = Guard(stop_path=stop, log_path=tmp_path / "log.jsonl")
    assert g.check("On time.").allowed
    stop.write_text("1\n", encoding="utf-8")
    r = g.check("On time.")
    assert not r.allowed
    assert r.reason == "kill_switch"


def test_dedupe_recent(tmp_path: Path):
    g = Guard(stop_path=tmp_path / "nope", recent_window=3, dedupe_ttl_s=0.0)
    assert g.check("Streak going.", now=1.0).allowed
    r2 = g.check("Streak going.", now=1.1)
    assert not r2.allowed
    assert r2.reason == "dedupe"
    assert g.check("That's a wrap.", now=1.2).allowed


def test_dedupe_ttl_expires(tmp_path: Path):
    g = Guard(stop_path=tmp_path / "nope", dedupe_ttl_s=2.0)
    assert g.check("On time.", now=10.0).allowed
    assert not g.check("On time.", now=10.5).allowed
    assert g.check("On time.", now=12.5).allowed


def test_length_cap(tmp_path: Path):
    g = Guard(stop_path=tmp_path / "nope", max_len=20)
    long = "word " * 40
    r = g.check(long)
    assert r.allowed
    assert len(r.filtered) <= 20


def test_rate_limit(tmp_path: Path):
    g = Guard(stop_path=tmp_path / "nope", min_interval_s=1.0)
    assert g.check("a", now=100.0).allowed
    r = g.check("b", now=100.2)
    assert not r.allowed
    assert r.reason == "rate_limit"
    assert g.check("c", now=101.5).allowed


def test_line_log_fields(tmp_path: Path):
    log = tmp_path / "lines.jsonl"
    g = Guard(stop_path=tmp_path / "STOP", log_path=log)
    g.check("Song starting.", cues="SONG_START", mode="picked", destination="overlay")
    g.check("consider suicide", cues="CHAT", mode="wrote", destination="overlay")
    rows = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln]
    assert len(rows) == 2
    import json

    first = json.loads(rows[0])
    for key in ("time", "cues", "mode", "raw", "filtered", "destination", "allowed", "reason"):
        assert key in first
    assert first["allowed"] is True
    assert first["filtered"] == "Song starting."
    second = json.loads(rows[1])
    assert second["allowed"] is False
    assert second["destination"] == "none"

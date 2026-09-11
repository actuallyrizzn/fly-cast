"""Chat / social stub tests — no network."""

from __future__ import annotations

from pathlib import Path

from flycast.external import load_chat_fixture, reply_to_message
from flycast.guard import Guard
from flycast.prompt import Event, build_prompt

ROOT = Path(__file__).resolve().parents[1]


def test_build_prompt_chat_message():
    text, cue = build_prompt([Event("MISS", "green")], message="hello chat")
    assert "CHAT hello chat" in text
    assert cue


def test_chat_fixture_guarded(tmp_path: Path):
    rows = load_chat_fixture(ROOT / "fixtures" / "chat_social.tsv")
    assert any(c == "CHAT" for c, _ in rows)
    assert any(c == "SOCIAL" for c, _ in rows)
    g = Guard(stop_path=tmp_path / "STOP", log_path=tmp_path / "log.jsonl")
    replies = [reply_to_message(c, m, guard=g, approve_mode=True) for c, m in rows]
    assert replies
    assert all(r.approve_mode for r in replies)
    assert any(r.allowed for r in replies)


def test_chat_url_stripped(tmp_path: Path):
    g = Guard(stop_path=tmp_path / "STOP")
    # poison bank path not needed — guard strips if model emits URL
    r = g.check("see https://evil.example/x now", cues="CHAT spam", mode="wrote")
    assert r.allowed
    assert "http" not in r.filtered.lower()

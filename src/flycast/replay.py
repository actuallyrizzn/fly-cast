"""Replay a recorded events.jsonl into picked reactions (CI-friendly)."""

from __future__ import annotations

from pathlib import Path

from flycast.bank import load_bank
from flycast.react import demo_brain, react
from flycast.senses import load_events

DEFAULT_BANK = Path(__file__).resolve().parent.parent.parent / "fixtures" / "reply_bank.tsv"


def replay(events_path: Path, *, bank_path: Path | None = None) -> list[str]:
    events = load_events(events_path)
    if not events:
        return ["(no events — mouth idle)"]
    brain, tok = demo_brain()
    bank = load_bank(bank_path) if bank_path else load_bank(DEFAULT_BANK)
    lines: list[str] = []
    interesting = {
        "MISS",
        "STREAK",
        "OVERSTRUM",
        "SONG_START",
        "SONG_END",
        "SCORE",
        "CHAT",
        "SOCIAL",
    }
    window = []
    for ev in events:
        window.append(ev.as_prompt_event())
        window = window[-6:]
        if ev.cue not in interesting and not (ev.cue == "HIT" and ev.detail == "STRUM"):
            continue
        result = react(brain, tok, window, bank=bank)
        detail = f" {ev.detail}" if ev.detail else ""
        lines.append(f"{ev.cue}{detail} → [{result.mode}] {result.text}")
    return lines

"""Replay a recorded events.jsonl into picked reactions (CI-friendly)."""

from __future__ import annotations

from pathlib import Path

from flycast.bank import load_bank
from flycast.guard import Guard
from flycast.react import demo_brain, react
from flycast.senses import load_events

DEFAULT_BANK = Path(__file__).resolve().parent.parent.parent / "fixtures" / "reply_bank.tsv"


def replay(
    events_path: Path,
    *,
    bank_path: Path | None = None,
    guard: Guard | None = None,
) -> list[str]:
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
        cues = f"{ev.cue}{detail}".strip()
        if guard is not None:
            g = guard.check(
                result.text,
                cues=cues,
                mode=result.mode,
                destination="replay",
            )
            if not g.allowed:
                lines.append(f"{cues} → [silent] ({g.reason})")
                continue
            lines.append(f"{cues} → [{g.mode}] {g.filtered}")
        else:
            lines.append(f"{cues} → [{result.mode}] {result.text}")
    return lines

"""Replay a recorded events.jsonl into picked reactions (CI-friendly)."""

from __future__ import annotations

from pathlib import Path

from flycast.bank import load_bank
from flycast.guard import Guard
from flycast.profile import Profile, default_profile
from flycast.react import demo_brain, react
from flycast.senses import load_events


def replay(
    events_path: Path,
    *,
    bank_path: Path | None = None,
    guard: Guard | None = None,
    profile: Profile | None = None,
) -> list[str]:
    profile = profile or default_profile()
    events = load_events(events_path)
    if not events:
        return ["(no events — mouth idle)"]
    brain, tok = demo_brain()
    bank = load_bank(bank_path) if bank_path else load_bank(profile.bank_path)
    lines: list[str] = []
    window = []
    for ev in events:
        window.append(ev.as_prompt_event())
        window = window[-6:]
        if not profile.should_react(ev.cue, ev.detail):
            continue
        result = react(brain, tok, window, bank=bank, profile=profile)
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

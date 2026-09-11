"""Gameplay / chat cue tokens → prompt strings for generate/pick."""

from __future__ import annotations

from dataclasses import dataclass


CUES = frozenset(
    {
        "HIT",
        "MISS",
        "STREAK",
        "OVERSTRUM",
        "SONG_START",
        "SONG_END",
        "SCORE",
        "CHAT",
        "SOCIAL",
        "LANE_G",
        "LANE_R",
        "LANE_Y",
        "LANE_B",
        "LANE_O",
    }
)


@dataclass(frozen=True)
class Event:
    cue: str
    detail: str = ""


def normalize_cue(cue: str) -> str:
    text = cue.strip().upper().replace(" ", "_")
    if text.startswith("STREAK_"):
        return "STREAK"
    if text.startswith("SCORE_"):
        return "SCORE"
    return text


def build_prompt(events: list[Event], *, message: str = "") -> tuple[str, str]:
    """Return (prompt_text, primary_cue) for picker/generate.

    primary_cue is the latest event cue (for bank lookup).
    """
    if not events and not message:
        raise ValueError("need events or message")
    parts: list[str] = []
    primary = "CHAT" if message and not events else ""
    for ev in events[-8:]:
        cue = normalize_cue(ev.cue)
        if cue not in CUES and not cue.startswith("STREAK") and not cue.startswith("SCORE"):
            cue = "HIT" if cue == "NOTE" else cue
        primary = cue if cue in CUES else primary or "HIT"
        chunk = cue if not ev.detail else f"{cue} {ev.detail}"
        parts.append(chunk)
    if message:
        parts.append(f"CHAT {message.strip()}")
        if not primary:
            primary = "CHAT"
    return " | ".join(parts), primary or "HIT"

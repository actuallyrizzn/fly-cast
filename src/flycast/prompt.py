"""Gameplay / chat cue tokens → prompt strings for generate/pick."""

from __future__ import annotations

from dataclasses import dataclass


# Minimal built-in set for unit tests when no profile is loaded.
DEFAULT_CUES = frozenset(
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
        "EVENT",
        "NOTE",
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


def build_prompt(
    events: list[Event],
    *,
    message: str = "",
    known_cues: frozenset[str] | None = None,
) -> tuple[str, str]:
    """Return (prompt_text, primary_cue) for picker/generate.

    primary_cue is the latest event cue (for bank lookup).
    Unknown cues are kept as-normalized so product profiles can extend freely.
    """
    if not events and not message:
        raise ValueError("need events or message")
    known = known_cues if known_cues is not None else DEFAULT_CUES
    parts: list[str] = []
    primary = "CHAT" if message and not events else ""
    for ev in events[-8:]:
        cue = normalize_cue(ev.cue)
        if cue == "NOTE":
            cue = "HIT"
        if known and cue not in known and not cue.startswith("STREAK") and not cue.startswith("SCORE"):
            # Still emit the cue text; bank may fall back to HIT.
            pass
        primary = cue
        chunk = cue if not ev.detail else f"{cue} {ev.detail}"
        parts.append(chunk)
    if message:
        parts.append(f"CHAT {message.strip()}")
        if not primary:
            primary = "CHAT"
    return " | ".join(parts), primary or "HIT"

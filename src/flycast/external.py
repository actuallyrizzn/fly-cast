"""Chat / social stub path — fixtures only, no platform accounts.

Future public posting must set approve_mode=True and wait for a human.
Product cue names (CHAT/SOCIAL) come from the active profile's bank.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from flycast.bank import load_bank
from flycast.guard import Guard
from flycast.profile import default_profile
from flycast.prompt import Event, build_prompt
from flycast.react import demo_brain, react


@dataclass(frozen=True)
class ExternalReply:
    cue: str
    text: str
    mode: str
    allowed: bool
    reason: str
    approve_mode: bool


def reply_to_message(
    cue: str,
    message: str,
    *,
    guard: Guard | None = None,
    bank_path: Path | None = None,
    approve_mode: bool = True,
) -> ExternalReply:
    """Build prompt + pick a bank reply + run guard. Never posts anywhere."""
    cue_u = cue.strip().upper()
    profile = default_profile()
    if profile.known_cues and cue_u not in profile.known_cues:
        raise ValueError(f"cue not in profile known set: {cue_u}")
    brain, tok = demo_brain()
    bank = load_bank(bank_path) if bank_path else load_bank(profile.bank_path)
    events = [Event(cue_u, message[:80])]
    _prompt, _primary = build_prompt(
        events,
        message=message if cue_u == "CHAT" else "",
        known_cues=profile.known_cues or None,
    )
    result = react(brain, tok, events, bank=bank, profile=profile)
    g = (guard or Guard(stop_path=Path("/tmp/flycast-no-stop"))).check(
        result.text,
        cues=f"{cue_u} {message[:40]}",
        mode=result.mode,
        destination="approve-queue" if approve_mode else "overlay",
    )
    return ExternalReply(
        cue=cue_u,
        text=g.filtered if g.allowed else "",
        mode=g.mode if g.allowed else "silent",
        allowed=g.allowed,
        reason=g.reason,
        approve_mode=approve_mode,
    )


def load_chat_fixture(path: Path) -> list[tuple[str, str]]:
    """Load TSV: CUE <tab> message text."""
    rows: list[tuple[str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        cue, msg = line.split("\t", 1)
        rows.append((cue.strip().upper(), msg.strip()))
    return rows

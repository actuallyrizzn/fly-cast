"""Follow an events.jsonl and push guarded lines to the overlay state file."""

from __future__ import annotations

import time
from pathlib import Path

from flycast.bank import load_bank
from flycast.guard import Guard
from flycast.overlay import OverlayState, default_state_path, write_state
from flycast.react import demo_brain, react
from flycast.replay import DEFAULT_BANK
from flycast.senses import LoggedEvent, follow_events, load_events

INTERESTING = {
    "MISS",
    "STREAK",
    "OVERSTRUM",
    "SONG_START",
    "SONG_END",
    "SCORE",
    "CHAT",
    "SOCIAL",
}


def _should_react(ev: LoggedEvent) -> bool:
    return ev.cue in INTERESTING or (ev.cue == "HIT" and ev.detail == "STRUM")


def process_event(
    ev: LoggedEvent,
    *,
    window: list,
    brain,
    tok,
    bank,
    guard: Guard,
    state_path: Path,
) -> str | None:
    window.append(ev.as_prompt_event())
    del window[:-6]
    if not _should_react(ev):
        return None
    detail = f" {ev.detail}" if ev.detail else ""
    cues = f"{ev.cue}{detail}".strip()
    result = react(brain, tok, window, bank=bank)
    g = guard.check(result.text, cues=cues, mode=result.mode, destination="overlay")
    if not g.allowed:
        write_state(
            state_path,
            OverlayState(line="", mode="silent", status="silent", cues=cues),
        )
        return f"{cues} → [silent] ({g.reason})"
    write_state(
        state_path,
        OverlayState(line=g.filtered, mode=g.mode, status="live", cues=cues),
    )
    return f"{cues} → [{g.mode}] {g.filtered}"


def run_once(
    events_path: Path,
    *,
    bank_path: Path | None = None,
    state_path: Path | None = None,
    stop_path: Path | None = None,
    line_log: Path | None = None,
) -> list[str]:
    """Replay existing events into overlay (no follow)."""
    state_path = state_path or default_state_path()
    stop_path = stop_path or (Path.home() / "fly-cast" / "STOP")
    guard = Guard(stop_path=stop_path, log_path=line_log)
    brain, tok = demo_brain()
    bank = load_bank(bank_path) if bank_path else load_bank(DEFAULT_BANK)
    window: list = []
    lines: list[str] = []
    write_state(
        state_path,
        OverlayState(line="", mode="silent", status="events-missing", cues=""),
    )
    events = load_events(events_path)
    if not events:
        return lines
    for ev in events:
        out = process_event(
            ev,
            window=window,
            brain=brain,
            tok=tok,
            bank=bank,
            guard=guard,
            state_path=state_path,
        )
        if out:
            lines.append(out)
    return lines


def run_follow(
    events_path: Path,
    *,
    bank_path: Path | None = None,
    state_path: Path | None = None,
    stop_path: Path | None = None,
    line_log: Path | None = None,
    max_seconds: float | None = None,
    print_lines: bool = True,
    from_start: bool = False,
) -> list[str]:
    """Tail events file and update overlay until max_seconds elapses."""
    state_path = state_path or default_state_path()
    stop_path = stop_path or (Path.home() / "fly-cast" / "STOP")
    guard = Guard(stop_path=stop_path, log_path=line_log)
    brain, tok = demo_brain()
    bank = load_bank(bank_path) if bank_path else load_bank(DEFAULT_BANK)
    window: list = []
    lines: list[str] = []
    write_state(
        state_path,
        OverlayState(line="", mode="silent", status="events-missing", cues=""),
    )
    started = time.time()
    for item in follow_events(events_path, from_start=from_start):
        if max_seconds is not None and (time.time() - started) >= max_seconds:
            break
        if item is None:
            if not events_path.is_file():
                write_state(
                    state_path,
                    OverlayState(line="", mode="silent", status="events-missing", cues=""),
                )
            continue
        out = process_event(
            item,
            window=window,
            brain=brain,
            tok=tok,
            bank=bank,
            guard=guard,
            state_path=state_path,
        )
        if out:
            lines.append(out)
            if print_lines:
                print(out, flush=True)
    return lines

"""Follow an events.jsonl and push guarded lines to the overlay state file."""

from __future__ import annotations

import time
from pathlib import Path

from flycast.bank import load_bank
from flycast.guard import Guard
from flycast.overlay import OverlayState, default_state_path, write_state
from flycast.profile import Profile, default_profile
from flycast.react import demo_brain, react
from flycast.senses import LoggedEvent, follow_events, load_events


def process_event(
    ev: LoggedEvent,
    *,
    window: list,
    brain,
    tok,
    bank,
    guard: Guard,
    state_path: Path,
    profile: Profile,
    last_hit_t: float = 0.0,
    hit_min_interval_s: float = 5.0,
    freewrite: bool = False,
) -> tuple[str | None, float]:
    window.append(ev.as_prompt_event())
    del window[:-6]
    if not profile.should_react(ev.cue, ev.detail):
        return None, last_hit_t
    cue_u = ev.cue.strip().upper()
    if (
        cue_u == "HIT"
        and hit_min_interval_s > 0
        and last_hit_t > 0
        and (ev.t - last_hit_t) < hit_min_interval_s
    ):
        return None, last_hit_t

    detail = f" {ev.detail}" if ev.detail else ""
    cues = f"{ev.cue}{detail}".strip()
    if freewrite:
        from flycast.write import freewrite as freewrite_fn

        result = freewrite_fn(brain, tok, window, profile=profile)
    else:
        result = react(brain, tok, window, bank=bank, profile=profile)
    g = guard.check(
        result.text,
        cues=cues,
        mode=result.mode,
        destination="overlay",
        now=float(ev.t) if ev.t else None,
    )
    new_hit_t = float(ev.t) if cue_u == "HIT" else last_hit_t
    if not g.allowed:
        write_state(
            state_path,
            OverlayState(line="", mode="silent", status="silent", cues=cues),
        )
        return f"{cues} → [silent] ({g.reason})", new_hit_t
    write_state(
        state_path,
        OverlayState(line=g.filtered, mode=g.mode, status="live", cues=cues),
    )
    return f"{cues} → [{g.mode}] {g.filtered}", new_hit_t


def run_once(
    events_path: Path,
    *,
    bank_path: Path | None = None,
    state_path: Path | None = None,
    stop_path: Path | None = None,
    line_log: Path | None = None,
    profile: Profile | None = None,
    freewrite: bool = False,
    checkpoint: Path | None = None,
) -> list[str]:
    """Replay existing events into overlay (no follow)."""
    profile = profile or default_profile()
    state_path = state_path or default_state_path()
    stop_path = stop_path or (Path.home() / "fly-cast" / "STOP")
    guard = Guard(stop_path=stop_path, log_path=line_log, dedupe_ttl_s=2.0)
    if freewrite:
        from flycast.write import load_writer

        brain, tok, _ckpt = load_writer(checkpoint)
        bank = {}
    else:
        brain, tok = demo_brain()
        bank = load_bank(bank_path) if bank_path else load_bank(profile.bank_path)
    window: list = []
    lines: list[str] = []
    write_state(
        state_path,
        OverlayState(line="", mode="silent", status="events-missing", cues=""),
    )
    events = load_events(events_path)
    if not events:
        return lines
    last_hit_t = 0.0
    for ev in events:
        out, last_hit_t = process_event(
            ev,
            window=window,
            brain=brain,
            tok=tok,
            bank=bank,
            guard=guard,
            state_path=state_path,
            profile=profile,
            last_hit_t=last_hit_t,
            freewrite=freewrite,
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
    profile: Profile | None = None,
    freewrite: bool = False,
    checkpoint: Path | None = None,
) -> list[str]:
    """Tail events file and update overlay until max_seconds elapses."""
    profile = profile or default_profile()
    state_path = state_path or default_state_path()
    stop_path = stop_path or (Path.home() / "fly-cast" / "STOP")
    guard = Guard(stop_path=stop_path, log_path=line_log, dedupe_ttl_s=2.0)
    if freewrite:
        from flycast.write import load_writer

        brain, tok, _ckpt = load_writer(checkpoint)
        bank = {}
    else:
        brain, tok = demo_brain()
        bank = load_bank(bank_path) if bank_path else load_bank(profile.bank_path)
    window: list = []
    lines: list[str] = []
    write_state(
        state_path,
        OverlayState(line="", mode="silent", status="events-missing", cues=""),
    )
    started = time.time()
    last_hit_t = 0.0
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
        out, last_hit_t = process_event(
            item,
            window=window,
            brain=brain,
            tok=tok,
            bank=bank,
            guard=guard,
            state_path=state_path,
            profile=profile,
            last_hit_t=last_hit_t,
            freewrite=freewrite,
        )
        if out:
            lines.append(out)
            if print_lines:
                print(out, flush=True)
    return lines

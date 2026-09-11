"""Parse events.jsonl for the mouth (generic schema).

Each line is JSON: ``{"t": <float>, "cue": "<NAME>", "detail": "<optional>"}``.
Product profiles decide which cues are interesting; this module only parses.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from flycast.prompt import Event


@dataclass(frozen=True)
class LoggedEvent:
    t: float
    cue: str
    detail: str = ""
    raw: dict | None = None

    def as_prompt_event(self) -> Event:
        return Event(cue=self.cue, detail=self.detail)


def parse_line(line: str) -> LoggedEvent | None:
    text = line.strip()
    if not text:
        return None
    data = json.loads(text)
    cue = str(data.get("cue", "")).upper()
    if not cue:
        return None
    detail = str(data.get("detail", "") or "")
    return LoggedEvent(t=float(data.get("t", 0.0)), cue=cue, detail=detail, raw=data)


def load_events(path: Path) -> list[LoggedEvent]:
    if not path.is_file():
        return []
    out: list[LoggedEvent] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        ev = parse_line(line)
        if ev is not None:
            out.append(ev)
    return out


def follow_events(path: Path, *, idle_sleep: float = 0.05, from_start: bool = False):
    """Yield new events as they are appended. Idle forever if file missing.

    By default seeks to EOF (live session). Pass from_start=True to read existing lines first.
    """
    while not path.is_file():
        yield None  # caller can show hands-offline / waiting
        time.sleep(max(idle_sleep, 0.2))
    with path.open("r", encoding="utf-8") as handle:
        if not from_start:
            handle.seek(0, 2)
        while True:
            line = handle.readline()
            if not line:
                yield None
                time.sleep(idle_sleep)
                continue
            ev = parse_line(line)
            if ev is not None:
                yield ev

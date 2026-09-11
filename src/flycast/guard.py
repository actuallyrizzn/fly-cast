"""Safety guard — filter, rate limit, kill switch, line log.

Every outbound mouth line must pass through here before overlay / stdout.
No shell, no tools, no secrets: pure string checks + file existence.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
# Conservative starter blocklist. Expand via Guard(extra_blocklist=...).
# Tests inject synthetic tokens; production can load a larger file later.
DEFAULT_BLOCKLIST: tuple[str, ...] = (
    # self-harm / suicide
    "kill myself",
    "kys",
    "suicide",
    "self-harm",
    "self harm",
    # sexual
    "porn",
    "nsfw",
    "onlyfans",
    # slurs / hate (minimal seed — not exhaustive)
    "nigger",
    "faggot",
    "retard",
)

_URL_RE = re.compile(
    r"(?i)\b(?:https?://|www\.)[^\s<>\"]+|mailto:[^\s<>\"]+",
)


@dataclass(frozen=True)
class GuardResult:
    allowed: bool
    raw: str
    filtered: str
    reason: str
    mode: str = "picked"
    cues: str = ""
    destination: str = "overlay"


@dataclass
class Guard:
    """Stateful outbound filter for mouth lines."""

    stop_path: Path = field(default_factory=lambda: Path.home() / "fly-cast" / "STOP")
    log_path: Path | None = None
    max_len: int = 120
    recent_window: int = 8
    dedupe_ttl_s: float = 3.0
    min_interval_s: float = 0.0
    blocklist: tuple[str, ...] = DEFAULT_BLOCKLIST
    extra_blocklist: tuple[str, ...] = ()

    _recent: list[tuple[str, float]] = field(default_factory=list, init=False, repr=False)
    _last_emit: float = field(default=0.0, init=False, repr=False)

    def _terms(self) -> tuple[str, ...]:
        return tuple(t.lower() for t in (*self.blocklist, *self.extra_blocklist) if t)

    def kill_active(self) -> bool:
        return self.stop_path.is_file()

    def strip_urls(self, text: str) -> str:
        # Regex only — do not treat sentence-final periods as domains.
        return " ".join(_URL_RE.sub(" ", text).split()).strip()

    def _blocked(self, text: str) -> str | None:
        low = text.lower()
        for term in self._terms():
            if term and term in low:
                return f"blocklist:{term}"
        return None

    def _append_log(self, row: dict) -> None:
        if self.log_path is None:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    def check(
        self,
        text: str,
        *,
        cues: str = "",
        mode: str = "picked",
        destination: str = "overlay",
        now: float | None = None,
    ) -> GuardResult:
        """Return whether `text` may be shown. Always logs when log_path is set."""
        raw = text if text is not None else ""
        ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(now or time.time()))
        tnow = now if now is not None else time.time()

        def finish(allowed: bool, filtered: str, reason: str) -> GuardResult:
            result = GuardResult(
                allowed=allowed,
                raw=raw,
                filtered=filtered if allowed else "",
                reason=reason,
                mode=mode if allowed else "silent",
                cues=cues,
                destination=destination if allowed else "none",
            )
            self._append_log(
                {
                    "time": ts,
                    "cues": cues,
                    "mode": result.mode,
                    "raw": raw,
                    "filtered": result.filtered,
                    "destination": result.destination,
                    "allowed": allowed,
                    "reason": reason,
                }
            )
            if allowed and filtered:
                self._recent.append((filtered.casefold(), tnow))
                self._recent = self._recent[-self.recent_window :]
                self._last_emit = tnow
            return result

        if self.kill_active():
            return finish(False, "", "kill_switch")

        filtered = self.strip_urls(raw)
        filtered = " ".join(filtered.split())
        if not filtered:
            return finish(False, "", "empty_after_strip")

        if len(filtered) > self.max_len:
            filtered = filtered[: self.max_len].rstrip()
            # Prefer word boundary when possible
            if " " in filtered:
                filtered = filtered.rsplit(" ", 1)[0]

        hit = self._blocked(filtered)
        if hit:
            return finish(False, "", hit)

        key = filtered.casefold()
        # Drop expired recent entries
        if self.dedupe_ttl_s > 0:
            self._recent = [(t, ts) for t, ts in self._recent if (tnow - ts) < self.dedupe_ttl_s]
        else:
            self._recent = self._recent[-self.recent_window :]
        if any(t == key for t, _ in self._recent):
            return finish(False, "", "dedupe")

        if self.min_interval_s > 0 and self._last_emit > 0:
            if (tnow - self._last_emit) < self.min_interval_s:
                return finish(False, "", "rate_limit")

        return finish(True, filtered, "ok")

    def as_dict(self, result: GuardResult) -> dict:
        return asdict(result)

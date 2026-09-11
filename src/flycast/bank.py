"""Load cue → candidate reply bank."""

from __future__ import annotations

from pathlib import Path


def load_bank(path: Path) -> dict[str, list[str]]:
    bank: dict[str, list[str]] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "\t" not in line:
            raise ValueError(f"bank line needs cue<TAB>text: {line!r}")
        cue, text = line.split("\t", 1)
        cue = cue.strip().upper()
        text = text.strip()
        if text.startswith("[synth]"):
            text = text[len("[synth]") :].strip()
        bank.setdefault(cue, []).append(text)
    return bank


def validate_bank(
    bank: dict[str, list[str]],
    *,
    required_cues: tuple[str, ...] | list[str] | frozenset[str],
    min_per_cue: int = 3,
) -> None:
    missing = [c for c in required_cues if len(bank.get(c, [])) < min_per_cue]
    if missing:
        raise ValueError(f"bank missing ≥{min_per_cue} lines for: {missing}")

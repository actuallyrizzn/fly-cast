"""Weighted lexicon — preferred mouth phrases for the active profile."""

from __future__ import annotations

from pathlib import Path


def load_lexicon(path: Path | None = None) -> dict[str, float]:
    """Load `phrase <tab> weight` rows. Phrases stored lowercased."""
    if path is None:
        from flycast.profile import default_profile

        path = default_profile().lexicon_path
    out: dict[str, float] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "\t" not in line:
            raise ValueError(f"lexicon line needs phrase<TAB>weight: {line!r}")
        phrase, weight_s = line.split("\t", 1)
        phrase = phrase.strip().lower()
        if not phrase:
            continue
        out[phrase] = float(weight_s.strip())
    return out


def lexicon_bonus(text: str, lexicon: dict[str, float]) -> float:
    """Sum of weights for lexicon phrases that appear in ``text`` (casefold)."""
    if not lexicon or not text:
        return 0.0
    low = text.casefold()
    total = 0.0
    for phrase, weight in sorted(lexicon.items(), key=lambda kv: len(kv[0]), reverse=True):
        if phrase and phrase in low:
            total += weight
            low = low.replace(phrase, " ", 1)
    return total

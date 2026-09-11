"""Weighted fly lexicon — preferred mouth phrases (not insect cosplay)."""

from __future__ import annotations

from pathlib import Path

DEFAULT_LEXICON = Path(__file__).resolve().parent.parent.parent / "fixtures" / "fly_lexicon.tsv"


def load_lexicon(path: Path | None = None) -> dict[str, float]:
    """Load `phrase <tab> weight` rows. Phrases stored lowercased."""
    path = path or DEFAULT_LEXICON
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
    # Longer phrases first so "missed it" beats "missed" if both listed
    for phrase, weight in sorted(lexicon.items(), key=lambda kv: len(kv[0]), reverse=True):
        if phrase and phrase in low:
            total += weight
            # consume once per phrase key
            low = low.replace(phrase, " ", 1)
    return total

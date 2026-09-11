"""Reaction climb corpus hygiene."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "examples" / "fly_hero" / "fixtures" / "reaction_train.txt"
HELD = ROOT / "examples" / "fly_hero" / "fixtures" / "reaction_heldout.txt"


def _lines(path: Path) -> list[str]:
    return [
        ln.strip()
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]


def test_reaction_train_no_heldout_leak():
    train = {ln.lower() for ln in _lines(TRAIN)}
    held = _lines(HELD)
    assert len(train) >= 50
    assert len(held) >= 5
    leaks = [h for h in held if h.lower() in train]
    assert leaks == []


def test_climb_script_exists():
    assert (ROOT / "tools" / "climb_reaction_freewrite.py").is_file()
    assert (ROOT / "examples" / "fly_hero" / "docs" / "FREEWRITE-CLIMB.md").is_file()

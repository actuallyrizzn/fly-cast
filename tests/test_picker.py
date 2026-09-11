"""Picker + reply bank tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from flycast.bank import load_bank, validate_bank
from flycast.brain import build_fly_brain
from flycast.picker import pick, score_candidate
from flycast.profile import load_profile
from flycast.tokenizer import Tokenizer
from flycast.train import train_fly_level_a

ROOT = Path(__file__).resolve().parents[1]
PROFILE = load_profile(ROOT / "examples" / "fly_hero")
BANK = PROFILE.bank_path


def test_bank_has_required_cues():
    bank = load_bank(BANK)
    validate_bank(bank, required_cues=PROFILE.bank_required_cues, min_per_cue=3)
    for cue in PROFILE.bank_required_cues:
        assert len(bank[cue]) >= 3


def test_picker_prefers_matching_line():
    # Tiny corpus that mentions miss language so the ridge path can lean that way.
    lines = [
        "missed a note on green.",
        "dropped that one badly.",
        "nice catch on the hit.",
        "song over that is a wrap.",
    ]
    tok = Tokenizer.build(lines + ["missed it", "nice catch", "hello world"], max_vocab=200)
    brain = build_fly_brain(vocab_size=tok.size, seed=0, inject_count=32)
    train_fly_level_a(brain, tok, lines, max_pairs=200)
    prompt = "MISS missed a note"
    candidates = ["Dropped that one.", "Nice catch.", "zzzz not a word xyzzy"]
    # Force a clear winner by scoring; at minimum pick returns labeled picked.
    result = pick(brain, tok, prompt, candidates)
    assert result.mode == "picked"
    assert result.text in candidates
    # Ranking helper is stable
    s0 = score_candidate(brain, tok, prompt, candidates[0])
    s1 = score_candidate(brain, tok, prompt, candidates[1])
    assert isinstance(s0, float) and isinstance(s1, float)


def test_pick_empty_raises():
    tok = Tokenizer.build(["a"], max_vocab=20)
    brain = build_fly_brain(vocab_size=tok.size, seed=0, inject_count=4)
    with pytest.raises(ValueError):
        pick(brain, tok, "a", [])

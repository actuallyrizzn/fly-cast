"""Fly lexicon + picker bonus tests."""

from __future__ import annotations

from pathlib import Path

from flycast.brain import build_fly_brain
from flycast.lexicon import lexicon_bonus, load_lexicon
from flycast.picker import pick, score_candidate
from flycast.tokenizer import Tokenizer
from flycast.train import train_fly_level_a

ROOT = Path(__file__).resolve().parents[1]


def test_load_lexicon():
    lex = load_lexicon(ROOT / "fixtures" / "fly_lexicon.tsv")
    assert lex["missed it"] >= 2.0
    assert lex["on time"] >= 2.0
    assert "buzz" not in lex  # no insect cosplay seed


def test_lexicon_bonus_prefers_phrase():
    lex = {"missed it": 3.0, "okay": 0.1}
    assert lexicon_bonus("Missed it.", lex) > lexicon_bonus("Okay.", lex)


def test_picker_lexicon_can_flip_winner():
    lines = ["missed a note on green.", "nice catch on the hit.", "song over wrap."]
    tok = Tokenizer.build(lines + ["missed it", "okay", "zzzz"], max_vocab=200)
    brain = build_fly_brain(vocab_size=tok.size, seed=0, inject_count=32)
    train_fly_level_a(brain, tok, lines, max_pairs=200)
    prompt = "MISS"
    candidates = ["Okay.", "Missed it."]
    lex = {"missed it": 5.0}
    # Strong lexicon should prefer Missed it even if model is noisy
    with_lex = pick(brain, tok, prompt, candidates, lexicon=lex, lexicon_scale=2.0)
    assert with_lex.text == "Missed it."
    # Bonus path is measurable
    s_ok = score_candidate(brain, tok, prompt, "Okay.", lexicon=lex, lexicon_scale=2.0)
    s_miss = score_candidate(brain, tok, prompt, "Missed it.", lexicon=lex, lexicon_scale=2.0)
    assert s_miss > s_ok

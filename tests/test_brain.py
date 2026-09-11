"""Brain, controls, generate, overfit gate."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from flycast.brain import (
    build_fly_brain,
    build_no_fly,
    param_budget_fly_io,
    param_budget_no_fly,
)
from flycast.generate import generate
from flycast.tokenizer import Tokenizer
from flycast.train import overfit_practice, train_fly_level_a

ROOT = Path(__file__).resolve().parents[1]
PRACTICE = ROOT / "fixtures" / "practice.txt"


def test_fly_and_scramble_step():
    tok = Tokenizer.build(["hit miss streak"], max_vocab=64)
    fly = build_fly_brain(vocab_size=tok.size, seed=0, scrambled=False, inject_count=16)
    scr = build_fly_brain(vocab_size=tok.size, seed=0, scrambled=True, inject_count=16)
    fly.reset()
    scr.reset()
    tid = tok.encode("hit")[0]
    s1 = fly.inject_token(tid)
    s2 = scr.inject_token(tid)
    assert s1.shape == (fly.size,)
    assert not np.allclose(s1, s2)
    probs = fly.next_token_probs()
    assert np.isclose(probs.sum(), 1.0)


def test_no_fly_budget_in_ballpark():
    fly = build_fly_brain(vocab_size=100, embed_dim=16, inject_count=16, seed=1)
    nof = build_no_fly(vocab_size=100, embed_dim=16, window_k=3, seed=1)
    # no-fly should not be a joke unigram: comparable IO budget order of magnitude
    fb = param_budget_fly_io(fly)
    nb = param_budget_no_fly(nof)
    assert nb > 1000
    assert fb > nb  # fly readout is huge (n_neurons * vocab); that is expected
    # window path works
    p = nof.probs([1, 2, 3])
    assert np.isclose(p.sum(), 1.0)


def test_generate_smoke():
    tok = Tokenizer.build(["the cat sat", "on the mat"], max_vocab=64)
    brain = build_fly_brain(vocab_size=tok.size, seed=2, inject_count=16)
    out = generate(brain, tok, "the cat", max_tokens=5, seed=2)
    assert isinstance(out, str)


def test_level_a_overfits_practice():
    lines = [ln.strip() for ln in PRACTICE.read_text().splitlines() if ln.strip() and not ln.startswith("#")]
    tok = Tokenizer.build(lines, max_vocab=200)
    brain = build_fly_brain(vocab_size=tok.size, seed=0, inject_count=32, steps=2)
    result = train_fly_level_a(brain, tok, lines)
    assert result.final_loss < 0.5, result.final_loss


def test_overfit_harness_three_way():
    result = overfit_practice(PRACTICE, seed=0)
    assert result["fly_ok"], result
    assert "scramble_loss" in result and "no_fly_loss" in result

"""Level B training tests."""

from __future__ import annotations

from flycast.brain import build_fly_brain
from flycast.tokenizer import Tokenizer
from flycast.train import train_fly_level_a, train_fly_level_b


def test_level_b_runs():
    lines = ["missed a note.", "nice catch.", "song over."]
    tok = Tokenizer.build(lines, max_vocab=100)
    brain = build_fly_brain(vocab_size=tok.size, seed=0, inject_count=16)
    train_fly_level_a(brain, tok, lines, max_pairs=50)
    before = brain.embed.copy()
    r = train_fly_level_b(brain, tok, lines, epochs=2, lr=0.05, max_pairs=40, seed=0)
    assert r.final_loss >= 0
    assert not (brain.embed == before).all()

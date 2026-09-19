"""Fly and scramble share the injection and the word vectors. Only the wiring differs."""

import numpy as np

from flycast.jevlab.arms import ArmCfg, build_reservoir, nofly_features, shuffle_tokens
from flycast.tokenizer import BOS, EOS, PAD, SEP, UNK, Tokenizer


def _cfg() -> ArmCfg:
    return ArmCfg(
        leak=0.5,
        steps=1,
        radius=0.9,
        inject_count=32,
        input_scale=1.0,
        pooling="mean",
        seed=0,
    )


def test_fly_and_scramble_share_inputs_not_wiring() -> None:
    tok = Tokenizer.from_tokens((PAD, UNK, BOS, EOS, SEP, "a"))
    embed = np.random.default_rng(0).normal(0, 0.1, size=(tok.size, 32)).astype(np.float32)
    cfg = _cfg()
    fly = build_reservoir(cfg, tok, embed, scrambled=False)
    scramble = build_reservoir(cfg, tok, embed, scrambled=True)
    assert np.array_equal(fly.brain.inject, scramble.brain.inject)
    assert np.array_equal(fly.brain.embed, scramble.brain.embed)
    assert not np.array_equal(fly.brain.syn_val, scramble.brain.syn_val)


def test_shuffle_keeps_bos_and_the_multiset() -> None:
    seqs = [[1, 2, 3, 4], [9, 8]]
    shuffled = shuffle_tokens(seqs, 3)
    assert shuffled[0][0] == 1
    assert sorted(shuffled[0]) == [1, 2, 3, 4]
    assert shuffled[1] == [9, 8]
    assert shuffle_tokens(seqs, 3) == shuffled


def test_nofly_feature_shapes() -> None:
    embed = np.ones((6, 4), dtype=np.float32)
    seqs = [[0, 1, 2]]
    assert nofly_features(embed, seqs, pooling="last").shape == (1, 4)
    assert nofly_features(embed, seqs, pooling="mean").shape == (1, 4)
    assert nofly_features(embed, seqs, pooling="last+mean").shape == (1, 8)

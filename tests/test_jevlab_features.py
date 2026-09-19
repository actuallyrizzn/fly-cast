"""Pooled states match FlyBrain.inject_token, including padded batches."""

import numpy as np

from flycast.brain import build_fly_brain
from flycast.jevlab.features import encode_packets, pooled_states
from flycast.tokenizer import Tokenizer


def _reservoir(brain):
    root_import = pooled_states.__globals__["_fast_reservoir"]
    return root_import()(brain)


def test_pooled_states_match_inject_token() -> None:
    rng = np.random.default_rng(1)
    brain = build_fly_brain(vocab_size=50, embed_dim=32, inject_count=32, seed=0)
    seqs = [rng.integers(1, 50, size=n).tolist() for n in (3, 7, 12)]
    res = _reservoir(brain)
    for pooling in ("last", "mean", "last+mean"):
        got = pooled_states(res, seqs, pooling=pooling, batch_lines=2)
        rows = []
        for seq in seqs:
            brain.reset()
            states = [brain.inject_token(int(tid)) for tid in seq]
            last = states[-1]
            mean = np.mean(np.stack(states), axis=0)
            if pooling == "last":
                rows.append(last)
            elif pooling == "mean":
                rows.append(mean)
            else:
                rows.append(np.concatenate([last, mean]))
        expected = np.stack(rows).astype(np.float32)
        assert got.shape == expected.shape
        assert np.max(np.abs(got - expected)) < 1e-4


def test_encode_packets_truncation_fraction() -> None:
    long = " ".join(f"w{i}" for i in range(100))
    short = " ".join(f"w{i}" for i in range(5))
    tok = Tokenizer.build([long, short], max_vocab=200)
    _seqs, frac = encode_packets(tok, [long], cap=64)
    assert frac == 1.0
    _seqs, frac = encode_packets(tok, [short], cap=64)
    assert frac == 0.0

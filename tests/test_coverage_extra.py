"""Extra coverage for error paths and CLI overfit."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from flycast.brain import FlyBrain, build_fly_brain, pick_inject_neurons
from flycast.cli import main
from flycast.connectome import Connectome, load_adjacency, load_connectome, scramble, spectral_radius
from flycast.generate import generate
from flycast.tokenizer import Tokenizer

ROOT = Path(__file__).resolve().parents[1]


def test_cli_overfit_ok():
    assert main(["overfit", str(ROOT / "fixtures" / "practice.txt"), "--epochs", "1"]) == 0


def test_generate_greedy():
    tok = Tokenizer.build(["a b c"], max_vocab=32)
    brain = build_fly_brain(vocab_size=tok.size, seed=1, inject_count=8)
    out = generate(brain, tok, "a", max_tokens=3, temperature=0.0, seed=1)
    assert isinstance(out, str)


def test_brain_validation_errors():
    with pytest.raises(ValueError):
        FlyBrain(
            n_neurons=2,
            syn_pre=np.array([0], dtype=np.int32),
            syn_post=np.array([1], dtype=np.int32),
            syn_val=np.array([1.0], dtype=np.float32),
            inject=np.array([0]),
            embed=np.zeros((2, 0), dtype=np.float32),
            readout=np.zeros((2, 2), dtype=np.float32),
        )
    brain = build_fly_brain(vocab_size=8, seed=0, inject_count=4)
    with pytest.raises(ValueError):
        brain.inject_token(99)


def test_scramble_and_radius_errors():
    with pytest.raises(ValueError):
        scramble(np.zeros((2, 3)))
    with pytest.raises(ValueError):
        spectral_radius(np.zeros((2, 3)))
    with pytest.raises(ValueError):
        spectral_radius(np.eye(2), iterations=0)
    z = np.zeros((3, 3), dtype=np.float32)
    assert spectral_radius(z) == 0.0


def test_load_adjacency_filters(tmp_path: Path):
    # unknown etype rejected via load_adjacency edge_types
    with pytest.raises(ValueError):
        load_adjacency(edge_types={"nope"})  # type: ignore[arg-type]


def test_pick_inject_no_sensory():
    weights = np.eye(4, dtype=np.float32)
    conn = Connectome(weights=weights, cell_types=("", "", "", ""))
    idx = pick_inject_neurons(conn, count=2, seed=0)
    assert len(idx) == 2


def test_tokenizer_unk_and_bad_id():
    tok = Tokenizer.build(["hello"], max_vocab=20)
    assert tok.decode([tok.token_to_id["<unk>"], 9999])

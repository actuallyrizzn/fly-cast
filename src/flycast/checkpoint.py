"""Save / load Level A free-write checkpoints (tokenizer + thin translator).

Wiring layout is rebuilt from the shipped connectome on load (not pickled).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from flycast.brain import FlyBrain, build_fly_brain
from flycast.tokenizer import Tokenizer


def save_level_a(path: Path, brain: FlyBrain, tokenizer: Tokenizer, *, meta: dict | None = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tok_path = path.with_suffix(".tok.json")
    tokenizer.save(tok_path)
    payload: dict = {
        "embed": brain.embed,
        "readout": brain.readout,
        "logit_bias": getattr(brain, "_logit_bias", np.zeros(brain.vocab_size, dtype=np.float32)),
        "inject": brain.inject,
        "fingerprint": np.asarray(tokenizer.fingerprint),
        "vocab_size": np.asarray(brain.vocab_size),
        "n_neurons": np.asarray(brain.n_neurons),
        "leak": np.asarray(brain.leak),
        "steps": np.asarray(brain.steps),
        "input_scale": np.asarray(brain.input_scale),
    }
    if meta is not None:
        import json as _json

        payload["meta_json"] = np.asarray(_json.dumps(meta))
    np.savez_compressed(path, **payload)


def load_level_a(path: Path, *, scrambled: bool = False, seed: int = 0) -> tuple[FlyBrain, Tokenizer]:
    path = Path(path)
    tok_path = path.with_suffix(".tok.json")
    data = np.load(path, allow_pickle=False)
    fingerprint = str(np.asarray(data["fingerprint"]).item())
    tokenizer = Tokenizer.load(tok_path, expect_fingerprint=fingerprint)
    brain = build_fly_brain(
        vocab_size=int(np.asarray(data["vocab_size"]).item()),
        seed=seed,
        scrambled=scrambled,
        leak=float(np.asarray(data["leak"]).item()),
        steps=int(np.asarray(data["steps"]).item()),
        input_scale=float(np.asarray(data["input_scale"]).item()),
    )
    brain.embed = data["embed"].astype(np.float32)
    brain.readout = data["readout"].astype(np.float32)
    brain._logit_bias = data["logit_bias"].astype(np.float32)
    inj = data["inject"].astype(np.int64)
    if inj.shape == brain.inject.shape:
        brain.inject = inj
    return brain, tokenizer


def default_checkpoint_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "artifacts" / "reaction-climb" / "level_a.npz"

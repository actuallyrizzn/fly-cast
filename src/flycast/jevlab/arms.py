"""Fly, scramble, no-fly, and order-shuffled arms on one shared GloVe matrix."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from flycast.jevlab.features import pooled_states
from flycast.tokenizer import Tokenizer

__all__ = [
    "ArmCfg",
    "arm_features",
    "build_reservoir",
    "nofly_features",
    "shuffle_tokens",
]


def _lab2():
    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from tools.lab2 import common

    return common


@dataclass
class ArmCfg:
    leak: float
    steps: int
    radius: float
    inject_count: int
    input_scale: float
    pooling: str
    seed: int

    def key(self) -> str:
        pooling = {"last": "last", "mean": "mean", "last+mean": "lastmean"}[self.pooling]
        return (
            f"l{self.leak}_s{self.steps}_r{self.radius}_i{self.inject_count}"
            f"_x{self.input_scale}_p{pooling}_seed{self.seed}"
        )

    def to_reservoir_cfg(self, scrambled: bool):
        common = _lab2()
        return common.ReservoirCfg(
            embed_dim=self.inject_count,
            radius=self.radius,
            leak=self.leak,
            steps=self.steps,
            inject_count=self.inject_count,
            input_scale=self.input_scale,
            seed=self.seed,
            scrambled=scrambled,
        )


def build_reservoir(cfg: ArmCfg, tok: Tokenizer, embed: np.ndarray, *, scrambled: bool):
    if embed.shape != (tok.size, cfg.inject_count):
        raise ValueError(
            f"embed {embed.shape} != ({tok.size}, {cfg.inject_count}); "
            "embed_dim must equal inject_count"
        )
    common = _lab2()
    brain = common.build_brain(cfg.to_reservoir_cfg(scrambled), tok.size)
    brain.embed = embed.astype(np.float32).copy()
    return common.FastReservoir(brain)


def nofly_features(embed: np.ndarray, seqs: list[list[int]], *, pooling: str) -> np.ndarray:
    rows: list[np.ndarray] = []
    for seq in seqs:
        body = seq[1:] if len(seq) > 1 else seq
        mean = embed[body].mean(axis=0)
        last = embed[seq[-1]]
        if pooling == "last":
            rows.append(last)
        elif pooling == "mean":
            rows.append(mean)
        elif pooling == "last+mean":
            rows.append(np.concatenate([last, mean]))
        else:
            raise ValueError(f"bad pooling {pooling}")
    return np.stack(rows).astype(np.float32)


def shuffle_tokens(seqs: list[list[int]], seed: int) -> list[list[int]]:
    rng = np.random.default_rng(seed)
    out: list[list[int]] = []
    for seq in seqs:
        if len(seq) <= 2:
            out.append(list(seq))
            continue
        rest = list(seq[1:])
        rng.shuffle(rest)
        out.append([seq[0], *rest])
    return out


def arm_features(
    arm: str,
    cfg: ArmCfg,
    tok: Tokenizer,
    embed: np.ndarray,
    seqs: list[list[int]],
) -> np.ndarray:
    if arm in {"fly", "fly_shuffled"}:
        rows = shuffle_tokens(seqs, cfg.seed) if arm == "fly_shuffled" else seqs
        res = build_reservoir(cfg, tok, embed, scrambled=False)
        return pooled_states(res, rows, pooling=cfg.pooling)
    if arm == "scramble":
        res = build_reservoir(cfg, tok, embed, scrambled=True)
        return pooled_states(res, seqs, pooling=cfg.pooling)
    if arm in {"nofly", "nofly_shuffled"}:
        rows = shuffle_tokens(seqs, cfg.seed) if arm == "nofly_shuffled" else seqs
        return nofly_features(embed, rows, pooling=cfg.pooling)
    raise ValueError(f"unknown arm {arm}")

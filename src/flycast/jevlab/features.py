"""Pooled reservoir states, batched, matched to FlyBrain.inject_token."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from flycast.tokenizer import BOS, Tokenizer

__all__ = ["encode_packets", "pooled_states"]


def _fast_reservoir():
    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from tools.lab2.common import FastReservoir

    return FastReservoir


def pooled_states(
    res,
    seqs: list[list[int]],
    *,
    pooling: str,
    batch_lines: int = 256,
) -> np.ndarray:
    """Pool each sequence to last, mean, or last+mean. Inactive pads do not step."""
    if pooling not in {"last", "mean", "last+mean"}:
        raise ValueError(f"bad pooling {pooling}")
    if not seqs:
        width = res.n * (2 if pooling == "last+mean" else 1)
        return np.zeros((0, width), dtype=np.float32)
    blocks: list[np.ndarray] = []
    for b0 in range(0, len(seqs), batch_lines):
        chunk = seqs[b0 : b0 + batch_lines]
        batch = len(chunk)
        length = max(len(seq) for seq in chunk)
        ids = np.zeros((batch, length), dtype=np.int64)
        lens = np.array([len(seq) for seq in chunk], dtype=np.int64)
        for i, seq in enumerate(chunk):
            ids[i, : len(seq)] = seq
        state = np.zeros((res.n, batch), dtype=np.float32)
        total = np.zeros((res.n, batch), dtype=np.float32)
        for t in range(length):
            active = t < lens
            if not active.any():
                break
            nxt = res.step(state, res.drive(ids[:, t]))
            state[:, active] = nxt[:, active]
            total[:, active] += state[:, active]
        last = state.T
        mean = (total / np.maximum(lens, 1)).T
        if pooling == "last":
            blocks.append(last)
        elif pooling == "mean":
            blocks.append(mean)
        else:
            blocks.append(np.concatenate([last, mean], axis=1))
    return np.concatenate(blocks, axis=0).astype(np.float32)


def encode_packets(
    tok: Tokenizer,
    texts: list[str],
    *,
    cap: int = 64,
) -> tuple[list[list[int]], float]:
    """Prepend <bos> and cap each packet. Return sequences and the truncated fraction."""
    if cap < 1:
        raise ValueError("cap must be positive")
    bos = tok.token_to_id[BOS]
    seqs: list[list[int]] = []
    truncated = 0
    for text in texts:
        ids = tok.encode(text)
        if len(ids) > cap - 1:
            truncated += 1
        seqs.append([bos, *ids[: cap - 1]])
    fraction = truncated / len(texts) if texts else 0.0
    return seqs, fraction

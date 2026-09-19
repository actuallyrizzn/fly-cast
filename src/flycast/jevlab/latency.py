"""Milliseconds per packet on the CPU. One packet at a time."""

from __future__ import annotations

import os
import platform

import numpy as np

from flycast.jevlab.data import token_count
from flycast.jevlab.features import encode_packets, pooled_states
from flycast.jevlab.readout import predict_proba
from flycast.tokenizer import Tokenizer

__all__ = ["nofly_latency_ms", "packet_latency_ms"]


def _sample(texts: list[str], n: int, seed: int) -> list[str]:
    rng = np.random.default_rng(seed)
    if not texts:
        raise ValueError("texts is empty")
    idx = rng.choice(len(texts), size=n, replace=len(texts) < n)
    return [texts[int(i)] for i in idx]


def _summary(samples: list[float], texts: list[str]) -> dict:
    arr = np.asarray(samples, dtype=np.float64)
    tokens = [token_count(text) for text in texts]
    return {
        "median_ms": float(np.median(arr)),
        "p90_ms": float(np.percentile(arr, 90)),
        "p99_ms": float(np.percentile(arr, 99)),
        "mean_tokens": float(np.mean(tokens)) if tokens else 0.0,
        "n": int(len(samples)),
        "cpu": platform.processor(),
        "threads": os.cpu_count(),
    }


def _time_rows(texts: list[str], step) -> list[float]:
    import time

    samples = []
    for text in texts:
        started = time.perf_counter()
        step(text)
        samples.append((time.perf_counter() - started) * 1000.0)
    return samples


def packet_latency_ms(tok: Tokenizer, res, head, texts: list[str], *, pooling: str, n: int = 1000, seed: int = 0) -> dict:
    warm = _sample(texts, 20, seed)
    measured = _sample(texts, n, seed + 1)

    def step(text: str) -> None:
        seqs, _fraction = encode_packets(tok, [text])
        pooled = pooled_states(res, seqs, pooling=pooling, batch_lines=1)
        predict_proba(head, pooled)

    _time_rows(warm, step)
    return _summary(_time_rows(measured, step), measured)


def nofly_latency_ms(tok: Tokenizer, embed: np.ndarray, texts: list[str], *, pooling: str, n: int = 1000, seed: int = 0) -> dict:
    from flycast.jevlab.arms import nofly_features

    warm = _sample(texts, 20, seed)
    measured = _sample(texts, n, seed + 1)

    def step(text: str) -> None:
        seqs, _fraction = encode_packets(tok, [text])
        nofly_features(embed, seqs, pooling=pooling)

    _time_rows(warm, step)
    return _summary(_time_rows(measured, step), measured)

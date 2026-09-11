"""Candidate picker: score reply bank under a prompt; label mode=picked."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from flycast.brain import FlyBrain
from flycast.tokenizer import BOS, EOS, Tokenizer


@dataclass(frozen=True)
class PickResult:
    text: str
    score: float
    mode: str = "picked"
    index: int = 0


def score_candidate(
    brain: FlyBrain,
    tokenizer: Tokenizer,
    prompt: str,
    candidate: str,
) -> float:
    """Average log-prob of candidate tokens after conditioning on prompt."""
    brain.reset()
    for tid in tokenizer.encode(prompt, add_bos=True):
        brain.inject_token(tid)
    ids = tokenizer.encode(candidate) + [tokenizer.token_to_id[EOS]]
    if not ids:
        return float("-inf")
    total = 0.0
    for tid in ids:
        probs = brain.next_token_probs()
        total += float(np.log(probs[tid] + 1e-12))
        brain.inject_token(tid)
    return total / len(ids)


def pick(
    brain: FlyBrain,
    tokenizer: Tokenizer,
    prompt: str,
    candidates: list[str],
) -> PickResult:
    if not candidates:
        raise ValueError("candidates must not be empty")
    best_i = 0
    best_s = float("-inf")
    for i, cand in enumerate(candidates):
        s = score_candidate(brain, tokenizer, prompt, cand)
        if s > best_s:
            best_s = s
            best_i = i
    return PickResult(text=candidates[best_i], score=best_s, mode="picked", index=best_i)

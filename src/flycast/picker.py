"""Candidate picker: score reply bank under a prompt; label mode=picked."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from flycast.brain import FlyBrain
from flycast.lexicon import lexicon_bonus
from flycast.tokenizer import EOS, Tokenizer


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
    *,
    lexicon: dict[str, float] | None = None,
    lexicon_scale: float = 0.85,
) -> float:
    """Average log-prob of candidate tokens after conditioning on prompt.

    Optional lexicon adds a soft bonus so preferred mouth phrases win more often.
    """
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
    model = total / len(ids)
    if lexicon:
        model = model + lexicon_scale * lexicon_bonus(candidate, lexicon)
    return model


def pick(
    brain: FlyBrain,
    tokenizer: Tokenizer,
    prompt: str,
    candidates: list[str],
    *,
    lexicon: dict[str, float] | None = None,
    lexicon_scale: float = 0.85,
    use_lexicon: bool = True,
) -> PickResult:
    if not candidates:
        raise ValueError("candidates must not be empty")
    if use_lexicon and lexicon is None:
        from flycast.lexicon import load_lexicon

        lexicon = load_lexicon()
    if not use_lexicon:
        lexicon = None
    best_i = 0
    best_s = float("-inf")
    for i, cand in enumerate(candidates):
        s = score_candidate(
            brain,
            tokenizer,
            prompt,
            cand,
            lexicon=lexicon,
            lexicon_scale=lexicon_scale,
        )
        if s > best_s:
            best_s = s
            best_i = i
    return PickResult(text=candidates[best_i], score=best_s, mode="picked", index=best_i)

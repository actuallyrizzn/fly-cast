"""Autoregressive decode helpers."""

from __future__ import annotations

from flycast.brain import FlyBrain
from flycast.tokenizer import EOS, Tokenizer


def generate(
    brain: FlyBrain,
    tokenizer: Tokenizer,
    prompt: str,
    *,
    max_tokens: int = 32,
    temperature: float = 1.0,
    seed: int = 0,
) -> str:
    """Feed prompt tokens, then sample until EOS or max_tokens."""
    import numpy as np

    rng = np.random.default_rng(seed)
    brain.reset()
    ids = tokenizer.encode(prompt, add_bos=True)
    for tid in ids:
        brain.inject_token(tid)
    out: list[int] = []
    eos_id = tokenizer.token_to_id[EOS]
    for _ in range(max_tokens):
        probs = brain.next_token_probs()
        if temperature <= 0:
            nxt = int(probs.argmax())
        else:
            logits = np.log(probs + 1e-12) / temperature
            logits -= logits.max()
            p = np.exp(logits)
            p /= p.sum()
            nxt = int(rng.choice(len(p), p=p))
        if nxt == eos_id:
            break
        out.append(nxt)
        brain.inject_token(nxt)
    return tokenizer.decode(out)

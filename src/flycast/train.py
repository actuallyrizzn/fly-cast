"""Level A training: frozen W + ridge readout (classic echo-state)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from flycast.brain import FlyBrain, NoFlyPredictor, build_fly_brain, build_no_fly
from flycast.tokenizer import BOS, EOS, Tokenizer


@dataclass
class TrainResult:
    losses: list[float]
    final_loss: float


def _pairs(
    tokenizer: Tokenizer,
    lines: list[str],
    *,
    max_pairs: int | None = None,
) -> list[tuple[list[int], int]]:
    pairs: list[tuple[list[int], int]] = []
    bos = tokenizer.token_to_id[BOS]
    eos = tokenizer.token_to_id[EOS]
    for line in lines:
        ids = [bos] + tokenizer.encode(line) + [eos]
        for i in range(len(ids) - 1):
            pairs.append((ids[: i + 1], ids[i + 1]))
            if max_pairs is not None and len(pairs) >= max_pairs:
                return pairs
    return pairs


def _nll(logits: np.ndarray, target: int) -> float:
    x = logits.astype(np.float64)
    x -= x.max()
    ex = np.exp(x)
    p = ex / ex.sum()
    return float(-np.log(p[target] + 1e-12))


def _collect_fly_examples(
    brain: FlyBrain,
    tokenizer: Tokenizer,
    lines: list[str],
    *,
    max_pairs: int | None,
) -> tuple[np.ndarray, np.ndarray]:
    """One forward pass per line. Returns states (N, n) and target ids (N,)."""
    bos = tokenizer.token_to_id[BOS]
    eos = tokenizer.token_to_id[EOS]
    states: list[np.ndarray] = []
    targets: list[int] = []
    for line in lines:
        ids = [bos] + tokenizer.encode(line) + [eos]
        if len(ids) < 2:
            continue
        brain.reset()
        for i in range(len(ids) - 1):
            brain.inject_token(ids[i])
            states.append(brain.state)
            targets.append(ids[i + 1])
            if max_pairs is not None and len(states) >= max_pairs:
                return np.stack(states), np.asarray(targets, dtype=np.int64)
    if not states:
        raise ValueError("no training pairs")
    return np.stack(states), np.asarray(targets, dtype=np.int64)


def train_fly_level_a(
    brain: FlyBrain,
    tokenizer: Tokenizer,
    lines: list[str],
    *,
    ridge: float = 1e-2,
    seed: int = 0,
    max_pairs: int | None = 800,
) -> TrainResult:
    """Fit readout by ridge regression (dual form). Embeddings and ``W`` stay fixed."""
    del seed
    states, targets = _collect_fly_examples(brain, tokenizer, lines, max_pairs=max_pairs)
    x = states.astype(np.float64)
    x = np.concatenate([x, np.ones((x.shape[0], 1), dtype=np.float64)], axis=1)
    y = np.zeros((len(targets), brain.vocab_size), dtype=np.float64)
    for i, t in enumerate(targets):
        y[i, t] = 1.0
    gram = x @ x.T
    gram += ridge * np.eye(gram.shape[0])
    alpha = np.linalg.solve(gram, y)
    w = x.T @ alpha
    base_w = w[:-1].astype(np.float32)
    base_b = w[-1].astype(np.float32)

    best_loss = float("inf")
    best_gain = 1.0
    # Evaluate CE on stored states — no second reservoir pass.
    for gain in (1.0, 2.0, 5.0, 10.0, 15.0, 20.0):
        logits = (states.astype(np.float64) @ (base_w * gain).astype(np.float64)) + (base_b * gain)
        total = 0.0
        for i, target in enumerate(targets):
            total += _nll(logits[i], int(target))
        avg = total / len(targets)
        if avg < best_loss:
            best_loss = avg
            best_gain = gain
    brain.readout = (base_w * best_gain).astype(np.float32)
    brain._logit_bias = (base_b * best_gain).astype(np.float32)
    return TrainResult(losses=[best_loss], final_loss=best_loss)


def train_fly_level_b(
    brain: FlyBrain,
    tokenizer: Tokenizer,
    lines: list[str],
    *,
    epochs: int = 8,
    lr: float = 0.05,
    max_pairs: int | None = 400,
    seed: int = 0,
) -> TrainResult:
    """Level B: freeze wiring ``W``, train input embeds + output readout with SGD.

    Does not add/remove synapses — only how signals enter (embed→inject) and leave (readout).
    """
    rng = np.random.default_rng(seed)
    pairs = _pairs(tokenizer, lines, max_pairs=max_pairs)
    if not pairs:
        raise ValueError("no training pairs")
    losses: list[float] = []
    for _ in range(epochs):
        order = np.arange(len(pairs))
        rng.shuffle(order)
        total = 0.0
        for idx in order:
            ctx, target = pairs[int(idx)]
            brain.reset()
            for tid in ctx:
                brain.inject_token(int(tid))
            state = brain.state.astype(np.float64)
            logits = state @ brain.readout.astype(np.float64)
            bias = getattr(brain, "_logit_bias", None)
            if bias is not None:
                logits = logits + bias.astype(np.float64)
            logits = logits - logits.max()
            ex = np.exp(logits)
            probs = ex / ex.sum()
            total += float(-np.log(probs[target] + 1e-12))
            # dL/dlogits
            dlogits = probs
            dlogits[target] -= 1.0
            # readout grad
            dW = np.outer(state, dlogits)
            brain.readout = (brain.readout.astype(np.float64) - lr * dW).astype(np.float32)
            if bias is not None:
                brain._logit_bias = (bias.astype(np.float64) - lr * dlogits).astype(np.float32)
            else:
                brain._logit_bias = (-lr * dlogits).astype(np.float32)
            # embed of last context token (input pathway)
            last = int(ctx[-1])
            # approximate: push embed via inject mapping sensitivity
            # dstate/dembed ~ input_scale on inject slots; use outer with dlogits through readout
            dstate = brain.readout.astype(np.float64) @ dlogits
            pool = brain.inject
            dim = brain.embed.shape[1]
            dembed = np.zeros(dim, dtype=np.float64)
            for i, neuron in enumerate(pool):
                dembed[i % dim] += float(dstate[int(neuron)]) * brain.input_scale
            brain.embed[last] = (brain.embed[last].astype(np.float64) - lr * dembed).astype(np.float32)
        losses.append(total / len(pairs))
    return TrainResult(losses=losses, final_loss=losses[-1])


def eval_fly_ce(
    brain: FlyBrain,
    tokenizer: Tokenizer,
    lines: list[str],
    *,
    max_pairs: int | None = 400,
) -> float:
    states, targets = _collect_fly_examples(brain, tokenizer, lines, max_pairs=max_pairs)
    total = 0.0
    for i, target in enumerate(targets):
        logits = states[i].astype(np.float64) @ brain.readout.astype(np.float64)
        bias = getattr(brain, "_logit_bias", None)
        if bias is not None:
            logits = logits + bias.astype(np.float64)
        total += _nll(logits, int(target))
    return total / len(targets)


def train_no_fly(
    pred: NoFlyPredictor,
    tokenizer: Tokenizer,
    lines: list[str],
    *,
    ridge: float = 1e-2,
    seed: int = 0,
    max_pairs: int | None = 800,
) -> TrainResult:
    del seed
    pairs = _pairs(tokenizer, lines, max_pairs=max_pairs)
    if not pairs:
        raise ValueError("no training pairs")
    feats = np.stack([pred.features(ctx) for ctx, _ in pairs], axis=0).astype(np.float64)
    feats = np.concatenate([feats, np.ones((feats.shape[0], 1))], axis=1)
    y = np.zeros((len(pairs), pred.vocab_size), dtype=np.float64)
    for i, (_, t) in enumerate(pairs):
        y[i, t] = 1.0
    gram = feats @ feats.T + ridge * np.eye(feats.shape[0])
    alpha = np.linalg.solve(gram, y)
    w = feats.T @ alpha
    pred.window = w[:-1].astype(np.float32)
    pred._logit_bias = w[-1].astype(np.float32)  # type: ignore[attr-defined]

    best_loss = float("inf")
    best_gain = 1.0
    base_w = pred.window.copy()
    base_b = pred._logit_bias.copy()
    for gain in (1.0, 2.0, 5.0, 10.0, 15.0, 20.0):
        pred.window = (base_w * gain).astype(np.float32)
        pred._logit_bias = (base_b * gain).astype(np.float32)
        total = 0.0
        for ctx, target in pairs:
            total += _nll(pred.logits(ctx), target)
        avg = total / len(pairs)
        if avg < best_loss:
            best_loss = avg
            best_gain = gain
    pred.window = (base_w * best_gain).astype(np.float32)
    pred._logit_bias = (base_b * best_gain).astype(np.float32)
    return TrainResult(losses=[best_loss], final_loss=best_loss)

def overfit_practice(
    practice_path: Path,
    *,
    seed: int = 0,
    epochs: int = 60,
) -> dict:
    """Harness gate helper: fly, scramble, no-fly all attempt the same tiny file."""
    del epochs  # ridge is one-shot
    lines = [
        ln.strip()
        for ln in practice_path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    tokenizer = Tokenizer.build(lines, max_vocab=500)
    fly = build_fly_brain(vocab_size=tokenizer.size, seed=seed, scrambled=False)
    scr = build_fly_brain(vocab_size=tokenizer.size, seed=seed, scrambled=True)
    nof = build_no_fly(vocab_size=tokenizer.size, seed=seed)
    # Share embeddings between fly variants for a fairer layout ablation
    scr.embed = fly.embed.copy()
    r_fly = train_fly_level_a(fly, tokenizer, lines, seed=seed)
    r_scr = train_fly_level_a(scr, tokenizer, lines, seed=seed)
    r_nof = train_no_fly(nof, tokenizer, lines, seed=seed)
    return {
        "lines": len(lines),
        "vocab": tokenizer.size,
        "fly_loss": r_fly.final_loss,
        "scramble_loss": r_scr.final_loss,
        "no_fly_loss": r_nof.final_loss,
        "fly_ok": r_fly.final_loss < 0.5,
        "tokenizer": tokenizer,
        "fly": fly,
    }

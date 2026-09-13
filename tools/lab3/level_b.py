"""Lab 3 training: softmax Level A warm-start + Level B (embed + readout, CE).

Wiring ``W`` stays frozen. Objective is next-token cross-entropy (not ridge-to-one-hot).
Level B embed grads use the same inject-pathway approximation as ``train_fly_level_b``,
but over many pairs with Adam + early stop on the Lab 2 valid split.
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "lab2"))
sys.path.insert(0, str(ROOT / "src"))

from common import (  # noqa: E402
    FastReservoir,
    ReservoirCfg,
    RidgeReadout,
    build_brain,
    build_tokenizer,
    ce_from_logits,
    collect_features,
    encode_lines,
    features,
    fit_ridge_streaming,
    fit_softmax,
    generate_fast,
    n_pairs,
)

LAB3 = ROOT / "artifacts" / "lab3"
DATA = LAB3 / "data"


def _apply_ro(brain, ro: RidgeReadout) -> None:
    brain.readout = ro.w.astype(np.float32)
    brain._logit_bias = ro.b.astype(np.float32)


def eval_held_ce(res: FastReservoir, ro: RidgeReadout, seqs: list[list[int]], skip_last_k: int = 0) -> float:
    hf, ht = collect_features(res, seqs, skip_last_k)
    return ce_from_logits(ro.logits(hf), ht)


def fit_level_b_softmax(
    brain,
    tok,
    train_seqs: list[list[int]],
    valid_seqs: list[list[int]],
    *,
    init_ro: RidgeReadout | None = None,
    epochs: int = 8,
    lr: float = 5e-4,
    lr_embed: float | None = None,
    l2: float = 1e-5,
    pairs_per_epoch: int = 12000,
    seed: int = 0,
    log=print,
) -> tuple[RidgeReadout, dict]:
    """Level B: Adam on readout + input embeds; W frozen. Softmax CE.

    Embed gradient: approximate via inject mapping (same idea as train_fly_level_b).
    Streams line-by-line so RAM stays under ~1GB on FlyBrain.
    """
    rng = np.random.default_rng(seed)
    lr_e = lr if lr_embed is None else lr_embed
    res = FastReservoir(brain)
    n = res.n
    V = tok.size
    dim = brain.embed.shape[1]

    if init_ro is not None:
        W = init_ro.w.astype(np.float32) * float(init_ro.gain)
        b = init_ro.b.astype(np.float32) * float(init_ro.gain)
    else:
        W = (rng.normal(0, 0.01, size=(n, V))).astype(np.float32)
        b = np.zeros(V, np.float32)

    mW = np.zeros_like(W)
    vW = np.zeros_like(W)
    mb = np.zeros_like(b)
    vb = np.zeros_like(b)
    mE = np.zeros_like(brain.embed)
    vE = np.zeros_like(brain.embed)
    b1, b2, eps = 0.9, 0.999, 1e-8
    step = 0
    best = (float("inf"), W.copy(), b.copy(), brain.embed.copy(), 0)
    hist: list[dict] = []

    # precompute inject map rows: for each embed dim slot, which neurons get it
    inject = brain.inject
    scale = float(brain.input_scale)

    def adam_update(param, grad, m, v, lr_):
        nonlocal step
        m[:] = b1 * m + (1 - b1) * grad
        v[:] = b2 * v + (1 - b2) * (grad * grad)
        a = lr_ * math.sqrt(1 - b2**step) / (1 - b1**step)
        param -= a * m / (np.sqrt(v) + eps)

    def valid_ce() -> float:
        ro = RidgeReadout(w=W, b=b, gain=1.0, ridge=0.0, feat_dim=n)
        # embeds already on brain; reservoir reads them live
        return eval_held_ce(res, ro, valid_seqs)

    for ep in range(1, epochs + 1):
        order = rng.permutation(len(train_seqs))
        tot = 0.0
        cnt = 0
        pairs_done = 0
        t0 = time.time()
        for li in order:
            if pairs_done >= pairs_per_epoch:
                break
            s = train_seqs[int(li)]
            if len(s) < 2:
                continue
            x = np.zeros((n, 1), dtype=np.float32)
            for t in range(len(s) - 1):
                tid = int(s[t])
                target = int(s[t + 1])
                x = res.step(x, res.drive(np.array([tid])))
                state = x[:, 0]
                logits = state.astype(np.float64) @ W.astype(np.float64) + b.astype(np.float64)
                logits -= logits.max()
                ex = np.exp(logits)
                p = ex / ex.sum()
                tot += float(-math.log(p[target] + 1e-12))
                cnt += 1
                dlogits = p
                dlogits[target] -= 1.0
                gW = np.outer(state, dlogits).astype(np.float32) + l2 * W
                gb = dlogits.astype(np.float32)
                # embed grad via inject pathway
                dstate = (W.astype(np.float64) @ dlogits).astype(np.float32)
                dembed = np.zeros(dim, dtype=np.float32)
                for i, neuron in enumerate(inject):
                    dembed[i % dim] += float(dstate[int(neuron)]) * scale

                step += 1
                adam_update(W, gW, mW, vW, lr)
                adam_update(b, gb, mb, vb, lr)
                # embed adam (single row)
                e = brain.embed[tid]
                ge = dembed + l2 * e
                mE[tid] = b1 * mE[tid] + (1 - b1) * ge
                vE[tid] = b2 * vE[tid] + (1 - b2) * (ge * ge)
                a = lr_e * math.sqrt(1 - b2**step) / (1 - b1**step)
                brain.embed[tid] = e - a * mE[tid] / (np.sqrt(vE[tid]) + eps)

                pairs_done += 1
                if pairs_done >= pairs_per_epoch:
                    break

        train_ce = tot / max(cnt, 1)
        vce = valid_ce()
        hist.append({"epoch": ep, "train_ce": train_ce, "valid_ce": vce, "pairs": pairs_done, "seconds": round(time.time() - t0, 1)})
        log(f"    Level-B softmax ep{ep}: train CE {train_ce:.4f}  valid CE {vce:.4f}  pairs={pairs_done} ({hist[-1]['seconds']}s)")
        if vce < best[0]:
            best = (vce, W.copy(), b.copy(), brain.embed.copy(), ep)
        elif ep - best[4] >= 2:
            log("    Level-B early stop")
            break

    vce_b, Wb, bb, Eb, ep_b = best
    brain.embed = Eb
    ro = RidgeReadout(w=Wb, b=bb, gain=1.0, ridge=0.0, feat_dim=n)
    _apply_ro(brain, ro)
    return ro, {
        "valid_ce": vce_b,
        "best_epoch": ep_b,
        "epochs_run": len(hist),
        "history": hist,
        "pairs_per_epoch": pairs_per_epoch,
    }


def train_lab3(
    train_lines: list[str],
    valid_lines: list[str],
    held_lines: list[str],
    *,
    cfg: ReservoirCfg,
    floors: dict,
    level_b_epochs: int = 8,
    pairs_per_epoch: int = 12000,
    softmax_a_epochs: int = 6,
    log=print,
) -> dict:
    """Full Lab 3 train: ridge → softmax Level A → softmax Level B; scramble Level B control."""
    tok = build_tokenizer(train_lines)
    tr = encode_lines(tok, train_lines)
    va = encode_lines(tok, valid_lines)
    he = encode_lines(tok, held_lines)
    log(f"  vocab={tok.size} pairs train={n_pairs(tr)} valid={n_pairs(va)} held={n_pairs(he)}")

    brain = build_brain(cfg, tok.size)
    res = FastReservoir(brain)

    # --- Level A ridge warm-start (fast, full data) ---
    vf, vt = collect_features(res, va, 0)
    ro_ridge, ridge_info = fit_ridge_streaming(
        res, tr, tok.size, ridges=(0.1, 1.0, 10.0, 100.0),
        valid_feats=vf, valid_targets=vt, log=log,
    )
    log(f"  Level-A ridge valid CE {ridge_info['valid_ce']:.4f}")

    # --- Level A softmax (readout only, correct objective) ---
    ro_a, a_info = fit_softmax(
        res, tr, tok.size, init=ro_ridge, epochs=softmax_a_epochs,
        valid_feats=vf, valid_targets=vt, cache_budget_mb=180, log=log,
    )
    _apply_ro(brain, ro_a)
    held_a = eval_held_ce(res, ro_a, he)
    log(f"  Level-A softmax held CE {held_a:.4f}")

    # --- Level B softmax (embed + readout) ---
    ro_b, b_info = fit_level_b_softmax(
        brain, tok, tr, va, init_ro=ro_a,
        epochs=level_b_epochs, pairs_per_epoch=pairs_per_epoch, log=log,
    )
    res = FastReservoir(brain)  # embeds changed
    held_b = eval_held_ce(res, ro_b, he)
    log(f"  Level-B softmax held CE {held_b:.4f}")

    # --- Scramble control: same Level A→B recipe, fresh embeds, scrambled W ---
    cfg_s = ReservoirCfg(**{**cfg.to_dict(), "scrambled": True, "seed": cfg.seed + 100})
    brain_s = build_brain(cfg_s, tok.size)
    res_s = FastReservoir(brain_s)
    vf_s, vt_s = collect_features(res_s, va, 0)
    ro_sr, _ = fit_ridge_streaming(
        res_s, tr, tok.size, ridges=(ridge_info["ridge"],),
        valid_feats=vf_s, valid_targets=vt_s, log=lambda *_: None,
    )
    ro_sa, _ = fit_softmax(
        res_s, tr, tok.size, init=ro_sr, epochs=max(2, softmax_a_epochs // 2),
        valid_feats=vf_s, valid_targets=vt_s, cache_budget_mb=180, log=lambda *_: None,
    )
    _apply_ro(brain_s, ro_sa)
    ro_sb, _ = fit_level_b_softmax(
        brain_s, tok, tr, va, init_ro=ro_sa,
        epochs=max(3, level_b_epochs // 2), pairs_per_epoch=pairs_per_epoch, log=lambda *_: None,
    )
    res_s = FastReservoir(brain_s)
    held_s = eval_held_ce(res_s, ro_sb, he)
    log(f"  scramble Level-B held CE {held_s:.4f}")

    bi = (floors.get("bigram") or {}).get("heldout_ce")
    tri = (floors.get("trigram") or {}).get("heldout_ce")
    honesty_ok = held_b < held_s
    return {
        "tok": tok,
        "brain": brain,
        "res": res,
        "ro": ro_b,
        "heldout_ce": held_b,
        "heldout_ce_level_a": held_a,
        "scramble_ce": held_s,
        "honesty_ok": honesty_ok,
        "beats_bigram": bi is not None and held_b < bi,
        "beats_trigram": tri is not None and held_b < tri,
        "beats_scramble": held_b < held_s,
        "ridge_valid_ce": ridge_info["valid_ce"],
        "level_a": a_info,
        "level_b": b_info,
        "vocab": tok.size,
        "pairs": n_pairs(tr),
        "bigram_floor": bi,
        "trigram_floor": tri,
    }

"""Lab 4 training: Level C — frozen mask, sign-preserving synapse magnitudes + embed + readout.

Pipeline: Lab 3 warm-start (ridge → softmax A → softmax B) → Level C Adam on
``syn_val`` (layout/sign frozen) + embeds + readout. Same CE objective and floors.
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "lab3"))
sys.path.insert(0, str(ROOT / "tools" / "lab2"))
sys.path.insert(0, str(ROOT / "src"))

from common import (  # noqa: E402
    FastReservoir,
    ReservoirCfg,
    RidgeReadout,
    build_brain,
    build_tokenizer,
    collect_features,
    encode_lines,
    fit_ridge_streaming,
    fit_softmax,
    n_pairs,
)
from level_b import _apply_ro, eval_held_ce, fit_level_b_softmax  # noqa: E402

LAB4 = ROOT / "artifacts" / "lab4"
DATA = ROOT / "artifacts" / "lab3" / "data"


def _rebuild_wt(res: FastReservoir) -> None:
    brain = res.brain
    n = brain.n_neurons
    w = np.zeros((n, n), dtype=np.float32)
    np.add.at(w, (brain.syn_pre, brain.syn_post), brain.syn_val)
    res.wt = np.ascontiguousarray(w.T)


def fit_level_c_softmax(
    brain,
    tok,
    train_seqs: list[list[int]],
    valid_seqs: list[list[int]],
    *,
    init_ro: RidgeReadout | None = None,
    epochs: int = 8,
    lr: float = 3e-4,
    lr_embed: float | None = None,
    lr_syn: float | None = None,
    l2: float = 1e-5,
    pairs_per_epoch: int = 40000,
    seed: int = 0,
    log=print,
) -> tuple[RidgeReadout, dict]:
    """Level C: Adam on readout + embeds + syn_val (sign/mask frozen). Softmax CE."""
    rng = np.random.default_rng(seed)
    lr_e = lr if lr_embed is None else lr_embed
    lr_s = (lr * 0.25) if lr_syn is None else lr_syn
    res = FastReservoir(brain)
    n = res.n
    V = tok.size
    dim = brain.embed.shape[1]
    syn0 = brain.syn_val.astype(np.float32).copy()
    syn_sign = np.sign(syn0)
    syn_sign[syn_sign == 0.0] = 0.0
    mask = syn_sign != 0.0

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
    mS = np.zeros_like(brain.syn_val)
    vS = np.zeros_like(brain.syn_val)
    b1, b2, eps = 0.9, 0.999, 1e-8
    step = 0
    best = (float("inf"), W.copy(), b.copy(), brain.embed.copy(), brain.syn_val.copy(), 0)
    hist: list[dict] = []

    inject = brain.inject
    scale = float(brain.input_scale)
    alpha = float(brain.leak)
    n_steps = int(brain.steps)

    def adam_update(param, grad, m, v, lr_):
        nonlocal step
        m[:] = b1 * m + (1 - b1) * grad
        v[:] = b2 * v + (1 - b2) * (grad * grad)
        a = lr_ * math.sqrt(1 - b2**step) / (1 - b1**step)
        param -= a * m / (np.sqrt(v) + eps)

    def valid_ce() -> float:
        _rebuild_wt(res)
        ro = RidgeReadout(w=W, b=b, gain=1.0, ridge=0.0, feat_dim=n)
        return eval_held_ce(res, ro, valid_seqs)

    for ep in range(1, epochs + 1):
        order = rng.permutation(len(train_seqs))
        tot = 0.0
        cnt = 0
        pairs_done = 0
        t0 = time.time()
        _rebuild_wt(res)
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
                # unroll reservoir steps; keep tape for syn grads
                drive = res.drive(np.array([tid]))
                xs = [x.copy()]
                ys = []
                for _ in range(n_steps):
                    pre = drive + res.wt @ xs[-1]
                    y = np.tanh(pre)
                    ys.append(y)
                    xs.append((1.0 - alpha) * xs[-1] + alpha * y)
                x = xs[-1]

                state = x[:, 0]
                logits = state.astype(np.float64) @ W.astype(np.float64) + b.astype(np.float64)
                logits -= logits.max()
                ex = np.exp(logits)
                p = ex / ex.sum()
                tot += float(-math.log(p[target] + 1e-12))
                cnt += 1

                dlogits = p.copy()
                dlogits[target] -= 1.0
                gW = np.outer(state, dlogits).astype(np.float32) + l2 * W
                gb = dlogits.astype(np.float32)
                dstate = (W.astype(np.float64) @ dlogits).astype(np.float32).reshape(n, 1)

                # BPTT through reservoir steps → syn_val + embed
                g_syn = np.zeros_like(brain.syn_val)
                dembed = np.zeros(dim, dtype=np.float32)
                dx = dstate
                for k in range(n_steps - 1, -1, -1):
                    # x_{k+1} = (1-a) x_k + a y_k ; y=tanh(drive + W^T x_k)
                    dy = alpha * dx
                    dpre = dy * (1.0 - ys[k] * ys[k])
                    # sparse W grads: syn contributes to (W^T x)[post] via x[pre]
                    xk = xs[k][:, 0]
                    dpre_v = dpre[:, 0]
                    g_syn += dpre_v[brain.syn_post] * xk[brain.syn_pre]
                    # embed via drive
                    for i, neuron in enumerate(inject):
                        dembed[i % dim] += float(dpre_v[int(neuron)]) * scale
                    dx = (1.0 - alpha) * dx + (res.wt.T @ dpre)  # d(W^T x)/dx = W

                g_syn = g_syn.astype(np.float32) + l2 * brain.syn_val
                g_syn *= mask.astype(np.float32)

                step += 1
                adam_update(W, gW, mW, vW, lr)
                adam_update(b, gb, mb, vb, lr)
                e = brain.embed[tid]
                ge = dembed + l2 * e
                mE[tid] = b1 * mE[tid] + (1 - b1) * ge
                vE[tid] = b2 * vE[tid] + (1 - b2) * (ge * ge)
                ae = lr_e * math.sqrt(1 - b2**step) / (1 - b1**step)
                brain.embed[tid] = e - ae * mE[tid] / (np.sqrt(vE[tid]) + eps)

                mS[:] = b1 * mS + (1 - b1) * g_syn
                vS[:] = b2 * vS + (1 - b2) * (g_syn * g_syn)
                as_ = lr_s * math.sqrt(1 - b2**step) / (1 - b1**step)
                brain.syn_val -= as_ * mS / (np.sqrt(vS) + eps)
                brain.syn_val = syn_sign * np.abs(brain.syn_val)
                brain.syn_val *= mask.astype(np.float32)
                _rebuild_wt(res)

                pairs_done += 1
                if pairs_done >= pairs_per_epoch:
                    break

        train_ce = tot / max(cnt, 1)
        vce = valid_ce()
        hist.append(
            {
                "epoch": ep,
                "train_ce": train_ce,
                "valid_ce": vce,
                "pairs": pairs_done,
                "seconds": round(time.time() - t0, 1),
                "syn_l1_delta": float(np.mean(np.abs(brain.syn_val - syn0))),
            }
        )
        log(
            f"    Level-C softmax ep{ep}: train CE {train_ce:.4f}  valid CE {vce:.4f}  "
            f"pairs={pairs_done} synΔ={hist[-1]['syn_l1_delta']:.5f} ({hist[-1]['seconds']}s)"
        )
        if vce < best[0]:
            best = (vce, W.copy(), b.copy(), brain.embed.copy(), brain.syn_val.copy(), ep)
        elif ep - best[5] >= 2:
            log("    Level-C early stop")
            break

    vce_b, Wb, bb, Eb, Sb, ep_b = best
    brain.embed = Eb
    brain.syn_val = Sb
    _rebuild_wt(res)
    ro = RidgeReadout(w=Wb, b=bb, gain=1.0, ridge=0.0, feat_dim=n)
    _apply_ro(brain, ro)
    return ro, {
        "valid_ce": vce_b,
        "best_epoch": ep_b,
        "epochs_run": len(hist),
        "history": hist,
        "pairs_per_epoch": pairs_per_epoch,
        "syn_l1_delta": float(np.mean(np.abs(Sb - syn0))),
    }


def train_lab4(
    train_lines: list[str],
    valid_lines: list[str],
    held_lines: list[str],
    *,
    cfg: ReservoirCfg,
    floors: dict,
    level_b_epochs: int = 6,
    level_c_epochs: int = 8,
    pairs_per_epoch: int = 40000,
    softmax_a_epochs: int = 5,
    scramble_pairs_per_epoch: int | None = None,
    log=print,
) -> dict:
    """Lab 4: Lab3 warm-start then Level C; scramble gets the same recipe."""
    tok = build_tokenizer(train_lines)
    tr = encode_lines(tok, train_lines)
    va = encode_lines(tok, valid_lines)
    he = encode_lines(tok, held_lines)
    log(f"  vocab={tok.size} pairs train={n_pairs(tr)} valid={n_pairs(va)} held={n_pairs(he)}")

    brain = build_brain(cfg, tok.size)
    res = FastReservoir(brain)

    vf, vt = collect_features(res, va, 0)
    ro_ridge, ridge_info = fit_ridge_streaming(
        res, tr, tok.size, ridges=(0.1, 1.0, 10.0, 100.0),
        valid_feats=vf, valid_targets=vt, log=log,
    )
    log(f"  Level-A ridge valid CE {ridge_info['valid_ce']:.4f}")

    ro_a, a_info = fit_softmax(
        res, tr, tok.size, init=ro_ridge, epochs=softmax_a_epochs,
        valid_feats=vf, valid_targets=vt, cache_budget_mb=512, log=log,
    )
    _apply_ro(brain, ro_a)
    held_a = eval_held_ce(res, ro_a, he)
    log(f"  Level-A softmax held CE {held_a:.4f}")

    ro_b, b_info = fit_level_b_softmax(
        brain, tok, tr, va, init_ro=ro_a,
        epochs=level_b_epochs, pairs_per_epoch=min(pairs_per_epoch, 20000), log=log,
    )
    res = FastReservoir(brain)
    held_b = eval_held_ce(res, ro_b, he)
    log(f"  Level-B softmax held CE {held_b:.4f}")

    ro_c, c_info = fit_level_c_softmax(
        brain, tok, tr, va, init_ro=ro_b,
        epochs=level_c_epochs, pairs_per_epoch=pairs_per_epoch, log=log,
    )
    res = FastReservoir(brain)
    held_c = eval_held_ce(res, ro_c, he)
    log(f"  Level-C softmax held CE {held_c:.4f}")

    # Scramble control — same full recipe
    log("  scramble control (A→B→C)…")
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
        valid_feats=vf_s, valid_targets=vt_s, cache_budget_mb=512, log=lambda *_: None,
    )
    _apply_ro(brain_s, ro_sa)
    ro_sb, _ = fit_level_b_softmax(
        brain_s, tok, tr, va, init_ro=ro_sa,
        epochs=max(3, level_b_epochs // 2),
        pairs_per_epoch=min(pairs_per_epoch, 20000),
        log=lambda *_: None,
    )
    ro_sc, _ = fit_level_c_softmax(
        brain_s, tok, tr, va, init_ro=ro_sb,
        epochs=max(3, level_c_epochs // 2),
        pairs_per_epoch=scramble_pairs_per_epoch or pairs_per_epoch,
        log=lambda msg: None if "ep" in msg else log(msg),
    )
    res_s = FastReservoir(brain_s)
    held_s = eval_held_ce(res_s, ro_sc, he)
    log(f"  scramble Level-C held CE {held_s:.4f}")

    bi = (floors.get("bigram") or {}).get("heldout_ce")
    tri = (floors.get("trigram") or {}).get("heldout_ce")
    honesty_ok = held_c < held_s
    return {
        "tok": tok,
        "brain": brain,
        "res": res,
        "ro": ro_c,
        "heldout_ce": held_c,
        "heldout_ce_level_a": held_a,
        "heldout_ce_level_b": held_b,
        "scramble_ce": held_s,
        "honesty_ok": honesty_ok,
        "beats_bigram": bi is not None and held_c < bi,
        "beats_trigram": tri is not None and held_c < tri,
        "beats_scramble": held_c < held_s,
        "beats_level_b": held_c < held_b,
        "ridge_valid_ce": ridge_info["valid_ce"],
        "level_a": a_info,
        "level_b": b_info,
        "level_c": c_info,
        "vocab": tok.size,
        "pairs": n_pairs(tr),
        "bigram_floor": bi,
        "trigram_floor": tri,
    }

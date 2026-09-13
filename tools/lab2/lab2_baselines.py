#!/usr/bin/env python3
"""Lab 2 phase 0b — floors the fly must beat, measured on the SAME tokenizer + held-out.

  python tools/lab2/lab2_baselines.py

Writes artifacts/lab2/baselines.json:
  uniform, unigram, bigram, trigram (interpolation tuned on valid), no-fly last-3 ridge on ALL pairs.
Also samples each n-gram on the probe cues so we can see what "floor-quality" free-write reads like.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import (  # noqa: E402
    LAB2,
    ROOT,
    NGram,
    Split,
    build_tokenizer,
    ce_from_logits,
    encode_lines,
    jdump,
    n_pairs,
    uniform_ce,
)

sys.path.insert(0, str(ROOT / "src"))
from flycast.tokenizer import BOS, EOS  # noqa: E402

PROBE_CUES = ("MISS", "HIT", "STREAK", "SONG_START", "SONG_END", "OVERSTRUM", "SCORE", "LANE_R")


def no_fly_ridge(tok, train_seqs, valid_seqs, held_seqs, *, k=3, dim=32, seed=0):
    """Capacity-matched control: last-k token embeddings (random, fixed) → ridge readout, ALL pairs."""
    rng = np.random.default_rng(seed + 99)
    V = tok.size
    emb = rng.normal(0, 0.1, size=(V, dim)).astype(np.float32)

    def feats(seqs):
        xs, ys = [], []
        for s in seqs:
            for i in range(1, len(s)):
                ctx = s[max(0, i - k) : i]
                ctx = [0] * (k - len(ctx)) + ctx
                xs.append(np.concatenate([emb[c] for c in ctx]))
                ys.append(s[i])
        x = np.asarray(xs, dtype=np.float64)
        x = np.concatenate([x, np.ones((x.shape[0], 1))], axis=1)
        return x, np.asarray(ys)

    xt, yt = feats(train_seqs)
    xv, yv = feats(valid_seqs)
    xh, yh = feats(held_seqs)
    F = xt.shape[1]
    gram = xt.T @ xt
    xty = np.zeros((F, V))
    np.add.at(xty.T, yt, xt)
    eye = np.eye(F)
    eye[-1, -1] = 0
    best = None
    for lam in (0.1, 1.0, 10.0, 100.0):
        w = np.linalg.solve(gram + lam * eye, xty)
        base_v = xv @ w
        for g in (1, 2, 4, 8, 12, 16, 24, 32):
            c = ce_from_logits(base_v * g, yv)
            if best is None or c < best[0]:
                best = (c, lam, g, w)
    c, lam, g, w = best
    return {"valid_ce": c, "heldout_ce": ce_from_logits((xh @ w) * g, yh), "ridge": lam, "gain": g, "features": F - 1}


def main() -> int:
    sp = Split.load()
    tok = build_tokenizer(sp.train)
    tr = encode_lines(tok, sp.train)
    va = encode_lines(tok, sp.valid)
    he = encode_lines(tok, sp.heldout)
    eos = tok.token_to_id[EOS]
    V = tok.size
    out = {
        "vocab": V,
        "pairs": {"train": n_pairs(tr), "valid": n_pairs(va), "heldout": n_pairs(he)},
        "uniform_ce": uniform_ce(V),
        "models": {},
        "samples": {},
    }
    print(f"vocab={V} pairs train={n_pairs(tr)} valid={n_pairs(va)} held={n_pairs(he)} uniform={uniform_ce(V):.3f}")
    for order, name in ((1, "unigram"), (2, "bigram"), (3, "trigram")):
        m = NGram(order=order).fit(tr, V).tune(va)
        vce, hce = m.ce(va), m.ce(he)
        out["models"][name] = {"valid_ce": vce, "heldout_ce": hce, "lams": m.lams, "k": m.k}
        print(f"{name:8s} valid {vce:.3f}  held {hce:.3f}  lams={m.lams} k={m.k}")
        samples = {}
        for cue in PROBE_CUES:
            prompt = [tok.token_to_id[BOS]] + tok.encode(cue)
            samples[cue] = [tok.decode(m.sample(prompt, eos, seed=s)) for s in range(3)]
        out["samples"][name] = samples
    nf = no_fly_ridge(tok, tr, va, he)
    out["models"]["no_fly_last3_ridge_all"] = nf
    print(f"no-fly   valid {nf['valid_ce']:.3f}  held {nf['heldout_ce']:.3f}  λ={nf['ridge']} gain={nf['gain']}")
    print("\nbigram/trigram free-write flavor:")
    for cue in PROBE_CUES[:6]:
        print(f"  {cue:10s} bigram: {out['samples']['bigram'][cue][0]!r:45s} trigram: {out['samples']['trigram'][cue][0]!r}")
    jdump(LAB2 / "baselines.json", out)
    print(f"\nwrote {LAB2 / 'baselines.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

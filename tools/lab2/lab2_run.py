#!/usr/bin/env python3
"""Lab 2 phase 1 — ONE reservoir config, trained on ALL pairs, honest controls, real eval.

  python tools/lab2/lab2_run.py --tag default
  python tools/lab2/lab2_run.py --tag wide --embed-dim 64 --inject-count 256 --leak 0.3 --steps 1
  python tools/lab2/lab2_run.py --tag gold3 --gold-weight 3      # Grok KEEP lines upweighted
  python tools/lab2/lab2_run.py --tag skip1 --skip-last-k 1      # fly + last-token skip (ablation)
  python tools/lab2/lab2_run.py --tag nofly-skip --skip-last-k 1 --no-reservoir   # skip only

Per run writes artifacts/lab2/runs/<tag>/{result.json, samples.md, readout.npz}
  * fly CE on held-out vs scramble (N seeds, mean±sd) vs the n-gram floors from baselines.json
  * samples on probe cues in greedy / top-k / temperature modes (local mouth grade attached)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import (  # noqa: E402
    LAB2,
    ROOT,
    FastReservoir,
    ReservoirCfg,
    Split,
    build_brain,
    build_tokenizer,
    ce_from_logits,
    collect_features,
    encode_lines,
    fit_ridge_streaming,
    fit_softmax,
    generate_fast,
    jdump,
    n_pairs,
    verify_fast_equals_brain,
)

sys.path.insert(0, str(ROOT / "src"))
from flycast.mouth_taste import grade_text  # noqa: E402

PROBE_CUES = ("MISS", "HIT", "STREAK", "SONG_START", "SONG_END", "OVERSTRUM", "SCORE", "LANE_R")


def log(msg: str) -> None:
    print(msg, flush=True)


def train_eval(
    cfg: ReservoirCfg, tok, tr, va, he, *, line_weights=None, ridges=(0.1, 1.0, 10.0, 100.0),
    zero_wiring: bool = False, softmax_epochs: int = 0, softmax_lr: float = 2e-3, log=log,
):
    brain = build_brain(cfg, tok.size)
    res = FastReservoir(brain)
    if zero_wiring:
        res.wt[:] = 0.0  # ablation: no recurrence at all; only inject drive (+ skip embeds)
    vf, vt = collect_features(res, va, cfg.skip_last_k)
    t0 = time.time()
    ro, info = fit_ridge_streaming(
        res, tr, tok.size, skip_last_k=cfg.skip_last_k, line_weights=line_weights,
        ridges=ridges, valid_feats=vf, valid_targets=vt, log=log,
    )
    hf, ht = collect_features(res, he, cfg.skip_last_k)
    info["ridge_heldout_ce"] = ce_from_logits(ro.logits(hf), ht)
    if softmax_epochs > 0:
        ro, sinfo = fit_softmax(
            res, tr, tok.size, init=ro, skip_last_k=cfg.skip_last_k, line_weights=line_weights,
            epochs=softmax_epochs, lr=softmax_lr, valid_feats=vf, valid_targets=vt, log=log,
        )
        info["softmax"] = sinfo
        info["valid_ce"] = sinfo["valid_ce"]
    held_ce = ce_from_logits(ro.logits(hf), ht)
    info.update({"heldout_ce": held_ce, "fit_seconds": round(time.time() - t0, 1)})
    return brain, res, ro, info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--embed-dim", type=int, default=32)
    ap.add_argument("--radius", type=float, default=0.9)
    ap.add_argument("--leak", type=float, default=0.5)
    ap.add_argument("--steps", type=int, default=2)
    ap.add_argument("--inject-count", type=int, default=64)
    ap.add_argument("--input-scale", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--skip-last-k", type=int, default=0)
    ap.add_argument("--scramble-seeds", type=int, default=2, help="N scrambled-wiring controls (0 to skip)")
    ap.add_argument("--gold-weight", type=float, default=1.0, help="row weight for Grok KEEP/REWRITE gold lines")
    ap.add_argument("--no-reservoir", action="store_true", help="ablation: zero the wiring (skip features only)")
    ap.add_argument("--max-train-lines", type=int, default=0)
    ap.add_argument("--softmax-epochs", type=int, default=0, help="after ridge, fit a softmax readout (Adam) for N epochs")
    ap.add_argument("--softmax-lr", type=float, default=2e-3)
    args = ap.parse_args()

    sp = Split.load()
    train_lines = sp.train[: args.max_train_lines] if args.max_train_lines else sp.train
    tok = build_tokenizer(train_lines)
    tr = encode_lines(tok, train_lines)
    va = encode_lines(tok, sp.valid)
    he = encode_lines(tok, sp.heldout)
    log(f"[{args.tag}] vocab={tok.size} pairs train={n_pairs(tr)} valid={n_pairs(va)} held={n_pairs(he)}")

    line_weights = None
    if args.gold_weight != 1.0 and sp.gold:
        gold = {g.lower() for g in sp.gold}
        line_weights = np.array([args.gold_weight if ln.lower() in gold else 1.0 for ln in train_lines], dtype=np.float64)
        log(f"[{args.tag}] gold upweight ×{args.gold_weight} on {int((line_weights > 1).sum())} train lines")

    cfg = ReservoirCfg(
        embed_dim=args.embed_dim, radius=args.radius, leak=args.leak, steps=args.steps,
        inject_count=args.inject_count, input_scale=args.input_scale, seed=args.seed,
        scrambled=False, skip_last_k=args.skip_last_k,
    )

    # sanity: batched twin == FlyBrain reference (only meaningful with wiring on)
    if not args.no_reservoir:
        b0 = build_brain(cfg, tok.size)
        diff = verify_fast_equals_brain(b0, tok, train_lines[0])
        log(f"[{args.tag}] fast-reservoir vs FlyBrain max|Δ| = {diff:.2e}")
        assert diff < 1e-4, "FastReservoir diverged from FlyBrain"

    brain, res, ro, fly = train_eval(
        cfg, tok, tr, va, he, line_weights=line_weights, zero_wiring=args.no_reservoir,
        softmax_epochs=args.softmax_epochs, softmax_lr=args.softmax_lr,
    )
    log(f"[{args.tag}] FLY  held CE {fly['heldout_ce']:.4f} (valid {fly['valid_ce']:.4f}, λ={fly['ridge']}, gain={fly['gain']}, {fly['fit_seconds']}s)")

    scr = []
    for s in range(args.scramble_seeds):
        c2 = ReservoirCfg(**{**cfg.to_dict(), "scrambled": True, "seed": 100 + s})
        _, _, _, r = train_eval(
            c2, tok, tr, va, he, line_weights=line_weights, ridges=(fly["ridge"],),
            softmax_epochs=args.softmax_epochs, softmax_lr=args.softmax_lr, log=lambda *_: None,
        )
        scr.append(r["heldout_ce"])
        log(f"[{args.tag}] SCR{s} held CE {r['heldout_ce']:.4f}")

    base_p = LAB2 / "baselines.json"
    floors = json.loads(base_p.read_text())["models"] if base_p.is_file() else {}
    floor_bi = floors.get("bigram", {}).get("heldout_ce")
    floor_tri = floors.get("trigram", {}).get("heldout_ce")

    # samples
    samples = []
    local_ok = {"greedy": 0, "topk": 0, "temp": 0}
    for i, cue in enumerate(PROBE_CUES):
        row = {"cue": cue}
        for mode in ("greedy", "topk", "temp"):
            txt = generate_fast(res, ro, tok, cue, skip_last_k=cfg.skip_last_k, mode=mode, seed=10 + i)
            g = grade_text(txt, cue=cue)
            row[mode] = txt
            row[f"{mode}_local_ok"] = bool(g.ok)
            local_ok[mode] += int(g.ok)
        samples.append(row)

    result = {
        "tag": args.tag,
        "cfg": cfg.to_dict(),
        "vocab": tok.size,
        "pairs": {"train": n_pairs(tr), "valid": n_pairs(va), "heldout": n_pairs(he)},
        "fly": fly,
        "scramble_heldout_ce": scr,
        "scramble_mean": float(np.mean(scr)) if scr else None,
        "scramble_sd": float(np.std(scr)) if scr else None,
        "floors": {"bigram": floor_bi, "trigram": floor_tri, "uniform": float(np.log(tok.size))},
        "beats_bigram": (floor_bi is not None and fly["heldout_ce"] < floor_bi),
        "beats_trigram": (floor_tri is not None and fly["heldout_ce"] < floor_tri),
        "beats_scramble": bool(scr) and fly["heldout_ce"] < min(scr),
        "gold_weight": args.gold_weight,
        "no_reservoir": args.no_reservoir,
        "local_probe_ok": {k: f"{v}/{len(PROBE_CUES)}" for k, v in local_ok.items()},
        "samples": samples,
    }
    out = LAB2 / "runs" / args.tag
    out.mkdir(parents=True, exist_ok=True)
    jdump(out / "result.json", result)
    np.savez_compressed(
        out / "readout.npz", w=ro.w, b=ro.b, gain=np.asarray(ro.gain), ridge=np.asarray(ro.ridge),
        embed=brain.embed, inject=brain.inject, cfg_json=np.asarray(json.dumps(cfg.to_dict())),
        tokens=np.asarray(list(tok.id_to_token)),
    )
    md = [f"# Lab 2 run `{args.tag}`", "", f"held CE fly **{fly['heldout_ce']:.3f}** · scramble {scr} · bigram {floor_bi} · trigram {floor_tri}", ""]
    md += ["| cue | greedy | top-k | temp |", "|---|---|---|---|"]
    for r in samples:
        md.append(f"| {r['cue']} | {r['greedy']} | {r['topk']} | {r['temp']} |")
    (out / "samples.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    log(f"[{args.tag}] beats bigram={result['beats_bigram']} trigram={result['beats_trigram']} scramble={result['beats_scramble']}")
    for r in samples:
        log(f"   {r['cue']:10s} greedy={r['greedy']!r}  topk={r['topk']!r}")
    log(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Lab 2 phase 2 — architecture sweep (the lever Lab 1 never pulled).

  nohup python tools/lab2/lab2_sweep.py --grid quick  >> artifacts/lab2/sweep.log 2>&1 &
  python tools/lab2/lab2_sweep.py --grid full --resume

Each config: full-data ridge readout, held-out CE, 1 scramble control. Results append to
artifacts/lab2/sweep.jsonl (resumable: configs already present are skipped). Fly must beat
the bigram floor to be interesting; beat trigram + scramble to be a story.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import (  # noqa: E402
    LAB2,
    ReservoirCfg,
    Split,
    build_tokenizer,
    encode_lines,
)
from lab2_run import train_eval  # noqa: E402

GRIDS = {
    "quick": dict(
        embed_dim=[32, 64],
        radius=[0.9],
        leak=[0.3, 0.5, 0.8, 1.0],
        steps=[1, 2],
        inject_count=[64, 256],
        input_scale=[1.0, 3.0],
    ),
    "full": dict(
        embed_dim=[32, 64, 128],
        radius=[0.7, 0.9, 1.1],
        leak=[0.2, 0.3, 0.5, 0.8, 1.0],
        steps=[1, 2, 4],
        inject_count=[64, 256, 512],
        input_scale=[0.5, 1.0, 3.0, 6.0],
    ),
    "input": dict(  # only the input pathway — cheap, high-yield
        embed_dim=[32, 64, 128],
        radius=[0.9],
        leak=[0.5],
        steps=[2],
        inject_count=[64, 256, 512, 1024],
        input_scale=[0.5, 1.0, 3.0, 6.0],
    ),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", choices=sorted(GRIDS), default="quick")
    ap.add_argument("--resume", action="store_true", default=True)
    ap.add_argument("--skip-last-k", type=int, default=0)
    ap.add_argument("--scramble", type=int, default=1)
    args = ap.parse_args()

    out = LAB2 / "sweep.jsonl"
    done: set[str] = set()
    if out.is_file() and args.resume:
        for ln in out.read_text().splitlines():
            if ln.strip():
                done.add(json.loads(ln)["key"])

    sp = Split.load()
    tok = build_tokenizer(sp.train)
    tr = encode_lines(tok, sp.train)
    va = encode_lines(tok, sp.valid)
    he = encode_lines(tok, sp.heldout)
    base_p = LAB2 / "baselines.json"
    floors = json.loads(base_p.read_text())["models"] if base_p.is_file() else {}
    bi = floors.get("bigram", {}).get("heldout_ce")
    tri = floors.get("trigram", {}).get("heldout_ce")

    grid = GRIDS[args.grid]
    keys = list(grid)
    combos = list(itertools.product(*[grid[k] for k in keys]))
    print(f"sweep {args.grid}: {len(combos)} configs, {len(done)} done, floors bigram={bi} trigram={tri}", flush=True)
    for vals in combos:
        cfg = ReservoirCfg(**dict(zip(keys, vals)), skip_last_k=args.skip_last_k)
        if cfg.key() in done:
            continue
        t0 = time.time()
        try:
            quiet = lambda *_: None  # noqa: E731
            _, _, _, fly = train_eval(cfg, tok, tr, va, he, log=quiet)
            scr = []
            for s in range(args.scramble):
                c2 = ReservoirCfg(**{**cfg.to_dict(), "scrambled": True, "seed": 100 + s})
                _, _, _, r = train_eval(c2, tok, tr, va, he, ridges=(fly["ridge"],), log=quiet)
                scr.append(r["heldout_ce"])
            rec = {
                "key": cfg.key(),
                "cfg": cfg.to_dict(),
                "heldout_ce": fly["heldout_ce"],
                "valid_ce": fly["valid_ce"],
                "ridge": fly["ridge"],
                "gain": fly["gain"],
                "scramble": scr,
                "beats_bigram": bi is not None and fly["heldout_ce"] < bi,
                "beats_trigram": tri is not None and fly["heldout_ce"] < tri,
                "beats_scramble": bool(scr) and fly["heldout_ce"] < min(scr),
                "seconds": round(time.time() - t0, 1),
            }
        except Exception as exc:  # noqa: BLE001
            rec = {"key": cfg.key(), "cfg": cfg.to_dict(), "error": str(exc), "seconds": round(time.time() - t0, 1)}
        with out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(
            f"  {cfg.key():60s} held {rec.get('heldout_ce', float('nan')):.4f} scr {rec.get('scramble')} "
            f"bigram={'Y' if rec.get('beats_bigram') else 'n'} {rec['seconds']}s",
            flush=True,
        )
    print("sweep done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

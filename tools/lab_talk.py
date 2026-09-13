#!/usr/bin/env python3
"""Talk to a saved Lab 4/5/6 fly on FlyBrain (or any host with the artifact).

  # interactive (default: latest run under artifacts/lab5/desk or pass --run)
  python tools/lab_talk.py
  python tools/lab_talk.py --run artifacts/lab5/desk/run-YYYYMMDDTHHMMSSZ
  python tools/lab_talk.py --run artifacts/lab6/run-…

  # one-shot
  python tools/lab_talk.py -p "DESK ETH long 2x, funding flipped negative, confluence 3/4, invalidation written, venue healthy"
  python tools/lab_talk.py -p "MISS" --max-tokens 16

Commands inside the REPL:
  /quit  /help  /greedy  /topk  /temp 0.8  /max 20  /seed 1
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "lab2"))
sys.path.insert(0, str(ROOT / "src"))

from common import FastReservoir, RidgeReadout, generate_fast  # noqa: E402
from flycast.brain import FlyBrain  # noqa: E402
from flycast.tokenizer import Tokenizer  # noqa: E402


def resolve_run(path: Path | None) -> Path:
    if path is None:
        for root in (
            ROOT / "artifacts" / "lab5" / "desk",
            ROOT / "artifacts" / "lab6",
            ROOT / "artifacts" / "lab4",
        ):
            latest = root / "LATEST"
            if latest.is_file():
                return Path(latest.read_text().strip())
            runs = sorted(root.glob("run-*"), reverse=True)
            for r in runs:
                if (r / "fly_model.npz").is_file():
                    return r
        raise SystemExit("no saved fly_model.npz found — train a lab with save first")
    p = path if path.is_absolute() else ROOT / path
    if p.is_file() and p.name == "LATEST":
        return Path(p.read_text().strip())
    if p.is_file() and p.name == "fly_model.npz":
        return p.parent
    if p.is_dir() and (p / "LATEST").is_file() and not (p / "fly_model.npz").is_file():
        return Path((p / "LATEST").read_text().strip())
    if (p / "fly_model.npz").is_file():
        return p
    raise SystemExit(f"no fly_model.npz under {p}")


def load_fly(run: Path):
    npz = np.load(run / "fly_model.npz", allow_pickle=False)
    meta = json.loads(str(npz["meta"]))
    tok = Tokenizer.load(run / "tokenizer.json")
    brain = FlyBrain(
        n_neurons=int(meta["n_neurons"]),
        syn_pre=npz["syn_pre"],
        syn_post=npz["syn_post"],
        syn_val=npz["syn_val"],
        inject=npz["inject"],
        embed=npz["embed"],
        readout=npz["ro_w"],  # (n, V) — brain field; FastReservoir uses RidgeReadout separately
        leak=float(meta.get("leak", 0.5)),
        steps=int(meta.get("steps", 2)),
        input_scale=float(meta.get("input_scale", 1.0)),
    )
    ro = RidgeReadout(
        w=npz["ro_w"],
        b=npz["ro_b"],
        gain=float(meta.get("gain", 1.0)),
        ridge=0.0,
        feat_dim=int(meta["n_neurons"]),
    )
    res = FastReservoir(brain)
    return tok, res, ro, meta


def main() -> int:
    ap = argparse.ArgumentParser(description="Talk to a saved Fly Cast model")
    ap.add_argument("--run", type=Path, default=None, help="run dir (or path to fly_model.npz)")
    ap.add_argument("-p", "--prompt", default=None, help="one-shot prompt; omit for REPL")
    ap.add_argument("--max-tokens", type=int, default=24)
    ap.add_argument("--mode", choices=("greedy", "topk", "temp"), default="topk")
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--top-k", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    run = resolve_run(args.run)
    tok, res, ro, meta = load_fly(run)
    print(f"loaded {run}")
    print(
        f"  vocab={tok.size} neurons={meta['n_neurons']} "
        f"held_CE={meta.get('heldout_ce')} beats_bigram={meta.get('beats_bigram')}"
    )

    def once(prompt: str, *, seed: int) -> str:
        return generate_fast(
            res, ro, tok, prompt,
            max_tokens=args.max_tokens, mode=args.mode,
            top_k=args.top_k, temperature=args.temperature, seed=seed,
        )

    if args.prompt is not None:
        print(once(args.prompt, seed=args.seed))
        return 0

    print("REPL — type a cue/situation line. /quit to exit. /help for knobs.")
    seed = args.seed
    while True:
        try:
            line = input("> ").rstrip("\n")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line.strip():
            continue
        if line.startswith("/"):
            cmd, *rest = line.split(None, 1)
            arg = rest[0] if rest else ""
            if cmd in ("/quit", "/exit", "/q"):
                break
            if cmd == "/help":
                print("  /greedy | /topk | /temp <f> | /max <n> | /seed <n> | /quit")
                continue
            if cmd == "/greedy":
                args.mode = "greedy"; print("mode=greedy"); continue
            if cmd == "/topk":
                args.mode = "topk"; print("mode=topk"); continue
            if cmd == "/temp" and arg:
                args.temperature = float(arg); args.mode = "temp"; print(f"temp={args.temperature}"); continue
            if cmd == "/max" and arg:
                args.max_tokens = int(arg); print(f"max={args.max_tokens}"); continue
            if cmd == "/seed" and arg:
                seed = int(arg); print(f"seed={seed}"); continue
            print("unknown command — /help")
            continue
        print(once(line, seed=seed))
        seed += 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

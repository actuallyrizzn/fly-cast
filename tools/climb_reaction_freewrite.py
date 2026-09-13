#!/usr/bin/env python3
"""Reaction free-write climb: Level A honesty + Level B gate (CPU).

  . .venv/bin/activate && python tools/climb_reaction_freewrite.py
  python tools/climb_reaction_freewrite.py --train examples/fly_hero/fixtures/reaction_train_v3.txt
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from flycast.brain import build_fly_brain, build_no_fly
from flycast.checkpoint import save_level_a
from flycast.generate import generate
from flycast.tokenizer import Tokenizer
from flycast.train import _nll, _pairs, eval_fly_ce, train_fly_level_a, train_fly_level_b, train_no_fly

PROFILE = ROOT / "examples" / "fly_hero"
DEFAULT_TRAIN = PROFILE / "fixtures" / "reaction_train.txt"
DEFAULT_HELD = PROFILE / "fixtures" / "reaction_heldout.txt"
ARTIFACTS = ROOT / "artifacts" / "reaction-climb"
B_WIN_MARGIN = 0.05
# Cue-shaped prompts match v2/v3 corpus (additive free-write UX).
SAMPLE_PROMPTS = (
    "MISS",
    "MISS Missed it",
    "HIT",
    "HIT Nice catch",
    "STREAK",
    "SONG_START",
    "SONG_END",
)


def _lines(path: Path) -> list[str]:
    return [
        ln.strip()
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=Path, default=DEFAULT_TRAIN)
    ap.add_argument("--heldout", type=Path, default=DEFAULT_HELD)
    ap.add_argument("--artifacts", type=Path, default=ARTIFACTS)
    ap.add_argument("--max-pairs-a", type=int, default=0, help="0 = scale with corpus")
    ap.add_argument("--max-pairs-b", type=int, default=0)
    ap.add_argument("--epochs-b", type=int, default=3)
    args = ap.parse_args()

    train_path = args.train if args.train.is_absolute() else ROOT / args.train
    held_path = args.heldout if args.heldout.is_absolute() else ROOT / args.heldout
    artifacts = args.artifacts if args.artifacts.is_absolute() else ROOT / args.artifacts

    train_lines = _lines(train_path)
    held = _lines(held_path)
    train_lower = {ln.lower() for ln in train_lines}
    leaked = [h for h in held if h.lower() in train_lower]
    if leaked:
        raise SystemExit(f"held-out leak into train: {leaked}")

    max_a = args.max_pairs_a or min(50000, max(2500, len(train_lines) * 4))
    max_b = args.max_pairs_b or min(20000, max(1200, len(train_lines) * 2))

    tok = Tokenizer.build(train_lines + held, max_vocab=min(4000, max(1200, len(train_lines) // 3)))

    fly_a = build_fly_brain(vocab_size=tok.size, seed=0, scrambled=False)
    fly_b = build_fly_brain(vocab_size=tok.size, seed=0, scrambled=False)
    fly_b.embed = fly_a.embed.copy()
    scr = build_fly_brain(vocab_size=tok.size, seed=0, scrambled=True)
    scr.embed = fly_a.embed.copy()
    nof = build_no_fly(vocab_size=tok.size, seed=0)

    train_fly_level_a(fly_a, tok, train_lines, max_pairs=max_a)
    fly_b.readout = fly_a.readout.copy()
    if hasattr(fly_a, "_logit_bias"):
        fly_b._logit_bias = fly_a._logit_bias.copy()
    # Gentle B — prior run overfit; keep W frozen, light SGD.
    train_fly_level_b(
        fly_b, tok, train_lines, epochs=args.epochs_b, lr=0.01, max_pairs=max_b, seed=0
    )
    train_fly_level_a(scr, tok, train_lines, max_pairs=max_a)
    train_no_fly(nof, tok, train_lines, max_pairs=max_a)

    ce_a = eval_fly_ce(fly_a, tok, held, max_pairs=800)
    ce_b = eval_fly_ce(fly_b, tok, held, max_pairs=800)
    ce_s = eval_fly_ce(scr, tok, held, max_pairs=800)
    nof_pairs = _pairs(tok, held, max_pairs=800)
    ce_n = sum(_nll(nof.logits(ctx), t) for ctx, t in nof_pairs) / max(len(nof_pairs), 1)

    samples: dict[str, dict[str, str]] = {}
    for prompt in SAMPLE_PROMPTS:
        samples[prompt] = {
            "A": generate(
                fly_a, tok, prompt, max_tokens=16, min_tokens=3, seed=1, temperature=0.7
            ),
            "B": generate(
                fly_b, tok, prompt, max_tokens=16, min_tokens=3, seed=1, temperature=0.7
            ),
        }

    b_wins = ce_b < ce_a - B_WIN_MARGIN
    gate = (
        "B_WINS — Level C may start; picker stays Fly Hero live default until free-write flag."
        if b_wins
        else "B_LOSES — stay on A + picker live; iterate corpus/hyperparams; do not open Level C."
    )

    readable_a = sum(1 for p in samples.values() if len(p["A"].replace(".", "").strip()) >= 3)
    print("=== Level A honesty (held-out reaction CE, lower better) ===")
    print(f"Fly (A):     {ce_a:.4f}")
    print(f"Scramble:    {ce_s:.4f}")
    print(f"No-fly:      {ce_n:.4f}")
    print("\n=== Level B vs A ===")
    print(f"Level A fly: {ce_a:.4f}")
    print(f"Level B fly: {ce_b:.4f}")
    print(f"Scramble A:  {ce_s:.4f}")
    print(f"B vs A:      {ce_b - ce_a:+.4f} (negative = B better)")
    print(f"\n=== Gate (margin {B_WIN_MARGIN}) ===")
    print(gate)
    print(f"readable_A_samples: {readable_a}/{len(samples)}")
    print(f"train_lines: {len(train_lines)} max_pairs_a={max_a} max_pairs_b={max_b}")
    print("\n=== Samples (min_tokens=3) ===")
    for prompt, pair in samples.items():
        print(f"A | {prompt!r} → {pair['A']}")
        print(f"B | {prompt!r} → {pair['B']}")

    artifacts.mkdir(parents=True, exist_ok=True)
    ckpt = artifacts / "level_a.npz"
    try:
        train_rel = str(train_path.relative_to(ROOT))
    except ValueError:
        train_rel = str(train_path)
    save_level_a(
        ckpt,
        fly_a,
        tok,
        meta={"train": train_rel, "ce_a": ce_a, "train_lines": len(train_lines)},
    )
    print(f"\nwrote {ckpt}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    try:
        held_rel = str(held_path.relative_to(ROOT))
    except ValueError:
        held_rel = str(held_path)
    payload = {
        "stamp": stamp,
        "train_path": train_rel,
        "held_path": held_rel,
        "train_lines": len(train_lines),
        "held_lines": len(held),
        "vocab": tok.size,
        "max_pairs_a": max_a,
        "max_pairs_b": max_b,
        "ce": {
            "level_a_fly": ce_a,
            "level_b_fly": ce_b,
            "scramble_a": ce_s,
            "no_fly": ce_n,
            "b_minus_a": ce_b - ce_a,
        },
        "b_win_margin": B_WIN_MARGIN,
        "b_wins": b_wins,
        "gate": gate,
        "readable_a_samples": readable_a,
        "sample_count": len(samples),
        "samples": samples,
        "checkpoint": str(ckpt),
    }
    out = artifacts / f"run-{stamp}.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (artifacts / "latest.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

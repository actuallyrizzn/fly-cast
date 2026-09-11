#!/usr/bin/env python3
"""Reaction free-write climb: Level A honesty + Level B gate (CPU).

  . .venv/bin/activate && python tools/climb_reaction_freewrite.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from flycast.brain import build_fly_brain, build_no_fly
from flycast.generate import generate
from flycast.tokenizer import Tokenizer
from flycast.train import eval_fly_ce, train_fly_level_a, train_fly_level_b, train_no_fly

PROFILE = ROOT / "examples" / "fly_hero"
TRAIN_PATH = PROFILE / "fixtures" / "reaction_train.txt"
HELD_PATH = PROFILE / "fixtures" / "reaction_heldout.txt"
ARTIFACTS = ROOT / "artifacts" / "reaction-climb"
B_WIN_MARGIN = 0.05
SAMPLE_PROMPTS = ("Missed it", "Song starting", "Streak going", "That's a wrap", "On time")


def _lines(path: Path) -> list[str]:
    return [
        ln.strip()
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]


def main() -> int:
    train_lines = _lines(TRAIN_PATH)
    held = _lines(HELD_PATH)
    train_lower = {ln.lower() for ln in train_lines}
    leaked = [h for h in held if h.lower() in train_lower]
    if leaked:
        raise SystemExit(f"held-out leak into train: {leaked}")

    tok = Tokenizer.build(train_lines + held, max_vocab=800)

    fly_a = build_fly_brain(vocab_size=tok.size, seed=0, scrambled=False)
    fly_b = build_fly_brain(vocab_size=tok.size, seed=0, scrambled=False)
    fly_b.embed = fly_a.embed.copy()
    scr = build_fly_brain(vocab_size=tok.size, seed=0, scrambled=True)
    scr.embed = fly_a.embed.copy()
    nof = build_no_fly(vocab_size=tok.size, seed=0)

    train_fly_level_a(fly_a, tok, train_lines, max_pairs=1200)
    fly_b.readout = fly_a.readout.copy()
    if hasattr(fly_a, "_logit_bias"):
        fly_b._logit_bias = fly_a._logit_bias.copy()
    train_fly_level_b(fly_b, tok, train_lines, epochs=8, lr=0.03, max_pairs=800, seed=0)
    train_fly_level_a(scr, tok, train_lines, max_pairs=1200)
    train_no_fly(nof, tok, train_lines, max_pairs=1200)

    ce_a = eval_fly_ce(fly_a, tok, held, max_pairs=400)
    ce_b = eval_fly_ce(fly_b, tok, held, max_pairs=400)
    ce_s = eval_fly_ce(scr, tok, held, max_pairs=400)
    # no-fly eval via pair NLL on held contexts
    from flycast.train import _nll, _pairs

    nof_pairs = _pairs(tok, held, max_pairs=400)
    ce_n = sum(_nll(nof.logits(ctx), t) for ctx, t in nof_pairs) / max(len(nof_pairs), 1)

    samples: dict[str, dict[str, str]] = {}
    for prompt in SAMPLE_PROMPTS:
        samples[prompt] = {
            "A": generate(fly_a, tok, prompt, max_tokens=12, seed=1, temperature=0.8),
            "B": generate(fly_b, tok, prompt, max_tokens=12, seed=1, temperature=0.8),
        }

    b_wins = ce_b < ce_a - B_WIN_MARGIN
    gate = (
        "B_WINS — Level C may start; picker stays Fly Hero live default until free-write flag."
        if b_wins
        else "B_LOSES — stay on A + picker live; iterate corpus/hyperparams; do not open Level C."
    )

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
    print("\n=== Samples ===")
    for prompt, pair in samples.items():
        print(f"A | {prompt!r} → {pair['A']}")
        print(f"B | {prompt!r} → {pair['B']}")

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "stamp": stamp,
        "train_path": str(TRAIN_PATH.relative_to(ROOT)),
        "held_path": str(HELD_PATH.relative_to(ROOT)),
        "train_lines": len(train_lines),
        "held_lines": len(held),
        "vocab": tok.size,
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
        "samples": samples,
    }
    out = ARTIFACTS / f"run-{stamp}.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    latest = ARTIFACTS / "latest.json"
    latest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {out.relative_to(ROOT)}")
    print(f"wrote {latest.relative_to(ROOT)}")
    return 0 if True else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Compare Level A vs Level B on held-out reaction prompts (CPU).

  . .venv/bin/activate && python tools/compare_level_b.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from flycast.brain import build_fly_brain, build_no_fly
from flycast.generate import generate
from flycast.tokenizer import Tokenizer
from flycast.train import eval_fly_ce, train_fly_level_a, train_fly_level_b, train_no_fly


def _lines(path: Path) -> list[str]:
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]


def main() -> int:
    train_lines = _lines(ROOT / "fixtures" / "tinystories_subset.txt")[:30]
    held = _lines(ROOT / "examples" / "fly_hero" / "fixtures" / "reaction_heldout.txt")
    # Include held text in vocab so CE is defined; train excludes held lines.
    tok = Tokenizer.build(train_lines + held, max_vocab=800)

    fly_a = build_fly_brain(vocab_size=tok.size, seed=0, scrambled=False)
    fly_b = build_fly_brain(vocab_size=tok.size, seed=0, scrambled=False)
    fly_b.embed = fly_a.embed.copy()
    scr = build_fly_brain(vocab_size=tok.size, seed=0, scrambled=True)
    scr.embed = fly_a.embed.copy()
    nof = build_no_fly(vocab_size=tok.size, seed=0)

    train_fly_level_a(fly_a, tok, train_lines, max_pairs=400)
    # Level B starts from Level A readout then trains embed+readout
    fly_b.readout = fly_a.readout.copy()
    if hasattr(fly_a, "_logit_bias"):
        fly_b._logit_bias = fly_a._logit_bias.copy()
    train_fly_level_b(fly_b, tok, train_lines, epochs=6, lr=0.03, max_pairs=300, seed=0)
    train_fly_level_a(scr, tok, train_lines, max_pairs=400)
    train_no_fly(nof, tok, train_lines, max_pairs=400)

    ce_a = eval_fly_ce(fly_a, tok, held, max_pairs=200)
    ce_b = eval_fly_ce(fly_b, tok, held, max_pairs=200)
    ce_s = eval_fly_ce(scr, tok, held, max_pairs=200)

    print("=== Honesty table (held-out reaction CE, lower better) ===")
    print(f"Level A fly:     {ce_a:.4f}")
    print(f"Level B fly:     {ce_b:.4f}")
    print(f"Scramble (A):    {ce_s:.4f}")
    print(f"B vs A delta:    {ce_b - ce_a:+.4f} (negative means B better)")

    print("\n=== Samples (prompt → continuation) ===")
    for prompt in ("Missed it", "Song starting", "Streak going"):
        a = generate(fly_a, tok, prompt, max_tokens=12, seed=1, temperature=0.8)
        b = generate(fly_b, tok, prompt, max_tokens=12, seed=1, temperature=0.8)
        print(f"A | {prompt!r} → {a}")
        print(f"B | {prompt!r} → {b}")

    b_wins = ce_b < ce_a - 0.05
    print("\n=== Gate call ===")
    if b_wins:
        print("CALL: B becomes default free-write candidate; keep picker as live fallback.")
    else:
        print("CALL: stay on A + picker as live default; B experimental only. Do not open Level C.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

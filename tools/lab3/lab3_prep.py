#!/usr/bin/env python3
"""Lab 3 data prep — Lab 2 cycle-23 corpus + frozen Lab 2 valid/held-out/floors.

  python tools/lab3/lab3_prep.py \\
    --lab2-run artifacts/lab2/grok-runs/run-20260912T071531Z --last-cycle 23
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAB2 = ROOT / "artifacts" / "lab2"
LAB3 = ROOT / "artifacts" / "lab3"
DATA = LAB3 / "data"


def read_lines(path: Path) -> list[str]:
    return [
        ln.strip()
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lab2-run", type=Path, required=True)
    ap.add_argument("--last-cycle", type=int, default=23)
    args = ap.parse_args()
    run = args.lab2_run if args.lab2_run.is_absolute() else ROOT / args.lab2_run
    train_src = run / f"cycle-{args.last_cycle}" / "reaction_train_clean.txt"
    if not train_src.is_file():
        raise SystemExit(f"missing {train_src}")

    DATA.mkdir(parents=True, exist_ok=True)
    train = read_lines(train_src)
    # Prefer post-apply corpus size from summary if present
    summ = run / f"cycle-{args.last_cycle}" / "summary.json"
    if summ.is_file():
        rec = json.loads(summ.read_text(encoding="utf-8"))
        n_after = rec.get("corpus_after_apply")
        if isinstance(n_after, int) and n_after < len(train):
            # summary out-count may exclude header-only diffs; keep file as truth
            pass

    valid = read_lines(LAB2 / "data" / "valid.txt")
    held = read_lines(LAB2 / "data" / "heldout.txt")
    gold = read_lines(LAB2 / "data" / "gold_keep.txt")
    # no leak into train
    tl = {t.lower() for t in train}
    valid = [v for v in valid if v.lower() not in tl]
    held = [h for h in held if h.lower() not in tl]
    held_l = {h.lower() for h in held} | {v.lower() for v in valid}
    gold = [g for g in gold if g.lower() not in held_l]

    (DATA / "train.txt").write_text(
        f"# Lab 3 train — from Lab 2 {run.name} cycle-{args.last_cycle}\n"
        + "\n".join(train)
        + "\n",
        encoding="utf-8",
    )
    (DATA / "valid.txt").write_text(
        "# Lab 3 valid — same as Lab 2 (tuning only)\n" + "\n".join(valid) + "\n",
        encoding="utf-8",
    )
    (DATA / "heldout.txt").write_text(
        "# Lab 3 held-out — same as Lab 2 (report only)\n" + "\n".join(held) + "\n",
        encoding="utf-8",
    )
    (DATA / "gold_keep.txt").write_text(
        "# Grok gold (train-side)\n" + "\n".join(gold) + "\n",
        encoding="utf-8",
    )
    if (LAB2 / "baselines.json").is_file():
        shutil.copy2(LAB2 / "baselines.json", LAB3 / "baselines.json")

    meta = {
        "lab": 3,
        "source_lab2_run": run.name,
        "source_cycle": args.last_cycle,
        "train": len(train),
        "valid": len(valid),
        "heldout": len(held),
        "gold_keep": len(gold),
        "spec": {
            "train": "softmax Level B (frozen W; embed + readout; CE)",
            "data": "Lab 2 end corpus; Lab 2 valid/held-out frozen",
            "floors": "scramble + bigram (+ trigram logged)",
            "loop": "+5 on any earn, cap 40, local Grok on FlyBrain",
        },
    }
    (DATA / "split.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

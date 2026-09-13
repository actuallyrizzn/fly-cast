#!/usr/bin/env python3
"""Lab 2 phase 0a — build a real data split from the Lab 1 end-state corpus.

  python tools/lab2/lab2_split.py --run artifacts/grok-judge/run-20260912T045201Z --last-cycle 8

Outputs artifacts/lab2/data/{train,valid,heldout,gold_keep}.txt + split.json
  * held-out ≥ 500 cue-prefixed lines, stratified by cue (Lab 1 had 10, off-distribution)
  * valid ~300 for ridge λ / gain / n-gram interpolation tuning (never touch held-out for tuning)
  * gold_keep = every line Grok marked KEEP (+ REWRITE outputs) across Lab 1 cycles
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from common import DATA, ROOT, cue_of, jdump, read_lines, stratified_split  # noqa: E402

sys.path.insert(0, str(ROOT / "src"))
from flycast.mouth_taste import split_cue  # noqa: E402


def lab1_end_corpus(run_dir: Path, last_cycle: int) -> list[str]:
    """Corpus AFTER the last cycle's Grok apply (= what cycle N+1 would have trained on)."""
    from flybrain_grok_loop import _apply_grades  # noqa: WPS433

    train = read_lines(run_dir / f"cycle-{last_cycle}" / "reaction_train_clean.txt")
    grades_p = run_dir / f"cycle-{last_cycle}" / "out" / "grades.jsonl"
    grades = [json.loads(l) for l in grades_p.read_text(encoding="utf-8").splitlines() if l.strip()]
    corpus, stats = _apply_grades(train, grades)
    print(f"lab1 end corpus: {stats['in']} → {stats['out']} lines after cycle-{last_cycle} apply")
    return corpus


def gold_from_grades(run_dir: Path) -> list[str]:
    gold: list[str] = []
    seen: set[str] = set()
    for gp in sorted(run_dir.glob("cycle-*/out/grades.jsonl")):
        for ln in gp.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            g = json.loads(ln)
            v = (g.get("verdict") or "").upper()
            cue = (g.get("cue") or "").strip().upper()
            text = (g.get("rewrite") if v == "REWRITE" else g.get("text")) or ""
            text = text.strip()
            if not text or v not in ("KEEP", "REWRITE"):
                continue
            c2, rest = split_cue(text)
            if c2:
                cue, text = c2, rest
            if not cue:
                continue
            line = f"{cue} {text}".strip()
            k = line.lower()
            if k not in seen:
                seen.add(k)
                gold.append(line)
    return gold


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, default=ROOT / "artifacts/grok-judge/run-20260912T045201Z")
    ap.add_argument("--last-cycle", type=int, default=8)
    ap.add_argument("--heldout", type=int, default=520)
    ap.add_argument("--valid", type=int, default=320)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    run_dir = args.run if args.run.is_absolute() else ROOT / args.run

    corpus = lab1_end_corpus(run_dir, args.last_cycle)
    # drop cue-less junk lines
    corpus = [ln for ln in corpus if cue_of(ln).isupper() and len(ln.split()) >= 2]
    train, valid, held = stratified_split(corpus, heldout_n=args.heldout, valid_n=args.valid, seed=args.seed)

    # leak guards
    tl = {t.lower() for t in train}
    assert not any(h.lower() in tl for h in held), "held-out leaked into train"
    assert not any(v.lower() in tl for v in valid), "valid leaked into train"
    legacy = read_lines(ROOT / "examples/fly_hero/fixtures/reaction_heldout.txt")

    gold = gold_from_grades(run_dir)
    held_l = {h.lower() for h in held} | {v.lower() for v in valid}
    gold = [g for g in gold if g.lower() not in held_l]  # gold may only touch train

    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "train.txt").write_text("# Lab 2 train (from Lab 1 cycle-%d end state)\n" % args.last_cycle + "\n".join(train) + "\n", encoding="utf-8")
    (DATA / "valid.txt").write_text("# Lab 2 valid — tuning only\n" + "\n".join(valid) + "\n", encoding="utf-8")
    (DATA / "heldout.txt").write_text("# Lab 2 held-out — report only, never tune on this\n" + "\n".join(held) + "\n", encoding="utf-8")
    (DATA / "heldout_legacy10.txt").write_text("\n".join(legacy) + "\n", encoding="utf-8")
    (DATA / "gold_keep.txt").write_text("# Grok KEEP + REWRITE outputs across Lab 1 (train-side only)\n" + "\n".join(gold) + "\n", encoding="utf-8")

    meta = {
        "source_run": run_dir.name,
        "last_cycle": args.last_cycle,
        "corpus_lines": len(corpus),
        "train": len(train),
        "valid": len(valid),
        "heldout": len(held),
        "gold_keep": len(gold),
        "cues_heldout": dict(Counter(cue_of(h) for h in held).most_common()),
        "cues_train": dict(Counter(cue_of(t) for t in train).most_common()),
        "seed": args.seed,
    }
    jdump(DATA / "split.json", meta)
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

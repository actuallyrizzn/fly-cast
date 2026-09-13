#!/usr/bin/env python3
"""Lab 5 (desk) — corpus JSONL → fly-cast line format, regime-aware split, n-gram floors.

Line format (same tokenizer pipeline as Lab 2–4; cue = first token):
  DESK <situation> => <GO|NOGO> : <rationale>

Split:
  heldout.txt      Grok rows whose (structure, flows, calendar) regime combo is NEVER in train
  valid.txt        random 4% of remaining Grok rows (early-stop signal)
  train.txt        the rest
  heldout_gold.txt Astra-labelled rows (different teacher; decision-accuracy eval only)
  baselines.json   uniform / unigram / bigram / trigram floors on heldout.txt (train-only vocab)

  python tools/lab5/desk/lab5_desk_prep.py
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "lab2"))
sys.path.insert(0, str(ROOT / "src"))
from common import NGram, build_tokenizer, encode_lines, jdump, n_pairs, uniform_ce  # noqa: E402

DESK = ROOT / "artifacts" / "lab5" / "desk"
DATA = DESK / "data"
BULK = DESK / "desk_corpus_grok.jsonl"
GOLD = DESK / "desk_gold_astra.jsonl"


def rows(path: Path) -> list[dict]:
    out = []
    if not path.is_file():
        return out
    for ln in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out


def fmt(r: dict) -> str:
    d = "GO" if r["decision"] == "GO" else "NOGO"
    sit = " ".join(r["situation"].split())
    rat = " ".join(r["rationale"].split()).rstrip(".")
    return f"DESK {sit} => {d} : {rat}"


def combo(r: dict) -> tuple[str, str, str]:
    t = r.get("tags") or []
    # tags order: track, venue, chain, structure, flows, calendar, risk, venue_health, confluence, trigger
    return (t[3], t[4], t[5]) if len(t) >= 6 else ("", "", "")


def main() -> int:
    rng = random.Random(5)
    bulk = rows(BULK)
    gold = rows(GOLD)
    if not bulk:
        raise SystemExit(f"no bulk corpus at {BULK}")
    DATA.mkdir(parents=True, exist_ok=True)

    combos = Counter(combo(r) for r in bulk)
    keys = [k for k in combos if k[0]]
    rng.shuffle(keys)
    held_keys: set[tuple[str, str, str]] = set()
    n_held = 0
    for k in keys:  # take whole regime combos until ~4% of rows are held out
        if n_held >= 0.04 * len(bulk):
            break
        held_keys.add(k)
        n_held += combos[k]

    held = [r for r in bulk if combo(r) in held_keys]
    rest = [r for r in bulk if combo(r) not in held_keys]
    rng.shuffle(rest)
    n_valid = max(500, int(0.04 * len(rest)))
    valid, train = rest[:n_valid], rest[n_valid:]

    files = {
        "train.txt": train, "valid.txt": valid, "heldout.txt": held, "heldout_gold.txt": gold,
    }
    for name, rs in files.items():
        (DATA / name).write_text("\n".join(fmt(r) for r in rs) + "\n", encoding="utf-8")

    tr_l = [fmt(r) for r in train]
    tok = build_tokenizer(tr_l)
    tr, va, he = (encode_lines(tok, [fmt(r) for r in rs]) for rs in (train, valid, held))
    V = tok.size
    out = {
        "vocab": V,
        "lines": {k: len(v) for k, v in files.items()},
        "pairs": {"train": n_pairs(tr), "valid": n_pairs(va), "heldout": n_pairs(he)},
        "held_regime_combos": len(held_keys),
        "decision_mix": {
            "train": dict(Counter(r["decision"] for r in train)),
            "heldout": dict(Counter(r["decision"] for r in held)),
            "gold": dict(Counter(r["decision"] for r in gold)),
        },
        "uniform_ce": uniform_ce(V),
        "models": {},
    }
    print(f"vocab={V} lines={out['lines']} pairs={out['pairs']} held_combos={len(held_keys)}")
    for order, name in ((1, "unigram"), (2, "bigram"), (3, "trigram")):
        m = NGram(order=order).fit(tr, V).tune(va)
        vce, hce = m.ce(va), m.ce(he)
        out["models"][name] = {"valid_ce": vce, "heldout_ce": hce, "lams": m.lams, "k": m.k}
        print(f"{name:8s} valid {vce:.3f}  held {hce:.3f}")
    jdump(DESK / "baselines.json", out)
    tok.save(DATA / "tokenizer.json")
    print(f"wrote {DATA} + {DESK / 'baselines.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

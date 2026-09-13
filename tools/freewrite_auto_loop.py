#!/usr/bin/env python3
"""Automatic free-write improvement loop.

Cycle: filter corpus (Athena mouth-taste) → climb train → grade samples
       → hybrid probe → keep best → iterate until pass or max rounds.

  . .venv/bin/activate
  python tools/freewrite_auto_loop.py --rounds 3

Picker stays live default. Loop only improves additive free-write / hybrid.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from flycast.checkpoint import load_level_a
from flycast.hybrid import hybrid_write
from flycast.mouth_taste import filter_corpus_lines, grade_text
from flycast.prompt import Event
from flycast.write import freewrite

PROFILE = ROOT / "examples" / "fly_hero"
DEFAULT_TRAIN = PROFILE / "fixtures" / "reaction_train.txt"
DEFAULT_HELD = PROFILE / "fixtures" / "reaction_heldout.txt"
ART_ROOT = ROOT / "artifacts" / "freewrite-loop"

PROBE_CUES = ("MISS", "HIT", "STREAK", "SONG_START", "SONG_END", "OVERSTRUM")


def _load_lines(path: Path) -> list[str]:
    return [
        ln.strip()
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]


def _write_corpus(path: Path, lines: list[str], *, note: str) -> None:
    header = (
        f"# Filtered reaction corpus — freewrite auto-loop\n"
        f"# {note}\n"
        f"# Held-out stays in reaction_heldout.txt — do not copy here.\n\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")


def _run_climb(train: Path, artifacts: Path, max_a: int, max_b: int) -> dict:
    artifacts.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(ROOT / "tools" / "climb_reaction_freewrite.py"),
        "--train",
        str(train),
        "--heldout",
        str(DEFAULT_HELD),
        "--artifacts",
        str(artifacts),
        "--max-pairs-a",
        str(max_a),
        "--max-pairs-b",
        str(max_b),
        "--epochs-b",
        "2",
    ]
    log = artifacts / "climb.log"
    with log.open("w", encoding="utf-8") as fh:
        proc = subprocess.run(cmd, cwd=str(ROOT), stdout=fh, stderr=subprocess.STDOUT, check=False)
    latest = artifacts / "latest.json"
    if not latest.is_file():
        raise RuntimeError(f"climb failed (exit {proc.returncode}); see {log}")
    return json.loads(latest.read_text(encoding="utf-8"))


def _probe(ckpt: Path) -> dict:
    brain, tok = load_level_a(ckpt)
    free_ok = 0
    hybrid_ok = 0
    rows = []
    for i, cue in enumerate(PROBE_CUES):
        events = [Event(cue=cue, detail="")]
        fw = freewrite(brain, tok, events, seed=10 + i, temperature=0.7)
        hy = hybrid_write(brain, tok, events, k=5, seed=20 + i, temperature=0.85)
        g_fw = grade_text(fw.text)
        g_hy = grade_text(hy.text)
        free_ok += int(g_fw.ok)
        hybrid_ok += int(g_hy.ok)
        rows.append(
            {
                "cue": cue,
                "freewrite": fw.text,
                "freewrite_ok": g_fw.ok,
                "freewrite_score": g_fw.score,
                "hybrid": hy.text,
                "hybrid_ok": g_hy.ok,
                "hybrid_score": g_hy.score,
                "hybrid_rank": hy.score,
            }
        )
    n = len(PROBE_CUES)
    return {
        "freewrite_pass": free_ok / n,
        "hybrid_pass": hybrid_ok / n,
        "rows": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-train", type=Path, default=DEFAULT_TRAIN)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--pass-threshold", type=float, default=0.67, help="hybrid sample pass rate to stop")
    ap.add_argument("--max-pairs-a", type=int, default=6000)
    ap.add_argument("--max-pairs-b", type=int, default=3000)
    ap.add_argument("--min-corpus", type=int, default=800)
    ap.add_argument("--out-dir", type=Path, default=ART_ROOT)
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.out_dir / f"run-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    source = args.source_train if args.source_train.is_absolute() else ROOT / args.source_train
    raw = _load_lines(source)
    history: list[dict] = []
    best: dict | None = None

    for rnd in range(1, args.rounds + 1):
        round_dir = run_dir / f"round-{rnd}"
        round_dir.mkdir(parents=True, exist_ok=True)

        # Tighten filter each round: drop bottom score band by re-grading
        filtered = filter_corpus_lines(raw)
        if rnd > 1 and best and best.get("probe"):
            # Prefer lines that look like winning hybrid samples' vocabulary
            prefer = set()
            for row in best["probe"]["rows"]:
                if row["hybrid_ok"]:
                    for w in row["hybrid"].lower().split():
                        if len(w) > 2:
                            prefer.add(w)
            if prefer:
                boosted = []
                rest = []
                for ln in filtered:
                    body = ln.split(None, 1)[-1].lower()
                    if any(w in body for w in prefer):
                        boosted.append(ln)
                    else:
                        rest.append(ln)
                # keep all boosted + a slice of rest for diversity
                filtered = boosted + rest[: max(0, args.min_corpus - len(boosted))]

        if len(filtered) < args.min_corpus:
            # Fall back to previous raw filter without boost
            filtered = filter_corpus_lines(raw)

        train_path = round_dir / "reaction_train_clean.txt"
        _write_corpus(
            train_path,
            filtered,
            note=f"round={rnd} from={source.name} kept={len(filtered)}/{len(raw)}",
        )

        # Seal: no held-out leak
        held = {h.lower() for h in _load_lines(DEFAULT_HELD)}
        leak = [ln for ln in filtered if ln.lower() in held]
        if leak:
            raise SystemExit(f"held-out leak after filter: {leak[:5]}")

        climb_dir = round_dir / "climb"
        climb = _run_climb(train_path, climb_dir, args.max_pairs_a, args.max_pairs_b)
        ckpt = Path(climb["checkpoint"])
        if not ckpt.is_file():
            ckpt = climb_dir / "level_a.npz"
        probe = _probe(ckpt)

        honesty_ok = (
            climb["ce"]["level_a_fly"] < climb["ce"]["scramble_a"]
            and climb["ce"]["level_a_fly"] < climb["ce"]["no_fly"]
        )
        record = {
            "round": rnd,
            "corpus_lines": len(filtered),
            "climb": {
                "ce": climb["ce"],
                "b_wins": climb["b_wins"],
                "gate": climb["gate"],
                "honesty_ok": honesty_ok,
            },
            "probe": probe,
            "train_path": str(train_path.relative_to(ROOT)),
            "checkpoint": str(ckpt),
        }
        (round_dir / "summary.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        history.append(record)

        score = (
            probe["hybrid_pass"] * 2.0
            + probe["freewrite_pass"]
            + (0.5 if honesty_ok else 0.0)
            + (0.25 if not climb["b_wins"] else 0.0)  # B win is bonus later; honesty first
        )
        record["loop_score"] = score
        if best is None or score > best.get("loop_score", -1):
            best = record

        print(
            f"round {rnd}/{args.rounds}: kept={len(filtered)} "
            f"honesty={'OK' if honesty_ok else 'FAIL'} "
            f"free={probe['freewrite_pass']:.2f} hybrid={probe['hybrid_pass']:.2f} "
            f"A={climb['ce']['level_a_fly']:.3f} BΔ={climb['ce']['b_minus_a']:+.3f}",
            flush=True,
        )

        if probe["hybrid_pass"] >= args.pass_threshold and honesty_ok:
            print("PASS threshold met — stopping early", flush=True)
            break

        # Next round source = this filtered set (compounding cleanup)
        raw = filtered

    # Promote best clean corpus + checkpoint into main artifacts paths
    assert best is not None
    promo_train = PROFILE / "fixtures" / "reaction_train_clean.txt"
    best_train = ROOT / best["train_path"]
    promo_train.write_text(best_train.read_text(encoding="utf-8"), encoding="utf-8")
    best_ckpt = Path(best["checkpoint"])
    promo_art = ROOT / "artifacts" / "reaction-climb-loop"
    promo_art.mkdir(parents=True, exist_ok=True)
    for name in ("level_a.npz", "level_a.tok.json", "latest.json"):
        src = best_ckpt.parent / name
        if src.is_file():
            (promo_art / name).write_bytes(src.read_bytes())

    final = {
        "stamp": stamp,
        "run_dir": str(run_dir.relative_to(ROOT)),
        "best_round": best["round"],
        "best": best,
        "history": history,
        "promoted_train": str(promo_train.relative_to(ROOT)),
        "promoted_artifacts": str(promo_art.relative_to(ROOT)),
        "live_default": "picker",
        "additive_modes": ["freewrite", "hybrid"],
    }
    (run_dir / "final.json").write_text(json.dumps(final, indent=2) + "\n", encoding="utf-8")
    (args.out_dir / "latest.json").write_text(json.dumps(final, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"best_round": best["round"], "hybrid_pass": best["probe"]["hybrid_pass"], "out": str(run_dir)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

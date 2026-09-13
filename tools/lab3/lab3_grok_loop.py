#!/usr/bin/env python3
"""Lab 3 Grok loop — softmax Level B on FlyBrain. Same earn rules (+5 / cap 40).

Spec (Mark 2026-09-12):
  * Data: Lab 2 end corpus; Lab 2 valid/held-out frozen
  * Train: ridge → softmax Level A → softmax Level B (frozen W; embed+readout; CE)
  * Floors: scramble + bigram (+ trigram logged)
  * Judge: local Grok; chronicle Doc #1331

  On FlyBrain:
    cd /root/fly-cast && . .venv/bin/activate
    nohup python -u tools/lab3/lab3_grok_loop.py --cycles 8 --extend-by 5 --max-total-cycles 40 \\
      >> artifacts/lab3/lab3-grok-loop.log 2>&1 &
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools" / "lab3"))
sys.path.insert(0, str(ROOT / "tools" / "lab2"))
sys.path.insert(0, str(ROOT / "tools"))

from flycast.mouth_taste import filter_corpus_lines, grade_text, split_cue  # noqa: E402

from common import ReservoirCfg, generate_fast, jdump, read_lines  # noqa: E402
from level_b import LAB3, DATA, train_lab3  # noqa: E402

JUDGE = Path("/root/flycast-mouth-judge")
MODEL_DEFAULT = "cursor-grok-4.6-high-fast"
PROBE_CUES = ("MISS", "HIT", "STREAK", "SONG_START", "SONG_END", "OVERSTRUM")
ATHENA_BRIEF = ROOT / "examples" / "fly_hero" / "docs" / "MOUTH-TASTE-ATHENA.md"
JUDGE_MD = ROOT / "artifacts" / "grok-judge" / "JUDGE.md"

ATHENA_SEED = [
    "MISS blue at 67%, cope.",
    "MISS choked on the sustain.",
    "MISS tap on red, gone.",
    "MISS off by one, again.",
    "MISS blue at the chorus, rip.",
    "STREAK still cooking.",
    "STREAK clean clean clean.",
    "STREAK untouched so far.",
]


def _log(msg: str) -> None:
    print(msg, flush=True)


def _load_grades(path: Path) -> list[dict]:
    """Parse grades.jsonl; skip blank/corrupt lines (Lab 2 crash fix)."""
    rows: list[dict] = []
    raw = path.read_text(encoding="utf-8", errors="replace")
    for i, ln in enumerate(raw.splitlines(), 1):
        s = ln.strip()
        if not s:
            continue
        try:
            rows.append(json.loads(s))
        except json.JSONDecodeError:
            _log(f"  grades.jsonl: skip bad line {i}")
    return rows


def _cycle_improved(curr: dict, prev: dict) -> tuple[bool, str]:
    reasons: list[str] = []
    cg, pg = curr.get("grok") or {}, prev.get("grok") or {}
    cf, pf = curr.get("fly") or {}, prev.get("fly") or {}

    def rate(d, k, n):
        kk, nn = d.get(k), d.get(n)
        if nn:
            return (kk or 0) / nn
        return 0.0

    pt, ct = rate(pg, "train_keep", "train_n"), rate(cg, "train_keep", "train_n")
    if ct > pt + 0.02:
        reasons.append(f"train_keep {pt:.2f}→{ct:.2f}")
    ps, cs = pg.get("train_salvage_rate", 0.0) or 0.0, cg.get("train_salvage_rate", 0.0) or 0.0
    if cs > ps + 0.02:
        reasons.append(f"train_salvage {ps:.2f}→{cs:.2f}")
    pp, cp = rate(pg, "probe_keep", "probe_n"), rate(cg, "probe_keep", "probe_n")
    if cp > pp + 0.01:
        reasons.append(f"probe_keep {pp:.2f}→{cp:.2f}")
    pce, cce = pf.get("heldout_ce"), cf.get("heldout_ce")
    if isinstance(pce, (int, float)) and isinstance(cce, (int, float)) and cce < pce - 0.02:
        reasons.append(f"held_CE {pce:.3f}→{cce:.3f}")
    if cf.get("honesty_ok") and not pf.get("honesty_ok"):
        reasons.append("honesty FAIL→OK")
    if cf.get("beats_bigram") and not pf.get("beats_bigram"):
        reasons.append("beats_bigram")
    if cf.get("beats_trigram") and not pf.get("beats_trigram"):
        reasons.append("beats_trigram")
    return (bool(reasons), "; ".join(reasons) if reasons else "flat/regress")


def _apply_grades(corpus: list[str], grades: list[dict]) -> tuple[list[str], dict]:
    cut_bodies: set[str] = set()
    rewrites: dict[str, str] = {}
    probe_keep = probe_n = 0
    train_n = train_keep = train_rewrite = train_cut = 0
    for g in grades:
        text = (g.get("text") or "").strip()
        verdict = (g.get("verdict") or "").upper()
        src = g.get("source") or ""
        if src == "probe":
            probe_n += 1
            if verdict == "KEEP":
                probe_keep += 1
        if src == "train":
            train_n += 1
            if verdict == "KEEP":
                train_keep += 1
            elif verdict == "REWRITE":
                train_rewrite += 1
            elif verdict == "CUT":
                train_cut += 1
        if not text:
            continue
        body = text.lower()
        if verdict == "CUT":
            cut_bodies.add(body)
        elif verdict == "REWRITE" and g.get("rewrite"):
            rewrites[body] = str(g["rewrite"]).strip()

    out: list[str] = []
    seen: set[str] = set()
    for ln in ATHENA_SEED + corpus:
        cue, rest = split_cue(ln)
        body = (rest or ln).strip().lower()
        if body in cut_bodies:
            continue
        if body in rewrites:
            rw = rewrites[body]
            c2, r2 = split_cue(rw)
            line = f"{(c2 or cue or 'MISS')} {r2 or rw}".strip()
        else:
            line = ln
        k = line.lower()
        if k not in seen:
            seen.add(k)
            out.append(line)
    stats = {
        "in": len(corpus),
        "out": len(out),
        "probe_keep": probe_keep,
        "probe_n": probe_n,
        "probe_keep_rate": (probe_keep / probe_n) if probe_n else 0.0,
        "train_keep": train_keep,
        "train_n": train_n,
        "train_rewrite": train_rewrite,
        "train_cut": train_cut,
        "train_keep_rate": (train_keep / train_n) if train_n else 0.0,
        "train_salvage_rate": ((train_keep + train_rewrite) / train_n) if train_n else 0.0,
    }
    return out, stats


def _probe(train_info: dict) -> dict:
    res, ro, tok = train_info["res"], train_info["ro"], train_info["tok"]
    rows = []
    free_ok = hy_ok = 0
    for i, cue in enumerate(PROBE_CUES):
        fw = generate_fast(res, ro, tok, cue, mode="temp", seed=10 + i, temperature=0.85)
        hy = generate_fast(res, ro, tok, cue, mode="topk", seed=20 + i, top_k=8, temperature=0.8)
        g_fw = grade_text(fw, cue=cue)
        g_hy = grade_text(hy, cue=cue)
        free_ok += int(g_fw.ok)
        hy_ok += int(g_hy.ok)
        rows.append({"cue": cue, "freewrite": fw, "hybrid": hy, "local_fw_ok": g_fw.ok, "local_hy_ok": g_hy.ok})
    n = len(PROBE_CUES)
    return {"local_freewrite_pass": free_ok / n, "local_hybrid_pass": hy_ok / n, "rows": rows}


def _pack_inbox(cycle_dir: Path, probe: dict, train_lines: list[str], n_train: int) -> None:
    inbox = cycle_dir / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    p_lines = ["# Probe samples — grade KEEP/CUT/REWRITE", ""]
    for row in probe["rows"]:
        p_lines += [f"## cue={row['cue']}", f"FREEWRITE: {row['freewrite']}", f"HYBRID: {row['hybrid']}", ""]
    (inbox / "01-probe-samples.md").write_text("\n".join(p_lines) + "\n", encoding="utf-8")
    rng = random.Random(42 + len(train_lines))
    sample = train_lines[:]
    rng.shuffle(sample)
    sample = sample[:n_train]
    (inbox / "03-train-slice.txt").write_text("\n".join(sample) + "\n", encoding="utf-8")


def _run_judge_once(cycle_dir: Path, model: str, timeout_s: int, *, attempt: int) -> list[dict]:
    """One Grok judge attempt. Returns parsed grades or raises."""
    inbox = cycle_dir / "inbox"
    out_local = cycle_dir / "out"
    out_local.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["bash", "-lc", f"rm -rf {JUDGE}/inbox {JUDGE}/out && mkdir -p {JUDGE}/inbox {JUDGE}/out {JUDGE}/artifacts"],
        check=True,
    )
    for f in sorted(inbox.iterdir()):
        subprocess.run(["cp", str(f), f"{JUDGE}/inbox/{f.name}"], check=True)
    if ATHENA_BRIEF.is_file():
        subprocess.run(["cp", str(ATHENA_BRIEF), f"{JUDGE}/MOUTH-TASTE.md"], check=True)
    if JUDGE_MD.is_file():
        subprocess.run(["cp", str(JUDGE_MD), f"{JUDGE}/JUDGE.md"], check=True)

    prompt = (
        "You are the Fly Cast mouth-taste judge. Read JUDGE.md and follow it exactly. "
        "You are not Otto. Grade all inbox samples against MOUTH-TASTE.md. "
        "Write out/grades.jsonl and out/SUMMARY.md. Be harsh on mush. "
        "CRITICAL for SUMMARY.md: one rates table is fine; everything OUTSIDE that table "
        "must be human-facing plain English — explain implications for the product mouth. "
        "When done, print a one-line BLUF: KEEP/CUT counts by source."
    )
    (cycle_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    subprocess.run(["cp", str(cycle_dir / "prompt.txt"), f"{JUDGE}/prompt.txt"], check=True)

    env = os.environ.copy()
    env["PATH"] = f"{Path.home() / '.local' / 'bin'}:{env.get('PATH', '')}"
    log = JUDGE / "artifacts" / "judge.log"
    with log.open("w", encoding="utf-8") as fh:
        proc = subprocess.Popen(
            ["agent", "--print", "--trust", "--force", "--workspace", str(JUDGE), "--model", model, prompt],
            cwd=str(JUDGE),
            stdout=fh,
            stderr=subprocess.STDOUT,
            env=env,
        )
    _log(f"  grok judge pid={proc.pid} model={model} (local) attempt={attempt}")

    deadline = time.time() + timeout_s
    last_size = -1
    stable = 0
    grades_path = JUDGE / "out" / "grades.jsonl"
    while time.time() < deadline:
        time.sleep(10)
        alive = proc.poll() is None
        if grades_path.is_file() and grades_path.stat().st_size > 0:
            size = grades_path.stat().st_size
            subprocess.run(["cp", str(grades_path), str(out_local / "grades.jsonl")], check=False)
            summ = JUDGE / "out" / "SUMMARY.md"
            if summ.is_file():
                subprocess.run(["cp", str(summ), str(out_local / "SUMMARY.md")], check=False)
            if size == last_size:
                stable += 1
            else:
                stable = 0
                last_size = size
            if (not alive) or stable >= 2:
                break
        elif not alive:
            subprocess.run(["cp", str(log), str(cycle_dir / "judge.log")], check=False)
            raise RuntimeError(f"judge died without grades; see {cycle_dir / 'judge.log'}")
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    local_grades = out_local / "grades.jsonl"
    if not local_grades.is_file():
        raise RuntimeError(f"judge timeout after {timeout_s}s")
    # keep a copy per attempt for forensics
    subprocess.run(
        ["cp", str(local_grades), str(out_local / f"grades.attempt{attempt}.jsonl")],
        check=False,
    )
    grades = _load_grades(local_grades)
    if len(grades) < 10:
        raise RuntimeError(f"grades too thin ({len(grades)} rows) — likely truncated/corrupt judge output")
    return grades


def _local_judge(cycle_dir: Path, model: str, timeout_s: int, *, max_attempts: int = 3) -> dict:
    """Grok judge with retries — Lab 2 died on empty/corrupt grades.jsonl."""
    last_err: Exception | None = None
    grades: list[dict] = []
    for attempt in range(1, max_attempts + 1):
        try:
            grades = _run_judge_once(cycle_dir, model, timeout_s, attempt=attempt)
            break
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            _log(f"  grok judge attempt {attempt}/{max_attempts} failed: {exc}")
            if attempt < max_attempts:
                _log("  retrying judge (same inbox)…")
                time.sleep(5)
    else:
        raise RuntimeError(f"judge failed after {max_attempts} attempts: {last_err}")

    try:
        from flycast_summary_human import ensure_human_summary

        cyc_n = None
        m = re.search(r"cycle-(\d+)", str(cycle_dir))
        if m:
            cyc_n = int(m.group(1))
        _, rewritten = ensure_human_summary(cycle_dir, grades, cycle=cyc_n)
        _log("  SUMMARY.md: Otto rewrote human prose" if rewritten else "  SUMMARY.md: human prose OK from Grok")
    except Exception as exc:  # noqa: BLE001
        _log(f"  SUMMARY human rewrite warn: {exc}")
    return {"grades": grades, "n": len(grades)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=8)
    ap.add_argument("--extend-by", type=int, default=5)
    ap.add_argument("--max-total-cycles", type=int, default=40)
    ap.add_argument("--probe-keep-threshold", type=float, default=0.5)
    ap.add_argument("--train-judge-n", type=int, default=80)
    ap.add_argument("--min-corpus", type=int, default=150)
    ap.add_argument("--judge-timeout", type=int, default=900)
    ap.add_argument("--model", default=MODEL_DEFAULT)
    ap.add_argument("--resume-run", type=Path, default=None)
    ap.add_argument("--level-b-epochs", type=int, default=8)
    ap.add_argument("--pairs-per-epoch", type=int, default=12000)
    ap.add_argument("--softmax-a-epochs", type=int, default=6)
    args = ap.parse_args()

    if not JUDGE.is_dir():
        raise SystemExit(f"missing {JUDGE}")
    if not (DATA / "train.txt").is_file():
        raise SystemExit(f"missing {DATA}/train.txt — run lab3_prep.py first")

    floors = {}
    bp = LAB3 / "baselines.json"
    if bp.is_file():
        floors = json.loads(bp.read_text()).get("models") or {}

    history: list[dict] = []
    best: dict | None = None
    cycle_budget = max(1, args.cycles)
    extensions = 0
    cyc = 0
    stop_reason = "budget_exhausted"
    cfg = ReservoirCfg(embed_dim=32, leak=0.5, steps=2, inject_count=64, seed=0)

    valid_lines = read_lines(DATA / "valid.txt")
    held_lines = read_lines(DATA / "heldout.txt")

    if args.resume_run:
        run_dir = args.resume_run if args.resume_run.is_absolute() else ROOT / args.resume_run
        stamp = run_dir.name.replace("run-", "") if run_dir.name.startswith("run-") else run_dir.name
        for summ_path in sorted(run_dir.glob("cycle-*/summary.json"), key=lambda p: int(p.parent.name.split("-")[1])):
            rec = json.loads(summ_path.read_text(encoding="utf-8"))
            history.append(rec)
            if best is None or rec.get("loop_score", -1) > best.get("loop_score", -1):
                best = rec
        for i in range(1, len(history)):
            improved, why = _cycle_improved(history[i], history[i - 1])
            history[i]["improved_vs_prev"] = improved
            history[i]["improve_why"] = why
        cyc = history[-1]["cycle"] if history else 0
        if history and not (run_dir / f"cycle-{cyc}" / "summary.json").is_file():
            cyc -= 1
        candidates = sorted(run_dir.glob("cycle-*/reaction_train_clean.txt"), key=lambda p: p.stat().st_mtime)
        corpus = read_lines(candidates[-1]) if candidates else read_lines(DATA / "train.txt")
        earn_count = sum(1 for h in history[1:] if h.get("improved_vs_prev"))
        extensions = earn_count
        cycle_budget = min(args.max_total_cycles, max(args.cycles + earn_count * args.extend_by, cyc + 1))
        _log(f"RESUME {run_dir.name}: next={cyc+1} corpus={len(corpus)} budget={cycle_budget}")
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = LAB3 / "grok-runs" / f"run-{stamp}"
        run_dir.mkdir(parents=True, exist_ok=True)
        raw = filter_corpus_lines(read_lines(DATA / "train.txt"))
        corpus, seen = [], set()
        for ln in ATHENA_SEED + raw:
            k = ln.lower()
            if k not in seen:
                seen.add(k)
                corpus.append(ln)
        (run_dir / "heldout.txt").write_text("\n".join(held_lines) + "\n", encoding="utf-8")
        (run_dir / "valid.txt").write_text("\n".join(valid_lines) + "\n", encoding="utf-8")
        jdump(run_dir / "floors.json", floors)
        _log(f"START Lab3 {run_dir.name} corpus={len(corpus)} held={len(held_lines)} budget={cycle_budget}")

    while cyc < cycle_budget and cyc < args.max_total_cycles:
        cyc += 1
        cycle_dir = run_dir / f"cycle-{cyc}"
        cycle_dir.mkdir(parents=True, exist_ok=True)
        _log(f"\n=== Lab3 cycle {cyc}/{cycle_budget} (cap {args.max_total_cycles}) corpus={len(corpus)} ===")

        if len(corpus) < args.min_corpus:
            stop_reason = "corpus_below_min"
            break

        train_path = cycle_dir / "reaction_train_clean.txt"
        train_path.write_text(f"# Lab3 cycle={cyc} n={len(corpus)}\n" + "\n".join(corpus) + "\n", encoding="utf-8")

        _log("  training Lab3 softmax Level B…")
        train_info = train_lab3(
            corpus, valid_lines, held_lines, cfg=cfg, floors=floors,
            level_b_epochs=args.level_b_epochs, pairs_per_epoch=args.pairs_per_epoch,
            softmax_a_epochs=args.softmax_a_epochs, log=_log,
        )
        _log(
            f"  fly held CE={train_info['heldout_ce']:.3f} (A={train_info['heldout_ce_level_a']:.3f}) "
            f"scramble={train_info['scramble_ce']:.3f} bigram={train_info['bigram_floor']} "
            f"honesty={'OK' if train_info['honesty_ok'] else 'FAIL'} "
            f"beats_bigram={train_info['beats_bigram']} beats_trigram={train_info['beats_trigram']}"
        )

        probe = _probe(train_info)
        _pack_inbox(cycle_dir, probe, corpus, args.train_judge_n)
        _log("  packed inbox → local Grok judge…")
        judged = _local_judge(cycle_dir, args.model, args.judge_timeout)
        corpus, apply_stats = _apply_grades(corpus, judged["grades"])

        record = {
            "cycle": cyc,
            "lab": 3,
            "corpus_before_apply": apply_stats["in"],
            "corpus_after_apply": apply_stats["out"],
            "fly": {
                "heldout_ce": train_info["heldout_ce"],
                "heldout_ce_level_a": train_info["heldout_ce_level_a"],
                "scramble_ce": train_info["scramble_ce"],
                "honesty_ok": train_info["honesty_ok"],
                "beats_bigram": train_info["beats_bigram"],
                "beats_trigram": train_info["beats_trigram"],
                "beats_scramble": train_info["beats_scramble"],
                "bigram_floor": train_info["bigram_floor"],
                "trigram_floor": train_info["trigram_floor"],
                "vocab": train_info["vocab"],
                "pairs": train_info["pairs"],
                "level_b_best_epoch": (train_info.get("level_b") or {}).get("best_epoch"),
            },
            "probe_local": {
                "freewrite_pass": probe["local_freewrite_pass"],
                "hybrid_pass": probe["local_hybrid_pass"],
                "rows": probe["rows"],
            },
            "grok": apply_stats,
            "grades_n": judged["n"],
            "train_path": str(train_path.relative_to(ROOT)),
        }
        score = (
            apply_stats["probe_keep_rate"] * 3.0
            + apply_stats.get("train_keep_rate", 0.0)
            + apply_stats.get("train_salvage_rate", 0.0) * 0.25
            + (0.5 if train_info["honesty_ok"] else 0.0)
            + (1.0 if train_info["beats_bigram"] else 0.0)
            + (1.5 if train_info["beats_trigram"] else 0.0)
            + max(0.0, (train_info["bigram_floor"] or 7.0) - train_info["heldout_ce"]) * 0.2
        )
        record["loop_score"] = score
        history.append(record)
        if best is None or score > best.get("loop_score", -1):
            best = record

        improved, improve_why = (False, "baseline")
        if len(history) >= 2:
            improved, improve_why = _cycle_improved(history[-1], history[-2])
        record["improved_vs_prev"] = improved
        record["improve_why"] = improve_why
        (cycle_dir / "summary.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

        _log(
            f"  honesty={'OK' if train_info['honesty_ok'] else 'FAIL'} "
            f"held={train_info['heldout_ce']:.3f} "
            f"grok_probe_keep={apply_stats['probe_keep_rate']:.2f} "
            f"({apply_stats['probe_keep']}/{apply_stats['probe_n']}) "
            f"train_keep={apply_stats.get('train_keep_rate', 0):.2f} "
            f"({apply_stats.get('train_keep', 0)}/{apply_stats.get('train_n', 0)}) "
            f"corpus→{apply_stats['out']} "
            f"improved={improved} ({improve_why})"
        )

        try:
            # Lab 3 chronicle doc
            os.environ.setdefault("TASKS_DSC_FLYCAST_CHRONICLE_DOC_ID", "1331")
            from flycast_chronicle_tasks import publish as _chronicle_publish

            doc_id = _chronicle_publish(run_dir, title=f"Fly Cast — Lab 3 Grok cycle log ({run_dir.name})")
            _log(f"  chronicle doc #{doc_id} refreshed")
        except Exception as exc:  # noqa: BLE001
            _log(f"  chronicle warn: {exc}")

        if apply_stats["probe_keep_rate"] >= args.probe_keep_threshold and train_info["honesty_ok"]:
            stop_reason = "pass_threshold"
            _log("PASS: Grok probe keep + honesty — stopping")
            break

        if improved and args.extend_by > 0 and cyc < args.max_total_cycles:
            new_budget = min(cycle_budget + args.extend_by, args.max_total_cycles)
            add = new_budget - cycle_budget
            if add > 0:
                cycle_budget = new_budget
                extensions += 1
                _log(f"EARN — +{add} cycles (budget now {cycle_budget}, extension #{extensions})")
        if cyc >= cycle_budget:
            stop_reason = "no_improvement" if not improved else "hit_max_total"
            _log(f"STOP at budget: improved={improved} ({improve_why}); reason={stop_reason}")
            break

    assert best is not None
    final = {
        "lab": 3,
        "stamp": stamp,
        "run_dir": str(run_dir.relative_to(ROOT)),
        "best_cycle": best["cycle"],
        "best": best,
        "stop_reason": stop_reason,
        "extensions": extensions,
        "final_budget": cycle_budget,
        "authorized": "Mark 2026-09-12 — Lab 3 softmax Level B; Lab2 end corpus; +5 earn, cap 40",
    }
    jdump(run_dir / "final.json", final)
    jdump(LAB3 / "latest-lab3-grok.json", final)
    _log(f"\nLab3 done: {stop_reason} best_cycle={best['cycle']} extensions={extensions}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

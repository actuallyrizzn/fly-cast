#!/usr/bin/env python3
"""Free-write climb loop with FlyBrain Cursor Grok as mouth judge.

Mark authorized (2026-09-12): hit Grok-on-FlyBrain until mouth training is
satisfactory. Ottoless workspace on FlyBrain; Otto only packs/applies/climbs.

Auto-extend: any cycle that earns vs the prior cycle adds +N to the budget
(default 5), hard-capped at --max-total-cycles (default 40). Stops on pass
threshold, flat at budget edge, or cap.

  . .venv/bin/activate
  python tools/flybrain_grok_loop.py --cycles 8 --extend-by 5 --max-total-cycles 40

Requires: ssh fly-brain, agent logged in there, /root/flycast-mouth-judge ready.
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from flycast.checkpoint import load_level_a
from flycast.hybrid import hybrid_write
from flycast.mouth_taste import filter_corpus_lines, grade_text, split_cue
from flycast.prompt import Event
from flycast.write import freewrite

PROFILE = ROOT / "examples" / "fly_hero"
DEFAULT_TRAIN = PROFILE / "fixtures" / "reaction_train.txt"
DEFAULT_HELD = PROFILE / "fixtures" / "reaction_heldout.txt"
ATHENA_BRIEF = PROFILE / "docs" / "MOUTH-TASTE-ATHENA.md"
ART_ROOT = ROOT / "artifacts" / "grok-judge"
REMOTE_JUDGE = "/root/flycast-mouth-judge"
SSH_PASS = Path.home() / ".ssh" / "fly-brain.pass"
SSH_HOST = "fly-brain"
MODEL_DEFAULT = "cursor-grok-4.6-high-fast"
PROBE_CUES = ("MISS", "HIT", "STREAK", "SONG_START", "SONG_END", "OVERSTRUM")

ATHENA_SEED = [
    "MISS blue at 67%, cope.",
    "MISS choked on the sustain.",
    "MISS tap on red, gone.",
    "MISS off by one, again.",
    "MISS blue at the chorus, rip.",
    "STREAK still cooking.",
    "STREAK clean clean clean.",
    "STREAK untouched so far.",
    "STREAK passing the kickline.",
    "STREAK 95%, no notes missed.",
    "STREAK 97%, don't choke now.",
    "STREAK clean to the chorus.",
    "STREAK 98%, last phrase.",
    "MISS streak dead, blue at 71%.",
    "MISS clean run died.",
    "MISS rest in pepperoni.",
    "MISS died at 96%, classic.",
    "MISS FC in shambles.",
    "MISS death by sustain.",
    "MISS died at the final hopo.",
    "STREAK saved it.",
    "STREAK got it back.",
    "STREAK sp activator bailed me out.",
    "STREAK still in it.",
]


def _ssh(cmd: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    full = [
        "sshpass",
        "-f",
        str(SSH_PASS),
        "ssh",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "ConnectTimeout=20",
        SSH_HOST,
        cmd,
    ]
    return subprocess.run(full, text=True, capture_output=True, check=check)


def _scp_to(local: Path, remote: str) -> None:
    cmd = [
        "sshpass",
        "-f",
        str(SSH_PASS),
        "scp",
        "-o",
        "StrictHostKeyChecking=no",
        str(local),
        f"{SSH_HOST}:{remote}",
    ]
    subprocess.run(cmd, check=True)


def _scp_from(remote: str, local: Path) -> None:
    local.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "sshpass",
        "-f",
        str(SSH_PASS),
        "scp",
        "-o",
        "StrictHostKeyChecking=no",
        f"{SSH_HOST}:{remote}",
        str(local),
    ]
    subprocess.run(cmd, check=True)


def _load_lines(path: Path) -> list[str]:
    return [
        ln.strip()
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]


def _write_corpus(path: Path, lines: list[str], *, note: str) -> None:
    header = (
        f"# Grok-judged reaction corpus\n"
        f"# {note}\n"
        f"# Held-out stays in reaction_heldout.txt — do not copy here.\n\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")


def _climb_pid_for(artifacts: Path) -> int | None:
    """Return PID of an in-flight climb writing to this artifacts dir, if any."""
    needle = str(artifacts.resolve())
    try:
        out = subprocess.check_output(["pgrep", "-af", "climb_reaction_freewrite.py"], text=True)
    except subprocess.CalledProcessError:
        return None
    for ln in out.splitlines():
        if needle not in ln:
            continue
        parts = ln.split(None, 1)
        if not parts:
            continue
        try:
            return int(parts[0])
        except ValueError:
            continue
    return None


def _run_climb(train: Path, artifacts: Path, max_a: int, max_b: int) -> dict:
    artifacts.mkdir(parents=True, exist_ok=True)
    latest = artifacts / "latest.json"
    # Do not restart an in-progress or finished climb for this cycle
    if latest.is_file():
        print(f"  climb: reusing existing {latest.relative_to(ROOT)} (no restart)", flush=True)
        return json.loads(latest.read_text(encoding="utf-8"))

    orphan = _climb_pid_for(artifacts)
    if orphan is not None:
        print(f"  climb: waiting on in-flight pid={orphan} (no restart)", flush=True)
        while True:
            if latest.is_file():
                break
            try:
                os.kill(orphan, 0)
            except OSError:
                break
            time.sleep(15)
        if latest.is_file():
            return json.loads(latest.read_text(encoding="utf-8"))
        raise RuntimeError(f"in-flight climb {orphan} exited without {latest}; see {artifacts / 'climb.log'}")

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
    if not latest.is_file():
        raise RuntimeError(f"climb failed (exit {proc.returncode}); see {log}")
    return json.loads(latest.read_text(encoding="utf-8"))


def _probe(ckpt: Path) -> dict:
    brain, tok = load_level_a(ckpt)
    rows = []
    free_ok = hybrid_ok = 0
    for i, cue in enumerate(PROBE_CUES):
        events = [Event(cue=cue, detail="")]
        fw = freewrite(brain, tok, events, seed=10 + i, temperature=0.7)
        hy = hybrid_write(brain, tok, events, k=5, seed=20 + i, temperature=0.85)
        g_fw = grade_text(fw.text, cue=cue)
        g_hy = grade_text(hy.text, cue=cue)
        free_ok += int(g_fw.ok)
        hybrid_ok += int(g_hy.ok)
        rows.append(
            {
                "cue": cue,
                "freewrite": fw.text,
                "hybrid": hy.text,
                "local_fw_ok": g_fw.ok,
                "local_hy_ok": g_hy.ok,
            }
        )
    n = len(PROBE_CUES)
    return {
        "local_freewrite_pass": free_ok / n,
        "local_hybrid_pass": hybrid_ok / n,
        "rows": rows,
    }


def _pack_inbox(cycle_dir: Path, probe: dict, climb: dict, train_lines: list[str], n_train: int) -> None:
    inbox = cycle_dir / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    p_lines = ["# Probe samples — grade KEEP/CUT/REWRITE", ""]
    for row in probe["rows"]:
        p_lines.append(f"## cue={row['cue']}")
        p_lines.append(f"FREEWRITE: {row['freewrite']}")
        p_lines.append(f"HYBRID: {row['hybrid']}")
        p_lines.append("")
    (inbox / "01-probe-samples.md").write_text("\n".join(p_lines) + "\n", encoding="utf-8")

    c_lines = ["# Climb A/B samples", ""]
    for cue, pair in (climb.get("samples") or {}).items():
        c_lines.append(f"## {cue}")
        c_lines.append(f"A: {pair.get('A', '')}")
        c_lines.append(f"B: {pair.get('B', '')}")
        c_lines.append("")
    (inbox / "02-climb-samples.md").write_text("\n".join(c_lines) + "\n", encoding="utf-8")

    rng = random.Random(42 + len(train_lines))
    sample = train_lines[:]
    rng.shuffle(sample)
    sample = sample[:n_train]
    (inbox / "03-train-slice.txt").write_text("\n".join(sample) + "\n", encoding="utf-8")
    (cycle_dir / "train_slice_ids.json").write_text(
        json.dumps({"lines": sample}, indent=2) + "\n", encoding="utf-8"
    )


def _push_and_judge(cycle_dir: Path, model: str, timeout_s: int) -> dict:
    inbox = cycle_dir / "inbox"
    # wipe remote inbox/out
    _ssh(f"rm -rf {REMOTE_JUDGE}/inbox {REMOTE_JUDGE}/out && mkdir -p {REMOTE_JUDGE}/inbox {REMOTE_JUDGE}/out {REMOTE_JUDGE}/artifacts")
    for f in sorted(inbox.iterdir()):
        _scp_to(f, f"{REMOTE_JUDGE}/inbox/{f.name}")
    # ensure brief + judge instructions present
    _scp_to(ATHENA_BRIEF, f"{REMOTE_JUDGE}/MOUTH-TASTE.md")
    judge_md = ROOT / "artifacts" / "grok-judge" / "JUDGE.md"
    if judge_md.is_file():
        _scp_to(judge_md, f"{REMOTE_JUDGE}/JUDGE.md")

    prompt = (
        "You are the Fly Cast mouth-taste judge. Read JUDGE.md and follow it exactly. "
        "You are not Otto. Grade all inbox samples against MOUTH-TASTE.md. "
        "Write out/grades.jsonl and out/SUMMARY.md. Be harsh on mush. "
        "CRITICAL for SUMMARY.md: one rates table is fine; everything OUTSIDE that table "
        "must be human-facing plain English — explain implications for the product mouth, "
        "what got better/worse, and what the next cycle or next lab should change. No engineer slang dumps. "
        "When done, print a one-line BLUF: KEEP/CUT counts by source."
    )
    # escape for remote single-quoted bash is painful — write prompt file
    prompt_path = cycle_dir / "prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    _scp_to(prompt_path, f"{REMOTE_JUDGE}/prompt.txt")

    remote_cmd = (
        f"export PATH=$HOME/.local/bin:$PATH; "
        f"cd {REMOTE_JUDGE}; "
        f"nohup agent --print --trust --force --workspace {REMOTE_JUDGE} "
        f"--model {model} \"$(cat prompt.txt)\" "
        f"> artifacts/judge.log 2>&1 & echo $!"
    )
    proc = _ssh(remote_cmd)
    pid = proc.stdout.strip().splitlines()[-1].strip()
    print(f"  grok judge pid={pid} model={model}", flush=True)

    out_local = cycle_dir / "out"
    out_local.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + timeout_s
    last_size = -1
    stable = 0
    while time.time() < deadline:
        time.sleep(10)
        alive = _ssh(f"kill -0 {pid} 2>/dev/null && echo alive || echo dead", check=False)
        pull = subprocess.run(
            [
                "sshpass",
                "-f",
                str(SSH_PASS),
                "scp",
                "-o",
                "StrictHostKeyChecking=no",
                f"{SSH_HOST}:{REMOTE_JUDGE}/out/grades.jsonl",
                str(out_local / "grades.jsonl"),
            ],
            capture_output=True,
            text=True,
        )
        got = pull.returncode == 0 and (out_local / "grades.jsonl").is_file() and (out_local / "grades.jsonl").stat().st_size > 0
        if got:
            size = (out_local / "grades.jsonl").stat().st_size
            subprocess.run(
                [
                    "sshpass",
                    "-f",
                    str(SSH_PASS),
                    "scp",
                    "-o",
                    "StrictHostKeyChecking=no",
                    f"{SSH_HOST}:{REMOTE_JUDGE}/out/SUMMARY.md",
                    str(out_local / "SUMMARY.md"),
                ],
                check=False,
            )
            if size == last_size:
                stable += 1
            else:
                stable = 0
                last_size = size
            if "dead" in (alive.stdout or "") or stable >= 2:
                _scp_from(f"{REMOTE_JUDGE}/artifacts/judge.log", cycle_dir / "judge.log")
                break
        elif "dead" in (alive.stdout or ""):
            _scp_from(f"{REMOTE_JUDGE}/artifacts/judge.log", cycle_dir / "judge.log")
            raise RuntimeError(f"judge died without grades; see {cycle_dir / 'judge.log'}")

    if not (out_local / "grades.jsonl").is_file():
        raise RuntimeError(f"judge timeout after {timeout_s}s; see remote artifacts/judge.log")

    grades = [
        json.loads(ln)
        for ln in (out_local / "grades.jsonl").read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    # If Grok skipped human-facing prose outside the rates table, Otto rewrites it
    try:
        tools_dir = str(ROOT / "tools")
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        from flycast_summary_human import ensure_human_summary

        cyc_n = None
        m = re.search(r"cycle-(\d+)", str(cycle_dir))
        if m:
            cyc_n = int(m.group(1))
        _sum_path, rewritten = ensure_human_summary(cycle_dir, grades, cycle=cyc_n)
        if rewritten:
            print("  SUMMARY.md: Otto rewrote human prose (Grok table/grades kept)", flush=True)
            # mirror rewrite back to FlyBrain for the judge workspace trail
            try:
                _scp_to(_sum_path, f"{REMOTE_JUDGE}/out/SUMMARY.md")
            except Exception:
                pass
        else:
            print("  SUMMARY.md: human prose OK from Grok", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"  SUMMARY human rewrite warn: {exc}", flush=True)
    return {"grades": grades, "n": len(grades)}


def _apply_grades(corpus: list[str], grades: list[dict]) -> tuple[list[str], dict]:
    """Remove CUT texts; replace REWRITE; keep KEEP; always retain Athena seed."""
    cut_bodies: set[str] = set()
    rewrites: dict[str, str] = {}
    keeps: list[str] = []
    probe_keep = probe_n = 0

    train_n = train_keep = train_rewrite = train_cut = 0
    for g in grades:
        text = (g.get("text") or "").strip()
        verdict = (g.get("verdict") or "").upper()
        src = g.get("source") or ""
        cue = (g.get("cue") or "").strip().upper() or None
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
        elif verdict == "REWRITE":
            rw = (g.get("rewrite") or "").strip()
            if rw:
                rewrites[body] = rw
                # add as cue-prefixed if we know cue
                if cue and cue not in {"", "NONE"}:
                    keeps.append(f"{cue} {rw}")
                else:
                    keeps.append(rw)
        elif verdict == "KEEP":
            if cue and not text.upper().startswith(cue):
                keeps.append(f"{cue} {text}")
            else:
                keeps.append(text)

    out: list[str] = []
    seen: set[str] = set()

    def add(line: str) -> None:
        norm = " ".join(line.strip().split())
        if not norm:
            return
        key = norm.lower()
        if key in seen:
            return
        # drop if body was CUTed
        cue, rest = split_cue(norm)
        body = (rest or norm).lower()
        if body in cut_bodies or norm.lower() in cut_bodies:
            return
        if body in rewrites:
            rw = rewrites[body]
            norm = f"{cue} {rw}" if cue else rw
            key = norm.lower()
            if key in seen:
                return
        # local filter still applies
        filtered = filter_corpus_lines([norm])
        if not filtered:
            return
        seen.add(key)
        out.append(filtered[0])

    for s in ATHENA_SEED:
        add(s)
    for k in keeps:
        add(k)
    for ln in corpus:
        add(ln)

    stats = {
        "in": len(corpus),
        "out": len(out),
        "cuts": len(cut_bodies),
        "rewrites": len(rewrites),
        "keeps_added": len(keeps),
        "probe_keep_rate": (probe_keep / probe_n) if probe_n else 0.0,
        "probe_keep": probe_keep,
        "probe_n": probe_n,
        "train_n": train_n,
        "train_keep": train_keep,
        "train_rewrite": train_rewrite,
        "train_cut": train_cut,
        "train_keep_rate": (train_keep / train_n) if train_n else 0.0,
        "train_salvage_rate": ((train_keep + train_rewrite) / train_n) if train_n else 0.0,
    }
    return out, stats


def _cycle_improved(curr: dict, prev: dict) -> tuple[bool, str]:
    """Did this cycle beat the previous one?

    Pass bar stays strict (probe KEEP + honesty). Continue/extend earns on
    probe KEEP, train KEEP/salvage, honesty flip, or meaningful A CE drop
    without probe regression — so we do not quit while the keep pile grows.
    """
    reasons: list[str] = []
    g, g0 = curr["grok"], prev["grok"]
    pk = g["probe_keep_rate"]
    pk0 = g0["probe_keep_rate"]
    if pk > pk0 + 1e-9:
        reasons.append(f"probe_keep {pk0:.2f}→{pk:.2f}")

    tk = float(g.get("train_keep_rate") or 0.0)
    tk0 = float(g0.get("train_keep_rate") or 0.0)
    if tk > tk0 + 0.005:  # >0.5pp on an 80-line slice
        reasons.append(f"train_keep {tk0:.2f}→{tk:.2f}")

    sv = float(g.get("train_salvage_rate") or 0.0)
    sv0 = float(g0.get("train_salvage_rate") or 0.0)
    if sv > sv0 + 0.01:
        reasons.append(f"train_salvage {sv0:.2f}→{sv:.2f}")

    a = curr["climb"]["ce"]["level_a_fly"]
    a0 = prev["climb"]["ce"]["level_a_fly"]
    if a < a0 - 0.05 and pk + 1e-9 >= pk0:
        reasons.append(f"A CE {a0:.3f}→{a:.3f}")

    if curr["climb"]["honesty_ok"] and not prev["climb"]["honesty_ok"]:
        reasons.append("honesty FAIL→OK")

    # Do not treat loop_score alone as earn — it ignored train KEEP before.
    # Still allow it if probe moved (already counted) or honesty+CE composite rose
    # while train did not regress hard.
    if curr.get("loop_score", 0) > prev.get("loop_score", 0) + 1e-9 and tk + 1e-9 >= tk0 - 0.02:
        reasons.append(f"loop_score {prev.get('loop_score', 0):.3f}→{curr.get('loop_score', 0):.3f}")

    return (len(reasons) > 0, "; ".join(reasons) if reasons else "flat/regress")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=8, help="initial cycle budget")
    ap.add_argument(
        "--extend-by",
        type=int,
        default=5,
        help="on any earn vs prior cycle, add this many to budget (capped by --max-total-cycles)",
    )
    ap.add_argument(
        "--max-total-cycles",
        type=int,
        default=40,
        help="hard cap so extend-by cannot run forever",
    )
    ap.add_argument("--probe-keep-threshold", type=float, default=0.5)
    ap.add_argument("--max-pairs-a", type=int, default=4000)
    ap.add_argument("--max-pairs-b", type=int, default=2000)
    ap.add_argument("--train-judge-n", type=int, default=80)
    ap.add_argument("--min-corpus", type=int, default=200)
    ap.add_argument("--model", default=MODEL_DEFAULT)
    ap.add_argument("--judge-timeout", type=int, default=600)
    ap.add_argument("--source-train", type=Path, default=DEFAULT_TRAIN)
    ap.add_argument(
        "--resume-run",
        type=Path,
        default=None,
        help="Continue an existing artifacts/grok-judge/run-* (load history + latest corpus)",
    )
    args = ap.parse_args()

    if not SSH_PASS.is_file():
        raise SystemExit(f"missing {SSH_PASS}")

    history: list[dict] = []
    best: dict | None = None
    cycle_budget = max(1, args.cycles)
    extensions = 0
    cyc = 0
    stop_reason = "budget_exhausted"

    if args.resume_run:
        run_dir = args.resume_run if args.resume_run.is_absolute() else ROOT / args.resume_run
        if not run_dir.is_dir():
            raise SystemExit(f"resume-run not found: {run_dir}")
        stamp = run_dir.name.replace("run-", "") if run_dir.name.startswith("run-") else run_dir.name
        # Load completed summaries; backfill train_* rates from grades if missing
        for summ_path in sorted(run_dir.glob("cycle-*/summary.json"), key=lambda p: int(p.parent.name.split("-")[1])):
            rec = json.loads(summ_path.read_text(encoding="utf-8"))
            gstat = rec.setdefault("grok", {})
            if "train_keep_rate" not in gstat:
                grades_path = summ_path.parent / "out" / "grades.jsonl"
                if grades_path.is_file():
                    rows = [
                        json.loads(ln)
                        for ln in grades_path.read_text(encoding="utf-8").splitlines()
                        if ln.strip()
                    ]
                    tr = [r for r in rows if r.get("source") == "train"]
                    tk = sum(1 for r in tr if (r.get("verdict") or "").upper() == "KEEP")
                    trw = sum(1 for r in tr if (r.get("verdict") or "").upper() == "REWRITE")
                    tcut = sum(1 for r in tr if (r.get("verdict") or "").upper() == "CUT")
                    gstat["train_n"] = len(tr)
                    gstat["train_keep"] = tk
                    gstat["train_rewrite"] = trw
                    gstat["train_cut"] = tcut
                    gstat["train_keep_rate"] = (tk / len(tr)) if tr else 0.0
                    gstat["train_salvage_rate"] = ((tk + trw) / len(tr)) if tr else 0.0
            history.append(rec)
            if best is None or rec.get("loop_score", -1) > best.get("loop_score", -1):
                best = rec
        if not history:
            raise SystemExit(f"resume-run has no cycle summaries: {run_dir}")
        # Recompute improved flags with current earn rules
        for i in range(1, len(history)):
            improved, why = _cycle_improved(history[i], history[i - 1])
            history[i]["improved_vs_prev"] = improved
            history[i]["improve_why"] = why
        cyc = history[-1]["cycle"]
        # Corpus = last written train file (pre-apply for in-progress) or post-apply path
        last_train = run_dir / f"cycle-{cyc}" / "reaction_train_clean.txt"
        # Prefer newest train file among cycles (in-progress climb may be mid-cycle)
        candidates = sorted(run_dir.glob("cycle-*/reaction_train_clean.txt"), key=lambda p: p.stat().st_mtime)
        corpus = _load_lines(candidates[-1]) if candidates else _load_lines(last_train)
        # If last cycle has no summary, it was interrupted — redo that cycle number
        last_summ = run_dir / f"cycle-{cyc}" / "summary.json"
        if last_summ.is_file():
            # start next cycle; budget at least cycles remaining toward original intent
            pass
        else:
            cyc -= 1  # redo incomplete cycle
            # corpus for incomplete cycle is already that cycle's train file
        # Budget = initial + (earns × extend-by), same as live +5-on-earn policy
        earn_count = sum(1 for h in history[1:] if h.get("improved_vs_prev"))
        extensions = earn_count
        cycle_budget = min(
            args.max_total_cycles,
            max(args.cycles + earn_count * args.extend_by, cyc + 1),
        )
        print(
            f"RESUME {run_dir.name}: loaded {len(history)} summaries, "
            f"next cycle={cyc+1}, corpus={len(corpus)}, budget={cycle_budget} "
            f"(earns={earn_count})",
            flush=True,
        )
        # Show whether last completed cycle would earn under new rules
        if len(history) >= 2:
            print(
                f"  last earn check (new rules): improved={history[-1].get('improved_vs_prev')} "
                f"({history[-1].get('improve_why')})",
                flush=True,
            )
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = ART_ROOT / f"run-{stamp}"
        run_dir.mkdir(parents=True, exist_ok=True)

        # Start from locally filtered Venice dump + Athena seed
        raw = filter_corpus_lines(
            _load_lines(args.source_train if args.source_train.is_absolute() else ROOT / args.source_train)
        )
        corpus = []
        seen: set[str] = set()
        for ln in ATHENA_SEED + raw:
            k = ln.lower()
            if k not in seen:
                seen.add(k)
                corpus.append(ln)

    while cyc < cycle_budget and cyc < args.max_total_cycles:
        cyc += 1
        cycle_dir = run_dir / f"cycle-{cyc}"
        cycle_dir.mkdir(parents=True, exist_ok=True)
        print(
            f"\n=== cycle {cyc}/{cycle_budget} (cap {args.max_total_cycles}) "
            f"corpus={len(corpus)} ===",
            flush=True,
        )

        if len(corpus) < args.min_corpus:
            stop_reason = "corpus_below_min"
            print(f"corpus below min ({len(corpus)} < {args.min_corpus}) — stopping", flush=True)
            break

        train_path = cycle_dir / "reaction_train_clean.txt"
        _write_corpus(train_path, corpus, note=f"cycle={cyc} n={len(corpus)}")

        held = {h.lower() for h in _load_lines(DEFAULT_HELD)}
        leak = [ln for ln in corpus if ln.lower() in held]
        if leak:
            raise SystemExit(f"held-out leak: {leak[:5]}")

        climb = _run_climb(train_path, cycle_dir / "climb", args.max_pairs_a, args.max_pairs_b)
        ckpt = Path(climb["checkpoint"])
        if not ckpt.is_file():
            ckpt = cycle_dir / "climb" / "level_a.npz"
        probe = _probe(ckpt)
        honesty_ok = (
            climb["ce"]["level_a_fly"] < climb["ce"]["scramble_a"]
            and climb["ce"]["level_a_fly"] < climb["ce"]["no_fly"]
        )

        _pack_inbox(cycle_dir, probe, climb, corpus, args.train_judge_n)
        print("  packed inbox → FlyBrain Grok judge…", flush=True)
        judged = _push_and_judge(cycle_dir, args.model, args.judge_timeout)
        corpus, apply_stats = _apply_grades(corpus, judged["grades"])

        record = {
            "cycle": cyc,
            "corpus_before_apply": apply_stats["in"],
            "corpus_after_apply": apply_stats["out"],
            "climb": {
                "ce": climb["ce"],
                "b_wins": climb["b_wins"],
                "honesty_ok": honesty_ok,
                "gate": climb["gate"],
            },
            "probe_local": {
                "freewrite_pass": probe["local_freewrite_pass"],
                "hybrid_pass": probe["local_hybrid_pass"],
                "rows": probe["rows"],
            },
            "grok": apply_stats,
            "grades_n": judged["n"],
            "checkpoint": str(ckpt),
            "train_path": str(train_path.relative_to(ROOT)),
        }
        # composite: probe KEEP is the win signal; train KEEP keeps the lab earning
        score = (
            apply_stats["probe_keep_rate"] * 3.0
            + apply_stats.get("train_keep_rate", 0.0) * 1.0
            + apply_stats.get("train_salvage_rate", 0.0) * 0.25
            + (0.5 if honesty_ok else 0.0)
            + probe["local_hybrid_pass"] * 0.1
        )
        record["loop_score"] = score
        (cycle_dir / "summary.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        history.append(record)
        if best is None or score > best.get("loop_score", -1):
            best = record

        improved = False
        improve_why = "baseline"
        if len(history) >= 2:
            improved, improve_why = _cycle_improved(history[-1], history[-2])
        record["improved_vs_prev"] = improved
        record["improve_why"] = improve_why
        (cycle_dir / "summary.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

        print(
            f"  honesty={'OK' if honesty_ok else 'FAIL'} "
            f"A={climb['ce']['level_a_fly']:.3f} "
            f"grok_probe_keep={apply_stats['probe_keep_rate']:.2f} "
            f"({apply_stats['probe_keep']}/{apply_stats['probe_n']}) "
            f"train_keep={apply_stats.get('train_keep_rate', 0):.2f} "
            f"({apply_stats.get('train_keep', 0)}/{apply_stats.get('train_n', 0)}) "
            f"corpus→{apply_stats['out']} "
            f"improved={improved} ({improve_why})",
            flush=True,
        )

        # Living cycle table on DSC Tasks (lab chronicle key)
        try:
            sys.path.insert(0, str(ROOT / "tools"))
            from flycast_chronicle_tasks import publish as _chronicle_publish

            doc_id = _chronicle_publish(run_dir)
            print(f"  chronicle doc #{doc_id} refreshed", flush=True)
        except Exception as exc:  # noqa: BLE001 — lab must continue if Tasks blips
            print(f"  chronicle warn: {exc}", flush=True)

        if apply_stats["probe_keep_rate"] >= args.probe_keep_threshold and honesty_ok:
            stop_reason = "pass_threshold"
            print("PASS: Grok probe keep + honesty — stopping", flush=True)
            break

        # Any earn → +N budget (capped). Flat at budget edge → stop.
        if improved and args.extend_by > 0 and cyc < args.max_total_cycles:
            new_budget = min(cycle_budget + args.extend_by, args.max_total_cycles)
            add = new_budget - cycle_budget
            if add > 0:
                cycle_budget = new_budget
                extensions += 1
                print(
                    f"EARN — +{add} cycles "
                    f"(budget now {cycle_budget}, extension #{extensions})",
                    flush=True,
                )
        if cyc >= cycle_budget:
            stop_reason = "no_improvement" if not improved else "hit_max_total"
            print(
                f"STOP at budget: improved={improved} ({improve_why}); "
                f"reason={stop_reason}",
                flush=True,
            )
            break

    assert best is not None
    # Promote best
    promo_train = PROFILE / "fixtures" / "reaction_train_clean.txt"
    best_train = ROOT / best["train_path"]
    promo_train.write_text(best_train.read_text(encoding="utf-8"), encoding="utf-8")
    promo_art = ROOT / "artifacts" / "reaction-climb-loop"
    promo_art.mkdir(parents=True, exist_ok=True)
    best_ckpt = Path(best["checkpoint"])
    for name in ("level_a.npz", "level_a.tok.json", "latest.json"):
        src = best_ckpt.parent / name
        if src.is_file():
            (promo_art / name).write_bytes(src.read_bytes())

    final = {
        "stamp": stamp,
        "run_dir": str(run_dir.relative_to(ROOT)),
        "best_cycle": best["cycle"],
        "best": best,
        "stop_reason": stop_reason,
        "extensions": extensions,
        "final_budget": cycle_budget,
        "history": [
            {
                "cycle": h["cycle"],
                "honesty_ok": h["climb"]["honesty_ok"],
                "probe_keep_rate": h["grok"]["probe_keep_rate"],
                "corpus_after": h["corpus_after_apply"],
                "A": h["climb"]["ce"]["level_a_fly"],
                "improved_vs_prev": h.get("improved_vs_prev"),
                "improve_why": h.get("improve_why"),
            }
            for h in history
        ],
        "model": args.model,
        "live_default": "picker",
        "authorized": "Mark 2026-09-12 — Grok-on-FlyBrain until mouth satisfactory; +5 budget on any earn, cap 40",
    }
    (run_dir / "final.json").write_text(json.dumps(final, indent=2) + "\n", encoding="utf-8")
    (ART_ROOT / "latest.json").write_text(json.dumps(final, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "best_cycle": best["cycle"],
                "probe_keep": best["grok"]["probe_keep_rate"],
                "stop_reason": stop_reason,
                "extensions": extensions,
                "out": str(run_dir),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

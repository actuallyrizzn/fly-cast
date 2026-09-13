#!/usr/bin/env python3
"""Publish / refresh Fly Cast Grok-loop cycle table on DSC Tasks.

Uses ~/.ssh/tasks-dsc-flycast-lab.pass (lab-only API key). Safe to call after
each cycle from flybrain_grok_loop.py.

  python tools/flycast_chronicle_tasks.py --run artifacts/grok-judge/run-…
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PASS = Path.home() / ".ssh" / "tasks-dsc-flycast-lab.pass"


def _load_pass() -> dict[str, str]:
    if not PASS.is_file():
        raise SystemExit(f"missing {PASS}")
    env: dict[str, str] = {}
    for ln in PASS.read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        env[k.strip()] = v.strip()
    for req in ("TASKS_DSC_BASE_URL", "TASKS_DSC_FLYCAST_LAB_API_KEY"):
        if not env.get(req):
            raise SystemExit(f"{PASS} missing {req}")
    return env


def _api(env: dict[str, str], method: str, path: str, payload: dict | None = None) -> dict:
    base = env["TASKS_DSC_BASE_URL"].rstrip("/")
    url = f"{base}/api/{path.lstrip('/')}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "X-API-Key": env["TASKS_DSC_FLYCAST_LAB_API_KEY"],
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Tasks {method} {path} → {e.code}: {body[:500]}") from e


def _backfill_train(rec: dict, cycle_dir: Path) -> None:
    g = rec.setdefault("grok", {})
    if "train_keep_rate" in g and g.get("train_n"):
        return
    grades_path = cycle_dir / "out" / "grades.jsonl"
    if not grades_path.is_file():
        return
    rows = [json.loads(ln) for ln in grades_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    train = [r for r in rows if r.get("source") == "train"]
    n = len(train)
    k = sum(1 for r in train if (r.get("verdict") or "").upper() == "KEEP")
    rw = sum(1 for r in train if (r.get("verdict") or "").upper() == "REWRITE")
    g["train_n"] = n
    g["train_keep"] = k
    g["train_rewrite"] = rw
    g["train_keep_rate"] = (k / n) if n else 0.0
    g["train_salvage_rate"] = ((k + rw) / n) if n else 0.0


def collect_cycles(run_dir: Path) -> list[dict]:
    out: list[dict] = []
    for summ in sorted(run_dir.glob("cycle-*/summary.json"), key=lambda p: int(p.parent.name.split("-")[1])):
        rec = json.loads(summ.read_text(encoding="utf-8"))
        _backfill_train(rec, summ.parent)
        out.append(rec)
    # Recompute earn column with current rules (historical display for next-lab design)
    try:
        sys_path_tools = str(ROOT / "tools")
        if sys_path_tools not in __import__("sys").path:
            __import__("sys").path.insert(0, sys_path_tools)
        from flybrain_grok_loop import _cycle_improved  # noqa: WPS433

        for i in range(1, len(out)):
            improved, why = _cycle_improved(out[i], out[i - 1])
            out[i]["improved_vs_prev"] = improved
            out[i]["improve_why"] = why
        if out:
            out[0]["improved_vs_prev"] = False
            out[0]["improve_why"] = "baseline"
    except Exception:
        pass
    return out


def render_body(*, run_dir: Path, cycles: list[dict], extra_note: str = "") -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    final_path = run_dir / "final.json"
    stop = ""
    lab_n = 1
    if cycles and cycles[-1].get("lab") == 2:
        lab_n = 2
    if final_path.is_file():
        fin = json.loads(final_path.read_text(encoding="utf-8"))
        lab_n = int(fin.get("lab") or lab_n)
        stop = f"\n**Run status:** stopped — `{fin.get('stop_reason')}` · best cycle **{fin.get('best_cycle')}** · extensions **{fin.get('extensions')}**\n"

    title = "Fly Cast — Lab 2 Grok cycle log" if lab_n == 2 else "Fly Cast — Grok judge cycle log"
    machine = (
        "FlyBrain lab box (full-data ridge + local Grok judge)"
        if lab_n == 2
        else "climb host + FlyBrain Grok judge (`cursor-grok-4.6-high-fast`)"
    )
    lines = [
        f"# {title}",
        "",
        f"**Updated:** {now} (auto from lab loop)",
        f"**Run:** `{run_dir.name}`",
        f"**Machine:** {machine}",
        "",
        "Living history for designing the next lab. Each Grok cycle appends/refreshes this table.",
        stop,
        "## Cycle table",
        "",
        "| Cycle | Probe KEEP | Train KEEP | Salvage | Honesty | Held CE | Scramble | Bigram? | Corpus | Earned? | Why |",
        "|------:|------------|------------|---------|---------|--------:|---------:|---------|-------:|---------|-----|",
    ]
    for rec in cycles:
        g = rec.get("grok") or {}
        climb = rec.get("climb") or {}
        fly = rec.get("fly") or {}
        ce = climb.get("ce") or {}
        tk = g.get("train_keep")
        tn = g.get("train_n")
        train_s = f"{tk}/{tn}" if tn else "—"
        salvage = g.get("train_salvage_rate")
        salvage_s = f"{salvage:.0%}" if isinstance(salvage, (int, float)) else "—"
        pk = g.get("probe_keep")
        pn = g.get("probe_n")
        probe_s = f"{pk}/{pn}" if pn else "—"
        honesty_ok = fly.get("honesty_ok") if fly else climb.get("honesty_ok")
        honesty = "OK" if honesty_ok else "FAIL"
        a = fly.get("heldout_ce") if fly else ce.get("level_a_fly")
        scr = fly.get("scramble_ce") if fly else ce.get("scramble_a")
        a_s = f"{a:.3f}" if isinstance(a, (int, float)) else "—"
        scr_s = f"{scr:.3f}" if isinstance(scr, (int, float)) else "—"
        bb = fly.get("beats_bigram")
        bb_s = "yes" if bb else ("no" if bb is False else "—")
        earned = rec.get("improved_vs_prev")
        earned_s = "yes" if earned else ("baseline" if rec.get("cycle") == 1 else "no")
        why = (rec.get("improve_why") or "").replace("|", "/")
        lines.append(
            f"| {rec.get('cycle')} | {probe_s} | {train_s} | {salvage_s} | {honesty} | "
            f"{a_s} | {scr_s} | {bb_s} | {rec.get('corpus_after_apply', '—')} | {earned_s} | {why} |"
        )

    extend_note = (
        "- **Earned?** — +5 budget on **any** earn vs prior cycle; hard cap 40. "
        "Pass bar still ≥50% probe KEEP + honesty."
    )
    lines += [
        "",
        "## How to read this",
        "",
        "- **Probe KEEP** — Grok taste on free-write/hybrid samples (product mouth).",
        "- **Train KEEP / Salvage** — Grok on the training slice (corpus quality). Salvage = KEEP+REWRITE.",
        "- **Honesty** — held-out CE beats scramble control.",
        "- **Held CE / Bigram?** — Lab 2: full-data readout CE; must beat bigram floor to be interesting.",
        extend_note,
        "",
        "## Lab policy (snapshot)",
        "",
        "- Live default stays **picker**; free-write/hybrid additive.",
        "- Judge: ottoless Cursor on FlyBrain, Grok 4.6 high-fast.",
        "- Pass: probe KEEP ≥ 50% and honesty OK.",
        "- Extend: +5 cycles on any earn; hard cap 40.",
        "- Lab 2: train on ALL pairs (primal ridge); fixed 500+ line held-out; n-gram floors.",
        "",
        "## Pointers",
        "",
        "- Frontier notes: Doc #1326",
        "- Tectum × lab: Doc #1328",
        "- Build thread: task #3811",
        f"- Artifacts: `{run_dir}`",
        "",
    ]
    if extra_note:
        lines += ["## Operator note", "", extra_note, ""]
    return "\n".join(lines) + "\n"


def publish(run_dir: Path, *, title: str | None = None, extra_note: str = "") -> int:
    env = _load_pass()
    run_dir = run_dir if run_dir.is_absolute() else ROOT / run_dir
    cycles = collect_cycles(run_dir)
    body = render_body(run_dir=run_dir, cycles=cycles, extra_note=extra_note)
    doc_title = title or f"Fly Cast — Grok cycle log ({run_dir.name})"
    doc_id_s = (env.get("TASKS_DSC_FLYCAST_CHRONICLE_DOC_ID") or "").strip()
    project_id = int(env.get("TASKS_DSC_FLYCAST_CHRONICLE_PROJECT_ID") or "62")

    if doc_id_s:
        doc_id = int(doc_id_s)
        _api(
            env,
            "POST",
            "update-document.php",
            {"id": doc_id, "title": doc_title, "body": body, "directory_path": "research"},
        )
        action = "updated"
    else:
        created = _api(
            env,
            "POST",
            "create-document.php",
            {
                "project_id": project_id,
                "directory_path": "research",
                "title": doc_title,
                "body": body,
            },
        )
        doc = created.get("document") or created
        doc_id = int(doc["id"])
        action = "created"
        # Persist id into pass file (no key rewrite)
        text = PASS.read_text(encoding="utf-8")
        if "TASKS_DSC_FLYCAST_CHRONICLE_DOC_ID=" in text:
            lines = []
            for ln in text.splitlines():
                if ln.startswith("TASKS_DSC_FLYCAST_CHRONICLE_DOC_ID="):
                    lines.append(f"TASKS_DSC_FLYCAST_CHRONICLE_DOC_ID={doc_id}")
                else:
                    lines.append(ln)
            PASS.write_text("\n".join(lines) + "\n", encoding="utf-8")
        else:
            with PASS.open("a", encoding="utf-8") as fh:
                fh.write(f"TASKS_DSC_FLYCAST_CHRONICLE_DOC_ID={doc_id}\n")

    # Mirror id onto FlyBrain pass if present via caller; local is enough for loop host
    print(json.dumps({"action": action, "doc_id": doc_id, "cycles": len(cycles), "run": run_dir.name}))
    return doc_id


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True, help="artifacts/grok-judge/run-*")
    ap.add_argument("--note", default="")
    args = ap.parse_args()
    publish(args.run, extra_note=args.note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

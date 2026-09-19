#!/usr/bin/env python3
"""Refresh docs/jevlab/JOURNAL.md from run bundles. Optional Tasks publish."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HAND_START = "<!-- hand:start -->"
HAND_END = "<!-- hand:end -->"
DEFAULT_HAND = f"""{HAND_START}
## What this does not prove

- Smoke bundles and unapproved runs are not publishable evidence.
- A pass on one task does not generalize to other tasks or to production Sanctum memory.
- Latency figures are ngram CPU medians, not hosted Jev comparisons by themselves.

## Process failures

1. 2026-09-18 — untrained readout probes were treated like tests; nuked. Protocol now requires APPROVED + trained heads.

## Reading the results

(Write one plain paragraph per task after that task's real run exists.)
{HAND_END}
"""


def _git_sha() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                text=True,
            ).strip()
        )
    except Exception:  # noqa: BLE001
        return ""


def _protocol_sha(runs: Path) -> str:
    for path in (
        ROOT / "tools" / "jevlab" / "protocol.json",
        runs.parent / "protocol.json" if runs.name == "runs" else None,
    ):
        if path and path.is_file():
            import hashlib

            return hashlib.sha256(path.read_bytes()).hexdigest()
    return ""


def _load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _discover_runs(runs_root: Path) -> list[Path]:
    if not runs_root.is_dir():
        return []
    out = []
    for child in sorted(runs_root.iterdir()):
        if child.is_dir() and (child / "score.json").is_file():
            out.append(child)
    return out


def _arm_row(score: dict, arm: str) -> str:
    pack = (score.get("arms") or {}).get(arm) or {}
    acc = pack.get("acc") or [None, None, None]
    if isinstance(acc, list) and len(acc) >= 3:
        mean, lo, hi = acc[0], acc[1], acc[2]
        acc_s = f"{mean:.3f} [{lo:.3f},{hi:.3f}]" if mean is not None else "—"
    else:
        acc_s = "—"
    brier = pack.get("brier")
    ece = pack.get("ece")
    if isinstance(brier, list):
        brier = brier[0]
    if isinstance(ece, list):
        ece = ece[0]
    brier_s = f"{brier:.3f}" if isinstance(brier, (int, float)) else "—"
    ece_s = f"{ece:.3f}" if isinstance(ece, (int, float)) else "—"
    return f"| {arm} | {acc_s} | {brier_s} | {ece_s} |"


def _extract_hand(existing: str | None) -> str:
    if not existing:
        return DEFAULT_HAND
    match = re.search(
        re.escape(HAND_START) + r".*?" + re.escape(HAND_END),
        existing,
        flags=re.DOTALL,
    )
    return match.group(0) if match else DEFAULT_HAND


def render(runs_root: Path, existing: str | None = None) -> str:
    runs = _discover_runs(runs_root)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    proto = _protocol_sha(runs_root)
    sha = _git_sha()
    lines = [
        "# Jev-task lab journal — fly vs controls",
        "",
        f"- Generated: `{now}`",
        f"- Protocol sha256: `{proto or 'unknown'}`",
        f"- Git: `{sha or 'unknown'}`",
        f"- Protocol doc: [Doc #1392](https://tasks.decisionsciencecorp.com/admin/doc.php?id=1392)",
        "",
        "## Runs",
        "",
        "| run_dir | task | glass | c1 | c2 | c3 | pass | frames |",
        "|---|---|---|---|---|---|---|---|",
    ]
    publishable = False
    by_task: dict[str, list[tuple[Path, dict]]] = {}
    for run in runs:
        score = _load_json(run / "score.json") or {}
        state = _load_json(run / "state.json") or {}
        crit = score.get("criteria") or state.get("criteria") or {}
        passed = bool(score.get("pass") or state.get("pass"))
        publishable = publishable or passed
        frames = 0
        index = run / "frames" / "index.tsv"
        if index.is_file():
            frames = max(0, len(index.read_text(encoding="utf-8").splitlines()) - 1)
        task = score.get("task") or state.get("task") or run.name.split("-")[0]
        glass = state.get("glass")
        lines.append(
            f"| `{run.name}` | {task} | {glass} | {crit.get('c1')} | {crit.get('c2')} | "
            f"{crit.get('c3')} | {passed} | {frames} |"
        )
        by_task.setdefault(str(task), []).append((run, score))

    lines += ["", "## Publishable", ""]
    if publishable:
        lines.append("Scorer publishable = true (at least one task pass).")
    else:
        lines.append("Internal record only. Not for external publication.")

    for task, items in by_task.items():
        lines += ["", f"### {task}", ""]
        for run, score in items:
            lat = _load_json(run / "latency.json") or {}
            lines += [
                f"Bundle `{run.name}`",
                "",
                "| arm | acc mean [lo,hi] | brier | ece |",
                "|---|---|---|---|",
            ]
            for arm in (
                "fly",
                "scramble",
                "nofly",
                "fly_shuffled",
                "nofly_shuffled",
                "tfidf",
            ):
                lines.append(_arm_row(score, arm))
            fly_ms = lat.get("fly") or (lat.get("fly_detail") or {}).get("median_ms")
            nofly_ms = lat.get("nofly") or (lat.get("nofly_detail") or {}).get("median_ms")
            tfidf_ms = lat.get("tfidf")
            lines += [
                "",
                f"Latency ms (median): fly={fly_ms} nofly={nofly_ms} tfidf={tfidf_ms}",
                "",
            ]

    lines += ["", "## Frames", "", "(Upload scoring milestone frames from run cards; map in frame_uploads.json.)", ""]
    lines.append(_extract_hand(existing))
    lines.append("")
    return "\n".join(lines)


def _api(base: str, key: str, method: str, path: str, payload: dict | None = None) -> dict:
    url = f"{base.rstrip('/')}/api/{path.lstrip('/')}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"X-API-Key": key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Tasks {method} {path} → {exc.code}: {body[:400]}") from exc


def _publish(markdown: str, doc_id_path: Path) -> int:
    base = os.environ.get("TASKS_DSC_BASE_URL", "https://tasks.decisionsciencecorp.com")
    key = os.environ.get("TASKS_DSC_OTTOVERNAL_API_KEY", "")
    if not key:
        raise SystemExit("TASKS_DSC_OTTOVERNAL_API_KEY required for --publish")
    title = "Jev-task lab journal — fly vs controls"
    if doc_id_path.is_file():
        doc_id = int(doc_id_path.read_text(encoding="utf-8").strip())
        _api(base, key, "POST", "update-document.php", {"id": doc_id, "body": markdown, "title": title})
        print(f"updated doc #{doc_id}")
        return doc_id
    created = _api(
        base,
        key,
        "POST",
        "create-document.php",
        {"project_id": 6, "title": title, "body": markdown, "directory_path": "jevlab"},
    )
    doc = created.get("document") or created.get("data") or created
    doc_id = int(doc["id"])
    doc_id_path.parent.mkdir(parents=True, exist_ok=True)
    doc_id_path.write_text(str(doc_id) + "\n", encoding="utf-8")
    print(f"created doc #{doc_id}")
    return doc_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "jevlab" / "JOURNAL.md")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument(
        "--doc-id-file",
        type=Path,
        default=Path.home() / "fly-cast-runs" / "jevlab" / "JOURNAL_DOC_ID",
    )
    args = parser.parse_args(argv)
    existing = args.out.read_text(encoding="utf-8") if args.out.is_file() else None
    text = render(args.runs.expanduser(), existing)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(f"wrote {args.out}")
    if args.publish:
        _publish(text, args.doc_id_file.expanduser())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

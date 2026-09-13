#!/usr/bin/env python3
"""Live Lab 4 progress → Tasks Doc #1332.

Tails artifacts/lab4/lab4-run.log, refreshes the chronicle whenever a new stage
line appears (or every --interval seconds). Optional local Grok one-liner BLUF.

  cd /root/fly-cast && . .venv/bin/activate
  nohup python -u tools/lab4/lab4_progress_chronicle.py >> artifacts/lab4/progress-chronicle.log 2>&1 &
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG_DEFAULT = ROOT / "artifacts" / "lab4" / "lab4-run.log"
PASS = Path.home() / ".ssh" / "tasks-dsc-flycast-lab.pass"
DOC_ID = 1332
LABEL = "Lab 4 Level C"
PGREP = "python -u tools/lab4/lab4_run.py"
JUDGE = Path("/root/flycast-mouth-judge")
AGENT = Path.home() / ".local" / "bin" / "agent"

STAGE_PATTERNS = [
    (re.compile(r"START Lab4 (\S+)"), "start"),
    (re.compile(r"Level-A ridge valid CE ([0-9.]+)"), "a_ridge"),
    (re.compile(r"softmax ep(\d+): train CE ([0-9.]+)\s+valid CE ([0-9.]+)"), "a_softmax_ep"),
    (re.compile(r"Level-A softmax held CE ([0-9.]+)"), "a_held"),
    (re.compile(r"Level-B softmax ep(\d+): train CE ([0-9.]+)\s+valid CE ([0-9.]+).*?\((\d+(?:\.\d+)?)s\)"), "b_ep"),
    (re.compile(r"Level-B early stop"), "b_early"),
    (re.compile(r"Level-B softmax held CE ([0-9.]+)"), "b_held"),
    (re.compile(r"Level-C softmax ep(\d+): train CE ([0-9.]+)\s+valid CE ([0-9.]+).*?synΔ=([0-9.]+).*?\((\d+(?:\.\d+)?)s\)"), "c_ep"),
    (re.compile(r"Level-C early stop"), "c_early"),
    (re.compile(r"Level-C softmax held CE ([0-9.]+)"), "c_held"),
    (re.compile(r"scramble control"), "scr_start"),
    (re.compile(r"scramble Level-C held CE ([0-9.]+)"), "scr_held"),
    (re.compile(r"DONE Lab4 (.+)"), "done"),
    (re.compile(r"chronicle (update|created|warn)"), "chronicle"),
]


def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for ln in PASS.read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def _api(env: dict[str, str], method: str, path: str, payload: dict) -> dict:
    url = f"{env['TASKS_DSC_BASE_URL'].rstrip('/')}/api/{path.lstrip('/')}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        method=method,
        headers={
            "X-API-Key": env["TASKS_DSC_FLYCAST_LAB_API_KEY"],
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def parse_state(log_text: str) -> dict:
    st: dict = {
        "run": "—",
        "phase": "starting",
        "floors": {},
        "a_eps": [],
        "b_eps": [],
        "c_eps": [],
        "a_ridge": None,
        "a_held": None,
        "b_held": None,
        "c_held": None,
        "scr_held": None,
        "done_line": None,
        "last_line": "",
        "events": [],
    }
    for ln in log_text.splitlines():
        s = ln.strip()
        if not s:
            continue
        st["last_line"] = s
        m = re.search(r"floors bigram=([0-9.]+) trigram=([0-9.]+)", s)
        if m:
            st["floors"] = {"bigram": float(m.group(1)), "trigram": float(m.group(2))}
        m = re.search(r"START Lab4 (\S+)", s)
        if m:
            st["run"] = m.group(1)
            st["phase"] = "started"
            st["events"].append(s)
        m = re.search(r"Level-A ridge valid CE ([0-9.]+)", s)
        if m:
            st["a_ridge"] = float(m.group(1))
            st["phase"] = "Level A softmax"
            st["events"].append(s)
        m = re.search(r"^\s*softmax ep(\d+): train CE ([0-9.]+)\s+valid CE ([0-9.]+)", s)
        if m and st["b_held"] is None and not st["b_eps"]:
            # Level-A softmax lines are bare "softmax ep" before B starts
            if "Level-B" not in s and "Level-C" not in s:
                st["a_eps"].append(
                    {"ep": int(m.group(1)), "train": float(m.group(2)), "valid": float(m.group(3))}
                )
                st["phase"] = f"Level A softmax ep{m.group(1)}"
        m = re.search(r"Level-A softmax held CE ([0-9.]+)", s)
        if m:
            st["a_held"] = float(m.group(1))
            st["phase"] = "Level B"
            st["events"].append(s)
        m = re.search(
            r"Level-B softmax ep(\d+): train CE ([0-9.]+)\s+valid CE ([0-9.]+).*?\((\d+(?:\.\d+)?)s\)",
            s,
        )
        if m:
            st["b_eps"].append(
                {
                    "ep": int(m.group(1)),
                    "train": float(m.group(2)),
                    "valid": float(m.group(3)),
                    "sec": float(m.group(4)),
                }
            )
            st["phase"] = f"Level B ep{m.group(1)}"
            st["events"].append(s)
        if "Level-B early stop" in s:
            st["events"].append(s)
        m = re.search(r"Level-B softmax held CE ([0-9.]+)", s)
        if m:
            st["b_held"] = float(m.group(1))
            st["phase"] = "Level C"
            st["events"].append(s)
        m = re.search(
            r"Level-C softmax ep(\d+): train CE ([0-9.]+)\s+valid CE ([0-9.]+).*?synΔ=([0-9.]+).*?\((\d+(?:\.\d+)?)s\)",
            s,
        )
        if m:
            st["c_eps"].append(
                {
                    "ep": int(m.group(1)),
                    "train": float(m.group(2)),
                    "valid": float(m.group(3)),
                    "syn": float(m.group(4)),
                    "sec": float(m.group(5)),
                }
            )
            st["phase"] = f"Level C ep{m.group(1)}"
            st["events"].append(s)
        if "Level-C early stop" in s:
            st["events"].append(s)
        m = re.search(r"Level-C softmax held CE ([0-9.]+)", s)
        if m:
            st["c_held"] = float(m.group(1))
            st["phase"] = "scramble control"
            st["events"].append(s)
        if "scramble control" in s:
            st["phase"] = "scramble control"
            st["events"].append(s)
        m = re.search(r"scramble Level-C held CE ([0-9.]+)", s)
        if m:
            st["scr_held"] = float(m.group(1))
            st["phase"] = "finishing"
            st["events"].append(s)
        m = re.search(r"DONE Lab4 (.+)", s)
        if m:
            st["done_line"] = m.group(1)
            st["phase"] = "done"
            st["events"].append(s)
    return st


def _fmt(x) -> str:
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.3f}"
    return str(x)


def grok_bluf(st: dict, log_tail: str) -> str:
    """Optional one-paragraph BLUF via local agent. Empty string on skip/fail."""
    if not AGENT.is_file():
        return ""
    inbox = JUDGE / "progress-inbox"
    outbox = JUDGE / "progress-out"
    inbox.mkdir(parents=True, exist_ok=True)
    outbox.mkdir(parents=True, exist_ok=True)
    prompt = inbox / "PROGRESS.md"
    prompt.write_text(
        "\n".join(
            [
                f"# {LABEL} progress — write ONE short plain-English paragraph (≤80 words).",
                "No code. Say: what stage, what the numbers mean vs bigram ~3.05, whether to stay engaged.",
                "",
                f"phase: {st['phase']}",
                f"A held: {_fmt(st['a_held'])}  B held: {_fmt(st['b_held'])}  C held: {_fmt(st['c_held'])}  scramble: {_fmt(st['scr_held'])}",
                f"floors: {st.get('floors')}",
                "",
                "## Recent log",
                "```",
                "\n".join(log_tail.strip().splitlines()[-40:]),
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    try:
        proc = subprocess.run(
            [
                str(AGENT),
                "-p",
                "--trust",
                "--force",
                "--model",
                "cursor-grok-4.6-high-fast",
                "--workspace",
                str(JUDGE),
                "Read progress-inbox/PROGRESS.md and print ONLY one plain-English paragraph BLUF (≤80 words).",
            ],
            cwd=str(JUDGE),
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        text = (proc.stdout or "").strip()
        lines = [
            ln
            for ln in text.splitlines()
            if ln.strip()
            and not ln.startswith("Created ")
            and "tool" not in ln.lower()[:24]
        ]
        para = " ".join(lines).strip()
        if len(para) > 600:
            para = para[:600] + "…"
        return para
    except Exception:
        return ""


def _series(st: dict) -> tuple[list[str], list[float], list[float]]:
    labels: list[str] = []
    train: list[float] = []
    valid: list[float] = []
    for ep in st["a_eps"]:
        labels.append(f"A{ep['ep']}")
        train.append(ep["train"])
        valid.append(ep["valid"])
    for ep in st["b_eps"]:
        labels.append(f"B{ep['ep']}")
        train.append(ep["train"])
        valid.append(ep["valid"])
    for ep in st["c_eps"]:
        labels.append(f"C{ep['ep']}")
        train.append(ep["train"])
        valid.append(ep["valid"])
    return labels, train, valid


def _ascii_chart(st: dict) -> str:
    """Terminal-style CE chart (always renders; no Mermaid dependency)."""
    labels, train, valid = _series(st)
    bi = st.get("floors", {}).get("bigram")
    if len(train) < 2:
        return "_Not enough epoch points for a chart yet._"
    vals = train + valid + ([bi] if isinstance(bi, (int, float)) else [])
    lo = min(vals) - 0.05
    hi = max(vals) + 0.05
    height = 10
    width = max(len(labels) * 3, 24)

    def row_for(series: list[float]) -> list[str]:
        cols = []
        for v in series:
            y = int(round((hi - v) / (hi - lo) * (height - 1))) if hi > lo else 0
            y = max(0, min(height - 1, y))
            cols.append(y)
        return cols

    t_cols = row_for(train)
    v_cols = row_for(valid)
    bi_row = None
    if isinstance(bi, (int, float)):
        bi_row = int(round((hi - bi) / (hi - lo) * (height - 1))) if hi > lo else 0
        bi_row = max(0, min(height - 1, bi_row))

    grid = [[" " for _ in range(len(labels))] for _ in range(height)]
    for x, y in enumerate(t_cols):
        grid[y][x] = "*"
    for x, y in enumerate(v_cols):
        grid[y][x] = "o" if grid[y][x] == " " else "x"
    if bi_row is not None:
        for x in range(len(labels)):
            if grid[bi_row][x] == " ":
                grid[bi_row][x] = "-"

    lines = [f"CE ↓  (y {hi:.2f} … {lo:.2f})  *=train  o=valid  x=both  -=bigram {_fmt(bi)}"]
    for r in range(height):
        label = f"{hi - (hi - lo) * r / (height - 1):5.2f} │"
        lines.append(label + " ".join(grid[r][x] for x in range(len(labels))))
    lines.append("      └" + "─" * (len(labels) * 2))
    lines.append("       " + " ".join(f"{lb:>1}"[:2] for lb in labels))
    del width  # kept for clarity if we pad later
    return "```\n" + "\n".join(lines) + "\n```"


def _mermaid_chart(st: dict) -> str:
    labels, train, valid = _series(st)
    bi = st.get("floors", {}).get("bigram")
    if len(train) < 2:
        return ""
    # Mermaid xychart — renders if Tasks markdown supports it; else ignored
    lab = ", ".join(f'"{x}"' for x in labels)
    tr = ", ".join(f"{v:.3f}" for v in train)
    va = ", ".join(f"{v:.3f}" for v in valid)
    lines = [
        "```mermaid",
        "xychart-beta",
        f'  title "{LABEL} train/valid CE (lower better)"',
        f"  x-axis [{lab}]",
        "  y-axis \"CE\" 2.8 --> 5.2",
        f"  line \"train\" [{tr}]",
        f"  line \"valid\" [{va}]",
    ]
    if isinstance(bi, (int, float)):
        floor = ", ".join(f"{bi:.3f}" for _ in labels)
        lines.append(f'  line "bigram" [{floor}]')
    lines += ["```", ""]
    return "\n".join(lines)


def render_body(st: dict, *, bluf: str = "", lab4_alive: bool = True) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    bi = st.get("floors", {}).get("bigram")
    rows = []
    for ep in st["a_eps"][-5:]:
        rows.append(f"| A softmax {ep['ep']} | {_fmt(ep['train'])} | {_fmt(ep['valid'])} | — |")
    for ep in st["b_eps"]:
        rows.append(f"| B ep{ep['ep']} ({ep['sec']:.0f}s) | {_fmt(ep['train'])} | {_fmt(ep['valid'])} | — |")
    for ep in st["c_eps"]:
        rows.append(f"| C ep{ep['ep']} ({ep['sec']:.0f}s) | {_fmt(ep['train'])} | {_fmt(ep['valid'])} | synΔ {_fmt(ep['syn'])} |")

    status = "RUNNING" if lab4_alive and st["phase"] != "done" else ("DONE" if st["phase"] == "done" else "STOPPED?")
    lines = [
        f"# Fly Cast — {LABEL}",
        "",
        f"**Updated:** {now} (live progress sidecar)",
        f"**Run:** `{st['run']}`",
        f"**Status:** **{status}** · phase **{st['phase']}**",
        f"**Machine:** FlyBrain upscaled · destroy still armed **2026-09-14 01:27 UTC**",
        "",
    ]
    if bluf:
        lines += ["## Right now (Grok)", "", bluf, ""]
    else:
        lines += ["## Right now (Grok)", "", "_Waiting on next Grok pass…_", ""]

    lines += [
        "## CE chart",
        "",
        _ascii_chart(st),
        "",
    ]
    mer = _mermaid_chart(st)
    if mer:
        lines += [mer]

    lines += [
        "## Snapshot",
        "",
        "| Gate | Value |",
        "|---|---|",
        f"| Level A ridge / held | {_fmt(st['a_ridge'])} / {_fmt(st['a_held'])} |",
        f"| Level B held | {_fmt(st['b_held'])} |",
        f"| Level C held | {_fmt(st['c_held'])} |",
        f"| Scramble (C) | {_fmt(st['scr_held'])} |",
        f"| Bigram floor | {_fmt(bi)} |",
        f"| Last log line | `{st['last_line'][:120]}` |",
        "",
        "## Epoch trail",
        "",
        "| Stage | Train CE | Valid CE | Notes |",
        "|---|---:|---:|---|",
    ]
    if rows:
        lines.extend(rows)
    else:
        lines.append("| — | — | — | waiting for epoch lines |")
    if st.get("done_line"):
        lines += ["", f"**Final:** `{st['done_line']}`", ""]
    lines += [
        "",
        "## Recent events",
        "",
    ]
    for ev in st["events"][-12:]:
        lines.append(f"- `{ev}`")
    lines += [
        "",
        "## Policy",
        "",
        "- Level C = sign-preserving synapse magnitudes + embed + readout; real CE.",
        "- Grok narrator writes the **Right now** section + a **document comment** (Notes).",
        "- Chart: ASCII always; Mermaid if the Tasks viewer renders it.",
        "- Full result table lands when `DONE Lab4` prints.",
        "",
    ]
    return "\n".join(lines) + "\n"


def fingerprint(st: dict) -> str:
    return json.dumps(
        {
            "phase": st["phase"],
            "a": len(st["a_eps"]),
            "b": len(st["b_eps"]),
            "c": len(st["c_eps"]),
            "a_held": st["a_held"],
            "b_held": st["b_held"],
            "c_held": st["c_held"],
            "scr": st["scr_held"],
            "done": st["done_line"],
            "last": st["last_line"],
        },
        sort_keys=True,
    )


STATE_PATH = ROOT / "artifacts" / "lab4" / "progress-chronicle.state.json"


def _load_state() -> dict:
    if STATE_PATH.is_file():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return {"last_fp": "", "last_bluf": "", "last_comment_key": "", "publishes": 0}


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _comment_key(phase: str, bluf: str) -> str:
    """Dedupe Notes posts across sidecar restarts (same phase + similar BLUF)."""
    import hashlib
    import re

    norm = re.sub(r"\s+", " ", (bluf or "").strip().lower())
    # drop volatile wording; keep digits so real CE changes still post
    digest = hashlib.sha1(f"{phase}|{norm}".encode()).hexdigest()[:16]
    return digest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", type=Path, default=LOG_DEFAULT)
    ap.add_argument("--interval", type=float, default=45.0)
    ap.add_argument("--doc-id", type=int, default=DOC_ID)
    ap.add_argument("--grok-every", type=int, default=3, help="Grok BLUF every N publishes (0=off)")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--label", default="Lab 4 Level C", help="human label used in titles/BLUF prompt")
    ap.add_argument("--state", type=Path, default=None, help="state json path (default artifacts/lab4/progress-chronicle.state.json)")
    ap.add_argument("--pgrep", default="python -u tools/lab4/lab4_run.py", help="process pattern that means the run is alive")
    args = ap.parse_args()
    global LABEL, PGREP, STATE_PATH
    LABEL, PGREP = args.label, args.pgrep
    if args.state:
        STATE_PATH = args.state

    if not PASS.is_file():
        raise SystemExit(f"missing {PASS}")
    env = _load_env()
    log_path = args.log if args.log.is_absolute() else ROOT / args.log

    state = _load_state()
    last_fp = state.get("last_fp") or ""
    last_bluf = state.get("last_bluf") or ""
    last_comment_key = state.get("last_comment_key") or ""
    publishes = int(state.get("publishes") or 0)
    print(f"progress chronicle → doc #{args.doc_id}; watching {log_path}", flush=True)

    while True:
        if not log_path.is_file():
            print("waiting for log…", flush=True)
            time.sleep(args.interval)
            if args.once:
                return 0
            continue
        text = log_path.read_text(encoding="utf-8", errors="replace")
        st = parse_state(text)
        fp = fingerprint(st)
        lab4_alive = (
            subprocess.run(["pgrep", "-f", PGREP], capture_output=True).returncode
            == 0
        )
        if fp != last_fp or args.once:
            fresh_grok = False
            want_grok = bool(args.grok_every) and (
                (publishes % max(args.grok_every, 1) == 0) or (not last_bluf and fp != last_fp)
            )
            # Never re-Grok solely because --once was used after a restart on the same fingerprint
            if args.once and fp == last_fp and last_bluf:
                want_grok = False
            if want_grok:
                print("  grok BLUF…", flush=True)
                got = grok_bluf(st, text)
                if got:
                    last_bluf = got
                    fresh_grok = True
            body = render_body(st, bluf=last_bluf, lab4_alive=lab4_alive)
            try:
                _api(
                    env,
                    "POST",
                    "update-document.php",
                    {
                        "id": args.doc_id,
                        "title": f"Fly Cast — {LABEL} ({st['run']})",
                        "body": body,
                        "directory_path": "research",
                    },
                )
                if fresh_grok and last_bluf:
                    ckey = _comment_key(st["phase"], last_bluf)
                    if ckey == last_comment_key:
                        print("  skip duplicate document comment", flush=True)
                    else:
                        try:
                            _api(
                                env,
                                "POST",
                                "create-document-comment.php",
                                {
                                    "document_id": args.doc_id,
                                    "comment": f"**Grok progress** · `{st['phase']}`\n\n{last_bluf}",
                                },
                            )
                            last_comment_key = ckey
                            print("  document comment posted", flush=True)
                        except Exception as cexc:  # noqa: BLE001
                            print(f"  comment warn: {cexc}", flush=True)
                publishes += 1
                last_fp = fp
                _save_state(
                    {
                        "last_fp": last_fp,
                        "last_bluf": last_bluf,
                        "last_comment_key": last_comment_key,
                        "publishes": publishes,
                    }
                )
                print(f"  updated doc #{args.doc_id} phase={st['phase']} publishes={publishes}", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"  chronicle warn: {exc}", flush=True)
        if args.once or st["phase"] == "done":
            if st["phase"] == "done":
                print("lab4 done — sidecar exit", flush=True)
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())

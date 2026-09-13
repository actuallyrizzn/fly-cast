#!/usr/bin/env python3
"""Force-republish Lab 5 chronicle with current chart code."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path

ROOT = Path("/root/fly-cast")
os.chdir(ROOT)
os.environ.setdefault("FLYBRAIN_DESTROY_AT", "2026-09-16T01:27:00Z")

spec = importlib.util.spec_from_file_location(
    "chr", ROOT / "tools/lab4/lab4_progress_chronicle.py"
)
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
c.LABEL = "Lab 5 Desk go/no-go"

log = (ROOT / "artifacts/lab5/desk/lab5-desk-run.log").read_text(encoding="utf-8")
st = c.parse_state(log)
print("floors", st.get("floors"))
print("ascii_legend", c._ascii_chart(st).splitlines()[1])
print("mermaid", [ln for ln in c._mermaid_chart(st).splitlines() if "line" in ln or "y-axis" in ln])

state_path = ROOT / "artifacts/lab5/desk/progress-chronicle.state.json"
state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
body = c.render_body(st, bluf=state.get("last_bluf") or "", lab4_alive=True)
env = c._load_env()
title = f"Fly Cast — Lab 5 Desk go/no-go ({st.get('run') or 'run'})"
out = c._api(env, "POST", "update-document.php", {"id": 1334, "body": body, "title": title})
print("api", out.get("status") or out.get("ok") or out)

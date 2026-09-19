#!/usr/bin/env python3
"""Serve a live status page for whatever job is using the ngram laptop."""

from __future__ import annotations

import argparse
from pathlib import Path

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>ngram — waiting</title>
<style>
  body { margin: 0; background: #1c1915; color: #f4f0e6;
    font-family: "Segoe UI", "Helvetica Neue", sans-serif; }
  main { padding: 2.2rem 2.4rem; }
  h1 { font-size: 32px; margin: 0 0 0.6rem; }
  .step { font-size: 22px; margin: 0.2rem 0; }
  .meta { font-size: 20px; color: #d7cbb8; margin: 0.15rem 0; }
  .stale { color: #e0a060; }
</style>
</head>
<body>
<main>
  <h1 id="job">waiting</h1>
  <p class="step" id="step">no status yet</p>
  <p class="meta" id="progress"></p>
  <p class="meta" id="elapsed"></p>
  <p class="meta" id="numbers"></p>
</main>
<script>
async function tick() {
  try {
    const res = await fetch("desk_status.txt?t=" + Date.now(), {cache: "no-store"});
    if (!res.ok) throw new Error(String(res.status));
    const lines = (await res.text()).split(/\\n/);
    const job = (lines[0] || "waiting").trim();
    document.getElementById("job").textContent = job;
    document.getElementById("step").textContent = (lines[1] || "").trim();
    document.getElementById("progress").textContent = (lines[2] || "").trim();
    document.getElementById("elapsed").textContent = (lines[3] || "").trim();
    document.getElementById("numbers").textContent = (lines[4] || "").trim();
    document.title = "ngram — " + job;
    document.body.classList.remove("stale");
  } catch (err) {
    document.getElementById("numbers").textContent = "status file unreadable";
  }
}
tick();
setInterval(tick, 2000);
</script>
</body>
</html>
"""


def write_page(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "index.html"
    path.write_text(PAGE, encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path, required=True)
    args = parser.parse_args()
    print(write_page(args.dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

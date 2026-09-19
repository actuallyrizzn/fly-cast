"""Live state.json the watch page reads. Atomic writes + glass frames."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = ["frame", "read", "write"]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def read(run_dir: str | Path) -> dict[str, Any]:
    path = Path(run_dir) / "state.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write(run_dir: str | Path, **fields: Any) -> dict[str, Any]:
    """Merge fields into state.json. Atomic via temp file + os.replace."""
    directory = Path(run_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "state.json"
    current = read(directory)
    current.update(fields)
    current["updated"] = _now()
    temp = directory / "state.json.tmp"
    temp.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)
    return current


def _append_index(frames: Path, filename: str, tag: str, phase: str) -> None:
    index = frames / "index.tsv"
    if not index.exists():
        index.write_text("filename\ttag\tiso\tphase\n", encoding="utf-8")
    with index.open("a", encoding="utf-8") as handle:
        handle.write(f"{filename}\t{tag}\t{_now()}\t{phase}\n")


def _scrot(path: Path) -> bool:
    """Compositor grab. Short timeout — GNOME often hangs or blanks this path."""
    if not os.environ.get("DISPLAY"):
        return False
    if not shutil.which("scrot"):
        return False
    try:
        subprocess.run(
            ["scrot", "-q", "80", str(path)],
            check=True,
            timeout=5,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return False
    return path.exists() and path.stat().st_size > 20_000


def _webkit_snapshot(url: str, path: Path) -> bool:
    """Render the watch URL into a PNG. Works when GNOME blocks compositor shots."""
    script = Path(__file__).resolve().parents[3] / "tools" / "jevlab" / "snapshot_url.py"
    if not script.exists():
        return False
    env = os.environ.copy()
    env.setdefault("GDK_BACKEND", "x11")
    try:
        subprocess.run(
            [sys_executable(), str(script), url, str(path)],
            check=True,
            timeout=60,
            env=env,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return False
    return path.exists() and path.stat().st_size > 5_000


def sys_executable() -> str:
    return os.environ.get("PYTHON", "python3")


def frame(run_dir: str | Path, tag: str) -> Path:
    """Capture one frame into run_dir/frames/. Prefer watch-URL WebKit when present."""
    run_dir = Path(run_dir)
    frames = run_dir / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    phase = str(read(run_dir).get("phase") or "")
    stamp = _stamp()
    png_name = f"{stamp}_{tag}.png"
    png = frames / png_name
    glass = False

    url_path = run_dir / "watch" / "URL"
    url = url_path.read_text(encoding="utf-8").strip() if url_path.exists() else ""

    # Prefer WebKit of the watch page when the server is up — scrot/GNOME often blanks.
    if url and _webkit_snapshot(url, png):
        glass = True
    elif _scrot(png):
        glass = True
    else:
        if png.exists():
            png.unlink()
        missing = frames / f"MISSING_{tag}.txt"
        missing.write_text(
            f"no glass frame for tag={tag} at {_now()}\n"
            f"DISPLAY={os.environ.get('DISPLAY', '')!r}\n"
            f"url={url!r}\n",
            encoding="utf-8",
        )
        _append_index(frames, missing.name, tag, phase)
        write(run_dir, glass=False)
        return missing

    _append_index(frames, png_name, tag, phase)
    write(run_dir, glass=glass)
    return png

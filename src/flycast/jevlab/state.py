"""Live state.json the watch page reads. Atomic writes."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = ["read", "write"]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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

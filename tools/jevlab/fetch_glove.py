"""Checksum glove.6B.100d.txt and write its manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_LINES = 400_000
LICENCE = "PDDL 1.0"
SOURCE = "https://nlp.stanford.edu/data/glove.6B.zip"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _line_count(path: Path) -> int:
    n = 0
    with path.open("rb") as handle:
        for _ in handle:
            n += 1
    return n


def ensure(root: Path) -> tuple[int, str]:
    root.mkdir(parents=True, exist_ok=True)
    text = root / "glove.6B.100d.txt"
    archive = root / "glove.6B.zip"
    if not text.exists():
        if not archive.exists():
            raise SystemExit(f"missing {text} and {archive}")
        with zipfile.ZipFile(archive) as zipped:
            zipped.extract("glove.6B.100d.txt", path=root)
    lines = _line_count(text)
    digest = _sha256(text)
    manifest = {
        "file": "glove.6B.100d.txt",
        "source_url": SOURCE,
        "licence": LICENCE,
        "lines": lines,
        "sha256": digest,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    (root / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return lines, digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    lines, digest = ensure(args.root.expanduser())
    print(f"lines {lines}")
    print(digest)
    if args.check and lines != EXPECTED_LINES:
        raise SystemExit(f"expected {EXPECTED_LINES} lines, got {lines}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

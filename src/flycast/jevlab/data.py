"""Load frozen Jev-lab splits and check their manifests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from flycast.tokenizer import _TOKEN_RE

__all__ = [
    "load_split",
    "sha256_file",
    "stratified_indices",
    "token_count",
    "verify_manifest",
    "write_manifest",
    "write_tsv",
]


def stratified_indices(labels: list[Any] | np.ndarray, n: int, seed: int) -> np.ndarray:
    """Return ``n`` indices, stratified by label, drawn with ``default_rng(seed)``."""
    arr = np.asarray(labels)
    if n < 0 or n > len(arr):
        raise ValueError(f"n={n} out of range for {len(arr)} rows")
    if n == 0:
        return np.array([], dtype=np.int64)
    classes, counts = np.unique(arr, return_counts=True)
    raw = counts.astype(np.float64) / counts.sum() * n
    take = np.floor(raw).astype(np.int64)
    # Largest remainder, never exceeding the class size.
    order = np.argsort(-(raw - take))
    left = int(n - take.sum())
    for i in order:
        if left <= 0:
            break
        room = int(counts[i] - take[i])
        if room <= 0:
            continue
        take[i] += 1
        left -= 1
    if int(take.sum()) != n:
        raise ValueError("could not allocate a stratified sample")
    rng = np.random.default_rng(seed)
    chosen: list[np.ndarray] = []
    for cls, k in zip(classes, take):
        pool = np.flatnonzero(arr == cls)
        chosen.append(rng.choice(pool, size=int(k), replace=False))
    return np.sort(np.concatenate(chosen).astype(np.int64))


def token_count(text: str) -> int:
    return len(_TOKEN_RE.findall(text.lower()))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_tsv(path: Path, rows: list[tuple[str, str, int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["id\ttext\tlabel"]
    for row_id, text, label in rows:
        clean = text.replace("\t", " ").replace("\n", " ").replace("\r", " ")
        lines.append(f"{row_id}\t{clean}\t{int(label)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_manifest(directory: Path, manifest: dict[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def _task_dir(task: str, root: str | Path) -> Path:
    return Path(root).expanduser() / task


def load_split(
    task: str,
    split: str,
    root: str | Path | None = None,
) -> list[tuple[str, int]]:
    if root is None:
        raise ValueError("root is required")
    path = _task_dir(task, root) / f"{split}.tsv"
    rows: list[tuple[str, int]] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "id\ttext\tlabel":
        raise ValueError(f"bad header in {path}")
    for line in lines[1:]:
        if not line:
            continue
        _row_id, text, label = line.split("\t")
        rows.append((text, int(label)))
    return rows


def verify_manifest(task: str, root: str | Path | None = None) -> dict[str, Any]:
    if root is None:
        raise ValueError("root is required")
    directory = _task_dir(task, root)
    path = directory / "MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        file_path = directory / entry["name"]
        got = sha256_file(file_path)
        if got != entry["sha256"]:
            raise ValueError(f"{entry['name']}: sha256 {got} != {entry['sha256']}")
        n_lines = sum(1 for _ in file_path.open(encoding="utf-8"))
        # Header plus data rows.
        if n_lines - 1 != entry["rows"]:
            raise ValueError(f"{entry['name']}: rows {n_lines - 1} != {entry['rows']}")
    return manifest

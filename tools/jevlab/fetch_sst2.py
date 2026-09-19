"""Freeze SST-2 into train / valid / test plus a negation slice."""

from __future__ import annotations

import argparse
import csv
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from flycast.jevlab.data import (
    sha256_file,
    stratified_indices,
    token_count,
    verify_manifest,
    write_manifest,
    write_tsv,
)

NEGATION = re.compile(r"\b(not|no|never|nothing|nobody|neither|nor)\b|n't")
SOURCE = "https://dl.fbaipublicfiles.com/glue/data/SST-2.zip"
LICENCE = "GLUE/SST-2, research use"


def _read_glue(zip_path: Path, name: str) -> list[tuple[str, int]]:
    with zipfile.ZipFile(zip_path) as archive:
        raw = archive.read(name).decode("utf-8")
    rows = list(csv.reader(raw.splitlines(), delimiter="\t"))
    if rows[0][:2] != ["sentence", "label"]:
        raise ValueError(f"unexpected header in {name}: {rows[0]}")
    return [(sentence, int(label)) for sentence, label in rows[1:]]


def build(root: Path, *, seed: int = 7, valid_n: int = 3000) -> dict[str, int]:
    raw = root / "sst2" / "raw" / "SST-2.zip"
    train_rows = _read_glue(raw, "SST-2/train.tsv")
    test_rows = _read_glue(raw, "SST-2/dev.tsv")
    labels = [label for _text, label in train_rows]
    valid_idx = set(int(i) for i in stratified_indices(labels, valid_n, seed))
    out = root / "sst2"
    train_out = [
        (f"train-{i}", text, label)
        for i, (text, label) in enumerate(train_rows)
        if i not in valid_idx
    ]
    valid_out = [
        (f"train-{i}", text, label)
        for i, (text, label) in enumerate(train_rows)
        if i in valid_idx
    ]
    test_out = [(f"dev-{i}", text, label) for i, (text, label) in enumerate(test_rows)]
    negation = [
        row for row in test_out if NEGATION.search(row[1].lower())
    ]
    files = {
        "train.tsv": train_out,
        "valid.tsv": valid_out,
        "test.tsv": test_out,
        "test_negation.tsv": negation,
    }
    for name, rows in files.items():
        write_tsv(out / name, rows)

    def counts(rows: list[tuple[str, str, int]]) -> dict[str, int]:
        tally: dict[str, int] = {}
        for _row_id, _text, label in rows:
            key = str(label)
            tally[key] = tally.get(key, 0) + 1
        return tally

    def length_stats(rows: list[tuple[str, str, int]]) -> dict[str, float]:
        lengths = [token_count(text) for _row_id, text, _label in rows]
        return {
            "mean_tokens": round(sum(lengths) / len(lengths), 3),
            "max_tokens": max(lengths),
        }

    file_entries = []
    for name, rows in files.items():
        path = out / name
        file_entries.append(
            {
                "name": name,
                "sha256": sha256_file(path),
                "rows": len(rows),
                "label_counts": counts(rows),
                **length_stats(rows),
            }
        )
    write_manifest(
        out,
        {
            "task": "sst2",
            "source_url": SOURCE,
            "licence": LICENCE,
            "seed": seed,
            "valid_n": valid_n,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "files": file_entries,
        },
    )
    verify_manifest("sst2", root=root)
    return {name: len(rows) for name, rows in files.items()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    counts = build(args.root.expanduser())
    print(
        "sst2 "
        f"train={counts['train.tsv']} valid={counts['valid.tsv']} "
        f"test={counts['test.tsv']} negation={counts['test_negation.tsv']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

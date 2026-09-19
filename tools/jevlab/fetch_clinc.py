"""Freeze CLINC150 and the 10-intent subset, plus a confusable slice."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from flycast.jevlab.data import (
    confusable_mask,
    sha256_file,
    token_count,
    verify_manifest,
    write_manifest,
    write_tsv,
)

SOURCE = "https://raw.githubusercontent.com/clinc/oos-eval/master/data/data_full.json"
LICENCE = "CC-BY-3.0 (CLINC150 / oos-eval)"
CLINC10 = (
    "alarm",
    "calculator",
    "date",
    "definition",
    "measurement_conversion",
    "spelling",
    "time",
    "timer",
    "translate",
    "weather",
)


def _rows(raw: list, labels: dict[str, int], *, prefix: str) -> list[tuple[str, str, int]]:
    out = []
    for i, (text, intent) in enumerate(raw):
        if intent not in labels:
            continue
        out.append((f"{prefix}-{i}", str(text), labels[intent]))
    return out


def _file_entry(path: Path, rows: list[tuple[str, str, int]]) -> dict:
    tally: dict[str, int] = {}
    lengths = []
    for _row_id, text, label in rows:
        key = str(label)
        tally[key] = tally.get(key, 0) + 1
        lengths.append(token_count(text))
    return {
        "name": path.name,
        "sha256": sha256_file(path),
        "rows": len(rows),
        "label_counts": tally,
        "mean_tokens": round(sum(lengths) / len(lengths), 3) if lengths else 0,
        "max_tokens": max(lengths) if lengths else 0,
    }


def _write_task(
    root: Path,
    task: str,
    data: dict,
    intents: list[str],
    *,
    with_oos: bool,
    confusable: bool,
) -> dict[str, int]:
    labels = {name: i for i, name in enumerate(intents)}
    if with_oos:
        labels["oos"] = len(intents)
    train = _rows(data["train"], labels, prefix="train") + (
        _rows(data["oos_train"], labels, prefix="oos-train") if with_oos else []
    )
    valid = _rows(data["val"], labels, prefix="val") + (
        _rows(data["oos_val"], labels, prefix="oos-val") if with_oos else []
    )
    test = _rows(data["test"], labels, prefix="test") + (
        _rows(data["oos_test"], labels, prefix="oos-test") if with_oos else []
    )
    out = root / task
    files = {"train.tsv": train, "valid.tsv": valid, "test.tsv": test}
    if confusable:
        mask = confusable_mask(
            [text for _i, text, _l in train],
            [label for _i, _t, label in train],
            [text for _i, text, _l in test],
            [label for _i, _t, label in test],
        )
        files["test_confusable.tsv"] = [row for row, flag in zip(test, mask) if flag]
    for name, rows in files.items():
        write_tsv(out / name, rows)
    (out / "labels.json").write_text(
        json.dumps(intents + (["oos"] if with_oos else []), indent=2) + "\n",
        encoding="utf-8",
    )
    write_manifest(
        out,
        {
            "task": task,
            "source_url": SOURCE,
            "licence": LICENCE,
            "intents": intents + (["oos"] if with_oos else []),
            "substitutions": [],
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "files": [_file_entry(out / name, rows) for name, rows in files.items()],
        },
    )
    verify_manifest(task, root=root)
    return {name: len(rows) for name, rows in files.items()}


def build(root: Path) -> dict[str, dict[str, int]]:
    raw_path = root / "clinc" / "raw" / "data_full.json"
    data = json.loads(raw_path.read_text(encoding="utf-8"))
    have = {row[1] for row in data["train"]}
    missing = [name for name in CLINC10 if name not in have]
    if missing:
        raise ValueError(f"missing intents: {missing}")
    intents_150 = sorted(have)
    return {
        "clinc150": _write_task(root, "clinc150", data, intents_150, with_oos=True, confusable=False),
        "clinc10": _write_task(root, "clinc10", data, list(CLINC10), with_oos=False, confusable=True),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    counts = build(args.root.expanduser())
    for task, files in counts.items():
        extra = ""
        if "test_confusable.tsv" in files:
            extra = f" confusable={files['test_confusable.tsv']}"
        print(
            f"{task} train={files['train.tsv']} valid={files['valid.tsv']} "
            f"test={files['test.tsv']}{extra}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

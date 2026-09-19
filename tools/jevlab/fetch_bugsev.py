"""Freeze Eclipse bug severity into a 3-class train / valid / test."""

from __future__ import annotations

import argparse
import json
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

SOURCE = "https://github.com/ansymo/msr2013-bug_dataset"
LICENCE = (
    "No licence file in the repo. README asks to cite Lamkanfi, Perez, "
    "and Demeyer, MSR 2013 (The Eclipse and Mozilla Defect Tracking Dataset)."
)
LABELS = {"low": 0, "normal": 1, "high": 2}
SEVERITY = {
    "trivial": 0,
    "minor": 0,
    "normal": 1,
    "major": 2,
    "critical": 2,
    "blocker": 2,
}
CAP = 20000


def _last_what(history: list[dict] | None) -> str:
    if not history:
        return ""
    latest = max(history, key=lambda item: item.get("when", 0))
    return str(latest.get("what") or "").strip()


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    key = next(iter(payload))
    return payload[key]


def build(root: Path, *, seed: int = 7) -> dict[str, int]:
    raw = root / "bugsev" / "raw" / "msr2013-bug_dataset" / "data" / "v02" / "eclipse"
    titles = _load(raw / "short_desc.json")
    severities = _load(raw / "severity.json")
    before: dict[str, int] = {name: 0 for name in LABELS}
    dropped = {"enhancement": 0, "empty": 0, "other": 0, "no_title": 0}
    rows: list[tuple[str, str, int]] = []
    for bug_id, history in severities.items():
        severity = _last_what(history).lower()
        label = SEVERITY.get(severity)
        if label is None:
            if severity == "enhancement":
                dropped["enhancement"] += 1
            elif not severity:
                dropped["empty"] += 1
            else:
                dropped["other"] += 1
            continue
        title = _collapse(_last_what(titles.get(bug_id)))
        if not title:
            dropped["no_title"] += 1
            continue
        name = next(key for key, value in LABELS.items() if value == label)
        before[name] += 1
        rows.append((str(bug_id), title, label))

    labels = [label for _bug_id, _text, label in rows]
    if len(rows) > CAP:
        keep = {int(i) for i in stratified_indices(labels, CAP, seed)}
        capped = [row for i, row in enumerate(rows) if i in keep]
    else:
        capped = rows
    after: dict[str, int] = {name: 0 for name in LABELS}
    for _bug_id, _text, label in capped:
        name = next(key for key, value in LABELS.items() if value == label)
        after[name] += 1

    n = len(capped)
    n_test = n // 10
    n_valid = n // 10
    cap_labels = [label for _bug_id, _text, label in capped]
    test_idx = {int(i) for i in stratified_indices(cap_labels, n_test, seed)}
    remain = [i for i in range(n) if i not in test_idx]
    remain_labels = [cap_labels[i] for i in remain]
    valid_local = {int(i) for i in stratified_indices(remain_labels, n_valid, seed)}
    valid_idx = {remain[i] for i in valid_local}
    splits: dict[str, list[tuple[str, str, int]]] = {"train": [], "valid": [], "test": []}
    for i, row in enumerate(capped):
        if i in test_idx:
            splits["test"].append(row)
        elif i in valid_idx:
            splits["valid"].append(row)
        else:
            splits["train"].append(row)

    out = root / "bugsev"
    for name, split_rows in splits.items():
        write_tsv(out / f"{name}.tsv", split_rows)
    (out / "labels.json").write_text(
        json.dumps({"0": "low", "1": "normal", "2": "high"}, indent=2) + "\n",
        encoding="utf-8",
    )

    def counts(split_rows: list[tuple[str, str, int]]) -> dict[str, int]:
        tally = {"0": 0, "1": 0, "2": 0}
        for _bug_id, _text, label in split_rows:
            tally[str(label)] += 1
        return tally

    def length_stats(split_rows: list[tuple[str, str, int]]) -> dict[str, float]:
        lengths = [token_count(text) for _bug_id, text, _label in split_rows]
        return {
            "mean_tokens": round(sum(lengths) / len(lengths), 3),
            "max_tokens": max(lengths),
        }

    files = []
    for name, split_rows in splits.items():
        path = out / f"{name}.tsv"
        files.append(
            {
                "name": f"{name}.tsv",
                "sha256": sha256_file(path),
                "rows": len(split_rows),
                "label_counts": counts(split_rows),
                **length_stats(split_rows),
            }
        )
    write_manifest(
        out,
        {
            "task": "bugsev",
            "source_url": SOURCE,
            "licence": LICENCE,
            "seed": seed,
            "cap": CAP,
            "class_counts_before_cap": before,
            "class_counts_after_cap": after,
            "truncation_fraction_400": 0.0,
            "notes": (
                "Used data/v02/eclipse JSON, not the per-product XML tarball. "
                "That release has no description or long_desc field, so text is "
                "the latest short_desc only and truncation_fraction_400 is 0. "
                "Severity and title are the history entry with the greatest when. "
                f"Dropped {dropped}."
            ),
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "files": files,
        },
    )
    verify_manifest("bugsev", root=root)
    return {name: len(split_rows) for name, split_rows in splits.items()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    counts = build(args.root.expanduser())
    print(f"bugsev train={counts['train']} valid={counts['valid']} test={counts['test']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

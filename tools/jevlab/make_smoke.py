"""Cut 400/50/50 smoke slices and a mini GloVe from the ngram data root."""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from flycast.jevlab.data import sha256_file, stratified_indices, token_count, write_manifest, write_tsv
from flycast.tokenizer import _TOKEN_RE

TASKS = ("sst2", "clinc10", "bugsev")
TAKE = {"train": 400, "valid": 50, "test": 50}


def _read_tsv(path: Path) -> list[tuple[str, str, int]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "id\ttext\tlabel":
        raise ValueError(f"bad header in {path}")
    rows = []
    for line in lines[1:]:
        if not line:
            continue
        row_id, text, label = line.split("\t")
        rows.append((row_id, text, int(label)))
    return rows


def _sample(rows: list[tuple[str, str, int]], n: int, seed: int) -> list[tuple[str, str, int]]:
    if len(rows) <= n:
        return rows
    labels = [label for _row_id, _text, label in rows]
    keep = {int(i) for i in stratified_indices(labels, n, seed)}
    return [row for i, row in enumerate(rows) if i in keep]


def _counts(rows: list[tuple[str, str, int]]) -> dict[str, int]:
    tally: dict[str, int] = {}
    for _row_id, _text, label in rows:
        key = str(label)
        tally[key] = tally.get(key, 0) + 1
    return tally


def build(data_root: Path, glove_path: Path, out: Path, *, seed: int = 7) -> None:
    words: Counter[str] = Counter()
    out.mkdir(parents=True, exist_ok=True)
    for task in TASKS:
        src = data_root / task
        dest = out / task
        dest.mkdir(parents=True, exist_ok=True)
        files = []
        for split, n in TAKE.items():
            rows = _sample(_read_tsv(src / f"{split}.tsv"), n, seed)
            write_tsv(dest / f"{split}.tsv", rows)
            for _row_id, text, _label in rows:
                for tok in _TOKEN_RE.findall(text.lower()):
                    if any(ch.isalnum() for ch in tok):
                        words[tok] += 1
            path = dest / f"{split}.tsv"
            lengths = [token_count(text) for _row_id, text, _label in rows]
            files.append(
                {
                    "name": f"{split}.tsv",
                    "sha256": sha256_file(path),
                    "rows": len(rows),
                    "label_counts": _counts(rows),
                    "mean_tokens": round(sum(lengths) / len(lengths), 3),
                    "max_tokens": max(lengths),
                }
            )
        labels = src / "labels.json"
        if labels.exists():
            shutil.copyfile(labels, dest / "labels.json")
        elif task == "sst2":
            (dest / "labels.json").write_text(
                json.dumps({"0": "negative", "1": "positive"}, indent=2) + "\n",
                encoding="utf-8",
            )
        write_manifest(
            dest,
            {
                "task": task,
                "source_url": "smoke slice of the frozen ngram split",
                "licence": "same as the parent task",
                "seed": seed,
                "notes": "400 train / 50 valid / 50 test, stratified, seed 7.",
                "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                "files": files,
            },
        )

    wanted = set(words)
    if not wanted:
        raise ValueError("smoke slices produced no words")
    mini = out / "glove.mini.txt"
    kept = 0
    with glove_path.open(encoding="utf-8") as src, mini.open("w", encoding="utf-8") as dst:
        for line in src:
            word = line.partition(" ")[0].lower()
            if word in wanted:
                dst.write(line if line.endswith("\n") else line + "\n")
                kept += 1
                wanted.discard(word)
                if not wanted:
                    break
    size = mini.stat().st_size
    if size > 8_000_000:
        frequent = {word for word, _n in words.most_common(3000)}
        lines = []
        with mini.open(encoding="utf-8") as handle:
            for line in handle:
                if line.partition(" ")[0].lower() in frequent:
                    lines.append(line)
        mini.write_text("".join(lines), encoding="utf-8")
        kept = len(lines)
        size = mini.stat().st_size
    print(f"smoke words={len(words)} glove_lines={kept} bytes={size}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--glove", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    build(args.data_root.expanduser(), args.glove.expanduser(), args.out.expanduser())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

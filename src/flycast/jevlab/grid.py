"""Validation-only grid. Never loads the test split."""

from __future__ import annotations

import itertools
import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from flycast.jevlab.arms import ArmCfg
from flycast.jevlab.cache import feature_path
from flycast.jevlab.readout import fit_ridge_classes, metrics, predict_proba

__all__ = ["cfg_grid", "done_keys", "rank_stage1", "score_point"]

PROTOCOL = Path(__file__).resolve().parents[3] / "tools" / "jevlab" / "protocol.json"


def cfg_grid(protocol: dict | None = None) -> list[ArmCfg]:
    data = protocol or json.loads(PROTOCOL.read_text(encoding="utf-8"))
    grid = data["grid"]
    out: list[ArmCfg] = []
    for leak, steps, radius, inject, scale, pooling in itertools.product(
        grid["leak"],
        grid["steps"],
        grid["radius"],
        grid["inject_count"],
        grid["input_scale"],
        grid["pooling"],
    ):
        out.append(
            ArmCfg(
                leak=float(leak),
                steps=int(steps),
                radius=float(radius),
                inject_count=int(inject),
                input_scale=float(scale),
                pooling=str(pooling),
                seed=0,
            )
        )
    return out


def done_keys(jsonl: Path) -> set[tuple[str, str, int]]:
    found: set[tuple[str, str, int]] = set()
    if not jsonl.exists():
        return found
    for line in jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        found.add((row["arm"], row["cfg"], int(row["seed"])))
    return found


def rank_stage1(jsonl: Path, arm: str, top: int = 10) -> list[dict[str, Any]]:
    rows = []
    if not jsonl.exists():
        return rows
    for line in jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row["arm"] != arm:
            continue
        rows.append(row)
    rows.sort(key=lambda item: (-float(item["valid"]["acc"]), item["cfg"]))
    return rows[:top]


def _data_root(root: Path, task: str) -> Path:
    if (root / "data" / task).is_dir():
        return root / "data"
    return root


def _labels_for_features(root: Path, task: str, split: str) -> np.ndarray:
    data = _data_root(root, task)
    tsv = data / task / f"{split}.tsv"
    by_id: dict[str, int] = {}
    for line in tsv.read_text(encoding="utf-8").splitlines()[1:]:
        if not line:
            continue
        row_id, _text, label = line.split("\t")
        by_id[row_id] = int(label)
    if split == "train":
        cap = root / "cache" / task / "train_cap_ids.json"
        if cap.exists():
            order = json.loads(cap.read_text(encoding="utf-8"))["ids"]
            return np.asarray([by_id[row_id] for row_id in order], dtype=np.int64)
    return np.asarray(list(by_id.values()), dtype=np.int64)


def score_point(
    *,
    root: Path,
    task: str,
    arm: str,
    cfg: ArmCfg,
    seed: int,
    train_cap: int,
) -> dict[str, Any]:
    """Cache train+valid features, fit ridge on train, score valid. Never touches test."""
    import sys

    repo = Path(__file__).resolve().parents[3]
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    from tools.jevlab.cache_features import main as cache_main

    cfg = ArmCfg(
        leak=cfg.leak,
        steps=cfg.steps,
        radius=cfg.radius,
        inject_count=cfg.inject_count,
        input_scale=cfg.input_scale,
        pooling=cfg.pooling,
        seed=seed,
    )
    started = time.perf_counter()
    cache_main(
        [
            "--task",
            task,
            "--arms",
            arm,
            "--cfg",
            json.dumps(
                {
                    "leak": cfg.leak,
                    "steps": cfg.steps,
                    "radius": cfg.radius,
                    "inject_count": cfg.inject_count,
                    "input_scale": cfg.input_scale,
                    "pooling": cfg.pooling,
                    "seed": cfg.seed,
                }
            ),
            "--splits",
            "train,valid",
            "--train-cap",
            str(train_cap),
            "--root",
            str(root),
        ]
    )
    x_train = np.load(feature_path(root / "cache", task, arm, cfg.key(), "train")).astype(np.float32)
    x_valid = np.load(feature_path(root / "cache", task, arm, cfg.key(), "valid")).astype(np.float32)
    y_train = _labels_for_features(root, task, "train")
    y_valid = _labels_for_features(root, task, "valid")
    if len(y_train) != len(x_train) or len(y_valid) != len(x_valid):
        raise ValueError(
            f"label/feature mismatch train {len(y_train)}/{len(x_train)} "
            f"valid {len(y_valid)}/{len(x_valid)}"
        )
    n_classes = int(max(int(y_train.max()), int(y_valid.max())) + 1)
    head, _info = fit_ridge_classes(x_train, y_train, n_classes, x_valid=x_valid, y_valid=y_valid)
    valid = metrics(predict_proba(head, x_valid), y_valid)
    return {
        "arm": arm,
        "cfg": cfg.key(),
        "seed": seed,
        "valid": valid,
        "seconds": time.perf_counter() - started,
        "ridge": head.lam,
        "temperature": head.temperature,
    }

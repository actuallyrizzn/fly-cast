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

__all__ = ["cfg_grid", "done_keys", "rank_stage1", "score_point", "score_pooling_family"]

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
    rows = score_pooling_family(
        root=root,
        task=task,
        arm=arm,
        cfgs=[cfg],
        seed=seed,
        train_cap=train_cap,
    )
    return rows[0]


def _slice_pooling(wide: np.ndarray, pooling: str) -> np.ndarray:
    """Derive last / mean / last+mean columns from a last+mean feature matrix."""
    if pooling == "last+mean":
        return wide
    width = wide.shape[1]
    if width % 2 != 0:
        raise ValueError(f"last+mean width must be even, got {width}")
    n = width // 2
    if pooling == "last":
        return wide[:, :n]
    if pooling == "mean":
        return wide[:, n:]
    raise ValueError(f"bad pooling {pooling}")


def _write_derived_cache(
    *,
    root: Path,
    task: str,
    arm: str,
    cfg: ArmCfg,
    split: str,
    features: np.ndarray,
    tokenizer_fingerprint: str,
) -> None:
    from flycast.jevlab.cache import feature_path, save_sidecar

    npy = feature_path(root / "cache", task, arm, cfg.key(), split)
    npy.parent.mkdir(parents=True, exist_ok=True)
    np.save(npy, features.astype(np.float16))
    # np.save adds .npy; feature_path already ends in .npy — np.save is correct.
    save_sidecar(
        npy.with_suffix(".json"),
        {
            "task": task,
            "arm": arm,
            "cfg_key": cfg.key(),
            "split": split,
            "pooling": cfg.pooling,
            "n_rows": int(features.shape[0]),
            "tokenizer_fingerprint": tokenizer_fingerprint,
            "derived_from": "last+mean",
        },
    )


def score_pooling_family(
    *,
    root: Path,
    task: str,
    arm: str,
    cfgs: list[ArmCfg],
    seed: int,
    train_cap: int,
    write_derived: bool = True,
) -> list[dict[str, Any]]:
    """Drive the reservoir once (last+mean), then score each pooling variant.

    Same features as separate score_point calls; ~3× fewer reservoir passes when
    last/mean/last+mean are requested together.
    """
    import sys

    repo = Path(__file__).resolve().parents[3]
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    from tools.jevlab.cache_features import main as cache_main

    if not cfgs:
        return []
    started = time.perf_counter()
    base = cfgs[0]
    wide_cfg = ArmCfg(
        leak=base.leak,
        steps=base.steps,
        radius=base.radius,
        inject_count=base.inject_count,
        input_scale=base.input_scale,
        pooling="last+mean",
        seed=seed,
    )
    cache_main(
        [
            "--task",
            task,
            "--arms",
            arm,
            "--cfg",
            json.dumps(
                {
                    "leak": wide_cfg.leak,
                    "steps": wide_cfg.steps,
                    "radius": wide_cfg.radius,
                    "inject_count": wide_cfg.inject_count,
                    "input_scale": wide_cfg.input_scale,
                    "pooling": wide_cfg.pooling,
                    "seed": wide_cfg.seed,
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
    x_train_wide = np.load(
        feature_path(root / "cache", task, arm, wide_cfg.key(), "train")
    ).astype(np.float32)
    x_valid_wide = np.load(
        feature_path(root / "cache", task, arm, wide_cfg.key(), "valid")
    ).astype(np.float32)
    sidecar = feature_path(root / "cache", task, arm, wide_cfg.key(), "train").with_suffix(
        ".json"
    )
    fingerprint = ""
    if sidecar.exists():
        fingerprint = str(json.loads(sidecar.read_text(encoding="utf-8")).get(
            "tokenizer_fingerprint", ""
        ))
    y_train = _labels_for_features(root, task, "train")
    y_valid = _labels_for_features(root, task, "valid")
    if len(y_train) != len(x_train_wide) or len(y_valid) != len(x_valid_wide):
        raise ValueError(
            f"label/feature mismatch train {len(y_train)}/{len(x_train_wide)} "
            f"valid {len(y_valid)}/{len(x_valid_wide)}"
        )
    n_classes = int(max(int(y_train.max()), int(y_valid.max())) + 1)
    rows: list[dict[str, Any]] = []
    per = (time.perf_counter() - started) / max(len(cfgs), 1)
    for cfg in cfgs:
        cfg = ArmCfg(
            leak=cfg.leak,
            steps=cfg.steps,
            radius=cfg.radius,
            inject_count=cfg.inject_count,
            input_scale=cfg.input_scale,
            pooling=cfg.pooling,
            seed=seed,
        )
        x_train = _slice_pooling(x_train_wide, cfg.pooling)
        x_valid = _slice_pooling(x_valid_wide, cfg.pooling)
        if write_derived and cfg.pooling != "last+mean":
            _write_derived_cache(
                root=root,
                task=task,
                arm=arm,
                cfg=cfg,
                split="train",
                features=x_train,
                tokenizer_fingerprint=fingerprint,
            )
            _write_derived_cache(
                root=root,
                task=task,
                arm=arm,
                cfg=cfg,
                split="valid",
                features=x_valid,
                tokenizer_fingerprint=fingerprint,
            )
        fit_t0 = time.perf_counter()
        head, _info = fit_ridge_classes(
            x_train, y_train, n_classes, x_valid=x_valid, y_valid=y_valid
        )
        valid = metrics(predict_proba(head, x_valid), y_valid)
        rows.append(
            {
                "arm": arm,
                "cfg": cfg.key(),
                "seed": seed,
                "valid": valid,
                "seconds": per + (time.perf_counter() - fit_t0),
                "ridge": head.lam,
                "temperature": head.temperature,
                "pooled_with": "last+mean" if len(cfgs) > 1 else cfg.pooling,
            }
        )
    return rows


def score_point_legacy_single(
    *,
    root: Path,
    task: str,
    arm: str,
    cfg: ArmCfg,
    seed: int,
    train_cap: int,
) -> dict[str, Any]:
    """One pooling only — used when the family has a single unfinished point."""
    return score_pooling_family(
        root=root,
        task=task,
        arm=arm,
        cfgs=[cfg],
        seed=seed,
        train_cap=train_cap,
    )[0]

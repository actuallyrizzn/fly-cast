"""Paths and sidecars for cached float16 features."""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

from flycast.jevlab.arms import ArmCfg

__all__ = [
    "ArmCfg",
    "feature_path",
    "load_sidecar",
    "parse_cfg",
    "save_sidecar",
    "skip_reason",
]

_KEY = re.compile(
    r"^l([^_]+)_s(\d+)_r([^_]+)_i(\d+)_x([^_]+)_p(lastmean|last|mean)_seed(\d+)$"
)
_POOL = {"last": "last", "mean": "mean", "lastmean": "last+mean"}


def parse_cfg(text: str) -> ArmCfg:
    raw = text.strip()
    if raw.startswith("{"):
        data = json.loads(raw)
        return ArmCfg(
            leak=float(data["leak"]),
            steps=int(data["steps"]),
            radius=float(data["radius"]),
            inject_count=int(data["inject_count"]),
            input_scale=float(data["input_scale"]),
            pooling=str(data["pooling"]),
            seed=int(data["seed"]),
        )
    match = _KEY.match(raw)
    if not match:
        raise ValueError(f"cfg is neither json nor a key: {raw}")
    leak, steps, radius, inject, scale, pooling, seed = match.groups()
    return ArmCfg(
        leak=float(leak),
        steps=int(steps),
        radius=float(radius),
        inject_count=int(inject),
        input_scale=float(scale),
        pooling=_POOL[pooling],
        seed=int(seed),
    )


def feature_path(cache: Path, task: str, arm: str, cfg_key: str, split: str) -> Path:
    return cache / task / arm / cfg_key / f"{split}.npy"


def save_sidecar(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_sidecar(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def skip_reason(npy: Path, sidecar: Path, n_rows: int) -> str | None:
    if not npy.exists() or not sidecar.exists():
        return None
    got = load_sidecar(sidecar)
    if int(got.get("n_rows", -1)) != n_rows:
        return None
    return "skip"


def write_memmap(path: Path, rows: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cast = np.ascontiguousarray(rows, dtype=np.float16)
    mapped = np.lib.format.open_memmap(path, mode="w+", dtype=np.float16, shape=cast.shape)
    mapped[:] = cast
    mapped.flush()
    del mapped

"""Pass/fail against tools/jevlab/protocol.json. publishable is computed."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

__all__ = ["ci", "evaluate", "publishable"]

ARMS = ("fly", "scramble", "nofly", "fly_shuffled", "nofly_shuffled", "tfidf")
_METRICS = ("acc", "macro_f1", "brier", "ece")


def ci(values) -> tuple[float, float, float]:
    arr = np.asarray(list(values), dtype=np.float64)
    if arr.size == 0:
        raise ValueError("ci needs at least one value")
    mean = float(arr.mean())
    if arr.size < 2:
        return mean, mean, mean
    sd = float(arr.std(ddof=1))
    half = 1.96 * sd / np.sqrt(arr.size)
    return mean, mean - half, mean + half


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _metric_files(run_dir: Path, arm: str) -> list[Path]:
    folder = run_dir / "metrics"
    found = []
    for path in sorted(folder.glob(f"{arm}_seed*_test.json")):
        if "_test_" in path.name:
            continue
        found.append(path)
    return found


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate(run_dir: str | Path, protocol_path: str | Path) -> dict:
    run_dir = Path(run_dir)
    protocol_path = Path(protocol_path)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if "criteria" not in protocol:
        raise ValueError("protocol has no criteria")
    arms: dict[str, dict] = {}
    seeds: set[int] = set()
    task = ""
    insufficient = False
    series: dict[str, dict[str, list[float]]] = {}
    for arm in ARMS:
        files = _metric_files(run_dir, arm)
        rows = [_load(path) for path in files]
        if not rows:
            raise ValueError(f"no test metrics for {arm}")
        if not task:
            task = str(rows[0].get("task", run_dir.name))
        values = {key: [float(row[key]) for row in rows] for key in _METRICS}
        if len(rows) < 2:
            insufficient = True
        for path in files:
            seed = path.name.split("_seed", 1)[1].split("_", 1)[0]
            seeds.add(int(seed))
        packed = {}
        for key in _METRICS:
            mean, lo, hi = ci(values[key])
            packed[key] = [mean, lo, hi]
        arms[arm] = packed
        series[arm] = values
    fly_mean, fly_lo, _fly_hi = ci(series["fly"]["acc"])
    _scr_mean, _scr_lo, scr_hi = ci(series["scramble"]["acc"])
    nofly_mean = float(np.mean(series["nofly"]["acc"]))
    fly_shuffled = float(np.mean(series["fly_shuffled"]["acc"]))
    nofly_shuffled = float(np.mean(series["nofly_shuffled"]["acc"]))
    c1 = bool(fly_lo > scr_hi)
    c2 = bool(fly_mean >= nofly_mean)
    c3 = bool((fly_mean - fly_shuffled) > (nofly_mean - nofly_shuffled) + 0.01)
    passed = bool(c1 and c2 and c3)
    return {
        "task": task,
        "arms": arms,
        "criteria": {"c1": c1, "c2": c2, "c3": c3},
        "pass": passed,
        "protocol_sha256": _sha256(protocol_path),
        "seeds_found": sorted(seeds),
        "insufficient_seeds": insufficient,
    }


def publishable(results_for_all_tasks: list[dict]) -> bool:
    return any(bool(row.get("pass")) for row in results_for_all_tasks)

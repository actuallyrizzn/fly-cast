"""Smoke run_task builds a full bundle under 90 seconds."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flycast.jevlab.arms import ArmCfg
from flycast.jevlab.data import smoke_root
from tools.jevlab.run_task import main


def _layout(tmp_path: Path) -> Path:
    smoke = smoke_root()
    root = tmp_path / "jevlab"
    data = root / "data" / "sst2"
    data.mkdir(parents=True)
    for name in ("train.tsv", "valid.tsv", "test.tsv"):
        (data / name).symlink_to(smoke / "sst2" / name)
    vectors = root / "vectors"
    vectors.mkdir()
    (vectors / "glove.mini.txt").symlink_to(smoke / "glove.mini.txt")
    (vectors / "MANIFEST.json").write_text(
        json.dumps({"file": "glove.mini.txt"}) + "\n", encoding="utf-8"
    )
    cfg = ArmCfg(0.5, 1, 0.9, 32, 1.0, "last", 0).key()
    grid = root / "grid" / "sst2"
    grid.mkdir(parents=True)
    (grid / "best.json").write_text(
        json.dumps(
            {
                "fly": {"cfg": cfg, "valid_acc": 0.5},
                "scramble": {"cfg": cfg, "valid_acc": 0.5},
                "nofly": {"cfg": cfg},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return root


@pytest.mark.slow
def test_smoke_run_task_bundle(tmp_path: Path) -> None:
    root = _layout(tmp_path)
    out = tmp_path / "run"
    code = main(
        [
            "--task",
            "sst2",
            "--root",
            str(root),
            "--out",
            str(out),
            "--smoke",
            "--seeds",
            "0",
        ]
    )
    assert code == 0
    assert (out / "protocol.json").exists()
    assert (out / "protocol.sha256").exists()
    assert (out / "config.json").exists()
    assert (out / "grid_done").exists()
    assert (out / "score.json").exists()
    assert (out / "latency.json").exists()
    score = json.loads((out / "score.json").read_text(encoding="utf-8"))
    assert "criteria" in score
    assert set(score["criteria"]) == {"c1", "c2", "c3"}
    assert (out / "metrics" / "fly_seed0_test.json").exists()
    assert (out / "metrics" / "tfidf_seed0_test.json").exists()
    assert (out / "proba" / "fly_seed0_test.npy").exists()
    test_metrics = json.loads((out / "metrics" / "fly_seed0_test.json").read_text(encoding="utf-8"))
    assert "top3_acc" in test_metrics
    assert "off_by_one_acc" in test_metrics
    proba = __import__("numpy").load(out / "proba" / "fly_seed0_test.npy")
    assert proba.ndim == 2
    assert proba.shape[0] == test_metrics["n"]

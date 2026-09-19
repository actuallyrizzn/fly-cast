"""Feature cache writes once and skips the second time."""

import json
import sys
from pathlib import Path

from flycast.jevlab.data import smoke_root

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.jevlab.cache_features import main


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
    return root


def test_cache_skips_the_second_run(tmp_path: Path, capsys) -> None:
    root = _layout(tmp_path)
    cfg = json.dumps(
        {
            "leak": 0.5,
            "steps": 1,
            "radius": 0.9,
            "inject_count": 32,
            "input_scale": 1.0,
            "pooling": "last",
            "seed": 0,
        }
    )
    argv = [
        "--task",
        "sst2",
        "--arms",
        "nofly",
        "--cfg",
        cfg,
        "--splits",
        "valid",
        "--root",
        str(root),
    ]
    assert main(argv) == 0
    npy = next((root / "cache").rglob("valid.npy"))
    sidecar = json.loads(npy.with_suffix(".json").read_text(encoding="utf-8"))
    tsv_rows = sum(1 for line in (root / "data" / "sst2" / "valid.tsv").read_text().splitlines() if line) - 1
    assert sidecar["n_rows"] == tsv_rows == 50
    assert sidecar["tokenizer_fingerprint"]
    stamp = npy.stat().st_mtime_ns
    capsys.readouterr()
    assert main(argv) == 0
    out = capsys.readouterr().out
    assert "skip" in out
    assert npy.stat().st_mtime_ns == stamp

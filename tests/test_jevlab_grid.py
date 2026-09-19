"""Grid dry-run writes four lines and resume writes none."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flycast.jevlab.data import smoke_root
from tools.jevlab.grid import main


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


def test_dry_run_then_resume(tmp_path: Path, monkeypatch) -> None:
    root = _layout(tmp_path)
    desk = tmp_path / "desk_status.txt"
    monkeypatch.setenv("JEVLAB_DESK_STATUS", str(desk))
    argv = [
        "--task",
        "sst2",
        "--stage",
        "1",
        "--root",
        str(root),
        "--dry-run",
    ]
    assert main(argv) == 0
    jsonl = root / "grid" / "sst2" / "stage1.jsonl"
    lines = [line for line in jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 4
    assert (root / "grid" / "sst2" / "best.json").exists()
    assert desk.is_file()
    assert "jevlab-grid-sst2" in desk.read_text(encoding="utf-8")
    before = jsonl.read_text(encoding="utf-8")
    assert main(argv + ["--resume"]) == 0
    assert jsonl.read_text(encoding="utf-8") == before


def test_grid_source_only_caches_train_and_valid() -> None:
    text = (ROOT / "src" / "flycast" / "jevlab" / "grid.py").read_text(encoding="utf-8")
    assert '"train,valid"' in text
    assert '"test"' not in text
    assert "'test'" not in text


def test_from_copies_best_json(tmp_path: Path) -> None:
    root = tmp_path / "jevlab"
    src = root / "grid" / "clinc10"
    src.mkdir(parents=True)
    payload = {"fly": {"cfg": "l0.5_s1_r0.9_i32_x1.0_plast_seed0"}, "scramble": {"cfg": "x"}}
    (src / "best.json").write_text(json.dumps(payload) + "\n", encoding="utf-8")
    assert (
        main(
            [
                "--task",
                "clinc150",
                "--from",
                "clinc10",
                "--root",
                str(root),
            ]
        )
        == 0
    )
    dest = root / "grid" / "clinc150" / "best.json"
    got = json.loads(dest.read_text(encoding="utf-8"))
    assert got["fly"] == payload["fly"]
    assert got["_copied_from"] == "clinc10"
    assert main(["--task", "clinc150", "--from", "missing", "--root", str(root)]) == 5

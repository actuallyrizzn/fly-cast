"""Scorer passes a clear win, fails a tie, and refuses a run with no grid."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flycast.jevlab.scorer import evaluate
from tools.jevlab.score_run import main

PROTOCOL = ROOT / "tools" / "jevlab" / "protocol.json"
ARMS = ("fly", "scramble", "nofly", "fly_shuffled", "nofly_shuffled", "tfidf")


def _write(run: Path, acc: dict[str, float]) -> None:
    folder = run / "metrics"
    folder.mkdir(parents=True)
    for arm in ARMS:
        for seed in range(5):
            payload = {
                "task": "sst2",
                "arm": arm,
                "seed": seed,
                "split": "test",
                "acc": acc[arm],
                "macro_f1": acc[arm],
                "brier": 0.2,
                "ece": 0.05,
                "nll": 0.4,
                "n": 20,
            }
            (folder / f"{arm}_seed{seed}_test.json").write_text(json.dumps(payload), encoding="utf-8")
    (run / "grid_done").write_text("ok\n", encoding="utf-8")


def test_clear_win_passes(tmp_path: Path) -> None:
    run = tmp_path / "win"
    _write(
        run,
        {
            "fly": 0.90,
            "scramble": 0.50,
            "nofly": 0.40,
            "fly_shuffled": 0.50,
            "nofly_shuffled": 0.39,
            "tfidf": 0.80,
        },
    )
    got = evaluate(run, PROTOCOL)
    assert got["criteria"] == {"c1": True, "c2": True, "c3": True}
    assert got["pass"] is True


def test_tie_with_scramble_fails(tmp_path: Path) -> None:
    run = tmp_path / "tie"
    _write(
        run,
        {
            "fly": 0.70,
            "scramble": 0.70,
            "nofly": 0.60,
            "fly_shuffled": 0.70,
            "nofly_shuffled": 0.60,
            "tfidf": 0.75,
        },
    )
    got = evaluate(run, PROTOCOL)
    assert got["criteria"]["c1"] is False
    assert got["pass"] is False


def test_missing_grid_done_exits_3(tmp_path: Path) -> None:
    run = tmp_path / "empty"
    (run / "metrics").mkdir(parents=True)
    code = main(["--run-dir", str(run), "--protocol", str(PROTOCOL)])
    assert code == 3

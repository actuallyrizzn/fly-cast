"""journal_refresh keeps hand sections and lists run rows."""

from __future__ import annotations

import json
from pathlib import Path

from tools.jevlab.journal_refresh import HAND_END, HAND_START, render


def _fake_run(root: Path, name: str, task: str, passed: bool) -> None:
    run = root / name
    run.mkdir(parents=True)
    (run / "score.json").write_text(
        json.dumps(
            {
                "task": task,
                "pass": passed,
                "criteria": {"c1": passed, "c2": True, "c3": True},
                "arms": {
                    "fly": {"acc": [0.7, 0.6, 0.8], "brier": 0.2, "ece": 0.05},
                    "scramble": {"acc": [0.5, 0.4, 0.6], "brier": 0.3, "ece": 0.1},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run / "state.json").write_text(
        json.dumps({"task": task, "glass": True, "pass": passed}) + "\n",
        encoding="utf-8",
    )
    frames = run / "frames"
    frames.mkdir()
    (frames / "index.tsv").write_text(
        "filename\ttag\tiso\tphase\na.png\tscoring\t2026-01-01T00:00:00Z\tdone\n",
        encoding="utf-8",
    )


def test_journal_lists_both_runs_and_keeps_hand(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    _fake_run(runs, "sst2-aaa", "sst2", False)
    _fake_run(runs, "clinc10-bbb", "clinc10", True)
    # slice metrics on sst2 run
    metrics = runs / "sst2-aaa" / "metrics"
    metrics.mkdir(parents=True, exist_ok=True)
    (metrics / "fly_seed0_test.json").write_text(
        json.dumps({"acc": 0.7, "top3_acc": 0.9, "off_by_one_acc": 1.0, "split": "test"}) + "\n",
        encoding="utf-8",
    )
    (metrics / "fly_shuffled_seed0_test.json").write_text(
        json.dumps({"acc": 0.55, "split": "test"}) + "\n",
        encoding="utf-8",
    )
    (metrics / "nofly_seed0_test.json").write_text(
        json.dumps({"acc": 0.65, "split": "test"}) + "\n",
        encoding="utf-8",
    )
    (metrics / "nofly_shuffled_seed0_test.json").write_text(
        json.dumps({"acc": 0.60, "split": "test"}) + "\n",
        encoding="utf-8",
    )
    (metrics / "fly_seed0_test_negation.json").write_text(
        json.dumps(
            {
                "acc": 0.66,
                "top3_acc": 0.88,
                "off_by_one_acc": 1.0,
                "split": "test_negation",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    hand = f"{HAND_START}\n## Reading the results\n\nkeep me\n{HAND_END}"
    first = render(runs, existing=None)
    assert "sst2-aaa" in first
    assert "clinc10-bbb" in first
    assert "publishable = true" in first.lower() or "publishable = true" in first
    assert "test_negation" in first
    assert "Shuffle drop" in first
    assert "top3_acc" in first
    # inject custom hand into "existing"
    existing = first.split(HAND_START)[0] + hand
    second = render(runs, existing=existing)
    assert "keep me" in second
    assert HAND_START in second and HAND_END in second

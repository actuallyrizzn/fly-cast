"""SST-2 helpers: stratified draw and manifest checks. No network."""

from pathlib import Path

import numpy as np
import pytest

from flycast.jevlab.data import (
    load_split,
    sha256_file,
    stratified_indices,
    verify_manifest,
    write_manifest,
    write_tsv,
)


def test_stratified_indices_keeps_balance() -> None:
    labels = [0] * 70 + [1] * 30
    idx = stratified_indices(labels, 10, 7)
    assert len(idx) == 10
    assert len(set(int(i) for i in idx)) == 10
    drawn = [labels[int(i)] for i in idx]
    assert drawn.count(0) == 7
    assert drawn.count(1) == 3
    again = stratified_indices(labels, 10, 7)
    assert np.array_equal(idx, again)


def test_verify_manifest_rejects_a_changed_file(tmp_path: Path) -> None:
    task = tmp_path / "toy"
    rows = [(f"r{i}", f"word {i}", i % 2) for i in range(20)]
    write_tsv(task / "train.tsv", rows)
    write_manifest(
        task,
        {
            "task": "toy",
            "files": [
                {
                    "name": "train.tsv",
                    "sha256": sha256_file(task / "train.tsv"),
                    "rows": 20,
                }
            ],
        },
    )
    assert len(load_split("toy", "train", root=tmp_path)) == 20
    verify_manifest("toy", root=tmp_path)
    (task / "train.tsv").write_text("id\ttext\tlabel\nhacked\tno\t0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="sha256"):
        verify_manifest("toy", root=tmp_path)


def test_confusable_needs_two_shared_tokens_and_a_different_label() -> None:
    from flycast.jevlab.data import confusable_mask

    train_texts = ["set alarm now", "bake a cake"]
    train_labels = [0, 1]
    test_texts = ["set alarm please", "bake cake tonight"]
    test_labels = [1, 1]
    assert confusable_mask(train_texts, train_labels, test_texts, test_labels) == [True, False]

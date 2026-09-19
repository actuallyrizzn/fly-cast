"""Heads separate two blobs, and the metric keys match a hand-built case."""

import numpy as np
import pytest

from flycast.jevlab.readout import (
    fit_logistic,
    fit_ridge_classes,
    fit_temperature,
    metrics,
    predict_proba,
)


def _split(x, y, n_valid=100):
    return x[n_valid:], y[n_valid:], x[:n_valid], y[:n_valid]


def test_ridge_and_logistic_separate_two_blobs() -> None:
    rng = np.random.default_rng(0)
    x = np.vstack(
        [
            rng.normal(-2.0, 0.4, size=(200, 20)),
            rng.normal(2.0, 0.4, size=(200, 20)),
        ]
    ).astype(np.float32)
    y = np.array([0] * 200 + [1] * 200)
    order = rng.permutation(len(y))
    x, y = x[order], y[order]
    x_train, y_train, x_valid, y_valid = _split(x, y)
    ridge, _info = fit_ridge_classes(x_train, y_train, 2, x_valid=x_valid, y_valid=y_valid)
    assert metrics(predict_proba(ridge, x_valid), y_valid)["acc"] > 0.95
    pytest.importorskip("sklearn")
    logistic = fit_logistic(x_train, y_train, x_valid=x_valid, y_valid=y_valid)
    assert metrics(predict_proba(logistic, x_valid), y_valid)["acc"] > 0.95


def test_temperature_on_true_logits_stays_near_one() -> None:
    rng = np.random.default_rng(1)
    logits = rng.normal(size=(4000, 2))
    logits -= logits.max(axis=1, keepdims=True)
    ex = np.exp(logits)
    proba = ex / ex.sum(axis=1, keepdims=True)
    y = np.array([rng.choice(2, p=row) for row in proba])
    temp = fit_temperature(logits, y, (0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4))
    assert abs(temp - 1.0) <= 0.5


def test_metrics_on_four_rows() -> None:
    proba = np.array(
        [[1.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.5, 0.5]],
        dtype=np.float64,
    )
    got = metrics(proba, np.array([0, 0, 1, 1]))
    assert got["acc"] == 0.75
    assert got["brier"] == pytest.approx(0.125)
    assert got["confusion"] == [[2, 0], [1, 1]]
    assert got["n"] == 4
    assert got["top3_acc"] == 1.0  # binary: top-2 covers all
    assert got["off_by_one_acc"] == 1.0


def test_top3_and_off_by_one() -> None:
    from flycast.jevlab.readout import off_by_one_acc, top_k_acc

    # Three-class: true labels in ranks 1, 2, 3 of the softmax rows.
    proba = np.array(
        [
            [0.6, 0.3, 0.1],  # pred 0, true 0 → top1
            [0.1, 0.6, 0.3],  # pred 1, true 2 → top2
            [0.5, 0.4, 0.1],  # pred 0, true 2 → not in top2 of {0,1}
            [0.2, 0.3, 0.5],  # pred 2, true 0 → off-by-two
        ],
        dtype=np.float64,
    )
    y = np.array([0, 2, 2, 0])
    assert top_k_acc(proba, y, k=1) == 0.25
    assert top_k_acc(proba, y, k=2) == 0.5
    assert top_k_acc(proba, y, k=3) == 1.0
    # |pred-y|: 0,1,2,2 → off-by-one hits first two only
    assert off_by_one_acc(proba, y) == 0.5


def test_ridge_recovers_a_three_class_line() -> None:
    rng = np.random.default_rng(2)
    weight = rng.normal(size=(5, 3))
    x = rng.normal(size=(400, 5)).astype(np.float32)
    y = (x @ weight).argmax(axis=1)
    x_train, y_train, x_valid, y_valid = _split(x, y, n_valid=80)
    head, _info = fit_ridge_classes(
        x_train, y_train, 3, x_valid=x_valid, y_valid=y_valid, chunk=50
    )
    assert metrics(predict_proba(head, x_valid), y_valid)["acc"] > 0.9

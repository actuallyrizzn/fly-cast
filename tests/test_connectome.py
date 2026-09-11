"""Connectome load + scramble + spectral radius."""

from __future__ import annotations

import numpy as np

from flycast.connectome import load_connectome, scramble, spectral_radius


def test_load_larva_counts():
    conn = load_connectome()
    assert conn.size == 2956
    # Dense matrix collapses parallel edges; nonzero count is the unique (pre, post) pairs.
    assert conn.edge_count >= 110_000
    assert len(conn.neurons_of_type("sensory")) > 100


def test_scramble_preserves_weight_mass():
    conn = load_connectome()
    s = scramble(conn.weights, seed=1)
    assert s.shape == conn.weights.shape
    assert np.isclose(s.sum(), conn.weights.sum())
    # layout changed
    assert not np.array_equal(s, conn.weights)


def test_spectral_radius_positive():
    conn = load_connectome()
    r = spectral_radius(conn.weights, iterations=20, seed=0)
    assert r > 0

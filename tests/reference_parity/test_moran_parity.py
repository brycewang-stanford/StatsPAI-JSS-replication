"""Analytical parity: sp.moran (Moran's I) null expectation + permutation p-value.

Moran's I under spatial randomness has known expectation -1/(n-1) and a
conditional-permutation null distribution. Analytical evidence tier
(known-truth on a non-spatial random sample; no cross-package target).
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp


@pytest.fixture(scope="module")
def fitted():
    rng = np.random.default_rng(0)
    n = 200
    y = rng.standard_normal(n)
    coords = np.column_stack([rng.uniform(0, 1, n), rng.uniform(0, 1, n)])
    W = sp.knn_weights(coords, k=4)
    return sp.moran(y, W, permutations=199, seed=0), n


def test_null_expectation_close_to_minus_one_over_n_minus_one(fitted):
    r, n = fitted
    assert float(r.expectation) == pytest.approx(-1.0 / (n - 1), abs=1e-12)


def test_independent_data_pvalue_non_significant(fitted):
    """Under H0 (spatial randomness) a clean random sample should not reject."""
    r, _ = fitted
    assert float(r.p_sim) > 0.05


def test_known_attrs_present(fitted):
    r, _ = fitted
    assert isinstance(float(r.I), float)
    assert isinstance(float(r.p_norm), float)
    assert isinstance(float(r.variance), float)
    assert float(r.variance) > 0


def test_morans_I_reproduces_under_seeded_permutation(fitted):
    r1, _ = fitted
    _, n = fitted
    rng = np.random.default_rng(0)
    y = rng.standard_normal(n)
    coords = np.column_stack([rng.uniform(0, 1, n), rng.uniform(0, 1, n)])
    W = sp.knn_weights(coords, k=4)
    r2 = sp.moran(y, W, permutations=199, seed=0)
    assert float(r1.I) == float(r2.I)

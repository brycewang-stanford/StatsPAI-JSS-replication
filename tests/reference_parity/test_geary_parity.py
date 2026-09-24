"""Analytical parity: sp.geary (Geary's C) null expectation.

Geary's C under spatial randomness has known expectation 1.0; the
conditional-permutation null distribution is the appropriate reference.
Analytical evidence tier.
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
    return sp.geary(y, W, permutations=199, seed=0)


def test_geary_null_expectation_is_one(fitted):
    assert float(fitted.expectation) == 1.0


def test_geary_independent_pvalue_non_significant(fitted):
    assert float(fitted.p_sim) > 0.05


def test_geary_C_near_one_for_independent_data(fitted):
    # C = 1 + (sum_{i!=j} w_ij) / (2 W) * ...; for independent normals, C
    # is close to 1 by construction.
    assert 0.5 < float(fitted.C) < 1.5

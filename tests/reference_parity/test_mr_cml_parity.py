"""Frozen-formula parity: sp.mr_cml constrained-maximum-likelihood MR.

Xue, Shen & Pan 2021 (MR-cML-BIC): profile-likelihood MR with BIC-selected
sparsity K, where K is the number of pleiotropic SNPs. Under a constant
effect the optimal K is 0 (no pleiotropy) and the recovered estimate is
near the planted beta. Analytical evidence tier (known-truth recovery).
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp

BETA = 0.4


def test_mr_cml_recovers_constant_effect_with_pleiotropic_screening():
    rng = np.random.default_rng(0)
    K = 50
    bx = rng.uniform(0.1, 0.5, K)
    sx = np.full(K, 0.02)
    sy = np.full(K, 0.02)
    by = BETA * bx + rng.normal(0, sy)
    r = sp.mr_cml(bx, by, se_exposure=sx, se_outcome=sy)
    # BIC selects K; under no true pleiotropy K should be small.
    assert int(r.K_selected) <= 2
    assert float(r.estimate) == pytest.approx(BETA, abs=0.1)


def test_mr_cml_recovers_across_seeds():
    for seed in range(4):
        rng = np.random.default_rng(seed)
        K = 50
        bx = rng.uniform(0.1, 0.5, K)
        sx = np.full(K, 0.02)
        sy = np.full(K, 0.02)
        by = BETA * bx + rng.normal(0, sy)
        r = sp.mr_cml(bx, by, se_exposure=sx, se_outcome=sy)
        assert float(r.estimate) == pytest.approx(BETA, abs=0.15)

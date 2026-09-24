"""Analytical parity: sp.continuous_iv_late quantile-bin Wald recovery.

With a continuous instrument and monotone selection D = 1{Z > U}
(U ~ Uniform, independent of Z), every instrument shift moves only compliers,
so the quantile-bin Wald estimator identifies the constant treatment effect
beta. Single-draw estimates are noisy (few bins), so we assert the across-seed
mean recovers beta — an unbiasedness check on a known DGP. Analytical evidence
tier (no cross-package reference).
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp

BETA = 1.5


def _estimate(seed, n=8000):
    rng = np.random.default_rng(seed)
    Z = rng.uniform(0, 1, n)
    U = rng.uniform(0, 1, n)
    D = (Z > U).astype(int)
    Y = BETA * D + rng.normal(0, 1, n)
    df = pd.DataFrame({"y": Y, "d": D, "z": Z})
    return sp.continuous_iv_late(
        df, y="y", treat="d", instrument="z", n_boot=20, seed=seed
    )


def test_mean_estimate_recovers_beta_across_seeds():
    ests = [float(_estimate(seed).estimate) for seed in range(6)]
    assert np.all(np.isfinite(ests))
    assert float(np.mean(ests)) == pytest.approx(BETA, abs=0.1)


def test_result_structure_sane():
    r = _estimate(0)
    assert float(r.se) > 0 and np.isfinite(float(r.se))
    assert 0.0 < float(r.complier_share) <= 1.0
    lo, hi = float(r.ci[0]), float(r.ci[1])
    assert lo < float(r.estimate) < hi

"""Analytical parity: sp.ivqreg endogeneity-robust quantile recovery.

Chernozhukov & Hansen IV quantile regression. On a location-shift DGP with a
strong instrument and an endogenous regressor,

    D = 0.8 Z + 0.7 u + e_D,   Y = beta * D + 0.9 u + e_Y,

the common shock u biases naive OLS/QR upward by cov(D, 0.9u)/var(D) ~ 0.46,
while the structural quantile effect equals the constant beta = 1.0 at every
quantile. ivqreg recovers beta across quantiles and strips the endogeneity
bias. Analytical evidence tier (known-truth recovery on a deterministic DGP;
no cross-package reference).
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp

BETA = 1.0
TAUS = [0.25, 0.5, 0.75]


@pytest.fixture(scope="module")
def fitted():
    rng = np.random.default_rng(0)
    n = 3000
    Z = rng.normal(0, 1, n)
    u = rng.normal(0, 1, n)
    D = 0.8 * Z + 0.7 * u + rng.normal(0, 0.5, n)
    Y = BETA * D + 0.9 * u + rng.normal(0, 0.5, n)
    df = pd.DataFrame({"y": Y, "d": D, "z": Z})
    # multi-tau call returns the per-quantile coefficient DataFrame
    res = sp.ivqreg(df, y="y", endog="d", instruments="z", tau=TAUS)
    return df, res


def test_recovers_constant_effect_at_all_quantiles(fitted):
    _, r = fitted
    coefs = np.asarray(r["d_coef"], dtype=float)
    assert coefs.shape == (len(TAUS),)
    assert np.all(np.isfinite(coefs))
    assert np.max(np.abs(coefs - BETA)) < 0.12


def test_strips_endogeneity_bias(fitted):
    df, r = fitted
    ivq_median = float(np.asarray(r.loc[r["tau"] == 0.5, "d_coef"], dtype=float)[0])
    d = df["d"].to_numpy()
    y = df["y"].to_numpy()
    naive = float(np.cov(y, d, bias=True)[0, 1] / np.var(d))
    # Naive is biased up by ~0.46; ivqreg sits at the truth.
    assert naive > BETA + 0.3
    assert abs(ivq_median - BETA) < abs(naive - BETA)

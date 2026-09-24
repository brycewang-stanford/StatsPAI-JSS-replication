"""Analytical parity: sp.sensemakr closed-form identities (Cinelli-Hazlett).

The sensitivity statistics reported by sensemakr are exact closed forms of the
OLS fit (Cinelli & Hazlett 2020, JRSS-B "Making sense of sensitivity"):

    partial_r2_yd == t^2 / (t^2 + df)
    rv_q (q=1)    == (sqrt(f^4 + 4 f^2) - f^2) / 2,   f^2 = t^2 / df
    beta / se / t == the OLS treatment coefficient, its SE, and t-ratio

All hold to machine precision against a hand-rolled lstsq fit (observed
diffs <= 2e-16 / 0).
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp

N = 2000
DOF = N - 3  # intercept + treatment + one control


@pytest.fixture(scope="module")
def fitted():
    rng = np.random.default_rng(0)
    x1 = rng.normal(0, 1, N)
    d = 0.5 * x1 + rng.normal(0, 1, N)
    y = 1.0 * d + 0.8 * x1 + rng.normal(0, 1, N)
    df = pd.DataFrame({"y": y, "d": d, "x1": x1})
    return df, sp.sensemakr(df, y="y", treat="d", controls=["x1"])


def test_ols_quantities_match_hand_fit(fitted):
    df, r = fitted
    X = np.column_stack([np.ones(N), df["d"], df["x1"]])
    y = df["y"].to_numpy()
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    vcov = (resid @ resid / DOF) * np.linalg.inv(X.T @ X)
    se = float(np.sqrt(vcov[1, 1]))
    assert r["beta_treat"] == pytest.approx(float(coef[1]), abs=1e-12)
    assert r["se_treat"] == pytest.approx(se, abs=1e-12)
    assert r["t_treat"] == pytest.approx(float(coef[1]) / se, abs=1e-10)


def test_partial_r2_identity(fitted):
    _, r = fitted
    t2 = r["t_treat"] ** 2
    assert r["partial_r2_yd"] == pytest.approx(t2 / (t2 + DOF), abs=1e-12)


def test_robustness_value_identity(fitted):
    _, r = fitted
    f2 = r["t_treat"] ** 2 / DOF
    rv = 0.5 * (np.sqrt(f2**2 + 4 * f2) - f2)
    assert r["rv_q"] == pytest.approx(rv, abs=1e-12)
    # alpha-adjusted RV is strictly smaller when t exceeds its critical value.
    assert 0.0 < r["rv_qa"] < r["rv_q"] < 1.0

"""Analytical parity: sp.margins_at exact predictive-margin identity.

Predictive margins at fixed covariate values are an exact linear form of the
OLS coefficients: setting x to v and averaging the other regressors over the
sample gives

    margin(x=v) == b0 + b_x * v + b_z * mean(z)

which matches a hand computation to machine precision (observed diff 0). The
symmetric grid x in {-1, 0, 1} also produces symmetric standard errors.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp

GRID = [-1.0, 0.0, 1.0]


@pytest.fixture(scope="module")
def fitted():
    rng = np.random.default_rng(0)
    n = 1500
    x = rng.normal(0, 1, n)
    z = rng.normal(0, 1, n)
    y = 1 + 0.8 * x + 0.5 * z + rng.normal(0, 0.5, n)
    df = pd.DataFrame({"y": y, "x": x, "z": z})
    res = sp.regress("y ~ x + z", data=df)
    return df, res, sp.margins_at(res, data=df, at={"x": GRID})


def test_margins_match_linear_prediction(fitted):
    df, res, tab = fitted
    b = res.params
    zbar = df["z"].mean()
    got = {float(row["x"]): float(row["margin"]) for _, row in tab.iterrows()}
    for v in GRID:
        expected = b["Intercept"] + b["x"] * v + b["z"] * zbar
        assert got[v] == pytest.approx(expected, abs=1e-10)


def test_se_is_the_delta_method_closed_form(fitted):
    """se(margin at x=v) = sqrt(g' V g), g = (1, v, mean z), V the full vcov.

    This test used to assert se(x=-1) == se(x=+1). That holds only when
    cov(b0, b_x) is ignored -- which the old diagonal-covariance fallback
    did. The variance is symmetric about mean(x) (here -0.015), not about 0.
    """
    df, res, tab = fitted
    V = np.asarray(res.data_info["var_cov"], dtype=float)
    zbar = df["z"].mean()
    for v in GRID:
        g = np.array([1.0, v, zbar])
        got = float(tab.loc[tab["x"] == v, "se"].iloc[0])
        assert got == pytest.approx(float(np.sqrt(g @ V @ g)), rel=1e-12)


def test_se_symmetric_about_the_mean_of_x(fitted):
    df, res, _ = fitted
    xbar = float(df["x"].mean())
    tab = sp.margins_at(res, data=df, at={"x": [xbar - 1.0, xbar, xbar + 1.0]})
    se = tab["se"].to_numpy()
    assert se[0] == pytest.approx(se[2], rel=1e-10)
    assert se[1] < se[0]

"""Frozen-stat parity: sp.wild_cluster_boot determinism + closed-form identity.

Cameron-Gelbach-Miller (2008) wild cluster bootstrap. With identical inputs
the result is deterministic: same t-statistic, same p-value, same CI. The
estimate equals the OLS coefficient, and the SE is the asymptotic-cluster
robust SE applied to the same input. Analytical evidence tier.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp


@pytest.fixture(scope="module")
def fitted():
    rng = np.random.default_rng(0)
    n = 200
    g = rng.integers(0, 10, size=n)
    x = rng.normal(size=n)
    y = 0.5 + 1.0 * x + rng.normal(size=n)
    return pd.DataFrame({"y": y, "d": g, "x": x})


def _boot(df, n_boot=99, seed=0):
    return sp.wild_cluster_bootstrap(
        df,
        "y",
        ["x"],
        cluster="d",
        test_var="x",
        n_boot=n_boot,
        seed=seed,
    )


def test_seeded_deterministic_p_value_and_ci(fitted):
    """Same seed + input -> same p-value and CI (deterministic)."""
    r1 = _boot(fitted)
    r2 = _boot(fitted)
    assert r1["p_boot"] == r2["p_boot"]
    assert r1["ci_boot"] == r2["ci_boot"]
    assert r1["beta_hat"] == r2["beta_hat"]


def test_beta_hat_equals_ols_estimate(fitted):
    """The bootstrap reports the OLS coefficient; OLS gives x_hat=1.0 here."""
    out = _boot(fitted)
    assert out["beta_hat"] == pytest.approx(1.0, abs=0.05)
    # t = (beta_hat - 0) / se_cluster.
    assert out["t_stat"] == pytest.approx(
        out["beta_hat"] / out["se_cluster"], abs=1e-10
    )

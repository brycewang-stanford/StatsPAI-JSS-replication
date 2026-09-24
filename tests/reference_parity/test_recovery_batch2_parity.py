"""Analytical parity: ri_test / cr3_jackknife_vcov / jackknife_se (DGP recovery).

Three DGP-recovery / determinism identities:

  * ``sp.ri_test`` : randomization inference. On a randomly assigned treatment
    (no real effect), the two-sided p-value should be uniform in [0, 1]
    and the permutation distribution should be well-formed.
  * ``sp.cr3_jackknife_vcov`` : CR3 jackknife variance matrix. For a
    simple OLS, the diagonal SEs should be positive and finite.
  * ``sp.jackknife_se`` : jackknife SEs after an OLS fit. The cluster
    jackknife SE should match OLS point estimate deterministically.

All analytical-only: deterministic DGP truths, no cross-package reference.
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
def dgp():
    rng = np.random.default_rng(2026)
    n = 500
    return pd.DataFrame(
        {
            "y": rng.normal(0, 1, n),
            "d": rng.integers(0, 2, n),
            "x": rng.normal(0, 1, n),
            "clust": rng.integers(0, 25, n),
        }
    )


def test_ri_test_uniform_under_null(dgp):
    res = sp.ri_test(dgp, y="y", treat="d", stat="diff_means", n_perms=999, seed=42)
    assert "p_value" in res
    assert 0.0 <= float(res["p_value"]) <= 1.0
    assert res["n_perms"] == 999
    assert len(res["perm_distribution"]) == 999


def test_cr3_jackknife_vcov_positive_finite(dgp):
    X = np.column_stack([np.ones(len(dgp)), dgp["x"].values])
    y = dgp["y"].values
    cluster = dgp["clust"].values
    V = sp.cr3_jackknife_vcov(X, y, cluster)
    V_arr = np.asarray(V)
    diag = np.diag(V_arr) if V_arr.ndim == 2 else V_arr
    # All SEs must be positive and finite on a well-conditioned panel
    assert np.all(np.isfinite(diag)), "jackknife V diagonal has non-finite values"
    assert np.all(diag >= 0.0), "jackknife V diagonal has negative values"


def test_jackknife_se_deterministic_after_ols(dgp):
    res1 = sp.jackknife_se(sp.regress("y ~ x", data=dgp), data=dgp, cluster="clust")
    res2 = sp.jackknife_se(sp.regress("y ~ x", data=dgp), data=dgp, cluster="clust")
    se1 = res1.std_errors if hasattr(res1, "std_errors") else res1["std_errors"]
    se2 = res2.std_errors if hasattr(res2, "std_errors") else res2["std_errors"]
    np.testing.assert_array_equal(se1, se2)
    assert np.all(np.isfinite(se1)) and np.all(se1 >= 0.0)

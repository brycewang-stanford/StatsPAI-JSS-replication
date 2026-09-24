"""Reference parity: ``sp.truncreg`` covariance options vs Stata 18 ``truncreg``.

Track A module 62 pins ``truncreg``'s default (observed-information)
estimates against R and Stata.  ``robust=`` and ``cluster=`` are a separate
promise: they were accepted and silently ignored before 1.29, and nothing
pinned them afterwards.  This fixture freezes the *full* covariance matrix
that Stata reports under ``vce(oim)``, ``vce(robust)`` and
``vce(cluster cl)`` on module 62's data (read as double,
``cl = mod(_n - 1, 50)``), so a wrong sandwich or a missing finite-sample
factor cannot pass unnoticed.

StatsPAI parameterizes the scale as ``ln_sigma`` and Stata as ``sigma``, so
the comparison delta-maps our covariance with ``J = diag(1, 1, 1, sigma)``,
which is exact for a sandwich at the optimum.

Tolerances.  Coefficients and standard errors use ``rtol = 2e-6``: Stata's
``ml`` stops at its own convergence criterion, which leaves a coefficient
gap of about 8e-8 and standard-error gaps of about 5e-7 here.  Off-diagonal
covariances are compared in correlation units --- ``|V - V_stata| /
sqrt(V_ii V_jj)``, which does not blow up where a covariance is near zero
--- with ``atol = 5e-6`` against an observed worst case of 9.3e-7.  A wrong
finite-sample factor would show up far outside both budgets: ``n / (n - 1)``
is 1e-3 on this sample and ``G / (G - 1)`` is 2e-2.

Regenerate with ``_fixtures/_generate_truncreg_vce_Stata.do`` (Stata 18,
built-in ``truncreg``; no external packages).
"""

from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd
import pytest

import statspai as sp

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_TXT = pathlib.Path(__file__).parent / "_fixtures" / "truncreg_vce_Stata.txt"
_CSV = _ROOT / "r_parity" / "data" / "62_truncreg.csv"

pytestmark = pytest.mark.skipif(
    not (_TXT.exists() and _CSV.exists()),
    reason="truncreg Stata vce fixture is not materialized",
)

RTOL = 2e-6
ATOL_CORR = 5e-6
# Stata's coefficient order; StatsPAI reports ln_sigma where Stata reports sigma.
ORDER = ["x1", "x2", "_cons", "ln_sigma"]


def _stata() -> dict:
    values: dict = {}
    for line in _TXT.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("*"):
            continue
        tag, value = line.split()
        values.setdefault(tag, []).append(float(value))
    return values


@pytest.fixture(scope="module")
def data() -> pd.DataFrame:
    df = pd.read_csv(_CSV)
    df["cl"] = np.arange(len(df)) % 50
    return df


@pytest.mark.parametrize(
    "tag,kwargs,label",
    [
        ("V0", {}, "nonrobust"),
        ("Vr", {"robust": "robust"}, "robust"),
        ("Vc", {"cluster": "cl"}, "cluster"),
    ],
)
def test_truncreg_covariance_matches_stata(data, tag, kwargs, label):
    ref = _stata()
    res = sp.truncreg(data=data, y="y", x=["x1", "x2"], ll=0.0, **kwargs)
    assert res.model_info["robust"] == label
    if label == "cluster":
        assert res.model_info["cluster"] == "cl"

    sigma = float(res.model_info["sigma"])
    order = [list(res.params.index).index(name) for name in ORDER]
    jacobian = np.diag([1.0, 1.0, 1.0, sigma])  # d sigma / d ln_sigma
    cov = np.asarray(res.data_info["var_cov"], dtype=float)[np.ix_(order, order)]
    cov = jacobian @ cov @ jacobian

    estimate = np.array([res.params[n] for n in ORDER[:3]] + [sigma])
    se = np.array(
        [res.std_errors[n] for n in ORDER[:3]] + [sigma * res.std_errors["ln_sigma"]]
    )
    stata_cov = np.array(ref[tag]).reshape(4, 4)
    stata_se = np.sqrt(np.diag(stata_cov))

    np.testing.assert_allclose(estimate, ref["b"], rtol=RTOL)
    np.testing.assert_allclose(se, stata_se, rtol=RTOL)
    # Whole matrix, in correlation units.
    scale = np.outer(stata_se, stata_se)
    np.testing.assert_allclose(cov / scale, stata_cov / scale, atol=ATOL_CORR)


def test_unsupported_vce_fails_loudly(data):
    with pytest.raises(Exception) as excinfo:
        sp.truncreg(data=data, y="y", x=["x1", "x2"], ll=0.0, robust="hc42")
    assert "hc42" in str(excinfo.value)

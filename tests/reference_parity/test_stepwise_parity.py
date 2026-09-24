"""Analytical parity: sp.stepwise known-truth support recovery.

Stepwise selection (forward + backward) with BIC / AIC / pvalue criteria
recovers the planted support on a sparse linear DGP. Analytical evidence
tier (known-truth recovery on a deterministic DGP).
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp

TRUE_SUPPORT = [0, 3, 15]


def _dgp(seed, n=300, p=20):
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((n, p))
    true_b = np.zeros(p)
    for i, v in zip(TRUE_SUPPORT, (1.0, -0.8, 0.5)):
        true_b[i] = v
    y = X @ true_b + rng.standard_normal(n) * 0.5
    return pd.DataFrame({"y": y, **{f"x{i}": X[:, i] for i in range(p)}})


def test_bic_recovers_true_support():
    df = _dgp(0)
    r = sp.stepwise(
        df,
        "y",
        [f"x{i}" for i in range(20)],
        method="both",
        criterion="bic",
    )
    assert set(r.selected) == {f"x{i}" for i in TRUE_SUPPORT}


def test_aic_contains_true_support():
    df = _dgp(1)
    r = sp.stepwise(
        df,
        "y",
        [f"x{i}" for i in range(20)],
        method="both",
        criterion="aic",
    )
    # AIC is less parsimonious than BIC and may admit noise variables;
    # only assert that the planted predictors are all retained.
    for i in TRUE_SUPPORT:
        assert f"x{i}" in r.selected


def test_recovers_across_seeds():
    for seed in range(4):
        df = _dgp(seed)
        r = sp.stepwise(
            df,
            "y",
            [f"x{i}" for i in range(20)],
            method="both",
            criterion="bic",
        )
        assert set(r.selected) == {f"x{i}" for i in TRUE_SUPPORT}


def test_final_model_coefficients_close_to_truth():
    df = _dgp(0)
    r = sp.stepwise(
        df,
        "y",
        [f"x{i}" for i in range(20)],
        method="both",
        criterion="bic",
    )
    coef = dict(r.coefficients)  # noqa: E501
    for var, true_val in zip(["x0", "x3", "x15"], (1.0, -0.8, 0.5)):
        assert float(coef[var]) == pytest.approx(true_val, abs=0.1)

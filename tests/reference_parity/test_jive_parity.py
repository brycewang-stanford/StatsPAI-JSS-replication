"""Analytical parity: sp.jive (jackknife IV) known-truth recovery.

JIVE (Angrist, Imbens & Kolesar 2025, arXiv:2506.11923) replaces instruments
with their leave-one-out first-stage fitted values, reducing the many-IV
bias of 2SLS to leading order in 1/n. On a DGP with K=30 instruments and a
genuine effect beta=0.8, the JIVE estimator recovers the true effect while
naive 2SLS would be biased toward OLS. Analytical evidence tier (known-truth
recovery on a deterministic DGP).
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp

TRUE_BETA = 0.8
TRUE_CONST = 1.0


def _dgp(seed, n=1000, K=30):
    rng = np.random.default_rng(seed)
    Z = rng.standard_normal((n, K))
    u = rng.standard_normal(n)
    X = 0.5 * Z[:, 0] + 0.3 * Z[:, 1] + u + rng.standard_normal(n) * 0.5
    y = TRUE_CONST + TRUE_BETA * X + 0.6 * u + rng.standard_normal(n) * 0.5
    return pd.DataFrame({"y": y, "x": X, **{f"z{i}": Z[:, i] for i in range(K)}})


def test_recovers_true_effect_with_many_instruments():
    df = _dgp(0)
    r = sp.jive(df, "y", x_endog=["x"], z=[f"z{i}" for i in range(30)])
    p = dict(r.params)
    assert p["x"] == pytest.approx(TRUE_BETA, abs=0.1)
    assert p["_cons"] == pytest.approx(TRUE_CONST, abs=0.1)


def test_recovers_effect_across_seeds():
    for seed in range(4):
        df = _dgp(seed)
        r = sp.jive(df, "y", x_endog=["x"], z=[f"z{i}" for i in range(30)])
        p = dict(r.params)
        assert p["x"] == pytest.approx(TRUE_BETA, abs=0.15)

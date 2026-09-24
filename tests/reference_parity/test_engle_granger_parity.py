"""Analytical parity: sp.engle_granger cointegration recovery.

Two-step Engle-Granger residual-based cointegration test. On a pair
constructed as y = 2 x + stationary noise with x a random walk, the test finds
rank 1 with the ADF statistic far below the 1% critical value and recovers the
cointegrating coefficient ~2. On two independent random walks it finds rank 0.
Analytical evidence tier (known-truth recovery on deterministic DGPs).
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp

N = 400
COINT_COEF = 2.0


def _pair(cointegrated):
    rng = np.random.default_rng(0)
    x = np.cumsum(rng.normal(0, 1, N))
    if cointegrated:
        y = COINT_COEF * x + rng.normal(0, 1, N)
    else:
        y = np.cumsum(rng.normal(0, 1, N))
    return pd.DataFrame({"y": y, "x": x})


def test_detects_cointegration_and_recovers_coefficient():
    r = sp.engle_granger(_pair(True))
    assert int(r.rank) == 1
    assert float(r.test_stats) < float(r.critical_values[0])  # beyond 1% CV
    coef = float(np.asarray(r.eigenvectors, dtype=float)[1])
    assert coef == pytest.approx(COINT_COEF, abs=0.05)


def test_independent_walks_not_cointegrated():
    r = sp.engle_granger(_pair(False))
    assert int(r.rank) == 0
    assert float(r.test_stats) > float(r.critical_values[2])  # inside 10% CV

"""Frozen-formula parity: sp.local_projections impulse response recovery.

Local projections (Jordà 2005): at each horizon h, the coefficient beta_h on
the contemporaneous shock is estimated by OLS of y_{t+h} on shock_t (plus
controls). Under a stable AR(1) with a direct effect, the IRF at h=0
recovers the direct impact (no double-counting of lagged effects). Analytical
evidence tier (known-truth recovery on a deterministic AR(1) DGP).
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp

DIRECT = 0.3  # y_t = 0.3 * shock_t + 0.2 * shock_{t-1} + ...
LAG = 0.2


def _dgp(seed, T=200, shock_at=100):
    rng = np.random.default_rng(seed)
    shock = np.zeros(T)
    shock[shock_at] = 1.0
    y = np.zeros(T)
    for t in range(1, T):
        y[t] = (
            0.5 * y[t - 1]
            + DIRECT * shock[t]
            + LAG * shock[max(0, t - 1)]
            + rng.normal(0, 1)
        )
    return pd.DataFrame(
        {
            "y": y,
            "shock": shock,
            "x1": rng.normal(0, 1, T),
        }
    )


def test_irf_at_h0_recovers_direct_effect():
    r = sp.local_projections(_dgp(0), outcome="y", shock="shock", horizons=4)
    # IRF is indexed from h=-1 (baseline) ... h=horizons-1.
    # After Jordà's convention: index 0 is h=-1 (mean before shock).
    # h=0 is the first post-shock period -> should be DIRECT.
    h_zero_value = float(r.irf[1])  # first post-shock = h=0
    assert h_zero_value == pytest.approx(DIRECT, abs=0.15)


def test_irf_at_h1_lags_persist_through_ar():
    # At h=1 (one period after shock), the IRF is bounded but non-zero
    # because the AR(1) propagates the shock + a lag term contributes.
    r = sp.local_projections(_dgp(0), outcome="y", shock="shock", horizons=4)
    h_one_value = float(r.irf[2])  # h=1
    # Not zero (the lag term is non-zero)
    assert abs(h_one_value) > 0.05
    # And is finite / reasonable
    assert abs(h_one_value) < 5.0


def test_irf_values_finite_and_reasonable():
    r = sp.local_projections(_dgp(0), outcome="y", shock="shock", horizons=4)
    irf = np.asarray(r.irf, dtype=float)
    assert np.all(np.isfinite(irf))
    # The IRF values are all bounded; the impact doesn't explode.
    assert np.all(np.abs(irf) < 5.0)

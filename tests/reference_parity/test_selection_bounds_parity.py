"""Analytical parity: sp.selection_bounds Lee-type recovery.

The conditional selection-bounds estimator reports Lee-type trimming bounds.
On a monotone-selection DGP with a constant planted effect the bounds bracket
the truth, the trimming fraction and selection rates equal their exact
definitions, and the bounds sit within numerical-implementation distance
(<= 5e-3, quantile-interpolation variant) of the plain Lee closed form.
Analytical evidence tier.
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
N = 4000


@pytest.fixture(scope="module")
def fitted():
    rng = np.random.default_rng(0)
    x = rng.normal(0, 1, N)
    d = (rng.random(N) < 1 / (1 + np.exp(-2.5 * x))).astype(int)
    s = (rng.random(N) < (0.5 + 0.3 * d)).astype(int)
    y = np.where(s == 1, BETA * d + rng.normal(0, 1, N), np.nan)
    df = pd.DataFrame({"y": y, "d": d, "s": s})
    return df, sp.selection_bounds(df, y="y", treatment="d", selection="s")


def test_rates_and_trim_fraction_exact(fitted):
    df, r = fitted
    mi = r.model_info
    s1 = df.loc[df.d == 1, "s"].mean()
    s0 = df.loc[df.d == 0, "s"].mean()
    assert mi["selection_rate_treated"] == pytest.approx(s1, abs=1e-15)
    assert mi["selection_rate_control"] == pytest.approx(s0, abs=1e-15)
    assert mi["trimming_fraction"] == pytest.approx((s1 - s0) / s1, abs=1e-12)


def test_bounds_bracket_truth_and_track_lee_form(fitted):
    df, r = fitted
    assert float(r.lower) <= BETA <= float(r.upper)
    y1 = df.loc[(df.d == 1) & (df.s == 1), "y"].to_numpy()
    y0 = df.loc[(df.d == 0) & (df.s == 1), "y"].to_numpy()
    s1 = df.loc[df.d == 1, "s"].mean()
    s0 = df.loc[df.d == 0, "s"].mean()
    p = (s1 - s0) / s1
    lower_lee = y1[y1 <= np.quantile(y1, 1 - p)].mean() - y0.mean()
    upper_lee = y1[y1 >= np.quantile(y1, p)].mean() - y0.mean()
    assert float(r.lower) == pytest.approx(lower_lee, abs=5e-3)
    assert float(r.upper) == pytest.approx(upper_lee, abs=5e-3)

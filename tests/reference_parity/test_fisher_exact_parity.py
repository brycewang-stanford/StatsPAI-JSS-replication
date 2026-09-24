"""Analytical parity: sp.fisher_exact randomization-test identities.

Fisher randomization inference under the sharp null (Fisher 1935 framework;
permutation implementation). Exactly checkable properties:

    statistic (ate) == mean(y | d=1) - mean(y | d=0)   (machine-exact)
    same seed -> identical p-value (deterministic permutation stream)
    strong planted effect -> small p; the p-value is a valid permutation scale

Analytical evidence tier (identities + known-truth behaviour; the permutation
p has Monte-Carlo resolution 1/n_perm, not a cross-package target).
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp


def _data(seed, effect):
    rng = np.random.default_rng(seed)
    n = 120
    d = rng.integers(0, 2, n)
    y = ((0.3 + effect * d) > rng.random(n)).astype(int)
    return pd.DataFrame({"y": y, "d": d})


def test_statistic_is_exact_mean_difference():
    df = _data(0, 0.4)
    r = sp.fisher_exact(df, y="y", treatment="d", seed=0, n_perm=2000)
    y1 = df.loc[df["d"] == 1, "y"].mean()
    y0 = df.loc[df["d"] == 0, "y"].mean()
    assert float(r.statistic) == pytest.approx(float(y1 - y0), abs=1e-15)


def test_seeded_determinism():
    df = _data(1, 0.4)
    p1 = sp.fisher_exact(df, y="y", treatment="d", seed=7, n_perm=2000).p_value
    p2 = sp.fisher_exact(df, y="y", treatment="d", seed=7, n_perm=2000).p_value
    assert float(p1) == float(p2)


def test_power_against_planted_effect():
    strong = sp.fisher_exact(_data(2, 0.5), y="y", treatment="d", seed=0, n_perm=2000)
    assert float(strong.p_value) < 0.01
    lo, hi = strong.ci
    assert lo <= float(strong.statistic) <= hi

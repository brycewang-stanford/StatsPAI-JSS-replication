"""Analytical parity: sp.lrtest exact likelihood-ratio identity.

The likelihood-ratio test statistic is the closed form

    chi2 == 2 * (logL_full - logL_restricted)

with the reported logL fields equal to the models' own ``log_likelihood``
attributes and p == chi2 survival at the df difference. Verified on nested
ML-fitted mixed models to machine precision (observed diff 0).
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest
from scipy import stats

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp


@pytest.fixture(scope="module")
def models():
    rng = np.random.default_rng(0)
    G, m = 40, 25
    g = np.repeat(np.arange(G), m)
    u = rng.normal(0, 0.8, G)[g]
    x = rng.normal(0, 1, G * m)
    y = 1 + 0.5 * x + u + rng.normal(0, 1, G * m)
    df = pd.DataFrame({"y": y, "x": x, "g": g})
    full = sp.mixed(df, y="y", x_fixed=["x"], group="g", method="ml")
    restricted = sp.mixed(df, y="y", x_fixed=[], group="g", method="ml")
    return restricted, full


def test_chi2_is_twice_loglik_difference(models):
    restricted, full = models
    r = sp.lrtest(restricted, full)
    hand = 2 * (float(full.log_likelihood) - float(restricted.log_likelihood))
    assert float(r.chi2) == pytest.approx(hand, abs=1e-10)
    assert float(r.full_logL) == pytest.approx(float(full.log_likelihood), abs=1e-12)
    assert float(r.restricted_logL) == pytest.approx(
        float(restricted.log_likelihood), abs=1e-12
    )


def test_pvalue_is_chi2_survival(models):
    restricted, full = models
    r = sp.lrtest(restricted, full)
    assert float(r.df) == 1.0
    assert float(r.p_value) == pytest.approx(
        float(stats.chi2.sf(float(r.chi2), 1)), abs=1e-12
    )
    assert bool(r.boundary_corrected) is False

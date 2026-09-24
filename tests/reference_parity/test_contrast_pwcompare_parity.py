"""Analytical parity: sp.contrast / sp.pwcompare treatment-contrast identity.

For a linear model with a treatment-coded categorical C(g), the reference
contrast of predictive margins collapses to the corresponding dummy
coefficient (all other covariates average out and cancel in the difference):

    contrast(r): level k vs ref  ==  coef[C(g)[T.k]]
    pwcompare:   level j vs k     ==  coef[C(g)[T.j]] - coef[C(g)[T.k]]

Both hold to machine precision (observed <= 1e-15). This also guards the
correctness fix that taught the margins machinery to parse C(var)[T.level]
design terms (previously these returned all-zero contrasts).
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp

B1, B2 = 0.5, 1.2


@pytest.fixture(scope="module")
def fitted():
    rng = np.random.default_rng(0)
    n = 3000
    g = rng.integers(0, 3, n)
    xc = rng.normal(0, 1, n)
    y = 1 + B1 * (g == 1) + B2 * (g == 2) + 0.7 * xc + rng.normal(0, 0.3, n)
    df = pd.DataFrame({"y": y, "g": g, "xc": xc})
    return df, sp.regress("y ~ C(g) + xc", data=df)


def test_reference_contrast_equals_dummy_coefficient(fitted):
    df, res = fitted
    b = res.params
    c = sp.contrast(res, data=df, variable="g", method="r", reference=0)
    got = dict(zip(c["contrast_label"], c["contrast"]))
    assert got["1 vs 0"] == pytest.approx(b["C(g)[T.1]"], abs=1e-12)
    assert got["2 vs 0"] == pytest.approx(b["C(g)[T.2]"], abs=1e-12)
    # not the previously-broken all-zero output
    assert abs(got["1 vs 0"]) > 0.1


def test_pwcompare_pairwise_differences(fitted):
    df, res = fitted
    b = res.params
    p = sp.pwcompare(res, data=df, variable="g")
    got = dict(zip(p["comparison"], p["diff"]))
    assert got["1 vs 0"] == pytest.approx(b["C(g)[T.1]"], abs=1e-12)
    assert got["2 vs 0"] == pytest.approx(b["C(g)[T.2]"], abs=1e-12)
    assert got["2 vs 1"] == pytest.approx(b["C(g)[T.2]"] - b["C(g)[T.1]"], abs=1e-12)


def test_recovers_planted_effects(fitted):
    df, res = fitted
    c = sp.contrast(res, data=df, variable="g", method="r", reference=0)
    got = dict(zip(c["contrast_label"], c["contrast"]))
    assert got["1 vs 0"] == pytest.approx(B1, abs=0.05)
    assert got["2 vs 0"] == pytest.approx(B2, abs=0.05)

"""Analytical parity: sp.mediate_interventional telescoping identity + recovery.

Interventional (in)direct effects (VanderWeele, Vansteelandt & Robins 2014)
decompose the total effect as a telescoping sum over the same Monte-Carlo
draws:

    IIE = E[Y(1, G_{M|1})] - E[Y(1, G_{M|0})]
    IDE = E[Y(1, G_{M|0})] - E[Y(0, G_{M|0})]
    Total = IIE + IDE          (exact, the middle term cancels)

so ``total_effect == iie + ide`` holds to machine precision. On a linear DGP
M = 0.5 D + e_M, Y = 0.8 D + 0.6 M + e_Y the components recover their
population values IDE = 0.8 and IIE = 0.6 * 0.5 = 0.3.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp

IDE_TRUE = 0.8
IIE_TRUE = 0.6 * 0.5


@pytest.fixture(scope="module")
def result():
    rng = np.random.default_rng(0)
    n = 3000
    D = rng.integers(0, 2, n)
    M = 0.5 * D + rng.normal(0, 1, n)
    Y = 0.8 * D + 0.6 * M + rng.normal(0, 0.5, n)
    df = pd.DataFrame({"Y": Y, "D": D, "M": M})
    return sp.mediate_interventional(
        df, y="Y", treat="D", mediator="M", n_boot=50, seed=0
    )


def test_total_equals_iie_plus_ide_exactly(result):
    d = result.diagnostics
    assert float(d["total_effect"]) == pytest.approx(
        float(d["iie"]) + float(d["ide"]), abs=1e-12
    )


def test_recovers_population_components(result):
    d = result.diagnostics
    assert float(d["ide"]) == pytest.approx(IDE_TRUE, abs=0.1)
    assert float(d["iie"]) == pytest.approx(IIE_TRUE, abs=0.1)

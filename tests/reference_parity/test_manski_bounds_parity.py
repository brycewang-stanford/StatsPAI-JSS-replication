"""Analytical parity: sp.manski_bounds no-assumption width identity (exact).

Manski (1990) worst-case (no-assumption) ATE bounds have an exact closed form.
With the outcome known to lie in ``[y_lower, y_upper]`` the bound width is
*independent of the data*:

    upper_bound - lower_bound == y_upper - y_lower

and each bound reconstructs exactly from the observed cell means and the
treatment share:

    upper = m1*p + yU*(1-p) - m0*(1-p) - yL*p
    lower = m1*p + yL*(1-p) - m0*(1-p) - yU*p

where m1, m0 are the treated/control outcome means and p = P(D=1). All hold to
machine precision. Closed-form identity (no external fixture).
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp

Y_LOWER, Y_UPPER = 0.0, 1.0


@pytest.fixture(scope="module")
def result():
    rng = np.random.default_rng(3)
    n = 1500
    d = rng.integers(0, 2, n)
    y = (0.3 + 0.4 * d + rng.normal(0, 0.1, n)).clip(0, 1)
    df = pd.DataFrame({"y": y, "d": d})
    return sp.manski_bounds(
        df, y="y", treat="d", y_lower=Y_LOWER, y_upper=Y_UPPER, assumption="none"
    )


def test_bound_width_equals_outcome_range(result):
    diag = result.diagnostics
    width = float(diag["upper_bound"]) - float(diag["lower_bound"])
    assert width == pytest.approx(Y_UPPER - Y_LOWER, abs=1e-12)
    assert float(diag["bound_width"]) == pytest.approx(Y_UPPER - Y_LOWER, abs=1e-12)


def test_bounds_reconstruct_from_cell_means(result):
    d = result.diagnostics
    p = float(d["p_treated"])
    m1 = float(d["mean_y_treated"])
    m0 = float(d["mean_y_control"])
    upper = m1 * p + Y_UPPER * (1 - p) - m0 * (1 - p) - Y_LOWER * p
    lower = m1 * p + Y_LOWER * (1 - p) - m0 * (1 - p) - Y_UPPER * p
    assert float(d["upper_bound"]) == pytest.approx(upper, abs=1e-12)
    assert float(d["lower_bound"]) == pytest.approx(lower, abs=1e-12)


def test_bounds_ordered_and_contain_point(result):
    d = result.diagnostics
    assert float(d["lower_bound"]) <= float(d["upper_bound"])
    assert float(d["lower_bound"]) <= float(result.estimate) <= float(d["upper_bound"])

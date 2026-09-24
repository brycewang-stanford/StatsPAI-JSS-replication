"""Frozen-formula parity: sp.four_way_decomposition telescoping sum.

VanderWeele (2014) parametric four-way decomposition:
    TE = CDE(a0, a1; m0) + INT_ref + INT_med + PIE
The four components sum to the total effect (a0 = 0, a1 = 1 by default).
Bit-exact against the closed-form identity.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp


def test_four_components_sum_to_total_effect():
    rng = np.random.default_rng(0)
    n = 5000
    tr = rng.binomial(1, 0.5, n).astype(float)
    m = 0.3 + 0.4 * tr + rng.normal(0, 0.5, n)
    y = 0.5 + 0.6 * tr + 0.4 * m + rng.normal(0, 0.3, n)
    df = pd.DataFrame({"y": y, "t": tr, "m": m})
    r = sp.four_way_decomposition(df, y="y", treat="t", mediator="m")
    assert r.cde + r.int_ref + r.int_med + r.pie == pytest.approx(
        r.total_effect, abs=1e-9
    )


def test_cde_close_to_direct_effect_when_no_m_pathway():
    """With M generated from T only, the indirect effects vanish and CDE ≈ TE."""
    rng = np.random.default_rng(1)
    n = 5000
    tr = rng.binomial(1, 0.5, n).astype(float)
    # M is independent of T (and Y is just T + noise) — INT_ref ≈ 0,
    # INT_med ≈ 0, PIE ≈ 0, so CDE ≈ TE.
    m = rng.normal(0, 1, n)
    y = 0.5 + 0.8 * tr + rng.normal(0, 1, n)
    df = pd.DataFrame({"y": y, "t": tr, "m": m})
    r = sp.four_way_decomposition(df, y="y", treat="t", mediator="m")
    assert r.int_ref == pytest.approx(0.0, abs=0.05)
    assert r.int_med == pytest.approx(0.0, abs=0.05)
    assert r.pie == pytest.approx(0.0, abs=0.05)
    assert r.cde == pytest.approx(r.total_effect, abs=0.05)

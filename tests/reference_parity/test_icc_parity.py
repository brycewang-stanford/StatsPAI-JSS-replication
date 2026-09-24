"""Analytical parity: sp.icc exact variance-component identity.

For a random-intercept mixed model the intraclass correlation is the exact
transform of the fitted variance components:

    ICC == var(_cons) / (var(_cons) + var(Residual))

verified to machine precision against the model's own ``variance_components``.
Across seeds the estimate tracks the *realized* group-effect variance of each
draw (the REML target), and the delta-method CI stays inside (0, 1).
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp


def _fit(seed, G=60, m=25):
    rng = np.random.default_rng(seed)
    g = np.repeat(np.arange(G), m)
    ug = rng.normal(0, 0.8, G)
    u = ug[g]
    x = rng.normal(0, 1, G * m)
    y = 1 + 0.5 * x + u + rng.normal(0, 1, G * m)
    df = pd.DataFrame({"y": y, "x": x, "g": g})
    model = sp.mixed(df, y="y", x_fixed=["x"], group="g")
    realized_var_u = float(np.var(ug, ddof=1))
    return model, realized_var_u


def test_icc_is_exact_varcomp_transform():
    model, _ = _fit(0)
    r = sp.icc(model, n_boot=0)
    vc = model.variance_components
    hand = vc["var(_cons)"] / (vc["var(_cons)"] + vc["var(Residual)"])
    assert float(r.estimate) == pytest.approx(float(hand), abs=1e-12)
    assert 0.0 < float(r.ci_lower) < float(r.estimate) < float(r.ci_upper) < 1.0


def test_tracks_realized_group_variance_across_seeds():
    diffs = []
    for seed in range(3):
        model, realized_var_u = _fit(seed)
        est = float(sp.icc(model, n_boot=0).estimate)
        realized_icc = realized_var_u / (realized_var_u + 1.0)
        diffs.append(abs(est - realized_icc))
    assert max(diffs) < 0.05

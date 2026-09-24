"""Analytical parity: sp.conformal_fair_ite coverage + fairness (MC).

Counterfactual-fair conformal ITE intervals excise the protected attribute from
the outcome model but calibrate per protected group, so the guarantee is a
*balanced* marginal-coverage property: each protected group's interval brackets
the conditional average treatment effect tau(x) with probability at least
``1 - alpha``. The honest evidence tier is a probabilistic lower bound verified
by Monte-Carlo on a known DGP (both potential outcomes simulated), plus the
exact structural identities of the returned interval matrix.

Note: the intervals bracket the conditional-mean effect tau(x); they are not
sized to cover the noisier *realized* ITE Y(1)-Y(0), so we check tau-coverage.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp

ALPHA = 0.1
N = 1500
COVS = ["x0", "x1", "x2"]


def _simulate(seed):
    rng = np.random.default_rng(seed)
    X = rng.normal(0, 1, (N, 3))
    prot = rng.integers(0, 2, N)
    base = X[:, 0] + 0.3 * X[:, 1]
    tau = 1.0 + 0.5 * X[:, 0]
    y0 = base + rng.normal(0, 0.5, N)
    y1 = base + tau + rng.normal(0, 0.5, N)
    d = rng.integers(0, 2, N)
    y = np.where(d == 1, y1, y0)
    df = pd.DataFrame(
        {
            "y": y,
            "treat": d,
            "x0": X[:, 0],
            "x1": X[:, 1],
            "x2": X[:, 2],
            "prot": prot,
        }
    )
    return df, tau, prot


def _fit(df, seed):
    return sp.conformal_fair_ite(
        df,
        y="y",
        treat="treat",
        covariates=COVS,
        protected="prot",
        alpha=ALPHA,
        seed=seed,
    )


def test_balanced_group_coverage_at_least_nominal():
    overall, g0, g1 = [], [], []
    for seed in range(6):
        df, tau, prot = _simulate(seed)
        iv = np.asarray(_fit(df, seed).intervals)
        inside = (tau >= iv[:, 0]) & (tau <= iv[:, 1])
        overall.append(float(inside.mean()))
        g0.append(float(inside[prot == 0].mean()))
        g1.append(float(inside[prot == 1].mean()))
    # Distribution-free lower bound (allow small MC slack per replicate).
    assert min(overall) >= (1 - ALPHA) - 0.05
    # Fairness: both protected groups meet the nominal level.
    assert min(g0) >= (1 - ALPHA) - 0.05
    assert min(g1) >= (1 - ALPHA) - 0.05


def test_interval_structural_identities():
    df, _, _ = _simulate(0)
    r = _fit(df, 0)
    iv = np.asarray(r.intervals)
    assert iv.shape == (N, 2)
    assert np.all(iv[:, 0] <= iv[:, 1])
    assert float(r.coverage_target) == pytest.approx(ALPHA)
    for tgt in r.group_coverage_targets.values():
        assert float(tgt) == pytest.approx(1 - ALPHA)

"""Known-truth recovery for panel causal forests (evidence: analytical-only).

Three deterministic designs with a known population parameter; no
cross-package reference applies (the forests are stochastic and no reference
implements the same estimator on the same bytes).

* ``sp.did_forest`` on the simulation design of Gavrilova, Langorgen and
  Zoutman (2025, Appendix C; [@gavrilova2025difference]): workers nested in
  firms, firm-level treatment with propensity ``exp(x1_bar)/(exp(x1_bar) +
  exp(x2_bar))``, conditional ATT 10 for ``x1 = 1`` and 1 for ``x1 = 0``.
  The mean unit-level CATE in each ``x1`` group must be within 0.5 of the
  truth; the overall ATT within 3.5 cluster-robust standard errors of
  ``1 + 9 * share(x1 = 1 | treated)``.
* ``sp.causal_forest(fe="twoway")`` on a staggered panel where adoption
  selects on the unit effect and the effect is constant (tau = 1.5): the mean
  OOB CATE on treated rows must be within 0.15 of 1.5, while the pooled forest
  is off by more than 0.5 (the confounding the FE forest removes).
* ``sp.calibrate_cate`` under a constant effect: the out-of-bag calibration
  slope must not detect heterogeneity (one-sided p > 0.05) and calibrated
  predictions must have a smaller spread than the raw OOB predictions.

Seeds are fixed; tolerances are sized to the Monte Carlo spread observed over
4 seeds at calibration time (see docs/guides/heterogeneity_panel_forests.md).
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

import statspai as sp
from statspai.exceptions import AssumptionWarning


def test_did_forest_recovers_gavrilova_langorgen_zoutman_catt():
    rng = np.random.default_rng(4321)
    firms, per_firm = 120, 12
    firm = np.repeat(np.arange(firms), per_firm)
    n = firm.size
    x1 = rng.binomial(1, 0.5, n)
    x2 = rng.binomial(1, 0.5, n)
    m1 = np.bincount(firm, weights=x1) / per_firm
    m2 = np.bincount(firm, weights=x2) / per_firm
    p = np.exp(m1) / (np.exp(m1) + np.exp(m2))
    W = rng.binomial(1, p)[firm]
    sd = (np.bincount(firm, weights=rng.choice(np.arange(1, 11) / 10, n)) / per_firm)[
        firm
    ]
    rows = []
    for t in (1, 2):
        tau = np.where(x1 == 1, 10.0, 1.0)
        y = (
            10
            + (t == 2)
            + tau * W * (t == 2)
            + x1
            + (t == 2) * x2
            + rng.normal(scale=sd)
        )
        rows.append(
            pd.DataFrame(
                dict(
                    worker=np.arange(n),
                    t=t,
                    firm=firm,
                    x1=x1,
                    x2=x2,
                    y=y,
                    g=np.where(W == 1, 2, 0),
                )
            )
        )
    df = pd.concat(rows, ignore_index=True)
    res = sp.did_forest(
        df,
        y="y",
        id="worker",
        time="t",
        cohort="g",
        x=["x1", "x2"],
        clusters="firm",
        n_estimators=600,
    )
    assert res.n_clusters == firms
    cate = res.unit_cate.merge(
        df[df["t"] == 2][["worker", "x1"]].rename(columns={"worker": "unit"}), on="unit"
    )
    assert abs(cate.loc[cate["x1"] == 1, "cate"].mean() - 10.0) < 0.5
    assert abs(cate.loc[cate["x1"] == 0, "cate"].mean() - 1.0) < 0.5
    share = df[(df["t"] == 2) & (df["g"] == 2)]["x1"].mean()
    truth = 1 + 9 * share
    assert abs(res.overall["estimate"] - truth) < 3.5 * res.overall["se"]


def _staggered_panel(seed: int = 2, N: int = 300, T: int = 5):
    rng = np.random.default_rng(seed)
    unit = np.repeat(np.arange(N), T)
    time = np.tile(np.arange(T), N)
    alpha = rng.normal(scale=3.0, size=N)
    adopt = np.where(alpha > 0.5, 2, np.where(alpha > -0.5, 3, 99))
    D = (time >= adopt[unit]).astype(float)
    X = rng.normal(size=(N, 2))[unit]
    Y = alpha[unit] + 2.0 * time + 1.5 * D + rng.normal(size=N * T)
    df = pd.DataFrame(X, columns=["x1", "x2"])
    df["y"], df["d"], df["id"], df["t"] = Y, D, unit, time
    return df


def test_fe_forest_recovers_constant_effect_under_fixed_effect_selection():
    df = _staggered_panel()
    treated = df["d"].to_numpy() == 1
    fe = sp.causal_forest(
        data=df,
        y="y",
        d="d",
        x=["x1", "x2"],
        id="id",
        time="t",
        fe="twoway",
        n_estimators=600,
        random_state=0,
    )
    assert abs(fe.predict()[treated].mean() - 1.5) < 0.15
    pooled = sp.causal_forest(
        data=df,
        y="y",
        d="d",
        x=["x1", "x2"],
        clusters="id",
        n_estimators=600,
        random_state=0,
    )
    assert abs(pooled.predict()[treated].mean() - 1.5) > 0.5


def test_calibrate_cate_does_not_manufacture_heterogeneity():
    rng = np.random.default_rng(12)
    n = 2000
    X = rng.normal(size=(n, 5))
    T = rng.integers(0, 2, n)
    Y = X[:, 1] + 1.0 * T + rng.normal(size=n)
    cf = sp.causal_forest(Y=Y, T=T, X=X, n_estimators=1000, random_state=0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", AssumptionWarning)
        cal = sp.calibrate_cate(cf)
    assert not cal["heterogeneity_detected"]
    assert np.std(cal["cate"]) < np.std(cal["raw_cate"])
    assert abs(np.mean(cal["cate"]) - 1.0) < 0.15

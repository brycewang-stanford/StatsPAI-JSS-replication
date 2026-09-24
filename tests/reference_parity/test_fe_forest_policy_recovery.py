"""Known-truth Monte Carlo for policy learning on FE forests (T1).

``tau = 0.3 + b z`` with ``z`` standard normal and independent of adoption,
and a per-cell ``cost``. A rule that treats where ``z > theta`` is then
worth, relative to treating every cell,

    gain(theta) = -E[(tau - cost) 1{z <= theta}]

which is computable exactly for the realised evaluation cells. Two claims
are pinned:

1. **The split is doing work.** With ``b = 0`` and ``cost = 0.3`` every rule
   is worth exactly the same, so the true gain is exactly 0. A tree fitted
   on the scores it is then priced against does not find 0: it averaged
   +0.048 -- more than its own standard error -- and 13.0% of runs reported
   a significant benefit from targeting. Fitted and priced on disjoint
   halves: +0.005 and 3.5%.
2. **The split costs little when the heterogeneity is real.** With
   ``b = 0.8`` and ``cost = 0.3`` the oracle gain is ``0.8 * phi(0) =
   0.3191``; the split-sample estimate averaged 0.3189 at 99.5% power
   against a same-sample 0.3316 that overshoots by 0.012.

These runs use ``n_splits=1`` deliberately: the claim under test is what
one split's pricing does against the same-sample alternative, which is the
comparison ``n_splits`` was introduced to settle. Aggregating would hide
exactly the quantity being measured.

``REPS`` is 30 here against the 200 those figures came from, so only the
ordering and the sign are asserted, with bands wide enough for the Monte
Carlo error (binomial sd ~4 points at a 5% rate).
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

import statspai as sp
from statspai.forest import _fe_imputation as fi
from statspai.forest.forest_heterogeneity import _policy_functional, _refit_halves
from statspai.policy_learning._exact_tree import exact_policy_tree
from statspai.policy_learning.policy_tree import PolicyTree

REPS = 30
N_UNITS, N_PERIODS = 200, 8
TAU0, COST = 0.3, 0.3


def _panel(seed: int, slope: float) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(N_UNITS):
        a, z, w = rng.normal(), rng.normal(), rng.normal()
        never = i % 5 == 0
        g = 10**6 if never else int(np.clip(4 + round(a), 3, N_PERIODS))
        for t in range(1, N_PERIODS + 1):
            d = 1.0 * (t >= g)
            tau = TAU0 + slope * z
            y = a + 0.25 * t + tau * d + rng.normal(0, 0.6)
            rows.append((i, t, y, d, z, w, tau))
    return pd.DataFrame(rows, columns=["id", "t", "y", "d", "z", "w", "tau"])


def _same_sample_gain(cf, cost: float) -> dict:
    """Fit the tree on every treated cell and price it on the same ones."""
    design = fi.imputation_design(cf, "mc", "none")
    rows = np.flatnonzero(design.target)
    x = np.asarray(cf._X_original, dtype=float)[rows]
    leaf = max(10, int(0.05 * rows.size))
    tree = exact_policy_tree(
        x, design.gamma[rows] - cost, max_depth=1, min_leaf_size=leaf
    )
    helper = PolicyTree.__new__(PolicyTree)
    helper.max_depth, helper.min_leaf_size, helper.split_step = 1, leaf, 1
    policy = helper._predict_tree(tree, x)
    return _policy_functional(
        cf,
        policy,
        cost=cost,
        variance="bjs",
        cluster=None,
        members=None,
        covariates="none",
        alpha=0.05,
        context="mc",
    )["gain_over_treat_all"]


def _run(slope: float) -> pd.DataFrame:
    rows = []
    for seed in range(REPS):
        df = _panel(seed, slope)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            cf = sp.causal_forest(
                "y ~ d | z + w",
                data=df,
                fe="twoway",
                unit="id",
                time="t",
                clusters=df["id"].to_numpy(),
                n_estimators=250,
                random_state=seed,
            )
            naive = _same_sample_gain(cf, COST)
            split = sp.forest_policy_tree(
                cf, depth=1, cost=COST, n_splits=1, random_state=seed
            )
            halves = _refit_halves(cf, None, 0.5, seed, "mc")
            design_ev = fi.imputation_design(halves.evaluate, "mc", "none")
            rows_ev = np.flatnonzero(design_ev.target)
            tau_ev = df["tau"].to_numpy()[halves.in_eval][rows_ev]
            policy = split["policy"].astype(float)
            truth = float(np.mean((tau_ev - COST) * (policy - 1.0)))
        gain = split["gain_over_treat_all"]
        rows.append(
            {
                "naive_gain": naive["estimate"],
                "naive_claims": bool(naive["ci_low"] > 0),
                "split_gain": gain["estimate"],
                "split_claims": bool(gain["ci_low"] > 0),
                "split_err": gain["estimate"] - truth,
                "split_covers": bool(gain["ci_low"] <= truth <= gain["ci_high"]),
                "truth": truth,
            }
        )
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def null_runs():
    return _run(slope=0.0)


@pytest.fixture(scope="module")
def alternative_runs():
    return _run(slope=0.8)


@pytest.mark.slow
def test_same_sample_pricing_invents_a_gain_that_is_not_there(null_runs):
    # Every rule is worth exactly 0 here, so any positive average is the
    # tree being priced on its own noise.
    m = null_runs.mean(numeric_only=True)
    assert m["naive_gain"] > 0.02
    assert m["naive_claims"] > 0.05


@pytest.mark.slow
def test_splitting_removes_it(null_runs):
    m = null_runs.mean(numeric_only=True)
    assert abs(m["split_gain"]) < 0.02
    assert abs(m["split_gain"]) < m["naive_gain"]
    assert m["split_claims"] <= 0.15
    assert m["split_claims"] < m["naive_claims"]


@pytest.mark.slow
def test_the_split_still_finds_a_real_gain(alternative_runs):
    m = alternative_runs.mean(numeric_only=True)
    oracle = 0.8 * float(np.exp(0) / np.sqrt(2 * np.pi))  # 0.8 * phi(0)
    assert m["split_claims"] >= 0.9
    assert abs(m["split_gain"] - oracle) < 0.08
    # The same-sample version overshoots even here.
    assert m["naive_gain"] > m["split_gain"]


@pytest.mark.slow
def test_the_split_sample_gain_covers_the_rule_it_actually_fitted(
    alternative_runs,
):
    m = alternative_runs.mean(numeric_only=True)
    assert abs(m["split_err"]) < 0.05
    assert m["split_covers"] >= 0.85

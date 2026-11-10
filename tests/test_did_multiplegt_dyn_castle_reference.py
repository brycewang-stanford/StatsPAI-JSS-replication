"""``sp.did_multiplegt_dyn`` on the castle-doctrine panel vs the authors' packages.

Reference values: ``Paper-DiD-JAE/replication/applications/castle/results/
castle_R.json`` (R ``DIDmultiplegtDYN`` 2.3.4 via ``DIDmultiplegt`` 2.1.0,
``did_multiplegt_dyn(df, "l_homicide", "sid", "year", "treat", effects = 5,
placebo = 3, cluster = "sid")``, and the same with ``weight = "popwt"``) and
``castle_Stata.json`` (Stata 18 ``did_multiplegt_dyn l_homicide sid year
treat, effects(5) placebo(3) cluster(sid) [weight(popwt)]``). R and Stata
agree with each other to 2e-7 relative on every row; the constants below are
the R side (canonical, the authors' own), copied verbatim from the JSON.

Both reference runs use the packages' default inference, which is the
analytic influence-function variance (``bootstrap = NULL``), and the
packages' ``Av_tot_eff`` = switcher-weighted average of the five effects,
so the StatsPAI call is ``dynamic=4`` (five effects: their ``Effect_k`` is
horizon ``k-1``), ``aggregation="switchers"``, ``se_method="analytic"``.

Panel: ``sp.datasets.castle_doctrine(event_time=True)`` with
``treat = (gvar > 0) & (year >= gvar)``; identical to the replication CSV
(50 states x 2000-2010, cohorts 2005:1, 2006:13, 2007:4, 2008:2, 2009:1).

What this pins that Track A module 78 does not:

* the placebo sample rule on a panel where it bites -- cohort 2009 supports
  effect 3 only if observed at 2011, so it drops from Effect_3 AND from
  Placebo_3 (20 switchers, not 21), and placebo 2's control group is
  "not yet switched at F+1", not "at F";
* the analytic standard errors, including a single-switcher cohort (2005,
  Florida) whose residual the reference centres on the pooled cell;
* ``weight=`` against the packages' ``weight()``.

Tolerance: 1e-6 relative on every estimate and SE (CLAUDE.md §5.1 T2).
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

import statspai as sp

RTOL = 1e-6

# (estimate, se, switchers) from castle_R.json, estimator == "dcdh".
R_UNW = {
    "att": (0.109327431128696, 0.0406453766620652, 94),
    0: (0.102576092364649, 0.0438949121584593, 21),
    1: (0.113269605939078, 0.0474836285381435, 21),
    2: (0.0993179839687141, 0.0599355365598398, 20),
    3: (0.136747060005747, 0.0603028720739205, 18),
    4: (0.0925865787315271, 0.055955338517631, 14),
    -1: (0.0651515831469713, 0.0478637183545778, 21),
    -2: (0.0509659197662424, 0.0472129156897283, 21),
    -3: (0.0232443450725359, 0.0475581389535325, 20),
}
R_WT = {
    "att": (0.109095214674054, 0.0291023350161463, None),
    0: (0.0597974712568119, 0.0229951403033784, 21),
    1: (0.137807457495668, 0.0283796475100201, 21),
    2: (0.118134100393765, 0.0413529904756269, 20),
    3: (0.126381750872905, 0.0481387363727568, 18),
    4: (0.102969835629326, 0.0573305518235908, 14),
    -1: (0.0388248555347625, 0.0249326642556385, 21),
    -2: (0.0503416938610938, 0.0272248208174787, 21),
    -3: (0.0315450209088599, 0.0350048918317363, 20),
}
# Stata side, castle_Stata.json, for the rows the paper reports in the text.
STATA_UNW = {
    "att": (0.1093274486251175, 0.04064537922289846),
    0: (0.1025761060696095, 0.04389491084225664),
    -2: (0.0509659266564995, 0.04721291716883966),
    -3: (0.02324435442686081, 0.04755813990788012),
}
# cluster != group: Stata 18 MP ``did_multiplegt_dyn l_homicide sid year
# treat, effects(5) placebo(3) cluster(region) [weight(popwt)]`` with
# region = 1*northeast + 2*midwest + 3*south + 4*west (9/12/16/13 states),
# e() scalars printed at %21.17g on 2026-09-06 (scratch do-file, not part of
# the replication bundle). Estimates are unchanged by clustering; only the
# SEs move. Stata carries some intermediates in float, so 4e-7 is its own
# noise level here (it is 2e-7 against R on the group-clustered runs).
STATA_REGION_SE_UNW = {
    "att": 0.027982631210537148,
    0: 0.061488360811384035,
    1: 0.028497298037421522,
    2: 0.031884069776901454,
    3: 0.078299081260094786,
    4: 0.057406822148655785,
    -1: 0.041487151688791371,
    -2: 0.0583510856776841,
    -3: 0.079602224704579921,
}
STATA_REGION_SE_WT = {
    "att": 0.030567024911191645,
    0: 0.02840517940014526,
    1: 0.028944564789086403,
    2: 0.052539368469028042,
    3: 0.041317669099267935,
    4: 0.082784953088186633,
    -1: 0.012549849759903213,
    -2: 0.031756587902261678,
    -3: 0.052834759597700696,
}
# What the pre-1.25.1 code returned on this panel (placebo rule + variance).
OLD_PLACEBO_2 = 0.062241
OLD_PLACEBO_3 = 0.015389
OLD_SE_E0 = 0.041055


@pytest.fixture(scope="module")
def castle() -> pd.DataFrame:
    df = sp.datasets.castle_doctrine(event_time=True)
    df = df.copy()
    df["treat"] = ((df["gvar"] > 0) & (df["year"] >= df["gvar"])).astype(int)
    return df


def _fit(df: pd.DataFrame, **kw):
    base = dict(
        group="sid",
        time="year",
        treatment="treat",
        dynamic=4,
        placebo=3,
        control="not_yet_treated",
        aggregation="switchers",
        se_method="analytic",
        n_boot=0,
    )
    base.update(kw)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return sp.did_multiplegt_dyn(df, "l_homicide", **base)


@pytest.fixture(scope="module")
def unw(castle):
    return _fit(castle, cluster="sid")


@pytest.fixture(scope="module")
def wt(castle):
    return _fit(castle, cluster="sid", weight="popwt")


def _row(fit, key):
    if key == "att":
        return float(fit.estimate), float(fit.se)
    es = fit.model_info["event_study"].set_index("relative_time")
    return float(es.loc[key, "att"]), float(es.loc[key, "se"])


@pytest.mark.parametrize("key", list(R_UNW))
def test_unweighted_matches_r(unw, key):
    est, se = _row(unw, key)
    ref_est, ref_se, _ = R_UNW[key]
    assert est == pytest.approx(ref_est, rel=RTOL), (key, est, ref_est)
    assert se == pytest.approx(ref_se, rel=RTOL), (key, se, ref_se)


@pytest.mark.parametrize("key", list(R_WT))
def test_popwt_weighted_matches_r(wt, key):
    est, se = _row(wt, key)
    ref_est, ref_se, _ = R_WT[key]
    assert est == pytest.approx(ref_est, rel=RTOL), (key, est, ref_est)
    assert se == pytest.approx(ref_se, rel=RTOL), (key, se, ref_se)


@pytest.mark.parametrize("key", list(STATA_UNW))
def test_unweighted_matches_stata_too(unw, key):
    """Stata is the authors' port; it agrees with R to 2e-7 here."""
    est, se = _row(unw, key)
    ref_est, ref_se = STATA_UNW[key]
    assert est == pytest.approx(ref_est, rel=RTOL)
    assert se == pytest.approx(ref_se, rel=RTOL)


@pytest.mark.parametrize("h", [k for k in R_UNW if k != "att"])
def test_switcher_counts_match_the_reference_samples(unw, wt, h):
    """The sample behind each horizon, not just its number.

    Placebo 3 must drop cohort 2009 exactly as Effect_3 does: the reference
    computes placebo l on the switchers for which effect l is estimable.
    """
    detail = unw.detail.set_index("horizon")
    assert int(detail.loc[h, "n_switchers"]) == R_UNW[h][2]
    assert float(detail.loc[h, "w_switchers"]) == R_UNW[h][2]
    # Weighted run: same units, switcher weight becomes the popwt sum.
    detail_w = wt.detail.set_index("horizon")
    assert int(detail_w.loc[h, "n_switchers"]) == R_WT[h][2]
    assert float(detail_w.loc[h, "w_switchers"]) > 1e6


def test_switcher_weighted_headline_uses_the_five_effects(unw):
    """Av_tot_eff = Σ_l N_l δ_l / Σ_l N_l over effects 1..5 (94 switchers)."""
    es = unw.model_info["event_study"].set_index("relative_time")
    w = np.array([R_UNW[h][2] for h in range(5)], dtype=float)
    d = np.array([float(es.loc[h, "att"]) for h in range(5)])
    assert w.sum() == 94
    assert unw.estimate == pytest.approx(float((w * d).sum() / w.sum()), rel=1e-12)


def test_default_cluster_is_the_group(castle, unw):
    """cluster=None must equal cluster='sid' here: one group per cluster."""
    alt = _fit(castle)
    for key in R_UNW:
        assert _row(alt, key) == pytest.approx(_row(unw, key), rel=1e-12)


@pytest.fixture(scope="module")
def castle_region(castle):
    df = castle.copy()
    df["region"] = (
        1 * df["northeast"] + 2 * df["midwest"] + 3 * df["south"] + 4 * df["west"]
    ).astype(int)
    assert (df.groupby("sid")["region"].nunique() == 1).all()
    return df


@pytest.mark.parametrize("weighted", [False, True])
def test_cluster_coarser_than_group_matches_stata(castle_region, unw, wt, weighted):
    """The cluster path: distinct-cluster DOF counts and within-cluster sums.

    Every other reference run clusters on the group, so this is the only
    check that ``cluster=`` does what the authors' code does when a
    cluster holds several groups.
    """
    ref = STATA_REGION_SE_WT if weighted else STATA_REGION_SE_UNW
    same = wt if weighted else unw
    fit = _fit(castle_region, cluster="region", weight="popwt" if weighted else None)
    for key in ref:
        est, se = _row(fit, key)
        assert est == pytest.approx(_row(same, key)[0], rel=1e-12), key
        assert se == pytest.approx(ref[key], rel=RTOL), (key, se, ref[key])


def test_group_not_nested_in_cluster_is_an_error(castle_region):
    bad = castle_region.copy()
    bad.loc[bad.index[0], "region"] = 99
    with pytest.raises(ValueError, match="nested"):
        _fit(bad, cluster="region")


def test_regression_the_old_numbers_are_gone(unw):
    """Guards the two ⚠️ correctness fixes of 1.25.1 on this panel."""
    p2, _ = _row(unw, -2)
    p3, _ = _row(unw, -3)
    _, se0 = _row(unw, 0)
    assert abs(p2 - OLD_PLACEBO_2) > 1e-3
    assert abs(p3 - OLD_PLACEBO_3) > 1e-3
    assert abs(se0 - OLD_SE_E0) > 1e-3


def test_weight_argument_is_validated(castle):
    with pytest.raises(ValueError, match="weight"):
        _fit(castle, weight="no_such_column")
    bad = castle.copy()
    bad.loc[bad.index[0], "popwt"] = -1.0
    with pytest.raises(ValueError, match="negative"):
        _fit(bad, weight="popwt")


def test_bootstrap_path_keeps_the_same_point_estimates(castle, unw):
    """The bootstrap replicates estimate the same object as the analytic path."""
    boot = _fit(castle, se_method="bootstrap", n_boot=5, seed=0)
    for key in R_UNW:
        assert _row(boot, key)[0] == pytest.approx(_row(unw, key)[0], rel=1e-12)
    assert boot.model_info["se_method"] == "bootstrap"

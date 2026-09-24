"""Imputation-score inference and heterogeneity tools for panel forests.

Exact identities (the imputation ATT of an ``fe=`` forest *is* the
Borusyak-Jaravel-Spiess imputation estimator; group, BLP and calibration
estimates are linear functionals of the same scores; the dyadic variance is
the pairwise-sharing definition) plus known-truth checks on
``sp.datasets.currency_union_panel`` and the input contracts of
``sp.forest_group_effects``, ``sp.forest_support`` and
``sp.cate_pretrend_test``.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

import statspai as sp
from statspai.exceptions import (
    AssumptionWarning,
    DataInsufficient,
    MethodIncompatibility,
)
from statspai.forest import _fe_imputation as fi


def _panel(N=240, T=7, seed=0, hetero=True, pretrend=0.0, drop=0.0):
    rng = np.random.default_rng(seed)
    x1 = rng.standard_normal(N)
    x2 = rng.standard_normal(N)
    alpha = x1 + rng.standard_normal(N)
    p = 1 / (1 + np.exp(-alpha))
    cohort = np.where(rng.random(N) < p, rng.choice([3, 4, 6], size=N), 99)
    gamma = np.cumsum(rng.normal(0, 0.5, size=T))
    unit = np.repeat(np.arange(N), T)
    t = np.tile(np.arange(T), N)
    D = (t >= cohort[unit]).astype(float)
    e = np.maximum(t - cohort[unit], 0)
    tau = (1 + x1[unit]) * (1 + 0.2 * e) if hetero else np.ones(N * T)
    # Optional differential pre-trend for high-x1 treated units.
    lead = np.clip(cohort[unit] - t, 0, 3) * (cohort[unit] < 99) * (x1[unit] > 0)
    Y = alpha[unit] + gamma[t] + tau * D - pretrend * lead + rng.standard_normal(N * T)
    df = pd.DataFrame(
        {
            "id": unit,
            "t": t,
            "y": Y,
            "d": D,
            "x1": x1[unit],
            "x2": x2[unit],
            "tau": tau,
            "first_treat": np.where(cohort[unit] < 99, cohort[unit], 0),
        }
    )
    if drop:
        df = df.sample(frac=1 - drop, random_state=seed).sort_index()
        df = df.reset_index(drop=True)
    return df


def _fe(df, x=("x1", "x2"), n_estimators=400, seed=0, **kw):
    return sp.causal_forest(
        data=df,
        y="y",
        d="d",
        x=list(x),
        id="id",
        time="t",
        fe="twoway",
        n_estimators=n_estimators,
        random_state=seed,
        **kw,
    )


@pytest.fixture(scope="module")
def panel():
    return _panel()


@pytest.fixture(scope="module")
def forest(panel):
    return _fe(panel)


# --------------------------------------------------------------------------- #
#  Identities with the imputation estimator
# --------------------------------------------------------------------------- #


def test_att_equals_did_imputation_on_mpdta():
    df = sp.datasets.mpdta()
    df["D"] = ((df.first_treat > 0) & (df.year >= df.first_treat)).astype(float)
    df["base"] = df.groupby("countyreal").lemp.transform("first")
    cf = sp.causal_forest(
        data=df,
        y="lemp",
        d="D",
        x=["base"],
        id="countyreal",
        time="year",
        fe="twoway",
        n_estimators=200,
        random_state=1,
    )
    ref = sp.did_imputation(
        df,
        y="lemp",
        group="countyreal",
        time="year",
        first_treat="first_treat",
        cluster="countyreal",
    )
    got = cf.average_treatment_effect("treated", variance="bjs")
    # Same estimator, same linear weights: agreement to round-off.
    assert got["estimate"] == pytest.approx(ref.estimate, rel=1e-10, abs=1e-12)
    assert got["se"] == pytest.approx(ref.se, rel=1e-9)
    assert got["estimand"] == "ATT" and got["method"] == "imputation"
    # The time-invariant covariate is absorbed by the unit effect.
    assert got["imputation_covariates"] == []


def test_att_equals_did_imputation_unbalanced():
    df = _panel(seed=3, drop=0.1)
    # The forest only sees D, so a unit's cohort is its first *observed*
    # treated period; align the reference's first_treat with that (it
    # differs where the onset row was dropped, which moves the BJS block
    # centring of the variance but not the estimate).
    obs_first = df[df.d == 1].groupby("id").t.min()
    df["first_obs"] = df["id"].map(obs_first).fillna(0).astype(int)
    cf = _fe(df, n_estimators=200)
    ref = sp.did_imputation(
        df, y="y", group="id", time="t", first_treat="first_obs", cluster="id"
    )
    got = cf.average_treatment_effect("treated", variance="bjs", covariates="none")
    assert got["estimate"] == pytest.approx(ref.estimate, rel=1e-9)
    assert got["se"] == pytest.approx(ref.se, rel=1e-8)


def test_functional_weights_are_imputation_weights(forest, panel):
    D = fi.imputation_design(forest)
    w = np.where(D.target, 1.0, 0.0)
    w /= w.sum()
    v = fi.functional_weights(D, w)[:, 0]
    # v'y is the mean imputed effect ...
    assert v @ D.y == pytest.approx(np.nanmean(D.gamma[D.target]), abs=1e-12)
    # ... and v annihilates any unit + period (Y(0)) pattern.
    Z0 = D.Z.toarray()
    np.testing.assert_allclose(Z0.T @ v, 0.0, atol=1e-10)


# --------------------------------------------------------------------------- #
#  Linear functionals
# --------------------------------------------------------------------------- #


def test_group_estimates_are_group_means_of_scores(forest, panel):
    D = fi.imputation_design(forest)
    by = (panel["x1"] > 0).to_numpy()
    tab = sp.forest_group_effects(forest, by=by)
    g = pd.Series(D.gamma[D.target]).groupby(by[D.target]).mean()
    np.testing.assert_allclose(tab["estimate"].to_numpy(), g.to_numpy(), atol=1e-12)
    assert tab["n_rows"].sum() == D.target.sum()
    assert tab.attrs["estimand"].startswith("ATT")
    tests = tab.attrs["tests"]
    assert tests["equality_df"] == 1
    assert np.isfinite(tests["last_minus_first"]["se"])


def test_blp_matches_ols_of_scores(forest, panel):
    D = fi.imputation_design(forest)
    blp = forest.best_linear_projection()
    A = np.column_stack(
        [np.ones(D.target.sum()), panel.loc[D.target, ["x1", "x2"]].to_numpy()]
    )
    beta = np.linalg.lstsq(A, D.gamma[D.target], rcond=None)[0]
    np.testing.assert_allclose(blp["coef"].to_numpy(), beta, atol=1e-10)
    assert list(blp.index) == ["Intercept", "x1", "x2"]
    assert list(blp.columns) == ["coef", "se", "t", "p", "ci_lower", "ci_upper"]


def test_calibration_matches_ols_and_detects_heterogeneity(forest):
    D = fi.imputation_design(forest)
    tab = sp.calibration_test(forest)
    tau = forest._oob_tau[D.target]
    tb = tau.mean()
    A = np.column_stack([np.full(tau.size, tb), tau - tb])
    beta = np.linalg.lstsq(A, D.gamma[D.target], rcond=None)[0]
    np.testing.assert_allclose(tab["coef"].to_numpy(), beta, atol=1e-10)
    assert tab.loc["differential_forest_prediction", "p_one_sided"] < 0.01
    within = sp.calibration_test(forest, method="within")
    assert not np.allclose(within["coef"].to_numpy(), tab["coef"].to_numpy())


def test_calibrate_cate_uses_imputation(forest):
    with warnings.catch_warnings():
        warnings.simplefilter("error", AssumptionWarning)
        cal = sp.calibrate_cate(forest)
    assert cal["method"] == "blp_imputation"
    D = fi.imputation_design(forest)
    # beta_mean * mean prediction on treated cells is the imputation ATT.
    att = forest.average_treatment_effect("treated")["estimate"]
    assert cal["beta_mean"] * cal["mean_oob_prediction"] == pytest.approx(
        att, rel=1e-10
    )
    assert cal["cate"].shape == D.y.shape


def test_cate_quantile_groups_sorted(forest):
    tab = sp.forest_group_effects(forest, by="cate_quantile", n_groups=4)
    assert list(tab.index) == ["Q1", "Q2", "Q3", "Q4"]
    assert np.all(np.diff(tab["forest_mean"].to_numpy()) > 0)
    assert tab.loc["Q4", "estimate"] > tab.loc["Q1", "estimate"]
    assert tab.attrs["tests"]["equality_p"] < 0.05


# --------------------------------------------------------------------------- #
#  Dyadic data
# --------------------------------------------------------------------------- #


def test_dyadic_vcov_equals_pairwise_definition():
    rng = np.random.default_rng(0)
    n_nodes, n = 12, 300
    ci = rng.integers(0, n_nodes, n)
    cj = (ci + rng.integers(1, n_nodes, n)) % n_nodes
    S = rng.standard_normal((n, 2))
    share = (
        (ci[:, None] == ci[None, :])
        | (ci[:, None] == cj[None, :])
        | (cj[:, None] == ci[None, :])
        | (cj[:, None] == cj[None, :])
    )
    brute = S.T @ share @ S
    np.testing.assert_allclose(
        fi.vcov_from_scores(S, None, (ci, cj)), brute, rtol=1e-12
    )


def test_dyadic_vcov_matches_dyadic_regression():
    rng = np.random.default_rng(1)
    n_nodes, n = 25, 400
    i = rng.integers(0, n_nodes, n)
    j = (i + rng.integers(1, n_nodes, n)) % n_nodes
    y = rng.standard_normal(n) + 0.3 * (i % 3)
    ref = sp.dyadic_regression(
        pd.DataFrame({"y": y, "i": i, "j": j}), y="y", covariates=[], i="i", j="j"
    )
    S = ((y - y.mean()) / n)[:, None]
    V = fi.vcov_from_scores(S, None, (i, j))
    assert np.sqrt(V[0, 0]) == pytest.approx(
        float(ref.coefficients["se_dyadic"].iloc[0]), rel=1e-12
    )


def test_membership_groups_on_currency_union():
    df = sp.datasets.currency_union_panel(seed=0)
    cf = sp.causal_forest(
        data=df,
        y="log_trade",
        d="euro",
        x=["pre_trade", "log_gdp_prod", "log_gdppc"],
        id="pair",
        time="year",
        fe="twoway",
        n_estimators=300,
        random_state=0,
    )
    members = df[["country_i", "country_j"]].to_numpy()
    tab = sp.forest_group_effects(cf, members=members, scale="percent")
    D = fi.imputation_design(cf)
    c01 = D.target & ((df.country_i == "C01") | (df.country_j == "C01")).to_numpy()
    # log_trade is ~22, so the sparse solve's round-off is ~1e-11 absolute.
    assert tab.loc["C01", "estimate"] == pytest.approx(D.gamma[c01].mean(), rel=1e-9)
    assert tab.loc["C01", "n_rows"] == int(c01.sum())
    # Non-adopters have no treated cells and so no group.
    assert "C13" not in tab.index
    assert tab.loc["C01", "estimate_pct"] == pytest.approx(
        100 * np.expm1(tab.loc["C01", "estimate"])
    )
    with pytest.warns(AssumptionWarning, match="members"):
        dy = sp.forest_group_effects(cf, members=members, cluster="dyadic")
    # Non-positive dyadic variances are NaN, never a zero-width interval.
    assert not np.any(dy["se"].to_numpy() == 0)
    with pytest.raises(MethodIncompatibility, match="members"):
        sp.forest_group_effects(cf, cluster="dyadic")


# --------------------------------------------------------------------------- #
#  Known truth on the simulated currency union
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("late", [False, True])
def test_currency_union_att_recovers_truth(late):
    df = sp.datasets.currency_union_panel(seed=0, late_adopters=late)
    cf = sp.causal_forest(
        data=df,
        y="log_trade",
        d="euro",
        x=["pre_trade", "log_gdp_prod", "log_gdppc"],
        id="pair",
        time="year",
        fe="twoway",
        n_estimators=300,
        random_state=0,
    )
    res = cf.average_treatment_effect("treated", covariates="auto")
    truth = df.attrs["true_att"]
    assert abs(res["estimate"] - truth) < 2 * res["se"]
    # GDP varies within pairs and enters Y(0): 'auto' keeps it.
    assert "log_gdp_prod" in res["imputation_covariates"]
    assert "pre_trade" not in res["imputation_covariates"]
    # Without it (the did_imputation default) the untreated model is
    # misspecified by pair-specific GDP trends.
    bad = cf.average_treatment_effect("treated")
    assert bad["imputation_covariates"] == []
    assert abs(bad["estimate"] - truth) > abs(res["estimate"] - truth)
    named = cf.average_treatment_effect("treated", covariates=["log_gdp_prod"])
    assert named["imputation_covariates"] == ["log_gdp_prod"]


# --------------------------------------------------------------------------- #
#  Contracts and failure modes
# --------------------------------------------------------------------------- #


def test_target_other_than_treated_raises(forest):
    with pytest.raises(MethodIncompatibility, match="not identified"):
        forest.average_treatment_effect("all")
    with pytest.raises(MethodIncompatibility):
        forest.average_treatment_effect("control")


def test_positional_target_and_scalar_att(forest):
    a = forest.average_treatment_effect("treated")
    b = forest.average_treatment_effect(target_sample="treated")
    assert a["estimate"] == b["estimate"]
    att = forest.att()
    assert float(att) == pytest.approx(a["estimate"])
    assert att.ci[0] < float(att) < att.ci[1]
    with pytest.raises(MethodIncompatibility, match="string first argument"):
        forest.average_treatment_effect("treated", target_sample="control")


def test_variance_options(forest):
    a = forest.average_treatment_effect("treated", variance="forest")
    b = forest.average_treatment_effect("treated", variance="bjs")
    assert a["estimate"] == b["estimate"]
    assert a["se"] > 0 and b["se"] > 0 and a["se"] != b["se"]
    with pytest.raises(MethodIncompatibility, match="variance"):
        forest.average_treatment_effect("treated", variance="hc1")


def test_always_treated_units_are_excluded_with_warning():
    df = _panel(seed=5)
    df.loc[df.id < 5, "d"] = 1.0
    cf = _fe(df, n_estimators=150)
    with pytest.warns(AssumptionWarning, match="cannot be imputed"):
        res = cf.average_treatment_effect("treated")
    assert res["n_not_imputable"] == 5 * 7


def test_continuous_treatment_is_refused():
    df = _panel(seed=6)
    df["d"] = df["d"] * np.random.default_rng(0).uniform(0.5, 1.5, len(df))
    cf = _fe(df, n_estimators=150, discrete_treatment=False)
    with pytest.raises(MethodIncompatibility, match="binary"):
        cf.average_treatment_effect("treated")
    # Calibration falls back to the within regression for a continuous D.
    tab = sp.calibration_test(cf)
    assert tab.attrs["method"].startswith("BLP calibration on out-of-bag")
    with pytest.raises(MethodIncompatibility, match="binary"):
        sp.calibration_test(cf, method="imputation")


def test_group_inputs_validated(forest, panel):
    with pytest.raises(MethodIncompatibility, match="one label per"):
        sp.forest_group_effects(forest, by=np.zeros(3))
    with pytest.raises(MethodIncompatibility, match="scale"):
        sp.forest_group_effects(forest, scale="log")
    with pytest.raises(MethodIncompatibility, match=r"\(n, 2\)"):
        sp.forest_group_effects(forest, members=np.zeros((len(panel), 3)))
    with pytest.raises(DataInsufficient):
        sp.forest_group_effects(forest, by=panel["id"].to_numpy(), min_rows=10_000)


def test_pooled_forest_group_effects_use_aipw_scores():
    rng = np.random.default_rng(0)
    n = 1500
    X = rng.standard_normal((n, 2))
    T = rng.binomial(1, 0.5, n)
    Y = X[:, 1] + (1 + X[:, 0]) * T + rng.standard_normal(n)
    df = pd.DataFrame({"y": Y, "d": T, "x1": X[:, 0], "x2": X[:, 1]})
    cf = sp.causal_forest(
        data=df, y="y", d="d", x=["x1", "x2"], n_estimators=400, random_state=0
    )
    one = sp.forest_group_effects(cf)
    ate = cf.average_treatment_effect("all")
    assert one.loc["all", "estimate"] == pytest.approx(ate["estimate"], rel=1e-10)
    assert one.loc["all", "se"] == pytest.approx(ate["se"], rel=1e-10)
    assert one.attrs["estimand"].startswith("ATE")
    grp = sp.forest_group_effects(cf, by=(df.x1 > 0).to_numpy())
    assert grp.loc[True, "estimate"] > grp.loc[False, "estimate"]
    with pytest.raises(MethodIncompatibility, match="fixed effects"):
        sp.cate_pretrend_test(cf)


def test_column_interface_keeps_feature_names(forest, panel):
    assert forest._feature_names == ["x1", "x2"]
    np.testing.assert_allclose(
        forest.effect(panel[["x2", "x1"]]),
        forest.effect(panel[["x1", "x2"]].to_numpy()),
    )


# --------------------------------------------------------------------------- #
#  Support of counterfactual predictions
# --------------------------------------------------------------------------- #


def test_forest_support_flags_extrapolation(forest, panel):
    new = pd.DataFrame({"x1": [0.0, 0.2, 8.0], "x2": [0.0, -0.1, 0.0]})
    sup = sp.forest_support(forest, new)
    assert list(sup["supported"]) == [True, True, False]
    assert sup.loc[2, "n_outside_range"] == 1
    assert sup.loc[2, "knn_ratio"] > 1
    assert np.all(sup["ci_low"] <= sup["cate"]) and np.all(
        sup["cate"] <= sup["ci_high"]
    )
    s = sup.attrs["summary"]
    assert s["reference"] == "rows of units whose treatment varies"
    assert 0 < s["share_supported"] < 1
    with pytest.raises(MethodIncompatibility):
        sp.forest_support(forest, new, k=0)


# --------------------------------------------------------------------------- #
#  Pre-trends by predicted-effect group
# --------------------------------------------------------------------------- #


def _lead_ols(df, rows, lead_cols):
    """Dummy-variable OLS with CR1 (fixest 'nested') for cross-checking."""
    sub = df.loc[rows]
    U = pd.get_dummies(sub["id"]).to_numpy(float)
    Tm = pd.get_dummies(sub["t"]).to_numpy(float)[:, 1:]
    L = np.column_stack(lead_cols)
    X = np.column_stack([L, U, Tm])
    y = sub["y"].to_numpy()
    XtX_inv = np.linalg.pinv(X.T @ X)
    b = XtX_inv @ X.T @ y
    e = y - X @ b
    cl = sub["id"].to_numpy()
    G = len(np.unique(cl))
    scores = pd.DataFrame(X * e[:, None]).groupby(cl).sum().to_numpy()
    V = XtX_inv @ scores.T @ scores @ XtX_inv
    k = L.shape[1] + Tm.shape[1]
    n = len(y)
    V *= G / (G - 1) * (n - 1) / (n - k)
    return b[: L.shape[1]], np.sqrt(np.diag(V)[: L.shape[1]])


def test_pretrend_regression_matches_dummy_ols(forest, panel):
    groups = np.where(panel["x1"] > 0, "hi", "lo")
    res = sp.cate_pretrend_test(forest, groups=groups, leads=2, covariates="none")
    rows = panel["d"] == 0
    rel = np.where(panel.first_treat > 0, panel.t - panel.first_treat, 0)
    cols, keys = [], []
    for g in ["hi", "lo"]:
        for k in (1, 2):
            c = ((groups == g) & (panel.first_treat > 0) & (rel == -k)).astype(float)
            cols.append(c[rows.to_numpy()])
            keys.append((g, -k))
    b, se = _lead_ols(panel, rows, cols)
    coef = res["coefficients"].loc[keys]
    np.testing.assert_allclose(coef["coef"].to_numpy(), b, atol=1e-8)
    np.testing.assert_allclose(coef["se"].to_numpy(), se, rtol=1e-6)


def test_pretrend_test_detects_group_specific_pretrend():
    clean = _pretrend_p(pretrend=0.0)
    dirty = _pretrend_p(pretrend=0.6)
    assert clean > 0.05
    assert dirty < 0.01


def _pretrend_p(pretrend):
    df = _panel(N=400, seed=11, pretrend=pretrend)
    cf = _fe(df, n_estimators=300)
    res = sp.cate_pretrend_test(cf, n_groups=2, leads=2)
    assert set(res["coefficients"].index.get_level_values("group")) == {"Q1", "Q2"}
    return res["equal_across_groups"]["p"]


def test_pretrend_input_contracts(forest, panel):
    with pytest.raises(DataInsufficient, match="leads"):
        sp.cate_pretrend_test(forest, leads=50)
    with pytest.raises(MethodIncompatibility, match="constant within units"):
        sp.cate_pretrend_test(forest, groups=np.arange(len(panel)) % 2)
    with pytest.raises(MethodIncompatibility, match="time_effects"):
        sp.cate_pretrend_test(forest, time_effects="none")
    by_group = sp.cate_pretrend_test(forest, leads=2, time_effects="by_group")
    assert by_group["time_effects"] == "by_group"


# --------------------------------------------------------------------------- #
#  Regression tests for review findings
# --------------------------------------------------------------------------- #


def test_array_controls_are_cached_by_content(forest, panel):
    rng = np.random.default_rng(0)
    seen = {}
    for _ in range(6):
        C = rng.standard_normal((len(panel), 1))
        est = forest.average_treatment_effect("treated", covariates=C)["estimate"]
        fresh = fi.imputation_design(_fe(panel, n_estimators=50), covariates=C)
        ref = np.nanmean(fresh.gamma[fresh.target])
        assert est == pytest.approx(ref, rel=1e-10)
        seen[est] = True
    assert len(seen) == 6


def test_unit_fe_forest_refuses_imputation_and_calibrates_within():
    df = _panel(seed=4)
    cf = sp.causal_forest(
        data=df,
        y="y",
        d="d",
        x=["x1", "x2"],
        id="id",
        fe="unit",
        n_estimators=150,
        random_state=0,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error", AssumptionWarning)
        with pytest.raises(MethodIncompatibility, match="fe='twoway'"):
            cf.average_treatment_effect("treated")
    with pytest.raises(MethodIncompatibility, match="fe='twoway'"):
        sp.cate_pretrend_test(cf)
    tab = sp.calibration_test(cf)  # 'auto' falls back to the within regression
    assert tab.attrs["method"].startswith("BLP calibration on out-of-bag")


def test_pretrend_default_leads_on_short_panel():
    df = _panel(N=300, T=6, seed=8)
    cf = _fe(df, n_estimators=200)
    res = sp.cate_pretrend_test(cf)
    # Longest observed untreated spell before adoption (cohort 6 lies
    # beyond T = 6, so those units are never treated in the sample).
    first = df[df.d == 1].groupby("id").t.min()
    max_leads = int(first.max())
    assert res["leads"] == min(4, max_leads - 1)
    # The review's reproduction: the panel of test_panel_causal_forest (T=6)
    # raised "collinear" with the old default.
    from tests.test_panel_causal_forest import _fe_forest
    from tests.test_panel_causal_forest import _panel as _panel6

    out = sp.cate_pretrend_test(_fe_forest(_panel6(seed=1), n_estimators=200))
    assert np.isfinite(out["equal_across_groups"]["p"])


def test_pretrend_by_group_dof():
    df = _panel(N=300, seed=9)
    cf = _fe(df, n_estimators=200)
    common = sp.cate_pretrend_test(cf, leads=2)
    by = sp.cate_pretrend_test(cf, leads=2, time_effects="by_group")
    assert by["n_obs"] == common["n_obs"]
    assert np.all(np.isfinite(by["coefficients"]["se"]))


def test_forest_support_benchmark_excludes_own_unit():
    df = sp.datasets.currency_union_panel(seed=0)
    x = ["pre_trade", "log_gdp_prod", "log_gdppc"]
    cf = sp.causal_forest(
        data=df,
        y="log_trade",
        d="euro",
        x=x,
        id="pair",
        time="year",
        fe="twoway",
        n_estimators=200,
        random_state=0,
    )
    # A switching pair's own rows, presented as new data, are supported:
    # the benchmark compares against other units, like a new unit would be.
    own = df[(df.ever_euro == 1) & (df.year == 2005)][x]
    assert sp.forest_support(cf, own)["supported"].mean() > 0.8
    # Time-invariant modifiers with T > k no longer give a zero cutoff.
    cf2 = sp.causal_forest(
        data=df,
        y="log_trade",
        d="euro",
        x=["pre_trade"],
        id="pair",
        time="year",
        fe="twoway",
        n_estimators=100,
        random_state=0,
    )
    sup = sp.forest_support(cf2, df[["pre_trade"]].iloc[:5])
    assert sup.attrs["summary"]["knn_cutoff"] > 0


def test_bjs_variance_does_not_need_oob(forest):
    saved = forest._oob_tau.copy()
    try:
        forest._oob_tau = saved.copy()
        forest._oob_tau[np.flatnonzero(forest._T_original == 1)[:3]] = np.nan
        res = forest.average_treatment_effect("treated", variance="bjs")
        assert np.isfinite(res["se"]) and np.isnan(res["forest_plug_in"])
        with pytest.raises(DataInsufficient, match="out-of-bag"):
            forest.average_treatment_effect("treated", variance="forest")
    finally:
        forest._oob_tau = saved


# --------------------------------------------------------------------------- #
#  The Kattenberg / causalfe splitting rule
# --------------------------------------------------------------------------- #


def test_cffe_split_rule_recovers_effects(panel):
    cf = _fe(panel, split_rule="cffe", min_samples_leaf=20, max_depth=4)
    tr = panel["d"].to_numpy() == 1
    tau = panel["tau"].to_numpy()
    assert cf.diagnostics["split_rule"] == "cffe"
    assert np.corrcoef(cf.predict()[tr], tau[tr])[0, 1] > 0.7
    att = cf.average_treatment_effect("treated")
    assert abs(att["estimate"] - tau[tr].mean()) < 3 * att["se"]
    # The rule changes the partition, not the estimator downstream: the
    # imputation ATT does not depend on the forest at all.
    grf = _fe(panel, min_samples_leaf=20, max_depth=4)
    assert att["estimate"] == pytest.approx(
        grf.average_treatment_effect("treated")["estimate"], rel=1e-12
    )
    assert not np.allclose(cf.predict(), grf.predict())


def test_cffe_split_rule_warns_on_deep_default_trees(panel):
    with pytest.warns(AssumptionWarning, match="tau-heterogeneity criterion"):
        _fe(panel, split_rule="cffe", n_estimators=100)
    with warnings.catch_warnings():
        warnings.simplefilter("error", AssumptionWarning)
        _fe(
            panel, split_rule="cffe", n_estimators=100, min_samples_leaf=20, max_depth=4
        )


def test_cffe_split_rule_requires_fixed_effects(panel):
    with pytest.raises(MethodIncompatibility, match="cffe"):
        sp.causal_forest(
            data=panel,
            y="y",
            d="d",
            x=["x1", "x2"],
            split_rule="cffe",
            n_estimators=50,
            random_state=0,
        )
    with pytest.raises(MethodIncompatibility, match="split_rule"):
        _fe(panel, split_rule="tau-heterogeneity", n_estimators=50)


def test_cffe_split_criterion_matches_its_definition():
    """The engine's split score is nL nR / n^2 (tauL - tauR)^2."""
    from statspai.forest import _grf_engine as engine

    rng = np.random.default_rng(0)
    m, p = 200, 2
    X = rng.standard_normal((m, p))
    Wr = rng.standard_normal(m)
    Yr = (1 + (X[:, 0] > 0)) * Wr + 0.1 * rng.standard_normal(m)
    idx = np.arange(m, dtype=np.int64)
    G = np.ones(m)
    found, var, val = engine._split_tau_heterogeneity(
        X, idx, Yr, Wr, G, np.arange(p), 20, 0.0, 0.0
    )
    assert found and var == 0

    def score(mask):
        nl, nr = int(mask.sum()), int((~mask).sum())
        tl = (Wr[mask] * Yr[mask]).sum() / (Wr[mask] ** 2).sum()
        tr_ = (Wr[~mask] * Yr[~mask]).sum() / (Wr[~mask] ** 2).sum()
        return nl * nr / m**2 * (tl - tr_) ** 2

    best = score(X[:, var] <= val)
    grid = np.unique(X[:, var])
    for thr in grid[10:-10]:
        assert score(X[:, var] <= thr) <= best + 1e-12

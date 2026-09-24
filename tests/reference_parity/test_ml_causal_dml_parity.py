"""Reference parity: sp.dml_panel and sp.dml_model_averaging, learners and folds shared.

Fixtures
--------
* ``_fixtures/ml_causal_panel_R.json`` -- ``_generate_ml_causal_panel_R.R``
  (R 4.5.2, fixest 0.14.0, ddml 0.3.1, sandwich 3.1.1): ``fixest::demean``
  one- and two-way residuals on a balanced (60 x 6) and an unbalanced
  (323-row) panel; ``ddml::ddml_plm`` with an OLS learner and unit
  clustering; ``ddml`` short-stacking (``ensemble_type = "nnls1"``) over
  three OLS candidates.
* ``_fixtures/ml_causal_doubleml.json`` -- ``_generate_ml_causal_doubleml.py``
  (Python DoubleML 0.11.3, scikit-learn 1.6.1): ``DoubleMLPLR`` on the
  fixest-demeaned data with ``LinearRegression`` learners, the committed
  unit-level folds and one-way unit clustering. R DoubleML 1.0.2 rejects
  external sample splits with clustered data, hence the Python package.

With OLS learners and a shared fold column (``fold``, 12 units per fold)
nothing is random, so:

* the within transform is pinned to fixest at 1e-10 (abs, data O(1));
* ``sp.dml_panel`` estimate and cluster SE are pinned to DoubleML at 1e-10
  rel. DoubleML's one-way cluster variance weights each fold by
  ``1/|I_k|``; with equal cluster counts per fold it equals
  ``sum_g S_g^2 / (sum psi_a)^2``, StatsPAI's formula (asserted exactly).
* ``ddml`` is a documented convention difference (class 3): it regresses
  ``y_r`` on ``d_r`` WITH an intercept and reports ``sandwich::vcovCL``
  (CR1: ``G/(G-1) * (n-1)/(n-k)``). Its SE equals StatsPAI's times the
  CR1 factor at 1e-10 (the intercept is inert on this fixture).
* short-stacking weights are pinned to ddml's ``nnls1`` QP at 1e-10;
  ddml's with-intercept HC1 slope/SE are rebuilt from StatsPAI's stacked
  residuals at 1e-10.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd
import pytest

import statspai as sp

_FIX = pathlib.Path(__file__).parent / "_fixtures"
REL = 1e-10


@pytest.fixture(scope="module")
def rref():
    return json.loads((_FIX / "ml_causal_panel_R.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def dref():
    return json.loads((_FIX / "ml_causal_doubleml.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def bal():
    return pd.read_csv(_FIX / "ml_causal_panel.csv")


@pytest.fixture(scope="module")
def unb():
    return pd.read_csv(_FIX / "ml_causal_panel_unbal.csv")


def _within():
    import sys

    sp.dml_panel  # noqa: B018  (materialise the lazy module)
    return sys.modules["statspai.dml.panel_dml"]._within_transform


@pytest.mark.parametrize(
    "key,which,twoway",
    [
        ("balanced_unit", "bal", False),
        ("balanced_twoway", "bal", True),
        ("unbal_unit", "unb", False),
        ("unbal_twoway", "unb", True),
    ],
)
def test_within_transform_matches_fixest(rref, bal, unb, key, which, twoway):
    df = bal if which == "bal" else unb
    wt = _within()
    for v in ("y", "d", "x1", "x2", "x3"):
        got = wt(
            df[v].to_numpy(),
            df["unit"].to_numpy(),
            df["time"].to_numpy() if twoway else None,
        )
        np.testing.assert_allclose(got, rref["demeaned"][key][v], rtol=0, atol=1e-10)


def test_unbalanced_twoway_is_a_projection(unb):
    """Identity: the two-way residual is orthogonal to unit and time dummies."""
    wt = _within()
    r = wt(unb["y"].to_numpy(), unb["unit"].to_numpy(), unb["time"].to_numpy())
    for g in ("unit", "time"):
        means = pd.Series(r).groupby(unb[g].to_numpy()).mean().to_numpy()
        assert np.max(np.abs(means)) < 1e-11


def _panel(df, twoway, **kw):
    return sp.dml_panel(
        df,
        y="y",
        treat="d",
        covariates=["x1", "x2", "x3"],
        unit="unit",
        time="time",
        include_time_fe=twoway,
        ml_g="linear",
        ml_m="linear",
        fold_indices="fold",
        **kw,
    )


@pytest.mark.parametrize(
    "key,which,twoway",
    [
        ("balanced_unit", "bal", False),
        ("balanced_twoway", "bal", True),
        ("unbal_twoway", "unb", True),
    ],
)
def test_dml_panel_matches_doubleml(dref, bal, unb, key, which, twoway):
    res = _panel(bal if which == "bal" else unb, twoway)
    assert res.estimate == pytest.approx(dref[key]["coef"], rel=REL)
    assert res.se == pytest.approx(dref[key]["se"], rel=REL)


def test_dml_panel_ddml_convention_rebuilt(rref, unb):
    """ddml: OLS of y_r on d_r with intercept, vcovCL (CR1), same folds.

    On this fixture the intercept is numerically inert (observed slope
    ratio 1 - 6e-16), so ddml's SE is StatsPAI's times the CR1 factor
    ``sqrt(G/(G-1) (n-1)/(n-2))`` -- observed to 1e-15.
    """
    res = _panel(unb, True)
    ref = rref["ddml_panel"]
    assert res.estimate == pytest.approx(ref["coef"], rel=REL)
    G, n, k = ref["n_clusters"], res.n_obs, 2
    cr1 = np.sqrt(G / (G - 1) * (n - 1) / (n - k))
    assert ref["se"] / res.se == pytest.approx(cr1, rel=REL)


def test_dml_panel_folds_must_be_unit_level(bal):
    bad = bal["fold"].to_numpy().copy()
    bad[0] = (bad[0] + 1) % 5
    with pytest.raises(Exception, match="constant within unit"):
        sp.dml_panel(
            bal,
            y="y",
            treat="d",
            covariates=["x1"],
            unit="unit",
            ml_g="linear",
            ml_m="linear",
            fold_indices=bad,
        )


# ------------------------------------------------------ model averaging
def _ols(cols):
    from sklearn.compose import ColumnTransformer
    from sklearn.linear_model import LinearRegression
    from sklearn.pipeline import make_pipeline

    return make_pipeline(
        ColumnTransformer([("s", "passthrough", cols)]), LinearRegression()
    )


@pytest.fixture(scope="module")
def stack_fit(bal):
    df = bal.copy()
    for c in ("x1", "x2", "x3"):
        df[c + "sq"] = df[c] ** 2
    cov = ["x1", "x2", "x3", "x1sq", "x2sq", "x3sq"]
    cands = [
        (_ols([0, 1, 2]), _ols([0, 1, 2]), "lin"),
        (_ols([0]), _ols([0]), "x1"),
        (_ols(list(range(6))), _ols(list(range(6))), "quad"),
    ]
    return sp.dml_model_averaging(
        df, y="y", treat="d", covariates=cov, candidates=cands, fold_indices="fold"
    )


def test_short_stacking_weights_match_ddml_nnls1(rref, stack_fit):
    ref = rref["shortstack"]
    wg = list(stack_fit.model_info["weights_g"].values())
    wm = list(stack_fit.model_info["weights_m"].values())
    np.testing.assert_allclose(wg, ref["weights_y"], rtol=REL, atol=1e-12)
    np.testing.assert_allclose(wm, ref["weights_d"], rtol=REL, atol=1e-12)


def test_model_averaging_dml_is_the_same_callable(rref, bal):
    """Alias proof: ``sp.model_averaging_dml`` is ``sp.dml_model_averaging``
    (same function object), and called under its own name on the committed
    bytes it reproduces the ddml short-stacking weights."""
    assert sp.model_averaging_dml is sp.dml_model_averaging
    df = bal.copy()
    for c in ("x1", "x2", "x3"):
        df[c + "sq"] = df[c] ** 2
    cov = ["x1", "x2", "x3", "x1sq", "x2sq", "x3sq"]
    cands = [
        (_ols([0, 1, 2]), _ols([0, 1, 2]), "lin"),
        (_ols([0]), _ols([0]), "x1"),
        (_ols(list(range(6))), _ols(list(range(6))), "quad"),
    ]
    fit = sp.model_averaging_dml(
        df, y="y", treat="d", covariates=cov, candidates=cands, fold_indices="fold"
    )
    ref = rref["shortstack"]
    np.testing.assert_allclose(
        list(fit.model_info["weights_g"].values()),
        ref["weights_y"],
        rtol=REL,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        list(fit.model_info["weights_m"].values()),
        ref["weights_d"],
        rtol=REL,
        atol=1e-12,
    )


def test_short_stacking_estimate_is_plr_on_stacked_residuals(stack_fit):
    yr = stack_fit.model_info["_y_resid"]
    dr = stack_fit.model_info["_d_resid"]
    assert stack_fit.estimate == pytest.approx(
        np.sum(yr * dr) / np.sum(dr * dr), rel=1e-13
    )
    psi = (yr - stack_fit.estimate * dr) * dr
    se = np.sqrt(np.mean(psi**2) / np.mean(dr**2) ** 2 / len(yr))
    assert stack_fit.se == pytest.approx(se, rel=1e-12)


def test_short_stacking_ddml_convention_rebuilt(rref, stack_fit):
    """ddml: lm(y_r ~ d_r) with intercept, HC1 -- rebuilt from our residuals."""
    ref = rref["shortstack"]
    yr = stack_fit.model_info["_y_resid"]
    dr = stack_fit.model_info["_d_resid"]
    X = np.column_stack([np.ones_like(dr), dr])
    XtX_inv = np.linalg.inv(X.T @ X)
    b = XtX_inv @ X.T @ yr
    e = yr - X @ b
    n = len(yr)
    V = XtX_inv @ ((X * e[:, None] ** 2).T @ X) @ XtX_inv * n / (n - 2)
    assert b[1] == pytest.approx(ref["coef"], rel=REL)
    assert np.sqrt(V[1, 1]) == pytest.approx(ref["se_HC1"], rel=REL)


def test_cls_exact_solution_satisfies_kkt():
    """Identity: optimum of min||y - Fw|| s.t. w>=0, sum w=1 satisfies KKT."""
    import sys

    sp.dml_model_averaging  # noqa: B018
    mod = sys.modules["statspai.dml.model_averaging"]
    rng = np.random.default_rng(2)
    F = rng.normal(size=(200, 5))
    y = F @ np.array([0.6, 0.4, 0.0, 0.0, 0.0]) + rng.normal(size=200)
    w = mod._solve_cls_weights(y, F)
    g = -2 * F.T @ (y - F @ w)
    lam = np.mean(g[w > 1e-12])
    assert np.all(np.abs(g[w > 1e-12] - lam) < 1e-8)
    assert np.all(g[w <= 1e-12] >= lam - 1e-8)
    assert w.sum() == pytest.approx(1.0, abs=1e-14)


# ------------------------------------------------------------ dml_diagnostics
def test_dml_diagnostics_balance_table_uses_the_stored_residuals(bal):
    """Identity: the balance table correlates each covariate with the fitted
    treatment residual the estimator stored (the diagnostics' score report
    follows the upstream design; see dml/_diagnostics.py)."""
    fit = sp.dml(
        bal,
        y="y",
        treat="d",
        covariates=["x1", "x2", "x3"],
        model="plr",
        ml_g="linear",
        ml_m="linear",
        fold_indices="fold",
    )
    diag = sp.dml_diagnostics(fit)
    dr = np.asarray(fit.model_info["_d_resid"])
    x1 = bal["x1"].to_numpy()
    row = diag.balance_table.set_index("variable").loc["x1"]
    assert row["corr_d_resid"] == pytest.approx(np.corrcoef(x1, dr)[0, 1], rel=1e-12)

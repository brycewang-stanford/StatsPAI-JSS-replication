"""Reference parity: distributional decompositions and IV-QTE vs Stata.

Fixture: ``_fixtures/decomp_qte_Stata.json`` written by
``_fixtures/_generate_decomp_qte_stata.do`` (Stata 18 MP) from the CSVs of
``_fixtures/_generate_decomp_qte_data.py``. Packages: Chernozhukov,
Fernandez-Val & Melly's ``cdeco`` (bmelly/Stata ``counterfactual``) with
``qrprocess`` / ``drprocess``; Froelich & Melly's ``ivqte``; Jann's
``fairlie``; ``shapley2`` + ``ineqdeco``; Liu & Emsley's ``paramed``.

Conventions each number depends on (see the do-file header for detail)
----------------------------------------------------------------------
* ``melly_decompose`` vs ``cdeco, method(qr) nreg(100)``: 100 exact QR fits
  at (j-0.5)/100 (Stata's simplex ``method(qreg)``), pooled predictions
  inverted with the averaged inverse CDF (``mm_quantile`` definition 2).
  Evaluated at offset quantiles (0.10003, ...) so tau*N is never an
  integer: at an exact tie definition 2's averaging depends on the last
  bit of Stata's running weight sum. Tolerance rel 1e-10 (observed ~6e-16).
* ``cfm_decompose(thresholds=1.5:0.05:3.4, inversion='step')`` vs
  ``cdeco, method(logit)``: CDFs at the thresholds agree to 2.4e-10 abs --
  Stata's ``logit`` stops at its default tolerance; ours is the converged
  MLE. Tolerance 1e-8 abs on CDFs; quantiles (a step inverse over a 0.05
  grid) asserted equal to 1e-12.
* ``fairlie`` vs Stata ``fairlie``: 500/500 groups, so no random subsample
  and the matching is deterministic. ``_tight`` runs converge Stata's
  logit/probit to 1e-14: contributions and SEs agree to 1e-12 rel. At
  Stata's default tolerance contributions agree to 2e-10 and SEs to 2e-6
  (asserted separately at 1e-5, the default-tolerance gap).
* ``shapley_inequality`` vs ``shapley2`` over ``regress`` + ``ineqdeco``:
  the value function v(S) (inequality of fitted values) is recorded at full
  precision and matches to 1e-11 rel; ``shapley2``'s own Shapley values go
  through float storage and carry ~3e-7 rel rounding, so they are asserted
  at 1e-6. The Gini value function uses the plug-in (population) Gini, as
  ineqdeco does; ``shapley_inequality(index='gini')`` reports the
  bias-corrected Gini (``n/(n-1)``) -- a documented convention.
* ``mediation_decompose`` vs ``paramed`` (linear/linear, interaction,
  covariates at their means): effects and delta-method SEs to 1e-12 rel.
  Without covariates ``paramed``'s NIE SE uses the gradient
  ``(theta3, ..., beta1, beta1, ...)`` in the theta2 slot where the
  derivative is ``theta2 + theta3`` -- a reference defect, reconstructed
  exactly below (T4); every other number matches.
* ``dist_iv`` vs ``ivqte``: identical complier CDFs, but ``ivqte`` inverts
  with ``ys[max(1, #{F <= tau})]`` (largest support point with F <= tau)
  whereas StatsPAI uses the left-continuous inverse inf{y: F(y) >= tau}.
  Documented convention; the test reproduces ivqte's numbers exactly by
  applying its rule to StatsPAI-side weights (and to Stata's own phat).
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp

from statspai.decomposition._common import gini_population  # noqa: E402
from statspai.decomposition.inequality import _INDEX_FN  # noqa: E402
from statspai.decomposition.machado_mata import (  # noqa: E402
    _qreg_grid,
    _tau_process_grid,
)

FIX = Path(__file__).parent / "_fixtures"
ST = json.loads((FIX / "decomp_qte_Stata.json").read_text(encoding="utf-8"))
X = ["educ", "exper", "tenure"]
TAUS_OFF = [0.10003, 0.25003, 0.50003, 0.75003, 0.90003]
Q_IV = np.array([0.1, 0.25, 0.5, 0.75, 0.9])


@pytest.fixture(scope="module")
def wage():
    return pd.read_csv(FIX / "dq_wage.csv")


def _rel(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return float(np.max(np.abs(a - b) / np.maximum(np.abs(b), 1e-300)))


# ---- Melly / cdeco method(qr) ---------------------------------------------
def test_qr_process_matches_qrprocess(wage):
    C = np.asarray(ST["cdeco_qr_fwd"]["coef0"])  # rows: tau, educ, exper, tenure, _cons
    s = wage[wage.female == 0]
    Xm = np.column_stack([np.ones(len(s)), s[X].to_numpy()])
    B = _qreg_grid(s.log_wage.to_numpy(), Xm, _tau_process_grid(100))
    np.testing.assert_allclose(C[0], _tau_process_grid(100), atol=1e-15)
    St = np.vstack([C[4], C[1], C[2], C[3]]).T
    np.testing.assert_allclose(B, St, atol=1e-12)


@pytest.mark.parametrize("ref,key", [(0, "cdeco_qr_fwd"), (1, "cdeco_qr_rev")])
def test_melly_matches_cdeco_qr(wage, ref, key):
    g = sp.melly_decompose(
        wage, y="log_wage", group="female", x=X, tau_grid=TAUS_OFF, reference=ref
    ).quantile_grid
    s = ST[key]
    own = ("q_a", "q_b") if ref == 0 else ("q_b", "q_a")
    assert _rel(g[own[0]], s["fitted_0"]) < 1e-10
    assert _rel(g[own[1]], s["fitted_1"]) < 1e-10
    assert _rel(g["q_cf"], s["counterfactual"]) < 1e-10
    # identity: gap = composition + structure
    np.testing.assert_allclose(g.gap, g.composition + g.structure, atol=1e-14)


def test_machado_mata_converges_to_melly(wage):
    """MM draws (tau, x) pairs from exactly the pool Melly integrates, so with
    many draws it must approach Melly (T3, Monte-Carlo error ~ n_sim^-1/2)."""
    kw = dict(y="log_wage", group="female", x=X, tau_grid=[0.25, 0.5, 0.75])
    m = sp.melly_decompose(wage, **kw).quantile_grid
    mm = sp.machado_mata(wage, n_sim=200_000, seed=1, **kw).quantile_grid
    assert np.max(np.abs(mm.q_cf - m.q_cf)) < 0.01


# ---- CFM distribution regression / cdeco method(logit) -------------------
THR = np.round(np.arange(1.5, 3.4001, 0.05), 10)


@pytest.mark.parametrize("ref,key", [(0, "cdeco_logit_fwd"), (1, "cdeco_logit_rev")])
def test_cfm_matches_cdeco_logit(wage, ref, key):
    r = sp.cfm_decompose(
        wage,
        y="log_wage",
        group="female",
        x=X,
        tau_grid=TAUS_OFF,
        reference=ref,
        thresholds=THR,
        inversion="step",
    )
    s = ST[key]
    np.testing.assert_allclose(s["thresholds"], THR, atol=1e-12)
    c, g = r.cdf_grid, r.quantile_grid
    own = ("a", "b") if ref == 0 else ("b", "a")
    for col, k in [
        (f"cdf_{own[0]}", "cdf_fitted_0"),
        (f"cdf_{own[1]}", "cdf_fitted_1"),
        ("cdf_cf", "cdf_counterfactual"),
    ]:
        np.testing.assert_allclose(c[col], np.sort(s[k]), atol=1e-8)
    for col, k in [
        (f"q_{own[0]}", "fitted_0"),
        (f"q_{own[1]}", "fitted_1"),
        ("q_cf", "counterfactual"),
    ]:
        np.testing.assert_allclose(g[col], s[k], atol=1e-12)


def test_cfm_rejects_bad_inversion(wage):
    with pytest.raises(ValueError):
        sp.cfm_decompose(wage, y="log_wage", group="female", x=X, inversion="x")


# ---- Fairlie --------------------------------------------------------------
@pytest.mark.parametrize(
    "key,model,ref,tol_b,tol_se",
    [
        ("fairlie_logit_ref0_tight", "logit", 0, 1e-12, 1e-12),
        ("fairlie_probit_ref0_tight", "probit", 0, 1e-12, 1e-12),
        ("fairlie_logit_ref1", "logit", 1, 1e-10, 1e-7),
        ("fairlie_logit_ref0", "logit", 0, 1e-8, 1e-5),
        ("fairlie_probit_ref0", "probit", 0, 1e-10, 1e-6),
    ],
)
def test_fairlie_matches_stata(wage, key, model, ref, tol_b, tol_se):
    r = sp.fairlie(
        wage, y="union", group="female", x=X, model=model, reference=ref, n_sim=3
    )
    s = ST[key]
    assert _rel(r.detailed.contribution, s["b"]) < tol_b
    assert _rel(r.detailed.se, np.sqrt(s["V_diag"])) < tol_se
    assert _rel(r.explained, s["expl"]) < tol_b
    assert r.gap == pytest.approx(s["diff"], abs=1e-15)
    # equal group sizes: contributions sum to the explained gap exactly
    assert r.detailed.contribution.sum() == pytest.approx(r.explained, abs=1e-14)


# ---- Shapley inequality ----------------------------------------------------
def _yhat(df, cols):
    Xm = np.column_stack([np.ones(len(df)), df[cols].to_numpy()])
    return Xm @ np.linalg.lstsq(Xm, df.wage.to_numpy(), rcond=None)[0]


SUBSETS = [
    ["educ"],
    ["exper"],
    ["tenure"],
    ["educ", "exper"],
    ["educ", "tenure"],
    ["exper", "tenure"],
    ["educ", "exper", "tenure"],
]


@pytest.mark.parametrize("k,idx", [("ge0", "ge0"), ("ge1", "ge1"), ("ge2", "ge2")])
def test_shapley_matches_shapley2(wage, k, idx):
    v = [_INDEX_FN[idx](_yhat(wage, S)) for S in SUBSETS]
    assert _rel(v, ST["shapley"][f"v_{k}"]) < 1e-11
    r = sp.shapley_inequality(wage, y="wage", x=X, index=idx)
    assert _rel(r.shapley.contribution, ST["shapley"][k]) < 1e-6
    assert r.total == pytest.approx(ST["shapley"][f"total_{k}"], rel=1e-12)
    # efficiency: Shapley values sum to v(full)
    assert r.shapley.contribution.sum() == pytest.approx(v[-1], rel=1e-12)


def test_shapley_gini_value_function_is_plugin_gini(wage):
    v = [gini_population(_yhat(wage, S), np.ones(len(wage))) for S in SUBSETS]
    assert _rel(v, ST["shapley"]["v_gini"]) < 1e-10


# ---- Mediation vs paramed --------------------------------------------------
@pytest.fixture(scope="module")
def med():
    return pd.read_csv(FIX / "dq_med.csv")


def test_mediation_matches_paramed(med):
    r = sp.mediation_decompose(
        med, y="y", treatment="a", mediator="m", covariates=["c1", "c2"]
    )
    s = ST["paramed"]  # names: cde nde nie mte
    assert _rel([r.cde, r.nde, r.nie, r.total], s["b"]) < 1e-12
    assert _rel([r.se[k] for k in ("cde", "nde", "nie", "total")], s["se"]) < 1e-12
    fw = sp.four_way_decomposition(
        med, y="y", treat="a", mediator="m", covariates=["c1", "c2"]
    )
    assert fw.cde + fw.int_ref == pytest.approx(r.nde, abs=1e-12)
    assert fw.int_med + fw.pie == pytest.approx(r.nie, abs=1e-12)


def test_mediation_nocov_paramed_nie_se_is_reference_defect(med):
    r = sp.mediation_decompose(med, y="y", treatment="a", mediator="m")
    s = ST["paramed_nocov"]
    assert _rel([r.cde, r.nde, r.nie, r.total], s["b"]) < 1e-12
    assert (
        _rel(
            [r.se["cde"], r.se["nde"], r.se["total"]],
            [s["se"][0], s["se"][1], s["se"][3]],
        )
        < 1e-12
    )
    # paramed's NIE gradient puts theta3 where theta2 + theta3 belongs:
    A, M, Y = (med[c].to_numpy(float) for c in ("a", "m", "y"))
    n = len(A)
    Xm = np.column_stack([A, np.ones(n)])
    Xy = np.column_stack([A, M, A * M, np.ones(n)])
    bm = np.linalg.lstsq(Xm, M, rcond=None)[0]
    by = np.linalg.lstsq(Xy, Y, rcond=None)[0]

    def V(Xd, yv, b):
        e = yv - Xd @ b
        return e @ e / (n - Xd.shape[1]) * np.linalg.inv(Xd.T @ Xd)

    Sig = np.zeros((6, 6))
    Sig[:2, :2], Sig[2:, 2:] = V(Xm, M, bm), V(Xy, Y, by)
    b1, t2, t3 = bm[0], by[1], by[2]
    g_paramed = np.array([t3, 0, 0, b1, b1, 0])
    g_correct = np.array([t2 + t3, 0, 0, b1, b1, 0])
    assert np.sqrt(g_paramed @ Sig @ g_paramed) == pytest.approx(s["se"][2], rel=1e-12)
    assert np.sqrt(g_correct @ Sig @ g_correct) == pytest.approx(r.se["nie"], rel=1e-12)


# ---- dist_iv vs ivqte -------------------------------------------------------
@pytest.fixture(scope="module")
def iv():
    return pd.read_csv(FIX / "dq_iv.csv")


def _ivqte_rule(Y, D, Z, pi, taus):
    """ivqte's est_qte(): demeaned weights, quantile = ys[max(1, #{F<=tau})]."""
    n = len(Y)
    w = (Z - pi) / (pi * (1 - pi))
    w = w - w.mean()
    Pc = np.mean(D * w)
    o = np.argsort(Y, kind="mergesort")
    ys = np.unique(Y)
    cnt = np.searchsorted(Y[o], ys, side="right") - 1
    d1 = (np.cumsum(D[o] * w[o]) / Pc / n)[cnt]
    d0 = (np.cumsum((D[o] - 1) * w[o]) / Pc / n)[cnt]
    return np.array(
        [
            ys[max(0, np.sum(d1 <= t) - 1)] - ys[max(0, np.sum(d0 <= t) - 1)]
            for t in taus
        ]
    )


def test_dist_iv_vs_ivqte_is_inversion_convention(iv):
    Y, D, Z = (iv[c].to_numpy(float) for c in ("y", "d", "z"))
    ref = np.asarray(ST["ivqte_nocov"]["qte"])
    np.testing.assert_allclose(
        _ivqte_rule(Y, D, Z, np.full(len(Y), Z.mean()), Q_IV), ref, atol=1e-12
    )
    ph = np.asarray(ST["ivqte_cov"]["phat"])
    np.testing.assert_allclose(
        _ivqte_rule(Y, D, Z, ph, Q_IV), ST["ivqte_cov"]["qte"], atol=1e-12
    )
    # StatsPAI's logit propensity is Stata's logit MLE
    from statspai.qte._core import logit_propensity

    np.testing.assert_allclose(
        logit_propensity(iv[["x1", "x2"]].to_numpy(), Z), ph, atol=1e-9
    )
    # same CDFs, different inverse: within one support step of each other
    ours = sp.dist_iv(iv, y="y", treat="d", instrument="z", quantiles=Q_IV).late_q
    assert np.max(np.abs(ours - ref)) < 0.05


def test_beyond_average_late_equals_dist_iv(iv):
    a = sp.beyond_average_late(
        iv, y="y", treat="d", instrument="z", quantiles=Q_IV, n_boot=3
    )
    b = sp.dist_iv(iv, y="y", treat="d", instrument="z", quantiles=Q_IV, se="none")
    np.testing.assert_array_equal(a.late_q, b.late_q)

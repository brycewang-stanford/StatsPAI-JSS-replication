"""Reference parity (T2): GRF-family operators vs ``grf``, forest held fixed.

Two independently grown forests never agree tree by tree, so end-to-end
forest comparisons are graded against Monte Carlo error
(``test_grf_family_statistical_parity.py``).  Everything *after* the forest
is deterministic and is pinned here: fed ``grf``'s own out-of-bag forest
weights, nuisance estimates and score inputs (``grf_family_R.json``,
grf 2.6.1), the StatsPAI operators must reproduce ``grf``'s outputs to the
floating-point floor:

=====================================  =====================================
operator                               grf reference
=====================================  =====================================
local IV (Wald) solve                  ``instrumental_forest`` predictions
ACLATE scores / average / BLP          ``get_scores``, ``average_treatment_
                                       effect``, ``best_linear_projection``
                                       (``compliance.score`` supplied)
local multi-regressor least squares    ``multi_arm_causal_forest``,
                                       ``lm_forest`` predictions
multi-arm AIPW scores / averages       ``get_scores``, ``average_treatment_
                                       effect``
causal-survival ratio / scores / BLP   ``causal_survival_forest`` (RMST and
                                       survival probability)
forest-weighted Kaplan-Meier /         ``survival_forest`` predictions
Nelson-Aalen curves
forest-weighted quantiles              ``quantile_forest`` predictions
class frequencies, regression means    ``probability_forest``,
                                       ``regression_forest`` predictions
split-frequency importance             ``variable_importance`` (8 forests)
=====================================  =====================================

The nuisance-to-score map of the causal survival forest (the censoring-
adjusted numerator of Cui et al. 2023, eq. 11) is pinned separately in
``test_csf_psi_operator_parity.py``.

Regenerate with::

    python tests/reference_parity/_fixtures/_generate_grf_family_data.py
    Rscript tests/reference_parity/_fixtures/_generate_grf_family.R

References
----------
[@athey2019generalized], [@cui2023estimating], [@nie2021quasi]
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd
import pytest

from statspai.forest import _grf_ext as ext
from statspai.forest._grf_family import (
    importance_from_split_frequencies,
    score_average,
    score_blp,
)
from statspai.forest.iv_forest import iv_debiasing_weights, iv_dr_scores
from statspai.forest.multi_arm_forest import multi_arm_scores
from statspai.survival.causal_forest import csf_dr_scores

_DIR = pathlib.Path(__file__).parent / "_fixtures"
_JSON = _DIR / "grf_family_R.json"
_CSV = _DIR / "grf_family_data.csv"

pytestmark = pytest.mark.skipif(
    not (_JSON.exists() and _CSV.exists()),
    reason="grf_family fixture is not materialized",
)

# Floating-point floor: sums over 200 rows of products of O(1) numbers.
TOL = 1e-12


def _a(values) -> np.ndarray:
    return np.asarray(values, dtype=float)


@pytest.fixture(scope="module")
def ref():
    return json.loads(_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def data():
    return pd.read_csv(_CSV)


def _uniform(n: int) -> np.ndarray:
    return np.full(n, 1.0 / n)


# --------------------------------------------------------------------------- #
#  Instrumental forest
# --------------------------------------------------------------------------- #


def test_iv_local_wald_solve_matches_grf_predictions(ref):
    iv = ref["iv"]
    K = ref["meta"]["weight_rows"]
    M = np.column_stack(
        [
            _a(iv["Y"]) - _a(iv["Y_hat"]),
            _a(iv["W"]) - _a(iv["W_hat"]),
            _a(iv["Z"]) - _a(iv["Z_hat"]),
        ]
    )
    ours = ext.weighted_solve(
        ext.KIND_INSTRUMENTAL, _a(iv["weights"]), M, np.ones(M.shape[0]), np.zeros(1)
    )[:, 0]
    np.testing.assert_allclose(ours, _a(iv["predictions"])[:K], rtol=0, atol=TOL)


def _iv_scores(iv):
    Z, zh = _a(iv["Z"]), _a(iv["Z_hat"])
    g = iv_debiasing_weights(Z, zh, zh * (1 - zh), _a(iv["compliance"]))
    return iv_dr_scores(
        _a(iv["Y"]),
        _a(iv["W"]),
        _a(iv["Y_hat"]),
        _a(iv["W_hat"]),
        _a(iv["predictions"]),
        g,
    )


def test_iv_scores_average_and_blp_match_grf(ref, data):
    iv = ref["iv"]
    scores = _iv_scores(iv)
    np.testing.assert_allclose(scores, _a(iv["scores"]), rtol=0, atol=1e-11)
    n = scores.size
    avg = score_average(scores, _uniform(n), None, 0.05)
    assert avg["estimate"] == pytest.approx(iv["ate"], abs=TOL)
    assert avg["se"] == pytest.approx(iv["ate_se"], abs=TOL)
    A = data.query("design == 'iv'")[["x1", "x2"]].to_numpy()
    blp = score_blp(scores, A, ["I", "x1", "x2"], _uniform(n), None, "HC3", 0.05, "")
    np.testing.assert_allclose(blp["coef"], iv["blp"]["coef"], rtol=0, atol=TOL)
    np.testing.assert_allclose(blp["se"], iv["blp"]["se"], rtol=0, atol=TOL)


# --------------------------------------------------------------------------- #
#  Multi-arm causal forest and lm forest
# --------------------------------------------------------------------------- #


def test_multi_arm_local_solve_matches_grf_predictions(ref):
    ma = ref["multiarm"]
    K = ref["meta"]["weight_rows"]
    arms = _a(ma["W"]).astype(int)
    onehot = np.eye(3)[arms]
    What = _a(ma["W_hat"])
    M = np.column_stack([_a(ma["Y"]) - _a(ma["Y_hat"]), onehot[:, 1:] - What[:, 1:]])
    ours = ext.weighted_solve(
        ext.KIND_MULTI_CAUSAL,
        _a(ma["weights"]),
        M,
        np.ones(M.shape[0]),
        np.array([1.0, 2.0]),
    )
    np.testing.assert_allclose(ours, _a(ma["predictions"])[:K], rtol=0, atol=TOL)


def test_multi_arm_scores_and_averages_match_grf(ref):
    ma = ref["multiarm"]
    scores = multi_arm_scores(
        _a(ma["Y"]),
        _a(ma["W"]).astype(int),
        _a(ma["Y_hat"]),
        _a(ma["W_hat"]),
        _a(ma["predictions"]),
    )
    np.testing.assert_allclose(scores, _a(ma["scores"]), rtol=0, atol=1e-11)
    n = scores.shape[0]
    for j in range(scores.shape[1]):
        avg = score_average(scores[:, j], _uniform(n), None, 0.05)
        assert avg["estimate"] == pytest.approx(ma["ate"][j], abs=TOL)
        assert avg["se"] == pytest.approx(ma["ate_se"][j], abs=TOL)


def test_lm_forest_local_solve_matches_grf_predictions(ref):
    lm = ref["lm"]
    K = ref["meta"]["weight_rows"]
    M = np.column_stack([_a(lm["Y"]) - _a(lm["Y_hat"]), _a(lm["W"]) - _a(lm["W_hat"])])
    ours = ext.weighted_solve(
        ext.KIND_MULTI_CAUSAL,
        _a(lm["weights"]),
        M,
        np.ones(M.shape[0]),
        np.array([1.0, 2.0]),
    )
    np.testing.assert_allclose(ours, _a(lm["predictions"])[:K], rtol=0, atol=1e-11)


# --------------------------------------------------------------------------- #
#  Causal survival forest
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("target", ["RMST", "survival.probability"])
def test_csf_ratio_scores_average_and_blp_match_grf(ref, data, target):
    c = ref[f"csf_{target}"]
    K = ref["meta"]["weight_rows"]
    num, den = _a(c["numerator"]), _a(c["denominator"])
    ours = ext.weighted_solve(
        ext.KIND_CAUSAL_SURV,
        _a(c["weights"]),
        np.column_stack([num, den]),
        np.ones(num.size),
        np.zeros(1),
    )[:, 0]
    np.testing.assert_allclose(ours, _a(c["predictions"])[:K], rtol=0, atol=TOL)
    scores = csf_dr_scores(_a(c["predictions"]), num, den, _a(c["W_hat"]))
    np.testing.assert_allclose(scores, _a(c["scores"]), rtol=0, atol=TOL)
    avg = score_average(scores, _uniform(num.size), None, 0.05)
    assert avg["estimate"] == pytest.approx(c["ate"], abs=TOL)
    assert avg["se"] == pytest.approx(c["ate_se"], abs=TOL)
    A = data.query("design == 'survival'")[["x1", "x2"]].to_numpy()
    blp = score_blp(
        scores, A, ["I", "x1", "x2"], _uniform(num.size), None, "HC3", 0.05, ""
    )
    np.testing.assert_allclose(blp["coef"], c["blp"]["coef"], rtol=0, atol=TOL)
    np.testing.assert_allclose(blp["se"], c["blp"]["se"], rtol=0, atol=TOL)


def test_csf_denominator_is_the_squared_centred_treatment(ref):
    """grf's denominator equals ``(W - W_hat)^2`` -- the population value of
    the censoring bracket, which StatsPAI uses too."""
    for target in ("RMST", "survival.probability"):
        c = ref[f"csf_{target}"]
        resid = _a(c["W"]) - _a(c["W_hat"])
        np.testing.assert_allclose(_a(c["denominator"]), resid**2, rtol=0, atol=TOL)


# --------------------------------------------------------------------------- #
#  Survival, quantile, probability and regression forests
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("estimator", ["km", "na"])
def test_survival_curves_from_weights_match_grf(ref, estimator):
    s = ref["survival"]
    grid = _a(s["failure_times"])
    tidx = np.searchsorted(grid, _a(s["Y"]), side="right")
    ours = ext.km_from_weights(
        _a(s["weights"]),
        tidx,
        _a(s["D"]),
        np.ones(tidx.size),
        grid.size,
        nelson_aalen=estimator == "na",
    )
    np.testing.assert_allclose(ours, _a(s[estimator]), rtol=0, atol=TOL)


def test_weighted_quantiles_match_grf(ref):
    q = ref["quantile"]
    ours = ext.quantiles_from_weights(_a(q["weights"]), _a(q["Y"]), _a(q["quantiles"]))
    np.testing.assert_allclose(ours, _a(q["predictions"]), rtol=0, atol=0)


def test_probability_and_regression_means_match_grf(ref):
    p = ref["probability"]
    cls = _a(p["classes"]).astype(int)
    onehot = np.eye(cls.max() + 1)[cls]
    ours = ext.weighted_solve(
        ext.KIND_MULTI_REG,
        _a(p["weights"]),
        onehot,
        np.ones(cls.size),
        np.array([float(onehot.shape[1])]),
    )
    np.testing.assert_allclose(ours, _a(p["predictions"]), rtol=0, atol=TOL)
    r = ref["regression"]
    y = _a(r["Y"])
    ours = ext.weighted_solve(
        ext.KIND_MULTI_REG,
        _a(r["weights"]),
        y[:, None],
        np.ones(y.size),
        np.array([1.0]),
    )[:, 0]
    np.testing.assert_allclose(ours, _a(r["predictions"]), rtol=0, atol=TOL)


@pytest.mark.parametrize(
    "forest",
    [
        "iv",
        "multiarm",
        "lm",
        "csf_RMST",
        "survival",
        "quantile",
        "probability",
        "regression",
    ],
)
def test_variable_importance_matches_grf(ref, forest):
    f = ref[forest]
    ours = importance_from_split_frequencies(_a(f["split_frequencies"]), 2.0)
    np.testing.assert_allclose(ours, _a(f["importance"]), rtol=0, atol=TOL)


# --------------------------------------------------------------------------- #
#  The public entry points route to the pinned operators
# --------------------------------------------------------------------------- #


def test_public_tools_route_to_pinned_operators(data):
    """sp.get_scores / sp.best_linear_projection / sp.variable_importance on
    a fitted forest are exactly the operators pinned above, applied to that
    forest's own inputs."""
    import statspai as sp

    d = data.query("design == 'iv'")
    X = d[["x1", "x2", "x3"]].to_numpy()
    fit = sp.iv_forest(y=d.Y, treat=d.W, instrument=d.Z, covariates=X, n_estimators=200)
    g = iv_debiasing_weights(fit._Z, fit._z_hat, fit._z_var, fit._compliance)
    own = iv_dr_scores(fit._Y, fit._W, fit._y_hat, fit._w_hat, fit.cate, g)
    np.testing.assert_array_equal(sp.get_scores(fit), own)
    A = X[:, :2]
    blp = sp.best_linear_projection(fit, A=A, vce="HC3")
    ref = score_blp(
        own, A, ["Intercept", "A1", "A2"], fit._obs_weight, None, "HC3", 0.05, ""
    )
    np.testing.assert_allclose(blp["coef"], ref["coef"], rtol=0, atol=TOL)
    np.testing.assert_allclose(blp["se"], ref["se"], rtol=0, atol=TOL)
    counts = fit.split_frequencies(4).to_numpy()
    np.testing.assert_allclose(
        sp.variable_importance(fit).to_numpy(),
        importance_from_split_frequencies(counts, 2.0),
        rtol=0,
        atol=TOL,
    )

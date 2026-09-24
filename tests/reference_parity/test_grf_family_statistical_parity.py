"""Statistical parity (T3): GRF-family forests vs ``grf`` on known-truth designs.

Two forests grown with independent random streams never produce the same
predictions, so -- as for the causal forest in
``test_grf_engine_statistical_parity.py`` -- the comparison is on what each
estimator is *for*, against the truth of the design
(``_fixtures/_generate_grf_family_stat_data.py``) and against grf 2.6.1
run with three seeds (``_fixtures/_generate_grf_family_stat.R``).  The
operators after the forest are pinned exactly in
``test_grf_family_operator_parity.py``; what remains here is the forest.

=====================  ============================================  =============
forest                 quantity (sp / grf, calibration)              gate
=====================  ============================================  =============
instrumental           CATE RMSE ratio                               [0.92, 1.08]
                       pointwise 95% coverage difference             |.| <= 0.05
                       median variance ratio                         [0.80, 1.25]
                       ACLATE difference / grf SE                    <= 0.5
                       ACLATE SE ratio                               [0.95, 1.05]
multi-arm (per arm)    same five quantities                          same gates
lm forest              coefficient RMSE ratios                       [0.92, 1.08]
causal survival        same five quantities (RMST, h = 1.5)          same gates
survival forest        MAE of S(t | x), t = 0.25, 0.5, 1             [0.90, 1.10]
quantile forest        MAE of q = 0.1, 0.5, 0.9                      [0.90, 1.10]
=====================  ============================================  =============

Regenerate with::

    python tests/reference_parity/_fixtures/_generate_grf_family_stat_data.py
    Rscript tests/reference_parity/_fixtures/_generate_grf_family_stat.R

References
----------
[@athey2019generalized], [@cui2023estimating], [@ishwaran2008random]
"""

from __future__ import annotations

import json
import pathlib
import warnings

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

import statspai as sp
from statspai.forest.survival_forest import step_eval

_DIR = pathlib.Path(__file__).parent / "_fixtures"
_CSV = _DIR / "grf_family_stat_data.csv"
_JSON = _DIR / "grf_family_stat_R.json"

pytestmark = pytest.mark.skipif(
    not (_CSV.exists() and _JSON.exists()),
    reason="grf_family_stat fixture is not materialized",
)

SEED = 5


@pytest.fixture(scope="module")
def ref():
    return json.loads(_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def data():
    return pd.read_csv(_CSV)


def _X(d: pd.DataFrame) -> np.ndarray:
    return d[[f"x{j}" for j in range(1, 6)]].to_numpy()


def _rmse(a, b) -> float:
    return float(np.sqrt(np.mean((np.asarray(a) - np.asarray(b)) ** 2)))


def _cover(p, v, truth) -> float:
    return float(np.mean(np.abs(p - truth) <= norm.ppf(0.975) * np.sqrt(v)))


def _grf_mean(runs, key, sub=None):
    vals = [(r[sub] if sub else r)[key] for r in runs.values()]
    return float(np.mean(vals))


def _check_effect_forest(pred, var, truth, ate, se, runs, sub=None):
    ratio = _rmse(pred, truth) / _grf_mean(runs, "rmse", sub)
    assert 0.92 <= ratio <= 1.08, f"CATE RMSE ratio {ratio:.3f}"
    cov_diff = _cover(pred, var, truth) - _grf_mean(runs, "cover", sub)
    assert abs(cov_diff) <= 0.05, f"coverage difference {cov_diff:+.3f}"
    var_ratio = float(np.median(var)) / _grf_mean(runs, "median_var", sub)
    assert 0.80 <= var_ratio <= 1.25, f"median variance ratio {var_ratio:.3f}"
    grf_se = _grf_mean(runs, "ate_se", sub)
    ate_gap = abs(ate - _grf_mean(runs, "ate", sub)) / grf_se
    assert ate_gap <= 0.5, f"ATE difference {ate_gap:.2f} grf SEs"
    se_ratio = se / grf_se
    assert 0.95 <= se_ratio <= 1.05, f"ATE SE ratio {se_ratio:.3f}"


def test_instrumental_forest_matches_grf_statistically(ref, data):
    d = data[data.design == "iv"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        fit = sp.iv_forest(
            y=d.Y, treat=d.W, instrument=d.Z, covariates=_X(d), random_state=SEED
        )
    _check_effect_forest(
        fit.cate,
        fit.cate_variance,
        d.tau.to_numpy(),
        fit.late,
        fit.se,
        ref["iv"]["runs"],
    )


def test_multi_arm_forest_matches_grf_statistically(ref, data):
    d = data[data.design == "multiarm"]
    fit = sp.multi_arm_forest(y=d.Y, treat=d.W, covariates=_X(d), random_state=SEED)
    for arm, col, sub in ((1, "tau", "arm1"), (2, "tau2", "arm2")):
        _check_effect_forest(
            fit.cate[arm],
            fit.cate_variance[arm],
            d[col].to_numpy(),
            fit.ate[arm],
            fit.ate_se[arm],
            ref["multiarm"]["runs"],
            sub,
        )


def test_lm_forest_matches_grf_statistically(ref, data):
    d = data[data.design == "lm"]
    fit = sp.lm_forest(
        y=d.Y,
        regressors=d[["W", "W2"]].to_numpy(),
        covariates=_X(d),
        random_state=SEED,
    )
    runs = ref["lm"]["runs"]
    for j, (col, key) in enumerate((("tau", "rmse1"), ("tau2", "rmse2"))):
        ratio = _rmse(fit.coefficients[:, j, 0], d[col]) / _grf_mean(runs, key)
        assert 0.92 <= ratio <= 1.08, f"h{j + 1} RMSE ratio {ratio:.3f}"


def test_causal_survival_forest_matches_grf_statistically(ref, data):
    d = data[data.design == "csf"]
    fit = sp.causal_survival_forest(
        time=d.Y,
        event=d.D,
        treat=d.W,
        covariates=_X(d),
        horizon=ref["meta"]["horizon"],
        random_state=SEED,
    )
    _check_effect_forest(
        fit.cate,
        fit.cate_variance,
        d.tau.to_numpy(),
        fit.ate,
        fit.se,
        ref["csf"]["runs"],
    )


def test_survival_forest_matches_grf_statistically(ref, data):
    d = data[data.design == "survival"]
    fit = sp.survival_forest(time=d.Y, event=d.D, covariates=_X(d), random_state=SEED)
    times = np.asarray(ref["survival"]["times"])
    truth = np.exp(-np.outer(d.tau, times))
    mae = np.mean(
        np.abs(step_eval(fit.predictions, fit.failure_times, times) - truth), axis=0
    )
    grf = np.mean([r["mae"] for r in ref["survival"]["runs"].values()], axis=0)
    ratio = mae / grf
    assert np.all((ratio >= 0.90) & (ratio <= 1.10)), f"MAE ratios {np.round(ratio, 3)}"


def test_quantile_forest_matches_grf_statistically(ref, data):
    d = data[data.design == "quantile"]
    qs = np.asarray(ref["quantile"]["quantiles"])
    fit = sp.quantile_forest(y=d.Y, covariates=_X(d), quantiles=qs, random_state=SEED)
    truth = d.x1.to_numpy()[:, None] + np.outer(d.tau, norm.ppf(qs))
    mae = np.mean(np.abs(fit.predictions - truth), axis=0)
    grf = np.mean([r["mae"] for r in ref["quantile"]["runs"].values()], axis=0)
    ratio = mae / grf
    assert np.all((ratio >= 0.90) & (ratio <= 1.10)), f"MAE ratios {np.round(ratio, 3)}"

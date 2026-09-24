"""sp.dynamic_dml against econml's DynamicDML, and against a known truth.

Two kinds of evidence, kept apart:

**T2, strict parity.** ``econml.panel.dml.DynamicDML`` [econml] is the
reference implementation of [lewis2021double], written by the authors of
the method. Given the same cross-fitting folds and the same first-stage
learners the two estimators solve the same moment conditions, so they must
agree to floating point -- and they do, to ~1e-15 relative on both the
per-period estimates and their standard errors. Fixing the folds is what
makes this a parity test rather than a Monte Carlo comparison: econml draws
its own ``GroupKFold`` otherwise, and any disagreement would then be
unattributable.

**T1, known truth.** On a linear dynamic system the estimand has a closed
form -- the direct blip plus every path through the states the treatment
moves -- so bias and coverage are measurable without any reference. The
Monte Carlo pins three claims: the periods and the total sequence effect
are unbiased and cover at the nominal rate, the heterogeneity slopes are
recovered, and dropping the treatment history from the state (``lags=0``)
destroys all of it.

References
----------
[@lewis2021double], [@econml]
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LinearRegression

import statspai as sp

econml_panel = pytest.importorskip("econml.panel.dml")

M = 3
A_T, B_T = 0.8, 0.5
C_W, D_W = 0.6, 0.7
THETA = np.array([0.4, 0.6, 1.0])
PHI = np.array([0.5, 0.9, 1.3])
GAMMA = np.array([0.3, -0.5, 0.8])
REPS = 40
Z975 = 1.959963984540054


def truth() -> np.ndarray:
    total = THETA.astype(float).copy()
    for t in range(M):
        for k in range(t + 1, M):
            total[t] += PHI[k] * D_W * (C_W ** (k - t - 1))
    return total


def _simulate(seed: int, n_units: int, het: bool = False):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n_units)
    W = np.zeros((n_units, M))
    T = np.zeros((n_units, M))
    W[:, 0] = rng.normal(size=n_units)
    for t in range(M):
        if t:
            W[:, t] = C_W * W[:, t - 1] + D_W * T[:, t - 1] + rng.normal(size=n_units)
        T[:, t] = (
            A_T * W[:, t] + (B_T * T[:, t - 1] if t else 0.0) + rng.normal(size=n_units)
        )
    blips = THETA + (np.outer(x, GAMMA) if het else 0.0)
    y = (T * blips).sum(1) + (W * PHI).sum(1) + 0.4 * x + rng.normal(size=n_units)
    frame = pd.DataFrame(
        {
            "id": np.repeat(np.arange(n_units), M),
            "t": np.tile(np.arange(M), n_units),
            "y": np.repeat(y, M),
            "d": T.ravel(),
            "w": W.reshape(-1, 1).ravel(),
            "x": np.repeat(x, M),
        }
    )
    return frame, T, W, y, x


# --------------------------------------------------------------------------- #
#  T2: strict parity with the reference implementation
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("n_folds", [3, 4])
def test_matches_econml_given_the_same_folds_and_learners(n_folds):
    n_units = 1500
    frame, T, W, y_final, _ = _simulate(21, n_units)
    rng = np.random.default_rng(5)
    unit_fold = rng.permutation(n_units) % n_folds

    ours = sp.dynamic_dml(
        frame,
        y="y",
        treat="d",
        id="id",
        time="t",
        covariates=["w"],
        lags=1,
        model_y=LinearRegression(),
        model_t=LinearRegression(),
        fold_ids=unit_fold,
    )

    # econml takes the state as one long array, so build exactly what
    # dynamic_dml builds internally: W_t, the one lagged treatment, and the
    # intercept its own final stage does not add for us.
    lagged = np.zeros_like(T)
    lagged[:, 1:] = T[:, :-1]
    state = np.column_stack(
        [W.reshape(-1, 1), lagged.reshape(-1, 1), np.ones(n_units * M)]
    )
    groups = np.repeat(np.arange(n_units), M)
    row_fold = np.repeat(unit_fold, M)
    splits = [
        (np.flatnonzero(row_fold != f), np.flatnonzero(row_fold == f))
        for f in range(n_folds)
    ]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        est = econml_panel.DynamicDML(
            model_y=LinearRegression(), model_t=LinearRegression(), cv=splits
        )
        est.fit(
            np.repeat(y_final, M),
            T.reshape(-1, 1),
            X=None,
            W=state,
            groups=groups,
            inference="auto",
        )
        reference = np.ravel(est.const_marginal_effect())
        lo, hi = est.const_marginal_effect_interval()
    reference_se = (np.ravel(hi) - np.ravel(lo)) / 2 / Z975

    np.testing.assert_allclose(
        ours.periods["estimate"].to_numpy(), reference, rtol=1e-12, atol=0
    )
    np.testing.assert_allclose(
        ours.periods["se"].to_numpy(), reference_se, rtol=1e-10, atol=0
    )


def test_total_effect_matches_econmls_sequence_effect():
    # The point of the joint covariance: econml gets the same number for the
    # whole sequence from its own stacked inference, so ours is not a
    # reinterpretation of the per-period intervals.
    n_units = 1200
    frame, T, W, y_final, _ = _simulate(22, n_units)
    rng = np.random.default_rng(9)
    unit_fold = rng.permutation(n_units) % 3
    ours = sp.dynamic_dml(
        frame,
        y="y",
        treat="d",
        id="id",
        time="t",
        covariates=["w"],
        model_y=LinearRegression(),
        model_t=LinearRegression(),
        fold_ids=unit_fold,
    )
    lagged = np.zeros_like(T)
    lagged[:, 1:] = T[:, :-1]
    state = np.column_stack(
        [W.reshape(-1, 1), lagged.reshape(-1, 1), np.ones(n_units * M)]
    )
    row_fold = np.repeat(unit_fold, M)
    splits = [
        (np.flatnonzero(row_fold != f), np.flatnonzero(row_fold == f)) for f in range(3)
    ]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        est = econml_panel.DynamicDML(
            model_y=LinearRegression(), model_t=LinearRegression(), cv=splits
        )
        est.fit(
            np.repeat(y_final, M),
            T.reshape(-1, 1),
            X=None,
            W=state,
            groups=groups_of(n_units),
            inference="auto",
        )
        total = float(np.ravel(est.effect(T0=np.zeros((1, M)), T1=np.ones((1, M))))[0])
        tlo, thi = est.effect_interval(T0=np.zeros((1, M)), T1=np.ones((1, M)))
    total_se = (float(np.ravel(thi)[0]) - float(np.ravel(tlo)[0])) / 2 / Z975
    np.testing.assert_allclose(ours.estimate, total, rtol=1e-12)
    np.testing.assert_allclose(ours.se, total_se, rtol=1e-8)
    # And it is not the naive sum of variances.
    assert ours.se < 0.75 * ours.diagnostics["independent_sum_se"]


def groups_of(n_units: int) -> np.ndarray:
    return np.repeat(np.arange(n_units), M)


# --------------------------------------------------------------------------- #
#  T1: known truth
# --------------------------------------------------------------------------- #


def _run(het: bool, lags: int = 1, n_units: int = 2500):
    rows = []
    tr = truth()
    for seed in range(REPS):
        frame, *_ = _simulate(seed, n_units, het=het)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = sp.dynamic_dml(
                frame,
                y="y",
                treat="d",
                id="id",
                time="t",
                covariates=["w"],
                modifiers=["x"] if het else None,
                lags=lags,
                model_y=LinearRegression(),
                model_t=LinearRegression(),
                n_folds=4,
                random_state=seed,
            )
        record = {
            "total_err": res.estimate - tr.sum(),
            "total_cov": res.ci_lower <= tr.sum() <= res.ci_upper,
        }
        for k, label in enumerate(res.period_labels):
            record[f"err{k}"] = res.periods["estimate"].iloc[k] - tr[k]
            record[f"cov{k}"] = (
                res.periods["ci_low"].iloc[k] <= tr[k] <= res.periods["ci_high"].iloc[k]
            )
        if het:
            block = res.coef.xs("x", level="term")
            for k in range(M):
                record[f"gerr{k}"] = block["estimate"].iloc[k] - GAMMA[k]
                record[f"gcov{k}"] = (
                    block["ci_low"].iloc[k] <= GAMMA[k] <= block["ci_high"].iloc[k]
                )
        rows.append(record)
    return pd.DataFrame(rows).mean()


@pytest.fixture(scope="module")
def homogeneous():
    return _run(het=False)


@pytest.fixture(scope="module")
def heterogeneous():
    return _run(het=True)


@pytest.mark.slow
@pytest.mark.parametrize("period", range(M))
def test_period_effects_are_unbiased_and_cover(homogeneous, period):
    # Bands allow for the Monte Carlo error of 40 replications (binomial sd
    # ~3.4 points on a 95% rate).
    assert abs(homogeneous[f"err{period}"]) < 0.04
    assert homogeneous[f"cov{period}"] >= 0.85


@pytest.mark.slow
def test_total_sequence_effect_is_unbiased_and_covers(homogeneous):
    assert abs(homogeneous["total_err"]) < 0.04
    assert homogeneous["total_cov"] >= 0.85


@pytest.mark.slow
@pytest.mark.parametrize("period", range(M))
def test_heterogeneity_slopes_are_recovered(heterogeneous, period):
    assert abs(heterogeneous[f"gerr{period}"]) < 0.05
    assert heterogeneous[f"gcov{period}"] >= 0.85
    assert abs(heterogeneous[f"err{period}"]) < 0.05
    assert heterogeneous[f"cov{period}"] >= 0.85


@pytest.mark.slow
def test_dropping_the_treatment_history_breaks_coverage_entirely():
    # The reason lags=1 is the default. Not a tolerance question: with the
    # history out of the state nothing covers, at any sample size.
    m = _run(het=False, lags=0, n_units=1500)
    assert max(abs(m["err0"]), abs(m["err1"]), abs(m["err2"])) > 0.15
    assert max(m["cov0"], m["cov1"], m["cov2"]) <= 0.05

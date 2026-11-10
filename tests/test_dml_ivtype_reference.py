"""Fold-controlled reference test: ``sp.dml(model='plr', score='IV-type')``.

The unpinned parity test in ``tests/external_parity/test_dml_python_parity.py``
lets each engine draw its own folds and therefore has to tolerate a
0.05 gap, inside which a wrong moment condition can hide -- the ML4CI
companion paper found exactly that: before 1.29.0 the IV-type option
substituted ``l(X) = E[Y|X]`` for the third nuisance ``g(X) = E[Y - theta~ D
| X]`` and disagreed with both DoubleML ports by 0.40 standard errors
while passing the tolerance.  Pinning the partition makes the comparison
sharp: with closed-form learners the two engines must agree to floating
point, and with a regularised learner to the reproducibility of the
learner itself.

Three assertions:

1. With linear learners the IV-type estimate equals DoubleML-for-Python's
   IV-type estimate on the shared partition to 1e-10 (both point estimate
   and standard error).
2. With linear learners the IV-type estimate equals StatsPAI's own
   partialling-out estimate on the same partition -- the finite-sample
   identity the companion paper proves (the cross-fitted estimator of
   ``Y - theta~ D`` is linear in its argument, so the IV-type numerator
   collapses to the partialling-out numerator).
3. With a cross-validated lasso the two engines still agree to 1e-8 on the
   shared partition (the lasso path is deterministic given ``random_state``).

DoubleML is an optional test dependency; the reference assertions skip
when it is not installed, the identity assertion never does.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import sklearn
from sklearn.linear_model import LassoCV, LinearRegression

import statspai as sp


def _lasso_cv() -> LassoCV:
    """LassoCV on a 50-point alpha path under every supported scikit-learn.

    scikit-learn 1.7 folded ``n_alphas`` into ``alphas=<int>`` and later
    releases removed ``n_alphas``; earlier releases accept only ``n_alphas``.
    """
    if tuple(int(p) for p in sklearn.__version__.split(".")[:2]) >= (1, 7):
        return LassoCV(cv=5, random_state=0, alphas=50, max_iter=10000)
    return LassoCV(cv=5, random_state=0, n_alphas=50, max_iter=10000)


doubleml = pytest.importorskip("doubleml")


def _dgp(n: int = 2000, p: int = 20, seed: int = 20260811) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rho = 0.5
    sigma = rho ** np.abs(np.subtract.outer(np.arange(p), np.arange(p)))
    X = rng.normal(size=(n, p)) @ np.linalg.cholesky(sigma).T
    beta = np.array([1.0 / (j + 1) ** 2 for j in range(p)])
    D = X @ beta * 0.8 + rng.normal(size=n)
    Y = 1.0 * D + X @ beta + rng.normal(size=n)
    df = pd.DataFrame(X, columns=[f"x{j + 1}" for j in range(p)])
    df["d"] = D
    df["y"] = Y
    return df


def _folds(n: int, k: int = 5, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    labels = np.tile(np.arange(k), int(np.ceil(n / k)))[:n]
    rng.shuffle(labels)
    return labels.astype(int)


def _doubleml_ivtype(df, X, folds, learner):
    from sklearn.base import clone

    data = doubleml.DoubleMLData(df, y_col="y", d_cols="d", x_cols=X)
    obj = doubleml.DoubleMLPLR(
        data,
        ml_l=clone(learner),
        ml_m=clone(learner),
        ml_g=clone(learner),
        n_folds=5,
        score="IV-type",
        draw_sample_splitting=False,
    )
    idx = np.arange(len(folds))
    smpls = [[(idx[folds != k], idx[folds == k]) for k in sorted(np.unique(folds))]]
    obj.set_sample_splitting(smpls)
    obj.fit()
    return float(np.ravel(obj.coef)[0]), float(np.ravel(obj.se)[0])


@pytest.fixture(scope="module")
def data():
    df = _dgp()
    X = [c for c in df.columns if c.startswith("x")]
    return df, X, _folds(len(df))


def test_ivtype_matches_doubleml_bitwise_with_linear_learners(data):
    df, X, folds = data
    res = sp.dml(
        df,
        y="y",
        treat="d",
        covariates=X,
        model="plr",
        ml_g=LinearRegression(),
        ml_m=LinearRegression(),
        n_folds=5,
        fold_indices=folds,
        score="IV-type",
    )
    ref_coef, ref_se = _doubleml_ivtype(df, X, folds, LinearRegression())
    assert abs(res.estimate - ref_coef) < 1e-10, (res.estimate, ref_coef)
    assert abs(res.se - ref_se) < 1e-10, (res.se, ref_se)


def test_ivtype_equals_partialling_out_under_linear_learners(data):
    """Proposition 1 of the companion paper: linear smoother => identity."""
    df, X, folds = data
    po = sp.dml(
        df,
        y="y",
        treat="d",
        covariates=X,
        model="plr",
        ml_g=LinearRegression(),
        ml_m=LinearRegression(),
        n_folds=5,
        fold_indices=folds,
    )
    iv = sp.dml(
        df,
        y="y",
        treat="d",
        covariates=X,
        model="plr",
        ml_g=LinearRegression(),
        ml_m=LinearRegression(),
        n_folds=5,
        fold_indices=folds,
        score="IV-type",
    )
    assert abs(po.estimate - iv.estimate) < 1e-10, (po.estimate, iv.estimate)


def _doubleml_plr_po(df, X, folds, learner):
    from sklearn.base import clone

    data = doubleml.DoubleMLData(df, y_col="y", d_cols="d", x_cols=X)
    obj = doubleml.DoubleMLPLR(
        data,
        ml_l=clone(learner),
        ml_m=clone(learner),
        n_folds=5,
        score="partialling out",
        draw_sample_splitting=False,
    )
    idx = np.arange(len(folds))
    obj.set_sample_splitting(
        [[(idx[folds != k], idx[folds == k]) for k in sorted(np.unique(folds))]]
    )
    obj.fit()
    return float(np.ravel(obj.coef)[0]), float(np.ravel(obj.se)[0])


def test_partialling_out_matches_doubleml_bitwise_on_shared_folds(data):
    """The default score, pinned: a 0.05 tolerance is not a parity test."""
    df, X, folds = data
    res = sp.dml(
        df,
        y="y",
        treat="d",
        covariates=X,
        model="plr",
        ml_g=LinearRegression(),
        ml_m=LinearRegression(),
        n_folds=5,
        fold_indices=folds,
    )
    ref_coef, ref_se = _doubleml_plr_po(df, X, folds, LinearRegression())
    assert res.estimate == ref_coef, (res.estimate, ref_coef)
    assert abs(res.se - ref_se) < 1e-12


@pytest.mark.parametrize("score", ["ATE", "ATTE"])
def test_irm_matches_doubleml_bitwise_on_shared_folds(score):
    """Interactive model, both scores, on a pinned partition."""
    from sklearn.base import clone
    from sklearn.linear_model import LogisticRegression

    rng = np.random.default_rng(20260811)
    n, p = 2000, 20
    X = rng.normal(size=(n, p))
    ps = 1.0 / (1.0 + np.exp(-(0.4 * X[:, 0] - 0.25 * X[:, 1] + 0.15 * X[:, 2])))
    D = rng.binomial(1, ps)
    Y = 1.0 * D + X[:, 0] + 0.5 * X[:, 1] + 0.25 * X[:, 2] + rng.normal(size=n)
    df = pd.DataFrame(X, columns=[f"x{j + 1}" for j in range(p)])
    df["d"] = D.astype(int)
    df["y"] = Y
    cols = [c for c in df.columns if c.startswith("x")]
    folds = _folds(n)
    clf = LogisticRegression(penalty=None, max_iter=1000)
    res = sp.dml(
        df,
        y="y",
        treat="d",
        covariates=cols,
        model="irm",
        ml_g=LinearRegression(),
        ml_m=clone(clf),
        n_folds=5,
        fold_indices=folds,
        score=score,
    )
    data = doubleml.DoubleMLData(df, y_col="y", d_cols="d", x_cols=cols)
    obj = doubleml.DoubleMLIRM(
        data,
        ml_g=LinearRegression(),
        ml_m=clone(clf),
        n_folds=5,
        score=score,
        draw_sample_splitting=False,
    )
    idx = np.arange(n)
    obj.set_sample_splitting(
        [[(idx[folds != k], idx[folds == k]) for k in sorted(np.unique(folds))]]
    )
    obj.fit()
    assert abs(res.estimate - float(np.ravel(obj.coef)[0])) < 1e-10
    assert abs(res.se - float(np.ravel(obj.se)[0])) < 1e-10


def test_ivtype_matches_doubleml_with_lasso_on_shared_folds(data):
    df, X, folds = data
    learner = _lasso_cv()
    res = sp.dml(
        df,
        y="y",
        treat="d",
        covariates=X,
        model="plr",
        ml_g=learner,
        ml_m=_lasso_cv(),
        n_folds=5,
        fold_indices=folds,
        score="IV-type",
    )
    ref_coef, ref_se = _doubleml_ivtype(df, X, folds, learner)
    assert abs(res.estimate - ref_coef) < 1e-8, (res.estimate, ref_coef)
    assert abs(res.se - ref_se) < 1e-8, (res.se, ref_se)
    # And it is a genuinely different estimator from partialling out here.
    po = sp.dml(
        df,
        y="y",
        treat="d",
        covariates=X,
        model="plr",
        ml_g=_lasso_cv(),
        ml_m=_lasso_cv(),
        n_folds=5,
        fold_indices=folds,
    )
    assert abs(po.estimate - res.estimate) > 1e-6

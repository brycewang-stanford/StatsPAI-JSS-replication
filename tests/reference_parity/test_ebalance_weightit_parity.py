"""``sp.ebalance`` ATT and standard error vs R ``WeightIt`` 1.7.0.

Until 1.31 the entropy-balancing standard error was a weighted two-sample
variance that held the weights fixed. That ignores what entropy balancing
does: the weights equalise the covariate moments exactly, so outcome
variation explained by those covariates cancels out of the ATT. On the
Track B design the old SE was twice the Monte Carlo SD of the estimator
(coverage 1.000, size 0.000 at the tested null) -- conservative, but not a
valid variance. The default is now the M-estimation sandwich of the stacked
estimating equations, the variance ``WeightIt::lm_weightit(vcov = "asympt")``
reports for ``weightit(method = "ebal", estimand = "ATT")``.

Fixture: ``_fixtures/ebalance_weightit_R.json`` from
``_fixtures/_generate_ebalance_weightit_R.R`` (two simulated
selection-on-observables designs at moments 1-3, and the public
``MatchIt::lalonde`` extract).
"""

from __future__ import annotations

import json
import pathlib
import warnings

import numpy as np
import pandas as pd
import pytest

import statspai as sp

_FIX = pathlib.Path(__file__).parent / "_fixtures"
REF = json.loads((_FIX / "ebalance_weightit_R.json").read_text(encoding="utf-8"))
CASES = sorted(k for k in REF if not k.startswith("_"))


def _fit(key, **kw):
    c = REF[key]
    df = pd.read_csv(_FIX / c["data"])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return c, sp.ebalance(
            df, y="y", treat="d", covariates=c["covariates"], moments=c["moments"], **kw
        )


@pytest.mark.parametrize("key", CASES)
def test_att_matches_weightit(key):
    c, r = _fit(key)
    assert abs(r.estimate - c["att"]) / abs(c["att"]) < 1e-9


@pytest.mark.parametrize("key", CASES)
def test_mestimation_se_matches_weightit(key):
    # Both sides solve the dual to ~1e-10; the sandwich inherits that.
    c, r = _fit(key)
    assert r.model_info["vce"] == "mestimation"
    assert abs(r.se - c["se"]) / c["se"] < 1e-7


def test_naive_se_is_the_old_formula_and_is_larger_here():
    c, r_new = _fit("sim_cia_m1")
    _, r_old = _fit("sim_cia_m1", vce="naive")
    assert r_old.estimate == r_new.estimate
    assert r_old.model_info["vce"] == "naive"
    # The covariates explain most of the outcome variance in this design, so
    # holding the weights fixed roughly doubles the standard error.
    assert r_old.se > 1.8 * r_new.se


def test_unknown_vce_raises():
    c = REF["sim_cia_m1"]
    df = pd.read_csv(_FIX / c["data"])
    with pytest.raises(sp.exceptions.MethodIncompatibility):
        sp.ebalance(df, y="y", treat="d", covariates=c["covariates"], vce="hc1")


@pytest.mark.slow
def test_coverage_is_nominal_on_the_track_b_design():
    """Known-truth guard: 400 draws of the Track B DGP (ATT = 2).

    With the old SE the interval covered 100% of the time; the corrected
    SE should sit near 95%, and its mean should be near the Monte Carlo SD.
    """
    est, se, cov = [], [], 0
    for seed in range(400):
        rng = np.random.default_rng(seed)
        n = 500
        x1, x2 = rng.normal(size=n), rng.normal(size=n)
        p = 1 / (1 + np.exp(-(-0.3 + 0.5 * x1 - 0.3 * x2)))
        d = (rng.uniform(0, 1, n) < p).astype(int)
        y = 1.0 + 1.5 * x1 - 0.8 * x2 + 2.0 * d + rng.normal(scale=0.8, size=n)
        r = sp.ebalance(
            pd.DataFrame({"y": y, "d": d, "X1": x1, "X2": x2}),
            y="y",
            treat="d",
            covariates=["X1", "X2"],
        )
        est.append(r.estimate)
        se.append(r.se)
        cov += r.ci[0] <= 2.0 <= r.ci[1]
    ratio = np.mean(se) / np.std(est, ddof=1)
    assert 0.9 < ratio < 1.1
    assert 0.92 <= cov / 400 <= 0.98

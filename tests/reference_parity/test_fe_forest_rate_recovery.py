"""Known-truth Monte Carlo for the FE-forest RATE (T1).

``tau = 0.3 + b z`` with ``z`` standard normal and independent of adoption,
so the population curve is analytic: ranking by ``z`` gives
``TOC(q) = b phi(Phi^-1(1 - q)) / q``, hence

* ``AUTOC = b * int phi(u)^2 / Phi(-u) du = 0.9031972855686256 b``
* ``QINI  = b * int phi(u)^2 du = b / (2 sqrt(pi)) = 0.28209479177387825 b``

and ``b = 0`` makes both exactly 0 for *any* ranking, which is what turns
the alternative into a size study for the heterogeneity test.

Three claims are pinned here, all measured at 200 replications and
tabulated in ``docs/guides/heterogeneity_panel_forests.md``:

1. with a held-out ranking the estimator is unbiased for the population
   RATE and ``variance="bjs"`` covers it (97.5% at 200 replications;
   ``variance="forest"`` is calibrated for the *sample's* RATE instead and
   covered the population one 90.8% of the time -- it is not the default);
2. ranking the treated cells by the forest's own out-of-bag predictions
   and scoring them on the same sample is biased: AUTOC averaged -0.025
   under no heterogeneity at all and rejected 17.5% of the time;
3. ``sp.rate_split`` removes that: +0.0008 and 7.5%, at 99.5% power.

These runs use ``n_splits=1``: the claim under test is the bias of one
split's evaluation against the reused ranking, and aggregating over splits
would average away the quantity being measured.

``REPS`` is cut to 40 here (binomial sd ~3.4 points at a 5% rate), so the
bands are wide enough for that Monte Carlo error and only the signs and
orders of magnitude are asserted.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

import statspai as sp

REPS = 40
N_UNITS, N_PERIODS, SIGMA = 150, 8, 0.6
AUTOC_COEF = 0.9031972855686256
QINI_COEF = 0.28209479177387825


def _dgp(seed: int, b: float) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(N_UNITS):
        a, z, w = rng.normal(), rng.normal(), rng.normal()
        never = i % 5 == 0
        g = 10**6 if never else int(np.clip(4 + round(a), 3, N_PERIODS + 1))
        for t in range(1, N_PERIODS + 1):
            d = 1.0 * (t >= g)
            y = a + 0.25 * t + (0.3 + b * z) * d + rng.normal(0, SIGMA)
            rows.append((i, t, y, d, z, w))
    return pd.DataFrame(rows, columns=["id", "t", "y", "d", "z", "w"])


def _run(b: float) -> pd.DataFrame:
    rows = []
    for s in range(REPS):
        df = _dgp(s, b)
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
                random_state=s,
            )
            record = {}
            for target, coef in (("AUTOC", AUTOC_COEF), ("QINI", QINI_COEF)):
                truth = b * coef
                held = sp.rate(cf, target=target, priorities=df["z"].to_numpy())
                forest_var = sp.rate(
                    cf,
                    target=target,
                    priorities=df["z"].to_numpy(),
                    variance="forest",
                )
                reused = sp.rate(cf, target=target)
                split = sp.rate_split(cf, target=target, n_splits=1, random_state=s)
                record.update(
                    {
                        f"{target}_held_err": held["estimate"] - truth,
                        f"{target}_held_cov": held["ci_low"]
                        <= truth
                        <= held["ci_high"],
                        f"{target}_forestvar_cov": forest_var["ci_low"]
                        <= truth
                        <= forest_var["ci_high"],
                        f"{target}_reused_est": reused["estimate"],
                        f"{target}_reused_rej": (reused["ci_low"] > 0)
                        | (reused["ci_high"] < 0),
                        f"{target}_split_est": split["estimate"],
                        f"{target}_split_rej": (split["ci_low"] > 0)
                        | (split["ci_high"] < 0),
                    }
                )
        rows.append(record)
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def null_runs():
    return _run(b=0.0).mean()


@pytest.fixture(scope="module")
def alternative_runs():
    return _run(b=0.5).mean()


@pytest.mark.slow
@pytest.mark.parametrize("target", ["AUTOC", "QINI"])
def test_held_out_ranking_recovers_the_population_rate(alternative_runs, target):
    m = alternative_runs
    scale = 0.5 * (AUTOC_COEF if target == "AUTOC" else QINI_COEF)
    assert abs(m[f"{target}_held_err"]) < 0.1 * scale
    assert m[f"{target}_held_cov"] >= 0.88


@pytest.mark.slow
def test_bjs_covers_the_population_rate_better_than_forest_centring(
    alternative_runs,
):
    # Why 'bjs' is the default for rate(): 'forest' nets the heterogeneity
    # out of the residual, which is right for the RATE of this sample and
    # too tight for the population's.
    m = alternative_runs
    assert m["AUTOC_held_cov"] > m["AUTOC_forestvar_cov"]
    assert m["AUTOC_forestvar_cov"] < 0.95


@pytest.mark.slow
@pytest.mark.parametrize("target", ["AUTOC", "QINI"])
def test_reusing_the_ranking_is_biased_and_oversized(null_runs, target):
    m = null_runs
    assert m[f"{target}_reused_est"] < 0  # the -gamma_hat_t channel
    assert m[f"{target}_reused_rej"] > 0.10  # nominal 5%


@pytest.mark.slow
@pytest.mark.parametrize("target", ["AUTOC", "QINI"])
def test_rate_split_is_unbiased_and_sized_under_the_null(null_runs, target):
    m = null_runs
    assert abs(m[f"{target}_split_est"]) < abs(m[f"{target}_reused_est"])
    assert abs(m[f"{target}_split_est"]) < 0.02
    assert m[f"{target}_split_rej"] <= 0.15
    assert m[f"{target}_split_rej"] < m[f"{target}_reused_rej"]


@pytest.mark.slow
@pytest.mark.parametrize("target", ["AUTOC", "QINI"])
def test_rate_split_keeps_its_power(alternative_runs, target):
    assert alternative_runs[f"{target}_split_rej"] >= 0.9

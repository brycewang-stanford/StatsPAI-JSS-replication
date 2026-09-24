"""Reference parity: ``sp.causal_forest`` ATE vs R ``grf::causal_forest``.

Both engines report the **AIPW doubly-robust** average treatment effect
(``grf::average_treatment_effect`` on the R side;
``sp.causal_forest.average_treatment_effect`` on the Python side), so
the comparison is like-for-like.  The two implementations use different
RNGs, so a single fit on each side is one draw from each engine's
algorithmic distribution *given the data*.

What this file checks is deliberately weak: one draw each, compared on the
scale of the ATE's **sampling** standard error. That is a plausibility
screen, not an equivalence test -- the sampling SE describes variation
across datasets, not the forest's own Monte Carlo error on fixed data, and
the two single draws share the data, so their sampling errors are not
independent. The algorithmic comparison proper -- many seeds per engine on
fixed data, tree-count scaling, and an equivalence margin -- is
``test_grf_seed_mc_equivalence.py``.

This replaces the previous test, which compared the *plug-in* mean of
the CATE predictions (``cf.ate()``) against grf's AIPW estimate with a
25% tolerance.  The plug-in average is a regularised CATE-summary
convenience path, not grf's doubly-robust AIPW estimand, so that
comparison both used the wrong estimator and needed a band too wide to
be called validation.  The plug-in path is still exercised below as a
documented sanity check, not as the parity claim.

References
----------
- Athey, S., Tibshirani, J. and Wager, S. (2019). Generalized random
  forests. *Annals of Statistics*, 47(2), 1148-1178.
  [@athey2019generalized]
"""

from __future__ import annotations

import json
import math
import pathlib

import numpy as np
import pandas as pd
import pytest

import statspai as sp

_FIXTURE_DIR = pathlib.Path(__file__).parent / "_fixtures"


@pytest.fixture(scope="module")
def grf_data():
    return pd.read_csv(_FIXTURE_DIR / "grf_data.csv")


@pytest.fixture(scope="module")
def r_reference():
    with open(_FIXTURE_DIR / "grf_R.json") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def fitted_cf(grf_data):
    """Fit once per module -- causal forests are slow."""
    return sp.causal_forest(
        "y ~ W | X1 + X2 + X3 + X4 + X5",
        data=grf_data,
        n_estimators=2000,
        random_state=42,
        discrete_treatment=True,
    )


def test_grf_ate_aipw_single_draw_screen(fitted_cf, r_reference):
    """One sp draw and one grf draw differ by far less than the sampling SE.

    A screen, not an equivalence claim (module docstring): the threshold is
    a quarter of grf's reported ATE standard error, which is ~20x the
    seed-to-seed spread of either engine at 2,000 trees.
    """
    aipw = fitted_cf.average_treatment_effect(target_sample="all")
    assert aipw["method"] == "aipw", "headline ATE must use the AIPW score"
    py_ate = float(aipw["estimate"])
    r_ate, r_se = r_reference["ate"]["estimate"], r_reference["ate"]["se"]
    gap = abs(py_ate - r_ate) / r_se
    assert gap < 0.25, (
        f"sp AIPW ATE={py_ate:.4f} vs grf AIPW ATE={r_ate:.4f}: "
        f"{gap:.2f} sampling SEs apart (screen threshold 0.25). Investigate "
        f"the AIPW score or the nuisance cross-fitting, then the seed-"
        f"replicated comparison in test_grf_seed_mc_equivalence.py."
    )


def test_grf_ate_sign_agreement(fitted_cf, r_reference):
    """Both engines agree on the sign of the AIPW ATE."""
    py_ate = float(fitted_cf.average_treatment_effect(target_sample="all")["estimate"])
    r_ate = r_reference["ate"]["estimate"]
    assert (py_ate > 0) == (r_ate > 0), (
        f"Sign disagreement is a serious red flag: "
        f"Python AIPW ATE={py_ate:.4f}, R AIPW ATE={r_ate:.4f}"
    )


def test_grf_aipw_recovers_grf_ci(fitted_cf, r_reference):
    """sp AIPW point estimate lies inside grf's 95% CI (and vice versa).

    A weaker, asymmetric cross-check that does not depend on the sp SE.
    """
    py_ate = float(fitted_cf.average_treatment_effect(target_sample="all")["estimate"])
    r_ate, r_se = r_reference["ate"]["estimate"], r_reference["ate"]["se"]
    lo, hi = r_ate - 1.96 * r_se, r_ate + 1.96 * r_se
    assert (
        lo <= py_ate <= hi
    ), f"sp AIPW ATE={py_ate:.4f} outside grf 95% CI [{lo:.4f}, {hi:.4f}]"


def test_grf_plugin_is_documented_convenience_estimand(fitted_cf, r_reference):
    """Documents (does not validate) the plug-in CATE average path.

    ``float(cf.ate())`` is the doubly-robust (AIPW) estimate its SE / CI
    describe; the mean of the CATE predictions is kept as a convenience in
    ``detail["plug_in_estimate"]`` but is NOT the parity estimand. This test
    asserts that the plug-in remains a distinct, finite CATE-summary path so a
    regression that silently aliases it to the AIPW estimand is caught,
    without treating the plug-in mean as validated.
    """
    ate = fitted_cf.ate()
    plug_in = float(ate.detail["plug_in_estimate"])
    detail = fitted_cf.average_treatment_effect(target_sample="all")
    aipw = float(detail["estimate"])
    assert float(ate) == pytest.approx(aipw, abs=1e-12)
    assert math.isfinite(plug_in)
    # The plug-in path is the mean of the out-of-bag CATE predictions ...
    assert plug_in == pytest.approx(float(fitted_cf.predict().mean()), abs=1e-12)
    # ... and the AIPW path adds the doubly-robust correction on top of it.
    assert detail["method"] == "aipw"
    scores_mean = float(
        np.mean(
            fitted_cf.predict()
            + (fitted_cf._T_original - np.clip(fitted_cf._e_insample, 0.01, 0.99))
            / (
                np.clip(fitted_cf._e_insample, 0.01, 0.99)
                * (1 - np.clip(fitted_cf._e_insample, 0.01, 0.99))
            )
            * (
                fitted_cf._Y_original
                - fitted_cf._m_insample
                - (fitted_cf._T_original - np.clip(fitted_cf._e_insample, 0.01, 0.99))
                * fitted_cf.predict()
            )
        )
    )
    assert aipw == pytest.approx(scores_mean, abs=1e-12)
    # With a well-fitted forest the two are close but not identical.
    assert abs(plug_in - aipw) < 0.25


def test_grf_fixture_meta(r_reference):
    assert "meta" in r_reference
    assert r_reference["meta"]["seed"] == 42
    assert r_reference["meta"]["num_trees"] == 2000


def test_grf_fixture_n(grf_data):
    assert len(grf_data) == 1000

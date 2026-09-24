"""Statistical parity (tier T3): the GRF engine vs ``grf::causal_forest``.

Two causal forests with independent random streams never produce the same
predictions, so this is graded against Monte Carlo variation, not a
relative band on a single number.  On two designs with a known CATE (i.i.d.
and clustered; see ``_fixtures/_generate_grf_engine_data.py``) grf 2.6.1 was
run with three seeds (``_fixtures/_generate_grf_engine.R``).  StatsPAI's
default forest (2000 trees) must match grf in what the estimator is *for*:

========================================  ==============  ================
quantity                                  observed         gate
========================================  ==============  ================
RMSE of OOB CATE vs truth, sp / grf       0.998 / 1.017    [0.92, 1.08]
median sp / grf pointwise variance        1.012 / 0.939    [0.80, 1.25]
pointwise 95% CI coverage, sp - grf       +0.007 / -0.010  |.| <= 0.05
mean abs(sp - grf) / grf RMSE             0.070 / 0.077    <= 0.15
AIPW ATE difference / grf SE              0.04 / 0.01      <= 0.5
AIPW ATE SE ratio                         1.00 / 1.00      [0.95, 1.05]
========================================  ==============  ================

(observed = i.i.d. / clustered, averaged over three sp and three grf seeds
at calibration time; the gates leave room for one sp seed.)  The operator
layer -- scores, calibration, averages, covariances given the forest -- is
pinned exactly in ``test_grf_cluster_operator_parity.py``; what remains here
is the forest itself.

Regenerate with::

    python tests/reference_parity/_fixtures/_generate_grf_engine_data.py
    Rscript tests/reference_parity/_fixtures/_generate_grf_engine.R
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd
import pytest

import statspai as sp

_DIR = pathlib.Path(__file__).parent / "_fixtures"
_CSV = _DIR / "grf_engine_data.csv"
_JSON = _DIR / "grf_engine_R.json"

pytestmark = pytest.mark.skipif(
    not (_CSV.exists() and _JSON.exists()),
    reason="grf engine fixture is not materialized",
)


@pytest.fixture(scope="module")
def ref():
    return json.loads(_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module", params=["iid", "clustered"])
def fitted(request):
    df = pd.read_csv(_CSV)
    d = df[df["design"] == request.param].reset_index(drop=True)
    X = d[[f"x{j}" for j in range(1, 6)]].to_numpy()
    cf = sp.causal_forest(
        Y=d["Y"].to_numpy(),
        T=d["W"].to_numpy(),
        X=X,
        clusters=d["cluster"].to_numpy() if request.param == "clustered" else None,
        random_state=5,
    )
    return request.param, d, cf


def _grf_runs(ref, design):
    return list(ref[design].values())


def test_cate_accuracy_matches_grf(fitted, ref):
    design, d, cf = fitted
    tau = d["tau"].to_numpy()
    sp_rmse = float(np.sqrt(np.mean((cf.predict() - tau) ** 2)))
    grf_rmse = float(
        np.mean(
            [
                np.sqrt(np.mean((np.asarray(r["tau"]) - tau) ** 2))
                for r in _grf_runs(ref, design)
            ]
        )
    )
    assert 0.92 <= sp_rmse / grf_rmse <= 1.08, (design, sp_rmse, grf_rmse)


def test_pointwise_predictions_close_to_grf(fitted, ref):
    design, d, cf = fitted
    tau = d["tau"].to_numpy()
    runs = _grf_runs(ref, design)
    grf_rmse = float(
        np.mean([np.sqrt(np.mean((np.asarray(r["tau"]) - tau) ** 2)) for r in runs])
    )
    dist = float(
        np.mean([np.mean(np.abs(cf.predict() - np.asarray(r["tau"]))) for r in runs])
    )
    assert dist / grf_rmse <= 0.15, (design, dist, grf_rmse)


def test_variance_estimates_match_grf(fitted, ref):
    design, d, cf = fitted
    tau = d["tau"].to_numpy()
    v = cf.effect_variance()
    runs = _grf_runs(ref, design)
    ratio = float(np.median(np.concatenate([v / np.asarray(r["var"]) for r in runs])))
    assert 0.80 <= ratio <= 1.25, (design, ratio)
    sp_cov = float(np.mean(np.abs(cf.predict() - tau) <= 1.959964 * np.sqrt(v)))
    grf_cov = float(
        np.mean(
            [
                np.mean(
                    np.abs(np.asarray(r["tau"]) - tau)
                    <= 1.959964 * np.sqrt(np.asarray(r["var"]))
                )
                for r in runs
            ]
        )
    )
    assert abs(sp_cov - grf_cov) <= 0.05, (design, sp_cov, grf_cov)


def test_aipw_ate_matches_grf(fitted, ref):
    design, d, cf = fitted
    res = cf.average_treatment_effect()
    runs = _grf_runs(ref, design)
    grf_ate = float(np.mean([r["ate"] for r in runs]))
    grf_se = float(np.mean([r["ate_se"] for r in runs]))
    assert abs(res["estimate"] - grf_ate) <= 0.5 * grf_se, (design, res, grf_ate)
    assert 0.95 <= res["se"] / grf_se <= 1.05, (design, res["se"], grf_se)

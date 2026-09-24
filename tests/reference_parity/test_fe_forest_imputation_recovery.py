"""Known-truth Monte Carlo for FE-forest imputation inference (T1).

Staggered adoption selected on the unit effect (cohorts 3, 5, 7 plus
never-treated; N = 300 units, T = 8), effects ``(1 + x1)(1 + 0.2 e)`` that
vary with a covariate and with exposure ``e``, or a constant effect.  No
cross-package reference implements the forest on the same bytes, so the
evidence is recovery of the known finite-sample targets (the mean true
effect over treated cells, overall and by ``x1 > 0``):

* the imputation ATT is unbiased (|mean error| < 0.03) while the mean
  forest prediction is shrunk (bias < -0.1) under heterogeneity;
* 95% intervals for the ATT and the group ATTs cover at least 88% of the
  time (``variance="forest"``) -- a band that allows for the Monte Carlo
  error of 60 replications (binomial sd ~2.8 points);
* the imputation calibration test rejects a constant effect at most 15% of
  the time and detects the heterogeneous one in at least 90% of runs.

The 200-replication version of this design is tabulated in
``docs/guides/heterogeneity_panel_forests.md`` (section 3).
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

import statspai as sp

REPS = 60


def _dgp(seed, het):
    r = np.random.default_rng(seed)
    N, T = 300, 8
    x1 = r.normal(size=N)
    x2 = r.normal(size=N)
    alpha = x1 + r.normal(size=N)
    p = np.exp(alpha) / (1 + np.exp(alpha))
    coh = np.where(r.random(N) < p, r.choice([3, 5, 7], size=N), 99)
    gam = np.cumsum(r.normal(0, 0.5, size=T))
    uid = np.repeat(np.arange(N), T)
    t = np.tile(np.arange(T), N)
    d = (t >= coh[uid]).astype(float)
    e = np.maximum(t - coh[uid], 0)
    tau = (1 + x1[uid]) * (1 + 0.2 * e) if het else np.ones(N * T)
    y = alpha[uid] + gam[t] + tau * d + r.normal(size=N * T)
    return pd.DataFrame(
        {"id": uid, "t": t, "y": y, "d": d, "x1": x1[uid], "x2": x2[uid], "tau": tau}
    )


def _run(het):
    rows = []
    for s in range(REPS):
        df = _dgp(s, het)
        cf = sp.causal_forest(
            data=df,
            y="y",
            d="d",
            x=["x1", "x2"],
            id="id",
            time="t",
            fe="twoway",
            n_estimators=300,
            random_state=s,
        )
        tr = df["d"].to_numpy() == 1
        truth = df["tau"].to_numpy()[tr].mean()
        att = cf.average_treatment_effect("treated")
        g = (df["x1"] > 0).to_numpy()
        ge = sp.forest_group_effects(cf, by=g)
        tg = df.loc[tr].groupby(g[tr])["tau"].mean().to_numpy()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            cal = sp.calibration_test(cf)
        rows.append(
            {
                "err": att["estimate"] - truth,
                "plug_err": att["forest_plug_in"] - truth,
                "cov": att["ci_low"] <= truth <= att["ci_high"],
                "gcov": np.mean((ge["ci_low"] <= tg) & (tg <= ge["ci_high"])),
                "rej": cal.loc["differential_forest_prediction", "p_one_sided"] < 0.05,
            }
        )
    return pd.DataFrame(rows).mean()


@pytest.mark.slow
def test_heterogeneous_effects_recovered_and_covered():
    m = _run(het=True)
    assert abs(m["err"]) < 0.03
    assert m["plug_err"] < -0.1
    assert m["cov"] >= 0.88
    assert m["gcov"] >= 0.88
    assert m["rej"] >= 0.9


@pytest.mark.slow
def test_constant_effect_size_and_coverage():
    m = _run(het=False)
    assert abs(m["err"]) < 0.03
    assert m["cov"] >= 0.88
    assert m["gcov"] >= 0.88
    assert m["rej"] <= 0.15

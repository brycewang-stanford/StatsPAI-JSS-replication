"""Reference parity: ``sp.did(method="2x2", vce="wild")`` vs Stata boottest.

The WCR wild cluster bootstrap on the 2x2 DID interaction regression is THE
canonical few-clusters DID inference (MacKinnon-Webb 2017). It runs the SAME
verified engine as ``sp.regress(vce="wild")`` on the interaction design
``[1, D, T, DxT]``, so it is byte-identical to regress-wild with the same
seed, and is validated against Stata::

    reg y d t dt, vce(cluster gid)      // b_dt = 0.0257697520
    boottest dt, reps(9999) weighttype(rademacher)
    // enumerated (2^12 = 4096): p = 0.81640625

Our engine samples ``wild_reps`` draws (no enumeration), so the p-value is
asserted within Monte-Carlo error of the enumerated Stata value
(sd ~ sqrt(p(1-p)/B) ~ 0.004 at B=9999; observed |diff| = 0.0022).
Staggered methods refuse ``vce=`` loudly (Callaway-Sant'Anna has its own
influence-function multiplier bootstrap — itself the wild bootstrap for that
estimator, per CS 2021 §4.1).
"""

import numpy as np
import pandas as pd
import pytest

from statspai.did import did
from statspai.regression.ols import regress

STATA_B_DT = 0.0257697520
BOOTTEST_P = 0.81640625  # enumerated 2^12


def _did_panel() -> pd.DataFrame:
    rng = np.random.default_rng(11)
    g, n_per = 12, 30
    gid = np.repeat(np.arange(g), n_per * 2)
    treat_g = (np.arange(g) < 6).astype(float)
    d = treat_g[gid]
    t = np.tile(np.concatenate([np.zeros(n_per), np.ones(n_per)]), g)
    ce = rng.normal(0, 0.6, g)[gid]
    yv = 1.0 + 0.4 * d + 0.3 * t + 0.25 * d * t + ce + rng.normal(0, 1, len(gid))
    return pd.DataFrame({"y": yv, "d": d.astype(int), "t": t.astype(int), "gid": gid})


def test_did2x2_wild_matches_boottest_within_mc_error() -> None:
    df = _did_panel()
    r = did(
        df,
        y="y",
        treat="d",
        time="t",
        method="2x2",
        cluster="gid",
        vce="wild",
        wild_reps=9999,
        seed=42,
    )
    assert np.isclose(r.estimate, STATA_B_DT, atol=1e-7)
    assert abs(r.pvalue - BOOTTEST_P) < 0.02  # MC error at B=9999
    assert "wild cluster bootstrap" in r.model_info["inference"]


def test_did2x2_wild_byte_identical_to_regress_wild() -> None:
    df = _did_panel()
    r = did(
        df,
        y="y",
        treat="d",
        time="t",
        method="2x2",
        cluster="gid",
        vce="wild",
        wild_reps=999,
        seed=7,
    )
    df2 = df.assign(dt=df["d"] * df["t"])
    rr = regress("y ~ d + t + dt", df2, vce="wild", cluster="gid", seed=7)
    assert float(r.pvalue) == float(rr.pvalues["dt"])


def test_did_staggered_refuses_vce() -> None:
    df = _did_panel()
    with pytest.raises(Exception):
        did(df, y="y", treat="d", time="t", id="gid", method="cs", vce="wild")
    with pytest.raises(Exception):
        did(df, y="y", treat="d", time="t", method="2x2", vce="wild")  # no cluster

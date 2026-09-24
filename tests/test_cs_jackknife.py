"""Tests for sp.cs_jackknife, the CV3 cluster jackknife for Callaway-Sant'Anna.

Reference parity (R didjack / Stata csdidjack on the castle-doctrine panel)
lives in ``test_cs_jackknife_reference.py``; this file pins the definition
and the failure modes.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

import statspai as sp
from statspai.exceptions import DataInsufficient, MethodIncompatibility


def _panel(n_units: int = 30, seed: int = 0, cohorts=(0, 3, 4)) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for u in range(n_units):
        g = cohorts[u % len(cohorts)]
        a = rng.normal()
        for t in range(1, 7):
            d = 1.0 if g and t >= g else 0.0
            rows.append((u, t, g, u // 3, a + 0.2 * t + 0.5 * d + rng.normal(0, 0.3)))
    return pd.DataFrame(rows, columns=["unit", "time", "g", "block", "y"])


def _manual_cv3(df, cluster, **kw):
    """Brute-force CV3 from its definition, independent of cs_jackknife."""
    full = sp.aggte(
        sp.callaway_santanna(df, y="y", g="g", t="time", i="unit", **kw),
        type="simple",
        bstrap=False,
        cband=False,
    ).estimate
    atts = []
    for c in sorted(df[cluster].unique()):
        sub = df[df[cluster] != c]
        fit = sp.callaway_santanna(sub, y="y", g="g", t="time", i="unit", **kw)
        atts.append(sp.aggte(fit, type="simple", bstrap=False, cband=False).estimate)
    atts = np.asarray(atts)
    r = len(atts)
    return full, np.sqrt((r - 1) / r * np.sum((atts - full) ** 2)), atts


def test_cv3_matches_definition_unit_clusters():
    df = _panel()
    jk = sp.cs_jackknife(df, y="y", g="g", t="time", i="unit", estimator="reg")
    full, se, atts = _manual_cv3(df, "unit", estimator="reg")
    assert jk.estimate == pytest.approx(full, rel=1e-12)
    assert jk.se == pytest.approx(se, rel=1e-12)
    np.testing.assert_allclose(jk.detail["att"].to_numpy(), atts, rtol=1e-12)
    assert jk.model_info["n_replicates"] == 30
    assert jk.model_info["df"] == 29
    assert jk.model_info["se_method"] == "cluster_jackknife"


def test_ci_and_pvalue_use_t_with_r_minus_1_df():
    from scipy import stats

    df = _panel()
    jk = sp.cs_jackknife(df, y="y", g="g", t="time", i="unit", estimator="reg")
    crit = stats.t.ppf(0.975, 29)
    assert jk.ci[0] == pytest.approx(jk.estimate - crit * jk.se, rel=1e-12)
    assert jk.ci[1] == pytest.approx(jk.estimate + crit * jk.se, rel=1e-12)
    tstat = jk.estimate / jk.se
    assert jk.pvalue == pytest.approx(2 * stats.t.sf(abs(tstat), 29), rel=1e-12)


def test_coarser_cluster_variable():
    df = _panel()
    jk = sp.cs_jackknife(
        df, y="y", g="g", t="time", i="unit", cluster="block", estimator="reg"
    )
    full, se, _ = _manual_cv3(df, "block", estimator="reg")
    assert jk.model_info["n_replicates"] == 10
    assert jk.se == pytest.approx(se, rel=1e-12)


@pytest.mark.parametrize("agg", ["dynamic", "group", "calendar"])
def test_other_aggregations_jackknife_the_aggte_overall(agg):
    df = _panel()
    jk = sp.cs_jackknife(
        df, y="y", g="g", t="time", i="unit", type=agg, estimator="reg"
    )
    fit = sp.callaway_santanna(df, y="y", g="g", t="time", i="unit", estimator="reg")
    ref = sp.aggte(fit, type=agg, bstrap=False, cband=False)
    assert jk.estimate == pytest.approx(ref.estimate, rel=1e-12)
    assert jk.model_info["analytic_se"] == pytest.approx(ref.se, rel=1e-12)
    assert jk.se > 0


def test_single_treated_cluster_is_skipped():
    # Only unit 1 is ever treated; the references skip its cluster.
    df = _panel(n_units=12, cohorts=(0,))
    df.loc[df["unit"] == 1, "g"] = 4
    df.loc[(df["unit"] == 1) & (df["time"] >= 4), "y"] += 0.5
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        jk = sp.cs_jackknife(df, y="y", g="g", t="time", i="unit", estimator="reg")
    assert jk.model_info["single_treated_cluster"] is True
    assert jk.model_info["skipped_clusters"] == [1]
    assert jk.model_info["n_replicates"] == 11
    assert 1 not in set(jk.detail["deleted_cluster"])


@pytest.mark.parametrize(
    "kw", [{"bstrap": True}, {"cband": True}, {"se_method": "multiplier"}]
)
def test_inference_options_are_rejected(kw):
    with pytest.raises(MethodIncompatibility):
        sp.cs_jackknife(_panel(), y="y", g="g", t="time", i="unit", **kw)


def test_bad_type_rejected():
    with pytest.raises(MethodIncompatibility):
        sp.cs_jackknife(_panel(), y="y", g="g", t="time", i="unit", type="event")


def test_time_varying_cluster_rejected():
    df = _panel()
    df["block"] = df["time"]
    with pytest.raises(MethodIncompatibility):
        sp.cs_jackknife(df, y="y", g="g", t="time", i="unit", cluster="block")


def test_deleting_the_only_never_treated_unit_fails_loudly():
    df = _panel(n_units=10, cohorts=(3, 4))
    df.loc[df["unit"] == 0, "g"] = 0
    with pytest.raises(DataInsufficient, match="deleting cluster"):
        sp.cs_jackknife(
            df, y="y", g="g", t="time", i="unit", control_group="nevertreated"
        )


def test_registered_and_cites_verified_key():
    assert "cs_jackknife" in sp.list_functions()
    jk = sp.cs_jackknife(_panel(), y="y", g="g", t="time", i="unit", estimator="reg")
    assert "karim2026improved" in jk.cite()

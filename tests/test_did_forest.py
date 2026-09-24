"""``sp.did_forest``: difference-in-differences causal forests.

Known-truth (tier T1) checks:

* a staggered panel whose effect grows with exposure and varies with a
  covariate that also drives adoption and the untreated trend (conditional
  parallel trends);
* (the simulation design of Gavrilova, Langorgen and Zoutman (2025,
  Appendix C) lives in
  ``tests/reference_parity/test_panel_forest_recovery.py``).

plus exact aggregation identities and the input contracts.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

import statspai as sp
from statspai.exceptions import (
    AssumptionWarning,
    DataInsufficient,
    MethodIncompatibility,
)


def _staggered(N=800, T=7, seed=0):
    rng = np.random.default_rng(seed)
    x1 = rng.normal(size=N)
    x2 = rng.normal(size=N)
    alpha = x1 + rng.normal(size=N)
    g = np.where(rng.uniform(size=N) < 0.3, 0, rng.choice([4, 6], size=N))
    g = np.where((g > 0) & (rng.uniform(size=N) < 1 / (1 + np.exp(-x1))), 4, g)
    frames = []
    for t in range(1, T + 1):
        d = (g > 0) & (t >= g)
        tau = (1 + x1) * (1 + 0.25 * np.maximum(t - g, 0))
        y = alpha + 0.5 * t + 0.3 * x1 * t + d * tau + rng.normal(size=N)
        frames.append(
            pd.DataFrame(
                dict(
                    id=np.arange(N),
                    t=t,
                    g=g,
                    x1=x1,
                    x2=x2,
                    y=y,
                    tau=np.where(d, tau, np.nan),
                )
            )
        )
    return pd.concat(frames, ignore_index=True)


@pytest.fixture(scope="module")
def staggered():
    df = _staggered()
    res = sp.did_forest(
        df, y="y", id="id", time="t", cohort="g", x=["x1", "x2"], n_estimators=400
    )
    return df, res


class TestKnownTruth:
    def test_event_study_recovers_dynamic_effects(self, staggered):
        df, res = staggered
        treated = df[df["tau"].notna()].assign(e=lambda d: d["t"] - d["g"])
        truth = treated.groupby("e")["tau"].mean()
        es = res.event_study.set_index("event_time")
        for e, value in truth.items():
            row = es.loc[e]
            assert abs(row["att"] - value) < 3.5 * row["se"], (e, row["att"], value)

    def test_pre_periods_are_placebos(self, staggered):
        _, res = staggered
        pre = res.event_study[res.event_study["event_time"] < 0]
        assert len(pre) > 0
        assert np.all(np.abs(pre["att"]) < 3.5 * pre["se"])
        assert res.pretrend_test["pvalue"] > 0.001
        assert res.pretrend_test["df"] == len(pre)

    def test_unit_cates_track_the_true_effects(self, staggered):
        df, res = staggered
        merged = res.unit_cate.merge(
            df[["id", "t", "tau"]].rename(columns={"id": "unit", "t": "time"}),
            on=["unit", "time"],
        )
        assert len(merged) == int(df["tau"].notna().sum())
        assert np.corrcoef(merged["cate"], merged["tau"])[0, 1] > 0.9
        assert np.all(merged["cate_se"] > 0)

    def test_heterogeneity_is_detected(self, staggered):
        _, res = staggered
        post = res.att_gt[res.att_gt["event_time"] >= 0]
        assert (post["heterogeneity_p"] < 0.05).mean() >= 0.8


class TestAggregationIdentities:
    def test_event_study_is_the_cohort_size_weighted_mean(self, staggered):
        _, res = staggered
        for e, cells in res.att_gt.groupby("event_time"):
            w = cells["n_treated"] / cells["n_treated"].sum()
            expected = float((w * cells["att"]).sum())
            got = float(res.event_study.set_index("event_time").loc[e, "att"])
            assert got == pytest.approx(expected, abs=1e-12)

    def test_overall_is_the_treated_weighted_post_average(self, staggered):
        _, res = staggered
        post = res.att_gt[res.att_gt["event_time"] >= 0]
        w = post["n_treated"] / post["n_treated"].sum()
        assert res.overall["estimate"] == pytest.approx(
            float((w * post["att"]).sum()), abs=1e-12
        )

    def test_single_cell_event_time_keeps_the_cell_standard_error(self, staggered):
        _, res = staggered
        single = res.event_study[res.event_study["n_cells"] == 1]
        assert len(single) > 0
        for e in single["event_time"]:
            cell = res.att_gt[res.att_gt["event_time"] == e].iloc[0]
            es_se = float(single.set_index("event_time").loc[e, "se"])
            assert es_se == pytest.approx(float(cell["se"]), rel=1e-12)

    def test_cell_att_is_plug_in_plus_doubly_robust_correction(self, staggered):
        df, res = staggered
        cell = res.att_gt[res.att_gt["event_time"] == 0].iloc[0]
        forest = res.forest(cell["group"], cell["time"])
        tau = forest.predict()
        W = forest._T_original
        z = forest._Y_original
        e = np.clip(forest._e_insample, 0.0, 1.0 - 0.001)
        m = forest._m_insample
        gamma = np.where(W == 1, len(W) / W.sum(), 0.0)
        g_c = e[W == 0] / (1 - e[W == 0])
        gamma[W == 0] = g_c / g_c.sum() * len(W)
        corr = W * gamma * (z - (m + (1 - e) * tau)) - (1 - W) * gamma * (
            z - (m - e * tau)
        )
        expected = tau[W == 1].mean() + corr.mean()
        assert cell["att"] == pytest.approx(expected, abs=1e-12)

    def test_predict_cate_and_serialisation(self, staggered):
        df, res = staggered
        X = df[df["t"] == 1][["x1", "x2"]].to_numpy()[:25]
        surface = res.predict_cate(X, event_time=0)
        assert surface.shape == (25,)
        json.dumps(res.to_dict())
        assert "Overall ATT" in res.summary()


class TestContracts:
    def test_time_varying_covariates_are_refused(self):
        df = _staggered(N=200, T=5)
        df["x1"] = df["x1"] + df["t"]
        with pytest.raises(MethodIncompatibility, match="vary within unit"):
            sp.did_forest(
                df, y="y", id="id", time="t", cohort="g", x="x1", n_estimators=50
            )

    def test_cohort_must_be_constant_within_unit(self):
        df = _staggered(N=200, T=5)
        df.loc[df.index[:3], "g"] = 99
        with pytest.raises(MethodIncompatibility, match="cohort column varies"):
            sp.did_forest(
                df, y="y", id="id", time="t", cohort="g", x="x1", n_estimators=50
            )

    def test_covariates_are_required(self):
        df = _staggered(N=200, T=5)
        with pytest.raises(MethodIncompatibility, match="at least one covariate"):
            sp.did_forest(
                df, y="y", id="id", time="t", cohort="g", x=[], n_estimators=50
            )

    def test_nevertreated_requires_never_treated_units(self):
        df = _staggered(N=200, T=5)
        df = df[df["g"] > 0]
        with pytest.raises(DataInsufficient, match="no unit is never treated"):
            sp.did_forest(
                df,
                y="y",
                id="id",
                time="t",
                cohort="g",
                x="x1",
                control_group="nevertreated",
                n_estimators=50,
            )

    def test_small_cells_are_dropped_loudly(self):
        df = _staggered(N=200, T=5)
        with pytest.warns(AssumptionWarning, match="dropped"):
            res = sp.did_forest(
                df,
                y="y",
                id="id",
                time="t",
                cohort="g",
                x="x1",
                min_group_size=60,
                n_estimators=100,
            )
        assert len(res.dropped_cells) > 0
        assert res.dropped_cells["reason"].str.contains("too few units").all()

    def test_duplicate_unit_periods_are_refused(self):
        df = _staggered(N=100, T=4)
        df = pd.concat([df, df.iloc[:2]])
        with pytest.raises(MethodIncompatibility, match="unique"):
            sp.did_forest(
                df, y="y", id="id", time="t", cohort="g", x="x1", n_estimators=50
            )

    def test_reserved_forest_kwargs(self):
        df = _staggered(N=100, T=4)
        with pytest.raises(MethodIncompatibility, match="pass 'clusters' directly"):
            sp.did_forest(
                df,
                y="y",
                id="id",
                time="t",
                cohort="g",
                x="x1",
                forest_kwargs={"clusters": df["id"]},
                n_estimators=50,
            )

    def test_unknown_cell_forest(self, staggered):
        _, res = staggered
        with pytest.raises(MethodIncompatibility, match="no forest for cell"):
            res.forest(99, 1)


def test_unit_is_accepted_as_an_alias_of_id():
    df = _staggered(N=200, T=5)
    a = sp.did_forest(
        df, y="y", unit="id", time="t", cohort="g", x="x1", n_estimators=100
    )
    b = sp.did_forest(
        df, y="y", id="id", time="t", cohort="g", x="x1", n_estimators=100
    )
    pd.testing.assert_frame_equal(a.att_gt, b.att_gt)
    with pytest.raises(TypeError, match="both"):
        sp.did_forest(df, y="y", id="id", unit="id", time="t", cohort="g", x="x1")

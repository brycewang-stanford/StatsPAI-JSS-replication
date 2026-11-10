"""Reference parity: ``sp.etwfe`` + ``sp.etwfe_emfx`` vs R ``etwfe`` on castle.

Every aggregation R ``etwfe::emfx`` offers (``simple`` / ``event`` / ``group``
/ ``calendar``) under both control groups is pinned on the Cheng & Hoekstra
castle-doctrine panel, ``sp.datasets.castle_doctrine(event_time=True)``
(50 states x 2000-2010, cohorts 2005-2009, 29 never-treated states).

Reference values were copied from the DiD reconciliation study,
``Paper-DiD-JAE/replication/applications/castle/results/castle_R.json`` and
``castle_Stata.json`` (rows ``estimator == "etwfe"``, specs ``notyet_unw`` /
``never_unw``), produced on the byte-identical CSV of this panel by

* R 4.5.2, etwfe 0.6.2, fixest 0.14.0, marginaleffects 0.32.0::

      etwfe::etwfe(fml = l_homicide ~ 0, tvar = year, gvar = gvar,
                   data = dat, vcov = ~sid, cgroup = "notyet" | "never")
      etwfe::emfx(e, type = "simple" | "event" | "group" | "calendar")

* Stata 18, jwdid v2.2 (reghdfe 6.13.1)::

      jwdid l_homicide, ivar(sid) tvar(year) gvar(gvar) [never]
      estat simple | event | group | calendar

R and Stata agree on every estimate to ~1e-15.  Their standard errors differ
by one documented degrees-of-freedom convention: both apply
``G / (G - 1) * (n - 1) / (n - K)`` to the same cluster-robust covariance, but
fixest's ``K`` counts the 6 cohort-FE levels + 11 period-FE levels - 1 on top
of the cell coefficients (K = 36 not-yet / 66 never), whereas reghdfe drops
the unit effects as nested in the cluster and counts 10 period effects + a
constant (K = 31 / 61).  Hence ``se_Stata = se_R * sqrt((n - K_R) / (n - K_Stata))``
with ``K_R - K_Stata = 5`` (= the number of treated cohorts).

StatsPAI follows R's design and ``K``.  R's *reported* standard errors carry
the finite-difference Jacobian noise of ``marginaleffects::slopes`` (up to
5.1e-7 relative on this panel; R's own ``sqrt(w' vcov(e) w)`` agrees with
StatsPAI to 1e-13), so the R-side SE tolerance is 1e-6 while the Stata-side
reconstruction, which uses analytic derivatives, is pinned at 1e-9.
"""

from __future__ import annotations

import numpy as np
import pytest

import statspai as sp

N_OBS = 550
N_CLUSTERS = 50
N_COHORTS = 5
STATS = (
    ["att"]
    + [f"dyn_e{k}" for k in range(6)]
    + [f"group_{g}" for g in range(2005, 2010)]
    + [f"cal_{t}" for t in range(2005, 2011)]
)

# (estimate, se) from castle_R.json -- etwfe 0.6.2 + emfx, vcov = ~sid.
R_REF = {
    "notyet": {
        "att": (0.0798015475914422, 0.0635615915980515),
        "dyn_e0": (0.0710705993805267, 0.0584523285869817),
        "dyn_e1": (0.0928844566278102, 0.0625908382463979),
        "dyn_e2": (0.0767730115149872, 0.0789213424478865),
        "dyn_e3": (0.100185177760692, 0.0828522119190612),
        "dyn_e4": (0.0502468939428482, 0.0769750954363368),
        "dyn_e5": (0.0958408998198526, 0.0478908502848361),
        "group_2005": (0.0743039743766249, 0.0295603862907761),
        "group_2006": (0.0624082942425604, 0.0856793905312392),
        "group_2007": (0.112496802324529, 0.0792572243222447),
        "group_2008": (0.14277902597493, 0.0529574642830773),
        "group_2009": (0.211080528059387, 0.0357809636169993),
        "cal_2005": (-0.136473544065304, 0.0291410915249236),
        "cal_2006": (0.0531012008226355, 0.0748795397171993),
        "cal_2007": (0.124803145169755, 0.0773372464440108),
        "cal_2008": (0.00267932873025323, 0.0834584102094712),
        "cal_2009": (0.148964994803915, 0.0755580011320634),
        "cal_2010": (0.0736140797710739, 0.0650179122591196),
    },
    "nevertreated": {
        "att": (0.110383028366969, 0.0415297530807037),
        "dyn_e0": (0.0972153506863703, 0.0405868240115171),
        "dyn_e1": (0.111549107026272, 0.0466460887670887),
        "dyn_e2": (0.111566151313793, 0.060576284311247),
        "dyn_e3": (0.136825392647509, 0.0614958897370243),
        "dyn_e4": (0.0925865787315273, 0.0576482432231604),
        "dyn_e5": (0.111941886724155, 0.0547111563025725),
        "group_2005": (0.0930697734310514, 0.0348929019842947),
        "group_2006": (0.109945016796285, 0.0566771639438815),
        "group_2007": (0.128402197237068, 0.0552248310866207),
        "group_2008": (0.122120659827586, 0.0610288376037339),
        "group_2009": (-0.00280807612070538, 0.0414222257401717),
        "cal_2005": (-0.120277066206878, 0.0385665045648842),
        "cal_2006": (0.107351348689655, 0.0504267917877693),
        "cal_2007": (0.157900568777778, 0.0596155133604956),
        "cal_2008": (0.0401251706413797, 0.0707333982678075),
        "cal_2009": (0.1676524153399, 0.0570583765238576),
        "cal_2010": (0.0923015003070599, 0.0513007168836326),
    },
}

# (estimate, se) from castle_Stata.json -- jwdid v2.2 + estat, vce(cluster sid).
STATA_REF = {
    "notyet": {
        "att": (0.07980154759144198, 0.06325465453485675),
        "dyn_e0": (0.07107059938052673, 0.05817008934603207),
        "dyn_e1": (0.09288445662780975, 0.06228860629578795),
        "dyn_e2": (0.07677301151498739, 0.07854022174188098),
        "dyn_e3": (0.1001851777606919, 0.08245215988054272),
        "dyn_e4": (0.05024689394284776, 0.07660341032497005),
        "dyn_e5": (0.095840899819851, 0.04765960322690863),
        "group_2005": (0.07430397437662362, 0.02941764972954178),
        "group_2006": (0.06240829424256011, 0.0852656764438381),
        "group_2007": (0.1124968023245294, 0.07887452402000315),
        "group_2008": (0.1427790259749306, 0.0527017518464557),
        "group_2009": (0.2110805280593897, 0.03560819047034552),
        "cal_2005": (-0.136473544065304, 0.02900038206823425),
        "cal_2006": (0.05310120082263525, 0.07451798119726656),
        "cal_2007": (0.1248031451697542, 0.07696381292640983),
        "cal_2008": (0.002679328730253117, 0.0830553852491728),
        "cal_2009": (0.1489649948039145, 0.07519316543069196),
        "cal_2010": (0.07361407977107359, 0.06470396530974043),
    },
    "nevertreated": {
        "att": (0.1103830283669693, 0.04131688951004162),
        "dyn_e0": (0.0972153506863711, 0.04037879135047187),
        "dyn_e1": (0.1115491070262731, 0.04640699660282013),
        "dyn_e2": (0.1115661513137929, 0.06026579903325973),
        "dyn_e3": (0.1368253926475105, 0.06118068584994101),
        "dyn_e4": (0.09258657873152698, 0.0573527610521688),
        "dyn_e5": (0.1119418867241404, 0.0544307344057585),
        "group_2005": (0.09306977343103795, 0.03471405499157543),
        "group_2006": (0.1099450167962861, 0.05638664980256296),
        "group_2007": (0.1284021972370692, 0.05494176829095524),
        "group_2008": (0.1221206598275861, 0.06071602326215262),
        "group_2009": (-0.002808076120688563, 0.0412099105057414),
        "cal_2005": (-0.1202770662068919, 0.03836882425866058),
        "cal_2006": (0.1073513486896549, 0.05016832324234934),
        "cal_2007": (0.1579005687777781, 0.05930994591704147),
        "cal_2008": (0.04012517064137922, 0.07037085147094493),
        "cal_2009": (0.1676524153399019, 0.05676591685739505),
        "cal_2010": (0.09230150030706108, 0.05103776848817476),
    },
}

# fixest K = cells + (6 cohort levels + 11 period levels - 1);
# reghdfe K = cells + 10 period effects + constant.
EXPECTED_K = {"notyet": 36, "nevertreated": 66}
EXPECTED_K_STATA = {"notyet": 31, "nevertreated": 61}


@pytest.fixture(scope="module")
def castle():
    df = sp.datasets.castle_doctrine(event_time=True)
    return df.assign(gvar=df["gvar"].fillna(0))


@pytest.fixture(scope="module")
def fits(castle):
    return {
        cg: sp.etwfe(
            castle,
            y="l_homicide",
            group="sid",
            time="year",
            first_treat="gvar",
            cgroup=cg,
        )
        for cg in ("notyet", "nevertreated")
    }


def _emfx_rows(fit):
    """Collect every emfx aggregation as {statistic: (estimate, se)}."""
    out = {}
    simple = sp.etwfe_emfx(fit, type="simple")
    out["att"] = (float(simple.estimate), float(simple.se))
    for _, r in sp.etwfe_emfx(fit, type="event").detail.iterrows():
        out[f"dyn_e{int(r['event_time'])}"] = (float(r["estimate"]), float(r["se"]))
    for _, r in sp.etwfe_emfx(fit, type="group").detail.iterrows():
        out[f"group_{int(r['cohort'])}"] = (float(r["estimate"]), float(r["se"]))
    for _, r in sp.etwfe_emfx(fit, type="calendar").detail.iterrows():
        out[f"cal_{int(r['calendar_time'])}"] = (float(r["estimate"]), float(r["se"]))
    return out


@pytest.fixture(scope="module")
def rows(fits):
    return {cg: _emfx_rows(fit) for cg, fit in fits.items()}


def _stata_factor(fit):
    ssc = fit.model_info["ssc"]
    n, k = ssc["n"], ssc["K"]
    k_stata = k - fit.model_info["n_cohorts"]
    return np.sqrt((n - k) / (n - k_stata))


# ---------------------------------------------------------------------------
# R etwfe::emfx -- estimates and standard errors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cgroup", ["notyet", "nevertreated"])
def test_reports_every_reference_row(rows, cgroup):
    assert set(rows[cgroup]) == set(STATS)


@pytest.mark.parametrize("cgroup", ["notyet", "nevertreated"])
@pytest.mark.parametrize("stat", STATS)
def test_estimate_matches_r_emfx(rows, cgroup, stat):
    est, _ = rows[cgroup][stat]
    # Observed max relative gap 6.4e-12 (on the near-zero never group_2009);
    # everything else is below 3e-13.
    assert est == pytest.approx(R_REF[cgroup][stat][0], rel=1e-9)


@pytest.mark.parametrize("cgroup", ["notyet", "nevertreated"])
@pytest.mark.parametrize("stat", STATS)
def test_se_matches_r_emfx(rows, cgroup, stat):
    _, se = rows[cgroup][stat]
    # 1e-6: R's reported SE carries marginaleffects' numerical-Jacobian
    # noise (max 5.1e-7 relative on this panel); see module docstring.
    assert se == pytest.approx(R_REF[cgroup][stat][1], rel=1e-6)


# ---------------------------------------------------------------------------
# Stata jwdid -- same estimates; SE differs only by the documented dof factor
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cgroup", ["notyet", "nevertreated"])
@pytest.mark.parametrize("stat", STATS)
def test_estimate_matches_stata_jwdid(rows, cgroup, stat):
    est, _ = rows[cgroup][stat]
    assert est == pytest.approx(STATA_REF[cgroup][stat][0], rel=1e-9)


@pytest.mark.parametrize("cgroup", ["notyet", "nevertreated"])
@pytest.mark.parametrize("stat", STATS)
def test_se_reconstructs_stata_after_dof_factor(fits, rows, cgroup, stat):
    _, se = rows[cgroup][stat]
    # Observed max relative gap 1.7e-13: Stata's margins uses analytic
    # derivatives, so this is an exact identity up to the K convention.
    assert se * _stata_factor(fits[cgroup]) == pytest.approx(
        STATA_REF[cgroup][stat][1], rel=1e-9
    )


@pytest.mark.parametrize("cgroup", ["notyet", "nevertreated"])
def test_small_sample_bookkeeping_matches_fixest(fits, cgroup):
    ssc = fits[cgroup].model_info["ssc"]
    assert ssc["n"] == N_OBS
    assert ssc["n_clusters"] == N_CLUSTERS
    assert ssc["K"] == EXPECTED_K[cgroup]
    assert fits[cgroup].model_info["n_cohorts"] == N_COHORTS
    assert ssc["K"] - N_COHORTS == EXPECTED_K_STATA[cgroup]


# ---------------------------------------------------------------------------
# Internal consistency
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cgroup", ["notyet", "nevertreated"])
def test_simple_headline_equals_fit(fits, cgroup):
    fit = fits[cgroup]
    simple = sp.etwfe_emfx(fit, type="simple")
    assert simple.estimate == pytest.approx(fit.estimate, abs=1e-15)
    assert simple.se == pytest.approx(fit.se, abs=1e-15)
    assert fit.n_obs == N_OBS


@pytest.mark.parametrize("cgroup", ["notyet", "nevertreated"])
def test_group_rows_equal_fit_detail(fits, cgroup):
    fit = fits[cgroup]
    res = sp.etwfe_emfx(fit, type="group")
    grp = res.detail.set_index("cohort")
    det = fit.detail.set_index("cohort")
    assert list(grp.index) == list(det.index)
    np.testing.assert_allclose(grp["estimate"], det["att"], rtol=1e-13)
    np.testing.assert_allclose(grp["se"], det["se"], rtol=1e-13)
    assert res.model_info["rows_source"] == "event_cells"
    assert res.model_info["rows_se_method"].startswith("vcov-based")


def test_control_group_changes_the_aggregations(rows):
    # The old code served identical group rows under both control groups.
    for stat in STATS:
        assert rows["notyet"][stat][0] != pytest.approx(
            rows["nevertreated"][stat][0], abs=1e-6
        )


def test_nevertreated_aggregates_equal_callaway_santanna(castle, rows):
    """Without covariates the never-treated ETWFE cells are the CS 2x2
    ATT(g, t) against ``g - 1``, so every aggregate coincides with
    ``aggte`` on the never-treated Callaway--Sant'Anna fit."""
    cs = sp.callaway_santanna(
        castle,
        y="l_homicide",
        g="gvar",
        t="year",
        i="sid",
        control_group="nevertreated",
        estimator="reg",
        base_period="universal",
    )
    got = rows["nevertreated"]
    dyn = sp.aggte(cs, type="dynamic", bstrap=False, cband=False).detail
    for _, r in dyn[dyn["relative_time"] >= 0].iterrows():
        k = int(r["relative_time"])
        assert got[f"dyn_e{k}"][0] == pytest.approx(float(r["att"]), rel=1e-9)
    grp = sp.aggte(cs, type="group", bstrap=False, cband=False).detail
    for _, r in grp.iterrows():
        assert got[f"group_{int(r['group'])}"][0] == pytest.approx(
            float(r["att"]), rel=1e-9
        )
    cal = sp.aggte(cs, type="calendar", bstrap=False, cband=False).detail
    for _, r in cal.iterrows():
        assert got[f"cal_{int(r['time'])}"][0] == pytest.approx(
            float(r["att"]), rel=1e-9
        )


def test_nevertreated_event_study_keeps_leads(fits):
    ev = sp.etwfe_emfx(fits["nevertreated"], type="event", include_leads=True)
    et = ev.detail["event_time"].tolist()
    assert min(et) < 0 and -1 not in et and max(et) == 5
    assert ev.model_info["se_method"].startswith("vcov-based")

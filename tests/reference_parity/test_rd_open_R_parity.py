"""Reference parity: boundary discontinuity designs vs R ``rd2d``, on identical bytes.

Functions pinned here against R ``rd2d`` 1.0.0 (Cattaneo, Titiunik, Yu):

* ``sp.rd2d(approach="location")`` / ``sp.boundary_rd`` -- R ``rd2d()``:
  pointwise effects at five points of the boundary ``x2 = 0.3 x1``. Cells:
  default (MSE-optimal common bandwidth, product triangular kernel, HC1,
  joint fit); a user bandwidth with ``p = 2``, Epanechnikov, HC3 and
  separate fits; clusters with HC0 / ``msetwo`` and with HC1 / joint; radial
  uniform kernel with ``imserd`` and the ROT pilot; the ``(1, 0)`` partial
  derivative with ``p = 2``; a tangential derivative; Gaussian kernel with
  ``cerrd``; fuzzy designs (joint, and clustered with separate fits); mass
  points with ``masspoints="adjust"``; ``icertwo`` with HC2.
* ``sp.rd2d_bw(approach="location")`` -- R ``rdbw2d()`` with its own
  defaults (``bwcheck = 20``, ``scaleregul = 1``), ``certwo`` with a radial
  kernel, the fuzzy ITT bandwidth, and unstandardised separate fits.
* ``sp.rd2d(approach="distance")`` -- R ``rd2d.distance()`` on the signed
  Euclidean distance to each boundary point: default, unknown kinks (both
  flags and first only), a known kink at the middle point, fuzzy with
  clusters, user bandwidths with ``p = 2`` / HC2 / separate fits,
  Epanechnikov ``imsetwo``, mass points, clusters with HC1.
* ``sp.rd2d_bw(approach="distance")`` -- R ``rdbw2d.distance()`` (default,
  ``certwo``, ``cqt = 0.3`` with a uniform kernel).

Every row of R's ``$main`` table is compared: ``estimate.p``, ``std.err.p``,
``estimate.q``, ``std.err.q``, ``t.value``, ``p.value``, ``ci.lower``,
``ci.upper``, the four (location) or two plus two bias-correction (distance)
bandwidths and the effective sample sizes; for fuzzy designs also the ITT
and first-stage tables. The covariance of the bias-corrected estimates
across boundary points (``params.cov = "main"``) is compared too, because
the headline of a multi-point call is their equally weighted average.

Fixture: ``_generate_rd_open_R.R`` (reads ``_fixtures/rd_open_bd.csv`` and
``rd_open_bd_mass.csv`` from ``_fixtures/_generate_rd_open_data.py``; writes
``_fixtures/rd_open_R.json``).

Conventions each number depends on
----------------------------------
* R ``rd2d`` passes ``bwcheck = 50 + p + 1`` and ``scaleregul = 3`` to its
  bandwidth selector; ``rdbw2d`` called directly uses ``bwcheck = 20`` and
  ``scaleregul = 1``. ``sp.rd2d`` / ``sp.rd2d_bw`` copy both sets of defaults.
* ``estimate.q`` / ``std.err.q`` come from the order ``q = p + 1`` fit at
  the same bandwidths; the interval and p-value use them (robust
  bias-corrected inference). StatsPAI reports them as ``estimate_q``,
  ``std_err_q`` and puts the order-``p`` pair in ``estimate_p``/``std_err_p``.
* ``fitmethod = "joint"``: HC1 / cluster degrees-of-freedom corrections use
  the effective sample of *both* sides with ``2k`` parameters.
* The distance approach's kink indices are 1-based in R (``kink.position =
  3``) and 0-based here (``kink_position=[2]``).

Tolerances: everything is closed-form least squares, so estimates, standard
errors, intervals and covariances are held at rel 1e-9 (observed ~1e-12);
bandwidths are closed-form plug-ins built from several pilot fits and are
held at rel 1e-8 (observed ~1e-13). p-values below 1e-300 are compared on
the z statistic instead.
"""

from __future__ import annotations

import json
import pathlib
import warnings

import numpy as np
import pandas as pd
import pytest

import statspai as sp

FX = pathlib.Path(__file__).parent / "_fixtures"
R = json.loads((FX / "rd_open_R.json").read_text(encoding="utf-8"))
DF = pd.read_csv(FX / "rd_open_bd.csv")
DM = pd.read_csv(FX / "rd_open_bd_mass.csv")
B = np.array(R["meta"]["b"], dtype=float)
TV = np.array(R["meta"]["tangvec"], dtype=float)
HD = np.array(R["meta"]["h_user_distance"], dtype=float)

EST_RTOL = 1e-9
BW_RTOL = 1e-8

_COLS_EST = [
    ("estimate.p", "estimate_p"),
    ("std.err.p", "std_err_p"),
    ("estimate.q", "estimate_q"),
    ("std.err.q", "std_err_q"),
    ("t.value", "t_value"),
    ("ci.lower", "ci_lower"),
    ("ci.upper", "ci_upper"),
]
_COLS_BW_LOC = [("h01", "h01"), ("h02", "h02"), ("h11", "h11"), ("h12", "h12")]
_COLS_BW_DIST = [("h0", "h0"), ("h1", "h1"), ("h0.rbc", "h0_rbc"), ("h1.rbc", "h1_rbc")]


def _fit(approach, data=DF, y="y", **kw):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return sp.rd2d(
            data,
            y=y,
            x1="x1",
            x2="x2",
            treatment="t",
            eval_points=B,
            approach=approach,
            **kw,
        )


def _check_main(res, ref, bw_cols):
    det = res.detail
    for rc, pc in _COLS_EST:
        np.testing.assert_allclose(
            det[pc], ref[rc], rtol=EST_RTOL, atol=1e-14, err_msg=rc
        )
    pv = np.array(ref["p.value"], dtype=float)
    ok = pv > 1e-300
    np.testing.assert_allclose(det["p_value"][ok], pv[ok], rtol=1e-8, atol=1e-300)
    for rc, pc in bw_cols:
        np.testing.assert_allclose(det[pc], ref[rc], rtol=BW_RTOL, err_msg=rc)
    np.testing.assert_array_equal(det["n_co"], np.array(ref["N.Co"], dtype=int))
    np.testing.assert_array_equal(det["n_tr"], np.array(ref["N.Tr"], dtype=int))


def _check_cov(res, ref_cov):
    np.testing.assert_allclose(
        res.model_info["cov_q"],
        np.array(ref_cov, dtype=float),
        rtol=EST_RTOL,
        atol=1e-15,
    )


def _check_headline(res, ref_main, ref_cov):
    est = np.mean(ref_main["estimate.q"])
    w = np.full(len(B), 1 / len(B))
    se = float(np.sqrt(w @ np.array(ref_cov, dtype=float) @ w))
    assert res.estimate == pytest.approx(est, rel=EST_RTOL)
    assert res.se == pytest.approx(se, rel=EST_RTOL)


# ---------------------------------------------------------------- location

_LOC_CELLS = {
    "L_default": dict(),
    "L_user_h_epa_hc3_sep_p2": dict(
        h=0.5, p=2, kernel="epa", vce="hc3", fitmethod="separate"
    ),
    "L_cluster_hc0_msetwo": dict(cluster="g", vce="hc0", bwselect="msetwo"),
    "L_cluster_hc1_joint": dict(cluster="g"),
    "L_deriv10_p2": dict(p=2, deriv=(1, 0)),
    "L_tangvec": dict(tangvec=TV),
    "L_gau_cerrd": dict(kernel="gau", bwselect="cerrd"),
    "L_icertwo_hc2": dict(bwselect="icertwo", vce="hc2"),
}


@pytest.mark.parametrize("cell", sorted(_LOC_CELLS))
def test_rd2d_location_matches_R(cell):
    res = _fit("location", **_LOC_CELLS[cell])
    _check_main(res, R[cell]["main"], _COLS_BW_LOC)
    _check_cov(res, R[cell]["cov_main"])


def test_rd2d_location_mass_points_adjust():
    res = _fit("location", data=DM, masspoints="adjust")
    _check_main(res, R["L_mass_adjust"]["main"], _COLS_BW_LOC)
    _check_cov(res, R["L_mass_adjust"]["cov_main"])


@pytest.mark.parametrize(
    "cell, kw",
    [
        ("L_fuzzy_joint", dict()),
        ("L_fuzzy_cluster_separate", dict(cluster="g", fitmethod="separate")),
    ],
)
def test_rd2d_location_fuzzy_matches_R(cell, kw):
    res = _fit("location", y="yf", fuzzy="takeup", **kw)
    ref = R[cell]
    _check_main(res, ref["main"], _COLS_BW_LOC)
    _check_cov(res, ref["cov_main"])
    mi = res.model_info
    for tag, key in (("itt", "itt"), ("fs", "fs")):
        np.testing.assert_allclose(
            mi[f"{key}_p"], ref[tag]["estimate.p"], rtol=EST_RTOL
        )
        np.testing.assert_allclose(
            mi[f"{key}_q"], ref[tag]["estimate.q"], rtol=EST_RTOL
        )
        np.testing.assert_allclose(
            mi[f"se_{key}_p"], ref[tag]["std.err.p"], rtol=EST_RTOL
        )
        np.testing.assert_allclose(
            mi[f"se_{key}_q"], ref[tag]["std.err.q"], rtol=EST_RTOL
        )


def test_rd2d_headline_is_average_of_pointwise_effects():
    res = _fit("location")
    _check_headline(res, R["L_default"]["main"], R["L_default"]["cov_main"])


def _check_wbate(res, ref):
    wb = res.model_info["wbate"]
    for rc, pc in (
        ("estimate.p", "estimate_p"),
        ("estimate.q", "estimate_q"),
        ("std.err.q", "std_err_q"),
        ("t.value", "t_value"),
        ("ci.lower", "ci_lower"),
        ("ci.upper", "ci_upper"),
    ):
        assert wb[pc] == pytest.approx(ref[rc], rel=EST_RTOL), rc
    assert wb["p_value"] == pytest.approx(ref["p.value"], rel=1e-8)
    assert res.estimate == pytest.approx(ref["estimate.q"], rel=EST_RTOL)
    assert res.se == pytest.approx(ref["std.err.q"], rel=EST_RTOL)
    assert res.ci[0] == pytest.approx(ref["ci.lower"], rel=EST_RTOL)


@pytest.mark.parametrize(
    "approach, cell, weights",
    [
        ("location", "WBATE_loc_equal", None),
        ("location", "WBATE_loc_1to5", [1, 2, 3, 4, 5]),
        ("distance", "WBATE_dist_equal", None),
        ("distance", "WBATE_dist_1to5", [1, 2, 3, 4, 5]),
    ],
)
def test_rd2d_wbate_matches_R_summary(approach, cell, weights):
    """Headline of a multi-point call = R summary(fit, WBATE = w)."""
    _check_wbate(_fit(approach, weights=weights), R[cell])


# R rd2d with kernel_type = "rad" (class 4, reference defect): the fit runs at
# radius sqrt(hx^2 + hy^2) (rd2d_h_normalize applied to the (hx, hy) row of the
# bandwidth grid) but the variance is rescaled with hx * hy, so every R
# radial-kernel variance is (hx^2 + hy^2) / (hx hy) times the sandwich of the
# fit it runs -- a factor 2 when hx = hy. Point estimates, bandwidths and
# effective sample sizes are pinned to R; the standard errors are pinned to an
# independent lm() + sandwich::vcovHC recomputation, and R's number is
# reconstructed from ours with that factor.


def _rad_factor(h):
    return (h[:, 0] ** 2 + h[:, 1] ** 2) / (h[:, 0] * h[:, 1])


def _check_rad(
    res,
    ref,
    tag_cols=(("p", "estimate.p", "std.err.p"), ("q", "estimate.q", "std.err.q")),
):
    det, mi = res.detail, res.model_info
    for tag, ec, sc in tag_cols:
        np.testing.assert_allclose(det[f"estimate_{tag}"], ref[ec], rtol=EST_RTOL)
        h = mi[f"h_used_{tag}"]
        f0, f1 = _rad_factor(h[:, 0:2]), _rad_factor(h[:, 2:4])
        se_r = np.sqrt(f0 * mi[f"se0_{tag}"] ** 2 + f1 * mi[f"se1_{tag}"] ** 2)
        np.testing.assert_allclose(se_r, ref[sc], rtol=EST_RTOL, err_msg=sc)
    for c in ("h01", "h02", "h11", "h12"):
        np.testing.assert_allclose(det[c], ref[c], rtol=BW_RTOL)
    np.testing.assert_array_equal(det["n_co"], np.array(ref["N.Co"], dtype=int))
    np.testing.assert_array_equal(det["n_tr"], np.array(ref["N.Tr"], dtype=int))


def test_rd2d_radial_kernel_selected_bandwidth():
    res = _fit(
        "location", kernel="uni", kernel_type="rad", bwselect="imserd", method="rot"
    )
    _check_rad(res, R["L_rad_uni_imserd_rot"]["main"])


def test_rd2d_radial_kernel_user_bandwidth_vs_sandwich():
    res = _fit(
        "location", h=0.4, kernel_type="rad", vce="hc0", fitmethod="separate", q=1
    )
    chk = R["rad_lm_check"]
    np.testing.assert_allclose(res.detail["estimate_p"], chk["est"], rtol=1e-10)
    np.testing.assert_allclose(res.detail["std_err_p"], chk["se"], rtol=1e-10)
    np.testing.assert_array_equal(res.detail["n_co"], np.array(chk["n0"], dtype=int))
    np.testing.assert_allclose(res.detail["radius_co"], 0.4 * np.sqrt(2), rtol=1e-15)
    res2 = _fit("location", h=0.4, kernel_type="rad", vce="hc0", fitmethod="separate")
    _check_rad(res2, R["L_rad_user_h_hc0_sep"]["main"])
    # R's radial standard error is exactly sqrt(2) times the sandwich here
    np.testing.assert_allclose(
        np.array(R["L_rad_user_h_hc0_sep"]["main"]["std.err.p"]),
        np.sqrt(2) * np.array(chk["se"]),
        rtol=1e-10,
    )


def test_boundary_rd_alias_matches_R():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = sp.boundary_rd(DF, y="y", x1="x1", x2="x2", treatment="t", eval_points=B)
    _check_main(res, R["L_default"]["main"], _COLS_BW_LOC)


_BW_LOC = {
    "BW_loc_default": dict(),
    "BW_loc_certwo_rad": dict(bwselect="certwo", kernel_type="rad"),
    "BW_loc_fuzzy_itt": dict(y="yf", fuzzy="takeup", bwparam="itt"),
    "BW_loc_nostd_sep": dict(stdvars=False, fitmethod="separate"),
}


@pytest.mark.parametrize("cell", sorted(_BW_LOC))
def test_rd2d_bw_location_matches_R(cell):
    kw = dict(_BW_LOC[cell])
    y = kw.pop("y", "y")
    bw = sp.rd2d_bw(DF, y=y, x1="x1", x2="x2", treatment="t", eval_points=B, **kw)
    for c in ("h01", "h02", "h11", "h12"):
        np.testing.assert_allclose(bw[c], R[cell][c], rtol=BW_RTOL, err_msg=c)


# ---------------------------------------------------------------- distance

_DIST_CELLS = {
    "D_default": dict(),
    "D_kink_unknown": dict(kink_unknown=True),
    "D_kink_unknown_TF": dict(kink_unknown=(True, False)),
    "D_kink_position3": dict(kink_position=[2]),
    "D_user_h_hc2_p2_sep": dict(h=HD, p=2, vce="hc2", fitmethod="separate"),
    "D_epa_imsetwo": dict(kernel="epa", bwselect="imsetwo"),
    "D_cluster_hc1_joint": dict(cluster="g"),
}


@pytest.mark.parametrize("cell", sorted(_DIST_CELLS))
def test_rd2d_distance_matches_R(cell):
    res = _fit("distance", **_DIST_CELLS[cell])
    _check_main(res, R[cell]["main"], _COLS_BW_DIST)
    _check_cov(res, R[cell]["cov_main"])


def test_rd2d_distance_fuzzy_cluster_matches_R():
    res = _fit("distance", y="yf", fuzzy="takeup", cluster="g")
    _check_main(res, R["D_fuzzy_cluster"]["main"], _COLS_BW_DIST)
    _check_cov(res, R["D_fuzzy_cluster"]["cov_main"])


def test_rd2d_distance_mass_points_adjust():
    res = _fit("distance", data=DM, masspoints="adjust")
    _check_main(res, R["D_mass_adjust"]["main"], _COLS_BW_DIST)


def test_rd2d_distance_headline_is_average():
    res = _fit("distance")
    _check_headline(res, R["D_default"]["main"], R["D_default"]["cov_main"])


def test_rd2d_distance_accepts_precomputed_distances():
    d = np.column_stack(
        [
            np.sqrt((DF.x1 - B[j, 0]) ** 2 + (DF.x2 - B[j, 1]) ** 2) * (2 * DF.t - 1)
            for j in range(len(B))
        ]
    )
    res = _fit("distance", distance=d)
    _check_main(res, R["D_default"]["main"], _COLS_BW_DIST)


_BW_DIST = {
    "BW_dist_default": dict(),
    "BW_dist_certwo": dict(bwselect="certwo"),
    "BW_dist_cqt": dict(cqt=0.3, kernel="uni"),
}


@pytest.mark.parametrize("cell", sorted(_BW_DIST))
def test_rd2d_bw_distance_matches_R(cell):
    bw = sp.rd2d_bw(
        DF,
        y="y",
        x1="x1",
        x2="x2",
        treatment="t",
        eval_points=B,
        approach="distance",
        **_BW_DIST[cell],
    )
    for c in ("h0", "h1"):
        np.testing.assert_allclose(bw[c], R[cell][c], rtol=BW_RTOL, err_msg=c)


# ------------------------------------------------ reference-free identities


def test_identity_user_bandwidth_is_two_weighted_least_squares_fits():
    """With h fixed and p = 1, estimate_p is the difference of two intercepts
    of kernel-weighted bivariate linear regressions -- recomputed here with
    numpy.linalg.lstsq, independently of the port."""
    h = 0.5
    res = _fit("location", h=h, bwcheck=None)
    for i, (b1, b2) in enumerate(B):
        mus = []
        for side in (0, 1):
            s = DF[DF.t == side]
            u1, u2 = (s.x1 - b1).to_numpy(), (s.x2 - b2).to_numpy()
            w = np.clip(1 - np.abs(u1 / h), 0, None) * np.clip(
                1 - np.abs(u2 / h), 0, None
            )
            k = w > 0
            X = np.column_stack([np.ones(k.sum()), u1[k], u2[k]])
            sw = np.sqrt(w[k])
            beta = np.linalg.lstsq(X * sw[:, None], s.y.to_numpy()[k] * sw, rcond=None)[
                0
            ]
            mus.append(beta[0])
        assert res.detail["estimate_p"][i] == pytest.approx(mus[1] - mus[0], rel=1e-10)


def test_identity_distance_is_univariate_rd_on_distance():
    """With h fixed, the distance approach at one point is two univariate
    kernel-weighted linear fits on |distance| (independent recomputation)."""
    h = 0.5
    res = _fit("distance", h=h, bwcheck=None)
    for i, (b1, b2) in enumerate(B):
        d = np.sqrt((DF.x1 - b1) ** 2 + (DF.x2 - b2) ** 2).to_numpy()
        mus = []
        for side in (0, 1):
            m = (DF.t == side).to_numpy()
            w = np.clip(1 - d[m] / h, 0, None)
            k = w > 0
            X = np.column_stack([np.ones(k.sum()), d[m][k]])
            sw = np.sqrt(w[k])
            beta = np.linalg.lstsq(
                X * sw[:, None], DF.y.to_numpy()[m][k] * sw, rcond=None
            )[0]
            mus.append(beta[0])
        assert res.detail["estimate_p"][i] == pytest.approx(mus[1] - mus[0], rel=1e-10)


def test_pooled_approach_is_rdrobust_on_signed_boundary_distance():
    """approach='pooled' is sp.rdrobust on the perpendicular distance to the
    boundary line x2 = 0.3 x1, signed by assignment."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = sp.rd2d(
            DF,
            y="y",
            x1="x1",
            x2="x2",
            treatment="t",
            approach="pooled",
            boundary=lambda v: 0.3 * v,
        )
        d = np.abs(DF.x2 - 0.3 * DF.x1) / np.sqrt(1.09) * (2 * DF.t - 1)
        ref = sp.rdrobust(
            pd.DataFrame({"y": DF.y, "d": d}), y="y", x="d", manipulation_test=False
        )
    assert res.estimate == pytest.approx(ref.estimate, rel=1e-9)
    assert res.se == pytest.approx(ref.se, rel=1e-9)


# ------------------------------------------------ discrete running variable
# sp.rd_discrete vs R RDHonest (Kolesar). 'bsd' = RDHonest(y ~ x) (the same
# engine as sp.rd_honest, pinned in test_rdhonest_parity.py; here on a running
# variable with 21 support points, which exercises the tie handling of the
# nearest-neighbour variance). 'bme' = RDHonestBME. Fixed-bandwidth cells are
# closed forms (rel 1e-9); the selected-bandwidth cell goes through RDHonest's
# optimiser for h (rel 1e-6, observed ~1e-9), as in test_rdhonest_parity.py.

DD = pd.read_csv(FX / "rd_open_discrete.csv")

_DISC = {
    "DISC_bsd_fixed": (dict(method="bsd", M=0.05, h=5), 1e-9),
    "DISC_bsd_selected": (dict(method="bsd"), 1e-6),
    "DISC_bsd_uniform": (dict(method="bsd", M=0.05, h=4, kernel="uniform"), 1e-9),
    "DISC_bme_h4": (dict(method="bme", h=4), 1e-9),
    "DISC_bme_h6_o1": (dict(method="bm", h=6, order=1), 1e-9),
    "DISC_bme_all_o2": (dict(method="bme", order=2), 1e-9),
}


@pytest.mark.parametrize("cell", sorted(_DISC))
def test_rd_discrete_matches_RDHonest(cell):
    kw, tol = _DISC[cell]
    ref = R[cell]
    res = sp.rd_discrete(DD, y="y", x="age", c=18, **kw)
    info = res.model_info["discrete"]
    assert res.estimate == pytest.approx(ref["estimate"], rel=tol)
    assert res.se == pytest.approx(ref["std.error"], rel=tol)
    assert info["maximum_bias"] == pytest.approx(ref["maximum.bias"], rel=tol)
    assert res.ci[0] == pytest.approx(ref["conf.low"], rel=tol)
    assert res.ci[1] == pytest.approx(ref["conf.high"], rel=tol)
    if kw["method"] == "bsd":
        assert res.pvalue == pytest.approx(ref["p.value"], rel=max(tol, 1e-8))
        assert info["bandwidth"] == pytest.approx(ref["bandwidth"], rel=tol)
        assert info["M"] == pytest.approx(ref["M"], rel=tol)
    else:
        assert info["conf_low_onesided"] == pytest.approx(
            ref["conf.low.onesided"], rel=tol
        )
        assert info["conf_high_onesided"] == pytest.approx(
            ref["conf.high.onesided"], rel=tol
        )
        assert info["leverage"] == pytest.approx(ref["leverage"], rel=tol)
        assert info["eff_obs"] == ref["eff.obs"]
        # RDHonestBME's p-value adds maximum.bias in outcome units to a z
        # statistic (class 4); reproduced from our quantities, while the
        # headline p-value uses maximum.bias / std.error like RDHonest().
        assert info["p_value_rdhonest"] == pytest.approx(ref["p.value"], rel=1e-8)


def test_rd_discrete_bme_order0_identity():
    """order = 0, one support point per side inside h: the BME estimate is the
    difference of the two side means (independent recomputation)."""
    res = sp.rd_discrete(DD, y="y", x="age", c=18, method="bme", h=1)
    left = DD.y[(DD.age >= 17) & (DD.age < 18)].mean()
    right = DD.y[(DD.age >= 18) & (DD.age <= 19)].mean()
    assert res.estimate == pytest.approx(right - left, rel=1e-12)

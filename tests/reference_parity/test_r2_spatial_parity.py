"""Round-2 spatial parity: ``sp.mgwr`` bandwidth search and ``sp.spatial_panel``
two-way effects.

MGWR -- reference PySAL ``mgwr`` 2.2.1, the authors' implementation
(``Sel_BW(multi=True).search()`` then ``MGWR.fit()``), frozen by
``_generate_r2_spatial_mgwr.py`` into ``_fixtures/r2_spatial_mgwr.json``.
Data: Georgia (``r2_spatial_georgia.csv`` = libpysal ``GData_utm.csv``),
y = PctBach, X = (PctFB, PctBlack, PctRural), all standardised with ddof 0
as in mgwr's documentation and test suite. Conventions every number depends
on: adaptive kernel scale = distance to the ``int(bw)``-th neighbour times
``eps = 1.0000001``; golden section with ``delta = 0.38197``, integer
probes, memo, stop on criterion difference <= 1e-6, result rounded to 2
decimals; bounds ``[40 + 2p, n]`` (adaptive) or ``[min d / 2, 2 max d]``
(fixed); back-fitting stop on the score of change < 1e-5; bandwidths frozen
after 5 unchanged sweeps; inference replays the recorded bandwidth history
on the identity; ``sigma^2 = RSS / (n - tr S)``; mgwr's CV is divided by n.
Four configurations: adaptive bisquare AICc (mgwr's default), fixed
Gaussian AICc, adaptive bisquare CV (runs the full 200 sweeps without
converging, in both), adaptive exponential BIC with ``multi_bw_min = 20``.

Tolerances: bandwidths, initial bandwidth and iteration counts exact; betas
1e-9 rel (observed 3.0e-12, the 200-sweep CV case; <= 3.6e-14 elsewhere);
SEs, ENP_j, tr(S), sigma^2, AICc / AIC / BIC 1e-10 rel (observed <= 1e-15);
SOC score path 1e-9 rel (observed 8e-13; a difference of small numbers).

Spatial panel, two-way effects -- the round-1 xsmle fixture
(``spatial_survey_stata.json``) plus ``r2_spatial_stata.json`` from
``_fixtures/_generate_r2_spatial_stata.do`` (xsmle 1.4.5, Stata 18). What is
asserted is why xsmle ``type(both)`` is not a parity target (class 4):

* xsmle's reported ``e(ll)`` is exactly the splm / StatsPAI objective (lag
  W(Qy), T log|I - rho W|, NT) evaluated at xsmle's coefficients (1e-12);
* StatsPAI's maximum of that same objective is higher than xsmle's reported
  maximum, so xsmle stops short of the maximiser of its own likelihood
  (with tightened tolerances it reports non-convergence, round 1);
* ``type(both, leeyu)`` returns exactly the ``type(ind, leeyu)`` result
  (same rho, same ll, N(T-1) observations): the time effects are dropped.
  Its rho equals StatsPAI's entity-effects rho (Lee & Yu: the
  transformation and direct approaches coincide for zeta under individual
  effects).

Reference-free identities for ``twoways_lag``: the ``"within"`` lag gives
the same SSE as least squares on unit and time dummies at the same rho (the
profile likelihood of the dummy model), and ``SSE_splm(rho) =
SSE_within(rho) + rho^2 N sum_t c_t^2`` with ``c_t`` the period mean of
``W (Q y)_t``.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd
import pytest

import statspai as sp

FX = pathlib.Path(__file__).resolve().parent / "_fixtures"


def _rel(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    return float(np.max(np.abs(a - b) / np.maximum(np.abs(b), 1e-300)))


# ====================================================================== #
#  MGWR vs PySAL mgwr
# ====================================================================== #


@pytest.fixture(scope="module")
def MG():
    return json.loads((FX / "r2_spatial_mgwr.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def georgia_std():
    d = pd.read_csv(FX / "r2_spatial_georgia.csv")
    coords = d[["X", "Y"]].to_numpy(float)
    y = d["PctBach"].to_numpy(float)
    X = d[["PctFB", "PctBlack", "PctRural"]].to_numpy(float)
    y = (y - y.mean()) / y.std()
    X = (X - X.mean(axis=0)) / X.std(axis=0)
    return coords, y, X


CONFIGS = [
    "adaptive_bisquare_aicc",
    "fixed_gaussian_aicc",
    "adaptive_bisquare_cv",
    "adaptive_exponential_bic_min20",
]


def _fit(georgia_std, m):
    coords, y, X = georgia_std
    kw = dict(kernel=m["kernel"], fixed=m["fixed"])
    s = m["search"]
    if "criterion" in s:
        kw["criterion"] = s["criterion"]
    if "multi_bw_min" in s:
        kw["bw_min"] = s["multi_bw_min"]
    return sp.mgwr(coords, y, X, **kw)


@pytest.fixture(scope="module")
def fits(MG, georgia_std):
    import warnings

    out = {}
    for c in CONFIGS:
        with warnings.catch_warnings(record=True) as rec:
            warnings.simplefilter("always")
            out[c] = (_fit(georgia_std, MG[c]), rec)
    return out


@pytest.mark.parametrize("cfg", CONFIGS)
def test_mgwr_bandwidth_search_matches_pysal(MG, fits, cfg):
    m = MG[cfg]
    res, _ = fits[cfg]
    assert res.bws == m["bws"]
    assert res.bw_init == m["bw_init"]
    assert res.n_iter == len(m["scores"])
    np.testing.assert_array_equal(res.bws_history, np.asarray(m["bws_history"]))
    assert _rel(res.scores, m["scores"]) < 1e-9


@pytest.mark.parametrize("cfg", CONFIGS)
def test_mgwr_estimates_and_inference_match_pysal(MG, fits, cfg):
    m = MG[cfg]
    res, _ = fits[cfg]
    assert _rel(res.params, m["params"]) < 1e-9
    assert _rel(res.predicted, m["predy"]) < 1e-9
    assert _rel(res.bse, m["bse"]) < 1e-10
    assert _rel(res.ENP_j, m["ENP_j"]) < 1e-10
    for key in ("tr_S", "sigma2", "resid_ss", "aicc", "aic", "bic", "llf"):
        assert _rel(getattr(res, key), m[key]) < 1e-10, key


def test_mgwr_nonconvergence_is_reported_like_pysal(MG, fits):
    """mgwr runs all 200 sweeps on the CV configuration; so must we, and say so."""
    res, rec = fits["adaptive_bisquare_cv"]
    assert len(MG["adaptive_bisquare_cv"]["scores"]) == 200
    assert not res.converged
    assert any("did not converge" in str(w.message) for w in rec)
    assert fits["adaptive_bisquare_aicc"][0].converged


def test_mgwr_diagnostic_identities(fits):
    """Reference-free: tr(S) = sum ENP_j and AICc / sigma^2 from their formulas."""
    res, _ = fits["adaptive_bisquare_aicc"]
    n = res.n
    assert res.tr_S == pytest.approx(res.ENP_j.sum(), rel=1e-14)
    assert res.sigma2 == pytest.approx(res.resid_ss / (n - res.tr_S), rel=1e-14)
    s2 = res.resid_ss / n
    aicc = n * np.log(2 * np.pi * s2) + n * (n + res.tr_S) / (n - res.tr_S - 2)
    assert res.aicc == pytest.approx(aicc, rel=1e-12)
    assert res.resid_ss == pytest.approx(
        float(res.residuals @ res.residuals), rel=1e-14
    )


def test_mgwr_kernel_eps_changes_only_the_adaptive_edge(georgia_std):
    """kernel_eps=1 is GWmodel's kernel: at a fixed bandwidth the one-covariate
    smooth then equals sp.gwr's; the mgwr eps moves betas by O(1e-7)."""
    coords, y, X = georgia_std
    Xc = np.column_stack([np.ones(len(y)), X])
    bws = [60, 80, 100, 120]
    a = sp.mgwr(coords, y, X, bws=bws, tol=1e-15, max_iter=5000, kernel_eps=1.0)
    f = a.params * Xc
    for j in range(4):
        part = y - (f.sum(axis=1) - f[:, j])
        rj = sp.gwr(coords, part, Xc[:, [j]], bw=bws[j], add_constant=False)
        assert np.max(np.abs(rj.params.ravel() - a.params[:, j])) < 1e-9
    b = sp.mgwr(coords, y, X, bws=bws, tol=1e-15, max_iter=5000)
    d = np.max(np.abs(a.params - b.params))
    assert 1e-10 < d < 1e-4


# ====================================================================== #
#  spatial_panel two-way effects vs xsmle
# ====================================================================== #

FORMULA = "lgsp ~ lpcap + lpc + lemp + unemp"
XV = ["lpcap", "lpc", "lemp", "unemp"]


@pytest.fixture(scope="module")
def produc():
    d = pd.read_csv(FX / "spatial_survey_produc.csv")
    W = pd.read_csv(FX / "spatial_survey_usaww.csv", index_col=0).to_numpy(float)
    return d, W


@pytest.fixture(scope="module")
def S1():
    return json.loads((FX / "spatial_survey_stata.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def S2():
    return json.loads((FX / "r2_spatial_stata.json").read_text(encoding="utf-8"))


def _mats(produc):
    d, W = produc
    W = W / W.sum(axis=1, keepdims=True)
    piv = lambda v: d.pivot(index="state", columns="year", values=v).to_numpy(
        float
    )  # noqa: E731
    return piv("lgsp"), [piv(v) for v in XV], W


def _Q(A):
    return A - A.mean(1, keepdims=True) - A.mean(0, keepdims=True) + A.mean()


def _loglik_splm(produc, sdm, rho, beta, sigma2):
    """Full log-likelihood of splm's two-way objective: lag W(Qy)."""
    Y, Xs, W = _mats(produc)
    N, T = Y.shape
    X = [_Q(x) for x in Xs] + ([_Q(W @ x) for x in Xs] if sdm else [])
    Xm = np.column_stack([x.ravel("F") for x in X])
    e = _Q(Y).ravel("F") - rho * (W @ _Q(Y)).ravel("F") - Xm @ beta
    ev = np.real(np.linalg.eigvals(W))
    return (
        -N * T / 2 * np.log(2 * np.pi * sigma2)
        + T * np.sum(np.log(1 - rho * ev))
        - e @ e / (2 * sigma2)
    )


def _xsmle_point(rec):
    c = rec["coef"]
    beta = np.array([v for k, v in c.items() if k.startswith(("Main:", "Wx:"))])
    return c["Spatial:rho"], beta, c["Variance:sigma2_e"]


@pytest.mark.parametrize("model", ["sar", "sdm"])
def test_xsmle_both_reports_the_splm_objective_short_of_its_maximum(
    produc, S1, S2, model
):
    d, W = produc
    for rec in (S1[f"{model}_both"], S2[f"{model}_default"]):
        rho, beta, s2 = _xsmle_point(rec)
        ll = _loglik_splm(produc, model == "sdm", rho, beta, s2)
        assert ll == pytest.approx(rec["ll"], rel=1e-12)
    res = sp.spatial_panel(
        d, FORMULA, entity="state", time="year", W=W, model=model, effects="twoways"
    )
    # StatsPAI maximises the same objective to a higher value.
    assert res.log_likelihood - S2[f"{model}_default"]["ll"] > 1e-6
    assert res.log_likelihood - S1[f"{model}_both"]["ll"] > 1e-6


@pytest.mark.parametrize("model", ["sar", "sdm"])
def test_xsmle_leeyu_both_silently_drops_time_effects(produc, S2, model):
    both, ind = S2[f"{model}_leeyu_both"], S2[f"{model}_leeyu_ind"]
    assert both["ll"] == ind["ll"]
    assert both["coef"] == ind["coef"]
    assert both["N"] == ind["N"] == 48 * 16
    d, W = produc
    fe = sp.spatial_panel(
        d, FORMULA, entity="state", time="year", W=W, model=model, effects="fe"
    )
    assert _rel(fe.params["rho"], both["coef"]["Spatial:rho"]) < 1e-8
    tw = sp.spatial_panel(
        d, FORMULA, entity="state", time="year", W=W, model=model, effects="twoways"
    )
    assert abs(tw.params["rho"] - both["coef"]["Spatial:rho"]) > 1e-2


@pytest.mark.parametrize("model", ["sar", "sdm"])
def test_twoways_lag_within_is_the_dummy_profile_likelihood(produc, model):
    d, W = produc
    kw = dict(
        entity="state", time="year", W=W, model=model, effects="twoways", vce="oim"
    )
    wi = sp.spatial_panel(d, FORMULA, twoways_lag="within", **kw)
    sl = sp.spatial_panel(d, FORMULA, twoways_lag="splm", **kw)
    Y, Xs, Wn = _mats(produc)
    N, T = Y.shape
    rho = float(wi.params["rho"])
    # LSDV with unit and time dummies at the same rho
    Z = (Y - rho * (Wn @ Y)).ravel("F")
    Xr = [x.ravel("F") for x in Xs] + (
        [(Wn @ x).ravel("F") for x in Xs] if model == "sdm" else []
    )
    D_i = np.tile(np.eye(N), (T, 1))
    D_t = np.repeat(np.eye(T), N, axis=0)[:, 1:]
    M = np.column_stack(Xr + [D_i, D_t])
    coef, *_ = np.linalg.lstsq(M, Z, rcond=None)
    sse_lsdv = float(np.sum((Z - M @ coef) ** 2))
    assert float(np.sum(wi.residuals**2)) == pytest.approx(sse_lsdv, rel=1e-10)
    np.testing.assert_allclose(coef[: len(Xr)], wi.params.to_numpy()[:-1], rtol=1e-8)
    # SSE_splm(rho) = SSE_within(rho) + rho^2 N sum_t c_t^2 at any rho (beta
    # is the same because Q X has zero period means).
    rs = float(sl.params["rho"])
    c = (Wn @ _Q(Y)).mean(axis=0)
    Xm = np.column_stack(
        [_Q(x).ravel("F") for x in Xs]
        + ([_Q(Wn @ x).ravel("F") for x in Xs] if model == "sdm" else [])
    )
    P = Xm @ np.linalg.pinv(Xm)

    def sse(lag):
        v = _Q(Y).ravel("F") - rs * lag
        v = v - P @ v
        return float(v @ v)

    s_splm = sse((Wn @ _Q(Y)).ravel("F"))
    s_within = sse(_Q(Wn @ Y).ravel("F"))
    assert s_splm == pytest.approx(s_within + rs**2 * N * np.sum(c**2), rel=1e-11)
    assert float(np.sum(sl.residuals**2)) == pytest.approx(s_splm, rel=1e-10)


def test_twoways_lag_within_score_is_zero_and_options_validate(produc):
    d, W = produc
    kw = dict(entity="state", time="year", W=W, model="sar", effects="twoways")
    wi = sp.spatial_panel(d, FORMULA, twoways_lag="within", vce="oim", **kw)
    Y, Xs, Wn = _mats(produc)
    N, T = Y.shape
    ev = np.real(np.linalg.eigvals(Wn))
    Xm = np.column_stack([_Q(x).ravel("F") for x in Xs])
    wy = _Q(Wn @ Y).ravel("F")
    y = _Q(Y).ravel("F")
    rho = float(wi.params["rho"])
    e = y - rho * wy
    e = e - Xm @ np.linalg.lstsq(Xm, e, rcond=None)[0]
    score = N * T * float(e @ wy) / float(e @ e) - T * float(
        np.sum(ev / (1 - rho * ev))
    )
    assert abs(score) < 1e-7
    with pytest.raises(ValueError):
        sp.spatial_panel(d, FORMULA, twoways_lag="within", vce="information", **kw)
    with pytest.raises(ValueError):
        sp.spatial_panel(d, FORMULA, twoways_lag="bogus", **kw)
    # entity effects: the two lags coincide
    a = sp.spatial_panel(
        d,
        FORMULA,
        entity="state",
        time="year",
        W=W,
        model="sar",
        effects="fe",
        vce="oim",
        twoways_lag="within",
    )
    b = sp.spatial_panel(
        d,
        FORMULA,
        entity="state",
        time="year",
        W=W,
        model="sar",
        effects="fe",
        vce="oim",
    )
    np.testing.assert_allclose(a.params, b.params, rtol=1e-13)

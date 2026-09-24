"""Round-2 frontier parity: ``sp.malmquist`` (SFA) and ``sp.zisf``.

References
----------
* ``_fixtures/r2_frontier_R.json`` -- ``_generate_r2_frontier_R.R``
  (R sfaR 1.0.1 ``sfacross`` + ``efficiencies``; metafrontier 0.3.1
  ``malmquist_meta(method="sfa")``; sfa 1.2.0 ``zsfm``) on
  ``frontier_struct_malm.csv`` / ``frontier_struct_zisf.csv`` (written by
  ``_generate_frontier_struct_data.py``) and ``r2_frontier_zisf_z.csv``
  (``_generate_r2_frontier_data.py``).
* ``_fixtures/r2_frontier_stata.json`` --
  ``_fixtures/_generate_r2_frontier_stata.do`` (Stata 18, Luis Chanci's
  ``chks`` 1.1, ``estimation(zsf) eoption(ml)``) on
  ``frontier_struct_zisf.csv``.

What each block claims
----------------------
* ``sp.malmquist`` (default ``efficiency="bc"``). Output-oriented SFA
  Malmquist index built from its components, as the parametric literature
  does because the cross-period distance has no conditional-expectation
  predictor under a stochastic frontier (Fuentes, Grifell-Tatje & Perelman
  2001, JPA 15(2) 79-94, doi:10.1023/A:1007852020847; the argument is
  spelled out in endnote 1 of Pantzios, Karagiannis & Tzouvelekas 2011,
  JPA 36 21-31, doi:10.1007/s11123-010-0202-2):
  EC = TE_{t+1} / TE_t with the Battese-Coelli predictor from each period's
  own frontier, TC = exp(0.5 (x_t + x_{t+1})'(b_{t+1} - b_t)), M = EC * TC.
  - vs sfaR: EC is ``sfaR::efficiencies()$teBC`` (``$teJLMS`` for
    ``efficiency="jlms"``) of per-period ``sfacross`` fits; TC is arithmetic
    on sfaR's betas. 1e-6 rel (observed ~2.7e-7): both sides are
    optimisers; the fixture writes sfaR's max |gradient| per period
    (<= 1.2e-7).
  - vs metafrontier::malmquist_meta(method="sfa"), two groups ``id %% 2``
    (the function requires >= 2): its ``EC_group`` is the same TE ratio;
    its ``TC_group`` uses Farrell distances ``exp(x'b - y)`` and equals
    ``1 / TC`` (its ``MPI_group = EC_group * TC_group`` mixes orientations
    and is not compared). Tolerance 1e-4 (observed 1.8e-5), a stated
    reference-optimiser limit, not parity: its group-period fits are
    ``optim(BFGS)`` with finite-difference gradients. With optim's default
    ``ndeps = 1e-3`` the gap is 2.8e-3; with ``ndeps = 1e-6`` (used in the
    generator) 1.8e-5, while the same group-period fit by sfaR agrees with
    StatsPAI at ~1e-7. Corroboration of the definition, not the T2 claim.
  - ``efficiency="residual"`` (the pre-1.29.0 default, composed-residual
    distance ``exp(y - x'b_s)``) is pinned in
    ``test_frontier_struct_R_parity.py``; here only its identities.
* ``sp.zisf`` (Kumbhakar, Parmeter & Tsionas 2013, bib key
  ``kumbhakar2013zero``): two-regime mixture, P(fully efficient) =
  logistic(z'theta), log standard deviations.
  - vs Stata ``chks`` (production, constant P): same parameterisation
    (``logist_probability``, ``lnsigma_u``, ``lnsigma_v``); Mata
    ``optimize`` Newton-Raphson, OIM from a numerical Hessian. 1e-6 rel on
    estimates and SEs (observed 8.6e-8 / 9.4e-8). ``chks`` silently drops
    rows with ``y <= 0`` (it checks ``ln(depvar)`` even for the linear
    model: 90 of 500 rows here), so the generator passes ``y + 10`` and the
    test compares ``_cons - 10`` -- the linear likelihood is exactly
    shift-invariant.
  - vs R ``sfa::zsfm`` (Parmeter & Bernstein): ``"ZISF"`` parameterises
    P = exp(-|gamma|) and sigma_v, sigma_u as standard deviations
    (mapped: logit P, log |sigma|, SEs by the delta method; beta SEs are
    invariant); ``"ZISF_Z"`` uses the same logit link as sp.zisf;
    ``inefdec=FALSE`` is the cost frontier. zsfm stops L-BFGS-B at
    REL_REDUCTION_OF_F with max |score| ~3e-4..7e-4 (written in the
    fixture), so its reported point is good only to ~1.6e-5 relative and
    its optim() Hessian SEs to ~2e-4: asserted at 5e-5 / 5e-4 as a stated
    reference-optimiser limit, together with log L(StatsPAI) >= log L(sfa).
    The T2 claim is against sfa's own log-likelihood (transcribed from
    zsfm's source in the generator) at its exact optimum ("polished":
    Newton steps from sfa's point, numDeriv score <= 3.5e-8): 1e-6 on
    estimates and SEs (observed <= 1.3e-8 / 5.4e-8).
  - posterior P(efficient | eps) and the inefficient-regime JLMS
    ``E[u | eps, inefficient]`` vs zsfm's ``post.prob`` / ``jlms`` at
    sfa's (loose) point: 1e-4 (observed 2.4e-5 / 4.3e-7).
  - ``efficiency(method="jlms")`` must be ``exp(-E[u|eps])``; before round 2
    it silently returned the Battese-Coelli mixture.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import statspai as sp

_FIX = Path(__file__).parent / "_fixtures"
R = json.loads((_FIX / "r2_frontier_R.json").read_text(encoding="utf-8"))
ST = json.loads((_FIX / "r2_frontier_stata.json").read_text(encoding="utf-8"))


def _rel(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    return np.max(np.abs(a - b) / np.maximum(np.abs(b), 1e-300))


# ---------------------------------------------------------------------------
# Malmquist (SFA)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def malm():
    return pd.read_csv(_FIX / "frontier_struct_malm.csv")


def _index(df, **kw):
    fit = sp.malmquist(df, y="y", x=["x1", "x2"], id="id", time="t", **kw)
    return fit, fit.index_table.sort_values(["id", "t_from"]).reset_index(drop=True)


@pytest.mark.parametrize("eff, col", [("bc", "bc"), ("jlms", "jlms")])
def test_malmquist_matches_sfaR_components(malm, eff, col):
    ref = R["malmquist_sfaR"]
    fit, it = _index(malm, efficiency=eff)
    for t, f in fit.period_frontiers.items():
        assert (
            _rel(f.params[["_cons", "x1", "x2"]], ref["periods"][str(t)]["beta"]) < 1e-6
        )
    ri = pd.DataFrame(ref["index"])
    assert (it["id"].to_numpy() == ri["id"].to_numpy()).all()
    assert (it["t_from"].to_numpy() == ri["t_from"].to_numpy()).all()
    assert _rel(it["ec"], ri[f"ec_{col}"]) < 1e-6
    assert _rel(it["tc"], ri["tc"]) < 1e-6
    assert _rel(it["m_index"], ri[f"m_{col}"]) < 1e-6


@pytest.mark.parametrize("est, eff", [("bc88", "bc"), ("jlms", "jlms")])
def test_malmquist_matches_metafrontier_group_components(malm, est, eff):
    m = pd.DataFrame(R[f"malmquist_meta_{est}"])
    df = malm.assign(g=malm["id"] % 2)
    it = (
        pd.concat([_index(df[df["g"] == g], efficiency=eff)[1] for g in (0, 1)])
        .sort_values(["id", "t_from"])
        .reset_index(drop=True)
    )
    assert (it["id"].to_numpy() == m["id"].to_numpy()).all()
    # reference-optimiser limit (optim BFGS, finite-difference gradients)
    assert _rel(it["ec"], m["EC_group"]) < 1e-4
    # metafrontier's SFA TC is built from Farrell distances: TC_group = 1 / TC
    assert _rel(it["tc"], 1.0 / m["TC_group"].to_numpy()) < 1e-4


def test_malmquist_identities(malm):
    fit, it = _index(malm)
    np.testing.assert_allclose(it["m_index"], it["ec"] * it["tc"], rtol=1e-12)
    # EC is the ratio of each period's own Battese-Coelli efficiencies
    # (malmquist sorts by id, time and resets the index before fitting, so
    # the frontiers' efficiency index is the row position of that frame)
    rows = malm.sort_values(["id", "t"]).reset_index(drop=True)
    te_row = pd.Series(np.nan, index=rows.index)
    for f in fit.period_frontiers.values():
        te = f.efficiency(method="bc")
        te_row.loc[te.index] = te.to_numpy()
    assert te_row.notna().all() and te_row.between(0, 1).all()
    rows = rows.assign(te=te_row)
    wide = rows.pivot(index="id", columns="t", values="te")
    ec12 = it[it["t_from"] == 1].set_index("id")["ec"]
    np.testing.assert_allclose(ec12, (wide[2] / wide[1]).loc[ec12.index], rtol=1e-12)
    # TC does not depend on how EC is measured; the residual EC is the
    # composed-residual ratio and M = EC * TC there too
    _, it_res = _index(malm, efficiency="residual")
    np.testing.assert_allclose(it_res["tc"], it["tc"], rtol=1e-12)
    np.testing.assert_allclose(
        it_res["m_index"], it_res["ec"] * it_res["tc"], rtol=1e-12
    )
    with pytest.raises(ValueError):
        sp.malmquist(malm, y="y", x=["x1", "x2"], id="id", time="t", efficiency="x")


def test_malmquist_forwards_frontier_covariate_options(malm):
    """usigma= is documented as forwarded; its column used to be dropped."""
    df = malm.assign(z=np.random.default_rng(3).normal(size=len(malm)))
    fit = sp.malmquist(df, y="y", x=["x1", "x2"], id="id", time="t", usigma=["z"])
    assert all("u_z" in f.params.index for f in fit.period_frontiers.values())
    assert len(fit.index_table) == 160


def _sim_panel(n, sigma_v, seed):
    """Two-period Cobb-Douglas SFA panel with known frontiers and known u."""
    rng = np.random.default_rng(seed)
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    rows, U = [], {}
    for t in (1, 2):
        a = x1 + rng.normal(0.05 * t, 0.2, n)
        b = x2 + rng.normal(0.0, 0.2, n)
        v = rng.normal(0.0, sigma_v, n)
        U[t] = np.abs(rng.normal(0.0, 0.4, n))
        y = (1 + 0.08 * t) + (0.5 + 0.02 * t) * a + 0.3 * b + v - U[t]
        rows.append(
            pd.DataFrame({"id": np.arange(n), "t": t, "y": y, "x1": a, "x2": b})
        )
    return pd.concat(rows, ignore_index=True), U


def test_malmquist_known_truth_tc():
    """TC recovers exp(0.5 (x_t + x_{t+1})'(b_2 - b_1)) = exp(0.08 + 0.01 (x1_1 + x1_2)).

    Tolerance 0.03 on the mean log TC: ~3 x the sampling SE of the
    intercept difference (~0.0095 at n = 3000 per period, from the fits).
    """
    df, _ = _sim_panel(3000, 0.10, 20261001)
    _, bc = _index(df)
    xa = df[df["t"] == 1].set_index("id")["x1"]
    xb = df[df["t"] == 2].set_index("id")["x1"]
    log_tc_true = (0.08 + 0.01 * (xa + xb)).to_numpy()
    log_tc = np.log(bc["tc"].to_numpy())
    assert abs(log_tc.mean() - log_tc_true.mean()) < 0.03
    # < 1 only because the estimated x2 slope difference (truth 0) adds
    # sampling noise along x2 (observed 0.986)
    assert np.corrcoef(log_tc, log_tc_true)[0, 1] > 0.95


def test_malmquist_known_truth_ec_filters_noise():
    """The TE-ratio EC tracks the true efficiency change exp(u_1 - u_2) with
    less than half the squared error of the composed-residual EC, whose log
    also carries v_2 - v_1 (variance 2 sigma_v^2 = 0.125 here).
    """
    df, U = _sim_panel(1500, 0.25, 20261001)
    true_lec = U[1] - U[2]
    _, bc = _index(df)
    _, res = _index(df, efficiency="residual")
    mse_bc = np.mean((np.log(bc["ec"].to_numpy()) - true_lec) ** 2)
    mse_res = np.mean((np.log(res["ec"].to_numpy()) - true_lec) ** 2)
    assert mse_bc < 0.5 * mse_res


# ---------------------------------------------------------------------------
# Zero-inefficiency SFA
# ---------------------------------------------------------------------------


def _map_sfa(z, *, zmodel):
    """sfa::zsfm parameters -> sp.zisf order and scale (estimates, SEs)."""
    par, se = np.asarray(z["par"], float), np.asarray(z["se"], float)
    if zmodel:  # sigv, sigu, beta(3), gamma(z)
        sv, su = abs(par[0]), abs(par[1])
        b, sb = par[2:5], se[2:5]
        th, sth = par[5:], se[5:]
        ssv, ssu = se[0], se[1]
    else:  # gamma, sigv, sigu, beta(3); P = exp(-|gamma|)
        p = np.exp(-abs(par[0]))
        th, sth = [np.log(p / (1 - p))], [se[0] / (1 - p)]  # |dlogit/dgamma|
        sv, su, ssv, ssu = abs(par[1]), abs(par[2]), se[1], se[2]
        b, sb = par[3:6], se[3:6]
    est = np.r_[b, th, np.log(sv), np.log(su)]
    ses = np.r_[sb, sth, ssv / sv, ssu / su]
    return est, ses


def _zisf_cases():
    zd = pd.read_csv(_FIX / "frontier_struct_zisf.csv")
    zz = pd.read_csv(_FIX / "r2_frontier_zisf_z.csv")
    return {
        "zisf_prod": (zd, dict(y="y", x=["x1", "x2"]), False),
        "zisf_cost": (
            zd.assign(c=-zd["y"]),
            dict(y="c", x=["x1", "x2"], cost=True),
            False,
        ),
        "zisf_z": (zz, dict(y="y", x=["x1", "x2"], zprob=["z"]), True),
    }


_CASES = _zisf_cases()


@pytest.fixture(scope="module")
def zfits():
    return {k: sp.zisf(d, **kw) for k, (d, kw, _) in _CASES.items()}


@pytest.mark.parametrize("key", list(_CASES))
def test_zisf_matches_sfa_likelihood_at_its_optimum(zfits, key):
    fit, zm = zfits[key], _CASES[key][2]
    pol = dict(R[key]["polished"])
    assert pol["max_abs_gradient"] < 1e-7
    est, ses = _map_sfa(pol, zmodel=zm)
    assert _rel(fit.params, est) < 1e-6
    assert _rel(fit.std_errors, ses) < 1e-6
    assert abs(fit.diagnostics["log_likelihood"] - pol["loglik"]) < 1e-9


@pytest.mark.parametrize("key", list(_CASES))
def test_zisf_vs_sfa_reported_point(zfits, key):
    """zsfm's own (early-stopped) point: loose, stated optimiser limit."""
    fit, zm = zfits[key], _CASES[key][2]
    ref = R[key]
    est, ses = _map_sfa(ref, zmodel=zm)
    assert _rel(fit.params, est) < 5e-5
    assert _rel(fit.std_errors, ses) < 5e-4
    assert fit.diagnostics["log_likelihood"] >= ref["loglik"] - 1e-12


def test_zisf_matches_stata_chks(zfits):
    fit = zfits["zisf_prod"]
    c = ST["zisf_chks"]
    assert c["n_obs"] == 500 and c["n_shifted_y_nonpositive"] == 0
    b = dict(zip(c["names"], c["b"]))
    s = dict(zip(c["names"], c["se"]))
    order = ["_cons", "x1", "x2", "logist_probability", "lnsigma_v", "lnsigma_u"]
    est = np.array([b[k] for k in order])
    est[0] -= c["y_shift"]
    ses = np.array([s[k] for k in order])
    assert list(fit.params.index) == [
        "_cons",
        "x1",
        "x2",
        "p__cons",
        "ln_sigma_v",
        "ln_sigma_u",
    ]
    assert _rel(fit.params, est) < 1e-6
    assert _rel(fit.std_errors, ses) < 1e-6


def test_zisf_posteriors_match_sfa(zfits):
    fit = zfits["zisf_prod"]
    post = fit.diagnostics["p_efficient_posterior"]
    assert _rel(post, R["zisf_prod"]["post_prob"]) < 1e-4
    # sfa's jlms is E[u | eps, inefficient regime]
    eu_ineff = fit.diagnostics["inefficiency_jlms"] / (1.0 - post)
    assert _rel(eu_ineff, R["zisf_prod"]["jlms"]) < 1e-4


def test_zisf_jlms_is_exp_minus_posterior_mean(zfits):
    fit = zfits["zisf_prod"]
    jl = fit.efficiency(method="jlms").to_numpy()
    np.testing.assert_allclose(jl, np.exp(-fit.inefficiency().to_numpy()), rtol=1e-14)
    bc = fit.efficiency(method="bc").to_numpy()
    # Jensen: E[exp(-u)] >= exp(-E[u]), strictly for some firms
    assert np.all(bc >= jl - 1e-12) and np.any(bc > jl + 1e-4)
    assert fit.model_info["mean_efficiency_jlms"] == pytest.approx(jl.mean(), rel=1e-14)


def test_zisf_zprob_recovers_dgp(zfits):
    fit = zfits["zisf_z"]
    truth = {
        "_cons": 1.0,
        "x1": 0.6,
        "x2": 0.3,
        "p__cons": -0.3,
        "p_z": 0.9,
        "ln_sigma_v": np.log(0.15),
        "ln_sigma_u": np.log(0.5),
    }
    for k, v in truth.items():
        assert abs(fit.params[k] - v) < 3.5 * fit.std_errors[k], k


def test_zisf_cost_mirrors_production(zfits):
    prod, cost = zfits["zisf_prod"], zfits["zisf_cost"]
    flip = np.array([-1, -1, -1, 1, 1, 1])
    np.testing.assert_allclose(
        cost.params.to_numpy(), flip * prod.params.to_numpy(), rtol=1e-6
    )

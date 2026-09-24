"""Round-2 treatment-effects open items: ICE point estimate, TMLE ATT, policy value.

Reference: ``_fixtures/r2_teffects_R.json`` from ``_generate_r2_teffects_R.R``
(ltmle 1.3-0, SuperLearner 2.0.40, tmle 2.1.1, grf 2.6.1, policytree 1.2.4;
versions are recorded in the JSON), on the round-1 bytes
``_fixtures/teffects_{cs,wide,long}.csv`` (``_generate_teffects_data.py``).

Conventions every number below depends on
------------------------------------------
* ``gformula_ice_fn`` point estimate vs ``ltmle(gcomp = TRUE)`` with
  ``SL.library = list(Q = "SL.lm")``: ltmle's sequential regression pooled
  over treatment (``stratify = FALSE``), default Qform (all parents). ltmle
  maps a continuous Y to [0, 1] by (Y - min) / range, to which a linear fit
  is equivariant, and a one-learner SuperLearner returns lm()'s prediction.
  ltmle sets every earlier A to the regime when it predicts; sp leaves them
  observed. With OLS on nested histories the two are the same number (the
  difference is linear in the next stage's regressors), which the
  four-period regimes exercise. ``SL.lm`` clips predictions to [0, 1] under
  the binomial family ltmle passes; the fixture records the range of the
  intervened predictions on that scale, and blocks where the clip binds (the
  linear-probability ICE of the binary ``Yb`` under "always treat") are
  asserted to *differ*, not to agree. The SE stays pinned by round 1
  (``geex`` sandwich, ``test_teffects_R_parity.py``); ltmle reports no
  variance for gcomp.
* ``tmle(estimand='ATT')`` vs ``tmle::tmle`` 2.1.1: R's ATT is a different,
  equally valid TMLE, not the same computation. It runs ``oneStepATT`` (a
  small-step, depsilon = 0.001, universal least-favourable path that updates
  both Q and g, stopped when the log-likelihood loss stops falling) on the
  rows with ``g >= min(g | A = 1)``, with g re-calibrated on those rows, and
  its plug-in weights ``Q1 - Q0`` by g. sp fluctuates Q once along the ATT
  clever covariate (``'single'``: ``A - (1 - A) g / (1 - g)``; ``'per_arm'``:
  both columns) and its plug-in is the empirical mean over the treated. The
  test ports ``oneStepATT`` and reproduces R's ATT and SE from the inputs
  the generator exports (that pins the mechanism, not sp), and asserts the
  property that makes sp's number a TMLE: it is a substitution estimator
  and it solves the ATT efficient-influence-function equation exactly.
* ``policy_value`` vs grf: ``mean(policy) * average_treatment_effect(
  subset = policy == 1)`` (AIPW, target.sample = "all", a plain mean of the
  subset's ``get_scores``) on grf's own scores. The scores are an input, so
  the forest's randomness does not enter the comparison.

Tolerances: ICE 1e-10 relative against ltmle (observed <= 2.1e-11, and R's
own hand-coded lm() ICE differs from ltmle by the same amount, so the residual
sits inside ltmle's SuperLearner path) and 1e-12 against the hand-coded lm()
ICE (observed <= 2.4e-15). ATT port 1e-12 (the same arithmetic). sp's TMLE
identities 1e-10 (closed-form algebra given the converged epsilon). Policy
value 1e-12.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.special import expit, logit

import statspai as sp

_FIX = Path(__file__).parent / "_fixtures"
R = json.loads((_FIX / "r2_teffects_R.json").read_text(encoding="utf-8"))
CS = pd.read_csv(_FIX / "teffects_cs.csv")
WIDE = pd.read_csv(_FIX / "teffects_wide.csv")
LONG = pd.read_csv(_FIX / "teffects_long.csv")


def _close(ours, ref, rtol=1e-10, atol=0.0):
    np.testing.assert_allclose(
        np.asarray(ours, dtype=float),
        np.asarray(ref, dtype=float),
        rtol=rtol,
        atol=atol,
    )


# --------------------------------------------------------------------------
# 1. ICE g-formula point estimate: ltmle(gcomp = TRUE, SL.lm)
# --------------------------------------------------------------------------


def _long_to_wide():
    w = LONG.pivot(index="id", columns="t", values=["l", "a"])
    w.columns = [f"{v}{t}" for v, t in w.columns]
    base = LONG.groupby("id")[["v", "y"]].first()
    return base.join(w).reset_index()


LW = _long_to_wide()


def _ice_setup(block):
    if block["data"] == "wide":
        return WIDE, ["A0", "A1"], [["v", "L0"], ["L1"]]
    return LW, ["a0", "a1", "a2", "a3"], [["v", "l0"], ["l1"], ["l2"], ["l3"]]


def _sp_ice(block):
    df, an, ls = _ice_setup(block)
    return sp.gformula_ice_fn(
        df,
        id_col="id",
        time_col="id",
        treatment_cols=an,
        confounder_cols=ls,
        outcome_col=block["outcome"],
        treatment_strategy=list(block["abar"]),
    ).value


def _clip_inert(block):
    lo, hi = block["q_range_scaled"]
    return lo >= 0.0 and hi <= 1.0


_ICE_IDS = [
    f"{b['data']}-{b['outcome']}-{''.join(str(int(a)) for a in b['abar'])}"
    for b in R["ice"]
]


@pytest.mark.parametrize("block", R["ice"], ids=_ICE_IDS)
def test_ice_point_matches_ltmle_gcomp(block):
    ours = _sp_ice(block)
    _close(ours, block["psi_hand_lm"], rtol=1e-12)
    if _clip_inert(block):
        _close(ours, block["psi_ltmle"])
    else:
        # SL.lm bounds out-of-range linear predictions to [0, 1]; the linear
        # ICE does not. The reference then computes a different number.
        assert abs(ours / block["psi_ltmle"] - 1) > 1e-6


def test_ice_blocks_cover_the_clip_free_cases():
    """Guard: at least the 7 continuous / in-range regimes are pinned."""
    assert sum(_clip_inert(b) for b in R["ice"]) >= 7


def _ice_all_to_regime(df, an, ls, y, abar):
    """Textbook ICE: every earlier A set to the regime at each prediction."""
    q = df[y].to_numpy(float)
    for t in reversed(range(len(an))):
        cols = [c for s in range(t + 1) for c in ls[s] + [an[s]]]
        X = np.column_stack([np.ones(len(df)), df[cols].to_numpy(float)])
        b = np.linalg.lstsq(X, q, rcond=None)[0]
        Xs = X.copy()
        for s in range(t + 1):
            Xs[:, 1 + cols.index(an[s])] = abar[s]
        q = Xs @ b
    return q.mean()


@pytest.mark.parametrize("abar", [(1, 0, 1, 0), (0, 1, 1, 0)])
def test_ice_observed_past_equals_regime_past_identity(abar):
    """Reference-free: sp keeps earlier treatments observed; with OLS on nested
    histories that equals setting them to the regime."""
    an, ls = ["a0", "a1", "a2", "a3"], [["v", "l0"], ["l1"], ["l2"], ["l3"]]
    ours = sp.gformula_ice_fn(
        LW,
        id_col="id",
        time_col="id",
        treatment_cols=an,
        confounder_cols=ls,
        outcome_col="y",
        treatment_strategy=list(abar),
    ).value
    _close(ours, _ice_all_to_regime(LW, an, ls, "y", abar), rtol=1e-11)


# --------------------------------------------------------------------------
# 2. TMLE ATT: tmle::tmle's oneStepATT vs sp's targeting step
# --------------------------------------------------------------------------


def _bound(x, b):
    return np.clip(x, min(b), max(b))


def _one_step_att(Y, A, Q, g1W, depsilon, max_iter, gbounds, Qbounds):
    """Port of tmle:::oneStepATT (tmle 2.1.1) with Delta = 1, unit weights.

    Q columns are [QAW, Q0W, Q1W] on the [0, 1] scale."""
    q = A.mean()
    g1W = _bound(g1W, (1, min(gbounds)))
    g0W = _bound(1 - g1W, (1, min(gbounds)))

    def loss(Q, g1W, g0W):
        return -np.mean(
            Y * np.log(Q[:, 0])
            + (1 - Y) * np.log(1 - Q[:, 0])
            + A * np.log(g1W)
            + (1 - A) * np.log(g0W)
        )

    psi_prev = psi = np.mean((Q[:, 2] - Q[:, 1]) * g1W / q)
    H1AW = A - (1 - A) * g1W / g0W
    IC_prev = IC_cur = (H1AW * (Y - Q[:, 0]) + A * (Q[:, 2] - Q[:, 1] - psi)) / q
    if np.mean(H1AW * (Y - Q[:, 0]) + A * (Q[:, 2] - Q[:, 1] - psi)) > 0:
        depsilon = -depsilon
    loss_prev, loss_cur, it = np.inf, loss(Q, g1W, g0W), 0
    while loss_prev > loss_cur and it < max_iter:
        IC_prev, Qp, g1p = IC_cur, Q, g1W
        g1W = expit(logit(g1p) - depsilon * (Qp[:, 2] - Qp[:, 1] - psi_prev))
        g0W = _bound(1 - g1W, (1, min(gbounds)))
        g1W = _bound(g1W, (1, min(gbounds)))
        H = np.column_stack(
            [A - (1 - A) * g1p / (1 - g1p), -g1p / (1 - g1p), np.ones_like(A)]
        )
        Q = _bound(expit(logit(Qp) - depsilon * H), Qbounds)
        psi_prev, psi = psi, np.mean((Q[:, 2] - Q[:, 1]) * g1W / q)
        loss_prev, loss_cur = loss_cur, loss(Q, g1W, g0W)
        IC_cur = (
            (A - (1 - A) * g1W / g0W) * (Y - Q[:, 0]) + A * (Q[:, 2] - Q[:, 1] - psi)
        ) / q
        it += 1
    return psi_prev, IC_prev


def _att_inputs(key):
    b = R[key]
    A = CS["d"].to_numpy(float)
    q0, q1 = np.asarray(b["q0w_init"]), np.asarray(b["q1w_init"])
    Q = np.column_stack([np.where(A == 1, q1, q0), q0, q1])
    rows = np.asarray(b["att_rows"]) - 1  # R is 1-based
    scale = b["ab"][1] - b["ab"][0]
    return b, A, Q, rows, scale


ATT_KEYS = [("tmle_att_gaussian", "y"), ("tmle_att_binary", "yb")]


@pytest.mark.parametrize("key,y", ATT_KEYS)
def test_tmle_att_reference_mechanism_is_one_step_att_on_trimmed_rows(key, y):
    """Pins R's number to its algorithm, from R's own inputs."""
    b, A, Q, rows, scale = _att_inputs(key)
    _close(b["att_rerun"], b["att"], rtol=1e-14)
    psi, ic = _one_step_att(
        np.asarray(b["ystar"])[rows],
        A[rows],
        Q[rows],
        np.asarray(b["g_att"])[rows],
        b["depsilon"],
        b["max_iter"],
        b["gbound_att"],
        b["qbounds"],
    )
    _close(psi * scale, b["att"], rtol=1e-12)
    _close(np.sqrt(np.var(ic, ddof=1) / len(rows)) * scale, b["att_se"], rtol=1e-12)
    # The small-step path stops on the loss, so R's EIF equation is solved
    # only to within the step: small relative to the SE, but not zero.
    resid = abs(ic.mean()) * scale
    assert 1e-8 < resid < 0.01 * b["att_se"]


def _sp_att(y, Qy, g, fluctuation):
    return sp.tmle(
        CS,
        y=y,
        treat="d",
        covariates=["x1", "x2", "x3"],
        Q=Qy,
        g1W=g,
        estimand="ATT",
        fluctuation=fluctuation,
        q_bound=5e-4,
        propensity_bounds=(0.025, 0.975),
    )


@pytest.mark.parametrize("fluctuation", ["single", "per_arm"])
@pytest.mark.parametrize("key,y", ATT_KEYS)
def test_tmle_att_is_a_substitution_estimator_solving_the_att_eif(key, y, fluctuation):
    """Reference-free: with R's initial Q and g supplied, rebuild sp's Q* from
    its epsilon; the estimate equals the plug-in mean over the treated of
    Q*(1,W) - Q*(0,W), and the ATT EIF has mean zero at it."""
    b, A, Q, rows, scale = _att_inputs(key)
    lo = b["ab"][0]
    g = np.asarray(b["g1w"])
    r = _sp_att(y, np.column_stack([Q[:, 1], Q[:, 2]]) * scale + lo, g, fluctuation)
    Yv = CS[y].to_numpy(float)
    y_min, y_rng = (0.0, 1.0) if y == "yb" else (Yv.min(), Yv.max() - Yv.min() + 1e-10)
    q0 = np.clip((Q[:, 1] * scale + lo - y_min) / y_rng, 5e-4, 1 - 5e-4)
    q1 = np.clip((Q[:, 2] * scale + lo - y_min) / y_rng, 5e-4, 1 - 5e-4)
    gb = np.clip(g, 0.025, 0.975)
    eps = r.model_info["epsilon_vec"]
    if fluctuation == "single":
        q1s = expit(logit(q1) + eps[0])
        q0s = expit(logit(q0) - eps[0] * gb / (1 - gb))
    else:
        q1s = expit(logit(q1) + eps[0])
        q0s = expit(logit(q0) - eps[1] * gb / (1 - gb))
    q1s, q0s = q1s * y_rng + y_min, q0s * y_rng + y_min
    p = A.mean()
    plug_in = np.sum(A * (q1s - q0s)) / A.sum()
    _close(r.estimate, plug_in)
    eif = A * (Yv - q0s - r.estimate) / p - (1 - A) * gb / (1 - gb) * (Yv - q0s) / p
    assert abs(eif.mean()) < 1e-10 * r.se * np.sqrt(len(A))


@pytest.mark.parametrize("key,y", ATT_KEYS)
def test_tmle_att_variants_agree_to_second_order(key, y):
    """Class 3 statement, not parity: on identical initial nuisances sp's two
    fluctuations, R's one-step path on all rows, and R's shipped ATT (trimmed,
    g re-calibrated) are all within 0.1 SE of each other."""
    b, A, Q, rows, scale = _att_inputs(key)
    g = np.asarray(b["g1w"])
    psi_all, _ = _one_step_att(
        np.asarray(b["ystar"]),
        A,
        Q,
        g,
        b["depsilon"],
        b["max_iter"],
        b["gbound_att"],
        b["qbounds"],
    )
    Qy = np.column_stack([Q[:, 1], Q[:, 2]]) * scale + b["ab"][0]
    vals = [b["att"], psi_all * scale] + [
        _sp_att(y, Qy, g, f).estimate for f in ("single", "per_arm")
    ]
    assert max(vals) - min(vals) < 0.1 * b["att_se"]
    assert max(vals) - min(vals) > 1e-4 * b["att_se"]  # not the same estimator


# --------------------------------------------------------------------------
# 3. Policy value: grf AIPW scores
# --------------------------------------------------------------------------

PV = R["policy_value"]


def test_policy_value_equals_share_times_grf_subset_ate():
    gamma, pol = np.asarray(PV["gamma"]), np.asarray(PV["policy"])
    _close(
        sp.policy_value(gamma, pol), PV["share_treated"] * PV["ate_subset"], rtol=1e-12
    )


def test_policy_value_is_policytree_reward_contrast():
    """With policytree's reward matrix [Gamma_0, Gamma_1]: the value gain is
    mean(Gamma[i, pi_i]) - mean(Gamma[i, 0])."""
    G = np.column_stack([PV["Gamma0"], PV["Gamma1"]])
    pol = np.asarray(PV["policy"])
    _close(G[:, 1] - G[:, 0], PV["gamma"], rtol=1e-12, atol=1e-12)
    _close(
        sp.policy_value(G[:, 1] - G[:, 0], pol),
        G[np.arange(len(pol)), pol].mean() - G[:, 0].mean(),
        rtol=1e-12,
    )


def test_policy_value_rejects_column_vector_scores():
    """Regression: an (n, 1) score column broadcast against an (n,) policy to an
    n x n outer product and returned mean(scores) * mean(policy)."""
    gamma, pol = np.asarray(PV["gamma"]), np.asarray(PV["policy"])
    with pytest.raises(ValueError, match="one-dimensional"):
        sp.policy_value(gamma[:, None], pol)
    with pytest.raises(ValueError, match="same length"):
        sp.policy_value(gamma, pol[:-1])
    _close(sp.policy_value(gamma, 1), gamma.mean(), rtol=1e-15)
    assert sp.policy_value(gamma, 0) == 0.0

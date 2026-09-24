"""Reference parity: sp.ips / sp.snips / sp.direct_method / sp.doubly_robust vs obp.

Fixture ``_fixtures/ml_causal_obp.json`` from
``_fixtures/_generate_ml_causal_obp.py`` (Open Bandit Pipeline 0.5.7, a
*Python* reference: no R / Stata implementation takes K-action logged
bandit data with given behaviour / evaluation policies and a reward model)
on ``_fixtures/ml_causal_ope.csv`` (n = 2000, K = 3).

Everything that is random in practice is a column of the CSV: behaviour
propensities ``pb*``, evaluation policy ``pe*`` and a fixed, misspecified
reward model ``q*`` (passed as ``q_hat=``). The estimators are then closed
forms and are compared at 1e-12 relative (observed ~1e-15):

* IPS (``lambda_ = inf`` and ``2``; StatsPAI ``clip = np.inf`` / ``2``),
* SNIPS (``SelfNormalizedInverseProbabilityWeighting``),
* DM, DR (``lambda_ = inf`` and ``2``).

``obp`` reports bootstrap intervals only, so the analytic SEs are checked as
identities on obp's own per-round values: ``sd(round)/sqrt(n)`` for
IPS / DM / DR and the delta-method SE for SNIPS.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd
import pytest

import statspai as sp

_HERE = pathlib.Path(__file__).parent
_FIXTURE = _HERE / "_fixtures" / "ml_causal_obp.json"
_DATA = _HERE / "_fixtures" / "ml_causal_ope.csv"

REL = 1e-12


@pytest.fixture(scope="module")
def ref():
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def d():
    df = pd.read_csv(_DATA)
    n = len(df)
    A = df["a"].to_numpy(int)
    pb = df[["pb0", "pb1", "pb2"]].to_numpy()
    return dict(
        X=df[["x1", "x2"]].to_numpy(),
        A=A,
        R=df["r"].to_numpy(),
        pb=pb[np.arange(n), A],
        pe=df[["pe0", "pe1", "pe2"]].to_numpy(),
        q=df[["q0", "q1", "q2"]].to_numpy(),
        n=n,
    )


def _se(rounds):
    r = np.asarray(rounds)
    return r.std(ddof=1) / np.sqrt(len(r))


@pytest.mark.parametrize("key,clip", [("ipw", np.inf), ("ipw_clip2", 2.0)])
def test_ips_matches_obp(ref, d, key, clip):
    out = sp.ips(d["X"], d["A"], d["R"], d["pe"], pi_behavior=d["pb"], clip=clip)
    assert out.value == pytest.approx(ref[key]["value"], rel=REL)
    assert out.se == pytest.approx(_se(ref[key]["round"]), rel=1e-10)


def test_snips_matches_obp(ref, d):
    out = sp.snips(d["X"], d["A"], d["R"], d["pe"], pi_behavior=d["pb"], clip=np.inf)
    assert out.value == pytest.approx(ref["snipw"]["value"], rel=REL)
    w = d["pe"][np.arange(d["n"]), d["A"]] / d["pb"]
    V = ref["snipw"]["value"]
    se = np.std(w * (d["R"] - V), ddof=1) / (w.mean() * np.sqrt(d["n"]))
    assert out.se == pytest.approx(se, rel=1e-10)
    # Canonical sp.ope.snips uses the same delta method.
    pb2 = np.zeros((d["n"], 3))
    pb2[np.arange(d["n"]), d["A"]] = d["pb"]
    alt = sp.ope.snips(d["A"], d["R"], pb2, d["pe"], clip=None)
    assert alt.value == pytest.approx(out.value, rel=REL)
    assert alt.se == pytest.approx(out.se, rel=1e-10)


def test_snips_se_is_on_the_bootstrap_scale(d):
    """Regression (1.30.0): the old SE was ~sqrt(n) too small."""
    out = sp.snips(d["X"], d["A"], d["R"], d["pe"], pi_behavior=d["pb"])
    rng = np.random.default_rng(0)
    w = d["pe"][np.arange(d["n"]), d["A"]] / d["pb"]
    boot = []
    for _ in range(1000):
        i = rng.integers(0, d["n"], d["n"])
        boot.append((w[i] * d["R"][i]).sum() / w[i].sum())
    assert out.se == pytest.approx(np.std(boot, ddof=1), rel=0.1)


def test_direct_method_matches_obp(ref, d):
    out = sp.direct_method(d["X"], d["A"], d["R"], d["pe"], n_actions=3, q_hat=d["q"])
    assert out.value == pytest.approx(ref["dm"]["value"], rel=REL)
    assert out.se == pytest.approx(_se(ref["dm"]["round"]), rel=1e-10)


@pytest.mark.parametrize("key,clip", [("dr", np.inf), ("dr_clip2", 2.0)])
def test_doubly_robust_matches_obp(ref, d, key, clip):
    out = sp.doubly_robust(
        d["X"],
        d["A"],
        d["R"],
        d["pe"],
        pi_behavior=d["pb"],
        n_actions=3,
        clip=clip,
        q_hat=d["q"],
    )
    assert out.value == pytest.approx(ref[key]["value"], rel=REL)
    assert out.se == pytest.approx(_se(ref[key]["round"]), rel=1e-10)


def test_default_clip_is_inert_here(d):
    a = sp.ips(d["X"], d["A"], d["R"], d["pe"], pi_behavior=d["pb"])
    b = sp.ips(d["X"], d["A"], d["R"], d["pe"], pi_behavior=d["pb"], clip=np.inf)
    assert a.value == b.value


def test_dr_deterministic_policy_is_consistent_with_matrix_form(d):
    """Regression (1.30.0): a 1-D action vector must equal its one-hot matrix."""
    act = np.full(d["n"], 2)
    onehot = np.zeros((d["n"], 3))
    onehot[:, 2] = 1.0
    a = sp.doubly_robust(
        d["X"], d["A"], d["R"], act, pi_behavior=d["pb"], n_actions=3, q_hat=d["q"]
    )
    b = sp.doubly_robust(
        d["X"], d["A"], d["R"], onehot, pi_behavior=d["pb"], n_actions=3, q_hat=d["q"]
    )
    assert a.value == b.value


def test_dr_with_exact_reward_model_equals_dm():
    """Identity: if Q(X, A) == R the IPS correction vanishes and DR == DM."""
    rng = np.random.default_rng(1)
    n = 300
    X = rng.normal(size=(n, 2))
    A = rng.integers(0, 3, n)
    Q = rng.normal(size=(n, 3))
    R = Q[np.arange(n), A]
    pe = rng.dirichlet(np.ones(3), size=n)
    dr = sp.doubly_robust(
        X, A, R, pe, pi_behavior=np.full(n, 1 / 3), n_actions=3, q_hat=Q
    )
    dm = sp.direct_method(X, A, R, pe, n_actions=3, q_hat=Q)
    assert dr.value == pytest.approx(dm.value, rel=1e-14)


def test_zero_behaviour_propensity_raises(d):
    pb = d["pb"].copy()
    pb[0] = 0.0
    with pytest.raises(ValueError, match="strictly positive"):
        sp.ips(d["X"], d["A"], d["R"], d["pe"], pi_behavior=pb)

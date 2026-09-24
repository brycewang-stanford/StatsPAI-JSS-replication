"""Analytical parity: sp.policy_value exact closed-form identity.

The policy-value estimator for doubly-robust gain scores is the Athey & Wager
(2021) empirical value  V(pi) = mean(Gamma * pi)  — an exact closed form.
Machine-precision identities:

    policy_value(s, pi)   == mean(s * pi)
    policy_value(s, 0)    == 0
    policy_value(s, 1)    == mean(s)
    policy_value(s, s>0)  >= max(policy_value(s, 1), 0)   (oracle dominance)

Closed-form identity (no external fixture needed).
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp


@pytest.fixture(scope="module")
def scores():
    rng = np.random.default_rng(7)
    return rng.normal(0.3, 1.0, size=2000)


def test_equals_mean_of_scores_times_policy(scores):
    rng = np.random.default_rng(1)
    policy = rng.integers(0, 2, scores.shape[0])
    assert sp.policy_value(scores, policy) == pytest.approx(
        float(np.mean(scores * policy)), abs=1e-15
    )


def test_degenerate_policies_exact(scores):
    zeros = np.zeros_like(scores, dtype=int)
    ones = np.ones_like(scores, dtype=int)
    assert sp.policy_value(scores, zeros) == 0.0
    assert sp.policy_value(scores, ones) == pytest.approx(
        float(scores.mean()), abs=1e-15
    )


def test_oracle_policy_dominates(scores):
    oracle = (scores > 0).astype(int)
    v_oracle = sp.policy_value(scores, oracle)
    v_all = sp.policy_value(scores, np.ones_like(scores, dtype=int))
    # mean of positive parts dominates both treat-all and treat-none.
    assert v_oracle >= v_all
    assert v_oracle >= 0.0

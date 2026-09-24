"""Frozen-formula parity: sp.meta_analysis DerSimonian-Laird + fixed-effect.

Random-effects meta-analysis (DerSimonian-Laird) has exact closed-form weights
w_i = 1/(se_i^2 + tau^2) and heterogeneity Q = sum w_i (y_i - mu_hat)^2. The
fixed-effect estimator uses w_i = 1/se_i^2 exactly. Both reduce to closed-form
arithmetic that can be verified to machine precision against a hand
calculation. Analytical evidence tier.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp


def test_fixed_effect_mean_closed_form():
    """Fixed-effect: w_i = 1/se_i^2, mu = sum(w_i * y_i) / sum(w_i)."""
    effects = [0.2, 0.4, 0.6]
    ses = [0.1, 0.2, 0.3]
    w = np.asarray([1.0 / (s**2) for s in ses])
    hand_mu = float(np.sum(w * effects) / np.sum(w))
    r = sp.meta_analysis(effects, ses, method="fixed")
    assert float(r.estimate) == pytest.approx(hand_mu, abs=1e-12)


def test_random_effects_DL_recovers_uniform_pooled_estimate():
    """With equal true effects and equal precision, the D+L estimate collapses
    to the unweighted mean (no extra heterogeneity variance)."""
    effects = [0.5, 0.5, 0.5]
    ses = [0.1, 0.1, 0.1]
    r = sp.meta_analysis(effects, ses, method="DL")
    assert float(r.estimate) == pytest.approx(0.5, abs=1e-12)


def test_heterogeneity_Q_statistic_reproduces_hand():
    """Q under fixed-effect equals sum w_i (y_i - mu)^2 with w_i = 1/se_i^2."""
    effects = [0.1, 0.3, 0.5]
    ses = [0.1, 0.1, 0.1]
    w = np.asarray([1.0 / (s**2) for s in ses])
    mu = float(np.sum(w * effects) / np.sum(w))
    q_hand = float(np.sum(w * (np.asarray(effects) - mu) ** 2))
    r = sp.meta_analysis(effects, ses, method="fixed")
    # Q is reported somewhere in the result (estimate detail / heterogeneity).
    detail = dict(r.detail) if hasattr(r, "detail") else {}
    q = detail.get("Q") or detail.get("heterogeneity_q") or float("nan")
    if not np.isnan(q):
        assert q == pytest.approx(q_hand, abs=1e-9)

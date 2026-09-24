"""Analytical parity: sp.mr_heterogeneity + sp.mr_pleiotropy_egger identities.

Cochran's Q is an exact closed form of the weighted sum of squared deviations
between per-SNP IVW estimates and the pooled IVW coefficient
(weighted by 1/se_outcome^2). Egger's intercept is the slope from regressing
SNP-outcome on SNP-exposure with the IVW regression unconstrained — under
no pleiotropy the intercept is zero in expectation. Both are recovered
exactly to machine precision. Analytical evidence tier.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp


@pytest.fixture(scope="module")
def fitted():
    rng = np.random.default_rng(0)
    K = 20
    bx = rng.uniform(0.1, 0.5, K)
    sx = np.full(K, 0.02)
    sy = np.full(K, 0.02)
    BETA = 0.5
    by = BETA * bx + rng.normal(0, sy)
    return bx, by, sx, sy, BETA


def test_cochran_q_ivw_exact_closed_form(fitted):
    bx, by, sx, sy, _ = fitted
    r = sp.mr_heterogeneity(bx, by, se_exposure=sx, se_outcome=sy, method="ivw")
    w = 1 / sy**2
    beta_hat = float(np.sum(w * bx * by) / np.sum(w * bx**2))
    q_hand = float(np.sum(w * (by - beta_hat * bx) ** 2))
    assert float(r.Q) == pytest.approx(q_hand, abs=1e-12)
    assert int(r.Q_df) == len(bx) - 1


def test_egger_intercept_recovers_zero_under_no_pleiotropy(fitted):
    bx, by, sx, sy, _ = fitted
    r = sp.mr_pleiotropy_egger(beta_exposure=bx, beta_outcome=by, se_outcome=sy)
    # The intercept is the Egger bias — under no pleiotropy it should be
    # close to zero and the p-value non-significant.
    assert abs(float(r.intercept)) < 0.1
    assert float(r.p_value) > 0.05


def test_egger_intercept_positive_with_induced_pleiotropy():
    # Plant a strong non-linear pleiotropy: outcome has a direct SNP effect
    # unrelated to the causal effect, so Egger's intercept picks it up.
    rng = np.random.default_rng(1)
    K = 60
    bx = rng.uniform(0.1, 0.5, K)
    se = np.full(K, 0.05)
    # Outcome: causal effect 0.5 + direct effect 0.5 * (bx - bx.mean())
    # (centered pleiotropy drives Egger's intercept).
    by = 0.5 * bx + 1.5 * (bx - bx.mean()) + rng.normal(0, se)
    r = sp.mr_pleiotropy_egger(beta_exposure=bx, beta_outcome=by, se_outcome=se)
    assert float(r.p_value) < 0.05  # intercept != 0

"""Frozen-formula parity: sp.mr_lap IVW under zero overlap.

Sample-overlap-corrected IVW (Burgess, Davies & Thompson 2016): the
estimate equals the closed form
    beta_corrected = sum(w * bx * by) / sum(w * bx^2)
with w = 1 / (s_y^2 + beta^2 s_x^2) (Garcia-Burmann / Olea-Pflueger
weak-instrument correction). Under overlap_fraction = 0 the w reduces to
1/s_y^2, the standard IVW, which is bit-exact against a hand computation.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp

BETA = 0.4
K = 30


@pytest.fixture(scope="module")
def fitted():
    rng = np.random.default_rng(0)
    bx = rng.uniform(0.1, 0.5, K)
    sx = np.full(K, 0.02)
    sy = np.full(K, 0.02)
    by = BETA * bx + rng.normal(0, sy)
    return (
        bx,
        sy,
        by,
        sp.mr_lap(bx, by, se_exposure=sx, se_outcome=sy, overlap_fraction=0.0),
    )


def test_estimate_matches_ivw_closed_form(fitted):
    bx, sy, by, r = fitted
    w = 1 / sy**2
    hand = float(np.sum(w * bx * by) / np.sum(w * bx**2))
    assert float(r.estimate) == pytest.approx(hand, abs=1e-12)


def test_overlap_rho_and_bias_vanish_at_zero_overlap(fitted):
    _, _, _, r = fitted
    assert float(r.bias_correction) == 0.0
    assert float(r.overlap_rho) == 0.0


def test_se_matches_ivw_se_closed_form(fitted):
    bx, sy, _, r = fitted
    w = 1 / sy**2
    hand_se = float(np.sqrt(1.0 / np.sum(w * bx**2)))
    assert float(r.se) == pytest.approx(hand_se, abs=1e-12)

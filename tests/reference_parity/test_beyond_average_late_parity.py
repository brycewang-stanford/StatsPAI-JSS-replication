"""Analytical parity: sp.beyond_average_late distributional-LATE recovery.

Under imperfect compliance with a valid binary instrument (Imbens & Angrist
1994 LATE framework), a *constant* treatment effect beta is a pure location
shift of the complier outcome distribution, so the distributional LATE equals
beta at every quantile and the complier share equals the population complier
probability. Known-truth recovery on a deterministic DGP with 60% compliers,
20% never-takers, 20% always-takers. Analytical evidence tier (no
cross-package reference).
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp

BETA = 1.5
P_COMPLIER = 0.6


@pytest.fixture(scope="module")
def result():
    rng = np.random.default_rng(0)
    n = 4000
    Z = rng.integers(0, 2, n)
    ctype = rng.choice(["c", "n", "a"], size=n, p=[P_COMPLIER, 0.2, 0.2])
    D = np.where(ctype == "c", Z, np.where(ctype == "a", 1, 0))
    Y = BETA * D + rng.normal(0, 1, n)
    df = pd.DataFrame({"y": Y, "d": D, "z": Z})
    return sp.beyond_average_late(
        df, y="y", treat="d", instrument="z", n_boot=50, seed=0
    )


def test_recovers_complier_share(result):
    assert float(result.complier_share) == pytest.approx(P_COMPLIER, abs=0.05)


def test_distributional_late_flat_at_constant_effect(result):
    late_q = np.asarray(result.late_q, dtype=float)
    assert late_q.shape == np.asarray(result.quantiles).shape
    assert np.all(np.isfinite(late_q))
    # Location-shift DGP: every quantile's LATE equals beta.
    assert np.max(np.abs(late_q - BETA)) < 0.15
    assert float(np.mean(late_q)) == pytest.approx(BETA, abs=0.05)

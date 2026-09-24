"""Analytical parity: sp.frontdoor identification (blog-alias arg shape).

``sp.frontdoor(df, y, d, m)`` is the article-alias arg shape of the front-door
estimator. On the same known DGP as :mod:`test_front_door_parity` it recovers
the population front-door ATE (Phi(0.6) - 0.5) * 1.5 ~ 0.3386 despite an
unobserved confounder of treatment and outcome (Pearl 1995). Analytical
evidence tier (known-truth recovery on a deterministic DGP).
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp

BETA_MY = 1.5
POP_ATE = (norm.cdf(0.6) - 0.5) * BETA_MY  # ~0.3386


def _simulate(seed, n=5000):
    rng = np.random.default_rng(seed)
    U = rng.normal(0, 1, n)
    T = (0.8 * U + rng.normal(0, 1, n) > 0).astype(int)
    M = (0.6 * T + rng.normal(0, 1, n) > 0).astype(int)
    Y = BETA_MY * M + 1.2 * U + rng.normal(0, 0.5, n)
    return pd.DataFrame({"Y": Y, "T": T, "M": M})


def test_frontdoor_alias_recovers_population_ate():
    df = _simulate(0)
    r = sp.frontdoor(df, y="Y", d="T", m="M")
    assert float(r.estimate) == pytest.approx(POP_ATE, abs=0.05)

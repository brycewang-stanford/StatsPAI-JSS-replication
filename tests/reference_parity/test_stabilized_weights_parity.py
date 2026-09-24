"""Analytical parity: sp.stabilized_weights mean-one property.

Stabilized IPT weights sw_i = prod_t P(A_t | past A) / P(A_t | past A, L_t)
satisfy E[sw] = 1 under a correctly specified treatment model (the classic
MSM stabilization property; Robins-style weighting). On a known sequential
DGP the sample mean of the weights is ~1 across seeds and all weights are
positive and finite. Analytical evidence tier.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp


def _weights(seed, n=800, T=3):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        L = rng.normal()
        a_prev = 0
        for t in range(T):
            L = 0.5 * L + 0.3 * a_prev + rng.normal()
            a = int(rng.random() < 1 / (1 + np.exp(-0.5 * L)))
            rows.append({"id": i, "time": t, "A": a, "L": L})
            a_prev = a
    df = pd.DataFrame(rows)
    return np.asarray(
        sp.stabilized_weights(df, treat="A", id="id", time="time", time_varying=["L"]),
        dtype=float,
    )


def test_mean_one_property_across_seeds():
    means = [float(_weights(seed).mean()) for seed in range(3)]
    assert max(abs(m - 1.0) for m in means) < 0.05


def test_weights_positive_and_finite():
    w = _weights(0)
    assert np.all(np.isfinite(w))
    assert np.all(w > 0)
    # stabilization keeps the tails moderate on this well-behaved DGP
    assert float(w.max()) < 25.0

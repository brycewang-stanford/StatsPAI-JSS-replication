"""Analytical parity: sp.cusum_test stability decision + max identity.

CUSUM parameter-stability test: on a stable mean series it does not reject;
with a large planted mean shift it rejects. The reported ``max_cusum`` equals
the maximum absolute value of the returned CUSUM path exactly. Analytical
evidence tier (known-truth behaviour on deterministic DGPs).
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp

N = 300


def _series(broken):
    rng = np.random.default_rng(0)
    if broken:
        y = np.concatenate(
            [1.0 + rng.normal(0, 0.5, N // 2), 3.5 + rng.normal(0, 0.5, N // 2)]
        )
    else:
        y = 1.0 + rng.normal(0, 0.5, N)
    return pd.DataFrame({"y": y})


def test_stable_series_not_rejected():
    r = sp.cusum_test(_series(False), y="y")
    assert bool(r["reject"]) is False


def test_planted_break_rejected():
    r = sp.cusum_test(_series(True), y="y")
    assert bool(r["reject"]) is True
    # the break-induced excursion dwarfs the stable-series one
    stable_max = float(sp.cusum_test(_series(False), y="y")["max_cusum"])
    assert float(r["max_cusum"]) > 5 * stable_max


def test_max_cusum_identity():
    r = sp.cusum_test(_series(True), y="y")
    path = np.asarray(r["cusum"], dtype=float)
    assert float(r["max_cusum"]) == pytest.approx(
        float(np.max(np.abs(path))), abs=1e-12
    )
    assert int(r["n_obs"]) == N

"""Reference parity: sp.kdensity vs the Gaussian KDE closed form.

The kernel density estimator at an evaluation point ``x0`` is the closed-form
average of scaled Gaussian kernels centered at the data points:
``f(x0) = (1/nh) * sum_i phi((x0 - x_i)/h) / sqrt(2*pi)`` for the Gaussian
kernel (Silverman 1986). This is the identical formula that base-R
``stats::density`` and scikit-learn implement; the match is machine-precision.

Closed-form identity (no external fixture needed).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import statspai as sp


def _gaussian_kde(x_data, x_eval, h):
    z = (x_eval - x_data) / h
    return float(np.mean(np.exp(-0.5 * z * z) / np.sqrt(2.0 * np.pi)) / h)


@pytest.fixture(scope="module")
def data():
    rng = np.random.default_rng(3)
    return pd.DataFrame({"v": rng.normal(0, 1, 200)})


def test_kdensity_matches_gaussian_kde(data):
    h = 0.5
    r = sp.kdensity(data, x="v", bandwidth=h)
    grid = np.ravel(r.grid)
    dens = np.ravel(r.density)
    for i in [10, 50, 90, 100, 150]:
        hand = _gaussian_kde(data["v"].values, grid[i], h)
        assert dens[i] == pytest.approx(hand, abs=1e-12)

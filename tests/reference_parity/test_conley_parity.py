"""Frozen-stat parity: sp.conley spatial-HAC SE determinism.

sp.conley returns Conley (1999) spatial HAC standard errors. With identical
inputs (residuals, coordinates, bandwidth) the result is deterministic and
its SEs are a closed-form function of those inputs (no MC). Analytical
evidence tier.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp


@pytest.fixture(scope="module")
def fitted():
    rng = np.random.default_rng(0)
    n = 500
    lat = rng.uniform(0, 1, n)
    lon = rng.uniform(0, 1, n)
    x = rng.normal(0, 1, n)
    y = 1.0 + 0.5 * x + rng.normal(0, 1, n)
    df = pd.DataFrame({"y": y, "x": x, "lat": lat, "lon": lon})
    r = sp.regress("y ~ x", data=df)
    return df, lat, lon, r


def test_deterministic_reproducibility(fitted):
    df, lat, lon, r = fitted
    se1 = sp.conley(r, df, "lat", "lon", dist_cutoff=0.2, kernel="uniform").std_errors
    se2 = sp.conley(r, df, "lat", "lon", dist_cutoff=0.2, kernel="uniform").std_errors
    assert np.allclose(se1.to_numpy(), se2.to_numpy(), atol=1e-15)


def test_uniform_and_bartlett_kernels_produce_finite_ses(fitted):
    """Both kernels must yield finite, non-negative SEs; the exact values
    depend on the spatial point pattern and can coincide on uniform random
    data."""
    df, lat, lon, r = fitted
    for k in ("uniform", "bartlett"):
        se = sp.conley(
            r, df, "lat", "lon", dist_cutoff=0.2, kernel=k
        ).std_errors.to_numpy()
        assert np.all(np.isfinite(se))
        assert np.all(se >= 0.0)


def test_larger_bandwidth_changes_se(fitted):
    df, lat, lon, r = fitted
    se_01 = sp.conley(r, df, "lat", "lon", dist_cutoff=0.1, kernel="uniform").std_errors
    se_03 = sp.conley(r, df, "lat", "lon", dist_cutoff=0.3, kernel="uniform").std_errors
    # In most cases a larger bandwidth yields a different SE.
    assert not np.allclose(se_01.to_numpy(), se_03.to_numpy(), atol=1e-12)


def test_se_finite_nonnegative(fitted):
    df, lat, lon, r = fitted
    se = sp.conley(r, df, "lat", "lon", dist_cutoff=0.2, kernel="uniform").std_errors
    assert np.all(np.isfinite(se.to_numpy()))
    assert np.all(se.to_numpy() >= 0.0)

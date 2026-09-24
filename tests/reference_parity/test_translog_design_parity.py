"""Frozen-formula parity: sp.translog_design exact translog feature matrix.

The standard translog (Christensen-Jorgenson) parameterization for a 2-input
production function uses main effects, an interaction term, and HALF of the
squared terms (so the total is a quadratic form in the logs). sp's
translog_design returns the closed-form features:
    l, k, l*k, 0.5*l^2, 0.5*k^2
i.e. the conventional half-scaled squares. Bit-exact.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp


def test_two_input_translog_features_exact():
    df = pd.DataFrame({"l": [1.0, 2.0, 3.0, 4.0], "k": [4.0, 3.0, 2.0, 1.0]})
    out = sp.translog_design(df, inputs=["l", "k"])
    assert list(out.columns) == ["l", "k", "l_sq", "k_sq", "l_x_k"]
    # Standard translog halves the squared terms.
    assert np.allclose(
        out["l"].to_numpy(),
        df["l"].to_numpy(),
        atol=1e-12,
    )
    assert np.allclose(
        out["k"].to_numpy(),
        df["k"].to_numpy(),
        atol=1e-12,
    )
    assert np.allclose(
        out["l_sq"].to_numpy(),
        0.5 * df["l"].to_numpy() ** 2,
        atol=1e-12,
    )
    assert np.allclose(
        out["k_sq"].to_numpy(),
        0.5 * df["k"].to_numpy() ** 2,
        atol=1e-12,
    )
    assert np.allclose(
        out["l_x_k"].to_numpy(),
        df["l"].to_numpy() * df["k"].to_numpy(),
        atol=1e-12,
    )


def test_no_interactions_no_cross_term():
    df = pd.DataFrame({"l": [1.0, 2.0], "k": [3.0, 4.0]})
    out = sp.translog_design(df, inputs=["l", "k"], include_interactions=False)
    assert "l_x_k" not in out.columns
    assert np.allclose(
        out["l_sq"].to_numpy(),
        0.5 * df["l"].to_numpy() ** 2,
        atol=1e-12,
    )


def test_no_squares_drops_halved_terms():
    df = pd.DataFrame({"l": [1.0, 2.0], "k": [3.0, 4.0]})
    out = sp.translog_design(df, inputs=["l", "k"], include_squares=False)
    assert "l_sq" not in out.columns
    assert "k_sq" not in out.columns
    assert "l_x_k" in out.columns  # interaction still present

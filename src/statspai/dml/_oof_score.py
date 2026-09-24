"""Pure score algebra shared by DML OOF validation and scoring."""

from __future__ import annotations

from typing import Any

import numpy as np


def _real_array(value: Any, name: str) -> np.ndarray:
    raw = np.asarray(value)
    if raw.ndim not in (1, 2):
        raise ValueError(f"{name} must be one- or two-dimensional")
    if np.iscomplexobj(raw):
        raise ValueError(f"{name} must not contain complex values")
    try:
        result = np.array(raw, dtype=float, order="C", copy=True)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be numeric") from exc
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain only finite values")
    return result


def binary_ate_pseudo_outcome(
    y: Any, d: Any, g0: Any, g1: Any, ps_used: Any
) -> np.ndarray:
    """Return the canonical binary-treatment ATE AIPW pseudo-outcome.

    Inputs must be finite, real, equally shaped one- or two-dimensional
    arrays. Treatment is binary and the supplied propensity is strictly
    inside ``(0, 1)``. The returned float array is a fresh, writeable copy.
    """
    values = {
        name: _real_array(value, name)
        for name, value in {
            "y": y,
            "d": d,
            "g0": g0,
            "g1": g1,
            "ps_used": ps_used,
        }.items()
    }
    shape = values["y"].shape
    if any(value.shape != shape for value in values.values()):
        raise ValueError("score inputs must have identical shapes")
    if not np.all((values["d"] == 0) | (values["d"] == 1)):
        raise ValueError("d must be binary")
    if not np.all((values["ps_used"] > 0) & (values["ps_used"] < 1)):
        raise ValueError("ps_used must lie strictly inside (0, 1)")

    y_value = values["y"]
    d_value = values["d"]
    g0_value = values["g0"]
    g1_value = values["g1"]
    propensity = values["ps_used"]
    return np.array(
        g1_value
        - g0_value
        + d_value * (y_value - g1_value) / propensity
        - (1.0 - d_value) * (y_value - g0_value) / (1.0 - propensity),
        dtype=float,
        order="C",
        copy=True,
    )


__all__ = ["binary_ate_pseudo_outcome"]

"""Score-array and aggregation validation for DML OOF bundles."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from . import _oof_serialization as _json
from . import _oof_validation as _arrays
from ._oof_score import binary_ate_pseudo_outcome

AGGREGATION_RULE = "median_theta_median_variance_plus_split_deviation"
# Retain the version-1 near-zero absolute tolerance. Eight ULPs cover the
# rounded AIPW arithmetic and reductions without a magnitude-scaled rtol.
_ABSOLUTE_ROUNDOFF = 1e-12
_MAX_ULPS = 8


def _close(actual: Any, expected: Any) -> bool:
    """Compare arithmetic results with zero relative and bounded ULP slack."""
    actual_array = np.asarray(actual, dtype=float)
    expected_array = np.asarray(expected, dtype=float)
    if actual_array.shape != expected_array.shape:
        return False
    ulp = np.abs(np.spacing(expected_array))
    bound = np.maximum(_ABSOLUTE_ROUNDOFF, _MAX_ULPS * ulp)
    return bool(np.all(np.abs(actual_array - expected_array) <= bound))


def validated_score_arrays(
    values: Mapping[str, Any], predictions: Mapping[str, np.ndarray]
) -> dict[str, np.ndarray]:
    """Validate canonical binary-ATE arrays without fitting any learner."""
    n_rep, n_obs = predictions["g0"].shape
    shape = (n_rep, n_obs)
    scores = {
        name: _arrays.immutable_array(values[name], name, 2)
        for name in ("ps_used", "psi_b", "psi")
    }
    if any(value.shape != shape for value in scores.values()):
        raise ValueError(f"ps_used, psi_b, and psi must have shape {shape}")
    theta = _arrays.immutable_array(values["theta"], "theta", 1)
    se = _arrays.immutable_array(values["se"], "se", 1)
    if theta.shape != (n_rep,) or se.shape != (n_rep,) or np.any(se < 0):
        raise ValueError("theta/se must be one finite value per repeat; se >= 0")

    y = np.broadcast_to(predictions["y"], shape)
    d = np.broadcast_to(predictions["d"], shape)
    canonical = binary_ate_pseudo_outcome(
        y,
        d,
        predictions["g0"],
        predictions["g1"],
        scores["ps_used"],
    )
    if not _close(scores["psi_b"], canonical):
        raise ValueError("psi_b must equal the canonical binary-ATE pseudo-outcome")

    expected_theta = np.mean(scores["psi_b"], axis=1)
    expected_psi = scores["psi_b"] - theta[:, None]
    expected_se = np.std(scores["psi_b"], axis=1, ddof=0) / np.sqrt(n_obs)
    if not _close(theta, expected_theta):
        raise ValueError("theta must equal mean(psi_b) by repeat")
    if not _close(scores["psi"], expected_psi):
        raise ValueError("psi must equal psi_b - theta by repeat")
    if not _close(se, expected_se):
        raise ValueError("se must use std(psi_b, ddof=0) / sqrt(n)")
    return {**scores, "theta": theta, "se": se}


def validated_aggregation(
    value: Any, theta: np.ndarray, se: np.ndarray
) -> dict[str, Any]:
    result = _json.require_keys(
        _json.copy_json(value, "aggregation"),
        {"rule", "theta", "se"},
        "aggregation",
    )
    median = float(np.median(theta))
    combined_se = float(np.sqrt(np.median(se**2 + (theta - median) ** 2)))
    if result["rule"] != AGGREGATION_RULE:
        raise ValueError(f"aggregation.rule must be {AGGREGATION_RULE!r}")
    for name in ("theta", "se"):
        if isinstance(result[name], bool) or not isinstance(result[name], (int, float)):
            raise ValueError(f"aggregation.{name} must be numeric")
    if not _close(result["theta"], median):
        raise ValueError("aggregation.theta disagrees with repeat estimates")
    if not _close(result["se"], combined_se):
        raise ValueError("aggregation.se disagrees with repeat estimates")
    return dict(result)

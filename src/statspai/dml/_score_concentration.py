"""Per-repeat concentration diagnostics for centered DML score arrays."""

from __future__ import annotations

from typing import Any

import numpy as np

SCORE_CONCENTRATION_FIELDS = (
    "rep",
    "status",
    "failure_reason",
    "n_obs",
    "top_fraction",
    "top_count",
    "cmax",
    "z_c",
    "top_share",
    "h",
    "effective_score_count",
)


def _fraction(value: Any) -> float:
    if isinstance(value, (bool, np.bool_, str, bytes)):
        raise ValueError("top_fraction must be a finite scalar in (0, 1]")
    raw = np.asarray(value)
    if raw.ndim != 0 or np.iscomplexobj(raw):
        raise ValueError("top_fraction must be a finite scalar in (0, 1]")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("top_fraction must be a finite scalar in (0, 1]") from exc
    if not np.isfinite(result) or not 0.0 < result <= 1.0:
        raise ValueError("top_fraction must be a finite scalar in (0, 1]")
    return result


def _unavailable(rep: int, n_obs: int, top_fraction: float, reason: str) -> dict:
    return {
        "rep": rep,
        "status": "diagnostic_unavailable",
        "failure_reason": reason,
        "n_obs": n_obs,
        "top_fraction": top_fraction,
        "top_count": max(1, int(np.ceil(top_fraction * n_obs))),
        "cmax": None,
        "z_c": None,
        "top_share": None,
        "h": None,
        "effective_score_count": None,
    }


def score_concentration(psi: Any, *, top_fraction: float = 0.01) -> tuple[dict, ...]:
    """Return JSON-ready squared-share diagnostics for each score repeat.

    ``psi`` contains centered influence scores with shape ``(n_rep, n_obs)``.
    Undefined numerical cases return ``diagnostic_unavailable`` records rather
    than raising or being interpreted as a non-alarm.
    """
    fraction = _fraction(top_fraction)
    raw = np.asarray(psi)
    if raw.ndim != 2:
        raise ValueError("psi must have shape (n_rep, n_obs)")
    if np.iscomplexobj(raw):
        raise ValueError("psi must not contain complex values")
    if raw.dtype.kind not in "biuf":
        raise TypeError("psi must be numeric")
    values = np.array(raw, dtype=float, order="C", copy=True)
    n_rep, n_obs = values.shape
    if n_rep == 0 or n_obs == 0:
        raise ValueError("psi must contain at least one repeat and observation")

    records = []
    for rep, score in enumerate(values):
        if not np.all(np.isfinite(score)):
            records.append(_unavailable(rep, n_obs, fraction, "nonfinite_score"))
            continue
        if n_obs < 2:
            records.append(
                _unavailable(rep, n_obs, fraction, "insufficient_score_count")
            )
            continue
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            squared = np.square(score)
            mass = float(np.sum(squared))
        if not np.isfinite(mass):
            records.append(_unavailable(rep, n_obs, fraction, "nonfinite_score_mass"))
            continue
        if mass <= 0.0:
            records.append(_unavailable(rep, n_obs, fraction, "zero_score_mass"))
            continue

        shares = squared / mass
        cmax = float(np.max(shares))
        top_count = max(1, int(np.ceil(fraction * n_obs)))
        top_share = float(np.sum(np.partition(shares, -top_count)[-top_count:]))
        h = float(np.sum(np.square(shares)))
        effective = float(1.0 / h)
        z_c = float(n_obs * cmax / (2.0 * np.log(n_obs)))
        if not np.all(np.isfinite([cmax, z_c, top_share, h, effective])):
            records.append(_unavailable(rep, n_obs, fraction, "nonfinite_diagnostic"))
            continue
        records.append(
            {
                "rep": rep,
                "status": "ok",
                "failure_reason": None,
                "n_obs": n_obs,
                "top_fraction": fraction,
                "top_count": top_count,
                "cmax": cmax,
                "z_c": z_c,
                "top_share": top_share,
                "h": h,
                "effective_score_count": effective,
            }
        )
    return tuple(records)


__all__ = ["SCORE_CONCENTRATION_FIELDS", "score_concentration"]

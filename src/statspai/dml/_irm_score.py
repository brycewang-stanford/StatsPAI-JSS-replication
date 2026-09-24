"""Pure binary-treatment ATE scoring for internal and external IRM paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import numpy as np

from . import _oof_validation as _v
from ._oof_score import binary_ate_pseudo_outcome


class _ImmutableScoreArray(np.ndarray):
    """Read-only view whose ordinary public header mutators fail closed."""

    def __setattr__(self, name: str, value: Any) -> None:
        if name in {"shape", "dtype", "strides"}:
            raise AttributeError(f"IRMScore array {name} is immutable")
        super().__setattr__(name, value)

    def resize(self, *_args: Any, **_kwargs: Any) -> None:
        raise ValueError("IRMScore array shape is immutable")

    def setflags(self, *_args: Any, **_kwargs: Any) -> None:
        raise ValueError("IRMScore array flags are immutable")


class _ScoreArrayView:
    """Return a fresh guarded header over one Task 3 byte snapshot."""

    __slots__ = ("_storage_name",)
    _storage_name: str

    def __init__(self, storage_name: str) -> None:
        object.__setattr__(self, "_storage_name", storage_name)

    def __setattr__(self, _name: str, _value: Any) -> None:
        raise AttributeError("array view descriptors are immutable")

    def __get__(self, instance: Any, owner: Any = None) -> Any:
        if instance is None:
            return self
        snapshot = getattr(instance, self._storage_name)
        return _v.array_view(snapshot).view(_ImmutableScoreArray)


@dataclass(frozen=True, init=False, eq=False)
class IRMScore:
    """Immutable snapshot of one canonical unweighted IRM ATE score."""

    __slots__ = ("_ps_used", "_psi_b", "_psi", "theta", "se")

    ps_used: np.ndarray
    psi_b: np.ndarray
    psi: np.ndarray
    theta: float
    se: float

    ps_used = cast(np.ndarray, _ScoreArrayView("_ps_used"))
    psi_b = cast(np.ndarray, _ScoreArrayView("_psi_b"))
    psi = cast(np.ndarray, _ScoreArrayView("_psi"))

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise TypeError("IRMScore must be created by score_binary_ate()")


def _threshold(value: Any) -> float:
    if isinstance(value, (bool, np.bool_, str, bytes)):
        raise ValueError(
            "trimming_threshold must be a finite scalar in the open interval (0, 0.5)"
        )
    raw = np.asarray(value)
    if raw.ndim != 0 or np.iscomplexobj(raw):
        raise ValueError(
            "trimming_threshold must be a finite scalar in the open interval (0, 0.5)"
        )
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "trimming_threshold must be a finite scalar in the open interval (0, 0.5)"
        ) from exc
    if not np.isfinite(result) or not 0.0 < result < 0.5:
        raise ValueError(
            "trimming_threshold must be a finite scalar in the open interval (0, 0.5)"
        )
    return result


def _one_dimensional_real_array(value: Any, name: str) -> np.ndarray:
    raw = np.asarray(value)
    if raw.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if np.iscomplexobj(raw):
        raise ValueError(f"{name} must not contain complex values")
    if raw.dtype.kind not in "biuf":
        raise TypeError(f"{name} must be numeric")
    result = np.array(raw, dtype=float, order="C", copy=True)
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain only finite values")
    return result


def _score_result(
    ps_used: np.ndarray,
    psi_b: np.ndarray,
    psi: np.ndarray,
    theta: float,
    se: float,
) -> IRMScore:
    result = object.__new__(IRMScore)
    object.__setattr__(result, "_ps_used", _v.snapshot_array(ps_used))
    object.__setattr__(result, "_psi_b", _v.snapshot_array(psi_b))
    object.__setattr__(result, "_psi", _v.snapshot_array(psi))
    object.__setattr__(result, "theta", theta)
    object.__setattr__(result, "se", se)
    return result


def score_binary_ate(
    y: Any,
    d: Any,
    g0: Any,
    g1: Any,
    ps_raw: Any,
    *,
    trimming_threshold: float,
) -> IRMScore:
    """Score one unweighted binary-treatment ATE from OOF predictions."""
    threshold = _threshold(trimming_threshold)
    values = {
        name: _one_dimensional_real_array(value, name)
        for name, value in (
            ("y", y),
            ("d", d),
            ("g0", g0),
            ("g1", g1),
            ("ps_raw", ps_raw),
        )
    }
    lengths = {len(value) for value in values.values()}
    if lengths == {0}:
        raise ValueError("score inputs must be non-empty")
    if len(lengths) != 1:
        raise ValueError("score inputs must have the same length")
    treatment = values["d"]
    if not np.all((treatment == 0.0) | (treatment == 1.0)):
        raise ValueError("d must be binary")
    if set(treatment.tolist()) != {0.0, 1.0}:
        raise ValueError("d must contain both treatment groups")
    raw_propensity = values["ps_raw"]
    if not np.all((raw_propensity >= 0.0) & (raw_propensity <= 1.0)):
        raise ValueError("ps_raw must lie in the inclusive interval [0, 1]")

    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        ps_used = np.clip(raw_propensity, threshold, 1.0 - threshold)
        psi_b = binary_ate_pseudo_outcome(
            values["y"],
            treatment,
            values["g0"],
            values["g1"],
            ps_used,
        )
        theta = float(np.mean(psi_b))
        psi = psi_b - theta
        se = float(np.std(psi_b, ddof=0) / np.sqrt(len(values["y"])))
    if (
        not np.all(np.isfinite(psi_b))
        or not np.isfinite(theta)
        or not np.all(np.isfinite(psi))
        or not np.isfinite(se)
    ):
        raise ValueError("binary ATE scoring produced non-finite output")
    return _score_result(ps_used, psi_b, psi, theta, se)

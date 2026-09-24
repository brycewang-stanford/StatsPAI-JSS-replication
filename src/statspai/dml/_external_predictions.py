"""Stateless validation for externally supplied DML predictions."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Optional, Tuple

import numpy as np

from ..exceptions import IdentificationFailure
from ._oof_validation import validated_names
from .oof import OOFPredictions, _clone_oof_predictions

_HASH_KEYS = {"data", "predictions_and_folds", "training_source"}
_PAYLOAD_KEYS = {
    "external_predictions_provided",
    "external_predictions_hashes",
    "store_oof",
    "observation_ids_source",
}
_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class ExternalPredictionInput:
    """Detached analysis arrays and validated external identity metadata."""

    predictions: OOFPredictions
    y: np.ndarray
    d: np.ndarray
    x: np.ndarray
    observation_ids_source: str
    hashes: Mapping[str, str]


def _normalise_ids(
    observation_ids: Optional[Sequence[str]], n_obs: int
) -> Tuple[Tuple[str, ...], str]:
    if observation_ids is None:
        return tuple(f"row:{index}" for index in range(n_obs)), "generated_ordinal"
    return (
        validated_names(observation_ids, "observation_ids", n_obs),
        "caller_provided",
    )


def _real_finite_column(values: Any, name: str) -> np.ndarray:
    raw = np.asarray(values)
    if np.iscomplexobj(raw) or raw.dtype.kind not in "biuf":
        raise ValueError(f"external analysis column {name!r} must be real numeric")
    result = np.array(raw, dtype=float, order="C", copy=True)
    if not np.all(np.isfinite(result)):
        raise ValueError(
            f"external analysis column {name!r} must contain only finite values"
        )
    return result


def _copy_hashes(value: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise TypeError("external prediction hashes must be a mapping")
    result = dict(value)
    if set(result) != _HASH_KEYS:
        raise ValueError("external prediction hashes must use the exact hash keys")
    if any(
        not isinstance(item, str) or _SHA256.fullmatch(item) is None
        for item in result.values()
    ):
        raise ValueError("external prediction hashes must be lowercase SHA-256 strings")
    return result


def partitions_equivalent(left: np.ndarray, right: np.ndarray) -> bool:
    """Return whether two label vectors encode the same partition in O(n)."""
    if left.shape != right.shape:
        return False
    forward: dict[Any, Any] = {}
    reverse: dict[Any, Any] = {}
    for left_label, right_label in zip(left.tolist(), right.tolist()):
        if left_label in forward and forward[left_label] != right_label:
            return False
        if right_label in reverse and reverse[right_label] != left_label:
            return False
        forward[left_label] = right_label
        reverse[right_label] = left_label
    return True


def validate_external_partitions(
    predictions: OOFPredictions, fold_indices: np.ndarray
) -> None:
    """Check one explicit partition against every declared repeat."""
    for rep, declared in enumerate(predictions.fold_ids):
        if not partitions_equivalent(fold_indices, declared):
            raise ValueError(
                "explicit fold partition does not match external "
                f"predictions at repeat {rep}"
            )


def validate_external_prediction_input(
    predictions: Any,
    *,
    y_values: Any,
    d_values: Any,
    x_columns: Sequence[Tuple[str, Any]],
    y_name: str,
    d_name: str,
    covariate_names: Sequence[str],
    observation_ids: Optional[Sequence[str]],
    n_obs: int,
    n_rep: int,
    n_folds: int,
    analysis_has_missing: bool,
    fold_has_missing: bool,
) -> ExternalPredictionInput:
    """Validate external predictions through alignment, preserving gate order."""
    if not isinstance(predictions, OOFPredictions):
        raise TypeError(
            "external_predictions must be an in-memory OOFPredictions instance"
        )
    ids, id_source = _normalise_ids(observation_ids, n_obs)
    if analysis_has_missing:
        raise ValueError(
            "external predictions require complete Y, D, and X rows; "
            "implicit row deletion is disabled"
        )
    if fold_has_missing:
        raise ValueError("external predictions require complete explicit fold labels")

    y = _real_finite_column(y_values, y_name)
    d = _real_finite_column(d_values, d_name)
    x = np.column_stack(
        [_real_finite_column(values, name) for name, values in x_columns]
    )
    if not np.all((d == 0.0) | (d == 1.0)):
        raise NotImplementedError(
            "external predictions currently require binary treatment (0/1)"
        )
    if set(d.tolist()) != {0.0, 1.0}:
        raise IdentificationFailure(
            "model='irm' requires variation in D (both 0 and 1); "
            "ATE is not identified with a constant treatment."
        )
    predictions = _clone_oof_predictions(predictions)
    if predictions.n_rep != n_rep:
        raise ValueError(
            "external prediction repeats do not match n_rep: "
            f"{predictions.n_rep} != {n_rep}"
        )
    if predictions.n_folds != n_folds:
        raise ValueError(
            "external prediction folds do not match n_folds: "
            f"{predictions.n_folds} != {n_folds}"
        )
    if {record["origin"] for record in predictions.training_records} != {
        "caller_declared"
    }:
        raise ValueError(
            "external predictions require training-record origin='caller_declared'"
        )
    predictions.validate_alignment(
        ids=ids,
        y=y,
        d=d,
        x=x,
        covariate_names=covariate_names,
    )
    hashes = MappingProxyType(_copy_hashes(predictions.hashes))
    return ExternalPredictionInput(predictions, y, d, x, id_source, hashes)


def _raw_oof_provenance_payload(
    *,
    external_predictions: Optional[OOFPredictions],
    store_oof: bool,
    observation_ids: Optional[Sequence[str]],
) -> dict[str, Any]:
    requested = (
        external_predictions is not None or store_oof or observation_ids is not None
    )
    if not requested:
        return {}
    hashes = (
        _copy_hashes(external_predictions.hashes)
        if external_predictions is not None
        else None
    )
    return {
        "external_predictions_provided": external_predictions is not None,
        "external_predictions_hashes": hashes,
        "store_oof": store_oof,
        "observation_ids_source": (
            "caller_provided" if observation_ids is not None else "generated_ordinal"
        ),
    }


def _validate_oof_provenance_payload(
    payload: Any, *, requested: bool
) -> dict[str, Any]:
    if type(payload) is not dict:
        raise TypeError("OOF provenance payload must be a plain dict")
    if not requested:
        if payload:
            raise ValueError("legacy DML calls must not add OOF provenance fields")
        return {}
    if set(payload) != _PAYLOAD_KEYS:
        raise ValueError("OOF provenance payload must use the exact keys")
    if type(payload["external_predictions_provided"]) is not bool:
        raise TypeError("external_predictions_provided must be a bool")
    if type(payload["store_oof"]) is not bool:
        raise TypeError("store_oof must be a bool")
    hashes = payload["external_predictions_hashes"]
    if payload["external_predictions_provided"]:
        if type(hashes) is not dict:
            raise TypeError("external_predictions_hashes must be a plain dict")
        _copy_hashes(hashes)
    elif hashes is not None:
        raise ValueError("external_predictions_hashes must be None without predictions")
    if payload["observation_ids_source"] not in {
        "generated_ordinal",
        "caller_provided",
    }:
        raise ValueError("observation_ids_source is invalid")
    json.dumps(payload, allow_nan=False)
    return payload


def build_oof_provenance_payload(
    *,
    external_predictions: Optional[OOFPredictions],
    store_oof: bool,
    observation_ids: Optional[Sequence[str]],
) -> dict[str, Any]:
    """Build and validate the tiny functional-dispatcher OOF payload."""
    if external_predictions is not None and not isinstance(
        external_predictions, OOFPredictions
    ):
        raise TypeError(
            "external_predictions must be an in-memory OOFPredictions instance"
        )
    requested = (
        external_predictions is not None or store_oof or observation_ids is not None
    )
    payload = _raw_oof_provenance_payload(
        external_predictions=external_predictions,
        store_oof=store_oof,
        observation_ids=observation_ids,
    )
    return _validate_oof_provenance_payload(payload, requested=requested)

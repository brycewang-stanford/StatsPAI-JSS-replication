"""Canonical JSON and integrity helpers for DML OOF artifacts."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np

PREDICTION_SCHEMA = "statspai.dml.predictions/1"
BUNDLE_SCHEMA = "statspai.dml.oof/1"

PREDICTION_KEYS = set(
    "schema_version ids covariate_names arrays training_records source hashes".split()
)
PREDICTION_ARRAY_KEYS = {"y", "d", "x", "g0", "g1", "ps_raw", "fold_ids"}
BUNDLE_KEYS = set(
    "schema_version predictions arrays input_mapping aggregation metadata hash".split()
)
BUNDLE_ARRAY_KEYS = {"ps_used", "psi_b", "psi", "theta", "se"}
INPUT_MAPPING_KEYS = {"input_positions", "dropped_positions"}
_HASH_KEYS = {"data", "predictions_and_folds", "training_source"}
_LOWER_HEX = frozenset("0123456789abcdef")


def plain(value: Any) -> Any:
    """Convert frozen views and NumPy values to ordinary JSON values."""
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("JSON object keys must be strings")
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [plain(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def canonical_bytes(value: Any) -> bytes:
    """Encode canonical JSON using the schema's frozen stdlib options."""
    try:
        return json.dumps(
            plain(value),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
            ensure_ascii=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"value is not finite canonical JSON: {exc}") from exc


def copy_json(value: Any, name: str) -> Any:
    try:
        return json.loads(canonical_bytes(value).decode("utf-8"))
    except ValueError as exc:
        raise ValueError(f"{name} must be finite JSON data: {exc}") from exc


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def read_json(path: Any, label: str) -> Any:
    try:
        return json.loads(
            Path(path).read_text(encoding="utf-8"), object_pairs_hook=_unique_object
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"could not read {label} JSON: {exc}") from exc


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def require_keys(value: Any, expected: set[str], name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    actual = set(value)
    if actual != expected:
        missing = sorted(expected.difference(actual))
        extra = sorted(actual.difference(expected))
        raise ValueError(f"{name} keys invalid; missing={missing}, extra={extra}")
    return value


def freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(freeze_json(item) for item in value)
    return value


def require_matching_digest(stored: Any, expected: str, message: str) -> None:
    """Reject malformed digests before invoking constant-time comparison."""
    valid = (
        isinstance(stored, str)
        and len(stored) == 64
        and all(character in _LOWER_HEX for character in stored)
    )
    if not valid or not hmac.compare_digest(stored, expected):
        raise ValueError(message)


def prediction_hashes(payload: Mapping[str, Any]) -> dict[str, str]:
    arrays = payload["arrays"]
    return {
        "data": digest(
            {
                "ids": payload["ids"],
                "covariate_names": payload["covariate_names"],
                "arrays": {key: arrays[key] for key in ("y", "d", "x")},
            }
        ),
        "predictions_and_folds": digest(
            {"arrays": {key: arrays[key] for key in ("g0", "g1", "ps_raw", "fold_ids")}}
        ),
        "training_source": digest(
            {
                "training_records": payload["training_records"],
                "source": payload["source"],
            }
        ),
    }


def verify_prediction_hashes(
    stored: Any, expected: Mapping[str, str], label: str
) -> None:
    stored = require_keys(stored, _HASH_KEYS, f"{label} hashes")
    for name, value in expected.items():
        require_matching_digest(
            stored[name], value, f"{label} hash mismatch for {name}"
        )

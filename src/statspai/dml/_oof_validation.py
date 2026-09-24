"""Stateless array, fold, mapping, and metadata validation for OOF records."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, NamedTuple, Optional, Sequence, Tuple, Type, overload

import numpy as np

from ..exceptions import MethodIncompatibility
from . import _oof_serialization as _json

_RECORD_KEYS = set(
    "rep fold_id train_ids test_ids nuisance_train_ids "
    "preprocessing_train_ids origin".split()
)
_LEARNERS = {"g0", "g1", "ps"}
_SOURCE_KEYS = {"engine", "recipe", "seed", "software_versions"}
_META_REQUIRED = set(
    "scoring_engine score psi_a variance_policy trimming_threshold normalize_ipw "
    "clipping_counts".split()
)
_META_OPTIONAL = {"fit_records"}
_FIT_KEYS = {"rep", "fold_id", "fit_seed", "subgroup_fallback_counts"}


class ArraySnapshot(NamedTuple):
    """Immutable byte, dtype, and shape state for one public array."""

    data: bytes
    dtype: str
    shape: Tuple[int, ...]


class ArrayView:
    """Descriptor returning a fresh read-only NumPy header for a snapshot."""

    __slots__ = ("_storage_name",)
    _storage_name: str

    def __init__(self, storage_name: str) -> None:
        object.__setattr__(self, "_storage_name", storage_name)

    def __setattr__(self, _name: str, _value: Any) -> None:
        raise AttributeError("array view descriptors are immutable")

    @overload
    def __get__(  # noqa: E704
        self, instance: None, owner: Optional[Type[Any]] = ...
    ) -> "ArrayView": ...

    @overload
    def __get__(  # noqa: E704
        self, instance: object, owner: Optional[Type[Any]] = ...
    ) -> np.ndarray: ...

    def __get__(self, instance: Any, owner: Optional[Type[Any]] = None) -> Any:
        if instance is None:
            return self
        return array_view(getattr(instance, self._storage_name))


def immutable_array(
    value: Any, name: str, ndim: int, *, integer: bool = False
) -> np.ndarray:
    """Validate numeric input and return a detached read-only working array."""
    raw = np.asarray(value)
    if raw.ndim != ndim:
        raise ValueError(f"{name} must be {ndim}-dimensional")
    if np.iscomplexobj(raw):
        raise ValueError(f"{name} must not contain complex values")
    if integer and raw.size and raw.dtype.kind not in "iu":
        raise ValueError(f"{name} must contain integer values")
    try:
        result = np.asarray(raw, dtype=np.int64 if integer else float)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be numeric") from exc
    if not integer and not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain only finite values")
    result = np.ascontiguousarray(result)
    return np.frombuffer(result.tobytes(), dtype=result.dtype).reshape(result.shape)


def snapshot_array(value: np.ndarray) -> ArraySnapshot:
    """Capture immutable storage independently of a caller-controlled header."""
    array = np.ascontiguousarray(value)
    return ArraySnapshot(array.tobytes(), array.dtype.str, tuple(array.shape))


def array_view(snapshot: ArraySnapshot) -> np.ndarray:
    """Build a fresh read-only ndarray header backed by immutable bytes."""
    return np.frombuffer(snapshot.data, dtype=np.dtype(snapshot.dtype)).reshape(
        snapshot.shape
    )


def _integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def validated_names(value: Any, name: str, length: int) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)):
        raise TypeError(f"{name} must be a sequence")
    try:
        result = tuple(value)
    except TypeError as exc:
        raise TypeError(f"{name} must be a sequence") from exc
    if len(result) != length:
        raise ValueError(f"{name} must have length {length}")
    if any(not isinstance(item, str) or not item for item in result):
        raise ValueError(f"{name} must contain non-empty strings")
    if len(set(result)) != len(result):
        raise ValueError(f"{name} must be unique")
    return result


def _id_list(value: Any, known: set[str], name: str) -> list[str]:
    if not isinstance(value, list):
        raise TypeError(f"{name} must be a list")
    if any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{name} must contain non-empty string IDs")
    values = set(value)
    if len(value) != len(values):
        raise ValueError(f"{name} must contain unique IDs")
    if values - known:
        raise ValueError(f"{name} contains unknown IDs")
    return value


def validated_source(value: Any) -> dict[str, Any]:
    result = _json.require_keys(
        _json.copy_json(value, "source"), _SOURCE_KEYS, "source"
    )
    for name in ("engine", "recipe"):
        if not isinstance(result[name], str) or not result[name].strip():
            raise ValueError(f"source.{name} must be a non-empty string")
    seed = result["seed"]
    if seed is not None and not _integer(seed):
        raise ValueError("source.seed must be an integer or None")
    versions = result["software_versions"]
    if not isinstance(versions, Mapping) or any(
        not isinstance(key, str) or not key or not isinstance(item, str) or not item
        for key, item in versions.items()
    ):
        raise ValueError("source.software_versions must map non-empty strings")
    return dict(result)


def validated_training_records(
    value: Any, ids: Sequence[str], d: np.ndarray, folds: np.ndarray
) -> list[dict[str, Any]]:
    records = _json.copy_json(value, "training_records")
    if not isinstance(records, list):
        raise TypeError("training_records must be a list")
    known, treatment = set(ids), dict(zip(ids, d.tolist()))
    labels_by_rep = []
    for rep, labels in enumerate(folds):
        unique = np.unique(labels)
        if len(unique) < 2 or not np.array_equal(unique, np.arange(len(unique))):
            raise MethodIncompatibility(
                f"fold_ids repeat {rep} must be contiguous 0..K-1"
            )
        labels_by_rep.append(unique)
    if len({len(labels) for labels in labels_by_rep}) != 1:
        raise MethodIncompatibility("all repeats must use the same number of folds")
    expected_pairs = [
        (rep, int(fold)) for rep, labels in enumerate(labels_by_rep) for fold in labels
    ]
    expected_pair_set = set(expected_pairs)
    if len(records) != len(expected_pairs):
        raise MethodIncompatibility(
            "training_records must cover every repeat/fold once"
        )

    actual_pairs = []
    for index, record in enumerate(records):
        record = _json.require_keys(record, _RECORD_KEYS, f"training_records[{index}]")
        rep, fold = record["rep"], record["fold_id"]
        if not all(_integer(item) for item in (rep, fold)):
            raise ValueError("record rep and fold_id must be integers")
        actual_pairs.append((rep, fold))
        if (rep, fold) not in expected_pair_set:
            raise MethodIncompatibility("record repeat/fold is outside fold_ids")
        if record["origin"] not in {"statspai_internal", "caller_declared"}:
            raise MethodIncompatibility("training record origin is invalid")

        train = _id_list(record["train_ids"], known, "train_ids")
        test = _id_list(record["test_ids"], known, "test_ids")
        expected_test = [row for row, label in zip(ids, folds[rep]) if label == fold]
        held_out = set(expected_test)
        expected_train = [row for row in ids if row not in held_out]
        if test != expected_test or train != expected_train:
            raise MethodIncompatibility(
                "train/test IDs must be ordered strict fold complements"
            )
        if {treatment[row] for row in train} != {0, 1}:
            raise MethodIncompatibility(
                "each training fold must contain both treatment arms"
            )

        nuisance = _json.require_keys(
            record["nuisance_train_ids"], _LEARNERS, "nuisance IDs"
        )
        expected_nuisance = {
            "g0": [row for row in train if treatment[row] == 0],
            "g1": [row for row in train if treatment[row] == 1],
            "ps": train,
        }
        for learner, expected in expected_nuisance.items():
            if _id_list(nuisance[learner], known, f"nuisance.{learner}") != expected:
                raise MethodIncompatibility(
                    f"nuisance.{learner} has wrong arm/training scope"
                )

        preprocessing = _json.require_keys(
            record["preprocessing_train_ids"], _LEARNERS, "preprocessing IDs"
        )
        for learner in _LEARNERS:
            declared = _id_list(
                preprocessing[learner], known, f"preprocessing.{learner}"
            )
            declared_ids = set(declared)
            canonical = [row for row in train if row in declared_ids]
            if declared != canonical:
                raise MethodIncompatibility(
                    f"preprocessing.{learner} must be an ordered training subset"
                )
    if actual_pairs != expected_pairs:
        raise MethodIncompatibility(
            "training_records must be sorted by repeat and fold"
        )
    return records


def validated_input_mapping(
    kept: Any, dropped: Any, n_obs: int
) -> Tuple[np.ndarray, np.ndarray]:
    kept = immutable_array(kept, "input_positions", 1, integer=True)
    dropped = immutable_array(dropped, "dropped_positions", 1, integer=True)
    if len(kept) != n_obs or np.any(kept < 0) or np.any(dropped < 0):
        raise ValueError("input mapping has invalid length or negative ordinals")
    if len(set(kept)) != len(kept) or len(set(dropped)) != len(dropped):
        raise ValueError("input mapping ordinals must be unique")
    if set(kept) & set(dropped):
        raise ValueError("kept and dropped input positions must be disjoint")
    combined = sorted(kept.tolist() + dropped.tolist())
    if combined != list(range(len(combined))):
        raise ValueError("input mapping must cover contiguous original ordinals")
    if np.any(np.diff(kept) <= 0) or np.any(np.diff(dropped) <= 0):
        raise ValueError("input positions must be strictly increasing")
    return kept, dropped


def validated_metadata(
    value: Any, info: Mapping[str, Any], ps_used: np.ndarray
) -> dict:
    result = _json.copy_json(value, "metadata")
    if not isinstance(result, Mapping):
        raise TypeError("metadata must be a mapping")
    actual, allowed = set(result), _META_REQUIRED | _META_OPTIONAL
    if not _META_REQUIRED <= actual or not actual <= allowed:
        missing = sorted(_META_REQUIRED.difference(actual))
        extra = sorted(actual.difference(allowed))
        raise ValueError(f"metadata keys invalid; missing={missing}, extra={extra}")
    engine = result["scoring_engine"]
    engines = {
        "statspai_irm_internal": "statspai_internal",
        "statspai_irm_external_predictions": "caller_declared",
    }
    if engine not in engines:
        raise ValueError("metadata.scoring_engine is invalid")
    if {row["origin"] for row in info["training_records"]} != {engines[engine]}:
        raise MethodIncompatibility(
            "metadata scoring engine disagrees with training origin"
        )
    if result["score"] != "ATE" or result["psi_a"] != -1:
        raise MethodIncompatibility("metadata must declare score='ATE' and psi_a=-1")
    if result["variance_policy"] != "ddof0":
        raise MethodIncompatibility("metadata.variance_policy must be 'ddof0'")
    if result["normalize_ipw"] is not False:
        raise MethodIncompatibility(
            "metadata.normalize_ipw must be false in schema version 1"
        )
    threshold = result["trimming_threshold"]
    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not 0 < threshold < 0.5
    ):
        raise ValueError("metadata.trimming_threshold must be between 0 and 0.5")
    ps_raw = info["ps_raw"]
    if not np.array_equal(ps_used, np.clip(ps_raw, threshold, 1 - threshold)):
        raise ValueError("ps_used does not match raw propensity clipping")

    counts = result["clipping_counts"]
    if not isinstance(counts, list) or len(counts) != info["n_rep"]:
        raise ValueError("metadata.clipping_counts must have one row per repeat")
    for rep, record in enumerate(counts):
        record = _json.require_keys(
            record, {"rep", "n_clipped_low", "n_clipped_high"}, "clipping count"
        )
        if not all(_integer(record[name]) for name in record):
            raise ValueError("metadata clipping counts must be integers")
        expected = {
            "rep": rep,
            "n_clipped_low": int(np.sum(ps_raw[rep] < threshold)),
            "n_clipped_high": int(np.sum(ps_raw[rep] > 1 - threshold)),
        }
        if dict(record) != expected:
            raise ValueError("metadata clipping count disagrees with ps_raw")

    if engine == "statspai_irm_internal" and "fit_records" not in result:
        raise ValueError("internal metadata requires concrete fit_records")
    if "fit_records" in result:
        _validate_fit_records(result["fit_records"], info, engine)
    return dict(result)


def _validate_fit_records(fits: Any, info: Mapping[str, Any], engine: str) -> None:
    pairs = [(row["rep"], row["fold_id"]) for row in info["training_records"]]
    if not isinstance(fits, list) or len(fits) != len(pairs):
        raise ValueError("metadata.fit_records must cover every repeat/fold")
    for fit, pair in zip(fits, pairs):
        fit = _json.require_keys(fit, _FIT_KEYS, "fit record")
        if not all(_integer(fit[name]) for name in ("rep", "fold_id")):
            raise ValueError("metadata.fit_records repeat/fold must be integers")
        if (fit["rep"], fit["fold_id"]) != pair:
            raise ValueError("metadata.fit_records must be sorted by repeat/fold")
        seed, fallback = fit["fit_seed"], fit["subgroup_fallback_counts"]
        if engine.endswith("external_predictions"):
            if seed is not None or fallback is not None:
                raise ValueError(
                    "external fit_seed and subgroup_fallback_counts must be None"
                )
            continue
        if not _integer(seed):
            raise ValueError("internal fit_seed must be an integer")
        fallback = _json.require_keys(fallback, {"g0", "g1"}, "fallback counts")
        if any(not _integer(item) or item < 0 for item in fallback.values()):
            raise ValueError("subgroup fallback counts must be non-negative")

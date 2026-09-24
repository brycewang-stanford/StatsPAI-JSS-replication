"""Immutable, versioned DML out-of-fold records with corruption hashes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence, Tuple, Type, TypeVar, Union

import numpy as np
import pandas as pd

from . import _oof_bundle_validation as _bundle
from . import _oof_serialization as _json
from . import _oof_validation as _v

_PREDICTION_ARRAYS = ("y", "d", "x", "g0", "g1", "ps_raw", "fold_ids")
_BUNDLE_ARRAYS = "ps_used psi_b psi theta se input_positions dropped_positions".split()
_T = TypeVar("_T")


def _make(cls: Type[_T], values: Mapping[str, Any]) -> _T:
    instance = object.__new__(cls)
    for name, value in values.items():
        object.__setattr__(instance, name, value)
    return instance


def _snapshots(values: Mapping[str, Any], names: Sequence[str]) -> dict[str, Any]:
    return {f"_{name}": _v.snapshot_array(values[name]) for name in names}


@dataclass(frozen=True, init=False, eq=False, repr=False)
class OOFPredictions:
    """Validated predictions and declared cross-fitting provenance.

    Records marked ``caller_declared`` describe claims StatsPAI can check for
    structural consistency, not training behavior StatsPAI observed. Public
    array access returns a fresh read-only NumPy header over immutable bytes.

    Returns
    -------
    OOFPredictions
        Immutable schema-v1 data, predictions, folds, and declared scopes.

    Examples
    --------
    >>> import statspai as sp
    >>> sp.OOFPredictions.__name__
    'OOFPredictions'

    Notes
    -----
    Construct with :meth:`from_arrays`, not the class constructor.

    References
    ----------
    See ``docs/dml_oof_audit.md`` for the data contract.
    """

    __slots__ = (
        "schema_version ids covariate_names _y _d _x _g0 _g1 _ps_raw "
        "_fold_ids training_records source hashes"
    ).split()

    schema_version: str
    ids: Tuple[str, ...]
    covariate_names: Tuple[str, ...]
    training_records: Tuple[Mapping[str, Any], ...]
    source: Mapping[str, Any]
    hashes: Mapping[str, str]

    y = _v.ArrayView("_y")
    d = _v.ArrayView("_d")
    x = _v.ArrayView("_x")
    g0 = _v.ArrayView("_g0")
    g1 = _v.ArrayView("_g1")
    ps_raw = _v.ArrayView("_ps_raw")
    fold_ids = _v.ArrayView("_fold_ids")

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise TypeError("OOFPredictions must be created with from_arrays()")

    @classmethod
    def from_arrays(
        cls,
        *,
        ids: Sequence[str],
        y: Any,
        d: Any,
        x: Any,
        covariate_names: Sequence[str],
        g0: Any,
        g1: Any,
        ps_raw: Any,
        fold_ids: Any,
        training_records: Sequence[Mapping[str, Any]],
        source: Mapping[str, Any],
    ) -> "OOFPredictions":
        """Validate and defensively copy a complete analysis-sample snapshot.

        Parameters
        ----------
        ids : sequence of str
            Unique row identifiers in analysis order.
        y, d : array-like of shape (n_obs,)
            Finite outcomes and binary treatment containing both arms.
        x : array-like of shape (n_obs, n_covariates)
            Finite covariate matrix in the declared column order.
        covariate_names : sequence of str
            Unique covariate names.
        g0, g1, ps_raw : array-like of shape (n_rep, n_obs)
            Outcome predictions by arm and raw propensities in [0, 1].
        fold_ids : array-like of int of shape (n_rep, n_obs)
            Complete held-out fold assignments for each repeat.
        training_records : sequence of mapping
            One record per repeat/fold declaring disjoint train/test IDs and
            nuisance and preprocessing training scopes. See the audit guide.
        source : mapping
            Engine, recipe, seed, and software version provenance.

        Returns
        -------
        OOFPredictions
            Validated independent snapshot with corruption hashes.

        Examples
        --------
        >>> import statspai as sp
        >>> callable(sp.OOFPredictions.from_arrays)
        True

        References
        ----------
        See ``docs/dml_oof_audit.md`` for training-record fields.
        """
        y = _v.immutable_array(y, "y", 1)
        d = _v.immutable_array(d, "d", 1)
        x = _v.immutable_array(x, "x", 2)
        if not len(y):
            raise ValueError("OOFPredictions requires at least one observation")
        ids = _v.validated_names(ids, "ids", len(y))
        covariates = _v.validated_names(covariate_names, "covariate_names", x.shape[1])
        if d.shape != y.shape or x.shape[0] != len(y):
            raise ValueError("d and x observation counts must match y")
        if not np.all((d == 0) | (d == 1)) or set(d.tolist()) != {0.0, 1.0}:
            raise ValueError("d must contain both binary treatment groups")
        d = _v.immutable_array(d.astype(np.int64), "d", 1, integer=True)

        predictions = {
            name: _v.immutable_array(value, name, 2, integer=name == "fold_ids")
            for name, value in {
                "g0": g0,
                "g1": g1,
                "ps_raw": ps_raw,
                "fold_ids": fold_ids,
            }.items()
        }
        shape = predictions["g0"].shape
        if shape[0] < 1 or shape[1] != len(y):
            raise ValueError("prediction shape must be (at least one repeat, n_obs)")
        if any(value.shape != shape for value in predictions.values()):
            raise ValueError("g0, g1, ps_raw, and fold_ids must share shape (R, n)")
        if not np.all((predictions["ps_raw"] >= 0) & (predictions["ps_raw"] <= 1)):
            raise ValueError("ps_raw must lie in inclusive [0, 1]")

        records = _v.validated_training_records(
            training_records, ids, d, predictions["fold_ids"]
        )
        source = _v.validated_source(source)
        arrays = {"y": y, "d": d, "x": x, **predictions}
        payload = {
            "schema_version": _json.PREDICTION_SCHEMA,
            "ids": list(ids),
            "covariate_names": list(covariates),
            "arrays": {name: value.tolist() for name, value in arrays.items()},
            "training_records": records,
            "source": source,
        }
        return _make(
            cls,
            {
                "schema_version": _json.PREDICTION_SCHEMA,
                "ids": ids,
                "covariate_names": covariates,
                **_snapshots(arrays, _PREDICTION_ARRAYS),
                "training_records": _json.freeze_json(records),
                "source": _json.freeze_json(source),
                "hashes": MappingProxyType(_json.prediction_hashes(payload)),
            },
        )

    @property
    def n_obs(self) -> int:
        return len(self.ids)

    @property
    def n_rep(self) -> int:
        return int(self.g0.shape[0])

    @property
    def n_folds(self) -> int:
        return len(np.unique(self.fold_ids[0]))

    def validate_alignment(
        self,
        *,
        ids: Sequence[str],
        y: Any,
        d: Any,
        x: Any,
        covariate_names: Sequence[str],
    ) -> None:
        """Raise unless current analysis inputs exactly match this row order.

        Parameters
        ----------
        ids, covariate_names : sequence of str
            Ordered identifiers to compare with the snapshot.
        y, d, x : array-like
            Observed arrays to compare exactly, including shape.

        Returns
        -------
        None
            Raises ValueError on any mismatch.
        """
        try:
            checks = {
                "ids": tuple(ids) == self.ids,
                "covariate_names": tuple(covariate_names) == self.covariate_names,
                "y": np.array_equal(_v.immutable_array(y, "y", 1), self.y),
                "d": np.array_equal(_v.immutable_array(d, "d", 1), self.d),
                "x": np.array_equal(_v.immutable_array(x, "x", 2), self.x),
            }
        except (TypeError, ValueError):
            checks = {"input": False}
        failed = [name for name, matches in checks.items() if not matches]
        if failed:
            raise ValueError(
                "OOFPredictions alignment failed for: " + ", ".join(failed)
            )

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "ids": list(self.ids),
            "covariate_names": list(self.covariate_names),
            "arrays": {
                name: getattr(self, name).tolist() for name in _PREDICTION_ARRAYS
            },
            "training_records": _json.plain(self.training_records),
            "source": _json.plain(self.source),
            "hashes": dict(self.hashes),
        }

    def to_json(self, path: Union[str, Path]) -> None:
        """Write deterministic UTF-8 JSON with three partition hashes.

        Parameters
        ----------
        path : str or pathlib.Path
            Destination for individual-level data, predictions, and scopes.

        Returns
        -------
        None
            Writes schema-v1 JSON to the requested path.
        """
        Path(path).write_bytes(_json.canonical_bytes(self._payload()))

    @classmethod
    def _from_payload(cls, payload: Any) -> "OOFPredictions":
        payload = _json.require_keys(payload, _json.PREDICTION_KEYS, "prediction")
        if payload["schema_version"] != _json.PREDICTION_SCHEMA:
            raise ValueError(
                f"unknown OOFPredictions schema: {payload['schema_version']!r}"
            )
        arrays = _json.require_keys(
            payload["arrays"], _json.PREDICTION_ARRAY_KEYS, "prediction arrays"
        )
        _json.verify_prediction_hashes(
            payload["hashes"], _json.prediction_hashes(payload), "prediction"
        )
        result = cls.from_arrays(
            ids=payload["ids"],
            covariate_names=payload["covariate_names"],
            training_records=payload["training_records"],
            source=payload["source"],
            **arrays,
        )
        _json.verify_prediction_hashes(payload["hashes"], result.hashes, "prediction")
        return result

    @classmethod
    def from_json(cls, path: Union[str, Path]) -> "OOFPredictions":
        """Read only after checking schema, duplicate keys, and stored hashes.

        Parameters
        ----------
        path : str or pathlib.Path
            Schema-v1 prediction JSON file.

        Returns
        -------
        OOFPredictions
            Validated independent snapshot.
        """
        return cls._from_payload(_json.read_json(path, "OOFPredictions"))

    def _clone(self) -> "OOFPredictions":
        return type(self).from_arrays(
            ids=self.ids,
            covariate_names=self.covariate_names,
            training_records=self.training_records,
            source=self.source,
            **{name: getattr(self, name) for name in _PREDICTION_ARRAYS},
        )


@dataclass(frozen=True, init=False, eq=False, repr=False)
class OOFBundle:
    """Validated StatsPAI binary-ATE score output with bounded ULP slack.

    Returns
    -------
    OOFBundle
        Immutable schema-v1 predictions, scores, and repeat aggregation.

    Examples
    --------
    >>> import statspai as sp
    >>> sp.OOFBundle.__name__
    'OOFBundle'

    Notes
    -----
    Obtain from a retained result or construct with :meth:`from_arrays`.

    References
    ----------
    See ``docs/dml_oof_audit.md`` for score and variance conventions.
    """

    __slots__ = (
        "schema_version predictions _ps_used _psi_b _psi _theta _se "
        "_input_positions _dropped_positions aggregation metadata hash"
    ).split()

    schema_version: str
    predictions: OOFPredictions
    aggregation: Mapping[str, Any]
    metadata: Mapping[str, Any]
    hash: str

    ps_used = _v.ArrayView("_ps_used")
    psi_b = _v.ArrayView("_psi_b")
    psi = _v.ArrayView("_psi")
    theta = _v.ArrayView("_theta")
    se = _v.ArrayView("_se")
    input_positions = _v.ArrayView("_input_positions")
    dropped_positions = _v.ArrayView("_dropped_positions")

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise TypeError("OOFBundle must be created with from_arrays()")

    @classmethod
    def from_arrays(
        cls,
        *,
        predictions: OOFPredictions,
        ps_used: Any,
        psi_b: Any,
        psi: Any,
        theta: Any,
        se: Any,
        input_positions: Any,
        dropped_positions: Any,
        aggregation: Mapping[str, Any],
        metadata: Mapping[str, Any],
    ) -> "OOFBundle":
        """Validate and copy canonical binary-ATE scoring output.

        Parameters
        ----------
        predictions : OOFPredictions
            Complete validated analysis snapshot.
        ps_used, psi_b, psi : array-like of shape (n_rep, n_obs)
            Clipped propensities, AIPW pseudo-outcomes, and centered scores.
        theta, se : array-like of shape (n_rep,)
            Per-repeat effects and standard errors.
        input_positions, dropped_positions : array-like of int
            Disjoint mappings covering the original input row positions.
        aggregation : mapping
            Validated median-effect and median-variance aggregation record.
        metadata : mapping
            Trimming, fit, and provenance metadata required by schema v1.

        Returns
        -------
        OOFBundle
            Independent snapshot; inconsistent scores or mappings raise.
        """
        if not isinstance(predictions, OOFPredictions):
            raise TypeError("predictions must be OOFPredictions")
        prediction_arrays = {
            name: getattr(predictions, name)
            for name in ("y", "d", "g0", "g1", "ps_raw")
        }
        scores = _bundle.validated_score_arrays(
            {
                "ps_used": ps_used,
                "psi_b": psi_b,
                "psi": psi,
                "theta": theta,
                "se": se,
            },
            prediction_arrays,
        )
        kept, dropped = _v.validated_input_mapping(
            input_positions, dropped_positions, predictions.n_obs
        )
        metadata = _v.validated_metadata(
            metadata,
            {
                "n_rep": predictions.n_rep,
                "ps_raw": prediction_arrays["ps_raw"],
                "training_records": predictions.training_records,
            },
            scores["ps_used"],
        )
        aggregation = _bundle.validated_aggregation(
            aggregation, scores["theta"], scores["se"]
        )
        arrays = {**scores, "input_positions": kept, "dropped_positions": dropped}
        instance = _make(
            cls,
            {
                "schema_version": _json.BUNDLE_SCHEMA,
                "predictions": predictions._clone(),
                **_snapshots(arrays, _BUNDLE_ARRAYS),
                "aggregation": _json.freeze_json(aggregation),
                "metadata": _json.freeze_json(metadata),
            },
        )
        object.__setattr__(instance, "hash", _json.digest(instance._unsigned_payload()))
        return instance

    def _unsigned_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "predictions": self.predictions._payload(),
            "arrays": {
                name: getattr(self, name).tolist()
                for name in ("ps_used", "psi_b", "psi", "theta", "se")
            },
            "input_mapping": {
                "input_positions": self.input_positions.tolist(),
                "dropped_positions": self.dropped_positions.tolist(),
            },
            "aggregation": _json.plain(self.aggregation),
            "metadata": _json.plain(self.metadata),
        }

    def _payload(self) -> dict[str, Any]:
        result = self._unsigned_payload()
        result["hash"] = self.hash
        return result

    def to_frame(self) -> pd.DataFrame:
        """Return repeat-major score rows without individual covariate values.

        Returns
        -------
        pandas.DataFrame
            Fresh row/fold identity, outcomes, treatments, predictions and
            scores, with one row per repeat and analysis observation.
        """
        from ._oof_result import bundle_frame

        return bundle_frame(self)

    def score_concentration(self, *, top_fraction: float = 0.01) -> tuple[dict, ...]:
        """Return per-repeat concentration diagnostics for centered scores.

        Parameters
        ----------
        top_fraction : float, default 0.01
            Fraction in (0, 1] used for the largest squared-score share sum.

        Returns
        -------
        tuple of dict
            One independent JSON-ready record per repeat, with cmax, z_c,
            top_share, h and effective_score_count. Undefined diagnostics
            have status='diagnostic_unavailable' and explicit failure_reason.

        References
        ----------
        See ``docs/dml_oof_audit.md`` for definitions; these are diagnostics,
        not tests of causal identification.
        """
        from ._score_concentration import score_concentration

        return score_concentration(self.psi, top_fraction=top_fraction)

    def to_json(self, path: Union[str, Path]) -> None:
        """Write full individual-level IDs, Y, D, X, nuisance predictions, and scores.

        Choose the path, permissions, and sharing scope under the applicable
        user-data policy; the file carries one whole-bundle hash.

        Parameters
        ----------
        path : str or pathlib.Path
            Destination for full individual-level schema-v1 records.

        Returns
        -------
        None
            Writes deterministic UTF-8 JSON.
        """
        Path(path).write_bytes(_json.canonical_bytes(self._payload()))

    @classmethod
    def from_json(cls, path: Union[str, Path]) -> "OOFBundle":
        """Read only after checking schema, duplicate keys, and stored hash.

        Parameters
        ----------
        path : str or pathlib.Path
            Schema-v1 bundle JSON file.

        Returns
        -------
        OOFBundle
            Validated independent snapshot, including reconstructed scores.
        """
        payload = _json.require_keys(
            _json.read_json(path, "OOFBundle"), _json.BUNDLE_KEYS, "bundle"
        )
        if payload["schema_version"] != _json.BUNDLE_SCHEMA:
            raise ValueError(f"unknown OOFBundle schema: {payload['schema_version']!r}")
        arrays = _json.require_keys(
            payload["arrays"], _json.BUNDLE_ARRAY_KEYS, "bundle arrays"
        )
        positions = _json.require_keys(
            payload["input_mapping"], _json.INPUT_MAPPING_KEYS, "input mapping"
        )
        stored = payload["hash"]
        unsigned = {name: value for name, value in payload.items() if name != "hash"}
        _json.require_matching_digest(
            stored, _json.digest(unsigned), "bundle hash mismatch"
        )
        result = cls.from_arrays(
            predictions=OOFPredictions._from_payload(payload["predictions"]),
            aggregation=payload["aggregation"],
            metadata=payload["metadata"],
            **arrays,
            **positions,
        )
        _json.require_matching_digest(
            stored, result.hash, "bundle hash changed during reconstruction"
        )
        return result


def _clone_oof_predictions(predictions: OOFPredictions) -> OOFPredictions:
    from ._oof_result import _clone_predictions

    return _clone_predictions(predictions)


def _attach_result_oof(result: Any, bundle: OOFBundle) -> None:
    from ._oof_result import attach_result_oof

    attach_result_oof(result, bundle)


def _get_result_oof(result: Any) -> OOFBundle:
    from ._oof_result import get_result_oof

    return get_result_oof(result)


def _get_result_residuals(result: Any, *, rep: Optional[int] = None) -> pd.DataFrame:
    from ._oof_result import get_result_residuals

    return get_result_residuals(result, rep)


__all__ = ["OOFBundle", "OOFPredictions"]

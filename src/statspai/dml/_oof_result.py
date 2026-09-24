"""Defensive result snapshots and tabular views for retained DML OOF data."""

from __future__ import annotations

import operator
from typing import Any, Optional, Sequence

import numpy as np
import pandas as pd

from . import _oof_serialization as _json
from .oof import OOFBundle, OOFPredictions

_UNAVAILABLE = (
    "OOF records are unavailable; refit a supported model='irm' ATE "
    "call with store_oof=True"
)
_PREDICTION_ARRAYS = ("y", "d", "x", "g0", "g1", "ps_raw", "fold_ids")
_BUNDLE_ARRAYS = (
    "ps_used",
    "psi_b",
    "psi",
    "theta",
    "se",
    "input_positions",
    "dropped_positions",
)


def _array_structure(value: Any, names: Sequence[str]) -> tuple:
    return tuple(
        (name, getattr(value, name).dtype.str, getattr(value, name).shape)
        for name in names
    )


def _prediction_structure(predictions: Any) -> tuple:
    return (
        predictions.schema_version,
        type(predictions.ids),
        type(predictions.covariate_names),
        type(predictions.training_records),
        type(predictions.source),
        type(predictions.hashes),
        _array_structure(predictions, _PREDICTION_ARRAYS),
    )


def _clone_predictions(predictions: OOFPredictions) -> OOFPredictions:
    """Clone only after checking live values, hashes, and array headers."""
    payload = predictions._payload()
    expected = _json.prediction_hashes(payload)
    _json.verify_prediction_hashes(predictions.hashes, expected, "OOF prediction")
    structure = _prediction_structure(predictions)
    clone = predictions._clone()
    preserved = _prediction_structure(clone) == structure
    if not preserved or dict(clone.hashes) != dict(predictions.hashes):
        raise ValueError("OOF prediction hash/structure changed during clone")
    return clone


def _bundle_structure(bundle: "OOFBundle") -> tuple:
    return (
        bundle.schema_version,
        type(bundle.aggregation),
        type(bundle.metadata),
        type(bundle.hash),
        _array_structure(bundle, _BUNDLE_ARRAYS),
    )


def clone_bundle(bundle: "OOFBundle") -> "OOFBundle":
    """Factory-clone a bundle while rejecting stale declared hashes."""
    predictions = _clone_predictions(bundle.predictions)
    unsigned = bundle._unsigned_payload()
    _json.require_matching_digest(
        bundle.hash, _json.digest(unsigned), "OOF bundle hash mismatch"
    )
    structure = _bundle_structure(bundle)
    clone = OOFBundle.from_arrays(
        predictions=predictions,
        ps_used=bundle.ps_used,
        psi_b=bundle.psi_b,
        psi=bundle.psi,
        theta=bundle.theta,
        se=bundle.se,
        input_positions=bundle.input_positions,
        dropped_positions=bundle.dropped_positions,
        aggregation=bundle.aggregation,
        metadata=bundle.metadata,
    )
    if _bundle_structure(clone) != structure:
        raise ValueError("OOF bundle hash/structure changed during clone")
    if dict(clone.predictions.hashes) != dict(bundle.predictions.hashes):
        raise ValueError("OOF prediction hash changed during clone")
    if clone.hash != bundle.hash:
        raise ValueError("OOF bundle hash changed during clone")
    return clone


def attach_result_oof(result: Any, bundle: "OOFBundle") -> None:
    """Attach an independent validated bundle snapshot to a result."""
    result.__dict__["_dml_oof_bundle"] = clone_bundle(bundle)


def get_result_oof(result: Any) -> "OOFBundle":
    """Return a fresh validated snapshot or the stable unavailable error."""
    bundle = result.__dict__.get("_dml_oof_bundle")
    if bundle is None:
        raise ValueError(_UNAVAILABLE)
    return clone_bundle(bundle)


def _row_columns(bundle: "OOFBundle") -> dict:
    repeats, n_obs = bundle.ps_used.shape
    rep = np.repeat(np.arange(repeats), n_obs)
    folds = bundle.predictions.fold_ids.reshape(-1)
    origins = {
        (row["rep"], row["fold_id"]): row["origin"]
        for row in bundle.predictions.training_records
    }
    return {
        "rep": rep,
        "row_id": pd.Series(np.tile(bundle.predictions.ids, repeats), dtype=object),
        "input_position": np.tile(bundle.input_positions, repeats),
        "fold_id": folds,
        "training_origin": pd.Series(
            [origins[(int(r), int(f))] for r, f in zip(rep, folds)], dtype=object
        ),
    }


def bundle_frame(bundle: "OOFBundle") -> pd.DataFrame:
    """Return the schema-v1 repeat-major public score table."""
    repeats = bundle.predictions.n_rep
    return pd.DataFrame(
        {
            **_row_columns(bundle),
            "y": np.tile(bundle.predictions.y, repeats),
            "d": np.tile(bundle.predictions.d, repeats),
            **{
                name: getattr(bundle.predictions, name).reshape(-1)
                for name in ("g0", "g1", "ps_raw")
            },
            **{
                name: getattr(bundle, name).reshape(-1)
                for name in ("ps_used", "psi_b", "psi")
            },
        }
    )


def get_result_residuals(result: Any, rep: Optional[int]) -> pd.DataFrame:
    """Build a fresh residual table and apply the strict repeat selector."""
    bundle = get_result_oof(result)
    prediction = bundle.predictions
    repeats = prediction.n_rep
    frame = pd.DataFrame(
        {
            **_row_columns(bundle),
            "psi": bundle.psi.reshape(-1),
            "y_minus_gd": np.tile(prediction.y, repeats)
            - (
                np.tile(prediction.d, repeats) * prediction.g1.reshape(-1)
                + np.tile(1 - prediction.d, repeats) * prediction.g0.reshape(-1)
            ),
            "d_minus_ps_raw": np.tile(prediction.d, repeats)
            - prediction.ps_raw.reshape(-1),
        }
    )
    if rep is None:
        return frame
    if isinstance(rep, (bool, np.bool_)):
        raise TypeError("rep must be an integer or None")
    try:
        selected = operator.index(rep)
    except TypeError as exc:
        raise TypeError("rep must be an integer or None") from exc
    if selected < 0 or selected >= repeats:
        raise IndexError("rep is outside the stored repeat range")
    return frame.loc[frame["rep"] == selected].reset_index(drop=True)

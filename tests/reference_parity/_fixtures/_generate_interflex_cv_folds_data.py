"""Fold assignments for the given-fold check of interflex's kernel CV.

StatsPAI draws its CV folds with numpy (``interflex._create_folds``, the
port of ``interflex:::createFolds``); R cannot reproduce that stream, but it
can *score* the same folds. This writes ``interflex_cv_folds.json``: for
numpy seeds 0..4 the 1-based fold id of every observation of
``interflex_cv_data.csv``, plus the indices of the interflex grid at which
the scoring is compared (the five smallest bandwidths, where the local fits
are nearly singular and any port slip would show first, and the plateau
point 17). ``_generate_interflex_cv_folds_R.R`` then scores them with
interflex's own ``getError.CV`` closure.

    python tests/reference_parity/_fixtures/_generate_interflex_cv_folds_data.py
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd

from statspai.regression.interflex import _create_folds

HERE = pathlib.Path(__file__).parent
SEEDS = [0, 1, 2, 3, 4]
GRID_INDICES = [0, 1, 2, 3, 4, 17]

if __name__ == "__main__":
    df = pd.read_csv(HERE / "interflex_cv_data.csv")
    out = {"grid_indices": GRID_INDICES, "kfold": 10, "folds": {}}
    for s in SEEDS:
        fold = _create_folds(df["D"].to_numpy(float), 10, np.random.default_rng(s))
        out["folds"][str(s)] = (fold + 1).tolist()
    (HERE / "interflex_cv_folds.json").write_text(json.dumps(out), encoding="utf-8")
    print("wrote interflex_cv_folds.json")

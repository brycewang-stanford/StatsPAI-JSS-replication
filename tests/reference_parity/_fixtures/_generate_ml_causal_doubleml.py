"""DoubleML reference for ``sp.dml_panel`` (cluster-robust PLR on within data).

Run after ``_generate_ml_causal_panel_R.R`` (which writes the fixest-demeaned
panel)::

    python tests/reference_parity/_fixtures/_generate_ml_causal_doubleml.py

Writes ``ml_causal_doubleml.json``. ``sp.dml_panel`` is Clarke & Polselli's
within-group DML: absorb unit (and time) effects, then cross-fit PLR with
folds that split units and a unit-clustered SE. DoubleML is fed the
fixest-demeaned y, d, x (so the fixed-effect absorption is pinned to fixest
separately), OLS learners, the committed unit-level folds, and one-way unit
clustering. R DoubleML 1.0.2 refuses externally set sample splits with
clustered data ("not yet implemented with clustering"), so the Python
package -- same maintainers, same estimator -- is the reference.
"""

from __future__ import annotations

import json
import pathlib

import doubleml as dml
import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import LinearRegression

HERE = pathlib.Path(__file__).parent


def _fit(panel: pd.DataFrame, dm: dict) -> dict:
    df = pd.DataFrame(
        {
            "y": dm["y"], "d": dm["d"], "x1": dm["x1"], "x2": dm["x2"], "x3": dm["x3"],
            "unit": panel["unit"].to_numpy(),
        }
    )
    data = dml.DoubleMLClusterData(
        df, y_col="y", d_cols="d", cluster_cols="unit", x_cols=["x1", "x2", "x3"]
    )
    fold = panel["fold"].to_numpy()
    unit = panel["unit"].to_numpy()
    idx = np.arange(len(df))
    smpls, smpls_cluster = [], []
    for k in sorted(np.unique(fold)):
        test = idx[fold == k]
        train = idx[fold != k]
        smpls.append((train, test))
        smpls_cluster.append(
            ([np.unique(unit[fold != k])], [np.unique(unit[fold == k])])
        )
    plr = dml.DoubleMLPLR(
        data, LinearRegression(), LinearRegression(), n_folds=len(smpls),
        draw_sample_splitting=False,
    )
    plr.set_sample_splitting(all_smpls=[smpls], all_smpls_cluster=[smpls_cluster])
    plr.fit()
    return {"coef": float(plr.coef[0]), "se": float(plr.se[0])}


def main() -> None:
    ref = json.loads((HERE / "ml_causal_panel_R.json").read_text(encoding="utf-8"))
    bal = pd.read_csv(HERE / "ml_causal_panel.csv")
    unb = pd.read_csv(HERE / "ml_causal_panel_unbal.csv")
    out = {
        "meta": {"doubleml_version": dml.__version__, "sklearn_version": sklearn.__version__},
        "balanced_unit": _fit(bal, ref["demeaned"]["balanced_unit"]),
        "balanced_twoway": _fit(bal, ref["demeaned"]["balanced_twoway"]),
        "unbal_twoway": _fit(unb, ref["demeaned"]["unbal_twoway"]),
    }
    (HERE / "ml_causal_doubleml.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()

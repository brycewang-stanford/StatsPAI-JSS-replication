"""Frozen PySAL ``mgwr`` reference for ``sp.mgwr`` (round-2 spatial line).

The canonical MGWR implementation is the authors' own Python package
``mgwr`` (PySAL; Oshan, Li, Kang, Wolf & Fotheringham). It is NOT a
StatsPAI dependency: install it into a scratch directory and put that
directory on PYTHONPATH for this script only, e.g.

    pip install --target /tmp/mgwr_ref mgwr==2.2.1
    PYTHONPATH=/tmp/mgwr_ref python tests/reference_parity/_generate_r2_spatial_mgwr.py

Data: the Georgia county file ``GData_utm.csv`` shipped with libpysal
(identical to ``GWmodel::Gedu.df``, checked with ``all.equal`` on PctBach,
PctFB and X). It is copied once to ``_fixtures/r2_spatial_georgia.csv``;
later runs read that copy. As in mgwr's documentation and its own test
suite, y = PctBach and X = (PctFB, PctBlack, PctRural) are standardised
(mean 0, numpy ``std`` with ddof = 0) before fitting.

Writes ``_fixtures/r2_spatial_mgwr.json``.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

import mgwr  # noqa: E402
from mgwr.gwr import MGWR  # noqa: E402
from mgwr.sel_bw import Sel_BW  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
FX = HERE / "_fixtures"
CSV = FX / "r2_spatial_georgia.csv"

if not CSV.exists():
    import libpysal as ps

    shutil.copyfile(ps.examples.get_path("GData_utm.csv"), CSV)

d = pd.read_csv(CSV)
coords = d[["X", "Y"]].to_numpy(float)
y = d[["PctBach"]].to_numpy(float)
X = d[["PctFB", "PctBlack", "PctRural"]].to_numpy(float)
y = (y - y.mean()) / y.std()
X = (X - X.mean(axis=0)) / X.std(axis=0)

CONFIGS = {
    # mgwr's documented default: adaptive bisquare, AICc
    "adaptive_bisquare_aicc": ({"kernel": "bisquare", "fixed": False}, {}),
    # fixed bandwidths: continuous golden section, 2-decimal rounding
    "fixed_gaussian_aicc": ({"kernel": "gaussian", "fixed": True}, {}),
    "adaptive_bisquare_cv": (
        {"kernel": "bisquare", "fixed": False},
        {"criterion": "CV"},
    ),
    "adaptive_exponential_bic_min20": (
        {"kernel": "exponential", "fixed": False},
        {"criterion": "BIC", "multi_bw_min": [20]},
    ),
}

out = {
    "versions": {
        "python": sys.version.split()[0],
        "mgwr": mgwr.__version__,
        "numpy": np.__version__,
    },
    "data": "r2_spatial_georgia.csv; y = PctBach, X = (PctFB, PctBlack, PctRural), standardised (ddof 0)",
}

for name, (kw, skw) in CONFIGS.items():
    sel = Sel_BW(coords, y, X, multi=True, constant=True, n_jobs=1, **kw)
    bws = sel.search(**skw)
    res = MGWR(coords, y, X, sel, constant=True, n_jobs=1, **kw).fit()
    out[name] = {
        "kernel": kw["kernel"],
        "fixed": kw["fixed"],
        "search": {k: v for k, v in skw.items()},
        "bws": [float(b) for b in bws],
        "bw_init": float(sel.bw_init),
        "bws_history": np.asarray(sel.bw[1], float).tolist(),
        "scores": np.asarray(sel.bw[2], float).ravel().tolist(),
        "params": res.params.tolist(),
        "bse": res.bse.tolist(),
        "predy": res.predy.ravel().tolist(),
        "ENP_j": np.asarray(res.ENP_j, float).tolist(),
        "tr_S": float(res.tr_S),
        "sigma2": float(res.sigma2),
        "resid_ss": float(res.resid_ss),
        "aicc": float(res.aicc),
        "aic": float(res.aic),
        "bic": float(res.bic),
        "llf": float(res.llf),
    }
    print(name, out[name]["bws"], out[name]["aicc"], flush=True)

(FX / "r2_spatial_mgwr.json").write_text(
    json.dumps(out, indent=1, default=float), encoding="utf-8"
)

"""Python side of the forest algorithmic Monte Carlo comparison.

Mirror of ``_generate_grf_seed_mc_R.R``: the data (``grf_data.csv``) are
fixed; ``sp.causal_forest`` is refitted under K seeds at each tree count, and
each fit records the AIPW ATE (and SE), the AIPW ATT, and OOB CATE
predictions at the first 20 training rows. The seeds are StatsPAI's own
(``random_state = 1000 + 100000 k``, spaced like the R side's -- grf's
consecutive seeds share most of their random draws); R and NumPy streams are
unrelated, which is exactly why the comparison is between distributions, not
between draws.

Run from this directory::

    python _generate_grf_seed_mc_py.py        # grf_data.csv  -> grf_seed_mc_py.json
    python _generate_grf_seed_mc_py.py m13    # module 13 CSV -> grf_seed_mc_m13_py.json

Both sides use their defaults for the ATE (no propensity clipping), so the
comparison is like-for-like.
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DESIGN = ((500, 50), (2000, 50), (8000, 20))
DATASETS = {
    "grf": (HERE / "grf_data.csv", "y ~ W | X1 + X2 + X3 + X4 + X5", "grf_seed_mc_py.json"),
    "m13": (
        HERE.parents[1] / "r_parity" / "data" / "13_causal_forest.csv",
        "Y ~ T | x1 + x2 + x3 + x4 + x5",
        "grf_seed_mc_m13_py.json",
    ),
}
FORMULA = DATASETS["grf"][1]


def fit_once(df: pd.DataFrame, trees: int, seed: int) -> dict:
    import statspai as sp

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cf = sp.causal_forest(
            FORMULA,
            data=df,
            n_estimators=trees,
            random_state=seed,
            discrete_treatment=True,
        )
        ate = cf.average_treatment_effect(target_sample="all")
        att = cf.average_treatment_effect(target_sample="treated")
    return {
        "seed": seed,
        "ate": float(ate["estimate"]),
        "ate_se": float(ate["se"]),
        "att": float(att["estimate"]),
        "cate20": [float(v) for v in np.asarray(cf.predict()).ravel()[:20]],
    }


def main() -> None:
    import statspai as sp

    global FORMULA
    which = sys.argv[1] if len(sys.argv) > 1 else "grf"
    path, FORMULA, outfile = DATASETS[which]
    df = pd.read_csv(path)
    out: dict = {}
    for trees, k_seeds in DESIGN:
        out[f"trees_{trees}"] = [
            fit_once(df, trees, 1000 + 100000 * k) for k in range(1, k_seeds + 1)
        ]
        print(f"trees={trees}: {k_seeds} fits", flush=True)
    out["meta"] = {
        "statspai": sp.__version__,
        "python": sys.version.split()[0],
        "n": int(len(df)),
        "seeds": "1000 + 100000 k",
    }
    (HERE / outfile).write_text(json.dumps(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

"""Data for the GRF engine statistical-parity fixture (evidence tier T3).

Two designs with a known CATE, written to ``grf_engine_data.csv``:

* ``iid``: n = 2000, five covariates, confounded binary treatment
  ``e(x) = 0.25 + 0.5 * Phi(x1)``, ``tau(x) = 1 + 2 * max(x1, 0) - x2``.
* ``clustered``: the same covariates and effect with 200 clusters carrying a
  shared outcome shock and a shared treatment-propensity shift.

The R companion fits ``grf::causal_forest`` with three seeds on each design
and stores the out-of-bag CATE predictions and variance estimates.

    python tests/reference_parity/_fixtures/_generate_grf_engine_data.py
"""

from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd
from scipy.stats import norm

OUT = pathlib.Path(__file__).parent / "grf_engine_data.csv"


def main() -> None:
    rng = np.random.default_rng(611)
    n = 2000
    X = rng.normal(size=(n, 5))
    cluster = rng.integers(0, 200, size=n)
    tau = 1.0 + 2.0 * np.maximum(X[:, 0], 0.0) - X[:, 1]
    frames = []
    for design in ("iid", "clustered"):
        if design == "iid":
            shift = np.zeros(n)
            shock = np.zeros(n)
        else:
            shift = rng.normal(scale=0.5, size=200)[cluster]
            shock = rng.normal(scale=1.0, size=200)[cluster]
        e = np.clip(0.25 + 0.5 * norm.cdf(X[:, 0] + shift), 0.05, 0.95)
        W = (rng.uniform(size=n) < e).astype(float)
        Y = X[:, 2] + np.maximum(X[:, 3], 0) + shock + tau * W + rng.normal(size=n)
        df = pd.DataFrame(X, columns=[f"x{j + 1}" for j in range(5)])
        df["W"] = W
        df["Y"] = Y
        df["tau"] = tau
        df["cluster"] = cluster
        df["design"] = design
        frames.append(df)
    pd.concat(frames, ignore_index=True).to_csv(OUT, index=False, float_format="%.17g")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

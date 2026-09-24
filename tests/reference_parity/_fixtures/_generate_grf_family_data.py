"""Data for the GRF-family operator fixture (evidence tier T2, forest held fixed).

One small design per forest, written to ``grf_family_data.csv`` (n = 200
each).  The R companion ``_generate_grf_family.R`` fits the grf forests on
these rows and exports what their *operators* consume and produce --
out-of-bag forest weights of the first 40 rows, nuisance estimates,
predictions, doubly-robust scores, averages, projections, split
frequencies -- so the StatsPAI operators can be fed grf's own forest and
checked to the floating-point floor.

Values are rounded to 6 decimals so the CSV round-trip is exact on both
sides (grid lookups such as ``findInterval`` compare times for equality).

    python tests/reference_parity/_fixtures/_generate_grf_family_data.py
"""

from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd

OUT = pathlib.Path(__file__).parent / "grf_family_data.csv"


def main() -> None:
    rng = np.random.default_rng(2026)
    n = 200
    frames = []

    X = rng.normal(size=(n, 3))
    Z = rng.binomial(1, 0.5, n)
    U = rng.normal(size=n)
    W = (1.2 * Z + 0.6 * U + rng.normal(scale=0.5, size=n) > 0.6).astype(int)
    Y = (1.0 + X[:, 0]) * W + X[:, 1] + U + rng.normal(size=n)
    frames.append(
        pd.DataFrame({"design": "iv", "Y": Y, "W": W, "Z": Z, "D": 0, "W2": 0.0}).join(
            pd.DataFrame(X, columns=["x1", "x2", "x3"])
        )
    )

    X = rng.normal(size=(n, 3))
    A = rng.integers(0, 3, n)
    Y = X[:, 1] + (1.0 + X[:, 0]) * (A == 1) - 0.5 * (A == 2) + rng.normal(size=n)
    W2 = rng.normal(size=n)
    frames.append(
        pd.DataFrame(
            {"design": "multiarm", "Y": Y, "W": A, "Z": 0, "D": 0, "W2": W2}
        ).join(pd.DataFrame(X, columns=["x1", "x2", "x3"]))
    )

    X = rng.normal(size=(n, 3))
    W = rng.binomial(1, 1 / (1 + np.exp(-0.5 * X[:, 1])))
    rate = np.exp(0.3 * X[:, 1] - 0.7 * W * (X[:, 0] > 0))
    T = rng.exponential(1 / rate)
    C = rng.exponential(3.0, n)
    frames.append(
        pd.DataFrame(
            {
                "design": "survival",
                "Y": np.minimum(T, C),
                "W": W,
                "Z": 0,
                "D": (T <= C).astype(int),
                "W2": 0.0,
            }
        ).join(pd.DataFrame(X, columns=["x1", "x2", "x3"]))
    )

    out = pd.concat(frames, ignore_index=True)
    num = out.select_dtypes("number").columns
    out[num] = out[num].round(6)
    out.to_csv(OUT, index=False)
    print(f"wrote {OUT.name} ({len(out)} rows)")


if __name__ == "__main__":
    main()

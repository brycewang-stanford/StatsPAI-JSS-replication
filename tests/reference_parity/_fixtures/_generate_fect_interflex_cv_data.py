"""Deterministic designs for the fect / interflex cross-validation T3 check.

Writes two CSVs next to this file, read byte-for-byte by both
``tests/reference_parity/_generate_fect_interflex_cv_R.R`` (R reference,
20 fold seeds) and ``tests/reference_parity/test_fect_interflex_cv_parity.py``:

- ``fect_cv_data.csv``: 60 units x 24 periods, 20 never treated, four
  cohorts of 10 first treated in 10 / 14 / 18 / 22 (so every unit has at
  least 9 untreated pre-onset periods, above fect's ``min.T0 + cv.nobs =
  8`` eligibility bar for the rolling holdout), a two-factor error
  structure whose loadings correlate with adoption timing, two
  covariates and noise sd 0.5. The true factor number is 2.
- ``interflex_cv_data.csv``: 400 observations, binary treatment, moderator
  with a quadratic conditional marginal effect and one covariate, as in
  Track A module 87.

    python tests/reference_parity/_fixtures/_generate_fect_interflex_cv_data.py
"""

from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).parent
SEED_FECT = 8620
SEED_INTERFLEX = 8720


def make_fect_panel(seed: int = SEED_FECT) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    N, T, R = 60, 24, 2
    first_treat = np.zeros(N, dtype=int)
    for c, start in enumerate((10, 14, 18, 22)):
        first_treat[20 + 10 * c : 30 + 10 * c] = start
    alpha = rng.normal(0.0, 1.0, N)
    xi = rng.normal(0.0, 1.0, T)
    F = rng.normal(0.0, 1.0, (T, R))
    L = rng.normal(0.0, 1.0, (N, R))
    L[:, 0] += np.where(first_treat > 0, (24 - first_treat) / 6.0, 0.0)
    tau_unit = rng.normal(1.0, 0.3, N)
    rows = []
    for i in range(N):
        for t_idx in range(T):
            t = t_idx + 1
            x1 = rng.normal(0.0, 1.0) + 0.3 * L[i, 1]
            x2 = rng.normal(0.0, 1.0)
            d = int(first_treat[i] > 0 and t >= first_treat[i])
            since = (t - first_treat[i] + 1) if d else 0
            effect = tau_unit[i] * (1.0 + 0.2 * since) if d else 0.0
            y = (
                5.0
                + alpha[i]
                + xi[t_idx]
                + F[t_idx] @ L[i]
                + 1.0 * x1
                - 0.5 * x2
                + effect
                + rng.normal(0.0, 0.5)
            )
            rows.append(
                {
                    "id": i + 1,
                    "time": t,
                    "Y": float(y),
                    "D": d,
                    "X1": float(x1),
                    "X2": float(x2),
                }
            )
    return pd.DataFrame(rows)


def make_interflex_sample(seed: int = SEED_INTERFLEX, n: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    x = rng.normal(1.0, 1.2, n)
    z = rng.normal(0.0, 1.0, n)
    d = rng.binomial(1, 0.5, n).astype(float)
    me = 2.0 + 1.5 * x - 0.25 * x**2
    y = 1.0 + 0.8 * x + 0.5 * z + d * me + rng.normal(0.0, 1.0, n)
    return pd.DataFrame({"Y": y, "D": d, "X": x, "Z1": z})


if __name__ == "__main__":
    make_fect_panel().to_csv(
        HERE / "fect_cv_data.csv", index=False, float_format="%.17g"
    )
    make_interflex_sample().to_csv(
        HERE / "interflex_cv_data.csv", index=False, float_format="%.17g"
    )
    print("wrote fect_cv_data.csv and interflex_cv_data.csv")

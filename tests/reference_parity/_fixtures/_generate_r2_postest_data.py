"""Write the simulated input of tests/reference_parity/test_r2_postest_parity.py.

Run before ``_generate_r2_postest_stata.do``. Deterministic (fixed seed); the
CSV is committed so the Stata and Python sides read identical bytes.

Design, chosen so every convention the margins family depends on is visible:

* ``g`` -- a four-level factor (levels 1..4, unequal cell sizes), so reference,
  adjacent and weighted-grand-mean contrasts differ from one another and there
  are six pairwise comparisons for the multiple-comparison adjustments;
* ``h`` -- a binary factor, unbalanced across ``g`` (so ``margins`` averaging
  over the observed ``h`` distribution differs from ``contrast`` / ``pwcompare``
  balancing over ``h`` in a g x h interaction);
* ``x``, ``z`` -- continuous covariates, correlated with ``g``;
* ``cl`` -- 40 clusters of unequal size (df = G - 1 under clustering);
* ``yl`` linear, ``yb`` logistic, ``yp`` probit, ``yc`` Poisson outcomes;
* ``yl_m`` -- ``yl`` with 25 values missing, so the estimation sample differs
  from the rows of the data frame (Stata's ``margins`` averages over
  ``e(sample)``).
"""

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).parent

rng = np.random.default_rng(20260918)
n = 600
g = rng.choice([1, 2, 3, 4], size=n, p=[0.35, 0.25, 0.25, 0.15])
h = (rng.uniform(size=n) < np.array([0.2, 0.4, 0.6, 0.8])[g - 1]).astype(int)
x = rng.normal(size=n) + 0.3 * (g - 2.5)
z = rng.normal(size=n)
cl = rng.integers(1, 41, size=n)
u_c = rng.normal(0, 0.5, 41)[cl]

gd = np.array([0.0, 0.6, 1.1, -0.4])[g - 1]
yl = (
    1.0
    + gd
    + 0.5 * x
    - 0.3 * z
    + 0.4 * h
    + 0.35 * x * (g == 3)
    - 0.5 * h * (g == 4)
    + u_c
    + rng.normal(size=n)
)
eta_b = -0.3 + 0.8 * gd + 0.6 * x - 0.4 * z
yb = (rng.uniform(size=n) < 1.0 / (1.0 + np.exp(-eta_b))).astype(int)
eta_p = -0.2 + 0.5 * gd + 0.4 * x - 0.3 * z
yp = (rng.normal(size=n) < eta_p).astype(int)
yc = rng.poisson(np.exp(0.2 + 0.3 * x - 0.2 * z + 0.2 * gd))

yl_m = yl.copy()
yl_m[rng.choice(n, size=25, replace=False)] = np.nan

pd.DataFrame(
    {
        "g": g,
        "h": h,
        "x": x,
        "z": z,
        "cl": cl,
        "yl": yl,
        "yb": yb,
        "yp": yp,
        "yc": yc,
        "yl_m": yl_m,
    }
).to_csv(OUT / "r2_postest_data.csv", index=False, float_format="%.17g")
print("wrote r2_postest_data.csv")

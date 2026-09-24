"""Write the simulated inputs of tests/reference_parity/test_decomp_qte_parity.py.

Run once, before ``_generate_decomp_qte_stata.do`` and
``../_generate_decomp_qte_R.R``. Deterministic (fixed seeds, numpy
``default_rng``); the CSVs are committed so Python, R and Stata read
identical bytes (``%.17g``).

* ``dq_wage.csv`` -- two groups of EXACTLY equal size (500 / 500). Equal
  sizes matter for ``fairlie``: Stata's ``fairlie`` only draws a random
  subsample when the groups differ in size, so with 500 / 500 its matching
  is the deterministic rank-to-rank pairing and the decomposition is
  reproducible to machine precision. Continuous covariates make every
  quantile regression solution unique (no LP degeneracy), so the Melly /
  CFM counterfactual distributions are pinnable. ``log_wage`` is
  heteroskedastic with group-specific slopes, so composition and structure
  effects both vary with tau.
* ``dq_med.csv`` -- confounded binary exposure (``a`` depends on ``c1``),
  continuous mediator and outcome with an exposure-mediator interaction.
  The confounding makes mean(c | a=0) differ from mean(c), which is what
  separates the natural direct effect at the covariate mean from the one
  at the unexposed covariate mean.
* ``dq_iv.csv`` -- binary instrument whose assignment depends on ``x1``
  (so a covariate propensity binds), 25% always-takers / 55% compliers /
  20% never-takers, and a complier effect that fans with the quantile.
"""

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).parent

# ---- wage decomposition data (balanced groups) ---------------------------
rng = np.random.default_rng(20260918)
n_per = 500
g = np.repeat([0, 1], n_per)
n = 2 * n_per
educ = rng.normal(13.0 - 0.6 * g, 2.5)
exper = rng.gamma(4.0, 4.0 - 0.5 * g)
tenure = rng.uniform(0.0, 12.0, n)
e = rng.normal(size=n)
scale = 0.35 + 0.02 * educ - 0.05 * g
log_wage = (
    1.0
    + (0.08 - 0.01 * g) * educ
    + 0.02 * exper
    + 0.015 * tenure
    - 0.10 * g
    + scale * e
)
lin_u = -1.2 + 0.10 * (educ - 13.0) + 0.04 * exper - 0.6 * g
union = (rng.uniform(size=n) < 1.0 / (1.0 + np.exp(-lin_u))).astype(int)
pd.DataFrame(
    {
        "female": g,
        "educ": educ,
        "exper": exper,
        "tenure": tenure,
        "log_wage": log_wage,
        "wage": np.exp(log_wage),
        "union": union,
    }
).to_csv(OUT / "dq_wage.csv", index=False, float_format="%.17g")

# ---- mediation / disparity data ------------------------------------------
rng = np.random.default_rng(7171)
n = 800
c1 = rng.normal(size=n)
c2 = rng.binomial(1, 0.4, n)
a = (rng.uniform(size=n) < 1.0 / (1.0 + np.exp(-(-0.2 + 0.9 * c1)))).astype(int)
m = 0.5 + 0.6 * a + 0.4 * c1 + 0.3 * c2 + rng.normal(size=n)
y = 1.0 + 0.5 * a + 0.7 * m + 0.4 * a * m + 0.3 * c1 - 0.2 * c2 + rng.normal(size=n)
pd.DataFrame({"y": y, "a": a, "m": m, "c1": c1, "c2": c2}).to_csv(
    OUT / "dq_med.csv", index=False, float_format="%.17g"
)

# ---- IV quantile data ------------------------------------------------------
rng = np.random.default_rng(99)
n = 1000
x1 = rng.normal(size=n)
x2 = rng.binomial(1, 0.5, n)
z = (rng.uniform(size=n) < 1.0 / (1.0 + np.exp(-(0.1 + 0.7 * x1 - 0.4 * x2)))).astype(
    int
)
u = rng.uniform(size=n)
typ = np.where(u < 0.25, 2, np.where(u < 0.80, 1, 0))  # 2 always, 1 complier, 0 never
d = np.where(typ == 2, 1, np.where(typ == 1, z, 0))
y0 = 1.0 + 0.5 * x1 + 0.3 * x2 + rng.normal(size=n)
y1 = y0 + 1.0 + 0.8 * rng.normal(size=n)
y = np.where(d == 1, y1, y0)
pd.DataFrame({"y": y, "d": d, "z": z, "x1": x1, "x2": x2}).to_csv(
    OUT / "dq_iv.csv", index=False, float_format="%.17g"
)
print("wrote dq_wage.csv, dq_med.csv, dq_iv.csv")

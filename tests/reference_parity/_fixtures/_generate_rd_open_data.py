"""Write the simulated inputs of tests/reference_parity/test_rd_open_R_parity.py.

Run before ``../_generate_rd_open_R.R``. Deterministic (fixed seed); the CSVs
are committed so the R and Python sides read identical bytes.

rd_open_bd.csv
    A boundary-discontinuity design for R ``rd2d`` (Cattaneo, Titiunik and
    Yu). Two running variables on [-1, 1]^2, assignment ``t = 1`` above the
    line ``x2 = 0.3 x1``. The conditional mean is smooth and non-linear on
    each side and the jump varies along the boundary, so the pointwise
    effects at different boundary points differ. Heteroskedastic noise,
    120 clusters ``g`` for the cluster-robust variances, and a fuzzy take-up
    ``takeup`` (P = 0.85 if assigned, 0.15 if not) whose outcome ``yf``
    carries a 1.5 LATE.

rd_open_bd_mass.csv
    The same design with both coordinates rounded to 0.05 -- a lattice with
    heavy mass points (exercises ``masspoints = "adjust"``).

rd_open_discrete.csv
    A running variable with 21 support points (integer ages 8..28, cutoff
    18) and a curved, heteroskedastic conditional mean -- the setting of
    Kolesar and Rothe's discrete-RD inference (``sp.rd_discrete`` vs R
    ``RDHonest`` / ``RDHonestBME``).

rd_open_extrap.csv
    A sharp RD whose running variable is a noisy index of two covariates,
    ``x = 0.8 z1 + 0.4 z2 + e``, with outcome linear in (z1, z2) on each side
    and an effect ``2 + 0.5 z1`` -- conditional independence of (Y(0), Y(1))
    and x given z holds by construction (Angrist-Rokkanen extrapolation,
    ``sp.rd_extrapolate``).
"""

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).parent


def _design(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    x1 = rng.uniform(-1.0, 1.0, n)
    x2 = rng.uniform(-1.0, 1.0, n)
    t = (x2 >= 0.3 * x1).astype(int)
    g = rng.integers(1, 121, n)
    mu = 0.5 + 0.8 * x1 - 0.6 * x2 + 0.7 * x1 * x2 + 0.5 * x1**2 - 0.3 * x2**2
    jump = 1.0 + 0.6 * x1 + 0.4 * x2
    sig = 0.4 + 0.2 * np.abs(x1)
    y = mu + t * jump + sig * rng.normal(size=n)
    takeup = (rng.uniform(size=n) < np.where(t == 1, 0.85, 0.15)).astype(int)
    yf = mu + 1.5 * takeup + sig * rng.normal(size=n)
    return pd.DataFrame({"y": y, "x1": x1, "x2": x2, "t": t, "g": g,
                         "takeup": takeup, "yf": yf})


def main() -> None:
    df = _design(2500, 20260918)
    df.to_csv(OUT / "rd_open_bd.csv", index=False, float_format="%.17g")
    m = _design(2500, 20260919)
    m["x1"] = np.round(m["x1"] / 0.05) * 0.05
    m["x2"] = np.round(m["x2"] / 0.05) * 0.05
    m["t"] = (m["x2"] >= 0.3 * m["x1"]).astype(int)
    m.to_csv(OUT / "rd_open_bd_mass.csv", index=False, float_format="%.17g")
    rng = np.random.default_rng(20260920)
    age = rng.integers(8, 29, 1500)
    ya = (1.0 + 0.15 * (age - 18) - 0.01 * (age - 18) ** 2 + 0.9 * (age >= 18)
          + (0.6 + 0.03 * np.abs(age - 18)) * rng.normal(size=1500))
    rng = np.random.default_rng(20260921)
    z1, z2 = rng.normal(size=2000), rng.normal(size=2000)
    xe = 0.8 * z1 + 0.4 * z2 + 0.5 * rng.normal(size=2000)
    de = (xe >= 0).astype(int)
    ye = (1.0 + 1.5 * z1 - 0.5 * z2 + de * (2.0 + 0.5 * z1)
          + (0.8 + 0.3 * de) * rng.normal(size=2000))
    pd.DataFrame({"y": ye, "x": xe, "z1": z1, "z2": z2, "d": de}).to_csv(
        OUT / "rd_open_extrap.csv", index=False, float_format="%.17g")
    pd.DataFrame({"y": ya, "age": age}).to_csv(
        OUT / "rd_open_discrete.csv", index=False, float_format="%.17g")


if __name__ == "__main__":
    main()

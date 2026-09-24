"""Write the round-2 frontier parity dataset (fixed seed).

Run from anywhere::

    python tests/reference_parity/_generate_r2_frontier_data.py

Writes ``_fixtures/r2_frontier_zisf_z.csv``: 600 obs of a zero-inefficiency
stochastic frontier whose probability of full efficiency depends on a
covariate ``z`` through a logit link (for ``sp.zisf(zprob=["z"])`` vs
``sfa::zsfm(model_name="ZISF_Z")``).  The other frontier fixtures are reused
from ``_generate_frontier_struct_data.py`` (``frontier_struct_zisf.csv`` and
``frontier_struct_malm.csv``).

Values are written with 17 significant digits so R, Stata and Python read
identical doubles.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).parent / "_fixtures"


def zisf_z_data() -> pd.DataFrame:
    rng = np.random.default_rng(20260930)
    n = 600
    x1 = rng.normal(0.0, 1.0, n)
    x2 = rng.normal(0.0, 1.0, n)
    z = rng.normal(0.0, 1.0, n)
    p_eff = 1.0 / (1.0 + np.exp(-(-0.3 + 0.9 * z)))
    eff = rng.uniform(size=n) < p_eff
    v = rng.normal(0.0, 0.15, n)
    u = np.where(eff, 0.0, np.abs(rng.normal(0.0, 0.5, n)))
    y = 1.0 + 0.6 * x1 + 0.3 * x2 + v - u
    return pd.DataFrame({"y": y, "x1": x1, "x2": x2, "z": z})


if __name__ == "__main__":
    zisf_z_data().to_csv(
        OUT / "r2_frontier_zisf_z.csv", index=False, float_format="%.17g"
    )

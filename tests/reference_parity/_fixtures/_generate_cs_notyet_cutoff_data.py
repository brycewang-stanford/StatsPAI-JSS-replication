"""Panel for the not-yet-treated control-set parity fixture.

Three cohorts (3, 5, 6) plus never-treated units over eight periods, with a
covariate-dependent trend.  The design makes the control set of pre-treatment
cells depend on whether the cutoff is ``t`` or ``max(t, base) +
anticipation``: under a universal base, cohort 5 is untreated at ``t = 2`` but
already treated in cohort 6's base period 5.

    python tests/reference_parity/_fixtures/_generate_cs_notyet_cutoff_data.py
"""

from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd

OUT = pathlib.Path(__file__).parent / "cs_notyet_cutoff_data.csv"


def main() -> None:
    rng = np.random.default_rng(917)
    N, T = 600, 8
    x1 = rng.normal(size=N)
    alpha = x1 + rng.normal(size=N)
    g = rng.choice([0, 3, 5, 6], size=N, p=[0.3, 0.25, 0.25, 0.2])
    rows = []
    for t in range(1, T + 1):
        d = (g > 0) & (t >= g)
        effect = (1 + 0.5 * x1) * (1 + 0.3 * np.maximum(t - g, 0))
        y = alpha + 0.4 * t + 0.25 * x1 * t + d * effect + rng.normal(size=N)
        rows.append(
            pd.DataFrame({"id": np.arange(N), "t": t, "g": g, "x1": x1, "y": y})
        )
    pd.concat(rows, ignore_index=True).to_csv(OUT, index=False, float_format="%.17g")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

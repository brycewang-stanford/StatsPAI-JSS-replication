"""Is the RD row's under-coverage StatsPAI's or the method's?

Track B's sharp-RD robust bias-corrected interval covers 0.934 at B=1,000 on
its curved DGP (size 0.076 at the tested null). A coverage rate cannot say
whether that is an implementation defect or the procedure's finite-sample
behaviour. This script answers it directly: it draws the first 200 datasets
of the Track B DGP, fits ``sp.rdrobust`` on each, has R ``rdrobust`` fit the
same bytes (``rd_drawwise_reference.R``), and records the largest per-draw
difference and both coverage rates. Identical intervals draw by draw mean the
reference procedure itself under-covers here.

Run from this directory: ``python rd_drawwise_reference.py`` (needs R and
``rdrobust``); writes ``results_rd_drawwise.json``.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

import statspai as sp

HERE = Path(__file__).resolve().parent
N_DRAWS = 200
TRUTH = 1.0


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        py = []
        for seed in range(N_DRAWS):
            rng = np.random.default_rng(seed)  # same stream as run_b1000.coverage_rd
            n = 1000
            x = rng.uniform(-1, 1, n)
            y = 2 + 3 * x + x**2 + TRUTH * (x >= 0).astype(int) + rng.normal(scale=0.4, size=n)
            df = pd.DataFrame({"y": y, "x": x})
            df.to_csv(Path(tmp) / f"d{seed:03d}.csv", index=False, float_format="%.17g")
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                r = sp.rdrobust(df, y="y", x="x", c=0.0)
            py.append((r.estimate, r.ci[0], r.ci[1]))
        subprocess.run(
            ["Rscript", str(HERE / "rd_drawwise_reference.R"), tmp, str(N_DRAWS)], check=True
        )
        ref = pd.read_csv(Path(tmp) / "r.csv").to_numpy()
    py = np.asarray(py)
    cover_py = (py[:, 1] <= TRUTH) & (TRUTH <= py[:, 2])
    cover_r = (ref[:, 1] <= TRUTH) & (TRUTH <= ref[:, 2])
    out = {
        "n_draws": N_DRAWS,
        "max_rel_diff_estimate": float(np.max(np.abs(py[:, 0] - ref[:, 0]) / np.abs(ref[:, 0]))),
        "max_abs_diff_ci": float(np.max(np.abs(py[:, 1:] - ref[:, 1:]))),
        "coverage_statspai": float(cover_py.mean()),
        "coverage_rdrobust": float(cover_r.mean()),
        "same_draws_covered": bool(np.array_equal(cover_py, cover_r)),
        "rdrobust_version": subprocess.run(
            ["Rscript", "-e", 'cat(as.character(packageVersion("rdrobust")))'],
            capture_output=True, text=True, check=True,
        ).stdout.strip(),
    }
    (HERE / "results_rd_drawwise.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()

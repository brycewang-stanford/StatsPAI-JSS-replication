#!/usr/bin/env python3
"""Is the SDID row's under-coverage StatsPAI's or the procedure's?

Track B's ``sp.sdid`` placebo interval covers 0.928 at B = 1,000 on a
factor-model panel with one treated unit and 20 controls. This script
redraws those datasets (same generator and seeds as
``tests/coverage_monte_carlo/run_b1000.coverage_sdid``), fits ``sp.sdid``
on each, and has R ``synthdid`` fit the same bytes
(``sdid_drawwise_reference.R``). It records

* the largest per-draw difference of the point estimates;
* the coverage of each package's own placebo interval (100 replications,
  normal quantile), which differ only through which controls the placebo
  resampling happened to draw;
* the coverage of the interval built from the *exhaustive* placebo standard
  error (every control taken once as the pseudo-treated unit), with the
  normal quantile and with the t quantile on N0 - 1 = 19 degrees of
  freedom. The exhaustive standard error has no simulation noise, so the
  last pair isolates the effect of the critical value.

Needs R with ``synthdid``. Writes
``replication/results/sdid_drawwise_reference.json``.

Usage::

    python replication/scripts/sdid_drawwise_reference.py [n_draws] [n_jobs]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _paths import PAPER_ROOT  # noqa: E402

N_DRAWS = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
N_JOBS = int(sys.argv[2]) if len(sys.argv) > 2 else max(1, (os.cpu_count() or 2) - 1)
TRUTH = 3.0
N_CTRL, T0, T1 = 20, 12, 6
OUT = PAPER_ROOT / "replication" / "results" / "sdid_drawwise_reference.json"
R_SIDE = Path(__file__).resolve().parent / "sdid_drawwise_reference.R"


def _panel(seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)  # same stream as run_b1000.coverage_sdid
    n_t = T0 + T1
    f = rng.normal(size=n_t)
    units, times, ys = [], [], []
    for u in range(N_CTRL + 1):
        loading = rng.uniform(0.5, 1.5)
        ai = rng.normal()
        for t in range(n_t):
            base = ai + loading * f[t] + rng.normal(scale=0.5)
            eff = TRUTH if (u == 0 and t >= T0) else 0.0
            units.append(u)
            times.append(t)
            ys.append(base + eff)
    return pd.DataFrame({"u": units, "t": times, "y": ys})


def _fit(seed: int, tmp: str) -> tuple[float, float]:
    import statspai as sp

    df = _panel(seed)
    wide = df.pivot(index="u", columns="t", values="y")
    wide = wide.loc[list(range(1, N_CTRL + 1)) + [0]]  # treated unit last
    wide.to_csv(Path(tmp) / f"d{seed:04d}.csv", index=False, float_format="%.17g")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = sp.sdid(df, outcome="y", unit="u", time="t", treated_unit=0,
                    treatment_time=T0, se_method="placebo", n_reps=100, seed=seed)
    return float(r.estimate), float(r.se)


def _cover(est: np.ndarray, se: np.ndarray, crit: float) -> float:
    return float(np.mean(np.abs(est - TRUTH) <= crit * se))


def main() -> int:
    import statspai as sp
    from joblib import Parallel, delayed

    with tempfile.TemporaryDirectory() as tmp:
        py = np.asarray(Parallel(n_jobs=N_JOBS)(
            delayed(_fit)(s, tmp) for s in range(N_DRAWS)))
        subprocess.run(["Rscript", str(R_SIDE), tmp, str(N_DRAWS), str(N_JOBS)],
                       check=True)
        ref = pd.read_csv(Path(tmp) / "r.csv")
    est_py, se_py = py[:, 0], py[:, 1]
    est_r = ref["estimate"].to_numpy()
    z = float(stats.norm.ppf(0.975))
    t19 = float(stats.t.ppf(0.975, N_CTRL - 1))
    se_ex = ref["se_placebo_exhaustive"].to_numpy()
    out = {
        "design": "run_b1000.coverage_sdid: 1 treated, 20 controls, 12 + 6 periods",
        "n_draws": N_DRAWS,
        "truth": TRUTH,
        "statspai_version": sp.__version__,
        "synthdid_version": subprocess.run(
            ["Rscript", "-e", 'cat(as.character(packageVersion("synthdid")))'],
            capture_output=True, text=True, check=True).stdout.strip(),
        "max_abs_diff_estimate": float(np.max(np.abs(est_py - est_r))),
        "max_rel_diff_estimate": float(np.max(np.abs(est_py - est_r) / np.abs(est_r))),
        "coverage_statspai_placebo100_normal": _cover(est_py, se_py, z),
        "coverage_synthdid_placebo100_normal": _cover(
            est_r, ref["se_placebo100"].to_numpy(), z),
        "coverage_exhaustive_placebo_normal": _cover(est_r, se_ex, z),
        "coverage_exhaustive_placebo_t19": _cover(est_r, se_ex, t19),
        "mean_se_statspai_placebo100": float(se_py.mean()),
        "mean_se_synthdid_placebo100": float(ref["se_placebo100"].mean()),
        "mean_se_exhaustive": float(se_ex.mean()),
        "mc_sd_estimate": float(est_r.std(ddof=1)),
        "critical_values": {"normal": z, "t19": t19},
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

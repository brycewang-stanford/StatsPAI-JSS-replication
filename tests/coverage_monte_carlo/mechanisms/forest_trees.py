"""Forest coverage on the Track B design, by forest size.

Before 1.31 ``causal_question(design="causal_forest")`` reported a separate
cross-fit AIPW and the Track B "forest" row did not depend on the forest:
fitting 30, 300 or 2,000 trees gave bit-identical results (this script
found it). The ATE is now the fitted forest's own doubly-robust average, so
the forest size matters. This script reports coverage, bias, Monte Carlo SD,
mean SE and their ratio at 300 and 2,000 (grf default) trees on the Track B
DGP. (30 trees no longer runs: some rows get no out-of-bag prediction, and
the forest's AIPW refuses rather than guessing.) Writes
``results_forest_trees.json``.
"""

from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

import statspai as sp

HERE = Path(__file__).resolve().parent
TRUTH = 1.0
B = int(sys.argv[1]) if len(sys.argv) > 1 else 300


def run(trees: int) -> dict:
    est, se, cov = [], [], 0
    t0 = time.time()
    for seed in range(B):
        rng = np.random.default_rng(seed)  # same stream as run_b1000
        n = 500
        x1, x2 = rng.normal(size=n), rng.normal(size=n)
        p = 1 / (1 + np.exp(-(0.5 * x1)))
        d = rng.binomial(1, p)
        y = 0.5 + TRUTH * d + 0.7 * x1 + 0.3 * x2 + rng.normal(size=n)
        df = pd.DataFrame({"y": y, "d": d, "x1": x1, "x2": x2})
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            q = sp.causal_question(treatment="d", outcome="y", design="causal_forest",
                                   covariates=["x1", "x2"], data=df)
            r = q.estimate(n_estimators=trees, random_state=seed)
        est.append(r.estimate)
        se.append(r.se)
        cov += r.ci[0] <= TRUTH <= r.ci[1]
    est, se = np.asarray(est), np.asarray(se)
    return {"trees": trees, "B": B, "coverage": cov / B,
            "bias": float(est.mean() - TRUTH), "mc_sd": float(est.std(ddof=1)),
            "mean_se": float(se.mean()), "se_sd_ratio": float(se.mean() / est.std(ddof=1)),
            "wall_s": round(time.time() - t0, 1)}


def main() -> None:
    rows = [run(t) for t in (300, 2000)]
    for r in rows:
        print(r, flush=True)
    (HERE / "results_forest_trees.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

"""``sp.fast.feols`` CR1 coverage under the two small-sample conventions.

Adding a Track B row that runs the suite's HDFE member itself (rather than
``sp.panel``) found that the pre-1.31 default ``ssc="statspai"`` charged the
unit effects, which are nested in the unit clusters, in the CR1 factor. On
the Track B panel (50 units x 6 periods, unit and period effects absorbed,
CR1 by unit) that inflates the SE and over-covers; ``ssc="fixest"`` (the
setting the parity rows pin, default since 1.31.0) is calibrated. Same
draws as ``run_b1000.coverage_fast_feols``. Writes ``results_feols_ssc.json``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t as t_dist

import statspai as sp

HERE = Path(__file__).resolve().parent
TRUTH = 1.5
B = int(sys.argv[1]) if len(sys.argv) > 1 else 1000


def run(ssc: str) -> dict:
    est, se, cov = [], [], 0
    for seed in range(B):
        rng = np.random.default_rng(seed)
        rows = []
        for i in range(50):
            ai = rng.normal()
            for t in range(6):
                d = rng.binomial(1, 0.5)
                y = ai + 0.3 * t + TRUTH * d + rng.normal(scale=0.8)
                rows.append({"i": i, "t": t, "d": d, "y": y})
        df = pd.DataFrame(rows)
        r = sp.fast.feols("y ~ d | i + t", data=df, vcov="cr1", cluster="i", ssc=ssc)
        b, s = float(r.coef()["d"]), float(r.se()["d"])
        crit = float(t_dist.ppf(0.975, 49))
        cov += int(b - crit * s <= TRUTH <= b + crit * s)
        est.append(b)
        se.append(s)
    est, se = np.asarray(est), np.asarray(se)
    mc_sd = float(np.std(est, ddof=1))
    return {
        "ssc": ssc,
        "B": B,
        "coverage": cov / B,
        "bias": float(est.mean() - TRUTH),
        "mc_sd": mc_sd,
        "mean_se": float(se.mean()),
        "se_sd_ratio": float(se.mean() / mc_sd),
    }


if __name__ == "__main__":
    out = [run("fixest"), run("statspai")]
    for row in out:
        print(row)
    (HERE / "results_feols_ssc.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )

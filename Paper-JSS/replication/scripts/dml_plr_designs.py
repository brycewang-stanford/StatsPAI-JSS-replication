#!/usr/bin/env python3
"""Is the DML PLR default-learner under-coverage specific to one design?

Track B's PLR row covers 0.883 at n = 500 with the default gradient-boosting
nuisances, and ``dml_plr_stacking_mechanism.py`` shows that short-stacking
over the default roster of ``sp.dml_model_averaging`` covers 0.948 on that
design. One design cannot say whether the default learner is generally
miscalibrated or was unlucky. This script repeats the comparison on six
designs that differ in what a nuisance learner has to get right: a smooth
low-dimensional surface (the Track B design), exactly linear nuisances,
sparse linear nuisances with fifty correlated covariates, logistic-type
nuisances with twenty correlated covariates, step functions and
interactions (the shape boosted trees fit best), and a larger
heteroskedastic sample.

Every draw fits ``sp.dml(model="plr")`` with its default learner and
``sp.dml_model_averaging`` with its default roster under short-stacking,
on the same data, folds count and seed. Run against the release the paper
describes. Writes ``replication/results/dml_plr_designs.json``.

Usage::

    python replication/scripts/dml_plr_designs.py [B] [n_jobs]
"""

from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _paths import PAPER_ROOT  # noqa: E402

B = int(sys.argv[1]) if len(sys.argv) > 1 else 500
N_JOBS = int(sys.argv[2]) if len(sys.argv) > 2 else -2  # all cores but one
OUT = PAPER_ROOT / "replication" / "results" / "dml_plr_designs.json"


def _expit(z):
    return 1.0 / (1.0 + np.exp(-z))


def _ar_cov(p: int, rho: float) -> np.ndarray:
    idx = np.arange(p)
    return rho ** np.abs(idx[:, None] - idx[None, :])


def _smooth2(rng, n):
    x = rng.normal(size=(n, 2))
    d = 0.5 * x[:, 0] + 0.3 * np.sin(2 * x[:, 1]) + rng.normal(size=n)
    y = 1.0 * d + x[:, 0] + 0.5 * x[:, 1] ** 2 + rng.normal(size=n)
    return x, d, y


def _linear10(rng, n):
    x = rng.normal(size=(n, 10))
    d = 0.5 * x[:, 0] + 0.3 * x[:, 1] + 0.2 * x[:, 2] + rng.normal(size=n)
    y = 1.0 * d + x[:, 0] + 0.5 * x[:, 1] + 0.25 * x[:, 2] + rng.normal(size=n)
    return x, d, y


def _sparse50(rng, n):
    p = 50
    x = rng.multivariate_normal(np.zeros(p), _ar_cov(p, 0.5), size=n)
    beta = 1.0 / np.arange(1, p + 1) ** 2
    d = x @ beta + rng.normal(size=n)
    y = 1.0 * d + x @ beta[::-1] + rng.normal(size=n)
    return x, d, y


def _logistic20(rng, n):
    p = 20
    x = rng.multivariate_normal(np.zeros(p), _ar_cov(p, 0.7), size=n)
    d = x[:, 0] + 0.25 * _expit(x[:, 2]) + rng.normal(size=n)
    y = 1.0 * d + _expit(x[:, 0]) + 0.25 * x[:, 2] + rng.normal(size=n)
    return x, d, y


def _steps5(rng, n):
    x = rng.normal(size=(n, 5))
    d = (0.8 * (x[:, 0] > 0) - 0.5 * (x[:, 1] > 0.5)
         + 0.4 * (x[:, 0] > 0) * (x[:, 2] > 0) + rng.normal(size=n))
    y = (1.0 * d + (x[:, 1] > 0) * x[:, 0] + 0.5 * (x[:, 3] > 1)
         + rng.normal(size=n))
    return x, d, y


def _hetero5(rng, n):
    x = rng.normal(size=(n, 5))
    d = (np.sin(x[:, 0]) + 0.5 * x[:, 1] * x[:, 2]
         + (0.5 + 0.5 * np.abs(x[:, 0])) * rng.normal(size=n))
    y = (1.0 * d + np.cos(x[:, 1]) + x[:, 0] * x[:, 3]
         + (1.0 + 0.5 * np.abs(x[:, 1])) * rng.normal(size=n))
    return x, d, y


DESIGNS = {
    "smooth2": (_smooth2, 500, "Track B design: smooth surface, 2 covariates"),
    "linear10": (_linear10, 500, "exactly linear nuisances, 10 covariates"),
    "sparse50": (_sparse50, 500, "sparse linear nuisances, 50 correlated covariates"),
    "logistic20": (_logistic20, 500, "logistic-type nuisances, 20 correlated covariates"),
    "steps5": (_steps5, 1000, "step functions and interactions, 5 covariates"),
    "hetero5": (_hetero5, 2000, "smooth interactions, heteroskedastic errors, 5 covariates"),
}
TRUTH = 1.0


def _draw(name: str, seed: int) -> dict:
    import statspai as sp

    gen, n, _ = DESIGNS[name]
    rng = np.random.default_rng(seed)
    x, d, y = gen(rng, n)
    cols = [f"x{j + 1}" for j in range(x.shape[1])]
    df = pd.DataFrame(x, columns=cols)
    df["d"], df["y"] = d, y
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        base = sp.dml(df, y="y", d="d", X=cols, model="plr", n_folds=5,
                      random_state=seed)
        stack = sp.dml_model_averaging(df, y="y", treat="d", covariates=cols,
                                       n_folds=5, seed=seed,
                                       weight_rule="short_stacking")
    return {
        "seed": seed,
        "default_est": float(base.estimate), "default_se": float(base.se),
        "default_ci": [float(base.ci[0]), float(base.ci[1])],
        "stack_est": float(stack.estimate), "stack_se": float(stack.se),
        "stack_ci": [float(stack.ci[0]), float(stack.ci[1])],
    }


def _summary(rows: list[dict], key: str) -> dict:
    est = np.array([r[f"{key}_est"] for r in rows])
    se = np.array([r[f"{key}_se"] for r in rows])
    cover = np.mean([r[f"{key}_ci"][0] <= TRUTH <= r[f"{key}_ci"][1] for r in rows])
    sd = est.std(ddof=1)
    return {
        "coverage": float(cover), "bias": float(est.mean() - TRUTH),
        "mc_sd": float(sd), "mean_se": float(se.mean()),
        "se_sd_ratio": float(se.mean() / sd),
        "bias_over_sd": float((est.mean() - TRUTH) / sd),
        "rmse": float(np.sqrt(np.mean((est - TRUTH) ** 2))),
    }


def main() -> int:
    import statspai as sp
    from joblib import Parallel, delayed

    out = {"statspai_version": sp.__version__, "B": B, "truth": TRUTH,
           "folds": 5, "designs": {}}
    if OUT.exists():
        prior = json.loads(OUT.read_text(encoding="utf-8"))
        if prior.get("B") == B and prior.get("statspai_version") == sp.__version__:
            out["designs"] = prior["designs"]
    for name, (_, n, label) in DESIGNS.items():
        if name in out["designs"]:
            continue
        t0 = time.time()
        rows = Parallel(n_jobs=N_JOBS)(delayed(_draw)(name, s) for s in range(B))
        gap = np.array([(r["stack_est"] - r["default_est"]) / r["default_se"]
                        for r in rows])
        out["designs"][name] = {
            "label": label, "n": n,
            "default_learner": _summary(rows, "default"),
            "short_stacking_default_roster": _summary(rows, "stack"),
            "share_abs_gap_gt_half_default_se": float(np.mean(np.abs(gap) > 0.5)),
            "wall_s": round(time.time() - t0, 1),
            "draws": rows,
        }
        OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
        print(name, json.dumps({k: v for k, v in out["designs"][name].items()
                                if k != "draws"}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

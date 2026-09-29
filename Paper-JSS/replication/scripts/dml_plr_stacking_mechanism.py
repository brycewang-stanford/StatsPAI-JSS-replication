#!/usr/bin/env python3
"""Does learner stacking repair the DML PLR under-coverage of Track B?

Track B's PLR row covers 0.883 at n = 500 with the default gradient-boosting
nuisances, and the mechanism study in StatsPAI
(``tests/coverage_monte_carlo/mechanisms/dml_plr_learners.py``) traces it
to first-stage regularisation bias: oracle nuisances cover 0.952, a random
forest 0.940, a spline Lasso 0.938. That study says what goes wrong; this
one asks what a user can do about it with the package as released.

On the same DGP, seeds, sample size, and fold count, it runs
``sp.dml_model_averaging`` with its *default* candidate roster (Lasso,
Ridge, random forest, gradient boosting) under short-stacking
(Ahrens et al. 2025) -- i.e. what a user gets by calling it with no
learner choices of their own. It also records, per draw, the gap between
the stacked and the default-learner estimate in units of the default
standard error, so the paper can say whether comparing the two within a
single data set flags the problem.

The DGP is imported from the StatsPAI mechanism script, so the two studies
cannot drift apart. Run against the release the paper describes
(``STATSPAI_ROOT`` / ``PYTHONPATH`` at tag v1.32.0). Writes
``replication/results/dml_plr_stacking_mechanism.json``.

Usage::

    python replication/scripts/dml_plr_stacking_mechanism.py [B] [n_jobs]
"""

from __future__ import annotations

import importlib.util
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

from _paths import PAPER_ROOT, statspai_root  # noqa: E402

B = int(sys.argv[1]) if len(sys.argv) > 1 else 500
N_JOBS = int(sys.argv[2]) if len(sys.argv) > 2 else 1
N = 500
OUT = PAPER_ROOT / "replication" / "results" / "dml_plr_stacking_mechanism.json"
MECHANISM = (
    statspai_root() / "tests" / "coverage_monte_carlo" / "mechanisms" / "dml_plr_learners.py"
)


def _dgp_module():
    spec = importlib.util.spec_from_file_location("_dml_plr_learners", MECHANISM)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _draw(seed: int) -> dict:
    import statspai as sp

    mech = _dgp_module()
    rng = np.random.default_rng(seed)
    x1, x2 = rng.normal(size=N), rng.normal(size=N)
    d = mech._e_d(x1, x2) + rng.normal(size=N)
    y = mech.TRUTH * d + x1 + 0.5 * x2**2 + rng.normal(size=N)
    df = pd.DataFrame({"y": y, "d": d, "x1": x1, "x2": x2})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        base = sp.dml(df, y="y", d="d", X=["x1", "x2"], model="plr", n_folds=5,
                      random_state=seed)
        stack = sp.dml_model_averaging(df, y="y", treat="d", covariates=["x1", "x2"],
                                       n_folds=5, seed=seed,
                                       weight_rule="short_stacking")
    return {
        "seed": seed,
        "default_est": float(base.estimate), "default_se": float(base.se),
        "default_ci": [float(base.ci[0]), float(base.ci[1])],
        "stack_est": float(stack.estimate), "stack_se": float(stack.se),
        "stack_ci": [float(stack.ci[0]), float(stack.ci[1])],
    }


def _summary(rows: list[dict], key: str, truth: float) -> dict:
    est = np.array([r[f"{key}_est"] for r in rows])
    se = np.array([r[f"{key}_se"] for r in rows])
    cover = np.mean([r[f"{key}_ci"][0] <= truth <= r[f"{key}_ci"][1] for r in rows])
    sd = est.std(ddof=1)
    return {
        "coverage": float(cover), "bias": float(est.mean() - truth),
        "mc_sd": float(sd), "mean_se": float(se.mean()),
        "se_sd_ratio": float(se.mean() / sd),
        "bias_over_sd": float((est.mean() - truth) / sd),
    }


def main() -> int:
    import statspai as sp

    truth = _dgp_module().TRUTH
    t0 = time.time()
    if N_JOBS > 1:
        from joblib import Parallel, delayed

        rows = Parallel(n_jobs=N_JOBS)(delayed(_draw)(s) for s in range(B))
    else:
        rows = [_draw(s) for s in range(B)]
    gap = np.array([(r["stack_est"] - r["default_est"]) / r["default_se"] for r in rows])
    payload = {
        "design": "dml_plr_learners.py DGP, n = 500, 5 folds, seeds 0..B-1",
        "statspai_version": sp.__version__,
        "B": B,
        "n": N,
        "truth": truth,
        "default_learner": _summary(rows, "default", truth),
        "short_stacking_default_roster": _summary(rows, "stack", truth),
        "stack_minus_default_over_default_se": {
            "mean": float(gap.mean()),
            "median": float(np.median(gap)),
            "share_abs_gt_0_5": float(np.mean(np.abs(gap) > 0.5)),
        },
        "wall_s": round(time.time() - t0, 1),
        "draws": rows,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in payload.items() if k != "draws"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

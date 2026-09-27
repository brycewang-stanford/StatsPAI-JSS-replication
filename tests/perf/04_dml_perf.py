"""Track C performance -- DML PLR.

Task (both sides, same process): partially linear DML with linear-regression
nuisance learners and five folds, public-workflow construction included, on
the shared input ``data/04_dml_<N>.csv``. StatsPAI ``sp.dml(model='plr')``
against ``doubleml-for-py``'s ``DoubleMLPLR``. With cheap learners the
timing isolates wrapper and cross-fitting overhead; timings are a few
milliseconds, so 15 repetitions are taken and the IQR is reported with the
median. Requires ``doubleml`` (``requirements-jss-recompute.txt``).
"""

from __future__ import annotations

import doubleml as dml_ref
import numpy as np
from _common import TimingResult, time_repeat, write_results
from _data import SIZES, load
from sklearn.linear_model import LinearRegression

import statspai as sp

EST = "04_dml"
N_REPS = 15
X = [f"x{i + 1}" for i in range(5)]


def main() -> None:
    rows: list[TimingResult] = []
    reference_rows: list[TimingResult] = []
    for n in SIZES[EST]:
        df, digest = load(EST, n)

        def run_sp():
            return sp.dml(
                data=df,
                y="y",
                d="d",
                X=X,
                model="plr",
                model_y=LinearRegression(),
                model_d=LinearRegression(),
            )

        def run_doubleml_python():
            np.random.seed(42)
            data = dml_ref.DoubleMLData(df, y_col="y", d_cols="d", x_cols=X)
            model = dml_ref.DoubleMLPLR(
                data, ml_l=LinearRegression(), ml_m=LinearRegression(), n_folds=5
            )
            model.fit()
            return model

        fit, ref = run_sp(), run_doubleml_python()
        common = {"data_sha256": digest, "task": "PLR, linear learners, 5 folds"}
        for side, fn, out, est, se in (
            ("py", run_sp, rows, float(fit.estimate), float(fit.se)),
            (
                "doubleml_py",
                run_doubleml_python,
                reference_rows,
                float(ref.coef[0]),
                float(ref.se[0]),
            ),
        ):
            med, iqr, mn, mx, peak = time_repeat(fn, n_reps=N_REPS, warmup=1)
            out.append(
                TimingResult(
                    estimator=EST,
                    side=side,
                    n=n,
                    n_reps=N_REPS,
                    median_time_s=med,
                    iqr_time_s=iqr,
                    min_time_s=mn,
                    max_time_s=mx,
                    peak_mem_mb=peak,
                    # Different random folds on each side: the estimates
                    # agree to sampling-split noise, not to machine precision.
                    extra={**common, "estimate": est, "se": se},
                )
            )
        print(
            f"  N={n:>6}  sp={rows[-1].median_time_s:.4f}s  "
            f"doubleml={reference_rows[-1].median_time_s:.4f}s"
        )
    write_results(EST, "py", rows)
    write_results(EST, "doubleml_py", reference_rows)


if __name__ == "__main__":
    main()

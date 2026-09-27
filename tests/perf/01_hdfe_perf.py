"""Track C performance benchmark -- HDFE 2-way FE.

Task (both sides): OLS of y on x1, x2 with firm and year effects absorbed,
iid standard errors, on the shared input ``data/01_hdfe_<N>.csv``
(``_data.py``), one thread. StatsPAI: ``sp.fast.feols``; reference:
``fixest::feols`` (``01_hdfe_perf.R``). The coefficient on x1 and its SE
are recorded outside the timed call so ``compare_perf.py`` can check that
both sides solved the same problem.
"""

from __future__ import annotations

from _common import TimingResult, time_repeat, write_results
from _data import SIZES, load

import statspai as sp

EST = "01_hdfe"
N_REPS = 5
FORMULA = "y ~ x1 + x2 | firm + year"


def main() -> None:
    rows: list[TimingResult] = []
    for n in SIZES[EST]:
        df, digest = load(EST, n)

        def run_sp():
            return sp.fast.feols(FORMULA, data=df, vcov="iid")

        fit = run_sp()
        med, iqr, mn, mx, peak = time_repeat(run_sp, n_reps=N_REPS, warmup=1)
        rows.append(
            TimingResult(
                estimator=EST,
                side="py",
                n=n,
                n_reps=N_REPS,
                median_time_s=med,
                iqr_time_s=iqr,
                min_time_s=mn,
                max_time_s=mx,
                peak_mem_mb=peak,
                extra={
                    "data_sha256": digest,
                    "task": "OLS, two absorbed FE (firm, year), iid SE",
                    "estimate": float(fit.coef()["x1"]),
                    "se": float(fit.se()["x1"]),
                },
            )
        )
        print(f"  N={n:>9}  median={med:.3f}s  iqr={iqr:.3f}s")
    write_results(EST, "py", rows)


if __name__ == "__main__":
    main()

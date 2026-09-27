"""Track C performance -- Callaway-Sant'Anna staggered DiD.

Task (both sides): group-time ATTs by outcome regression against the
never-treated, analytic SEs, the joint pre-trend test, and the simple and
dynamic aggregations, on the shared input ``data/02_csdid_<units>.csv``
(periods 1..5, cohorts 2, 3, 4; ``_data.py``), one thread. StatsPAI's
``sp.callaway_santanna`` returns all four in one call; the reference runs
``did::att_gt`` (which computes the pre-test) and two ``did::aggte`` calls
(``02_csdid_perf.R``). The simple ATT and its SE are recorded outside the
timed call.
"""

from __future__ import annotations

from _common import TimingResult, time_repeat, write_results
from _data import CSDID_T, SIZES, load

import statspai as sp

EST = "02_csdid"
N_REPS = 3


def main() -> None:
    rows: list[TimingResult] = []
    for n_units in SIZES[EST]:
        df, digest = load(EST, n_units)

        def run_sp():
            return sp.callaway_santanna(
                df,
                y="y",
                g="first_treat",
                t="year",
                i="unit",
                estimator="reg",
                control_group="nevertreated",
            )

        fit = run_sp()
        assert fit.model_info.get("event_study") is not None
        med, iqr, mn, mx, peak = time_repeat(run_sp, n_reps=N_REPS, warmup=1)
        rows.append(
            TimingResult(
                estimator=EST,
                side="py",
                n=int(n_units * CSDID_T),
                n_reps=N_REPS,
                median_time_s=med,
                iqr_time_s=iqr,
                min_time_s=mn,
                max_time_s=mx,
                peak_mem_mb=peak,
                extra={
                    "n_units": n_units,
                    "T": CSDID_T,
                    "data_sha256": digest,
                    "task": "ATT(g,t) reg/never-treated, analytic SE, pre-test, "
                    "simple + dynamic aggregation",
                    "estimate": float(fit.estimate),
                    "se": float(fit.se),
                },
            )
        )
        print(f"  N_units={n_units:>6}  median={med:.3f}s")
    write_results(EST, "py", rows)


if __name__ == "__main__":
    main()

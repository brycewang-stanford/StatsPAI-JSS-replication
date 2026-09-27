"""Track C performance -- Classical SCM.

Task (both sides): the Abadie-Diamond-Hainmueller specification -- one
outcome special predictor per pre-treatment year (1970-1984) and a nested
search over V -- solving for donor weights and the post-treatment gap, with
no placebo loop, on the shared input ``data/03_scm_<donors>.csv``.
StatsPAI: ``sp.synth(method='classic', special_predictors=..., v_method=
'nested', placebo=False)``; reference: ``Synth::dataprep`` +
``Synth::synth`` with BFGS (``03_scm_perf.R``).

The two solvers are not the same algorithm: Synth runs one outer search
from its regression-based V; StatsPAI runs six starts (equal, regression,
four random) with Nelder-Mead outside and, because donors outnumber
pre-periods here, SLSQP inside. Both are timed at their defaults for this
specification; ``starts`` is recorded.

The package *default* call (``sp.synth(method='classic')``: outcome-path
predictors, V = I, in-space placebos over every donor) is a different task
with no counterpart in the reference; its cost and the share taken by the
placebo loop are recorded in ``extra`` as ``default_workflow_s`` and
``default_no_placebo_s``.
"""

from __future__ import annotations

from _common import TimingResult, time_repeat, write_results
from _data import SCM_T, SCM_T0, SIZES, load

import statspai as sp

EST = "03_scm"
N_REPS = 3
BASE = dict(
    outcome="y",
    unit="unit_id",
    time="year",
    treated_unit=1,
    treatment_time=SCM_T0,
    method="classic",
)
SPECIAL = [("y", yr, "mean") for yr in range(1970, SCM_T0)]


def main() -> None:
    rows: list[TimingResult] = []
    for n_donors in SIZES[EST]:
        df, digest = load(EST, n_donors)

        def run_adh():
            return sp.synth(
                df, **BASE, special_predictors=SPECIAL, v_method="nested", placebo=False
            )

        fit = run_adh()
        med, iqr, mn, mx, peak = time_repeat(run_adh, n_reps=N_REPS, warmup=0)
        d_med = time_repeat(lambda: sp.synth(df, **BASE), n_reps=N_REPS, warmup=1)[0]
        dn_med = time_repeat(
            lambda: sp.synth(df, **BASE, placebo=False), n_reps=N_REPS, warmup=1
        )[0]
        rows.append(
            TimingResult(
                estimator=EST,
                side="py",
                n=n_donors,
                n_reps=N_REPS,
                median_time_s=med,
                iqr_time_s=iqr,
                min_time_s=mn,
                max_time_s=mx,
                peak_mem_mb=peak,
                extra={
                    "n_donors": n_donors,
                    "T": SCM_T,
                    "data_sha256": digest,
                    "task": "ADH special predictors (each pre-year), nested V, "
                    "no placebos",
                    "estimate": float(fit.estimate),
                    "loss_v": float(fit.model_info["solver_best_loss"]),
                    "starts": int(fit.model_info["n_starts"]),
                    "default_workflow_s": d_med,
                    "default_no_placebo_s": dn_med,
                },
            )
        )
        print(
            f"  n_donors={n_donors:>4}  ADH={med:.2f}s  default={d_med:.3f}s  "
            f"default w/o placebos={dn_med:.3f}s"
        )
    write_results(EST, "py", rows)


if __name__ == "__main__":
    main()

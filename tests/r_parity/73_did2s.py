"""StatsPAI Gardner two-stage DiD parity (Python side) -- Module 73.

Runs ``sp.gardner_did`` on the mpdta replica; the companion R script runs
``did2s::did2s`` with the same two-way FE first stage on the same CSV, and
the Stata do-file runs Butts' ``did2s`` port.

Tolerance: rel < 1e-6 on the point estimate and on the SE. The default
``vce='analytic'`` is the did2s corrected clustered variance (Gardner 2022):
the Stage-2 sandwich is built from the two-stage influence function, so the
Stage-1 fixed-effect estimation error is propagated exactly as the two
references do, with no small-sample cluster factor. Before this correction
the default clustered the stage-2 residuals only and landed ~26% low; that
legacy number is still reachable as ``vce='stage2'`` and is emitted here as
the ``static_ATT_stage2_se`` diagnostic row (no R/Stata counterpart, not
joined by compare.py) so the size of the old gap stays on record.
"""

from __future__ import annotations

import warnings

import statspai as sp

from _common import ParityRecord, dump_csv, write_results

MODULE = "73_did2s"


def main() -> None:
    df = sp.datasets.mpdta()
    dump_csv(df, MODULE)

    fit = sp.gardner_did(
        df,
        y="lemp",
        group="countyreal",
        time="year",
        first_treat="first_treat",
    )
    with warnings.catch_warnings():
        # vce='stage2' warns that it understates; that is the legacy
        # convention this diagnostic row exists to record.
        warnings.simplefilter("ignore")
        legacy = sp.gardner_did(
            df,
            y="lemp",
            group="countyreal",
            time="year",
            first_treat="first_treat",
            vce="stage2",
        )

    rows: list[ParityRecord] = [
        ParityRecord(
            module=MODULE,
            side="py",
            statistic="static_ATT",
            estimate=float(fit.estimate),
            se=float(fit.se),
            ci_lo=float(fit.ci[0]) if fit.ci is not None else None,
            ci_hi=float(fit.ci[1]) if fit.ci is not None else None,
            n=int(len(df)),
        ),
        ParityRecord(
            module=MODULE,
            side="py",
            statistic="static_ATT_stage2_se",
            estimate=float(legacy.estimate),
            se=float(legacy.se),
            n=int(len(df)),
        ),
    ]

    write_results(
        MODULE,
        "py",
        rows,
        extra={
            "estimator": "gardner_did",
            "vce": "analytic (did2s corrected two-stage variance) + stage2 diagnostic",
        },
    )


if __name__ == "__main__":
    main()

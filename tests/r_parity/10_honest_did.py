"""StatsPAI Honest-DiD parity (Python side) -- Module 10.

Runs the **native** ``sp.honest_did(method="smoothness")`` fixed-length
confidence interval (the Rambachan-Roth FLCI under ``Delta^SD(M)``, solved
in Python by ``statspai.did._flci``) on a hand-crafted event study, at five
values of ``M``, and compares it with R ``HonestDiD`` on the same inputs.

Until 1.31 this module called ``backend="honestdid"``, which hands the
computation to the R package itself: the row then checked the wrapper, not
an independent Python algorithm (comparing an R bridge with R is circular).
It now exercises the native solver, and the R side supplies three
references so each gap has a named mechanism:

``ci_{lower,upper}_M_*``  (headline for ``M > 0``)
    ``HonestDiD::createSensitivityResults(method = "FLCI")`` with its
    internal ``.qfoldednormal`` replaced by the exact folded-normal
    quantile -- the like-for-like comparison. The Stata ``honestdid`` port
    joins these rows too.
``shipped_ci_{lower,upper}_M_*``
    HonestDiD as shipped. It evaluates the folded-normal quantile by
    simulation (1e6 draws, seed 0), so it sits ~3e-4 from the exact
    quantile: a documented difference in the computed quantity, displayed
    but not a parity row.
``analytic_ci_{lower,upper}_M_0``  (headline)
    At ``M = 0`` the violation is exactly linear, the worst-case bias is
    zero and the FLCI centre is the GLS linear extrapolation
    ``beta_post[0] - s_hat`` (``s_hat`` = GLS slope of the pre-period
    coefficients on relative time), with half-length ``z_{0.975}`` times its
    standard deviation. R computes this closed form with base linear
    algebra, independently of both implementations. HonestDiD's cone solver
    returns this interval to ~6e-6; the native solver to ~2e-9. The plain
    ``ci_*_M_0`` rows are therefore displayed but are not the headline.

The event study carries an explicit covariance (``event_study_vcov``):
the native FLCI deliberately refuses to fabricate a joint covariance from
standard errors alone, and the reference uses ``diag(se^2)``.

The closed-form ``breakdown_m`` primitive is independently pinned in
tests/external_parity/test_honest_did_paper_parity.py, and the FLCI
half-length against ``HonestDiD::findOptimalFLCI`` (exact quantile) at 1e-8
on a correlated covariance in tests/reference_parity/test_did_synth_R_parity.py.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statspai as sp
from statspai.core.results import CausalResult

from _common import ParityRecord, write_results

MODULE = "10_honest_did"
M_GRID = [0.0, 0.05, 0.1, 0.2, 0.5]


def main() -> None:
    # Hand-crafted event study so the test is deterministic and the
    # R side can mirror the inputs without an intermediate CSV. Pre-period
    # relative_time -3, -2, -1; post-period 0, 1, 2.
    es = pd.DataFrame(
        {
            "relative_time": [-3, -2, -1, 0, 1, 2],
            "att": [0.01, -0.02, 0.0, 0.5, 0.4, 0.3],
            "se": [0.05, 0.05, 0.05, 0.10, 0.10, 0.10],
        }
    )
    vcov = pd.DataFrame(
        np.diag(es["se"].to_numpy() ** 2),
        index=es["relative_time"],
        columns=es["relative_time"],
    )
    res = CausalResult(
        method="ParityHonestDiDInput",
        estimand="ATT(0)",
        estimate=0.5,
        se=0.10,
        pvalue=0.0,
        ci=(0.30, 0.70),
        alpha=0.05,
        n_obs=1000,
        model_info={"event_study": es, "event_study_vcov": vcov},
    )

    rows: list[ParityRecord] = [
        ParityRecord(
            module=MODULE,
            side="py",
            statistic="breakdown_m_e0",
            estimate=float(sp.breakdown_m(res, e=0, method="smoothness", alpha=0.05)),
            n=int(res.n_obs),
        )
    ]

    table = sp.honest_did(res, e=0, m_grid=M_GRID, method="smoothness")
    if table.attrs.get("interval") != "flci":
        raise RuntimeError(
            "native honest_did fell back to the worst-case-bias interval; "
            "module 10 must exercise the native FLCI"
        )
    for _, row in table.iterrows():
        m = float(row["M"])
        prefixes = ["", "shipped_"] + (["analytic_"] if m == 0.0 else [])
        for prefix in prefixes:
            for side, col in (("lower", "ci_lower"), ("upper", "ci_upper")):
                rows.append(
                    ParityRecord(
                        module=MODULE,
                        side="py",
                        statistic=f"{prefix}ci_{side}_M_{m:g}",
                        estimate=float(row[col]),
                        n=int(res.n_obs),
                    )
                )

    write_results(
        MODULE,
        "py",
        rows,
        extra={
            "method": "smoothness",
            "backend": "native",
            "interval": "flci",
            "alpha": 0.05,
            "M_grid": M_GRID,
            "implementation": (
                "native Python FLCI (statspai.did._flci.flci_delta_sd) with "
                "the exact folded-normal quantile; no R call. The same "
                "native values are emitted under three statistic prefixes so "
                "they join the three R references (HonestDiD with the exact "
                "quantile, HonestDiD as shipped, closed form at M = 0)."
            ),
        },
    )


if __name__ == "__main__":
    main()

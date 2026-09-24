"""StatsPAI Honest-DiD relative-magnitudes parity (Python side).
Module 21.

Same hand-crafted event study as Module 10 but uses the relative-
magnitudes restriction ``Delta^RM(Mbar)`` rather than smoothness. The
companion 21_honest_relmags.R uses
HonestDiD::createSensitivityResults_relativeMagnitudes(method = "Conditional").

The Python side runs the **native** confidence set
(``statspai.did._arp``: the Andrews-Roth-Pakes conditional test inverted
over the union of ``Delta^RM`` pieces, on HonestDiD's 1,000-point grid);
no R call. Until 1.31 this module called ``backend="honestdid"``, which
compared R HonestDiD with itself. The Conditional method is used because it
involves no simulation, so a correct port agrees *exactly*: both sides
report the smallest and largest accepted grid point. Tolerance: abs < 1e-6
on each CI bound (observed: identical grid points, ~4e-16).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statspai as sp
from statspai.core.results import CausalResult

from _common import ParityRecord, write_results


MODULE = "21_honest_relmags"
MBAR_GRID = [0.0, 0.5, 1.0, 1.5, 2.0]


def main() -> None:
    es = pd.DataFrame({
        "relative_time": [-3, -2, -1, 0, 1, 2],
        "att": [0.01, -0.02, 0.0, 0.5, 0.4, 0.3],
        "se":  [0.05, 0.05, 0.05, 0.10, 0.10, 0.10],
    })
    # The reference is handed diag(se^2); the native set needs the same
    # covariance explicitly (it will not fabricate one from SEs alone).
    vcov = pd.DataFrame(np.diag(es["se"].to_numpy() ** 2),
                        index=es["relative_time"], columns=es["relative_time"])
    res = CausalResult(
        method="ParityHonestDiDRelMags",
        estimand="ATT(0)",
        estimate=0.5, se=0.10, pvalue=0.0,
        ci=(0.30, 0.70), alpha=0.05, n_obs=1000,
        model_info={"event_study": es, "event_study_vcov": vcov},
    )

    rows: list[ParityRecord] = []
    table = sp.honest_did(res, e=0, m_grid=MBAR_GRID,
                          method="relative_magnitude",
                          honestdid_method="Conditional")
    if table.attrs.get("interval") != "arp_conditional":
        raise RuntimeError(
            "native honest_did fell back to the worst-case-bias interval; "
            "module 21 must exercise the native ARP conditional set"
        )
    for _, row in table.iterrows():
        m = float(row["M"])
        rows.append(
            ParityRecord(
                module=MODULE, side="py",
                statistic=f"ci_lower_Mbar_{m:g}",
                estimate=float(row["ci_lower"]), n=int(res.n_obs),
            )
        )
        rows.append(
            ParityRecord(
                module=MODULE, side="py",
                statistic=f"ci_upper_Mbar_{m:g}",
                estimate=float(row["ci_upper"]), n=int(res.n_obs),
            )
        )

    write_results(
        MODULE, "py", rows,
        extra={
            "method": "relative_magnitude",
            "honestdid_method": "Conditional",
            "backend": "native",
            "interval": "arp_conditional",
            "Mbar_grid": MBAR_GRID, "alpha": 0.05,
            "implementation": (
                "native Python ARP conditional confidence set "
                "(statspai.did._arp.rm_confidence_set) on HonestDiD's default "
                "1,000-point grid; no R call."
            ),
        },
    )


if __name__ == "__main__":
    main()

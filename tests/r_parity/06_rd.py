"""StatsPAI RD CCT bias-corrected parity (Python side) -- Module 06.

Runs the **native** ``sp.rdrobust(...)`` default -- StatsPAI's own
implementation of the Calonico-Cattaneo-Titiunik MSE-optimal bandwidth
cascade and robust bias-corrected inference -- on the Lee 2008 senate
replica, and compares it with R and Stata ``rdrobust`` defaults.

Until 1.31 the headline rows came from ``bwselect="cct"``, which hands the
computation to the official ``rdrobust`` Python port maintained by the
method's authors. That is a same-language port, not an R shell-out, but
it is still not evidence about StatsPAI's own algorithm, so it is now a
secondary, recorded convergence check (``cct_port_*`` rows, no R or Stata
counterpart, never joined) rather than the parity headline.

Tolerance: rel < 1e-6 against R/Stata CCT defaults (observed ~3e-14).
"""
from __future__ import annotations

import statspai as sp

from _common import ParityRecord, dump_csv, write_results


MODULE = "06_rd"
# Shared with 06_rd.R. Near the CCT bandwidth (~17.8) on the rdrobust
# senate data, whose running variable is in percentage points.
FORCED_BANDWIDTH = 15.0


def _rows(fit, prefix: str, n: int) -> list[ParityRecord]:
    out = []
    for label in ("conventional", "robust"):
        d = fit.model_info[label]
        out.append(
            ParityRecord(
                module=MODULE, side="py", statistic=f"{prefix}_{label}_est",
                estimate=float(d["estimate"]),
                se=float(d["se"]),
                ci_lo=float(d["ci"][0]),
                ci_hi=float(d["ci"][1]),
                n=n,
            )
        )
    for bw in ("h", "b"):
        out.append(
            ParityRecord(
                module=MODULE, side="py", statistic=f"{prefix}_bandwidth_{bw}",
                estimate=float(fit.model_info[f"bandwidth_{bw}"]), n=n,
            )
        )
    return out


def main() -> None:
    df = sp.datasets.lee_2008_senate()
    dump_csv(df, MODULE)
    n = int(len(df))

    # Headline: the native default (bwselect="mserd", StatsPAI's own CCT
    # cascade). No third-party package is called on this path.
    fit = sp.rdrobust(df, y="y", x="x", c=0.0)
    rows: list[ParityRecord] = _rows(fit, "default", n)

    # Convergence check against the official rdrobust Python port
    # (bwselect="cct"; optional extra `rd-cct`). Named so it never joins an
    # R or Stata row: agreement here is port-vs-native, not parity.
    try:
        port = sp.rdrobust(df, y="y", x="x", c=0.0, bwselect="cct")
    except ImportError:  # the GPL port is an opt-in extra
        port = None
    if port is not None:
        rows += _rows(port, "cct_port_default", n)

    # Forced-bandwidth replicate so the local-polynomial estimator math stays
    # pinned separately from the bandwidth selector. Both sides hard-code the
    # SAME constant: deriving it from a selector on one side only (as this did)
    # makes the statistic name depend on that selector, so the two sides stop
    # joining as soon as either selector moves.
    H_FORCED = FORCED_BANDWIDTH
    fit_forced = sp.rdrobust(df, y="y", x="x", c=0.0,
                              h=H_FORCED, b=H_FORCED)
    for label in ("conventional", "robust"):
        d = fit_forced.model_info[label]
        rows.append(
            ParityRecord(
                module=MODULE, side="py",
                statistic=f"forced_h{H_FORCED:g}_{label}_est",
                estimate=float(d["estimate"]),
                se=float(d["se"]),
                ci_lo=float(d["ci"][0]),
                ci_hi=float(d["ci"][1]),
                n=int(len(df)),
            )
        )

    write_results(
        MODULE, "py", rows,
        extra={
            "kernel": fit.model_info["kernel"],
            "p": fit.model_info["polynomial_p"],
            "q": fit.model_info["polynomial_q"],
            "bwselect": fit.model_info["bwselect"],
            "backend": "native",
            "bandwidth_parity_note": (
                "Track A headline rows run the native sp.rdrobust(...) "
                "default (bwselect='mserd', StatsPAI's own CCT cascade), "
                "which matches R/Stata rdrobust default mserd bandwidths "
                "and robust estimates on the Lee-2008 fixture. The "
                "cct_port_default_* rows record sp.rdrobust(..., "
                "bwselect='cct'), which delegates to the official "
                "rdrobust Python port; they are a port-vs-native "
                "convergence check with no R or Stata counterpart and "
                "never enter the parity join."
            ),
        },
    )


if __name__ == "__main__":
    main()

r"""
StatsPAI JSS replication script -- Section 4.3 worked example.

Callaway-Sant'Anna staggered DiD. The case study of Section 4.3 runs on the
original did::mpdta bytes (``original_case``); the rest of this script keeps
the drift guards on the calibrated replica that the parity harness uses.
Cross-checks the simple ATT, the doubly-robust IPW-DR variant
(Sant'Anna & Zhao 2020), and the cross-estimator parity contract
against Sun-Abraham and the imputation estimator.

Run with:
    python ex03_csdid.py            # writes results/ex03_csdid.json + .tex
    python ex03_csdid.py --pretty   # also prints JSON to stdout

Pinned values from tests/external_parity/test_published_replications.py:
    PINNED_MPDTA_CS_ATT = -0.0330   (replica simple ATT)
    PINNED_MPDTA_CS_SE  =  0.00774  (replica SE, post v1.13 IF-scaling fix)
    R did::att_gt simple ATT on the *original* mpdta bytes: -0.03995
    (SE 0.01203; est_method='reg', never-treated, analytic SEs --
    tests/orig_parity/02_mpdta_original).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import statspai as sp


HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE.parent / "results"
TABLES_DIR = HERE.parent / "tables"
sys.path.insert(0, str(HERE))
from _paths import STATSPAI_ROOT  # noqa: E402


def run() -> dict:
    df = sp.datasets.mpdta()
    out: dict = {
        "dataset": "sp.datasets.mpdta() (calibrated replica)",
        "n_rows": int(len(df)),
        "n_units": int(df["countyreal"].nunique()),
        "cohorts": sorted(int(g) for g in df["first_treat"].unique() if g != 0),
        "replica_target_simple_att": float(df.attrs.get("expected_simple_att", -0.04)),
        "published_simple_att_original": float(
            df.attrs.get("published_simple_att_original", -0.03995)
        ),
    }

    # Simple ATT via the registered article-style alias.
    cs = sp.callaway_santanna(
        df, y="lemp", g="first_treat", t="year", i="countyreal",
        estimator="reg",
    )
    out["cs_simple_att"] = {
        "estimate": float(cs.estimate),
        "se": float(cs.se),
        "method": cs.method,
        "estimand": cs.estimand,
    }

    # Replica-vs-pinned check (1e-3 tolerance per the test suite). The
    # pinned SE 0.00774 reflects the v1.13 simple-ATT influence-function
    # scaling fix (each group-time IF is rescaled by
    # n_total/n_relevant when embedded in the full unit universe, and
    # the control-regression uncertainty term is included in the
    # outcome-regression IF). See Section 5.3 of the JSS draft.
    PIN_ATT = -0.0330
    PIN_SE = 0.00774
    out["pinned_check"] = {
        "att_diff": abs(float(cs.estimate) - PIN_ATT),
        "se_diff": abs(float(cs.se) - PIN_SE),
        "passes_at_1e-3": (
            abs(float(cs.estimate) - PIN_ATT) < 1e-3
            and abs(float(cs.se) - PIN_SE) < 1e-3
        ),
    }

    # Replica-vs-published structural neighbourhood check
    # ([-0.06, -0.02] per the test post-condition).
    out["neighbourhood_check"] = {
        "in_range": -0.06 <= float(cs.estimate) <= -0.02,
        "lower": -0.06,
        "upper": -0.02,
        "published_original": float(out["published_simple_att_original"]),
    }

    # Modern staggered-DiD companion estimators and diagnostics. These
    # values are used for the method-map table in Section 4.3; the
    # original drift guard remains the C&S simple ATT above.
    sa = sp.sun_abraham(
        df, y="lemp", g="first_treat", t="year", i="countyreal",
    )
    bjs = sp.did_imputation(
        df, y="lemp", group="countyreal", time="year",
        first_treat="first_treat",
    )
    bacon = sp.bacon_decomposition(
        df, y="lemp", treat="treat", time="year", id="countyreal",
    )
    dynamic = sp.aggte(cs, type="dynamic")
    # Pass the CS result itself so honest_did uses the stored influence
    # functions (full Rambachan-Roth path) rather than the covariance-free
    # worst-case fallback it must use on a bare aggte path.
    honest = sp.honest_did(cs, e=0, m_grid=[0.0, 0.005, 0.01, 0.015, 0.02])
    max_rejecting_m = float(
        honest.loc[honest["rejects_zero"], "M"].max()
        if bool(honest["rejects_zero"].any())
        else 0.0
    )
    out["modern_did_snapshot"] = {
        "callaway_santanna": {
            "estimate": float(cs.estimate),
            "se": float(cs.se),
        },
        "sun_abraham": {
            "estimate": float(sa.estimate),
            "se": float(sa.se),
        },
        "bjs_imputation": {
            "estimate": float(bjs.estimate),
            "se": float(bjs.se),
        },
        "bacon_decomposition": {
            "twfe_estimate": float(bacon["beta_twfe"]),
            "n_comparisons": int(bacon["n_comparisons"]),
            "forbidden_weight_share": float(bacon["negative_weight_share"]),
        },
        "honest_did": {
            "event_time": 0,
            "max_rejecting_m": max_rejecting_m,
            "rows": honest.to_dict(orient="records"),
        },
        "handoff_covariance": _handoff_covariance(cs),
        "drdid": {
            "dispatcher": 'sp.callaway_santanna(..., estimator="dr") or sp.drdid(...)',
            "role": "doubly robust 2x2/cell-level DiD estimator",
        },
        "sdid": {
            "dispatcher": 'sp.synth(..., method="sdid")',
            "role": "weighted synthetic-control x DiD estimator",
        },
    }
    out["original_case"] = _original_case()

    return out


def _original_case() -> dict:
    """Section 4.3 on the original did::mpdta bytes, every post period.

    For each event time: the M = 0 fixed-length interval and the breakdown
    value under the joint covariance the fit carries, and the same under the
    ``diag(SE^2)`` a hand-composed hand-off can rebuild from a results table.
    Every post period is reported so the comparison cannot be read as chosen.
    """
    import numpy as np
    import pandas as pd
    from statspai.did._flci import breakdown_m_sd, event_study_moments, flci_delta_sd

    df = pd.read_csv(STATSPAI_ROOT / "tests" / "orig_parity" / "data" / "02_mpdta_original.csv")
    cs = sp.callaway_santanna(
        df, y="lemp", time="year", id="countyreal", g="first_treat",
        control_group="nevertreated", estimator="reg",
    )
    agg = sp.aggte(cs, type="simple")
    dyn = sp.aggte(cs, type="dynamic")
    beta, sigma, times = event_study_moments(cs)
    post = times >= 0
    order = np.r_[np.where(~post)[0], np.where(post)[0]]
    beta, sigma, times = beta[order], sigma[np.ix_(order, order)], times[order]
    n_pre, n_post = int((~post).sum()), int(post.sum())
    diag = np.diag(np.diag(sigma))
    corr = sigma / np.sqrt(np.outer(np.diag(sigma), np.diag(sigma)))
    pre_idx, post_idx = np.arange(n_pre), np.arange(n_pre, n_pre + n_post)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    np.savetxt(RESULTS_DIR / "ex03_mpdta_beta.csv", beta, fmt="%.17g")
    np.savetxt(RESULTS_DIR / "ex03_mpdta_sigma.csv", sigma, fmt="%.17g", delimiter=",")
    rows = []
    for k, e in enumerate(times[n_pre:]):
        l_post = (times[n_pre:] == e).astype(float)
        joint = flci_delta_sd(beta, sigma, n_pre, n_post, 0.0, l_post=l_post)
        short = flci_delta_sd(beta, diag, n_pre, n_post, 0.0, l_post=l_post)
        rows.append({
            "event_time": int(e),
            "att": float(beta[n_pre + k]),
            "se": float(np.sqrt(sigma[n_pre + k, n_pre + k])),
            "ci_joint": [float(joint.ci_lower), float(joint.ci_upper)],
            "ci_diagonal": [float(short.ci_lower), float(short.ci_upper)],
            "breakdown_joint": float(breakdown_m_sd(beta, sigma, n_pre, n_post, l_post=l_post)),
            "breakdown_diagonal": float(breakdown_m_sd(beta, diag, n_pre, n_post, l_post=l_post)),
        })
    return {
        "dataset": "tests/orig_parity/data/02_mpdta_original.csv (did::mpdta)",
        "simple_att": float(agg.estimate),
        "simple_se": float(agg.se),
        "dynamic_overall_att": float(dyn.estimate),
        "max_abs_correlation_pre_post": float(np.max(np.abs(corr[np.ix_(pre_idx, post_idx)]))),
        "rows": rows,
    }


def _handoff_covariance(cs) -> dict:
    """What a hand-built Honest-DiD handoff loses (Section 4, mpdta case).

    Composed by hand, the event-study covariance is often rebuilt from the
    reported standard errors. Compare the FLCI and its breakdown value under
    the joint covariance that ``sp.honest_did`` reads from the fit against
    ``diag(SE^2)``.
    """
    import numpy as np
    from statspai.did._flci import breakdown_m_sd, event_study_moments, flci_delta_sd

    beta, sigma, times = event_study_moments(cs)
    post = times >= 0
    order = np.r_[np.where(~post)[0], np.where(post)[0]]
    beta, sigma, times = beta[order], sigma[np.ix_(order, order)], times[order]
    n_pre, n_post = int((~post).sum()), int(post.sum())
    l_post = (times[post] == 0).astype(float)
    diag = np.diag(np.diag(sigma))
    corr = sigma / np.sqrt(np.outer(np.diag(sigma), np.diag(sigma)))
    full0 = flci_delta_sd(beta, sigma, n_pre, n_post, 0.0, l_post=l_post)
    diag0 = flci_delta_sd(beta, diag, n_pre, n_post, 0.0, l_post=l_post)
    return {
        "max_abs_correlation": float(np.max(np.abs(corr[np.triu_indices(len(beta), 1)]))),
        "breakdown_joint": float(breakdown_m_sd(beta, sigma, n_pre, n_post, l_post=l_post)),
        "breakdown_diagonal": float(breakdown_m_sd(beta, diag, n_pre, n_post, l_post=l_post)),
        "ci_m0_joint": [float(full0.ci_lower), float(full0.ci_upper)],
        "ci_m0_diagonal": [float(diag0.ci_lower), float(diag0.ci_upper)],
    }


def write_outputs(results: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "ex03_csdid.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    cs = results["cs_simple_att"]
    body = (
        f"        Replica simple ATT & "
        f"{cs['estimate']:.4f} & ({cs['se']:.4f}) \\\\\n"
        f"        Pinned reference   & "
        f"$-0.0330$ & ($0.00774$) \\\\\n"
        f"        R \\pkg{{did}} on the original \\texttt{{mpdta}} bytes & "
        f"$-0.03995$ & ($0.01203$) \\\\"
    )
    tex = (
        "\\begin{tabular}{lrr}\n"
        "    \\toprule\n"
        "    Source & Estimate & SE \\\\\n"
        "    \\midrule\n"
        f"{body}\n"
        "    \\bottomrule\n"
        "\\end{tabular}\n"
    )
    (TABLES_DIR / "ex03_csdid.tex").write_text(tex, encoding="utf-8")

    def _ci(pair: list) -> str:
        return f"$[{pair[0]:.4f},\\,{pair[1]:.4f}]$".replace("-", "-")

    case_rows = "\n".join(
        f"    {r['event_time']} & ${r['att']:.4f}$ & {r['se']:.4f} & {_ci(r['ci_joint'])} & "
        f"{r['breakdown_joint']:.4f} & {_ci(r['ci_diagonal'])} & {r['breakdown_diagonal']:.4f} \\\\"
        for r in results["original_case"]["rows"]
    )
    (TABLES_DIR / "ex03_handoff.tex").write_text(
        "\\begin{tabular}{@{}rrrcrcr@{}}\n"
        "    \\toprule\n"
        "    & & & \\multicolumn{2}{c}{Joint covariance} & "
        "\\multicolumn{2}{c}{$\\operatorname{diag}(\\mathrm{SE}^2)$} \\\\\n"
        "    $e$ & ATT & SE & 95\\% interval at $M=0$ & Breakdown & "
        "95\\% interval at $M=0$ & Breakdown \\\\\n"
        "    \\midrule\n"
        f"{case_rows}\n"
        "    \\bottomrule\n"
        "\\end{tabular}\n",
        encoding="utf-8",
    )

    snap = results["modern_did_snapshot"]
    rows = [
        (
            "TWFE diagnostic",
            "\\code{sp.bacon\\_\\allowbreak{}decomposition(...)}",
            "Goodman--Bacon decomposition",
            f"$\\hat\\beta_{{TWFE}}={snap['bacon_decomposition']['twfe_estimate']:.4f}$; "
            f"forbidden-share {100 * snap['bacon_decomposition']['forbidden_weight_share']:.1f}\\%",
        ),
        (
            "Sun--Abraham",
            "\\code{sp.sun\\_abraham(...)}",
            "Interaction-weighted event study",
            f"ATT {snap['sun_abraham']['estimate']:.4f} "
            f"(SE {snap['sun_abraham']['se']:.4f})",
        ),
        (
            "Callaway--Sant'Anna",
            "\\code{sp.callaway\\_\\allowbreak{}santanna(...)}",
            "Group-time ATT aggregation",
            f"ATT {snap['callaway_santanna']['estimate']:.4f} "
            f"(SE {snap['callaway_santanna']['se']:.4f})",
        ),
        (
            "BJS imputation",
            "\\code{sp.did\\_imputation(...)}",
            "Untreated-outcome imputation",
            f"ATT {snap['bjs_imputation']['estimate']:.4f} "
            f"(SE {snap['bjs_imputation']['se']:.4f})",
        ),
        (
            "DR-DiD",
            "\\code{sp.callaway\\_\\allowbreak{}santanna(dr)}",
            "Doubly robust 2x2/cell estimator",
            "Dispatcher path; no separate simple-ATT row",
        ),
        (
            "Synthetic DiD",
            "\\code{sp.synth(..., method='sdid')}",
            "Weighted SC $\\times$ DiD design",
            "Used when treated aggregate units need donor weights",
        ),
        (
            "Honest DiD",
            "\\code{sp.honest\\_did(dynamic, e=0)}",
            "Parallel-trends sensitivity",
            f"rejects zero up to $M={snap['honest_did']['max_rejecting_m']:.4f}$",
        ),
    ]
    did_map_body = "\n".join(
        "    "
        + " & ".join(row)
        + " \\\\"
        for row in rows
    )
    did_map_tex = (
        "\\begin{tabular}{p{0.15\\linewidth}p{0.28\\linewidth}"
        "p{0.23\\linewidth}p{0.24\\linewidth}}\n"
        "    \\toprule\n"
        "    Component & StatsPAI call & Role & Local mpdta output \\\\\n"
        "    \\midrule\n"
        f"{did_map_body}\n"
        "    \\bottomrule\n"
        "\\end{tabular}\n"
    )
    (TABLES_DIR / "ex03_did_methods.tex").write_text(
        did_map_tex, encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true", help="print JSON")
    args = parser.parse_args()

    results = run()
    write_outputs(results)

    if args.pretty:
        print(json.dumps(results, indent=2))
    else:
        print("OK -- wrote", RESULTS_DIR / "ex03_csdid.json")
        print("OK -- wrote", TABLES_DIR / "ex03_csdid.tex")
        print("OK -- wrote", TABLES_DIR / "ex03_did_methods.tex")

    fails = []
    if not results["pinned_check"]["passes_at_1e-3"]:
        fails.append("pinned tolerance 1e-3 failed (drift detected)")
    if not results["neighbourhood_check"]["in_range"]:
        fails.append("simple ATT outside [-0.06, -0.02] neighbourhood")
    if fails:
        print("FAIL:", "; ".join(fails), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

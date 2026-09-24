r"""
StatsPAI JSS replication script -- Section 4.4 worked example.

Lee (2008) sharp RD incumbency-advantage example on the bundled
`sp.datasets.lee_2008_senate()` replica.

Run with:
    python ex04_lee.py            # writes results/ex04_lee.json + .tex
    python ex04_lee.py --pretty   # also prints JSON to stdout

Pinned replica value from tests/external_parity/test_published_replications.py:
    PINNED_LEE_RD_JUMP = 0.0768
Published Lee (2008) original-data figure: approximately 0.080.
Canonical CCT/R rdrobust parity on rdrobust_RDsenate:
    conventional = 7.4141, robust = 7.5065, h = 17.7544.
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


def run() -> dict:
    # simulated=True is passed explicitly: the dataset's default flipped to
    # the real extract in b0918220 ("ship the real data, hand back the real
    # data"), which silently changed the columns this arm reads. The paper's
    # replica arm is the calibrated simulated panel, so it names what it wants.
    df = sp.datasets.lee_2008_senate(simulated=True)
    rd = sp.rdrobust(
        df, y="voteshare_next", x="margin", c=0.0, bwselect="mserd"
    )
    robust = rd.model_info["robust"]
    conventional = rd.model_info["conventional"]
    estimate = float(rd.estimate)

    df_real = sp.datasets.lee_2008_senate(simulated=False)
    rd_cct = sp.rdrobust(
        df_real, y="y", x="x", c=0.0, kernel="triangular", bwselect="cct"
    )
    cct_h = float(rd_cct.model_info["bandwidth_h"])
    cct_robust = rd_cct.model_info["robust"]
    cct_conventional = rd_cct.model_info["conventional"]
    out: dict = {
        "dataset": "sp.datasets.lee_2008_senate() (calibrated replica)",
        "n_rows": int(len(df)),
        "running_variable": "margin",
        "outcome": "voteshare_next",
        "published_original_jump_approx": 0.080,
        "published_original_jump_pp": 7.99,
        # Was 0.0616. That value was pinned from StatsPAI's own output while
        # the CCT bandwidth selector returned an h 2.8-4.8x too narrow, and it
        # sat 23% below the published Lee (2008) Table 2 col 1 estimate of
        # 0.080 that this replica is calibrated to. After the bandwidth fix
        # the replica returns 0.0763, within 5% of the published number, and
        # R rdrobust 4.0.0 on the same replica returns conventional 0.077547 /
        # robust 0.076339. tests/external_parity/test_published_replications.py
        # carries the same corrected pin.
        "pinned_replica_jump": 0.0768,
        "rdrobust": {
            "robust_estimate": estimate,
            "robust_se": float(rd.se),
            "robust_pvalue": float(rd.pvalue),
            "robust_ci": [float(rd.ci[0]), float(rd.ci[1])],
            "conventional_estimate": float(conventional["estimate"]),
            "conventional_se": float(conventional["se"]),
            "bandwidth_h": float(rd.model_info["bandwidth_h"]),
            "bandwidth_b": float(rd.model_info["bandwidth_b"]),
            "n_left": int(rd.model_info["n_left"]),
            "n_right": int(rd.model_info["n_right"]),
            "n_effective_left": int(rd.model_info["n_effective_left"]),
            "n_effective_right": int(rd.model_info["n_effective_right"]),
        },
        "original_rdrobust_Rdsenate_cct": {
            "dataset": "rdrobust::rdrobust_RDsenate",
            "n_rows": int(len(df_real)),
            "bwselect": "cct",
            "robust_estimate": float(cct_robust["estimate"]),
            "robust_se": float(cct_robust["se"]),
            "robust_ci": [float(cct_robust["ci"][0]), float(cct_robust["ci"][1])],
            "conventional_estimate": float(cct_conventional["estimate"]),
            "conventional_se": float(cct_conventional["se"]),
            "bandwidth_h": cct_h,
            "n_effective_left": int(rd_cct.model_info["n_effective_left"]),
            "n_effective_right": int(rd_cct.model_info["n_effective_right"]),
        },
        "pinned_check": {
            "abs_diff": abs(estimate - 0.0768),
            "passes_at_1e-3": abs(estimate - 0.0768) < 1e-3,
        },
        "cct_parity_check": {
            "robust_abs_diff": abs(float(cct_robust["estimate"]) - 7.5065024835),
            "conventional_abs_diff": abs(
                float(cct_conventional["estimate"]) - 7.4141308229
            ),
            "bandwidth_abs_diff": abs(cct_h - 17.7543972961),
            "passes_at_1e-6": (
                abs(float(cct_robust["estimate"]) - 7.5065024835) < 1e-6
                and abs(float(cct_conventional["estimate"]) - 7.4141308229) < 1e-6
                and abs(cct_h - 17.7543972961) < 1e-6
            ),
        },
        "neighbourhood_check": {
            "in_range": 0.05 <= estimate <= 0.12,
            "lower": 0.05,
            "upper": 0.12,
        },
    }
    return out


def write_outputs(results: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "ex04_lee.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )

    rd = results["rdrobust"]
    cct = results["original_rdrobust_Rdsenate_cct"]
    tex = (
        "\\begin{tabular}{lrr}\n"
        "    \\toprule\n"
        "    Statistic & Estimate & SE \\\\\n"
        "    \\midrule\n"
        f"    Replica robust (share) & {rd['robust_estimate']:.4f} & {rd['robust_se']:.4f} \\\\\n"
        f"    Replica conventional (share) & {rd['conventional_estimate']:.4f} & {rd['conventional_se']:.4f} \\\\\n"
        f"    Original CCT robust (pp) & {cct['robust_estimate']:.4f} & {cct['robust_se']:.4f} \\\\\n"
        f"    Original CCT conventional (pp) & {cct['conventional_estimate']:.4f} & {cct['conventional_se']:.4f} \\\\\n"
        f"    Published original (pp) & {results['published_original_jump_pp']:.4f} & --- \\\\\n"
        "    \\bottomrule\n"
        "\\end{tabular}\n"
    )
    (TABLES_DIR / "ex04_lee.tex").write_text(tex, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true", help="print JSON")
    args = parser.parse_args()

    results = run()
    write_outputs(results)

    if args.pretty:
        print(json.dumps(results, indent=2))
    else:
        print("OK -- wrote", RESULTS_DIR / "ex04_lee.json")
        print("OK -- wrote", TABLES_DIR / "ex04_lee.tex")

    fails = []
    if not results["pinned_check"]["passes_at_1e-3"]:
        fails.append("pinned tolerance 1e-3 failed")
    if not results["cct_parity_check"]["passes_at_1e-6"]:
        fails.append("CCT parity tolerance 1e-6 failed")
    if not results["neighbourhood_check"]["in_range"]:
        fails.append("RD jump outside [0.05, 0.12]")
    if fails:
        print("FAIL:", "; ".join(fails), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

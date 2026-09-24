r"""
StatsPAI JSS replication script -- Section 4.2 worked example.

Abadie-Gardeazabal (2003) Basque terrorism synthetic-control example
on the bundled `sp.datasets.basque_terrorism()` replica.

Run with:
    python ex02_basque.py            # writes results/ex02_basque.json + .tex
    python ex02_basque.py --pretty   # also prints JSON to stdout

The bundled dataset is a compact calibrated replica with the canonical
treated unit, donor pool, outcome, and intervention timing. It is not
the full original Abadie-Gardeazabal covariate file; the check below
therefore uses a structural neighbourhood rather than a bit-equal
published-value target.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import pandas as pd
import statspai as sp


HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE.parent / "results"
TABLES_DIR = HERE.parent / "tables"


def _active_weights(fit) -> dict[str, float]:
    weights = fit.model_info.get("weights", "")
    if isinstance(weights, pd.DataFrame):
        df = weights
    elif isinstance(weights, str) and weights:
        df = pd.read_fwf(io.StringIO(weights))
    else:
        return {}
    if "unit" not in df or "weight" not in df:
        return {}
    return {str(row.unit): float(row.weight) for row in df.itertuples()}


def run() -> dict:
    df = sp.datasets.basque_terrorism()
    fit = sp.synth(
        df,
        outcome="gdppc",
        unit="region",
        time="year",
        treated_unit="Basque Country",
        treatment_time=1970,
        method="classic",
    )

    estimate = float(fit.estimate)
    se = float(fit.se)
    pre_mspe = float(fit.model_info.get("pre_treatment_mspe"))
    pre_rmse = float(fit.model_info.get("pre_treatment_rmse"))
    out: dict = {
        "dataset": "sp.datasets.basque_terrorism() (calibrated replica)",
        "n_rows": int(len(df)),
        "n_units": int(df["region"].nunique()),
        "years": [int(df["year"].min()), int(df["year"].max())],
        "treated_unit": "Basque Country",
        "treatment_time": 1970,
        "published_original_att_approx": -0.855,
        "synth_classic": {
            "estimate": estimate,
            "se": se,
            "pre_treatment_rmse": pre_rmse,
            "pre_treatment_mspe": pre_mspe,
            "weight_hhi": float(fit.model_info.get("weight_hhi")),
            "treated_post_pre_ratio": float(fit.model_info.get("treated_ratio")),
            "v_method": str(fit.model_info.get("v_method", "")),
            "n_donors": int(fit.model_info.get("n_donors")),
            "n_active_donors": int(fit.model_info.get("n_active_donors")),
            "n_pre_periods": int(fit.model_info.get("n_pre_periods")),
            "n_post_periods": int(fit.model_info.get("n_post_periods")),
            "n_placebos": int(fit.model_info.get("n_placebos")),
            "active_weights": _active_weights(fit),
        },
        "neighbourhood_check": {
            "negative_gap": estimate < 0,
            "in_range": -1.05 <= estimate <= -0.55,
            "lower": -1.05,
            "upper": -0.55,
        },
    }
    return out


def write_outputs(results: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "ex02_basque.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )

    fit = results["synth_classic"]
    active = ", ".join(
        f"{unit} {weight:.3f}"
        for unit, weight in fit["active_weights"].items()
    )
    tex = (
        "\\begin{tabular}{lr}\n"
        "    \\toprule\n"
        "    Statistic & Value \\\\\n"
        "    \\midrule\n"
        f"    Average post-1970 gap & {fit['estimate']:.4f} \\\\\n"
        f"    Placebo SE & {fit['se']:.4f} \\\\\n"
        f"    Pre-treatment RMSE & {fit['pre_treatment_rmse']:.4f} \\\\\n"
        f"    Pre-treatment MSPE & {fit['pre_treatment_mspe']:.6f} \\\\\n"
        f"    Treated post/pre MSPE ratio & "
        f"{fit['treated_post_pre_ratio']:.2f} \\\\\n"
        f"    Donor-weight HHI & {fit['weight_hhi']:.3f} \\\\\n"
        f"    Active donor weights & "
        f"\\multicolumn{{1}}{{l}}{{{active}}} \\\\\n"
        "    \\bottomrule\n"
        "\\end{tabular}\n"
    )
    (TABLES_DIR / "ex02_basque.tex").write_text(tex, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true", help="print JSON")
    args = parser.parse_args()

    results = run()
    write_outputs(results)

    if args.pretty:
        print(json.dumps(results, indent=2))
    else:
        print("OK -- wrote", RESULTS_DIR / "ex02_basque.json")
        print("OK -- wrote", TABLES_DIR / "ex02_basque.tex")

    checks = results["neighbourhood_check"]
    if not checks["negative_gap"] or not checks["in_range"]:
        print(
            "FAIL: Basque synthetic-control gap outside [-1.05, -0.55].",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

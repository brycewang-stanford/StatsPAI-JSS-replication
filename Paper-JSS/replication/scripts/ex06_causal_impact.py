r"""
StatsPAI JSS replication script -- Section 4.6 worked example.

Brodersen-style advertising-lift time-series example for
``sp.causal_impact``.  The data are a deterministic synthetic
marketing panel with 90 daily observations, four unaffected control
series, and a known post-intervention lift of 4.2 units/day from day
61 onward.

Run with:
    python ex06_causal_impact.py            # writes JSON + table + figures
    python ex06_causal_impact.py --pretty   # also prints JSON to stdout
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")

import statspai as sp


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
RESULTS_DIR = HERE.parent / "results"
TABLES_DIR = HERE.parent / "tables"
FIGURES_DIR = ROOT / "manuscript" / "figures"
PDF_METADATA = {"CreationDate": None}

TRUE_AVG_EFFECT = 4.2
INTERVENTION_DAY = 61


def make_ad_lift_data(seed: int = 20260505) -> pd.DataFrame:
    """Create a stable 90-day advertising-lift example."""
    rng = np.random.default_rng(seed)
    n = 90
    day = np.arange(1, n + 1)

    market = np.zeros(n)
    for idx in range(1, n):
        market[idx] = 0.82 * market[idx - 1] + rng.normal(0, 0.45)

    weekly = np.sin(2 * np.pi * day / 7)
    search = 30 + 1.1 * market + 1.8 * weekly + rng.normal(0, 0.35, n)
    category = 22 + 0.8 * market + 0.9 * np.cos(2 * np.pi * day / 7) + rng.normal(
        0, 0.4, n
    )
    competitor = 18 + 0.55 * market - 0.7 * weekly + rng.normal(0, 0.45, n)
    organic = 12 + 0.5 * market + rng.normal(0, 0.3, n)

    baseline = (
        35
        + 1.05 * search
        + 0.72 * category
        - 0.38 * competitor
        + 0.48 * organic
        + rng.normal(0, 0.65, n)
    )
    true_effect = np.where(day >= INTERVENTION_DAY, TRUE_AVG_EFFECT, 0.0)

    return pd.DataFrame(
        {
            "day": day,
            "sales": baseline + true_effect,
            "search": search,
            "category": category,
            "competitor": competitor,
            "organic": organic,
            "true_effect": true_effect,
        }
    )


def run() -> dict:
    df = make_ad_lift_data()
    covariates = ["search", "category", "competitor", "organic"]
    fit = sp.causal_impact(
        df,
        y="sales",
        time="day",
        intervention_time=INTERVENTION_DAY,
        covariates=covariates,
    )

    detail = fit.detail
    if detail is None:
        raise RuntimeError("sp.causal_impact returned no detail table")
    pre = detail.loc[~detail["post_intervention"]]
    post = detail.loc[detail["post_intervention"]]
    pre_rmse = float(np.sqrt(np.mean((pre["actual"] - pre["predicted"]) ** 2)))
    post_actual = float(post["actual"].sum())
    post_counterfactual = float(post["predicted"].sum())
    cumulative = float(fit.model_info["total_effect"])

    out = {
        "dataset": "deterministic Brodersen-style advertising-lift simulation",
        "n_days": int(len(df)),
        "intervention_day": INTERVENTION_DAY,
        "n_pre": int(fit.model_info["n_pre"]),
        "n_post": int(fit.model_info["n_post"]),
        "covariates": covariates,
        "true_avg_effect": TRUE_AVG_EFFECT,
        "estimated_avg_effect": float(fit.estimate),
        "se_avg_effect": float(fit.se),
        "ci95": [float(fit.ci[0]), float(fit.ci[1])],
        "pvalue": float(fit.pvalue),
        "estimated_cumulative_effect": cumulative,
        "true_cumulative_effect": float(TRUE_AVG_EFFECT * fit.model_info["n_post"]),
        "relative_effect_pct": float(fit.model_info["relative_effect_pct"]),
        "pre_period_rmse": pre_rmse,
        "post_actual_sum": post_actual,
        "post_counterfactual_sum": post_counterfactual,
        "pinned_checks": {
            "avg_effect_abs_diff_to_truth": abs(float(fit.estimate) - TRUE_AVG_EFFECT),
            "avg_effect_passes_abs_0_25": abs(float(fit.estimate) - TRUE_AVG_EFFECT)
            <= 0.25,
            "pre_rmse_below_0_75": pre_rmse < 0.75,
            "ci_contains_truth": float(fit.ci[0]) <= TRUE_AVG_EFFECT <= float(fit.ci[1]),
            "cumulative_effect_positive": cumulative > 0.0,
        },
    }
    return out, fit


def write_outputs(results: dict, fit) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    (RESULTS_DIR / "ex06_causal_impact.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )

    tex = (
        "\\begin{tabular}{lrr}\n"
        "    \\toprule\n"
        "    Quantity & Estimate & Reference \\\\\n"
        "    \\midrule\n"
        f"    Average post-period effect & {results['estimated_avg_effect']:.3f} & "
        f"{results['true_avg_effect']:.1f} \\\\\n"
        f"    SE of average effect & {results['se_avg_effect']:.3f} & -- \\\\\n"
        f"    95\\% CI & "
        f"$[{results['ci95'][0]:.3f}, {results['ci95'][1]:.3f}]$ & "
        "contains truth \\\\\n"
        f"    Cumulative effect & {results['estimated_cumulative_effect']:.1f} & "
        f"{results['true_cumulative_effect']:.1f} \\\\\n"
        f"    Relative effect & {results['relative_effect_pct']:.1f}\\% & -- \\\\\n"
        f"    Pre-period RMSE & {results['pre_period_rmse']:.3f} & $<0.75$ guard \\\\\n"
        "    \\bottomrule\n"
        "\\end{tabular}\n"
    )
    (TABLES_DIR / "ex06_causal_impact.tex").write_text(tex, encoding="utf-8")

    fig, _axes = sp.impactplot(
        fit,
        title="CausalImpact advertising-lift example",
        figsize=(10, 8),
    )
    fig.savefig(
        FIGURES_DIR / "ex06_causal_impact.pdf",
        bbox_inches="tight",
        metadata=PDF_METADATA,
    )
    fig.savefig(FIGURES_DIR / "ex06_causal_impact.png", dpi=160, bbox_inches="tight")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true", help="print JSON")
    args = parser.parse_args()

    results, fit = run()
    write_outputs(results, fit)

    if args.pretty:
        print(json.dumps(results, indent=2))
    else:
        print("OK -- wrote", RESULTS_DIR / "ex06_causal_impact.json")
        print("OK -- wrote", TABLES_DIR / "ex06_causal_impact.tex")
        print("OK -- wrote", FIGURES_DIR / "ex06_causal_impact.pdf")

    failed = [key for key, value in results["pinned_checks"].items() if not value]
    if failed:
        print("FAIL: " + "; ".join(failed), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

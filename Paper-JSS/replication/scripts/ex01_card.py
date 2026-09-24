r"""
StatsPAI JSS replication script -- Section 4.1 worked example.

Card (1995) returns to schooling. Runs OLS, 2SLS (nearc4 instrument),
DML (partially-linear regression), and a causal forest on the
calibrated replica `sp.datasets.card_1995()`.

Run with:
    python ex01_card.py            # writes results/ex01_card.json + .tex
    python ex01_card.py --pretty   # also prints a Stata-style table

The script writes JSON and a LaTeX fragment that the manuscript
includes via \input{tables/ex01_card.tex}. Numerical figures land in
results/.

This file is the source of truth for the paper's section 4.1
numbers; if it disagrees with the draft, the draft is wrong.
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
    df = sp.datasets.card_1995()
    out: dict = {
        "dataset": "sp.datasets.card_1995() (calibrated replica)",
        "n": int(len(df)),
    }

    # OLS
    ols = sp.regress(
        "lwage ~ educ + exper + expersq + black + south + smsa", data=df
    )
    out["ols"] = {
        "beta_educ": float(ols.params["educ"]),
        "se_educ": float(ols.std_errors["educ"]),
    }

    # 2SLS with nearc4 as instrument
    iv = sp.iv(
        "lwage ~ exper + expersq + black + south + smsa + (educ ~ nearc4)",
        data=df,
    )
    out["iv_2sls"] = {
        "beta_educ": float(iv.params["educ"]),
        "se_educ": float(iv.std_errors["educ"]),
    }

    # DML PLR with default cross-fitted nuisance learners
    try:
        dml = sp.dml(
            data=df,
            y="lwage",
            d="educ",
            X=["exper", "expersq", "black", "south", "smsa"],
            model="plr",
        )
        # CausalResult exposes .params and .std_errors as Series keyed
        # by 'ATE' (since dml is a single-parameter estimator here).
        theta = float(dml.params.iloc[0])
        se = float(dml.std_errors.iloc[0])
        out["dml_plr"] = {"theta": theta, "se": se}
    except Exception as exc:  # pragma: no cover - defensive
        out["dml_plr"] = {"error": f"{type(exc).__name__}: {exc}"}

    # Causal forest on the continuous treatment, exactly as Listing 1
    # fits it. The scalar aggregate is the continuous-treatment average
    # partial effect; the grf reference (ex01_card_grf.R, Tier 2) is a
    # second, independently seeded forest, so the gap is T3 evidence.
    cf = sp.causal_forest(
        "lwage ~ educ | exper + expersq + black + south + smsa",
        data=df,
        n_estimators=2000,
        discrete_treatment=False,
        random_state=42,
    )
    agg = cf.average_treatment_effect()
    cate = sp.cate_summary(cf)["CATE"]
    out["causal_forest"] = {
        "method": agg["method"],
        "ate": float(agg["estimate"]),
        "ate_se": float(agg["se"]),
        "cate_mean": float(cate["Mean (ATE)"]),
        "cate_sd": float(cate["Std. Dev."]),
        "cate_q25": float(cate["Q25"]),
        "cate_q75": float(cate["Q75"]),
    }
    grf_json = RESULTS_DIR / "ex01_card_grf.json"
    if grf_json.exists():
        grf = json.loads(grf_json.read_text(encoding="utf-8"))
        cfo = out["causal_forest"]
        out["causal_forest_grf_reference"] = {
            "grf_version": grf["grf_version"],
            "ate": grf["ate"],
            "ate_se": grf["ate_se"],
            "cate_sd": grf["cate_sd"],
            "cate_q25": grf["cate_q25"],
            "cate_q75": grf["cate_q75"],
            # Gap in units of the combined standard error of two
            # independent forests.
            "ate_z": (cfo["ate"] - grf["ate"])
            / (cfo["ate_se"] ** 2 + grf["ate_se"] ** 2) ** 0.5,
        }

    # External-parity targets recorded in tests/external_parity/
    out["replica_target"] = {
        "ols_target": 0.11,
        "iv_target": 0.142,
        "ols_published_original_nlsym": 0.075,
        "iv_published_original_nlsym": 0.132,
    }

    # Sanity check: replica should preserve the IV>OLS Card puzzle.
    out["puzzle_preserved"] = (
        out["iv_2sls"]["beta_educ"] > out["ols"]["beta_educ"]
    )
    return out


def write_outputs(results: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "ex01_card.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    rows = [
        ("OLS", results["ols"]["beta_educ"], results["ols"]["se_educ"]),
        ("2SLS (nearc4)",
         results["iv_2sls"]["beta_educ"], results["iv_2sls"]["se_educ"]),
    ]
    if "theta" in results.get("dml_plr", {}):
        rows.append(
            ("DML PLR (lasso)",
             results["dml_plr"]["theta"], results["dml_plr"]["se"])
        )
    body = "\n".join(
        f"        {name} & {b:.4f} & {s:.4f} \\\\"
        for name, b, s in rows
    )
    tex = (
        "\\begin{tabular}{lrr}\n"
        "    \\toprule\n"
        "    Estimator & $\\hat\\beta_{educ}$ & SE \\\\\n"
        "    \\midrule\n"
        f"{body}\n"
        "    \\bottomrule\n"
        "\\end{tabular}\n"
    )
    (TABLES_DIR / "ex01_card.tex").write_text(tex, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true", help="print table")
    args = parser.parse_args()

    results = run()
    write_outputs(results)

    if args.pretty:
        print(json.dumps(results, indent=2))
    else:
        print("OK -- wrote", RESULTS_DIR / "ex01_card.json")
        print("OK -- wrote", TABLES_DIR / "ex01_card.tex")

    if not results["puzzle_preserved"]:
        print(
            "FAIL: IV<=OLS on the replica; the Card puzzle should hold.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

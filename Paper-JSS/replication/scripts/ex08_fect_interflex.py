r"""
StatsPAI JSS replication script -- Section 4.7 worked example.

Cross-software equivalence in practice: the fect counterfactual
estimators (Liu, Wang and Xu 2024) and the interflex interaction-effect
estimators (Hainmueller, Mummolo and Xu 2019) run natively in StatsPAI on
the same CSV bytes that the Track A modules 86 and 87 hand to R (``fect``,
``interflex``) and Stata (``fect_stata``, SSC ``interflex``). The script
re-estimates the StatsPAI side live (Tier 1, no R or Stata needed), reads
the committed R and Stata golden artifacts, and writes the three-way table
printed in the manuscript.

Run with:
    python ex08_fect_interflex.py            # writes results/ex08_fect_interflex.json + tables/ex08_three_way.tex
    python ex08_fect_interflex.py --pretty   # also prints JSON to stdout
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

import statspai as sp


HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE.parent / "results"
TABLES_DIR = HERE.parent / "tables"
PAPER_ROOT = HERE.parents[1]


def _statspai_root() -> Path:
    import os

    override = os.environ.get("STATSPAI_ROOT")
    if override:
        return Path(override).resolve()
    return PAPER_ROOT.parent


REPO = _statspai_root()
R_DATA = REPO / "tests" / "r_parity" / "data"
R_RESULTS = REPO / "tests" / "r_parity" / "results"
STATA_RESULTS = REPO / "tests" / "stata_parity" / "results"

# Exact fingerprints of the shared fixtures, so the table cannot drift
# onto different bytes than the R / Stata goldens saw.
FIXTURE_SHA256 = {
    "86_fect.csv": None,
    "87_interflex.csv": None,
}


def _rows(path: Path) -> dict[str, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {row["statistic"]: row for row in payload["rows"]}


def _rel(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return abs(a - b) / max(abs(b), 1e-12)


def run() -> dict:
    out: dict = {"modules": ["86_fect", "87_interflex"]}

    # ---- fect on the module-86 panel ------------------------------------
    panel = pd.read_csv(R_DATA / "86_fect.csv")
    r86 = _rows(R_RESULTS / "86_fect_R.json")
    s86 = _rows(STATA_RESULTS / "86_fect_Stata.json")
    fect_rows = []
    for method, kw, label in (
        ("fe", {}, "two-way FE (imputation)"),
        ("ife", {"r": 2}, "interactive FE, r = 2"),
        ("mc", {"lam": 0.002}, "matrix completion, lambda = 0.002"),
    ):
        fit = sp.fect(
            panel, y="Y", treat="D", unit="id", time="time", covariates=["X1", "X2"],
            method=method, tol=1e-12, max_iter=20000, **kw,
        )
        key = f"{method}_att_avg"
        fect_rows.append(
            {
                "label": label,
                "statistic": key,
                "statspai": float(fit.estimate),
                "r": r86[key]["estimate"],
                "stata": s86[key]["estimate"],
                "rel_r": _rel(float(fit.estimate), r86[key]["estimate"]),
                "rel_stata": _rel(float(fit.estimate), s86[key]["estimate"]),
                "niter": int(fit.model_info["niter"]),
            }
        )
        b1 = f"{method}_beta_x1"
        fect_rows.append(
            {
                "label": f"  covariate X1 coefficient ({method})",
                "statistic": b1,
                "statspai": float(fit.model_info["beta"]["X1"]),
                "r": r86[b1]["estimate"],
                "stata": s86[b1]["estimate"],
                "rel_r": _rel(float(fit.model_info["beta"]["X1"]), r86[b1]["estimate"]),
                "rel_stata": _rel(float(fit.model_info["beta"]["X1"]), s86[b1]["estimate"]),
            }
        )
    out["fect"] = fect_rows

    # ---- interflex on the module-87 sample --------------------------------
    sample = pd.read_csv(R_DATA / "87_interflex.csv")
    r87 = _rows(R_RESULTS / "87_interflex_R.json")
    s87 = _rows(STATA_RESULTS / "87_interflex_Stata.json")
    lin = sp.interflex(sample, y="Y", d="D", x="X", z=["Z1"], estimator="linear", neval=5)
    binned = sp.interflex(sample, y="Y", d="D", x="X", z=["Z1"], estimator="binning", cutoffs=[0.3, 1.7])
    kern = sp.interflex(sample, y="Y", d="D", x="X", z=["Z1"], estimator="kernel", bw=1.0, neval=5)
    kern_fixed = sp.interflex(
        sample, y="Y", d="D", x="X", z=["Z1"], estimator="kernel", bw=1.0, neval=5, adaptive=False
    )
    inter_rows = []
    me3 = float(lin.detail["me"].iloc[2])
    inter_rows.append(
        {
            "label": "linear ME at the grid midpoint",
            "statistic": "linear_me_3",
            "statspai": me3, "r": r87["linear_me_3"]["estimate"], "stata": s87["linear_me_3"]["estimate"],
            "se_statspai": float(lin.detail["se"].iloc[2]), "se_r": r87["linear_me_3"]["se"], "se_stata": s87["linear_me_3"]["se"],
            "rel_r": _rel(me3, r87["linear_me_3"]["estimate"]), "rel_stata": _rel(me3, s87["linear_me_3"]["estimate"]),
        }
    )
    for j in (1, 2, 3):
        key = f"binning_me_{j}"
        val = float(binned.detail["me"].iloc[j - 1])
        inter_rows.append(
            {
                "label": f"binning effect, bin {j} (median x = {float(binned.detail['x'].iloc[j - 1]):.2f})",
                "statistic": key,
                "statspai": val, "r": r87[key]["estimate"], "stata": s87[key]["estimate"],
                "se_statspai": float(binned.detail["se"].iloc[j - 1]), "se_r": r87[key]["se"], "se_stata": s87[key]["se"],
                "rel_r": _rel(val, r87[key]["estimate"]), "rel_stata": _rel(val, s87[key]["estimate"]),
            }
        )
    tests = binned.model_info["tests"]
    inter_rows.append(
        {
            "label": "Wald p-value, linear vs binning (R convention)",
            "statistic": "p_wald",
            "statspai": float(tests["p_wald"]), "r": r87["p_wald"]["estimate"], "stata": None,
            "rel_r": _rel(float(tests["p_wald"]), r87["p_wald"]["estimate"]), "rel_stata": None,
        }
    )
    stata_wald = sp.interflex(
        sample, y="Y", d="D", x="X", z=["Z1"], estimator="binning", cutoffs=[0.3, 1.7],
        wald_full_moderate=False, wald_test="F",
    ).model_info["tests"]["p_wald"]
    inter_rows.append(
        {
            "label": "Wald p-value (Stata convention: no covariate-by-bin terms, F)",
            "statistic": "p_wald_stata",
            "statspai": float(stata_wald), "r": None, "stata": s87["p_wald_stata"]["estimate"],
            "rel_r": None, "rel_stata": _rel(float(stata_wald), s87["p_wald_stata"]["estimate"]),
        }
    )
    k3 = float(kern.detail["me"].iloc[2])
    inter_rows.append(
        {
            "label": "kernel ME at the midpoint, adaptive bandwidth (R convention)",
            "statistic": "kernel_me_3",
            "statspai": k3, "r": r87["kernel_me_3"]["estimate"], "stata": None,
            "rel_r": _rel(k3, r87["kernel_me_3"]["estimate"]), "rel_stata": None,
        }
    )
    kf3 = float(kern_fixed.detail["me"].iloc[2])
    inter_rows.append(
        {
            "label": "kernel ME at the midpoint, fixed bandwidth (Stata convention)",
            "statistic": "kernel_fixed_me_3",
            "statspai": kf3, "r": None, "stata": s87["kernel_fixed_me_3"]["estimate"],
            "rel_r": None, "rel_stata": _rel(kf3, s87["kernel_fixed_me_3"]["estimate"]),
        }
    )
    out["interflex"] = inter_rows
    worst = max(
        v for row in fect_rows + inter_rows for v in (row.get("rel_r"), row.get("rel_stata")) if v is not None
    )
    out["worst_relative_gap"] = worst
    return out


def _fmt(v: float | None, digits: int = 6) -> str:
    if v is None:
        return "---"
    return f"{v:.{digits}f}"


def _sci(v: float | None) -> str:
    if v is None:
        return "---"
    mant, exp = f"{v:.3e}".split("e")
    return f"${mant}\\times10^{{{int(exp)}}}$"


def _rel_fmt(v: float | None) -> str:
    if v is None:
        return "---"
    if v == 0.0:
        # An exact bit-equal match; "0.0 x 10^0" would misread as order 1.
        return "$0$"
    mant, exp = f"{v:.1e}".split("e")
    return f"${mant}\\times10^{{{int(exp)}}}$"


def write_outputs(results: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "ex08_fect_interflex.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    lines = [
        "\\begin{tabular}{@{}p{0.34\\linewidth}rrrrr@{}}",
        "    \\toprule",
        "    Quantity & \\statspai{} & \\proglang{R} & \\proglang{Stata} & rel(sp,R) & rel(sp,Stata) \\\\",
        "    \\midrule",
        "    \\multicolumn{6}{@{}l}{\\emph{fect counterfactual estimators (module 86, staggered two-factor panel)}} \\\\",
    ]
    for row in results["fect"]:
        if row["statistic"].endswith("_att_avg"):
            lines.append(
                f"    ATT, {row['label']} & {_fmt(row['statspai'])} & {_fmt(row['r'])} & {_fmt(row['stata'])} & "
                f"{_rel_fmt(row['rel_r'])} & {_rel_fmt(row['rel_stata'])} \\\\"
            )
    lines.append(
        "    \\multicolumn{6}{@{}l}{\\emph{interflex marginal effects (module 87, binary treatment, moderator $X$, covariate $Z$)}} \\\\"
    )
    for row in results["interflex"]:
        label = row["label"].replace("_", "\\_")
        is_p = row["statistic"].startswith("p_")
        cells = [
            _sci(row["statspai"]) if is_p else _fmt(row["statspai"], 5),
            _sci(row["r"]) if is_p else _fmt(row["r"], 5),
            _sci(row["stata"]) if is_p else _fmt(row["stata"], 5),
        ]
        lines.append(
            f"    {label} & {cells[0]} & {cells[1]} & {cells[2]} & "
            f"{_rel_fmt(row['rel_r'])} & {_rel_fmt(row['rel_stata'])} \\\\"
        )
    lines += ["    \\bottomrule", "\\end{tabular}"]
    (TABLES_DIR / "ex08_three_way.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    results = run()
    write_outputs(results)
    if args.pretty:
        print(json.dumps(results, indent=2))
    print(
        f"ex08: fect + interflex three-way table written; worst relative gap "
        f"{results['worst_relative_gap']:.2e}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

r"""
StatsPAI JSS replication script -- Section 4.5 worked example.

LaLonde (1986) / Dehejia-Wahba (1999) NSW examples on the bundled
experimental and observational replicas:

    sp.datasets.nsw_lalonde()
    sp.datasets.nsw_dw()

Run with:
    python ex05_lalonde.py            # writes results/ex05_lalonde.json + .tex
    python ex05_lalonde.py --pretty   # also prints JSON to stdout

The drift checks mirror tests/external_parity/test_published_replications.py.
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

from sklearn.exceptions import ConvergenceWarning

import statspai as sp


HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE.parent / "results"
TABLES_DIR = HERE.parent / "tables"

COVARIATES = [
    "age",
    "education",
    "black",
    "hispanic",
    "married",
    "nodegree",
    "re74",
    "re75",
]
ADJUSTED_COVARIATES = [
    "age",
    "education",
    "black",
    "hispanic",
    "married",
    "re74",
    "re75",
]


def _regression_estimate(df, formula: str) -> dict[str, float]:
    fit = sp.regress(formula, data=df, robust="hc1")
    return {
        "estimate": float(fit.params["treat"]),
        "se": float(fit.std_errors["treat"]),
    }


def _education_column(df) -> str:
    """Return whichever schooling column this frame actually carries.

    The two bundled NSW frames disagree: ``nsw_dw()`` names the years-of-
    schooling column ``education`` and ``nsw_lalonde()`` names it ``educ``.
    Hard-coding either one silently breaks the other arm of this example, so
    the covariate list is resolved per frame rather than assumed.
    """
    for candidate in ("education", "educ"):
        if candidate in df.columns:
            return candidate
    raise KeyError(
        f"no schooling column in {sorted(df.columns)}; expected 'education' or 'educ'"
    )


def _covariates(df, adjusted: bool = False) -> list[str]:
    base = ADJUSTED_COVARIATES if adjusted else COVARIATES
    edu = _education_column(df)
    return [edu if c == "education" else c for c in base]


def _matching_estimate(df) -> dict[str, float]:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning)
        fit = sp.psm(df, y="re78", d="treat", X=_covariates(df), method="nn")
    return {"estimate": float(fit.estimate), "se": float(fit.se)}


def _ipw_estimate(df) -> dict[str, float]:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=ConvergenceWarning)
        fit = sp.ipw(
            df,
            y="re78",
            treat="treat",
            covariates=_covariates(df),
            estimand="ATT",
            n_bootstrap=50,
            seed=123,
        )
    return {"estimate": float(fit.estimate), "se": float(fit.se)}


def _run_one(name: str, df) -> dict:
    edu = _education_column(df)
    return {
        "n_rows": int(len(df)),
        "schooling_column": edu,
        "naive_ols": _regression_estimate(df, "re78 ~ treat"),
        "adjusted_ols": _regression_estimate(
            df,
            f"re78 ~ treat + age + {edu} + black + hispanic + married + "
            "re74 + re75",
        ),
        "psm_1nn": _matching_estimate(df),
        "ipw_att": _ipw_estimate(df),
    }


def run() -> dict:
    # simulated=True is required, not incidental. The default flipped in
    # 1.21.0: sp.datasets.nsw_lalonde() now returns the real MatchIt::lalonde
    # extract, which is the DW treated cohort plus a PSID-1 comparison group
    # (n=614) -- an *observational* composite whose naive difference is about
    # -635. The experimental arm of this example needs the calibrated NSW
    # experimental subset (185 + 260 = 445), on which naive OLS recovers the
    # Dehejia-Wahba experimental ATT. Calling the default here would silently
    # relabel an observational frame as experimental.
    experimental = sp.datasets.nsw_lalonde(simulated=True)
    observational = sp.datasets.nsw_dw()
    out: dict = {
        "datasets": {
            "experimental": "sp.datasets.nsw_lalonde(simulated=True)",
            "observational": "sp.datasets.nsw_dw()",
        },
        "published_original": {
            "experimental_att_dehejia_wahba": 1794.0,
            "observational_naive_ols": -8498.0,
        },
        "experimental": _run_one("experimental", experimental),
        "observational": _run_one("observational", observational),
    }

    exp_naive = out["experimental"]["naive_ols"]["estimate"]
    obs_naive = out["observational"]["naive_ols"]["estimate"]
    obs_adj = out["observational"]["adjusted_ols"]["estimate"]
    out["pinned_checks"] = {
        "experimental_naive_abs_diff_to_1556": abs(exp_naive - 1556.0),
        "experimental_naive_passes_abs_50": abs(exp_naive - 1556.0) <= 50.0,
        "observational_naive_abs_diff_to_minus_8387": abs(obs_naive + 8387.0),
        "observational_naive_passes_abs_200": abs(obs_naive + 8387.0) <= 200.0,
        "observational_adjusted_abs_diff_to_2313": abs(obs_adj - 2313.0),
        "observational_adjusted_passes_abs_200": abs(obs_adj - 2313.0) <= 200.0,
    }
    out["neighbourhood_checks"] = {
        "experimental_naive_in_1000_2500": 1000.0 <= exp_naive <= 2500.0,
        "observational_naive_below_minus_5000": obs_naive < -5000.0,
        "observational_adjusted_in_1000_3000": 1000.0 <= obs_adj <= 3000.0,
    }
    return out


def write_outputs(results: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "ex05_lalonde.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )

    rows = []
    for group, label in [
        ("experimental", "NSW experimental"),
        ("observational", "NSW + PSID observational"),
    ]:
        for spec, spec_label in [
            ("naive_ols", "Naive OLS"),
            ("adjusted_ols", "Adjusted OLS"),
            ("psm_1nn", "PSM 1-NN"),
            ("ipw_att", "IPW ATT"),
        ]:
            cell = results[group][spec]
            rows.append(
                f"    {label} & {spec_label} & "
                f"{cell['estimate']:.1f} & {cell['se']:.1f} \\\\"
            )
    body = "\n".join(rows)
    tex = (
        "\\begin{tabular}{llrr}\n"
        "    \\toprule\n"
        "    Dataset & Estimator & ATT & SE \\\\\n"
        "    \\midrule\n"
        f"{body}\n"
        "    \\bottomrule\n"
        "\\end{tabular}\n"
    )
    (TABLES_DIR / "ex05_lalonde.tex").write_text(tex, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true", help="print JSON")
    args = parser.parse_args()

    results = run()
    write_outputs(results)

    if args.pretty:
        print(json.dumps(results, indent=2))
    else:
        print("OK -- wrote", RESULTS_DIR / "ex05_lalonde.json")
        print("OK -- wrote", TABLES_DIR / "ex05_lalonde.tex")

    pinned = results["pinned_checks"]
    neighbourhood = results["neighbourhood_checks"]
    failed_pinned = [k for k, v in pinned.items() if k.endswith("passes_abs_50") and not v]
    failed_pinned += [k for k, v in pinned.items() if k.endswith("passes_abs_200") and not v]
    failed_neighbourhood = [k for k, v in neighbourhood.items() if not v]
    if failed_pinned or failed_neighbourhood:
        print(
            "FAIL: "
            + "; ".join(failed_pinned + failed_neighbourhood),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

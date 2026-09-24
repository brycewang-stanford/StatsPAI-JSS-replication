"""Generate the Track A methodological-gap ledger for the JSS audit."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:  # _paths.py sits beside this script; importlib loaders do not add the script dir
    sys.path.insert(0, _SCRIPTS_DIR)

from _paths import PAPER_ROOT as _PAPER_ROOT
from _paths import statspai_root as _statspai_root

HERE = Path(__file__).resolve().parent
PAPER_DIR = _PAPER_ROOT
ROOT = _statspai_root()  # see _paths.py: worktree-safe
PARITY_TABLE = ROOT / "tests" / "r_parity" / "results" / "parity_table_3way.md"
RESULTS_DIR = PAPER_DIR / "replication" / "results"
OUT_JSON = RESULTS_DIR / "methodological_gap_ledger.json"
OUT_MD = RESULTS_DIR / "methodological_gap_ledger.md"
SOURCE_DATE_EPOCH = os.environ.get("SOURCE_DATE_EPOCH")


def _generated_at_unix() -> int:
    if SOURCE_DATE_EPOCH is not None:
        return int(SOURCE_DATE_EPOCH)
    return int(time.time())


ACTION_REGISTRY = {
    "07_scm": {
        "category": "classical_scm_reference_disagreement",
        "reviewer_risk": "Basque donor weights are not uniquely identified; R Synth and Stata synth choose measurably different optima, so native-vs-Synth equality is the wrong claim.",
        "next_action": "Keep the native Basque row as a T4 disclosure with deterministic multi-start diagnostics; use module 52_scm_unique and backend='synth' to separate solver correctness from exact Synth-number reproduction.",
    },
    "13_causal_forest": {
        "category": "stochastic_forest_aipw_pass",
        "reviewer_risk": "AIPW ATE/ATT parity is stochastic and should not be sold as deterministic equality.",
        "next_action": "Keep the T3 combined-MC-error criterion visible; promote only to T2 after a deterministic/common-random-number cross-language fixture exists.",
    },
}

EXPECTED_METADATA = {
    "07_scm": {
        "validation_tier": "identification_dependent_native",
        "reference_backend": "Synth",
        # 0f4b9e2b: winning start relabelled regression -> dirichlet_3; the two
        # starts tie to 1e-12 and the optimum is unchanged (CHANGELOG [Unreleased]).
        "solver_best_start": "dirichlet_3",
        "solver_near_best_start_count": "4",
        "solver_near_best_weight_class_count": "2",
        "solver_near_best_weight_l1_max": "0.00513",
        "weight_solution_nonunique": "True",
    },
}

NON_CIRCULAR_GUARDS = {
    "07_scm": {
        "path": "tests/r_parity/52_scm_unique.py",
        "snippet": "unique convex-hull SCM",
        "evidence": "module 52 certifies the native classical-SCM solver on a uniquely identified convex-hull DGP",
    },
}

REFERENCE_DISAGREEMENT_GUARDS = {
    "07_scm": {
        "statistic": "avg_post_gap",
        "py_stata_rel_max": 1e-3,
        "r_stata_rel_min": 1e-2,
        "evidence": (
            "native tracks Stata synth on the same ADH special-predictor "
            "spec, while R Synth and Stata synth choose measurably different "
            "local optima"
        ),
    },
}


def _clean(value: str) -> str:
    value = value.strip()
    if value.startswith("`") and value.endswith("`"):
        return value[1:-1]
    return value


def _parse_number(value: str) -> float | None:
    value = value.strip()
    if value in {"", "—", "---"}:
        return None
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return None


def _parse_representative_row(row: str) -> dict[str, Any] | None:
    cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
    if len(cells) < 6:
        return None
    statistic = cells[0].strip().strip("`")
    py_est = _parse_number(cells[1])
    r_est = _parse_number(cells[2])
    stata_est = _parse_number(cells[3])
    rel_py_r = _parse_number(cells[4])
    rel_py_stata = _parse_number(cells[5])
    if py_est is None or r_est is None or stata_est is None:
        return None
    denom = abs(stata_est) if abs(stata_est) > 1e-12 else 1.0
    return {
        "statistic": statistic,
        "py_est": py_est,
        "r_est": r_est,
        "stata_est": stata_est,
        "py_r_rel": rel_py_r,
        "py_stata_rel": rel_py_stata,
        "r_stata_rel": abs(r_est - stata_est) / denom,
    }


def _reference_disagreement_guard(
    module: dict[str, Any],
    guard: dict[str, Any],
) -> dict[str, Any]:
    parsed_rows = [
        parsed
        for row in module["representative_rows"]
        if (parsed := _parse_representative_row(row)) is not None
    ]
    target = next(
        (row for row in parsed_rows if row["statistic"] == guard["statistic"]),
        None,
    )
    if target is None:
        return {
            **guard,
            "ok": False,
            "observed": None,
            "failure": f"{guard['statistic']} row was not parseable",
        }

    py_stata_ok = (
        target["py_stata_rel"] is not None
        and target["py_stata_rel"] <= guard["py_stata_rel_max"]
    )
    r_stata_ok = target["r_stata_rel"] >= guard["r_stata_rel_min"]
    ok = py_stata_ok and r_stata_ok
    return {
        **guard,
        "observed": target,
        "py_stata_ok": py_stata_ok,
        "r_stata_ok": r_stata_ok,
        "ok": ok,
        "failure": (
            ""
            if ok
            else (
                f"expected py-Stata rel <= {guard['py_stata_rel_max']} and "
                f"R-Stata rel >= {guard['r_stata_rel_min']}, observed "
                f"py-Stata rel={target['py_stata_rel']}, "
                f"R-Stata rel={target['r_stata_rel']}"
            )
        ),
    }


def _parse_blocks(text: str) -> list[dict[str, Any]]:
    modules: list[dict[str, Any]] = []
    pattern = re.compile(
        r"^## Module (?P<module>[^\n]+)\n(?P<body>.*?)(?=^## Module |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    field_pattern = re.compile(
        r"^- \*\*(?P<key>[^*]+)\*\*: (?P<value>.*)$", re.MULTILINE
    )
    for match in pattern.finditer(text):
        module = match.group("module").strip()
        body = match.group("body")
        fields = {
            item.group("key").strip(): _clean(item.group("value"))
            for item in field_pattern.finditer(body)
        }
        strictness = fields.get("strictness_tier", "")
        declared_tier = fields.get("tier", "")
        native_note = fields.get("native_note", "")
        is_methodological = (
            "`methodological`" in strictness
            or strictness.startswith("methodological")
            or declared_tier == "T4"
            or "not a parity pass" in native_note
        )
        if not is_methodological:
            continue
        rows = [
            line
            for line in body.splitlines()
            if line.startswith("| `") and " rel " not in line
        ]
        modules.append(
            {
                "module": module,
                "name": module.split("_", 1)[1] if "_" in module else module,
                "strictness_tier": "methodological",
                "fields": fields,
                "evidence_notes": {
                    key: value
                    for key, value in fields.items()
                    if key == "note" or key.endswith("_note") or key.endswith("_gap")
                },
                "representative_rows": rows[:3],
            }
        )
    return modules


def main() -> int:
    if not PARITY_TABLE.exists():
        print(f"FAIL -- parity table not found: {PARITY_TABLE}", file=sys.stderr)
        return 1

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    modules = _parse_blocks(PARITY_TABLE.read_text(encoding="utf-8"))
    failures: list[str] = []
    ledger: list[dict[str, Any]] = []

    for module in modules:
        action = ACTION_REGISTRY.get(module["module"])
        if action is None:
            failures.append(f"unclassified methodological/T4 gap: {module['module']}")
            action = {
                "category": "unclassified",
                "reviewer_risk": "No reviewer-risk classification has been registered.",
                "next_action": "Classify this methodological/T4 row before submission.",
            }
        if not module["evidence_notes"]:
            failures.append(
                f"{module['module']} lacks a note/gap field in the parity table"
            )
        expected_metadata = EXPECTED_METADATA.get(module["module"], {})
        metadata_checks = []
        for key, expected in expected_metadata.items():
            observed = module["fields"].get(key)
            ok = observed == expected
            metadata_checks.append(
                {
                    "field": key,
                    "expected": expected,
                    "observed": observed,
                    "ok": ok,
                }
            )
            if not ok:
                failures.append(
                    f"{module['module']} lacks {key}={expected!r} "
                    f"(observed {observed!r})"
                )
        module["metadata_checks"] = metadata_checks
        guard = NON_CIRCULAR_GUARDS.get(module["module"])
        if guard is not None:
            guard_path = ROOT / guard["path"]
            guard_ok = guard_path.exists() and guard["snippet"] in guard_path.read_text(
                encoding="utf-8"
            )
            module["non_circular_guard"] = {
                **guard,
                "ok": guard_ok,
            }
            if not guard_ok:
                failures.append(
                    f"{module['module']} lacks non-circular guard "
                    f"{guard['path']}::{guard['snippet']}"
                )
        else:
            module["non_circular_guard"] = None
        ref_guard = REFERENCE_DISAGREEMENT_GUARDS.get(module["module"])
        if ref_guard is not None:
            guard_result = _reference_disagreement_guard(module, ref_guard)
            module["reference_disagreement_guard"] = guard_result
            if not guard_result["ok"]:
                failures.append(
                    f"{module['module']} lacks reference-disagreement guard: "
                    f"{guard_result['failure']}"
                )
        else:
            module["reference_disagreement_guard"] = None
        ledger.append({**module, **action})

    categories = Counter(row["category"] for row in ledger)
    status = "PASS" if not failures else "FAIL"
    result = {
        "generated_at_unix": _generated_at_unix(),
        "status": status,
        "source": str(PARITY_TABLE.relative_to(ROOT)),
        "summary": {
            "methodological_gap_count": len(ledger),
            "classified_gap_count": sum(
                row["category"] != "unclassified" for row in ledger
            ),
            "uncategorized_gap_count": sum(
                row["category"] == "unclassified" for row in ledger
            ),
            "metadata_guard_count": sum(len(row["metadata_checks"]) for row in ledger),
            "metadata_guard_failures": sum(
                not check["ok"] for row in ledger for check in row["metadata_checks"]
            ),
            "non_circular_guard_count": sum(
                row["non_circular_guard"] is not None for row in ledger
            ),
            "non_circular_guard_failures": sum(
                row["non_circular_guard"] is not None
                and not row["non_circular_guard"]["ok"]
                for row in ledger
            ),
            "reference_disagreement_guard_count": sum(
                row["reference_disagreement_guard"] is not None for row in ledger
            ),
            "reference_disagreement_guard_failures": sum(
                row["reference_disagreement_guard"] is not None
                and not row["reference_disagreement_guard"]["ok"]
                for row in ledger
            ),
            "category_counts": dict(sorted(categories.items())),
        },
        "failures": failures,
        "ledger": ledger,
    }
    OUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Track A Methodological-Gap Ledger",
        "",
        f"Status: {status}",
        f"Source: `{result['source']}`",
        f"Methodological/T4 rows: {len(ledger)}",
        f"Uncategorized gaps: {result['summary']['uncategorized_gap_count']}",
        "",
        "These rows are methodological/T4 Track A disclosures, not strict cross-language equality passes.",
        "Each row must have an explicit reviewer-risk classification and a concrete",
        "promotion path before the paper can describe it as deterministic T2 evidence.",
        "",
        "| Module | Category | Required metadata | Non-circular native guard | Reference disagreement guard | Reviewer risk | Next action |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in ledger:
        metadata = (
            "; ".join(
                f"{check['field']}=`{check['observed']}`"
                for check in row["metadata_checks"]
            )
            or "not required"
        )
        guard = row["non_circular_guard"]
        guard_text = (
            f"{guard['path']}::{guard['snippet']} ({guard['evidence']})"
            if guard is not None
            else "not required"
        )
        ref_guard = row["reference_disagreement_guard"]
        if ref_guard is None:
            ref_guard_text = "not required"
        elif ref_guard["observed"] is None:
            ref_guard_text = f"{ref_guard['statistic']}: missing/parse failed"
        else:
            observed = ref_guard["observed"]
            ref_guard_text = (
                f"{ref_guard['statistic']}: "
                f"py-Stata rel={observed['py_stata_rel']:.3g} "
                f"(max {ref_guard['py_stata_rel_max']:.1g}); "
                f"R-Stata rel={observed['r_stata_rel']:.3g} "
                f"(min {ref_guard['r_stata_rel_min']:.1g}); "
                f"{ref_guard['evidence']}"
            )
        lines.append(
            f"| `{row['module']}` | `{row['category']}` | "
            f"{metadata} | {guard_text} | "
            f"{ref_guard_text} | "
            f"{row['reviewer_risk']} | {row['next_action']} |"
        )
    if failures:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {failure}" for failure in failures)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"OK -- wrote {OUT_JSON}")
    print(f"OK -- wrote {OUT_MD}")
    if failures:
        print("FAIL -- methodological-gap ledger failed", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

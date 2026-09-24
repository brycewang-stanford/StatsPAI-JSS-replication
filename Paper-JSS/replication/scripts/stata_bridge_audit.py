"""Audit frozen Stata bridge artifacts without requiring a Stata license."""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:  # _paths.py sits beside this script; importlib loaders do not add the script dir
    sys.path.insert(0, _SCRIPTS_DIR)

from _paths import PAPER_ROOT as _PAPER_ROOT
from _paths import expected_stata_module_count as _expected_stata
from _paths import statspai_root as _statspai_root


HERE = Path(__file__).resolve().parent
PAPER_DIR = _PAPER_ROOT
ROOT = _statspai_root()  # see _paths.py: worktree-safe
STATA_DIR = ROOT / "tests" / "stata_parity"
STATA_RESULTS = STATA_DIR / "results"
R_RESULTS = ROOT / "tests" / "r_parity" / "results"
OUT_JSON = PAPER_DIR / "replication" / "results" / "stata_bridge_audit.json"
OUT_MD = PAPER_DIR / "replication" / "results" / "stata_bridge_audit.md"
SOURCE_DATE_EPOCH = os.environ.get("SOURCE_DATE_EPOCH")


def _generated_at_unix() -> int:
    if SOURCE_DATE_EPOCH is not None:
        return int(SOURCE_DATE_EPOCH)
    return int(time.time())

EXPECTED_STATA_MODULES = _expected_stata()
EXPECTED_R_JOINED_MODULES = EXPECTED_STATA_MODULES
EXPECTED_PY_STATA_ONLY: set[str] = set()
PENDING_STATA_BRIDGE_MODULES: set[str] = set()
PROVENANCE_KEYS = {
    "stata_version",
    "edition",
    "os",
    "machine_type",
    "born_date",
    "captured_via",
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _module_from_result(path: Path) -> str:
    return path.name.removesuffix("_Stata.json")


def _reproduces_status_count(report: str) -> int:
    """Count reproduced module rows without depending on Unicode status icons."""
    return sum(
        1
        for line in report.splitlines()
        if line.startswith("| `") and "reproduces" in line
    )


def main() -> int:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []

    do_modules = {path.stem for path in STATA_DIR.glob("[0-9][0-9]_*.do")}
    result_paths = sorted(STATA_RESULTS.glob("*_Stata.json"))
    result_modules = {_module_from_result(path) for path in result_paths}

    missing_json = sorted(do_modules - result_modules - PENDING_STATA_BRIDGE_MODULES)
    pending_json = sorted((do_modules - result_modules) & PENDING_STATA_BRIDGE_MODULES)
    missing_do = sorted(result_modules - do_modules)
    if missing_json:
        failures.append("Stata do-files without frozen JSON: " + ", ".join(missing_json))
    if missing_do:
        failures.append("Frozen Stata JSONs without do-files: " + ", ".join(missing_do))
    if len(result_modules) != EXPECTED_STATA_MODULES:
        failures.append(
            f"expected {EXPECTED_STATA_MODULES} Stata modules, found {len(result_modules)}"
        )

    for path in result_paths:
        module = _module_from_result(path)
        try:
            payload = _load_json(path)
        except json.JSONDecodeError as exc:
            failures.append(f"{path.relative_to(ROOT)} is not valid JSON: {exc}")
            continue
        rows_payload = payload.get("rows", [])
        extra = payload.get("extra", {}) or {}
        provenance = payload.get("provenance", {}) or {}
        missing_prov = sorted(PROVENANCE_KEYS - set(provenance))
        has_r_reference = (R_RESULTS / f"{module}_R.json").exists()
        has_py_reference = (R_RESULTS / f"{module}_py.json").exists()

        if payload.get("side") != "Stata":
            failures.append(f"{path.relative_to(ROOT)} side is not 'Stata'")
        if not rows_payload:
            failures.append(f"{path.relative_to(ROOT)} has no rows")
        if missing_prov:
            failures.append(
                f"{path.relative_to(ROOT)} missing provenance keys: "
                + ", ".join(missing_prov)
            )
        if provenance.get("captured_via") != "tests/stata_parity/_common.do::stata_parity_close":
            failures.append(f"{path.relative_to(ROOT)} has unexpected captured_via")
        if not has_py_reference:
            failures.append(f"{module} has no Python-side parity JSON")
        if not has_r_reference and module not in EXPECTED_PY_STATA_ONLY:
            failures.append(f"{module} is missing R-side JSON but is not registered Py-Stata-only")
        if has_r_reference and module in EXPECTED_PY_STATA_ONLY:
            failures.append(f"{module} is registered Py-Stata-only but has an R-side JSON")
        if (
            "stata_command" not in extra
            and "identification_note" not in extra
            and "stata_bridge_status" not in extra
        ):
            warnings.append(
                f"{module} has neither stata_command, identification_note, "
                "nor stata_bridge_status"
            )

        rows.append(
            {
                "module": module,
                "row_count": len(rows_payload),
                "has_do_file": module in do_modules,
                "has_python_reference": has_py_reference,
                "has_r_reference": has_r_reference,
                "py_stata_only": module in EXPECTED_PY_STATA_ONLY,
                "stata_version": provenance.get("stata_version"),
                "edition": provenance.get("edition"),
                "stata_command": extra.get("stata_command") or "",
                "identification_note": extra.get("identification_note") or "",
                "stata_bridge_status": extra.get("stata_bridge_status") or "",
                "stata_algorithm": extra.get("stata_algorithm") or "",
            }
        )

    r_joined = [row for row in rows if row["has_r_reference"]]
    py_stata_only = [row for row in rows if row["py_stata_only"]]
    if len(r_joined) != EXPECTED_R_JOINED_MODULES:
        failures.append(
            f"expected {EXPECTED_R_JOINED_MODULES} R-joined Stata modules, found {len(r_joined)}"
        )
    if {row["module"] for row in py_stata_only} != EXPECTED_PY_STATA_ONLY:
        failures.append(
            "Py-Stata-only module set mismatch: "
            + ", ".join(sorted(row["module"] for row in py_stata_only))
        )

    repro_report = STATA_RESULTS / "REPRODUCIBILITY_REPORT_STATA.md"
    report_text = repro_report.read_text(encoding="utf-8") if repro_report.exists() else ""
    if not report_text:
        failures.append("Stata reproducibility report is missing")
    else:
        reproduced_count = _reproduces_status_count(report_text)
        if reproduced_count != EXPECTED_STATA_MODULES:
            failures.append(
                f"Stata reproducibility report lists {reproduced_count} reproduced modules, "
                f"expected {EXPECTED_STATA_MODULES}"
            )
        if "DRIFT" in report_text:
            failures.append("Stata reproducibility report contains drift markers")

    env_manifest = STATA_DIR / "STATA_ENVIRONMENT.md"
    if not env_manifest.exists():
        failures.append("STATA_ENVIRONMENT.md is missing")
    else:
        env_text = env_manifest.read_text(encoding="utf-8")
        for required in ("Stata 18", "Edition | MP", "rddensity", "rdrobust"):
            if required not in env_text:
                failures.append(f"STATA_ENVIRONMENT.md missing {required!r}")

    status = "PASS" if not failures else "FAIL"
    result = {
        "generated_at_unix": _generated_at_unix(),
        "status": status,
        "summary": {
            "stata_modules": len(result_modules),
            "r_joined_stata_modules": len(r_joined),
            "py_stata_only_modules": sorted(row["module"] for row in py_stata_only),
            "do_files": len(do_modules),
            "pending_bridge_scripts": pending_json,
            "result_files": len(result_paths),
            "repro_report_modules": (
                _reproduces_status_count(report_text) if report_text else 0
            ),
            "license_boundary": (
                "Frozen JSON/do-file/provenance audit only; re-running Stata "
                "requires a separate Stata license."
            ),
        },
        "failures": failures,
        "warnings": warnings,
        "modules": rows,
    }
    OUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Stata Bridge Audit",
        "",
        f"Status: {status}",
        f"Stata modules: {len(result_modules)}",
        f"R-joined Stata modules: {len(r_joined)}",
        "Py-Stata-only migration modules: "
        + (
            ", ".join(f"`{name}`" for name in result["summary"]["py_stata_only_modules"])
            if result["summary"]["py_stata_only_modules"]
            else "none"
        ),
        "Pending scripted bridges: "
        + (
            ", ".join(f"`{name}`" for name in pending_json)
            if pending_json
            else "none"
        ),
        f"Reproducibility-report modules: {result['summary']['repro_report_modules']}",
        "",
        "This audit does not require Stata. It verifies the frozen Stata bridge:",
        "each `_Stata.json` must have a matching `.do` file, non-empty rows,",
        "inline engine provenance, and a committed reproducibility-report row.",
        "Re-running the Stata commands remains optional because it requires a",
        "separate Stata license.",
        "",
        "| Module | Rows | Join | Stata | Command / note |",
        "|---|---:|---|---|---|",
    ]
    for row in sorted(rows, key=lambda item: item["module"]):
        join = "R+Stata" if row["has_r_reference"] else "Py-Stata-only"
        command = (
            row.get("stata_command")
            or row.get("identification_note")
            or row.get("stata_algorithm")
            or row.get("stata_bridge_status")
            or ""
        )
        command = command.replace("|", "\\|")
        lines.append(
            f"| `{row['module']}` | {row['row_count']} | {join} | "
            f"{row.get('stata_version') or 'n/a'} {row.get('edition') or 'n/a'} | "
            f"{command} |"
        )
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    if failures:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {failure}" for failure in failures)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"OK -- wrote {OUT_JSON}")
    print(f"OK -- wrote {OUT_MD}")
    if failures:
        print("FAIL -- Stata bridge audit failed", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

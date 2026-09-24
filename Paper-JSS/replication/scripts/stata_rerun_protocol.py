"""Write the optional licensed Stata Tier-3 rerun protocol.

The JSS archive includes frozen Stata JSON/do/provenance evidence, but a live
Stata rerun requires a separate Stata license. This protocol makes the optional
rerun path concrete without treating the absence of Stata as a JSS upload
failure or claiming that this machine has completed a fresh licensed rerun.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

import sys
_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:  # _paths.py sits beside this script; importlib loaders do not add the script dir
    sys.path.insert(0, _SCRIPTS_DIR)

from _paths import PAPER_ROOT as _PAPER_ROOT
from _paths import expected_stata_module_count as _expected_stata
from _paths import statspai_root as _statspai_root


HERE = Path(__file__).resolve().parent
PAPER_DIR = _PAPER_ROOT
ROOT = _statspai_root()  # see _paths.py: worktree-safe
RESULTS_DIR = PAPER_DIR / "replication" / "results"
STATA_DIR = ROOT / "tests" / "stata_parity"
STATA_ENV = STATA_DIR / "STATA_ENVIRONMENT.md"
STATA_VERIFY = STATA_DIR / "verify_reproduce_stata.py"
STATA_REPRO_REPORT = STATA_DIR / "results" / "REPRODUCIBILITY_REPORT_STATA.md"
STATA_BRIDGE_JSON = RESULTS_DIR / "stata_bridge_audit.json"
REPRO_ENV_JSON = RESULTS_DIR / "reproduction_environment_audit.json"
OUT_JSON = RESULTS_DIR / "stata_rerun_protocol.json"
OUT_MD = RESULTS_DIR / "stata_rerun_protocol.md"
SOURCE_DATE_EPOCH = os.environ.get("SOURCE_DATE_EPOCH")
EXPECTED_STATA_MODULES = _expected_stata()


def _generated_at_unix() -> int:
    if SOURCE_DATE_EPOCH is not None:
        return int(SOURCE_DATE_EPOCH)
    return int(time.time())


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _repro_report_counts(text: str) -> dict[str, int]:
    rows = [
        line for line in text.splitlines()
        if line.startswith("| `") and " | " in line
    ]
    return {
        "rows": len(rows),
        "reproduced": sum(1 for line in rows if "reproduces" in line),
        "non_reproduced": sum(1 for line in rows if "reproduces" not in line),
    }


def _commands() -> list[dict[str, str]]:
    return [
        {
            "id": "paper_tier3_driver",
            "cwd": "Paper-JSS",
            "command": (
                "STATA_EXE=/path/to/stata-mp ../.venv/bin/python "
                "replication/reproduce.py --tier 3"
            ),
            "purpose": (
                "Runs Tier 1, Tier 2 if R is available, and the licensed "
                "Stata verifier through the paper reproduction driver."
            ),
        },
        {
            "id": "direct_stata_verifier",
            "cwd": "repository root",
            "command": (
                "STATA_EXE=/path/to/stata-mp .venv/bin/python "
                "tests/stata_parity/verify_reproduce_stata.py"
            ),
            "purpose": (
                "Runs only the Stata parity verifier and rewrites the "
                "Stata reproducibility report from staged fresh outputs."
            ),
        },
        {
            "id": "refresh_stata_environment_note",
            "cwd": "repository root",
            "command": (
                "stata-mp -q -b do tests/stata_parity/_capture_stata_env.do && "
                ".venv/bin/python tests/stata_parity/_gen_stata_env.py"
            ),
            "purpose": (
                "Optional: refreshes the Stata engine/ado inventory when a "
                "reviewer reruns under a different licensed Stata installation."
            ),
        },
        {
            "id": "audit_frozen_bridge",
            "cwd": "Paper-JSS",
            "command": "make stata-bridge-audit PYTHON=../.venv/bin/python",
            "purpose": (
                "Checks the frozen JSON/do/provenance bundle without requiring "
                "Stata; this remains the JSS upload evidence."
            ),
        },
    ]


def _checklist() -> list[dict[str, str]]:
    return [
        {
            "id": "confirm_license",
            "action": (
                "Confirm that a licensed Stata executable is available and "
                "record the executable path used as STATA_EXE."
            ),
            "expected_record": "STATA_EXE path and Stata edition/version",
        },
        {
            "id": "inspect_environment",
            "action": (
                "Read tests/stata_parity/STATA_ENVIRONMENT.md and decide "
                "whether to refresh the local ado inventory before rerunning."
            ),
            "expected_record": "whether environment note was refreshed",
        },
        {
            "id": "run_tier3_or_direct_verifier",
            "action": (
                "Run either the Paper-JSS Tier-3 driver or the direct "
                "tests/stata_parity/verify_reproduce_stata.py command."
            ),
            "expected_record": "command, exit code, and elapsed time",
        },
        {
            "id": "compare_report_counts",
            "action": (
                f"Confirm that REPRODUCIBILITY_REPORT_STATA.md lists "
                f"{EXPECTED_STATA_MODULES}/{EXPECTED_STATA_MODULES} "
                "reproduced modules and zero non-reproduced rows."
            ),
            "expected_record": "reproduced/non-reproduced counts",
        },
        {
            "id": "inspect_drift_rows",
            "action": (
                "If any row drifts, inspect the module, Stata version, ado "
                "version, tolerance override, and generated log before changing "
                "golden JSON."
            ),
            "expected_record": "drift rationale or 'none'",
        },
        {
            "id": "preserve_golden_files",
            "action": (
                "Do not overwrite committed *_Stata.json golden files unless "
                "the drift is explained and the manuscript/audits are refreshed "
                "in the same reviewed change."
            ),
            "expected_record": "golden files unchanged or justified refresh",
        },
        {
            "id": "interpret_missing_stata",
            "action": (
                "If Stata is absent, record an optional-runtime skip rather "
                "than a JSS upload failure; no Section 4-7 headline number "
                "depends on live Stata."
            ),
            "expected_record": "skip reason if applicable",
        },
        {
            "id": "rerun_jss_gates",
            "action": (
                "After any accepted Stata rerun update, rerun the Stata bridge "
                "audit and the JSS submission package verifier."
            ),
            "expected_record": "audit/verifier command results",
        },
    ]


def _build_payload() -> dict[str, Any]:
    failures: list[str] = []
    bridge: dict[str, Any] = {}
    repro: dict[str, Any] = {}

    if not STATA_BRIDGE_JSON.exists():
        failures.append(
            f"missing Stata bridge audit: {STATA_BRIDGE_JSON.relative_to(PAPER_DIR)}"
        )
    else:
        bridge = _read_json(STATA_BRIDGE_JSON)
        summary = bridge.get("summary", {})
        if bridge.get("status") != "PASS":
            failures.append("stata_bridge_audit.json is not PASS")
        if summary.get("stata_modules") != EXPECTED_STATA_MODULES:
            failures.append("stata_bridge_audit has stale Stata module count")
        if summary.get("r_joined_stata_modules") != EXPECTED_STATA_MODULES:
            failures.append("stata_bridge_audit has stale R-joined Stata count")
        if summary.get("py_stata_only_modules") not in ([], None):
            failures.append("stata_bridge_audit reports Py-Stata-only modules")
        if summary.get("repro_report_modules") != EXPECTED_STATA_MODULES:
            failures.append("stata_bridge_audit has stale reproducibility-report count")
        if "separate Stata license" not in str(summary.get("license_boundary")):
            failures.append("stata_bridge_audit lost the Stata license boundary")

    if not REPRO_ENV_JSON.exists():
        failures.append(
            "missing reproduction environment audit: "
            f"{REPRO_ENV_JSON.relative_to(PAPER_DIR)}"
        )
    else:
        repro = _read_json(REPRO_ENV_JSON)
        contract = repro.get("stata_live_rerun_contract", {})
        if repro.get("status") != "PASS":
            failures.append("reproduction_environment_audit.json is not PASS")
        if repro.get("stata_reproduced_modules") != EXPECTED_STATA_MODULES:
            failures.append("reproduction environment has stale Stata module count")
        if repro.get("stata_repro_report_non_reproduced_rows") not in (0, None):
            failures.append("reproduction environment reports Stata drift rows")
        if contract.get("stata_verify_script_present") is not True:
            failures.append("Stata verifier script is missing")
        if contract.get("stata_verify_uses_stata_exe") is not True:
            failures.append("Stata verifier does not use STATA_EXE")
        if contract.get("stata_verify_missing_runtime_returns_skip") is not True:
            failures.append("Stata verifier missing-runtime skip is not explicit")
        if repro.get("tier1_transcript_no_r_stata") is not True:
            failures.append("Tier-1 no-R/no-Stata headline boundary is stale")

    env_text = _read(STATA_ENV) if STATA_ENV.exists() else ""
    verify_text = _read(STATA_VERIFY) if STATA_VERIFY.exists() else ""
    report_text = _read(STATA_REPRO_REPORT) if STATA_REPRO_REPORT.exists() else ""
    if not env_text:
        failures.append("STATA_ENVIRONMENT.md is missing")
    else:
        for snippet in ("Stata 18", "Edition | MP", "verify_reproduce_stata.py"):
            if snippet not in env_text:
                failures.append(f"STATA_ENVIRONMENT.md missing {snippet!r}")
    if not verify_text:
        failures.append("verify_reproduce_stata.py is missing")
    else:
        for snippet in ("STATA_EXE", "STATSPAI_STATA_PARITY_RESULTS", "REPRO_TOL_OVERRIDE"):
            if snippet not in verify_text:
                failures.append(f"verify_reproduce_stata.py missing {snippet!r}")
    report_counts = _repro_report_counts(report_text) if report_text else {
        "rows": 0,
        "reproduced": 0,
        "non_reproduced": 0,
    }
    if report_counts["reproduced"] != EXPECTED_STATA_MODULES:
        failures.append("Stata reproducibility report has stale reproduced count")
    if report_counts["non_reproduced"] != 0:
        failures.append("Stata reproducibility report contains non-reproduced rows")

    boundary = {
        "requires_stata_license": True,
        "jss_upload_blocking": False,
        "absence_of_stata_is_optional_skip": True,
        "claimed_current_machine_live_rerun": False,
        "frozen_json_do_provenance_is_upload_evidence": True,
        "no_section_4_7_headline_depends_on_live_stata": True,
        "expected_stata_modules": EXPECTED_STATA_MODULES,
    }
    summary = {
        "stata_bridge_status": bridge.get("status"),
        "reproduction_environment_status": repro.get("status"),
        "stata_modules": bridge.get("summary", {}).get("stata_modules"),
        "r_joined_stata_modules": (
            bridge.get("summary", {}).get("r_joined_stata_modules")
        ),
        "repro_report_modules": bridge.get("summary", {}).get("repro_report_modules"),
        "reproduced_report_rows": report_counts["reproduced"],
        "non_reproduced_report_rows": report_counts["non_reproduced"],
        "checklist_item_count": len(_checklist()),
        "command_count": len(_commands()),
        **boundary,
    }
    return {
        "generated_at_unix": _generated_at_unix(),
        "status": "PASS" if not failures else "FAIL",
        "scope": (
            "Optional licensed Stata Tier-3 rerun protocol; the JSS upload "
            "evidence remains the frozen JSON/do/provenance bundle."
        ),
        "boundary": boundary,
        "summary": summary,
        "commands": _commands(),
        "checklist": _checklist(),
        "primary_evidence": [
            "replication/results/stata_bridge_audit.md",
            "replication/results/reproduction_environment_audit.md",
            "tests/stata_parity/STATA_ENVIRONMENT.md",
            "tests/stata_parity/verify_reproduce_stata.py",
            "tests/stata_parity/results/REPRODUCIBILITY_REPORT_STATA.md",
        ],
        "failures": failures,
    }


def _escape_md_cell(value: object) -> str:
    return str(value).replace("|", r"\|").replace("\n", " ")


def _write_markdown(payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    boundary = payload["boundary"]
    lines = [
        "# Stata Tier-3 Rerun Protocol",
        "",
        f"Status: {payload['status']}",
        "",
        payload["scope"],
        "This generated file does not require Stata, does not mark absence of "
        "Stata as a JSS upload failure, and does not claim that this machine "
        "has completed a fresh licensed rerun.",
        "",
        "## Boundary",
        "",
    ]
    for key, value in boundary.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Commands",
            "",
            "| ID | CWD | Command | Purpose |",
            "|---|---|---|---|",
        ]
    )
    for item in payload["commands"]:
        lines.append(
            "| "
            f"`{item['id']}` | "
            f"`{item['cwd']}` | "
            f"`{item['command']}` | "
            f"{_escape_md_cell(item['purpose'])} |"
        )
    lines.extend(
        [
            "",
            "## Checklist",
            "",
            "| Item | Action | Record |",
            "|---|---|---|",
        ]
    )
    for item in payload["checklist"]:
        lines.append(
            "| "
            f"`{item['id']}` | "
            f"{_escape_md_cell(item['action'])} | "
            f"{_escape_md_cell(item['expected_record'])} |"
        )
    lines.extend(["", "## Metrics", ""])
    for key, value in summary.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    if payload["failures"]:
        lines.append("Failures:")
        lines.extend(f"- {failure}" for failure in payload["failures"])
    else:
        lines.append("Failures: none")
    lines.extend(
        [
            "",
            f"Machine-readable detail: `{OUT_JSON.relative_to(PAPER_DIR)}`",
        ]
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = _build_payload()
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(payload)
    print(f"OK -- wrote {OUT_JSON}")
    print(f"OK -- wrote {OUT_MD}")
    if payload["failures"]:
        print("FAIL -- Stata Tier-3 rerun protocol has stale or missing evidence")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

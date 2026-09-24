"""Triage high-ROI experiments and reproduction checks for the JSS submission.

This report does not create new statistical claims.  It makes the current
reviewer-facing boundary explicit: which checks are implemented in the JSS
packet, which require external runtimes, which belong to a later behavioural
benchmark, and which are final release-cut work rather than upload blockers.
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
from _paths import expected_r_module_count as _expected_r
from _paths import statspai_root as _statspai_root


HERE = Path(__file__).resolve().parent
PAPER_DIR = _PAPER_ROOT
ROOT = _statspai_root()  # see _paths.py: worktree-safe
RESULTS_DIR = PAPER_DIR / "replication" / "results"
OUT_JSON = RESULTS_DIR / "experiment_triage.json"
OUT_MD = RESULTS_DIR / "experiment_triage.md"
SOURCE_DATE_EPOCH = os.environ.get("SOURCE_DATE_EPOCH")

EXPECTED_ITEM_IDS = (
    "cross_language_parity",
    "monte_carlo_validation",
    "performance_benchmark",
    "tier1_reproduction",
    "live_stata_rerun",
    "behavioural_agent_benchmark",
    "full_registry_numeric_validation",
    "final_tagged_release",
)


def _generated_at_unix() -> int:
    if SOURCE_DATE_EPOCH is not None:
        return int(SOURCE_DATE_EPOCH)
    return int(time.time())


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def _status(payload: dict[str, Any]) -> str | None:
    return payload.get("status")


def _count_perf_modules() -> int:
    perf_dir = ROOT / "tests" / "perf" / "results"
    return len(list(perf_dir.glob("*_py.json")))


def _tier1_step_summary(path: Path) -> str:
    if not path.exists():
        return "missing"
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"([0-9]+/[0-9]+)\s+steps passed", text)
    if match:
        return match.group(1)
    match = re.search(r"([0-9]+/[0-9]+)\s+successful steps", text)
    return match.group(1) if match else "unknown"


def _item(
    *,
    item_id: str,
    question: str,
    classification: str,
    answer: str,
    evidence: list[str],
    metrics: dict[str, Any],
    failures: list[str],
    jss_upload_blocking: bool = False,
) -> dict[str, Any]:
    clean_failures = [failure for failure in failures if failure]
    return {
        "id": item_id,
        "status": "PASS" if not clean_failures else "FAIL",
        "question": question,
        "classification": classification,
        "answer": answer,
        "primary_evidence": evidence,
        "metrics": metrics,
        "jss_upload_blocking": jss_upload_blocking,
        "failures": clean_failures,
    }


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    missing: list[str] = []

    required_paths = {
        "validation_evidence": RESULTS_DIR / "validation_evidence_audit.json",
        "methodological_gap": RESULTS_DIR / "methodological_gap_ledger.json",
        "stata_bridge": RESULTS_DIR / "stata_bridge_audit.json",
        "agent_interface": RESULTS_DIR / "agent_interface_audit.json",
        "agent_benchmark_protocol": RESULTS_DIR / "agent_benchmark_protocol.json",
        "reproduction_environment": RESULTS_DIR / "reproduction_environment_audit.json",
        "release_boundary": RESULTS_DIR / "release_boundary_audit.json",
        "claim_lint": RESULTS_DIR / "claim_lint.json",
    }
    payloads: dict[str, dict[str, Any]] = {}
    for name, path in required_paths.items():
        if not path.exists():
            missing.append(f"missing artifact: {path.relative_to(PAPER_DIR)}")
            continue
        payloads[name] = _read_json(path)

    coverage_path = ROOT / "tests" / "coverage_monte_carlo" / "results_b1000" / "coverage_b1000.json"
    robustness_path = (
        ROOT
        / "tests"
        / "coverage_monte_carlo"
        / "results_b1000"
        / "coverage_robustness_b1000.json"
    )
    coverage_rows = _read_json_list(coverage_path) if coverage_path.exists() else []
    robustness_rows = _read_json_list(robustness_path) if robustness_path.exists() else []

    if missing:
        items: list[dict[str, Any]] = []
        failures = missing
    else:
        validation = payloads["validation_evidence"]
        validation_summary = validation.get("summary", {})
        gap = payloads["methodological_gap"]
        gap_summary = gap.get("summary", {})
        stata = payloads["stata_bridge"]
        stata_summary = stata.get("summary", {})
        agent = payloads["agent_interface"]
        agent_protocol = payloads["agent_benchmark_protocol"]
        agent_schema = agent.get("schema_quality", {})
        agent_trace = agent.get("agent_trace", {})
        agent_protocol_summary = agent_protocol.get("summary", {})
        agent_protocol_boundary = agent_protocol.get("boundary", {})
        repro = payloads["reproduction_environment"]
        stata_contract = repro.get("stata_live_rerun_contract", {})
        reviewer_readmes = repro.get("reviewer_readmes", {})
        release = payloads["release_boundary"]
        release_summary = release.get("summary", {})
        claim = payloads["claim_lint"]
        claim_counts = claim.get("claim_counts", {})
        perf_modules = _count_perf_modules()
        tier1_steps = _tier1_step_summary(RESULTS_DIR / "reproduce_tier1_output.txt")

        items = [
            _item(
                item_id="cross_language_parity",
                question="Have the headline cross-language checks been run?",
                classification="implemented_with_boundary",
                answer=(
                    f"The JSS packet includes the {_expected_r()}-module R parity harness, "
                    f"{_expected_stata()} Stata bridges, and a classified T4 row rather "
                    "than treating all comparisons as equality claims."
                ),
                evidence=[
                    "replication/results/methodological_gap_ledger.md",
                    "replication/results/stata_bridge_audit.md",
                    "manuscript/tables/track_a_cross_language_snapshot.tex",
                ],
                metrics={
                    "r_modules": _expected_r(),
                    "stata_modules": stata_summary.get("stata_modules"),
                    "r_joined_stata_modules": stata_summary.get("r_joined_stata_modules"),
                    "methodological_gap_count": gap_summary.get("methodological_gap_count"),
                    "uncategorized_gap_count": gap_summary.get("uncategorized_gap_count"),
                },
                failures=[
                    "methodological gap ledger is not PASS"
                    if _status(gap) != "PASS"
                    else "",
                    "Stata bridge audit is not PASS"
                    if _status(stata) != "PASS"
                    else "",
                    f"Stata bridge count is not {_expected_stata()}"
                    if stata_summary.get("stata_modules") != _expected_stata()
                    else "",
                    "methodological/T4 rows are not fully classified"
                    if gap_summary.get("uncategorized_gap_count") not in (0, None)
                    else "",
                ],
            ),
            _item(
                item_id="monte_carlo_validation",
                question="Are the simulation rows implemented as validation evidence?",
                classification="implemented",
                answer=(
                    "The committed B=1000 Track-B artifacts cover all twelve "
                    "nominal rows (with bias, Monte Carlo SD, SE calibration "
                    "and interval length) plus three documented robustness "
                    "failure-mode rows."
                ),
                evidence=[
                    "tests/coverage_monte_carlo/results_b1000/coverage_b1000.json",
                    "tests/coverage_monte_carlo/results_b1000/coverage_robustness_b1000.json",
                    "manuscript/sections/05-parity-compact.tex",
                ],
                metrics={
                    "b1000_rows": len(coverage_rows),
                    "robustness_rows": len(robustness_rows),
                    "coverage_min": min((row.get("rate", 0.0) for row in coverage_rows), default=0.0),
                    "coverage_max": max((row.get("rate", 0.0) for row in coverage_rows), default=0.0),
                },
                failures=[
                    "B=1000 coverage headline rows are not complete"
                    if len(coverage_rows) != 12
                    else "",
                    "coverage robustness rows are not complete"
                    if len(robustness_rows) != 3
                    else "",
                ],
            ),
            _item(
                item_id="performance_benchmark",
                question="Is there measured runtime evidence rather than anecdote?",
                classification="implemented",
                answer=(
                    "Track C is a measured four-estimator benchmark with "
                    "generated tables and a log-log figure; it is not framed "
                    "as a universal speed claim."
                ),
                evidence=[
                    "tests/perf/results/perf_table.md",
                    "manuscript/tables/track_c_perf.tex",
                    "manuscript/figures/track_c_loglog.pdf",
                ],
                metrics={"performance_modules": perf_modules},
                failures=[
                    "performance benchmark module count is below four"
                    if perf_modules < 4
                    else ""
                ],
            ),
            _item(
                item_id="tier1_reproduction",
                question="Can a reviewer reproduce headline numbers without R or Stata?",
                classification="implemented",
                answer=(
                    "Tier 1 rebuilds the Section 4-7 headline numbers with "
                    "Python-only scripts and records a no-R/no-Stata transcript."
                ),
                evidence=[
                    "replication/reproduce.py",
                    "replication/results/reproduce_tier1_output.txt",
                    "replication/results/reproduction_environment_audit.md",
                ],
                metrics={
                    "tier1_steps": tier1_steps,
                    "tier1_no_r_stata": repro.get("tier1_transcript_no_r_stata"),
                    "tier1_live_external_call_count": repro.get("reproduce", {}).get(
                        "tier1_live_external_call_count"
                    ),
                },
                failures=[
                    "reproduction environment audit is not PASS"
                    if _status(repro) != "PASS"
                    else "",
                    "Tier 1 does not report 24/24 steps"
                    if tier1_steps != "24/24"
                    else "",
                    "Tier 1 is not no-R/no-Stata"
                    if repro.get("tier1_transcript_no_r_stata") is not True
                    else "",
                    "Tier 1 has live external-call markers"
                    if repro.get("reproduce", {}).get("tier1_live_external_call_count") != 0
                    else "",
                ],
            ),
            _item(
                item_id="live_stata_rerun",
                question="Is a live Stata rerun required for JSS upload?",
                classification="external_runtime_documented",
                answer=(
                    "Live Stata re-execution is optional because it requires a "
                    "separate license and an explicit `STATA_EXE` runtime; a "
                    "missing-Stata skip is documented as not being live-rerun "
                    "evidence. The upload includes frozen JSON, do-files, "
                    "provenance, and a bridge audit for all "
                    f"{stata_summary.get('stata_modules')} modules."
                ),
                evidence=[
                    "replication/results/stata_bridge_audit.md",
                    "tests/stata_parity/README.md",
                    "tests/stata_parity/verify_reproduce_stata.py",
                    "replication/results/reproduction_environment_audit.md",
                ],
                metrics={
                    "stata_modules": stata_summary.get("stata_modules"),
                    "license_boundary": stata_summary.get("license_boundary"),
                    "live_rerun_command_documented": reviewer_readmes.get(
                        "stata_live_rerun_command_documented"
                    ),
                    "missing_stata_skip_documented": reviewer_readmes.get(
                        "stata_missing_runtime_skip_documented"
                    ),
                    "verifier_missing_runtime_returns_skip": stata_contract.get(
                        "stata_verify_missing_runtime_returns_skip"
                    ),
                },
                failures=[
                    "Stata license boundary is missing"
                    if not stata_summary.get("license_boundary")
                    else "",
                    "Stata live-rerun STATA_EXE command is not documented"
                    if reviewer_readmes.get("stata_live_rerun_command_documented") is not True
                    else "",
                    "Stata missing-runtime skip boundary is not documented"
                    if reviewer_readmes.get("stata_missing_runtime_skip_documented") is not True
                    else "",
                    "Stata verifier missing-runtime skip contract is not explicit"
                    if stata_contract.get("stata_verify_missing_runtime_returns_skip") is not True
                    else "",
                    f"frozen Stata module count is not {_expected_stata()}"
                    if stata_summary.get("stata_modules") != _expected_stata()
                    else "",
                ],
            ),
            _item(
                item_id="behavioural_agent_benchmark",
                question="Does the JSS paper need a behavioural LLM benchmark?",
                classification="deferred_to_separate_benchmark",
                answer=(
                    "No behavioural agent-performance result is claimed here; "
                    "the JSS evidence is a mechanical and contractual "
                    "interface audit whose schemas, typed errors, handles, "
                    "citations, and deterministic trace are inspectable in "
                    "the same validation ledger as human calls, "
                    "with a packaged deferred benchmark protocol specifying "
                    "matched baselines, task families, scoring dimensions, "
                    "and leakage controls for the separate behavioural study."
                ),
                evidence=[
                    "replication/results/agent_interface_audit.md",
                    "replication/results/agent_benchmark_protocol.md",
                    "manuscript/sections/07-agent-eval.tex",
                    "replication/results/ex07_agent_trace.txt",
                ],
                metrics={
                    "schema_files": agent_schema.get("public_surface"),
                    "schema_parameters": agent_schema.get("parameter_total"),
                    "trace_tools": agent_trace.get("tool_count"),
                    "trace_bibtex_entry_count": agent_trace.get("bibtex_entry_count"),
                    "protocol_arms": agent_protocol_summary.get("arm_count"),
                    "protocol_task_families": agent_protocol_summary.get(
                        "task_family_count"
                    ),
                    "protocol_scoring_dimensions": agent_protocol_summary.get(
                        "scoring_dimension_count"
                    ),
                    "protocol_validity_controls": agent_protocol_summary.get(
                        "validity_control_count"
                    ),
                    "protocol_jss_upload_blocking": agent_protocol_summary.get(
                        "jss_upload_blocking"
                    ),
                    "protocol_claimed_behavioural_result": (
                        agent_protocol_summary.get("jss_claimed_behavioral_result")
                    ),
                },
                failures=[
                    "agent interface audit is not PASS"
                    if _status(agent) != "PASS"
                    else "",
                    "agent benchmark protocol is not PASS"
                    if _status(agent_protocol) != "PASS"
                    else "",
                    "agent trace is empty"
                    if (agent_trace.get("tool_count") or 0) <= 0
                    else "",
                    "agent benchmark protocol does not specify three comparator arms"
                    if agent_protocol_summary.get("arm_count", 0) < 3
                    else "",
                    "agent benchmark protocol does not specify five task families"
                    if agent_protocol_summary.get("task_family_count", 0) < 5
                    else "",
                    "agent benchmark protocol does not specify six scoring dimensions"
                    if agent_protocol_summary.get("scoring_dimension_count", 0) < 6
                    else "",
                    "agent benchmark protocol does not specify six validity controls"
                    if agent_protocol_summary.get("validity_control_count", 0) < 6
                    else "",
                    "agent benchmark protocol is incorrectly marked upload-blocking"
                    if agent_protocol_summary.get("jss_upload_blocking") is not False
                    else "",
                    "agent benchmark protocol implies a completed behavioural result"
                    if agent_protocol_summary.get("jss_claimed_behavioral_result")
                    is not False
                    else "",
                    "agent benchmark protocol lacks current-evidence boundary"
                    if "mechanical and contractual" not in str(
                        agent_protocol_boundary.get("current_jss_evidence", "")
                    )
                    else "",
                ],
            ),
            _item(
                item_id="full_registry_numeric_validation",
                question="Does every registered public function need numerical validation?",
                classification="not_a_jss_claim",
                answer=(
                    "No. The JSS claim is tiered: certified/validated symbols "
                    "carry evidence notes, while API-stable breadth is disclosed "
                    "as interface stability rather than numerical validation."
                ),
                evidence=[
                    "replication/results/validation_evidence_audit.md",
                    "replication/results/claim_lint.md",
                    "docs/guides/stability.md",
                ],
                metrics={
                    "certified_validated_symbols": validation_summary.get(
                        "certified_validated_symbols"
                    ),
                    "missing_validation_notes": validation_summary.get(
                        "missing_validation_notes"
                    ),
                    "api_stable_symbols": claim_counts.get("api_stable"),
                    "unbacked_auto_stable": claim_counts.get("unbacked_auto"),
                },
                failures=[
                    "validation evidence audit is not PASS"
                    if _status(validation) != "PASS"
                    else "",
                    "claim linter is not PASS"
                    if _status(claim) != "PASS"
                    else "",
                    "certified/validated evidence notes are missing"
                    if validation_summary.get("missing_validation_notes") not in (0, None)
                    else "",
                ],
            ),
            _item(
                item_id="final_tagged_release",
                question="Does JSS upload require the final clean tagged release cut?",
                classification="post_upload_release_work",
                answer=(
                    "No. The JSS archive is an audited source snapshot; the "
                    "clean worktree, changelog, and tag alignment remain listed "
                    "as nonblocking final-release work."
                ),
                evidence=[
                    "replication/results/release_boundary_audit.md",
                    "replication/results/source_snapshot_manifest.md",
                    "replication/results/submission_risk_ledger.md",
                ],
                metrics={
                    "release_boundary_status": _status(release),
                    "ready_for_final_publication": release_summary.get(
                        "ready_for_final_publication"
                    ),
                    "release_blocker_count": release_summary.get(
                        "release_blocker_count"
                    ),
                    "version_consistent": release_summary.get("version_consistent"),
                },
                failures=[
                    "release boundary audit is not PASS"
                    if _status(release) != "PASS"
                    else "",
                    "source versions are inconsistent"
                    if release_summary.get("version_consistent") is not True
                    else "",
                ],
            ),
        ]
        item_ids = [item["id"] for item in items]
        failures = [
            f"item identity/order drift: expected={list(EXPECTED_ITEM_IDS)}, observed={item_ids}"
        ] if item_ids != list(EXPECTED_ITEM_IDS) else []
        failures.extend(
            f"{item['id']}: {failure}"
            for item in items
            for failure in item.get("failures", [])
        )

    status = "PASS" if not failures else "FAIL"
    classification_counts: dict[str, int] = {}
    for item in items:
        classification = str(item.get("classification"))
        classification_counts[classification] = classification_counts.get(classification, 0) + 1
    blocking_items = [
        item["id"]
        for item in items
        if item.get("jss_upload_blocking") or item.get("status") != "PASS"
    ]
    summary = {
        "item_count": len(items),
        "expected_item_ids": list(EXPECTED_ITEM_IDS),
        "item_ids": [item.get("id") for item in items],
        "item_identity_ok": [item.get("id") for item in items] == list(EXPECTED_ITEM_IDS),
        "pass_items": sum(1 for item in items if item.get("status") == "PASS"),
        "failed_items": sum(1 for item in items if item.get("status") != "PASS"),
        "classification_counts": classification_counts,
        "jss_upload_blocking_item_count": len(blocking_items),
        "jss_upload_blocking_items": blocking_items,
    }
    payload = {
        "generated_at_unix": _generated_at_unix(),
        "status": status,
        "summary": summary,
        "items": items,
        "failures": failures,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# JSS Experiment And Evidence Triage",
        "",
        f"Status: {status}",
        f"Triage items: {summary['item_count']}",
        "Expected item identity: "
        + ("confirmed" if summary["item_identity_ok"] else "DRIFT"),
        f"JSS upload-blocking gaps: {summary['jss_upload_blocking_item_count']}",
        "",
        "| Item | Status | Classification | Reviewer question | Boundary answer | Evidence |",
        "|---|---:|---|---|---|---|",
    ]
    for item in items:
        evidence = "<br>".join(f"`{path}`" for path in item["primary_evidence"])
        lines.append(
            "| "
            + f"`{item['id']}`"
            + " | "
            + item["status"]
            + " | `"
            + item["classification"]
            + "` | "
            + item["question"]
            + " | "
            + item["answer"]
            + " | "
            + evidence
            + " |"
        )
    lines.extend(["", "## Metrics", ""])
    for item in items:
        lines.append(f"### {item['id']}")
        for key, value in item["metrics"].items():
            lines.append(f"- `{key}`: `{value}`")
        lines.append("")
    if failures:
        lines.extend(["## Failures", ""])
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.extend(["Failures: none"])
    lines.extend(["", f"Machine-readable detail: `{OUT_JSON.relative_to(PAPER_DIR)}`"])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"OK -- wrote {OUT_JSON}")
    print(f"OK -- wrote {OUT_MD}")
    if failures:
        print("FAIL -- experiment triage has unresolved or unclassified items")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

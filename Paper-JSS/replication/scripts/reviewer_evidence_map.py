"""Generate a reviewer evidence map for the compact JSS submission.

The active PDF is intentionally compact.  This generated map gives reviewers a
single route from likely review questions to the exact audit artifacts and
commands that answer them, without expanding the manuscript body.
"""
from __future__ import annotations

import json
import os
import time
import zipfile
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
OUT_JSON = RESULTS_DIR / "reviewer_evidence_map.json"
OUT_MD = RESULTS_DIR / "reviewer_evidence_map.md"
SUBMISSION_ARCHIVE = PAPER_DIR / "build" / "statspai-jss-submission.zip"
SOURCE_DATE_EPOCH = os.environ.get("SOURCE_DATE_EPOCH")

ARTIFACTS = {
    "claim_lint": RESULTS_DIR / "claim_lint.json",
    "validation_evidence": RESULTS_DIR / "validation_evidence_audit.json",
    "methodological_gap": RESULTS_DIR / "methodological_gap_ledger.json",
    "stata_bridge": RESULTS_DIR / "stata_bridge_audit.json",
    "stata_rerun_protocol": RESULTS_DIR / "stata_rerun_protocol.json",
    "agent_interface": RESULTS_DIR / "agent_interface_audit.json",
    "agent_benchmark_protocol": RESULTS_DIR / "agent_benchmark_protocol.json",
    "release_boundary": RESULTS_DIR / "release_boundary_audit.json",
    "reproduction_environment": RESULTS_DIR / "reproduction_environment_audit.json",
    "manuscript_artifacts": RESULTS_DIR / "manuscript_artifact_audit.json",
    "data_provenance": RESULTS_DIR / "data_provenance_audit.json",
    "pdf_render": RESULTS_DIR / "pdf_render_audit.json",
    "pdf_visual_check_protocol": RESULTS_DIR / "pdf_visual_check_protocol.json",
    "formal_compliance": RESULTS_DIR / "jss_formal_compliance_audit.json",
    "experiment_triage": RESULTS_DIR / "experiment_triage.json",
    "submission_risk": RESULTS_DIR / "submission_risk_ledger.json",
}

EXPECTED_CARD_IDS = (
    "validation_scope",
    "headline_reproduction",
    "cross_language_limits",
    "artifact_provenance",
    "worked_example_scope",
    "experiment_triage",
    "archive_boundary",
    "related_review_coi_boundary",
    "software_installability",
    "agent_interface_boundary",
    "limitations_crosswalk",
    "maintenance_sustainability",
    "final_cut_boundary",
)

EXPECTED_ROUTE_IDS = (
    "editor_triage",
    "statistical_validation",
    "quick_reproduction",
    "agent_interface",
    "limitations_and_release_boundary",
)


def _generated_at_unix() -> int:
    if SOURCE_DATE_EPOCH is not None:
        return int(SOURCE_DATE_EPOCH)
    return int(time.time())


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_archive_member(rel_path: str, names: set[str]) -> str | None:
    rel_path = rel_path.strip()
    if not rel_path or rel_path.startswith("/") or ".." in Path(rel_path).parts:
        return None
    for candidate in (rel_path, f"Paper-JSS/{rel_path}"):
        if candidate in names:
            return candidate
    return None


def _escape_md_cell(value: object) -> str:
    text = str(value)
    return text.replace("|", r"\|").replace("\n", " ")


def _archive_evidence_resolution(items: list[dict[str, Any]]) -> dict[str, Any]:
    evidence_paths = sorted(
        {
            path
            for item in items
            for path in item.get("primary_evidence", [])
            if isinstance(path, str)
        }
    )
    if not SUBMISSION_ARCHIVE.exists():
        return {
            "archive_present": False,
            "checked_paths": len(evidence_paths),
            "resolved_paths": None,
            "missing_paths": [],
        }
    with zipfile.ZipFile(SUBMISSION_ARCHIVE) as zf:
        names = set(zf.namelist())
    missing = [
        path
        for path in evidence_paths
        if _resolve_archive_member(path, names) is None
    ]
    return {
        "archive_present": True,
        "checked_paths": len(evidence_paths),
        "resolved_paths": len(evidence_paths) - len(missing),
        "missing_paths": missing,
    }


def _load_artifacts(failures: list[str]) -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = {}
    for name, path in ARTIFACTS.items():
        if not path.exists():
            failures.append(f"missing artifact: {path.relative_to(PAPER_DIR)}")
            continue
        payload = _read_json(path)
        loaded[name] = payload
        if payload.get("status") != "PASS":
            failures.append(
                f"{path.relative_to(PAPER_DIR)} status={payload.get('status')}"
            )
    return loaded


def _card(
    *,
    card_id: str,
    reviewer_question: str,
    answer_boundary: str,
    primary_evidence: list[str],
    verification_gate: str,
    metrics: dict[str, Any],
    failures: list[str],
) -> dict[str, Any]:
    clean_failures = [failure for failure in failures if failure]
    ok = not clean_failures
    return {
        "id": card_id,
        "status": "PASS" if ok else "FAIL",
        "reviewer_question": reviewer_question,
        "answer_boundary": answer_boundary,
        "primary_evidence": primary_evidence,
        "verification_gate": verification_gate,
        "metrics": metrics,
        "failures": clean_failures,
    }


def _route(
    *,
    route_id: str,
    reviewer_start: str,
    use_when: str,
    first_read: str,
    evidence_cards: list[str],
    primary_evidence: list[str],
    verification_gate: str,
) -> dict[str, Any]:
    return {
        "id": route_id,
        "reviewer_start": reviewer_start,
        "use_when": use_when,
        "first_read": first_read,
        "evidence_cards": evidence_cards,
        "primary_evidence": primary_evidence,
        "verification_gate": verification_gate,
    }


def _routes(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    card_ids = {card.get("id") for card in cards}
    routes = [
        _route(
            route_id="editor_triage",
            reviewer_start="Start with the editor checklist, then open the map card named evidence_navigation.",
            use_when="You need a fast upload-readiness and JSS-form check before reading statistical detail.",
            first_read="replication/results/editor_screening_checklist.md",
            evidence_cards=[
                "software_installability",
                "archive_boundary",
                "related_review_coi_boundary",
                "artifact_provenance",
                "final_cut_boundary",
            ],
            primary_evidence=[
                "replication/results/editor_screening_checklist.md",
                "replication/results/jss_formal_compliance_audit.md",
                "cover-letter.md",
                "replication/results/pdf_render_audit.md",
                "replication/results/pdf_visual_check_protocol.md",
                "replication/results/submission_risk_ledger.md",
            ],
            verification_gate=(
                "make editor-screening-checklist + make verify-submission-package"
            ),
        ),
        _route(
            route_id="statistical_validation",
            reviewer_start="Start with the validation-scope card, then read the cross-language limits card.",
            use_when="You want to audit the statistical evidence before the software packaging evidence.",
            first_read="replication/results/validation_evidence_audit.md",
            evidence_cards=[
                "validation_scope",
                "cross_language_limits",
                "experiment_triage",
                "limitations_crosswalk",
            ],
            primary_evidence=[
                "replication/results/validation_evidence_audit.md",
                "replication/results/methodological_gap_ledger.md",
                "replication/results/stata_rerun_protocol.md",
                "replication/results/experiment_triage.md",
                "manuscript/tables/track_a_cross_language_snapshot.tex",
            ],
            verification_gate="make audit",
        ),
        _route(
            route_id="quick_reproduction",
            reviewer_start="Start with the Tier-1 transcript and only escalate to Tier 2/3 for external-language reruns.",
            use_when="You need to reproduce the headline Section 4-7 numbers without live R or Stata.",
            first_read="replication/results/reproduce_tier1_output.txt",
            evidence_cards=[
                "headline_reproduction",
                "worked_example_scope",
                "artifact_provenance",
            ],
            primary_evidence=[
                "replication/results/reproduce_tier1_output.txt",
                "replication/results/reproduction_environment_audit.md",
                "replication/reproduce.py",
                "replication/results/manuscript_artifact_audit.md",
            ],
            verification_gate="make reproduce-jss-full",
        ),
        _route(
            route_id="agent_interface",
            reviewer_start="Start with the agent-interface boundary card and the deterministic MCP trace.",
            use_when="You are checking the agent-facing contribution but not behavioural agent performance.",
            first_read="replication/results/agent_interface_audit.md",
            evidence_cards=[
                "agent_interface_boundary",
                "experiment_triage",
            ],
            primary_evidence=[
                "replication/results/agent_interface_audit.md",
                "replication/results/agent_benchmark_protocol.md",
                "replication/results/ex07_agent_trace.txt",
                "schemas/tools.json",
                "manuscript/sections/07-agent-eval.tex",
            ],
            verification_gate="make agent-interface-audit",
        ),
        _route(
            route_id="limitations_and_release_boundary",
            reviewer_start="Start with the limitations crosswalk, then the final-cut boundary card.",
            use_when="You are checking residual risks, source-snapshot wording, and what remains after upload.",
            first_read="manuscript/sections/09-discussion-compact.tex",
            evidence_cards=[
                "limitations_crosswalk",
                "maintenance_sustainability",
                "final_cut_boundary",
                "archive_boundary",
            ],
            primary_evidence=[
                "manuscript/sections/09-discussion-compact.tex",
                "replication/results/submission_risk_ledger.md",
                "replication/results/reproduction_environment_audit.md",
                "replication/results/source_snapshot_manifest.md",
                "replication/results/release_boundary_audit.md",
            ],
            verification_gate="make submission-risk-ledger + make release-boundary-audit",
        ),
    ]
    for route in routes:
        missing = [
            card_id for card_id in route["evidence_cards"]
            if card_id not in card_ids
        ]
        route["status"] = "PASS" if not missing else "FAIL"
        route["missing_cards"] = missing
    return routes


def _cards(artifacts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    claim = artifacts["claim_lint"]
    validation = artifacts["validation_evidence"]
    gap = artifacts["methodological_gap"]
    stata = artifacts["stata_bridge"]
    stata_protocol = artifacts["stata_rerun_protocol"]
    agent = artifacts["agent_interface"]
    agent_protocol = artifacts["agent_benchmark_protocol"]
    release = artifacts["release_boundary"]
    repro = artifacts["reproduction_environment"]
    manuscript = artifacts["manuscript_artifacts"]
    data_provenance = artifacts["data_provenance"]
    pdf_render = artifacts["pdf_render"]
    pdf_protocol = artifacts["pdf_visual_check_protocol"]
    formal = artifacts["formal_compliance"]
    experiment = artifacts["experiment_triage"]
    risk = artifacts["submission_risk"]

    claim_counts = claim.get("claim_counts", {})
    validation_summary = validation.get("summary", {})
    gap_summary = gap.get("summary", {})
    stata_summary = stata.get("summary", {})
    stata_protocol_summary = stata_protocol.get("summary", {})
    agent_schema = agent.get("schema_quality", {})
    agent_trace = agent.get("agent_trace", {})
    agent_protocol_summary = agent_protocol.get("summary", {})
    risk_archive = risk.get("archive", {})
    data_summary = data_provenance.get("summary", {})
    risk_source = risk.get("source_snapshot", {})
    risk_details = risk.get("documented_nonblocking_risks", [])
    risk_runbook = risk.get("final_tagged_cut_runbook", {})
    experiment_summary = experiment.get("summary", {})
    worked = manuscript.get("worked_examples", {})
    worked_expected = worked.get("expected_count", 7)
    missing_pdf_boundary_snippets = (
        formal.get("missing_pdf_boundary_snippets") or []
    )
    pdf_render_summary = pdf_render.get("summary", {})
    manual_visual = pdf_render.get("manual_preupload_visual_check", {})
    pdf_protocol_summary = pdf_protocol.get("summary", {})
    formal_checks = {
        check.get("requirement"): check
        for check in formal.get("checks", [])
        if isinstance(check, dict)
    }
    related_review_check = formal_checks.get(
        "cover letter related-review and conflict disclosures are explicit",
        {},
    )
    source_release_check = formal_checks.get(
        "source-snapshot and final-release boundaries are explicit",
        {},
    )

    cards: list[dict[str, Any]] = []
    cards.append(
        _card(
            card_id="validation_scope",
            reviewer_question="What exactly is validated, and what is only API-stable?",
            answer_boundary=(
                "Validated is an evidence tier limited to certified/validated "
                "registry entries; API-stable breadth is disclosed separately."
            ),
            primary_evidence=[
                "replication/results/claim_lint.md",
                "replication/results/validation_evidence_audit.md",
                "docs/guides/stability.md",
            ],
            verification_gate="make audit -> claim_linter + validation_evidence_audit",
            metrics={
                "claim_files_checked": len(claim.get("checked_files", [])),
                "certified_validated_symbols": validation_summary.get(
                    "certified_validated_symbols"
                ),
                "api_stable_symbols": claim_counts.get("api_stable"),
                "unbacked_handwritten_stable": claim_counts.get(
                    "unbacked_handwritten"
                ),
                "unbacked_auto_stable": claim_counts.get("unbacked_auto"),
            },
            failures=[
                "unbacked hand-written stable symbols remain"
                if claim_counts.get("unbacked_handwritten") not in (0, None)
                else ""
            ],
        )
    )
    cards.append(
        _card(
            card_id="headline_reproduction",
            reviewer_question="Can headline Section 4-7 numbers be checked quickly?",
            answer_boundary=(
                "Tier 1 is the short reviewer path and does not require live R "
                "or Stata; Tier 2/3 are external-language reruns."
            ),
            primary_evidence=[
                "replication/results/reproduce_tier1_output.txt",
                "replication/results/reproduction_environment_audit.md",
                "replication/reproduce.py",
            ],
            verification_gate="make reproduce-tier1-transcript + make audit",
            metrics={
                "tier1_complete": repro.get("tier1_transcript_complete"),
                "tier1_no_r_stata": repro.get("tier1_transcript_no_r_stata"),
                "tier1_live_external_call_count": repro.get("reproduce", {}).get(
                    "tier1_live_external_call_count"
                ),
                "r_reproduced_modules": repro.get("r_reproduced_modules"),
                "stata_reproduced_modules": repro.get("stata_reproduced_modules"),
            },
            failures=[
                "Tier 1 transcript is incomplete"
                if repro.get("tier1_transcript_complete") is not True
                else "",
                "Tier 1 has live external-language dependency markers"
                if repro.get("reproduce", {}).get("tier1_live_external_call_count") != 0
                else "",
            ],
        )
    )
    cards.append(
        _card(
            card_id="cross_language_limits",
            reviewer_question="Where do R/Stata comparisons stop being equality claims?",
            answer_boundary=(
                "Track A separates machine/iterative/moderate agreement from "
                "the one methodological/T4 disclosure."
            ),
            primary_evidence=[
                "replication/results/methodological_gap_ledger.md",
                "replication/results/stata_bridge_audit.md",
                "replication/results/stata_rerun_protocol.md",
                "manuscript/tables/track_a_cross_language_snapshot.tex",
            ],
            verification_gate=(
                "make audit -> methodological_gap_ledger + "
                "stata_bridge_audit + stata_rerun_protocol"
            ),
            metrics={
                "methodological_gap_count": gap_summary.get("methodological_gap_count"),
                "classified_gap_count": gap_summary.get("classified_gap_count"),
                "uncategorized_gap_count": gap_summary.get("uncategorized_gap_count"),
                "stata_modules": stata_summary.get("stata_modules"),
                "r_joined_stata_modules": stata_summary.get("r_joined_stata_modules"),
                "stata_rerun_protocol_status": stata_protocol.get("status"),
                "stata_rerun_protocol_checklist_items": (
                    stata_protocol_summary.get("checklist_item_count")
                ),
                "stata_rerun_requires_license": (
                    stata_protocol_summary.get("requires_stata_license")
                ),
                "stata_rerun_upload_blocking": (
                    stata_protocol_summary.get("jss_upload_blocking")
                ),
                "stata_rerun_claimed_live_rerun": (
                    stata_protocol_summary.get(
                        "claimed_current_machine_live_rerun"
                    )
                ),
                "stata_rerun_non_reproduced_rows": (
                    stata_protocol_summary.get("non_reproduced_report_rows")
                ),
            },
            failures=[
                "methodological/T4 rows are not fully classified"
                if gap_summary.get("uncategorized_gap_count") not in (0, None)
                else "",
                "Py-Stata-only modules remain"
                if stata_summary.get("py_stata_only_modules")
                else "",
                "Stata rerun protocol is not PASS"
                if stata_protocol.get("status") != "PASS"
                else "",
                "Stata rerun protocol lost the license boundary"
                if stata_protocol_summary.get("requires_stata_license") is not True
                else "",
                "Stata rerun protocol is incorrectly upload-blocking"
                if stata_protocol_summary.get("jss_upload_blocking") is not False
                else "",
                "Stata rerun protocol falsely claims a current live rerun"
                if stata_protocol_summary.get("claimed_current_machine_live_rerun")
                is not False
                else "",
                "Stata rerun protocol reports Stata drift rows"
                if stata_protocol_summary.get("non_reproduced_report_rows") not in (0, None)
                else "",
            ],
        )
    )
    cards.append(
        _card(
            card_id="artifact_provenance",
            reviewer_question="Do active tables and figures map to generators?",
            answer_boundary=(
                "The active manuscript inputs, generated tables, and figures "
                "are audited by label and generator path."
            ),
            primary_evidence=[
                "replication/results/manuscript_artifact_audit.md",
                "replication/scripts/manuscript_artifact_audit.py",
                "manuscript/main.tex",
            ],
            verification_gate="make manuscript-artifact-audit",
            metrics={
                "active_sections": len(manuscript.get("active_sections", [])),
                "generated_artifacts": manuscript.get("artifact_count"),
                "float_labels": len(manuscript.get("active_float_labels", [])),
                "missing_refs": len(manuscript.get("missing_narrative_refs", [])),
                "dangling_refs": len(manuscript.get("dangling_float_refs", [])),
            },
            failures=[
                "active floats lack narrative references"
                if manuscript.get("missing_narrative_refs")
                else "",
                "prose points to inactive floats"
                if manuscript.get("dangling_float_refs")
                else "",
            ],
        )
    )
    cards.append(
        _card(
            card_id="worked_example_scope",
            reviewer_question=(
                "Do the worked examples match executable scripts and manuscript claims?"
            ),
            answer_boundary=(
                "The active manuscript reports seven worked examples; the artifact "
                "audit verifies the seven executable scripts, seven table/script "
                "mentions, seven active subsection labels, and the count claim."
            ),
            primary_evidence=[
                "replication/results/manuscript_artifact_audit.md",
                "replication/scripts/manuscript_artifact_audit.py",
                "manuscript/sections/04-examples-compact.tex",
            ],
            verification_gate="make manuscript-artifact-audit + make audit",
            metrics={
                "expected_count": worked_expected,
                "scripts_present": len(worked.get("scripts_present", [])),
                "script_mentions": len(worked.get("script_mentions", [])),
                "table_script_mentions": len(
                    worked.get("table_script_mentions", [])
                ),
                "subsection_labels": len(worked.get("labels_present", [])),
                "count_claim_present": worked.get("count_claim_present"),
            },
            failures=[
                "worked-example scope guard failed"
                if worked.get("ok") is not True
                else "",
                "worked-example scripts are incomplete"
                if len(worked.get("scripts_present", [])) != worked_expected
                else "",
                "worked-example script mentions are incomplete"
                if len(worked.get("script_mentions", [])) != worked_expected
                else "",
                "worked-example table script mentions are incomplete"
                if len(worked.get("table_script_mentions", [])) != worked_expected
                else "",
                "worked-example subsection labels are incomplete"
                if len(worked.get("labels_present", [])) != worked_expected
                else "",
                "worked-example count claim is missing"
                if worked.get("count_claim_present") is not True
                else "",
            ],
        )
    )
    cards.append(
        _card(
            card_id="experiment_triage",
            reviewer_question=(
                "Which high-ROI experiments are implemented, bounded, or deferred?"
            ),
            answer_boundary=(
                "The triage report separates implemented JSS evidence from "
                "external-runtime checks, behavioural agent benchmarking, "
                "API-breadth nonclaims, and post-upload release work; the "
                "deferred behavioural benchmark has a packaged protocol rather "
                "than an implied result."
            ),
            primary_evidence=[
                "replication/results/experiment_triage.md",
                "replication/results/agent_benchmark_protocol.md",
                "replication/scripts/experiment_triage.py",
                "replication/results/submission_risk_ledger.md",
            ],
            verification_gate="make experiment-triage + make reviewer-evidence-map",
            metrics={
                "triage_items": experiment_summary.get("item_count"),
                "triage_pass_items": experiment_summary.get("pass_items"),
                "triage_failed_items": experiment_summary.get("failed_items"),
                "jss_upload_blocking_item_count": experiment_summary.get(
                    "jss_upload_blocking_item_count"
                ),
                "classification_counts": experiment_summary.get(
                    "classification_counts"
                ),
                "item_ids": experiment_summary.get("item_ids"),
                "agent_protocol_arms": agent_protocol_summary.get("arm_count"),
                "agent_protocol_task_families": agent_protocol_summary.get(
                    "task_family_count"
                ),
                "agent_protocol_jss_upload_blocking": (
                    agent_protocol_summary.get("jss_upload_blocking")
                ),
            },
            failures=[
                "experiment triage is not PASS"
                if experiment.get("status") != "PASS"
                else "",
                "experiment triage has upload-blocking items"
                if experiment_summary.get("jss_upload_blocking_item_count") not in (0, None)
                else "",
                "experiment triage item identity drift"
                if experiment_summary.get("item_identity_ok") is not True
                else "",
                "agent benchmark protocol is not PASS"
                if agent_protocol.get("status") != "PASS"
                else "",
                "agent benchmark protocol is incorrectly upload-blocking"
                if agent_protocol_summary.get("jss_upload_blocking") is not False
                else "",
            ],
        )
    )
    cards.append(
        _card(
            card_id="archive_boundary",
            reviewer_question="Is the submitted archive bounded and free of review-lane spillover?",
            answer_boundary=(
                "The archive is a source snapshot with active external-review "
                "materials, local notes, and inactive draft sections excluded; "
                "the data-provenance audit classifies data/result members and "
                "rejects forbidden raw-data formats plus private or credential "
                "path hits."
            ),
            primary_evidence=[
                "replication/results/submission_risk_ledger.md",
                "replication/results/data_provenance_audit.md",
                "README.md",
                "replication/scripts/verify_submission_package.py",
            ],
            verification_gate="make verify-submission-package",
            metrics={
                "jss_upload_blockers": risk.get("jss_upload_blocker_count"),
                "archive_file_count": risk_archive.get("file_count"),
                "archive_size_mib": risk_archive.get("size_mib"),
                "data_provenance_status": data_provenance.get("status"),
                "data_provenance_scoped_data_files": data_summary.get(
                    "scoped_data_file_count"
                ),
                "data_provenance_csv_files": data_summary.get("csv_file_count"),
                "data_provenance_packaged_public_datasets": data_summary.get(
                    "packaged_public_dataset_csv_count"
                ),
                "data_provenance_public_original_extracts": data_summary.get(
                    "public_original_extract_csv_count"
                ),
                "data_provenance_r_stata_fixture_csv": data_summary.get(
                    "same_byte_r_stata_fixture_csv_count"
                ),
                "data_provenance_forbidden_raw_members": data_summary.get(
                    "forbidden_raw_member_count"
                ),
                "data_provenance_high_risk_path_hits": data_summary.get(
                    "high_risk_path_hit_count"
                ),
                "data_provenance_unknown_categories": data_summary.get(
                    "unknown_category_count"
                ),
                "active_external_present": len(
                    risk_archive.get("active_external_review_artifacts_present", [])
                ),
                "legacy_sections_present": len(
                    risk_archive.get("legacy_manuscript_sources_present", [])
                ),
            },
            failures=[
                "JSS upload blockers remain"
                if risk.get("jss_upload_blocker_count") not in (0, None)
                else "",
                "active external-review artifacts appear in archive"
                if risk_archive.get("active_external_review_artifacts_present")
                else "",
                "inactive manuscript drafts appear in archive"
                if risk_archive.get("legacy_manuscript_sources_present")
                else "",
                "data provenance audit is not PASS"
                if data_provenance.get("status") != "PASS"
                else "",
                "data provenance audit found forbidden raw-data members"
                if data_summary.get("forbidden_raw_member_count") not in (0, None)
                else "",
                "data provenance audit found private/credential path hits"
                if data_summary.get("high_risk_path_hit_count") not in (0, None)
                else "",
                "data provenance audit has unknown categories"
                if data_summary.get("unknown_category_count") not in (0, None)
                else "",
                "data provenance audit has CSV parse failures"
                if data_summary.get("csv_parse_failure_count") not in (0, None)
                else "",
                "data provenance public dataset count drift"
                if data_summary.get("packaged_public_dataset_csv_count") != 9
                else "",
                "data provenance original extract count drift"
                if data_summary.get("public_original_extract_csv_count") != 7
                else "",
                "data provenance R/Stata fixture CSV count drift"
                if data_summary.get("same_byte_r_stata_fixture_csv_count") != 91
                else "",
            ],
        )
    )
    cards.append(
        _card(
            card_id="related_review_coi_boundary",
            reviewer_question=(
                "Are the related JOSS publication and conflict disclosures "
                "visible without modifying the archived JOSS files?"
            ),
            answer_boundary=(
                "The cover letter discloses the published JOSS paper, "
                "states that this manuscript cites it and shares no evidence table with it, "
                "and names the maintainer, commercial downstream product, "
                "license, and funding facts."
            ),
            primary_evidence=[
                "cover-letter.md",
                "replication/results/jss_formal_compliance_audit.md",
                "replication/results/release_boundary_audit.md",
                "README.md",
            ],
            verification_gate=(
                "make jss-formal-compliance-audit + make release-boundary-audit"
            ),
            metrics={
                "related_review_check": related_review_check.get("ok"),
                "related_review_evidence": related_review_check.get("evidence"),
                "source_snapshot_boundary_check": source_release_check.get("ok"),
                "release_boundary_status": release.get("status"),
                "active_external_present": len(
                    risk_archive.get("active_external_review_artifacts_present", [])
                ),
            },
            failures=[
                "cover letter related-review/COI disclosure is not PASS"
                if related_review_check.get("ok") is not True
                else "",
                "source-snapshot/final-release boundary check is not PASS"
                if source_release_check.get("ok") is not True
                else "",
                "release boundary audit is not PASS"
                if release.get("status") != "PASS"
                else "",
                "active external-review artifacts appear in archive"
                if risk_archive.get("active_external_review_artifacts_present")
                else "",
            ],
        )
    )
    cards.append(
        _card(
            card_id="software_installability",
            reviewer_question="Can the submitted source be installed and imported?",
            answer_boundary=(
                "Formal compliance verifies JSS class/front matter, license, "
                "archive install/import, package help files, PDF-visible "
                "boundary text, source-synchronized polished PDF prose, "
                "Poppler-rendered PDF sample pages, and an all-page machine "
                "render scan; the packaged visual-check protocol adds a "
                "page-by-page inventory and makes the final full-document "
                "human spot-check actionable while keeping it an upload-time "
                "manual action rather than a machine-verified PASS."
            ),
            primary_evidence=[
                "replication/results/jss_formal_compliance_audit.md",
                "replication/results/pdf_render_audit.md",
                "replication/results/pdf_visual_check_protocol.md",
                "replication/scripts/jss_formal_compliance_audit.py",
                "replication/scripts/pdf_render_audit.py",
                "replication/scripts/pdf_visual_check_protocol.py",
                "manuscript/main.pdf",
                "pyproject.toml",
            ],
            verification_gate=(
                "make jss-formal-compliance-audit + "
                "make pdf-visual-check-protocol"
            ),
            metrics={
                "formal_checks": len(formal.get("checks", [])),
                "page_count": formal.get("page_count"),
                "pdf_text_chars": formal.get("pdf_text_chars"),
                "pdf_boundary_snippets": len(formal.get("pdf_boundary_snippets", [])),
                "missing_pdf_boundary_snippets": missing_pdf_boundary_snippets,
                "pdf_stale_prose_hits": formal.get("pdf_stale_prose_hits", []),
                "pdf_render_status": pdf_render.get("status"),
                "pdf_rendered_pages": pdf_render_summary.get("rendered_page_count"),
                "pdf_render_sampled_pages": pdf_render_summary.get("sampled_pages", []),
                "pdf_full_document_rendered_pages": pdf_render_summary.get(
                    "full_document_rendered_page_count"
                ),
                "pdf_full_document_failures": pdf_render_summary.get(
                    "full_document_failure_count"
                ),
                "pdf_render_min_width": pdf_render_summary.get("min_width"),
                "pdf_render_min_height": pdf_render_summary.get("min_height"),
                "pdf_render_min_ink_ratio": pdf_render_summary.get("min_ink_ratio"),
                "pdf_render_max_dark_ratio": pdf_render_summary.get("max_dark_ratio"),
                "pdf_render_failures": pdf_render_summary.get("failure_count"),
                "manual_visual_spot_check_required": manual_visual.get("required"),
                "manual_visual_spot_check_status": manual_visual.get("status"),
                "machine_render_not_human_review": manual_visual.get(
                    "machine_render_not_human_review"
                ),
                "pdf_visual_protocol_status": pdf_protocol.get("status"),
                "pdf_visual_protocol_page_count": pdf_protocol_summary.get(
                    "page_count"
                ),
                "pdf_visual_protocol_checklist_items": (
                    pdf_protocol_summary.get("checklist_item_count")
                ),
                "pdf_visual_protocol_page_inventory_count": (
                    pdf_protocol_summary.get("page_inventory_count")
                ),
                "pdf_visual_protocol_page_inventory_text_pages": (
                    pdf_protocol_summary.get("page_inventory_text_pages")
                ),
                "pdf_visual_protocol_page_inventory_min_text_chars": (
                    pdf_protocol_summary.get("page_inventory_min_text_chars")
                ),
                "pdf_visual_protocol_page_inventory_float_markers": (
                    pdf_protocol_summary.get("page_inventory_float_marker_count")
                ),
                "pdf_visual_protocol_manual_status": (
                    pdf_protocol_summary.get("manual_visual_check_status")
                ),
                "pdf_visual_protocol_claimed_manual_acceptance": (
                    pdf_protocol_summary.get("claimed_manual_acceptance")
                ),
                "pdf_visual_protocol_recorded_by_protocol": (
                    pdf_protocol_summary.get("recorded_by_this_protocol")
                ),
                "pdf_visual_protocol_jss_upload_blocking": (
                    pdf_protocol_summary.get("jss_upload_blocking")
                ),
                "archive_present": formal.get("archive_present"),
                "official_sources_checked": formal.get("official_sources_checked"),
            },
            failures=[
                "JSS formal-compliance checks failed"
                if formal.get("failures")
                else "",
                "PDF boundary snippets are missing from rendered manuscript"
                if missing_pdf_boundary_snippets
                else "",
                "PDF text still contains stale defensive manuscript prose"
                if formal.get("pdf_stale_prose_hits")
                else "",
                "rendered manuscript PDF text was not extracted"
                if formal.get("pdf_text_chars", 0) <= 0
                else "",
                "PDF render audit failed"
                if pdf_render.get("status") != "PASS"
                else "",
                "PDF render audit has stale page count"
                if pdf_render_summary.get("page_count") != formal.get("page_count")
                else "",
                "PDF render audit reports non-passing pages"
                if pdf_render_summary.get("failure_count") not in (0, None)
                else "",
                "PDF full-document machine scan has stale page count"
                if pdf_render_summary.get("full_document_rendered_page_count")
                != formal.get("page_count")
                else "",
                "PDF full-document machine scan reports non-passing pages"
                if pdf_render_summary.get("full_document_failure_count") not in (0, None)
                else "",
                "PDF render audit no longer records the manual visual-check boundary"
                if manual_visual.get("required") is not True
                or manual_visual.get("machine_render_not_human_review") is not True
                else "",
                "manual visual-check boundary has stale status"
                if manual_visual.get("status") != "PENDING_MANUAL_REVIEW"
                else "",
                "PDF visual-check protocol is not PASS"
                if pdf_protocol.get("status") != "PASS"
                else "",
                "PDF visual-check protocol has stale page count"
                if pdf_protocol_summary.get("page_count") != formal.get("page_count")
                else "",
                "PDF visual-check protocol has too few checklist items"
                if pdf_protocol_summary.get("checklist_item_count", 0) < 10
                else "",
                "PDF visual-check protocol page inventory is incomplete"
                if pdf_protocol_summary.get("page_inventory_count")
                != formal.get("page_count")
                or pdf_protocol_summary.get("page_inventory_text_pages")
                != formal.get("page_count")
                else "",
                "PDF visual-check protocol page inventory text is too sparse"
                if pdf_protocol_summary.get("page_inventory_min_text_chars", 0)
                <= 50
                else "",
                "PDF visual-check protocol page inventory lacks float markers"
                if pdf_protocol_summary.get("page_inventory_float_marker_count", 0)
                < 16
                else "",
                "PDF visual-check protocol has stale manual status"
                if pdf_protocol_summary.get("manual_visual_check_status")
                != "PENDING_MANUAL_REVIEW"
                else "",
                "PDF visual-check protocol falsely claims manual acceptance"
                if pdf_protocol_summary.get("claimed_manual_acceptance") is not False
                else "",
                "PDF visual-check protocol falsely records a completed review"
                if pdf_protocol_summary.get("recorded_by_this_protocol") is not False
                else "",
                "PDF visual-check protocol is incorrectly upload-blocking"
                if pdf_protocol_summary.get("jss_upload_blocking") is not False
                else "",
            ],
        )
    )
    cards.append(
        _card(
            card_id="agent_interface_boundary",
            reviewer_question="Are agent-facing claims mechanical rather than behavioural?",
            answer_boundary=(
                "The paper audits a mechanical and contractual interface: "
                "schemas, typed errors, result handles, traceable tool calls, "
                "citation resolution, and the same validation ledger as human "
                "calls, rather than claiming agent performance; the archive "
                "also ships a deferred benchmark protocol with matched "
                "baselines, task families, scoring dimensions, and leakage "
                "controls for the separate behavioural study."
            ),
            primary_evidence=[
                "replication/results/agent_interface_audit.md",
                "replication/results/agent_benchmark_protocol.md",
                "replication/results/ex07_agent_trace.txt",
                "schemas/tools.json",
            ],
            verification_gate="make agent-interface-audit + make agent-benchmark-protocol",
            metrics={
                "schema_files": agent_schema.get("public_surface"),
                "parameter_total": agent_schema.get("parameter_total"),
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
                "protocol_claimed_behavioural_result": (
                    agent_protocol_summary.get("jss_claimed_behavioral_result")
                ),
            },
            failures=[
                "agent trace BibTeX resolution failed"
                if agent_trace.get("bibtex_entry_count") not in (2, None)
                else "",
                "agent benchmark protocol is not PASS"
                if agent_protocol.get("status") != "PASS"
                else "",
                "agent benchmark protocol lacks three comparator arms"
                if agent_protocol_summary.get("arm_count", 0) < 3
                else "",
                "agent benchmark protocol lacks five task families"
                if agent_protocol_summary.get("task_family_count", 0) < 5
                else "",
                "agent benchmark protocol lacks six scoring dimensions"
                if agent_protocol_summary.get("scoring_dimension_count", 0) < 6
                else "",
                "agent benchmark protocol lacks six validity controls"
                if agent_protocol_summary.get("validity_control_count", 0) < 6
                else "",
                "agent benchmark protocol implies completed behavioural results"
                if agent_protocol_summary.get("jss_claimed_behavioral_result")
                is not False
                else "",
            ],
        )
    )
    cards.append(
        _card(
            card_id="limitations_crosswalk",
            reviewer_question=(
                "Where are the compact paper's limitations and residual risks "
                "made explicit?"
            ),
            answer_boundary=(
                "The compact discussion states the main limitations, while "
                "the hardening audit and risk ledger keep the residual "
                "reviewer risks visible without adding pages to the PDF."
            ),
            primary_evidence=[
                "manuscript/sections/09-discussion-compact.tex",
                "REVIEWER-HARDENING-AUDIT.md",
                "replication/results/submission_risk_ledger.md",
                "replication/results/pdf_visual_check_protocol.md",
                "replication/results/validation_evidence_audit.md",
            ],
            verification_gate="make reviewer-evidence-map + make verify-submission-package",
            metrics={
                "pdf_pages": formal.get("page_count"),
                "documented_nonblocking_risk_count": len(risk_details),
                "documented_nonblocking_risk_ids": risk.get(
                    "documented_nonblocking_risk_ids"
                ),
                "pdf_visual_protocol_status": pdf_protocol.get("status"),
                "pdf_visual_protocol_checklist_items": (
                    pdf_protocol_summary.get("checklist_item_count")
                ),
                "pdf_visual_protocol_page_inventory_count": (
                    pdf_protocol_summary.get("page_inventory_count")
                ),
                "pdf_visual_protocol_page_inventory_text_pages": (
                    pdf_protocol_summary.get("page_inventory_text_pages")
                ),
                "pdf_visual_protocol_manual_status": (
                    pdf_protocol_summary.get("manual_visual_check_status")
                ),
                "symbols_with_limitations": validation_summary.get(
                    "symbols_with_limitations"
                ),
                "certified_validated_symbols": validation_summary.get(
                    "certified_validated_symbols"
                ),
                "api_stable_symbols": claim_counts.get("api_stable"),
                "unbacked_auto_stable": claim_counts.get("unbacked_auto"),
            },
            failures=[
                "compact PDF exceeds the intended JSS page budget"
                if formal.get("page_count", 999) > 52
                else "",
                "documented nonblocking risks disappeared"
                if len(risk_details) != len(risk.get("documented_nonblocking_risk_ids") or [])
                else "",
                "validation limitations are not surfaced"
                if validation_summary.get("symbols_with_limitations", 0) <= 0
                else "",
                "PDF visual-check protocol is not surfaced"
                if pdf_protocol.get("status") != "PASS"
                else "",
            ],
        )
    )
    discussion = (PAPER_DIR / "manuscript" / "sections" / "09-discussion-compact.tex")
    discussion_text = (
        discussion.read_text(encoding="utf-8") if discussion.exists() else ""
    )
    discussion_norm = " ".join(discussion_text.split())
    license_path = ROOT / "LICENSE"
    license_text = (
        license_path.read_text(encoding="utf-8") if license_path.exists() else ""
    )
    sustainability_snippets = {
        "mit_forkable": "MIT-licensed" in discussion_norm
        and "validated core can be forked" in discussion_norm,
        "regression_tests": "pinned by a regression test" in discussion_norm,
        "scripted_parity": "cross-language parity harness is fully scripted" in discussion_norm,
        "license_file": "MIT License" in license_text,
    }
    cards.append(
        _card(
            card_id="maintenance_sustainability",
            reviewer_question=(
                "Is the validated core maintainable if the current maintainer or "
                "commercial sponsor changes?"
            ),
            answer_boundary=(
                "The sustainability claim is bounded: the Discussion states that "
                "the validated core is MIT-licensed and forkable, output-changing "
                "fixes are regression-tested, and cross-language parity is scripted "
                "with environment/provenance files."
            ),
            primary_evidence=[
                "manuscript/sections/09-discussion-compact.tex",
                "LICENSE",
                "replication/results/manuscript_artifact_audit.md",
                "replication/results/reproduction_environment_audit.md",
            ],
            verification_gate="make audit + make verify-submission-package",
            metrics={
                **sustainability_snippets,
                "artifact_hash_mismatches": manuscript.get("hash_mismatches"),
                "tier1_complete": repro.get("tier1_transcript_complete"),
                "r_reproduced_modules": repro.get("r_reproduced_modules"),
                "stata_reproduced_modules": repro.get("stata_reproduced_modules"),
            },
            failures=[
                "Discussion does not state MIT/forkability boundary"
                if sustainability_snippets["mit_forkable"] is not True
                else "",
                "Discussion does not state regression-test maintenance boundary"
                if sustainability_snippets["regression_tests"] is not True
                else "",
                "Discussion does not state scripted parity-harness boundary"
                if sustainability_snippets["scripted_parity"] is not True
                else "",
                "root LICENSE is missing the MIT license text"
                if sustainability_snippets["license_file"] is not True
                else "",
                "active artifact hashes are not clean"
                if manuscript.get("hash_mismatches") not in (0, None)
                else "",
                "Tier-1 reviewer transcript is incomplete"
                if repro.get("tier1_transcript_complete") is not True
                else "",
                "R/Stata reproducibility ledgers are incomplete"
                if repro.get("r_reproduced_modules") != _expected_r()
                or repro.get("stata_reproduced_modules") != _expected_stata()
                else "",
            ],
        )
    )
    cards.append(
        _card(
            card_id="final_cut_boundary",
            reviewer_question="What remains after upload before a final tagged release?",
            answer_boundary=(
                "The JSS upload snapshot is separate from final tagged-cut "
                "cleanup; pending worktree, tag, changelog, and Paper-JSS "
                "finalization items are listed as nonblocking final-cut work."
            ),
            primary_evidence=[
                "replication/results/submission_risk_ledger.md",
                "replication/results/source_snapshot_manifest.md",
                "replication/results/release_boundary_audit.md",
            ],
            verification_gate="make submission-risk-ledger + make release-boundary-audit",
            metrics={
                "final_tagged_cut_pending_items": risk.get(
                    "final_tagged_release_blocker_count"
                ),
                "final_tagged_cut_identity_ok": risk.get(
                    "final_tagged_release_blocker_identity_ok"
                ),
                "final_tagged_cut_check_ids": risk.get(
                    "final_tagged_release_blocker_ids"
                ),
                "final_tagged_cut_breakdown": risk_source.get(
                    "release_blocker_breakdown"
                ),
                "final_tagged_cut_runbook_step_count": risk_runbook.get(
                    "step_count"
                ),
                "final_tagged_cut_runbook": risk_runbook,
                "strict_release_command": risk_runbook.get(
                    "strict_release_command"
                ),
                "documented_nonblocking_risk_identity_ok": risk.get(
                    "documented_nonblocking_risk_identity_ok"
                ),
                "documented_nonblocking_risk_count": len(risk_details),
                "documented_nonblocking_risk_ids": risk.get(
                    "documented_nonblocking_risk_ids"
                ),
                "documented_nonblocking_risk_details": risk_details,
                "source_release_pending_paths": risk_source.get(
                    "source_release_blocker_count"
                ),
                "paper_release_pending_paths": risk_source.get(
                    "paper_release_blocker_count"
                ),
                "ready_for_final_publication": release.get("summary", {}).get(
                    "ready_for_final_publication"
                ),
            },
            failures=[
                "documented nonblocking risk identity drift"
                if risk.get("documented_nonblocking_risk_identity_ok") is not True
                else "",
                "documented nonblocking risk detail/order drift"
                if [item.get("risk") for item in risk_details]
                != risk.get("documented_nonblocking_risk_ids")
                else "",
            ],
        )
    )
    for item in cards:
        item["failures"] = [failure for failure in item["failures"] if failure]
        if item["failures"]:
            item["status"] = "FAIL"
    return cards


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    artifacts = _load_artifacts(failures)
    cards = _cards(artifacts) if not failures else []
    routes = _routes(cards) if cards else []
    card_failures = [
        f"{card['id']}: {failure}"
        for card in cards
        for failure in card.get("failures", [])
    ]
    failures.extend(card_failures)
    card_ids = [card.get("id") for card in cards]
    card_identity_ok = card_ids == list(EXPECTED_CARD_IDS)
    if cards and not card_identity_ok:
        failures.append(
            "reviewer evidence card identity/order drift: "
            f"expected={list(EXPECTED_CARD_IDS)}, observed={card_ids}"
        )
    route_ids = [route.get("id") for route in routes]
    route_identity_ok = route_ids == list(EXPECTED_ROUTE_IDS)
    if routes and not route_identity_ok:
        failures.append(
            "review route identity/order drift: "
            f"expected={list(EXPECTED_ROUTE_IDS)}, observed={route_ids}"
        )
    route_failures = [
        f"{route['id']}: missing evidence cards {route['missing_cards']}"
        for route in routes
        if route.get("missing_cards")
    ]
    failures.extend(route_failures)
    archive_resolution = _archive_evidence_resolution([*cards, *routes])
    if archive_resolution["archive_present"] and archive_resolution["missing_paths"]:
        failures.append(
            "reviewer evidence paths missing from submission archive: "
            + ", ".join(archive_resolution["missing_paths"])
        )

    status = "PASS" if not failures else "FAIL"
    summary = {
        "card_count": len(cards),
        "expected_card_ids": list(EXPECTED_CARD_IDS),
        "card_ids": card_ids,
        "card_identity_ok": card_identity_ok,
        "route_count": len(routes),
        "expected_route_ids": list(EXPECTED_ROUTE_IDS),
        "route_ids": route_ids,
        "route_identity_ok": route_identity_ok,
        "failed_routes": sum(
            1 for route in routes if route.get("status") != "PASS"
        ),
        "pass_cards": sum(1 for card in cards if card.get("status") == "PASS"),
        "failed_cards": sum(1 for card in cards if card.get("status") != "PASS"),
        "jss_upload_blockers": (
            artifacts.get("submission_risk", {}).get("jss_upload_blocker_count")
        ),
        "final_tagged_cut_pending_items": (
            artifacts.get("submission_risk", {}).get(
                "final_tagged_release_blocker_count"
            )
        ),
        "final_tagged_cut_runbook_step_count": (
            artifacts.get("submission_risk", {})
            .get("final_tagged_cut_runbook", {})
            .get("step_count")
        ),
        "documented_nonblocking_risk_count": len(
            artifacts.get("submission_risk", {}).get(
                "documented_nonblocking_risks", []
            )
        ),
        "documented_nonblocking_risk_details": (
            artifacts.get("submission_risk", {}).get(
                "documented_nonblocking_risks", []
            )
        ),
        "documented_nonblocking_risk_ids": (
            artifacts.get("submission_risk", {}).get(
                "documented_nonblocking_risk_ids"
            )
        ),
        "documented_nonblocking_risk_identity_ok": (
            artifacts.get("submission_risk", {}).get(
                "documented_nonblocking_risk_identity_ok"
            )
        ),
        "archive_file_count": (
            artifacts.get("submission_risk", {}).get("archive", {}).get("file_count")
        ),
        "pdf_text_chars": (
            artifacts.get("formal_compliance", {}).get("pdf_text_chars")
        ),
        "missing_pdf_boundary_snippets": len(
            artifacts.get("formal_compliance", {}).get(
                "missing_pdf_boundary_snippets", []
            )
        ),
        "pdf_render_status": artifacts.get("pdf_render", {}).get("status"),
        "pdf_render_failure_count": (
            artifacts.get("pdf_render", {}).get("summary", {}).get("failure_count")
        ),
        "pdf_full_document_rendered_page_count": (
            artifacts.get("pdf_render", {})
            .get("summary", {})
            .get("full_document_rendered_page_count")
        ),
        "pdf_full_document_failure_count": (
            artifacts.get("pdf_render", {})
            .get("summary", {})
            .get("full_document_failure_count")
        ),
        "pdf_visual_protocol_status": (
            artifacts.get("pdf_visual_check_protocol", {}).get("status")
        ),
        "pdf_visual_protocol_checklist_items": (
            artifacts.get("pdf_visual_check_protocol", {})
            .get("summary", {})
            .get("checklist_item_count")
        ),
        "pdf_visual_protocol_manual_status": (
            artifacts.get("pdf_visual_check_protocol", {})
            .get("summary", {})
            .get("manual_visual_check_status")
        ),
        "stata_rerun_protocol_status": (
            artifacts.get("stata_rerun_protocol", {}).get("status")
        ),
        "stata_rerun_protocol_checklist_items": (
            artifacts.get("stata_rerun_protocol", {})
            .get("summary", {})
            .get("checklist_item_count")
        ),
        "archive_evidence_present": archive_resolution["archive_present"],
        "archive_evidence_paths_checked": archive_resolution["checked_paths"],
        "archive_evidence_paths_resolved": archive_resolution["resolved_paths"],
        "archive_evidence_paths_missing": len(archive_resolution["missing_paths"]),
        "pdf_pages": artifacts.get("formal_compliance", {}).get("page_count"),
    }
    payload = {
        "generated_at_unix": _generated_at_unix(),
        "status": status,
        "summary": summary,
        "review_routes": routes,
        "cards": cards,
        "failures": failures,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# JSS Reviewer Evidence Map",
        "",
        f"Status: {status}",
        f"Reviewer evidence cards: {summary['card_count']}",
        f"Suggested review routes: {summary['route_count']}",
        (
            "Expected card identity: "
            + ("confirmed" if summary["card_identity_ok"] else "DRIFT")
        ),
        (
            "Expected route identity: "
            + ("confirmed" if summary["route_identity_ok"] else "DRIFT")
        ),
        f"JSS upload blockers: {summary['jss_upload_blockers']}",
        f"Final tagged-cut pending items: {summary['final_tagged_cut_pending_items']}",
        (
            "Archive evidence paths: "
            + (
                f"{summary['archive_evidence_paths_resolved']}/"
                f"{summary['archive_evidence_paths_checked']} resolved"
                if summary["archive_evidence_present"]
                else "not checked because no submission archive is present"
            )
        ),
        "",
        "## Suggested Review Routes",
        "",
        "| Route ID | Status | Use when | First read | Evidence cards | Gate |",
        "|---|---:|---|---|---|---|",
    ]
    for route in routes:
        lines.append(
            "| "
            + f"`{route['id']}`"
            + " | "
            + route["status"]
            + " | "
            + route["use_when"]
            + " | "
            + f"`{route['first_read']}`"
            + " | "
            + ", ".join(f"`{item}`" for item in route["evidence_cards"])
            + " | `"
            + route["verification_gate"]
            + "` |"
        )
    lines.extend(
        [
            "",
            "## Evidence Cards",
            "",
        "| Card ID | Status | Reviewer question | Boundary answer | Primary evidence | Gate |",
        "|---|---|---|---|---|---|",
        ]
    )
    for card in cards:
        evidence = "<br>".join(f"`{item}`" for item in card["primary_evidence"])
        lines.append(
            "| "
            + f"`{card['id']}`"
            + " | "
            + card["status"]
            + " | "
            + card["reviewer_question"]
            + " | "
            + card["answer_boundary"]
            + " | "
            + evidence
            + " | `"
            + card["verification_gate"]
            + "` |"
        )
    lines.extend(["", "## Machine-Readable Metrics", ""])
    for card in cards:
        lines.append(f"### {card['id']}")
        for key, value in card["metrics"].items():
            if key in {
                "documented_nonblocking_risk_details",
                "final_tagged_cut_runbook",
            }:
                continue
            lines.append(f"- `{key}`: `{value}`")
        lines.append("")
    final_cut_runbook = {}
    for card in cards:
        if card.get("id") == "final_cut_boundary":
            final_cut_runbook = (
                card.get("metrics", {}).get("final_tagged_cut_runbook", {})
            )
            break
    lines.extend(["## Final Tagged-Cut Runbook", ""])
    if final_cut_runbook:
        lines.append(str(final_cut_runbook.get("scope", "")))
        lines.append("")
        for item in final_cut_runbook.get("steps", []):
            lines.append(f"{item.get('step')}. {item.get('action')}")
        lines.extend(
            [
                "",
                "Strict release guard: "
                f"`{final_cut_runbook.get('strict_release_command')}`",
                "",
            ]
        )
    else:
        lines.extend(["None.", ""])
    risk_details = summary["documented_nonblocking_risk_details"]
    lines.extend(["## Final-Cut Nonblocking Risk Details", ""])
    if risk_details:
        lines.extend(["| Risk | Evidence | Next action |", "|---|---|---|"])
        for item in risk_details:
            lines.append(
                "| "
                + f"`{_escape_md_cell(item.get('risk'))}`"
                + " | "
                + _escape_md_cell(item.get("evidence"))
                + " | "
                + _escape_md_cell(item.get("next_action"))
                + " |"
            )
    else:
        lines.append("None.")
    lines.append("")
    if failures:
        lines.append("Failures:")
        lines.extend(f"- {failure}" for failure in failures)
        if archive_resolution["missing_paths"]:
            lines.extend(
                f"- missing archive evidence path: `{path}`"
                for path in archive_resolution["missing_paths"]
            )
    else:
        lines.append("Failures: none")
    lines.append("")
    lines.append(f"Machine-readable detail: `{OUT_JSON.relative_to(PAPER_DIR)}`")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"OK -- wrote {OUT_JSON}")
    print(f"OK -- wrote {OUT_MD}")
    if failures:
        print("FAIL -- reviewer evidence map has stale or missing evidence")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

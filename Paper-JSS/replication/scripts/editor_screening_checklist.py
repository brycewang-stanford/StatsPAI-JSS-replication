"""Generate a compact JSS editor-screening checklist.

This report is deliberately not a new source of claims.  It routes the first
editorial checks that are easy to miss at upload time to the generated audits
that already prove them: JSS PDF form, license/citation metadata, source
installability, reproduction paths, archive bounds, related-review and COI
disclosures, documented nonblocking risks, and the final-release boundary.
"""
from __future__ import annotations

import json
import os
import re
import time
import zipfile
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
PAPER_DIR = HERE.parents[1]
RESULTS_DIR = PAPER_DIR / "replication" / "results"
SUBMISSION_ARCHIVE = PAPER_DIR / "build" / "statspai-jss-submission.zip"
OUT_JSON = RESULTS_DIR / "editor_screening_checklist.json"
OUT_MD = RESULTS_DIR / "editor_screening_checklist.md"
SOURCE_DATE_EPOCH = os.environ.get("SOURCE_DATE_EPOCH")

EXPECTED_ITEM_IDS = (
    "jss_pdf_front_matter",
    "license_and_citation",
    "source_installability",
    "reproduction_quick_path",
    "archive_size_boundary",
    "related_review_coi",
    "evidence_navigation",
    "final_release_boundary",
    "nonblocking_risk_crosswalk",
    "artifact_provenance",
    "platform_dependency_boundary",
)

ARTIFACTS = {
    "formal": RESULTS_DIR / "jss_formal_compliance_audit.json",
    "risk": RESULTS_DIR / "submission_risk_ledger.json",
    "reviewer_map": RESULTS_DIR / "reviewer_evidence_map.json",
    "reproduction": RESULTS_DIR / "reproduction_environment_audit.json",
    "stata_rerun_protocol": RESULTS_DIR / "stata_rerun_protocol.json",
    "manuscript": RESULTS_DIR / "manuscript_artifact_audit.json",
    "data_provenance": RESULTS_DIR / "data_provenance_audit.json",
    "source_snapshot": RESULTS_DIR / "source_snapshot_manifest.json",
    "release_boundary": RESULTS_DIR / "release_boundary_audit.json",
    "pdf_render": RESULTS_DIR / "pdf_render_audit.json",
    "pdf_visual_check_protocol": RESULTS_DIR / "pdf_visual_check_protocol.json",
}


def _generated_at_unix() -> int:
    if SOURCE_DATE_EPOCH is not None:
        return int(SOURCE_DATE_EPOCH)
    return int(time.time())


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _formal_check(formal: dict[str, Any], requirement: str) -> dict[str, Any]:
    for check in formal.get("checks", []):
        if check.get("requirement") == requirement:
            return check
    return {
        "requirement": requirement,
        "ok": False,
        "evidence": "required formal-compliance row is missing",
    }


def _status(payload: dict[str, Any]) -> str | None:
    return payload.get("status")


def _count_value(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, (list, tuple, set, dict)):
        return len(value)
    return 0


def _format_int(value: Any) -> str:
    return f"{value:,}" if isinstance(value, int) else str(value)


def _format_float(value: Any) -> str:
    return f"{value:.2f}" if isinstance(value, (int, float)) else str(value)


def _first_match(pattern: str, text: str) -> str:
    match = re.search(pattern, text)
    return match.group(1) if match else "unknown"


def _archive_member_present(rel_path: str, names: set[str]) -> bool:
    return rel_path in names or f"Paper-JSS/{rel_path}" in names


def _archive_evidence(paths: list[str]) -> dict[str, Any]:
    if not SUBMISSION_ARCHIVE.exists():
        return {
            "archive_present": False,
            "checked_paths": len(paths),
            "resolved_paths": None,
            "missing_paths": [],
        }
    with zipfile.ZipFile(SUBMISSION_ARCHIVE) as zf:
        names = set(zf.namelist())
    missing = [path for path in paths if not _archive_member_present(path, names)]
    return {
        "archive_present": True,
        "checked_paths": len(paths),
        "resolved_paths": len(paths) - len(missing),
        "missing_paths": missing,
    }


def _item(
    *,
    item_id: str,
    editor_check: str,
    answer: str,
    primary_evidence: list[str],
    verification_gate: str,
    metrics: dict[str, Any],
    failures: list[str],
) -> dict[str, Any]:
    clean_failures = [failure for failure in failures if failure]
    return {
        "id": item_id,
        "status": "PASS" if not clean_failures else "FAIL",
        "editor_check": editor_check,
        "answer": answer,
        "primary_evidence": primary_evidence,
        "verification_gate": verification_gate,
        "metrics": metrics,
        "failures": clean_failures,
    }


def _load_artifacts() -> tuple[dict[str, dict[str, Any]], list[str]]:
    artifacts: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for name, path in ARTIFACTS.items():
        if not path.exists():
            failures.append(f"missing artifact: {path.relative_to(PAPER_DIR)}")
            continue
        payload = _read_json(path)
        artifacts[name] = payload
        if name != "source_snapshot" and payload.get("status") != "PASS":
            failures.append(
                f"{path.relative_to(PAPER_DIR)} status={payload.get('status')}"
            )
    return artifacts, failures


def _build_items(artifacts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    formal = artifacts["formal"]
    risk = artifacts["risk"]
    reviewer = artifacts["reviewer_map"]
    reproduction = artifacts["reproduction"]
    stata_protocol = artifacts["stata_rerun_protocol"]
    manuscript = artifacts["manuscript"]
    data_provenance = artifacts["data_provenance"]
    source_snapshot = artifacts["source_snapshot"]
    release_boundary = artifacts["release_boundary"]
    pdf_render = artifacts["pdf_render"]
    pdf_protocol = artifacts["pdf_visual_check_protocol"]
    manual_visual = pdf_render.get("manual_preupload_visual_check", {})
    pdf_protocol_summary = pdf_protocol.get("summary", {})

    reviewer_summary = reviewer.get("summary", {})
    reviewer_card_count = reviewer_summary.get("card_count")
    reviewer_route_count = reviewer_summary.get("route_count")
    risk_archive = risk.get("archive", {})
    data_summary = data_provenance.get("summary", {})
    risk_runbook = risk.get("final_tagged_cut_runbook", {})
    reproduction_summary = {
        "status": reproduction.get("status"),
        "tier1_no_r_stata": reproduction.get("tier1_transcript_no_r_stata"),
        "tier1_live_external_call_count": reproduction.get("reproduce", {}).get(
            "tier1_live_external_call_count"
        ),
        "r_reproduced_modules": reproduction.get("r_reproduced_modules"),
        "stata_reproduced_modules": reproduction.get("stata_reproduced_modules"),
    }
    random_seeding = reproduction.get("random_seeding", {})
    stata_protocol_summary = stata_protocol.get("summary", {})
    source_readiness = source_snapshot.get("release_readiness", {})
    source_snapshot_summary = source_snapshot.get("jss_source_snapshot", {})
    release_checked_files = release_boundary.get("checked_files", [])
    submission_archive_status = source_snapshot_summary.get(
        "submission_archive_status", ""
    )

    jss_pdf = _formal_check(
        formal, "PDF manuscript in JSS LaTeX article style"
    )
    license_check = _formal_check(
        formal, "GPL-compatible software license is clearly indicated"
    )
    citation_check = _formal_check(
        formal, "software citation metadata is included"
    )
    install_check = _formal_check(
        formal, "source code is packaged for installation"
    )
    transcript_check = _formal_check(
        formal, "reviewer output transcript for standalone replication script is included"
    )
    quick_path_check = _formal_check(
        formal, "short reviewer replication path completes within one hour"
    )
    archive_check = _formal_check(
        formal, "JSS attachment size and archive source set are bounded"
    )
    related_review_check = _formal_check(
        formal, "cover letter related-review and conflict disclosures are explicit"
    )
    provenance_check = _formal_check(
        formal, "active manuscript tables and figures map to generators and prose"
    )
    platform_check = _formal_check(
        formal, "platform dependencies and RNG seeds are disclosed"
    )
    manuscript_page_count = formal.get("page_count")
    tier1_step_summary = _first_match(
        r"records\s+([0-9]+/[0-9]+)\s+successful steps",
        str(transcript_check.get("evidence", "")),
    )
    if tier1_step_summary == "unknown":
        tier1_step_summary = _first_match(
            r"reports\s+([0-9]+/[0-9]+)\s+steps",
            str(quick_path_check.get("evidence", "")),
        )
    reproduction_summary["tier1_step_summary"] = tier1_step_summary
    archive_size_mib = risk_archive.get("size_mib")
    archive_size_mb_decimal = risk_archive.get("size_mb_decimal")
    archive_file_count = risk_archive.get("file_count")
    jss_upload_blockers = risk.get("jss_upload_blocker_count")
    final_runbook_steps = risk_runbook.get("step_count")
    source_release_pending = source_readiness.get("source_release_blocker_count")
    paper_release_pending = source_readiness.get("paper_release_blocker_count")
    documented_risk_ids = risk.get("documented_nonblocking_risk_ids", [])
    documented_risks = risk.get("documented_nonblocking_risks", [])
    documented_risk_next_actions = [
        item.get("next_action")
        for item in documented_risks
        if item.get("risk") in documented_risk_ids
    ]

    return [
        _item(
            item_id="jss_pdf_front_matter",
            editor_check="Does the submitted PDF look like a JSS article?",
            answer=(
                "The active PDF uses the JSS article class, has complete front "
                f"matter, is {_format_int(manuscript_page_count)} pages, and "
                "passes representative-page plus full-document machine render "
                "sanity audits. The packaged PDF visual-check protocol adds "
                "a page-by-page inventory and makes the final full-document "
                "human spot-check actionable, but the check remains an "
                "upload-time manual action rather than a machine-verified "
                "PASS."
            ),
            primary_evidence=[
                "manuscript/main.pdf",
                "replication/results/jss_formal_compliance_audit.md",
                "replication/results/pdf_render_audit.md",
                "replication/results/pdf_visual_check_protocol.md",
            ],
            verification_gate=(
                "make verify + make jss-formal-compliance-audit + "
                "make pdf-visual-check-protocol"
            ),
            metrics={
                "page_count": manuscript_page_count,
                "pdf_render_status": _status(pdf_render),
                "sampled_pages": pdf_render.get("summary", {}).get("sampled_pages"),
                "full_document_machine_scan_pages": (
                    pdf_render.get("summary", {}).get(
                        "full_document_rendered_page_count"
                    )
                ),
                "full_document_machine_scan_failures": (
                    pdf_render.get("summary", {}).get(
                        "full_document_failure_count"
                    )
                ),
                "manual_visual_spot_check_required": manual_visual.get("required"),
                "manual_visual_spot_check_status": manual_visual.get("status"),
                "machine_render_not_human_review": manual_visual.get(
                    "machine_render_not_human_review"
                ),
                "pdf_visual_protocol_status": _status(pdf_protocol),
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
            },
            failures=[
                jss_pdf.get("evidence") if jss_pdf.get("ok") is not True else "",
                "PDF render audit is not PASS" if _status(pdf_render) != "PASS" else "",
                "PDF full-document machine scan has stale page count"
                if pdf_render.get("summary", {}).get(
                    "full_document_rendered_page_count"
                )
                != manuscript_page_count
                else "",
                "PDF full-document machine scan reports non-passing pages"
                if pdf_render.get("summary", {}).get("full_document_failure_count")
                not in (0, None)
                else "",
                "PDF render audit no longer records the manual visual-check boundary"
                if manual_visual.get("required") is not True
                or manual_visual.get("machine_render_not_human_review") is not True
                else "",
                "manual visual-check boundary has stale status"
                if manual_visual.get("status") != "PENDING_MANUAL_REVIEW"
                else "",
                "PDF visual-check protocol is not PASS"
                if _status(pdf_protocol) != "PASS"
                else "",
                "PDF visual-check protocol page count is stale"
                if pdf_protocol_summary.get("page_count") != manuscript_page_count
                else "",
                "PDF visual-check protocol has too few checklist items"
                if pdf_protocol_summary.get("checklist_item_count", 0) < 10
                else "",
                "PDF visual-check protocol page inventory is incomplete"
                if pdf_protocol_summary.get("page_inventory_count")
                != manuscript_page_count
                or pdf_protocol_summary.get("page_inventory_text_pages")
                != manuscript_page_count
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
            ],
        ),
        _item(
            item_id="license_and_citation",
            editor_check="Are license and citation metadata explicit?",
            answer=(
                "The source archive includes MIT license evidence, GPL-compatible "
                "license disclosure, and root CITATION.cff metadata."
            ),
            primary_evidence=[
                "cover-letter.md",
                "replication/results/jss_formal_compliance_audit.md",
                "CITATION.cff",
                "LICENSE",
            ],
            verification_gate="make jss-formal-compliance-audit",
            metrics={
                "license_check": license_check.get("ok"),
                "citation_check": citation_check.get("ok"),
            },
            failures=[
                license_check.get("evidence")
                if license_check.get("ok") is not True
                else "",
                citation_check.get("evidence")
                if citation_check.get("ok") is not True
                else "",
            ],
        ),
        _item(
            item_id="source_installability",
            editor_check="Can the submitted source be installed/imported?",
            answer=(
                "The formal audit performs a no-deps source install/import probe "
                "against the packaged source and records the console scripts."
            ),
            primary_evidence=[
                "pyproject.toml",
                "src/statspai/__init__.py",
                "replication/results/jss_formal_compliance_audit.md",
            ],
            verification_gate="make jss-formal-compliance-audit",
            metrics={
                "install_check": install_check.get("ok"),
                "package_version": source_snapshot.get("package_metadata_version"),
                "source_version": source_snapshot.get("source_init_version"),
            },
            failures=[
                install_check.get("evidence")
                if install_check.get("ok") is not True
                else "",
            ],
        ),
        _item(
            item_id="reproduction_quick_path",
            editor_check="Is there a short reviewer reproduction path?",
            answer=(
                "Tier 1 rebuilds the Section 4-7 headline numbers without live "
                f"R or Stata and records a {tier1_step_summary} reviewer "
                "transcript."
            ),
            primary_evidence=[
                "replication/reproduce.py",
                "replication/results/reproduce_tier1_output.txt",
                "replication/results/reproduction_environment_audit.md",
            ],
            verification_gate="make reproduce-tier1-transcript + make audit",
            metrics=reproduction_summary,
            failures=[
                transcript_check.get("evidence")
                if transcript_check.get("ok") is not True
                else "",
                quick_path_check.get("evidence")
                if quick_path_check.get("ok") is not True
                else "",
                "Tier 1 transcript has live external-language calls"
                if reproduction_summary["tier1_live_external_call_count"] != 0
                else "",
            ],
        ),
        _item(
            item_id="archive_size_boundary",
            editor_check="Is the upload archive bounded and review-lane clean?",
            answer=(
                "The package is "
                f"{_format_float(archive_size_mib)} MiB "
                f"({_format_float(archive_size_mb_decimal)} MB decimal) with "
                f"{_format_int(archive_file_count)} files, under the 50 MB JSS "
                "limit, and excludes active external-review artifacts plus "
                "dormant manuscript drafts. The data-provenance report "
                "classifies archive data/result members and records zero "
                "forbidden raw-data members, zero private/credential path hits, "
                "and zero unknown categories."
            ),
            primary_evidence=[
                "build/statspai-jss-submission-manifest.md",
                "replication/results/submission_risk_ledger.md",
                "replication/results/data_provenance_audit.md",
                "replication/results/jss_full_audit.md",
            ],
            verification_gate=(
                "make data-provenance-audit + make verify-submission-package"
            ),
            metrics={
                "size_mib": risk_archive.get("size_mib"),
                "size_mb_decimal": risk_archive.get("size_mb_decimal"),
                "file_count": risk_archive.get("file_count"),
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
                "active_external_review_artifacts_present": risk_archive.get(
                    "active_external_review_artifacts_present"
                ),
                "legacy_manuscript_sources_present": risk_archive.get(
                    "legacy_manuscript_sources_present"
                ),
            },
            failures=[
                archive_check.get("evidence")
                if archive_check.get("ok") is not True
                else "",
                "active external-review artifacts are present in archive"
                if risk_archive.get("active_external_review_artifacts_present")
                else "",
                "legacy manuscript sources are present in archive"
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
        ),
        _item(
            item_id="related_review_coi",
            editor_check="Are related-review and COI disclosures explicit?",
            answer=(
                "The cover letter discloses the published JOSS software paper "
                "(doi.org/10.21105/joss.10604), states that this manuscript "
                "cites it and shares no table, figure, simulation, or parity "
                "ledger with it, and names COI and funding/license facts."
            ),
            primary_evidence=[
                "cover-letter.md",
                "replication/results/jss_formal_compliance_audit.md",
                "replication/results/release_boundary_audit.md",
            ],
            verification_gate="make jss-formal-compliance-audit + make release-boundary-audit",
            metrics={
                "related_review_check": related_review_check.get("ok"),
                "release_boundary_status": _status(release_boundary),
                "checked_file_count": len(release_checked_files),
            },
            failures=[
                related_review_check.get("evidence")
                if related_review_check.get("ok") is not True
                else "",
                "release boundary audit is not PASS"
                if _status(release_boundary) != "PASS"
                else "",
            ],
        ),
        _item(
            item_id="evidence_navigation",
            editor_check="Can reviewers navigate evidence without guessing?",
            answer=(
                f"The reviewer map has {reviewer_card_count} stable PASS cards "
                f"and {reviewer_route_count} suggested review routes; every "
                "primary evidence path resolves inside the submission archive."
            ),
            primary_evidence=[
                "replication/results/reviewer_evidence_map.md",
                "replication/results/jss_full_audit.md",
            ],
            verification_gate="make reviewer-evidence-map + make verify-submission-package",
            metrics={
                "card_count": reviewer_summary.get("card_count"),
                "failed_cards": reviewer_summary.get("failed_cards"),
                "route_count": reviewer_summary.get("route_count"),
                "failed_routes": reviewer_summary.get("failed_routes"),
                "archive_evidence_paths_resolved": reviewer_summary.get(
                    "archive_evidence_paths_resolved"
                ),
                "archive_evidence_paths_checked": reviewer_summary.get(
                    "archive_evidence_paths_checked"
                ),
            },
            failures=[
                "reviewer evidence map is not PASS"
                if _status(reviewer) != "PASS"
                else "",
                "reviewer evidence cards failed"
                if reviewer_summary.get("failed_cards") not in (0, None)
                else "",
                "reviewer evidence routes failed"
                if reviewer_summary.get("failed_routes") not in (0, None)
                else "",
                "reviewer evidence archive paths do not all resolve"
                if reviewer_summary.get("archive_evidence_paths_resolved")
                != reviewer_summary.get("archive_evidence_paths_checked")
                else "",
            ],
        ),
        _item(
            item_id="final_release_boundary",
            editor_check="Is upload readiness separated from final release cutting?",
            answer=(
                f"The submission has {_format_int(jss_upload_blockers)} JSS "
                "upload blockers, "
                f"{_format_int(risk.get('final_tagged_release_blocker_count'))} "
                "currently pending final tagged-cut checks, and "
                f"{_format_int(final_runbook_steps)} final tagged-release "
                "runbook steps explicitly listed as nonblocking. The source "
                f"release path has {_format_int(source_release_pending)} "
                "pending source/test/docs blockers, while "
                f"{_format_int(paper_release_pending)} Paper-JSS finalization "
                "paths remain for the tagged release cut."
            ),
            primary_evidence=[
                "replication/results/submission_risk_ledger.md",
                "replication/results/source_snapshot_manifest.md",
                "replication/results/release_boundary_audit.md",
            ],
            verification_gate="make submission-risk-ledger + make verify-submission-package",
            metrics={
                "jss_upload_blockers": risk.get("jss_upload_blocker_count"),
                "final_tagged_cut_pending_items": risk.get(
                    "final_tagged_release_blocker_count"
                ),
                "runbook_step_count": risk_runbook.get("step_count"),
                "ready_for_final_publication": source_readiness.get(
                    "ready_for_final_publication"
                ),
                "source_release_pending_paths": source_release_pending,
                "paper_release_pending_paths": paper_release_pending,
                "submission_archive_status": source_snapshot_summary.get(
                    "submission_archive_status"
                ),
            },
            failures=[
                "submission risk ledger is not PASS" if _status(risk) != "PASS" else "",
                "release boundary audit is not PASS"
                if _status(release_boundary) != "PASS"
                else "",
                "JSS upload blockers remain"
                if risk.get("jss_upload_blocker_count") != 0
                else "",
                "final tagged-cut runbook is missing"
                if risk_runbook.get("step_count") != len(
                    source_readiness.get("final_publication_requirements", [])
                )
                else "",
                "source-snapshot archive boundary is not disclosed"
                if "not a JSS upload reproducibility failure"
                not in str(submission_archive_status)
                else "",
                "final tagged-cut blocker identity drift"
                if risk.get("final_tagged_release_blocker_identity_ok") is not True
                else "",
            ],
        ),
        _item(
            item_id="nonblocking_risk_crosswalk",
            editor_check="Are residual risks disclosed without hiding upload blockers?",
            answer=(
                "The risk ledger lists "
                f"{_format_int(len(documented_risk_ids))} documented "
                "nonblocking risks with next actions and "
                f"{_format_int(jss_upload_blockers)} JSS upload blockers: "
                "final tagged-release cleanup; registry-breadth denominator "
                "disclosure; Stata Tier 3 license boundary; methodological/T4 "
                "disclosure; compact-text/PDF-review boundary (PDF-visible "
                "evidence routing, page-inventory navigation, and final manual "
                "PDF visual-check protocol); and agent-interface value boundary."
            ),
            primary_evidence=[
                "replication/results/submission_risk_ledger.md",
                "replication/results/reviewer_evidence_map.md",
                "manuscript/sections/09-discussion-compact.tex",
            ],
            verification_gate="make submission-risk-ledger + make reviewer-evidence-map",
            metrics={
                "documented_nonblocking_risk_count": len(documented_risk_ids),
                "documented_nonblocking_risk_ids": documented_risk_ids,
                "documented_nonblocking_risk_identity_ok": risk.get(
                    "documented_nonblocking_risk_identity_ok"
                ),
                "risks_with_next_action_count": sum(
                    1 for action in documented_risk_next_actions if action
                ),
                "jss_upload_blockers": jss_upload_blockers,
            },
            failures=[
                "submission risk ledger is not PASS" if _status(risk) != "PASS" else "",
                "documented nonblocking risk identity drift"
                if risk.get("documented_nonblocking_risk_identity_ok") is not True
                else "",
                "documented nonblocking risks lack next actions"
                if sum(1 for action in documented_risk_next_actions if action)
                != len(documented_risk_ids)
                else "",
                "JSS upload blockers remain"
                if jss_upload_blockers != 0
                else "",
            ],
        ),
        _item(
            item_id="artifact_provenance",
            editor_check="Do active tables and figures map to generators?",
            answer=(
                "The manuscript-artifact audit maps active tables/figures to "
                "generators, checks narrative references plus hashes, and "
                "guards compact-section contribution/evidence/boundary anchors."
            ),
            primary_evidence=[
                "replication/results/manuscript_artifact_audit.md",
                "manuscript/main.tex",
            ],
            verification_gate="make manuscript-artifact-audit",
            metrics={
                "artifact_count": manuscript.get("artifact_count"),
                "hash_mismatches": _count_value(manuscript.get("hash_mismatches")),
                "missing_refs": _count_value(
                    manuscript.get("missing_narrative_refs")
                ),
                "dangling_refs": _count_value(
                    manuscript.get("dangling_float_refs")
                ),
                "compact_sections_checked": manuscript.get(
                    "compact_section_coverage", {}
                ).get("sections_checked"),
                "compact_sections_passed": manuscript.get(
                    "compact_section_coverage", {}
                ).get("sections_passed"),
                "compact_missing_anchors": manuscript.get(
                    "compact_section_coverage", {}
                ).get("missing_anchor_count"),
            },
            failures=[
                provenance_check.get("evidence")
                if provenance_check.get("ok") is not True
                else "",
                "manuscript artifact audit is not PASS"
                if _status(manuscript) != "PASS"
                else "",
                "compact section coverage is not complete"
                if manuscript.get("compact_section_coverage", {}).get("ok")
                is not True
                else "",
            ],
        ),
        _item(
            item_id="platform_dependency_boundary",
            editor_check="Are platform dependencies and RNG boundaries explicit?",
            answer=(
                "The reproduction-environment audit verifies Docker/Python/R/"
                "Stata contracts, complete external-language ledgers, and zero "
                "unseeded stochastic reproduction scripts. The Stata Tier-3 "
                "rerun protocol records the licensed optional rerun path without "
                "making missing Stata an upload blocker."
            ),
            primary_evidence=[
                "replication/results/reproduction_environment_audit.md",
                "replication/results/stata_rerun_protocol.md",
                "replication/Dockerfile",
                "requirements-jss.txt",
            ],
            verification_gate=(
                "make reproduction-environment-audit + make stata-rerun-protocol"
            ),
            metrics={
                "reproduction_status": _status(reproduction),
                "stata_rerun_protocol_status": _status(stata_protocol),
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
                "stata_rerun_checklist_items": (
                    stata_protocol_summary.get("checklist_item_count")
                ),
                "tier1_no_r_stata": reproduction_summary["tier1_no_r_stata"],
                "r_reproduced_modules": reproduction_summary["r_reproduced_modules"],
                "stata_reproduced_modules": reproduction_summary[
                    "stata_reproduced_modules"
                ],
                "stochastic_file_count": random_seeding.get(
                    "stochastic_file_count", 0
                ),
                "unseeded_stochastic_file_count": random_seeding.get(
                    "unseeded_stochastic_file_count", 0
                ),
                "unseeded_stochastic_files": random_seeding.get(
                    "unseeded_stochastic_files", []
                ),
            },
            failures=[
                platform_check.get("evidence")
                if platform_check.get("ok") is not True
                else "",
                "reproduction environment audit is not PASS"
                if _status(reproduction) != "PASS"
                else "",
                "Stata rerun protocol is not PASS"
                if _status(stata_protocol) != "PASS"
                else "",
                "Stata rerun protocol lost license boundary"
                if stata_protocol_summary.get("requires_stata_license") is not True
                else "",
                "Stata rerun protocol is incorrectly upload-blocking"
                if stata_protocol_summary.get("jss_upload_blocking") is not False
                else "",
                "Stata rerun protocol falsely claims a current live rerun"
                if stata_protocol_summary.get("claimed_current_machine_live_rerun")
                is not False
                else "",
            ],
        ),
    ]


def _escape_md_cell(value: object) -> str:
    return str(value).replace("|", r"\|").replace("\n", " ")


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    artifacts, failures = _load_artifacts()
    items = _build_items(artifacts) if not failures else []
    item_ids = [item.get("id") for item in items]
    item_identity_ok = item_ids == list(EXPECTED_ITEM_IDS)
    if items and not item_identity_ok:
        failures.append(
            "editor checklist item identity/order drift: "
            f"expected={list(EXPECTED_ITEM_IDS)}, observed={item_ids}"
        )
    item_failures = [
        f"{item['id']}: {failure}"
        for item in items
        for failure in item.get("failures", [])
    ]
    failures.extend(item_failures)
    evidence_resolution = _archive_evidence(
        sorted(
            {
                path
                for item in items
                for path in item.get("primary_evidence", [])
                if isinstance(path, str) and not path.startswith("build/")
            }
        )
    )
    if evidence_resolution["archive_present"] and evidence_resolution["missing_paths"]:
        failures.append(
            "editor checklist evidence paths missing from submission archive: "
            + ", ".join(evidence_resolution["missing_paths"])
        )

    status = "PASS" if not failures else "FAIL"
    summary = {
        "item_count": len(items),
        "expected_item_ids": list(EXPECTED_ITEM_IDS),
        "item_ids": item_ids,
        "item_identity_ok": item_identity_ok,
        "pass_items": sum(1 for item in items if item.get("status") == "PASS"),
        "failed_items": sum(1 for item in items if item.get("status") != "PASS"),
        "jss_upload_blockers": (
            artifacts.get("risk", {}).get("jss_upload_blocker_count")
        ),
        "archive_file_count": (
            artifacts.get("risk", {}).get("archive", {}).get("file_count")
        ),
        "archive_size_mib": (
            artifacts.get("risk", {}).get("archive", {}).get("size_mib")
        ),
        "archive_size_mb_decimal": (
            artifacts.get("risk", {}).get("archive", {}).get("size_mb_decimal")
        ),
        "page_count": artifacts.get("formal", {}).get("page_count"),
        "manual_visual_spot_check_status": next(
            (
                item.get("metrics", {}).get("manual_visual_spot_check_status")
                for item in items
                if item.get("id") == "jss_pdf_front_matter"
            ),
            None,
        ),
        "pdf_visual_protocol_status": next(
            (
                item.get("metrics", {}).get("pdf_visual_protocol_status")
                for item in items
                if item.get("id") == "jss_pdf_front_matter"
            ),
            None,
        ),
        "pdf_visual_protocol_checklist_items": next(
            (
                item.get("metrics", {}).get("pdf_visual_protocol_checklist_items")
                for item in items
                if item.get("id") == "jss_pdf_front_matter"
            ),
            None,
        ),
        "tier1_step_summary": next(
            (
                item.get("metrics", {}).get("tier1_step_summary")
                for item in items
                if item.get("id") == "reproduction_quick_path"
            ),
            None,
        ),
        "reviewer_card_count": (
            artifacts.get("reviewer_map", {}).get("summary", {}).get("card_count")
        ),
        "reviewer_route_count": (
            artifacts.get("reviewer_map", {}).get("summary", {}).get("route_count")
        ),
        "final_tagged_cut_runbook_steps": (
            artifacts.get("risk", {}).get("final_tagged_cut_runbook", {}).get(
                "step_count"
            )
        ),
        "final_tagged_cut_pending_items": (
            artifacts.get("risk", {}).get("final_tagged_release_blocker_count")
        ),
        "documented_nonblocking_risk_count": len(
            artifacts.get("risk", {}).get("documented_nonblocking_risk_ids", [])
        ),
        "documented_nonblocking_risk_ids": (
            artifacts.get("risk", {}).get("documented_nonblocking_risk_ids", [])
        ),
        "source_release_pending_paths": (
            artifacts.get("source_snapshot", {})
            .get("release_readiness", {})
            .get("source_release_blocker_count")
        ),
        "paper_release_pending_paths": (
            artifacts.get("source_snapshot", {})
            .get("release_readiness", {})
            .get("paper_release_blocker_count")
        ),
        "archive_evidence_present": evidence_resolution["archive_present"],
        "archive_evidence_paths_checked": evidence_resolution["checked_paths"],
        "archive_evidence_paths_resolved": evidence_resolution["resolved_paths"],
        "archive_evidence_paths_missing": len(evidence_resolution["missing_paths"]),
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
        "# JSS Editor Screening Checklist",
        "",
        f"Status: {status}",
        f"Checklist items: {summary['item_count']}",
        "Expected item identity: "
        + ("confirmed" if item_identity_ok else "DRIFT"),
        f"JSS upload blockers: {summary['jss_upload_blockers']}",
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
        "| Item ID | Status | Editor check | Answer | Primary evidence | Gate |",
        "|---|---:|---|---|---|---|",
    ]
    for item in items:
        evidence = "<br>".join(f"`{path}`" for path in item["primary_evidence"])
        lines.append(
            "| "
            + f"`{item['id']}`"
            + " | "
            + item["status"]
            + " | "
            + _escape_md_cell(item["editor_check"])
            + " | "
            + _escape_md_cell(item["answer"])
            + " | "
            + evidence
            + " | `"
            + _escape_md_cell(item["verification_gate"])
            + "` |"
        )
    lines.extend(["", "## Machine-Readable Metrics", ""])
    for item in items:
        lines.append(f"### {item['id']}")
        for key, value in item["metrics"].items():
            lines.append(f"- `{key}`: `{value}`")
        lines.append("")
    if failures:
        lines.append("Failures:")
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.append("Failures: none")
    lines.append("")
    lines.append(f"Machine-readable detail: `{OUT_JSON.relative_to(PAPER_DIR)}`")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK -- wrote {OUT_JSON}")
    print(f"OK -- wrote {OUT_MD}")
    if failures:
        print("FAIL -- editor screening checklist has stale or missing evidence")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

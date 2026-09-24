"""Generate a JSS upload-risk ledger from the current audit artifacts.

This ledger separates two states that reviewers can easily conflate:
the JSS source-snapshot archive can be internally coherent and uploadable,
while the final tagged release cut can still be pending because local
manuscript/source edits have not been committed, changelog-finalized, and
tagged. The script is intentionally a reader of existing audit evidence.
"""
from __future__ import annotations

import json
import os
import re
import time
import zipfile
from pathlib import Path
from typing import Any

import sys
_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:  # _paths.py sits beside this script; importlib loaders do not add the script dir
    sys.path.insert(0, _SCRIPTS_DIR)

from _paths import PAPER_ROOT as _PAPER_ROOT
from _paths import statspai_root as _statspai_root


HERE = Path(__file__).resolve().parent
PAPER_DIR = _PAPER_ROOT
ROOT = _statspai_root()  # see _paths.py: worktree-safe
RESULTS_DIR = PAPER_DIR / "replication" / "results"
BUILD_DIR = PAPER_DIR / "build"
ARCHIVE = BUILD_DIR / "statspai-jss-submission.zip"
ARCHIVE_MANIFEST = BUILD_DIR / "statspai-jss-submission-manifest.json"
OUT_JSON = RESULTS_DIR / "submission_risk_ledger.json"
OUT_MD = RESULTS_DIR / "submission_risk_ledger.md"
SOURCE_DATE_EPOCH = os.environ.get("SOURCE_DATE_EPOCH")

ACTIVE_MANUSCRIPT_SECTIONS = {
    "Paper-JSS/manuscript/sections/01-introduction-compact.tex",
    "Paper-JSS/manuscript/sections/02-architecture-compact.tex",
    "Paper-JSS/manuscript/sections/03-agent-facing-compact.tex",
    "Paper-JSS/manuscript/sections/04-examples-compact.tex",
    "Paper-JSS/manuscript/sections/05-parity-compact.tex",
    "Paper-JSS/manuscript/sections/06-performance.tex",
    "Paper-JSS/manuscript/sections/07-agent-eval.tex",
    "Paper-JSS/manuscript/sections/08-computational-details-compact.tex",
    "Paper-JSS/manuscript/sections/09-discussion-compact.tex",
    # The parity appendix, compiled since the full Track A ledger moved
    # out of the archive and into the PDF.
    "Paper-JSS/manuscript/sections/appendix.tex",
}

ACTIVE_EXTERNAL_REVIEW_ARTIFACTS = {
    "paper.md",
    "docs/" + ("jo" "ss_reviewer_guide.md"),
    "docs/" + ("jo" "ss_validation_dossier.md"),
}

FORBIDDEN_ARCHIVE_PATTERNS = (
    re.compile(r"^paper\.md$"),
    re.compile(r"^docs/" + ("jo" "ss_")),
    re.compile(r"^Paper-JSS/notes/"),
    re.compile(r"^Paper-JSS/manuscript/main\.md$"),
    re.compile(
        r"^Paper-JSS/manuscript/sections/"
        r"(?:01-introduction|02-architecture|03-agent-facing|04-examples|"
        r"05-parity|08-computational-details|09-discussion)\.tex$"
    ),
)

AUDIT_STATUS_FILES = {
    "claim_lint": RESULTS_DIR / "claim_lint.json",
    "validation_evidence": RESULTS_DIR / "validation_evidence_audit.json",
    "methodological_gap_ledger": RESULTS_DIR / "methodological_gap_ledger.json",
    "stata_bridge": RESULTS_DIR / "stata_bridge_audit.json",
    "stata_rerun_protocol": RESULTS_DIR / "stata_rerun_protocol.json",
    "agent_interface": RESULTS_DIR / "agent_interface_audit.json",
    "release_boundary": RESULTS_DIR / "release_boundary_audit.json",
    "reproduction_environment": RESULTS_DIR / "reproduction_environment_audit.json",
    "manuscript_artifacts": RESULTS_DIR / "manuscript_artifact_audit.json",
    "pdf_visual_check_protocol": RESULTS_DIR / "pdf_visual_check_protocol.json",
    "jss_formal_compliance": RESULTS_DIR / "jss_formal_compliance_audit.json",
}

EXPECTED_FINAL_TAGGED_RELEASE_BLOCKERS = (
    "clean_combined_worktree",
    "package_tag_at_head",
    "unreleased_changelog_finalized",
    "source_paths_finalized",
    "paper_paths_finalized",
)

EXPECTED_DOCUMENTED_NONBLOCKING_RISKS = (
    "final_tagged_release_cut_pending",
    "registry_breadth_denominator_disclosed",
    "stata_tier3_requires_license",
    "methodological_t4_row_disclosed",
    "compact_text_may_feel_terse",
    "agent_interface_value_boundary",
)

RELEASE_BREAKDOWN_ROWS = (
    ("hand_edited_status_counts", "Hand-edited status counts"),
    ("generated_status_counts", "Generated status counts"),
    ("package_code_paths", "Package code/script paths"),
    ("package_docs_paths", "Package docs paths"),
    ("validation_test_paths", "Validation test/data paths"),
    ("paper_manuscript_paths", "Paper manuscript paths"),
    ("paper_replication_paths", "Paper replication paths"),
    ("paper_other_paths", "Paper other paths"),
)


def _is_ordered_expected_subset(observed: list[str], expected: list[str]) -> bool:
    return (
        all(item in expected for item in observed)
        and observed == [item for item in expected if item in observed]
    )


def _generated_at_unix() -> int:
    if SOURCE_DATE_EPOCH is not None:
        return int(SOURCE_DATE_EPOCH)
    return int(time.time())


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _check(ok: bool, name: str, detail: str, blockers: list[dict[str, str]]) -> dict[str, Any]:
    if not ok:
        blockers.append({"check": name, "detail": detail})
    return {"check": name, "ok": ok, "detail": detail}


def _audit_status_checks(blockers: list[dict[str, str]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    payloads: dict[str, Any] = {}
    for name, path in AUDIT_STATUS_FILES.items():
        if not path.exists():
            checks.append(
                _check(
                    False,
                    f"{name}_present",
                    f"missing {path.relative_to(PAPER_DIR)}",
                    blockers,
                )
            )
            continue
        payload = _read_json(path)
        payloads[name] = payload
        status = payload.get("status")
        checks.append(
            _check(
                status == "PASS",
                f"{name}_pass",
                f"{path.relative_to(PAPER_DIR)} status={status}",
                blockers,
            )
        )
    return checks, payloads


def _archive_checks(blockers: list[dict[str, str]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "present": ARCHIVE.exists(),
        "manifest_present": ARCHIVE_MANIFEST.exists(),
        "forbidden_members": [],
        "active_external_review_artifacts_present": [],
        "legacy_manuscript_sources_present": [],
    }
    checks.append(
        _check(
            ARCHIVE.exists(),
            "archive_present",
            str(ARCHIVE.relative_to(PAPER_DIR)),
            blockers,
        )
    )
    checks.append(
        _check(
            ARCHIVE_MANIFEST.exists(),
            "archive_manifest_present",
            str(ARCHIVE_MANIFEST.relative_to(PAPER_DIR)),
            blockers,
        )
    )
    if not ARCHIVE.exists() or not ARCHIVE_MANIFEST.exists():
        return checks, summary

    manifest = _read_json(ARCHIVE_MANIFEST)
    summary.update(
        {
            "file_count": manifest.get("file_count"),
            "size_mib": manifest.get("size_mib"),
            "size_mb_decimal": manifest.get("size_mb_decimal"),
            "within_jss_attachment_limit": manifest.get("within_jss_attachment_limit"),
            "registry_evidence_file_count": manifest.get("registry_evidence_file_count"),
            "active_manuscript_sections": manifest.get("active_manuscript_sections", []),
            "active_external_review_artifact_exclusion_count": len(
                manifest.get("active_external_review_artifacts_excluded", [])
            ),
        }
    )
    checks.append(
        _check(
            manifest.get("within_jss_attachment_limit") is True,
            "archive_within_50mb",
            (
                f"{manifest.get('size_mib')} MiB / "
                f"{manifest.get('size_mb_decimal')} MB decimal"
            ),
            blockers,
        )
    )
    checks.append(
        _check(
            set(manifest.get("active_manuscript_sections", []))
            == ACTIVE_MANUSCRIPT_SECTIONS,
            "active_manuscript_sections_only",
            "archive manifest lists the ten active manuscript inputs",
            blockers,
        )
    )
    checks.append(
        _check(
            set(manifest.get("active_external_review_artifacts_excluded", []))
            == ACTIVE_EXTERNAL_REVIEW_ARTIFACTS,
            "active_joss_artifacts_excluded",
            "active external-review artifacts are declared excluded from the JSS archive",
            blockers,
        )
    )

    with zipfile.ZipFile(ARCHIVE) as zf:
        names = set(zf.namelist())
    forbidden = sorted(
        name for name in names
        if any(pattern.search(name) for pattern in FORBIDDEN_ARCHIVE_PATTERNS)
    )
    active_external_present = sorted(ACTIVE_EXTERNAL_REVIEW_ARTIFACTS & names)
    legacy_sources = sorted(
        name for name in names
        if name.startswith("Paper-JSS/manuscript/sections/")
        and name.removeprefix("Paper-JSS/manuscript/sections/") in {
            "01-introduction.tex",
            "02-architecture.tex",
            "03-agent-facing.tex",
            "04-examples.tex",
            "05-parity.tex",
            "08-computational-details.tex",
            "09-discussion.tex",
        }
    )
    summary["forbidden_members"] = forbidden
    summary["active_external_review_artifacts_present"] = active_external_present
    summary["legacy_manuscript_sources_present"] = legacy_sources
    checks.append(
        _check(
            not forbidden,
            "archive_forbidden_members_absent",
            "no JOSS artifacts, local notes, main.md, or dormant full sections in archive",
            blockers,
        )
    )
    return checks, summary


def _source_snapshot_checks(blockers: list[dict[str, str]]) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, str]]]:
    checks: list[dict[str, Any]] = []
    final_release_blockers: list[dict[str, str]] = []
    path = RESULTS_DIR / "source_snapshot_manifest.json"
    if not path.exists():
        checks.append(
            _check(
                False,
                "source_snapshot_present",
                "missing replication/results/source_snapshot_manifest.json",
                blockers,
            )
        )
        return checks, {}, final_release_blockers

    payload = _read_json(path)
    readiness = payload.get("release_readiness", {})
    snapshot = payload.get("jss_source_snapshot", {})
    checks.append(
        _check(
            payload.get("version_consistent_inside_source") is True,
            "versions_consistent_inside_source",
            (
                f"package={payload.get('package_metadata_version')}; "
                f"source={payload.get('source_init_version')}; "
                f"schema={payload.get('schema_bundle_version')}"
            ),
            blockers,
        )
    )
    status = str(snapshot.get("submission_archive_status", ""))
    checks.append(
        _check(
            "not a JSS upload reproducibility failure" in status,
            "source_snapshot_submission_status_disclosed",
            status,
            blockers,
        )
    )
    for item in readiness.get("release_gate_checks", []):
        if item.get("ok") is False:
            final_release_blockers.append(
                {"check": str(item.get("check")), "detail": str(item.get("detail"))}
            )
    final_release_blocker_ids = [item["check"] for item in final_release_blockers]
    expected_final_release_blockers = list(EXPECTED_FINAL_TAGGED_RELEASE_BLOCKERS)
    final_release_blocker_identity_ok = _is_ordered_expected_subset(
        final_release_blocker_ids,
        expected_final_release_blockers,
    )
    checks.append(
        _check(
            final_release_blocker_identity_ok,
            "final_tagged_release_blocker_identity",
            (
                "expected_ordered_subset_of="
                f"{expected_final_release_blockers}; "
                f"observed={final_release_blocker_ids}"
            ),
            blockers,
        )
    )
    return checks, {
        "package_metadata_version": payload.get("package_metadata_version"),
        "source_init_version": payload.get("source_init_version"),
        "schema_bundle_version": payload.get("schema_bundle_version"),
        "package_commit": payload.get("git", {}).get("short_commit"),
        "paper_commit": payload.get("paper_git", {}).get("short_commit"),
        "ready_for_final_publication": readiness.get("ready_for_final_publication"),
        "release_blocker_count": readiness.get("release_blocker_count"),
        "source_release_blocker_count": readiness.get("source_release_blocker_count"),
        "paper_release_blocker_count": readiness.get("paper_release_blocker_count"),
        "generated_dirty_count": readiness.get("generated_dirty_count"),
        "release_blocker_breakdown": readiness.get(
            "release_blocker_breakdown", {}
        ),
        "strict_release_command": readiness.get("strict_release_command"),
        "expected_final_tagged_release_blocker_ids": list(
            EXPECTED_FINAL_TAGGED_RELEASE_BLOCKERS
        ),
        "final_tagged_release_blocker_ids": final_release_blocker_ids,
        "final_tagged_release_blocker_identity_ok": (
            final_release_blocker_identity_ok
        ),
        "final_publication_requirements": readiness.get(
            "final_publication_requirements", []
        ),
        "submission_archive_status": snapshot.get("submission_archive_status"),
    }, final_release_blockers


def _nonblocking_risks(
    payloads: dict[str, Any],
    source_summary: dict[str, Any],
    final_release_blockers: list[dict[str, str]],
) -> list[dict[str, str]]:
    risks: list[dict[str, str]] = []
    if final_release_blockers:
        risks.append(
            {
                "risk": "final_tagged_release_cut_pending",
                "evidence": (
                    f"{source_summary.get('release_blocker_count')} final-release "
                    "pending paths; source snapshot remains explicitly labelled"
                ),
                "next_action": "; ".join(
                    source_summary.get("final_publication_requirements", [])
                ),
            }
        )
    validation = payloads.get("validation_evidence", {}).get("summary", {})
    if validation.get("registry_symbols") is not None:
        risks.append(
            {
                "risk": "registry_breadth_denominator_disclosed",
                "evidence": (
                    f"{validation.get('certified_validated_symbols')}/"
                    f"{validation.get('registry_symbols')} registry symbols "
                    "are certified/validated; missing evidence paths="
                    f"{validation.get('missing_evidence_paths')}"
                ),
                "next_action": (
                    "Keep the validated-core framing and do not promote "
                    "API-stable breadth without attached evidence notes."
                ),
            }
        )
    repro = payloads.get("reproduction_environment", {})
    if repro.get("stata_environment_present"):
        stata_protocol = payloads.get("stata_rerun_protocol", {})
        stata_protocol_summary = stata_protocol.get("summary", {})
        protocol_status = (
            "licensed rerun protocol packaged"
            if stata_protocol.get("status") == "PASS"
            and stata_protocol_summary.get("requires_stata_license") is True
            and stata_protocol_summary.get("jss_upload_blocking") is False
            and stata_protocol_summary.get("claimed_current_machine_live_rerun")
            is False
            else "licensed rerun protocol incomplete"
        )
        risks.append(
            {
                "risk": "stata_tier3_requires_license",
                "evidence": (
                    f"{repro.get('stata_reproduced_modules')}/"
                    f"{repro.get('stata_expected_reproduced_modules')} frozen "
                    f"Stata modules audited without live Stata; {protocol_status}"
                ),
                "next_action": (
                    "Keep Tier 3 optional and keep the Stata license boundary "
                    "explicit; use stata_rerun_protocol.md for any licensed "
                    "reviewer rerun and treat missing Stata as an optional-runtime "
                    "skip, not a JSS upload blocker."
                ),
            }
        )
    gap = payloads.get("methodological_gap_ledger", {}).get("summary", {})
    if gap.get("methodological_gap_count"):
        risks.append(
            {
                "risk": "methodological_t4_row_disclosed",
                "evidence": (
                    f"{gap.get('classified_gap_count')}/"
                    f"{gap.get('methodological_gap_count')} methodological/T4 "
                    "rows classified; uncategorized="
                    f"{gap.get('uncategorized_gap_count')}"
                ),
                "next_action": "Keep the T4 row as a disclosure unless a deterministic T2 bridge is added.",
            }
        )
    formal = payloads.get("jss_formal_compliance", {})
    if formal.get("page_count") is not None:
        missing_pdf_snippets = formal.get("missing_pdf_boundary_snippets") or []
        pdf_protocol = payloads.get("pdf_visual_check_protocol", {})
        protocol_summary = pdf_protocol.get("summary", {})
        pdf_routing_status = (
            "PDF-visible evidence-map/checklist routing present"
            if "reviewer evidence map and editor screening checklist"
            in set(formal.get("pdf_boundary_snippets") or [])
            and not missing_pdf_snippets
            else "PDF-visible evidence routing incomplete"
        )
        protocol_status = (
            "packaged PDF visual-check protocol present"
            if pdf_protocol.get("status") == "PASS"
            and protocol_summary.get("manual_visual_check_status")
            == "PENDING_MANUAL_REVIEW"
            and protocol_summary.get("claimed_manual_acceptance") is False
            else "PDF visual-check protocol incomplete"
        )
        inventory_status = (
            "page inventory covers "
            f"{protocol_summary.get('page_inventory_count')}/"
            f"{formal.get('page_count')} pages"
            if protocol_summary.get("page_inventory_count") == formal.get("page_count")
            and protocol_summary.get("page_inventory_text_pages")
            == formal.get("page_count")
            and protocol_summary.get("page_inventory_min_text_chars", 0) > 50
            else "page inventory incomplete"
        )
        risks.append(
            {
                "risk": "compact_text_may_feel_terse",
                "evidence": (
                    f"active PDF has {formal.get('page_count')} pages; "
                    f"{pdf_routing_status}; {protocol_status}; "
                    f"{inventory_status}"
                ),
                "next_action": (
                    "Keep additional reviewer evidence in replication/results "
                    "and reviewer_evidence_map rather than expanding main.pdf; "
                    "perform the final full-document human visual spot-check "
                    "using pdf_visual_check_protocol.md and the PDF render "
                    "audit before JSS upload."
                ),
            }
        )
    agent = payloads.get("agent_interface", {})
    schema_quality = agent.get("schema_quality", {})
    agent_trace = agent.get("agent_trace", {})
    if schema_quality.get("public_surface") is not None:
        risks.append(
            {
                "risk": "agent_interface_value_boundary",
                "evidence": (
                    f"{schema_quality.get('public_surface')} schemas, "
                    f"{schema_quality.get('parameter_total')} documented "
                    "parameters, and "
                    f"{agent_trace.get('tool_count')} trace tools audited "
                    "without behavioural benchmark claims"
                ),
                "next_action": (
                    "Keep the agent section mechanical and contractual unless "
                    "a behavioural benchmark is actually run and packaged; "
                    "keep the deferred benchmark protocol labelled as protocol "
                    "rather than a completed behavioural result."
                ),
            }
        )
    return risks


def _final_tagged_cut_runbook(source_summary: dict[str, Any]) -> dict[str, Any]:
    requirements = list(source_summary.get("final_publication_requirements", []) or [])
    steps = [
        {"step": index, "action": action}
        for index, action in enumerate(requirements, start=1)
    ]
    return {
        "scope": (
            "Nonblocking post-upload release-cut work; not a JSS source-snapshot "
            "upload blocker."
        ),
        "step_count": len(steps),
        "steps": steps,
        "requirements": requirements,
        "strict_release_command": source_summary.get("strict_release_command"),
    }


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    upload_blockers: list[dict[str, str]] = []
    audit_checks, payloads = _audit_status_checks(upload_blockers)
    archive_checks, archive_summary = _archive_checks(upload_blockers)
    source_checks, source_summary, final_release_blockers = _source_snapshot_checks(
        upload_blockers
    )
    nonblocking_risks = _nonblocking_risks(
        payloads, source_summary, final_release_blockers
    )
    final_tagged_cut_runbook = _final_tagged_cut_runbook(source_summary)

    nonblocking_risk_ids = [item["risk"] for item in nonblocking_risks]
    # ``final_tagged_release_cut_pending`` is emitted only while the final cut
    # is actually pending -- ``_nonblocking_risks`` gates it on
    # ``final_release_blockers``. The identity expectation has to be gated the
    # same way, or completing the tagged cut turns this guard red for the one
    # reason it should never fire: the state improved. It did exactly that on
    # 2026-08-07, when tagging v1.22.0 emptied the pending list and the
    # unconditional expectation then reported a *missing* risk as an upload
    # blocker.
    #
    # The guard still does its job. Every other risk id must be present, in
    # order, and a pending cut must still announce itself.
    expected_risk_ids = [
        risk
        for risk in EXPECTED_DOCUMENTED_NONBLOCKING_RISKS
        if risk != "final_tagged_release_cut_pending" or final_release_blockers
    ]
    nonblocking_risk_identity_ok = nonblocking_risk_ids == expected_risk_ids
    risk_identity_check = _check(
        nonblocking_risk_identity_ok,
        "documented_nonblocking_risk_identity",
        (
            f"expected={expected_risk_ids}; "
            f"observed={nonblocking_risk_ids}"
        ),
        upload_blockers,
    )

    all_checks = audit_checks + archive_checks + source_checks + [risk_identity_check]
    ledger = {
        "generated_at_unix": _generated_at_unix(),
        "status": "PASS" if not upload_blockers else "FAIL",
        "scope": (
            "JSS source-snapshot upload readiness; final tagged-release "
            "readiness is tracked separately."
        ),
        "checks": all_checks,
        "jss_upload_blockers": upload_blockers,
        "jss_upload_blocker_count": len(upload_blockers),
        "final_tagged_release_blockers": final_release_blockers,
        "final_tagged_release_blocker_count": len(final_release_blockers),
        "expected_final_tagged_release_blocker_ids": list(
            EXPECTED_FINAL_TAGGED_RELEASE_BLOCKERS
        ),
        "final_tagged_release_blocker_ids": [
            item["check"] for item in final_release_blockers
        ],
        "final_tagged_release_blocker_identity_ok": source_summary.get(
            "final_tagged_release_blocker_identity_ok"
        ),
        "documented_nonblocking_risks": nonblocking_risks,
        "expected_documented_nonblocking_risk_ids": list(
            EXPECTED_DOCUMENTED_NONBLOCKING_RISKS
        ),
        "documented_nonblocking_risk_ids": nonblocking_risk_ids,
        "documented_nonblocking_risk_identity_ok": nonblocking_risk_identity_ok,
        "final_tagged_cut_runbook": final_tagged_cut_runbook,
        "archive": archive_summary,
        "source_snapshot": source_summary,
    }
    OUT_JSON.write_text(json.dumps(ledger, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# JSS Submission Risk Ledger",
        "",
        f"Status: {ledger['status']}",
        "",
        "Scope: JSS source-snapshot upload readiness. Final tagged-release "
        "readiness is tracked separately and is not treated as a JSS upload "
        "reproducibility failure when the source-snapshot boundary remains explicit.",
        "",
        f"JSS upload blockers: {len(upload_blockers)}",
        f"Final tagged-cut pending items: {len(final_release_blockers)}",
        "Final tagged-cut check identity: "
        + (
            "confirmed"
            if source_summary.get("final_tagged_release_blocker_identity_ok")
            else "drift detected"
        ),
        "Documented nonblocking risk identity: "
        + ("confirmed" if nonblocking_risk_identity_ok else "drift detected"),
        "",
        "## Upload Readiness Checks",
        "",
        "| Check | Status | Evidence |",
        "|---|---:|---|",
    ]
    for item in all_checks:
        lines.append(
            f"| `{item['check']}` | {'PASS' if item['ok'] else 'FAIL'} | "
            f"{item['detail']} |"
        )
    lines.extend(["", "## Final Tagged-Cut Pending Items", ""])
    if final_release_blockers:
        lines.extend(["| Check | Detail |", "|---|---|"])
        for item in final_release_blockers:
            lines.append(f"| `{item['check']}` | {item['detail']} |")
    else:
        lines.append("None.")
    lines.extend(["", "## Final Tagged-Cut Breakdown", ""])
    breakdown = source_summary.get("release_blocker_breakdown", {}) or {}
    if breakdown:
        lines.extend(["| Bucket | Count/detail |", "|---|---|"])
        for key, label in RELEASE_BREAKDOWN_ROWS:
            if key in breakdown:
                lines.append(f"| {label} | `{breakdown[key]}` |")
    else:
        lines.append("None.")
    lines.extend(
        [
            "",
            "## Final Tagged-Cut Runbook",
            "",
            "These steps are nonblocking post-upload release-cut work, not JSS "
            "source-snapshot upload blockers.",
            "",
        ]
    )
    if final_tagged_cut_runbook["steps"]:
        for item in final_tagged_cut_runbook["steps"]:
            lines.append(f"{item['step']}. {item['action']}")
    else:
        lines.append("No final tagged-cut steps are pending.")
    lines.extend(
        [
            "",
            "Strict release guard: "
            f"`{final_tagged_cut_runbook.get('strict_release_command')}`",
        ]
    )
    lines.extend(["", "## Documented Nonblocking Risks", ""])
    if nonblocking_risks:
        lines.extend(["| Risk | Evidence | Next action |", "|---|---|---|"])
        for item in nonblocking_risks:
            lines.append(
                f"| `{item['risk']}` | {item['evidence']} | {item['next_action']} |"
            )
    else:
        lines.append("None.")
    lines.extend(
        [
            "",
            "## Archive Summary",
            "",
            f"- Size: {archive_summary.get('size_mib')} MiB "
            f"({archive_summary.get('size_mb_decimal')} MB decimal)",
            f"- Files: {archive_summary.get('file_count')}",
            f"- Registry evidence files: {archive_summary.get('registry_evidence_file_count')}",
            f"- Active external-review artifacts present: "
            f"{archive_summary.get('active_external_review_artifacts_present', [])}",
            f"- Legacy manuscript sources present: "
            f"{archive_summary.get('legacy_manuscript_sources_present', [])}",
            "",
            "## Source Snapshot Summary",
            "",
            f"- Package/source/schema versions: "
            f"{source_summary.get('package_metadata_version')} / "
            f"{source_summary.get('source_init_version')} / "
            f"{source_summary.get('schema_bundle_version')}",
            f"- Package commit: {source_summary.get('package_commit')}",
            f"- Paper commit: {source_summary.get('paper_commit')}",
            f"- Ready for final publication release: "
            f"{source_summary.get('ready_for_final_publication')}",
            f"- Strict release command: `{source_summary.get('strict_release_command')}`",
            "",
            f"Machine-readable detail: `{OUT_JSON.relative_to(PAPER_DIR)}`",
        ]
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK -- wrote {OUT_JSON}")
    print(f"OK -- wrote {OUT_MD}")
    if upload_blockers:
        print("FAIL -- JSS upload blockers remain")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

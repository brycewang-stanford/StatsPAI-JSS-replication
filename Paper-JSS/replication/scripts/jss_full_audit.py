"""Reviewer-facing validation audit for the StatsPAI JSS submission.

This script is intentionally broader than ``make reproduce-jss``.  The
paper build regenerates the manuscript, worked examples, figures, and
appendix fragments.  This audit checks the evidence chain behind the
manuscript's validation claims: original-data parity, R/Stata parity
rollups, Track-B coverage artifacts, Track-C performance artifacts,
schema quality, stability/validation tiers, and the JSS validation API.

The expensive primary reruns (full R/Stata parity, B=1000 Monte Carlo,
and benchmark timing sweeps) remain separate commands because reviewers
may not have R, Stata, or 10+ minutes available.  This audit verifies
that their committed artifacts are present, internally consistent, and
regenerated into the tables consumed by the manuscript.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
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
RESULTS_DIR = PAPER_DIR / "replication" / "results"
BUILD_DIR = PAPER_DIR / "build"
SUBMISSION_ARCHIVE = BUILD_DIR / "statspai-jss-submission.zip"
SUBMISSION_ARCHIVE_MANIFEST = BUILD_DIR / "statspai-jss-submission-manifest.json"
SOURCE_DATE_EPOCH = os.environ.get("SOURCE_DATE_EPOCH")


def _generated_at_unix() -> int:
    if SOURCE_DATE_EPOCH is not None:
        return int(SOURCE_DATE_EPOCH)
    return int(time.time())


def _elapsed_seconds(start: float) -> float:
    if SOURCE_DATE_EPOCH is not None:
        return 0.0
    return round(time.perf_counter() - start, 3)


def _normalize_command_output(text: str) -> str:
    if SOURCE_DATE_EPOCH is None:
        return text
    stripped = text.strip()
    if stripped.startswith(("{", "[")):
        try:
            return json.dumps(json.loads(stripped), indent=2, sort_keys=True) + "\n"
        except json.JSONDecodeError:
            pass
    return re.sub(r"in \d+(?:\.\d+)?s", "in <elapsed>s", text)


def _run(cmd: list[str], *, cwd: Path = ROOT) -> dict[str, Any]:
    start = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    output = _normalize_command_output(proc.stdout)
    return {
        "cmd": " ".join(cmd),
        "cwd": str(cwd),
        "returncode": proc.returncode,
        "seconds": _elapsed_seconds(start),
        "output": output,
        "output_tail": "\n".join(output.splitlines()[-40:]),
    }


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _format_size_pair(size_mib: float | None, size_mb_decimal: float | None) -> str:
    if size_mib is None:
        return "unknown size"
    if size_mb_decimal is None:
        return f"{size_mib:.2f} MiB"
    return f"{size_mib:.2f} MiB ({size_mb_decimal:.2f} MB decimal)"


def _count_orig_rows() -> int:
    total = 0
    for path in (ROOT / "tests" / "orig_parity" / "results").glob("*_py.json"):
        payload = _json(path)
        total += len(payload.get("rows", []))
    return total


def _count_parity_verdicts() -> dict[str, int]:
    table = ROOT / "tests" / "r_parity" / "results" / "parity_table_3way.md"
    text = table.read_text(encoding="utf-8")
    return {
        "modules": text.count("\n## Module "),
        "gap_modules": text.count("**strictness_tier**: `methodological`"),
        "machine_modules": text.count("**strictness_tier**: `machine`"),
        "iterative_modules": text.count("**strictness_tier**: `iterative`"),
        "moderate_modules": text.count("**strictness_tier**: `moderate`"),
    }


def _coverage_summary() -> dict[str, Any]:
    base = ROOT / "tests" / "coverage_monte_carlo" / "results_b1000"
    nominal = _json(base / "coverage_b1000.json")
    robustness = _json(base / "coverage_robustness_b1000.json")
    return {
        "b1000_rows": len(nominal),
        "b1000_min_rate": min(row["rate"] for row in nominal),
        "b1000_max_rate": max(row["rate"] for row in nominal),
        "robustness_rows": len(robustness),
        "robustness": [
            {
                "name": row["name"],
                "B": row["B"],
                "rate": row["rate"],
                "documented_band": row.get("documented_band"),
            }
            for row in robustness
        ],
    }


def _performance_summary() -> dict[str, Any]:
    perf_dir = ROOT / "tests" / "perf" / "results"
    rows = []
    for path in sorted(perf_dir.glob("*_py.json")):
        side = path.stem.removesuffix("_py")
        py_rows = _json(path).get("rows", [])
        r_path = perf_dir / f"{side}_R.json"
        r_rows = _json(r_path).get("rows", []) if r_path.exists() else []
        if not py_rows or not r_rows:
            continue
        max_n = max(row["n"] for row in py_rows)
        py = next(row for row in py_rows if row["n"] == max_n)
        r_by_n = {row["n"]: row for row in r_rows}
        r = r_by_n.get(max_n)
        rows.append(
            {
                "module": side,
                "max_n": max_n,
                "sp_seconds": py["median_time_s"],
                "r_seconds": r["median_time_s"] if r else None,
                "r_over_sp": (
                    r["median_time_s"] / py["median_time_s"]
                    if r and py["median_time_s"] > 0
                    else None
                ),
            }
        )
    return {"rows": rows}


def _working_tree_size_summary_mib() -> dict[str, Any]:
    paths = [
        PAPER_DIR / ".git",
        PAPER_DIR / "htmlcov",
        PAPER_DIR / "references",
        PAPER_DIR / "manuscript",
        PAPER_DIR / "replication",
    ]
    sizes: dict[str, int] = {}
    for path in paths:
        if path.is_file():
            sizes[path.name] = path.stat().st_size
        elif path.is_dir():
            sizes[path.name] = sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
    return {k: round(v / (1024 * 1024), 2) for k, v in sorted(sizes.items())}


def _submission_package_summary() -> dict[str, Any]:
    manifest = SUBMISSION_ARCHIVE_MANIFEST
    if not manifest.exists():
        return {
            "present": False,
            "note": "Run `make submission-ready` to build the audited JSS archive.",
        }
    data = _json(manifest)
    size_mib = data.get("size_mib", data.get("size_mb"))
    return {
        "present": True,
        "size_bytes": data.get("size_bytes"),
        "size_mb": data.get("size_mb"),
        "size_mib": size_mib,
        "size_mb_decimal": data.get("size_mb_decimal"),
        "file_count": data.get("file_count"),
        "within_jss_attachment_limit": data.get("within_jss_attachment_limit"),
        "registry_evidence_file_count": data.get("registry_evidence_file_count"),
        "ascii_data_suffixes": data.get("ascii_data_suffixes"),
        "ascii_normalized_source_file_count": data.get(
            "ascii_normalized_source_file_count"
        ),
    }


def _source_snapshot_summary() -> dict[str, Any]:
    manifest = RESULTS_DIR / "source_snapshot_manifest.json"
    if not manifest.exists():
        return {
            "present": False,
            "note": "Run `make snapshot` or `make reproduce-jss` to generate the source-snapshot manifest.",
        }
    data = _json(manifest)
    git = data.get("git", {})
    snapshot = data.get("jss_source_snapshot", {})
    readiness = data.get("release_readiness", {})
    return {
        "present": True,
        "package_metadata_version": data.get("package_metadata_version"),
        "source_init_version": data.get("source_init_version"),
        "schema_bundle_version": data.get("schema_bundle_version"),
        "version_consistent_inside_source": data.get("version_consistent_inside_source"),
        "short_commit": git.get("short_commit"),
        "paper_short_commit": data.get("paper_git", {}).get("short_commit"),
        "branch": git.get("branch"),
        "is_clean": git.get("is_clean"),
        "tags_at_head": git.get("tags_at_head", []),
        "contains_unreleased_source_changes": snapshot.get("contains_unreleased_source_changes"),
        "hand_edited_dirty_path_count": len(snapshot.get("hand_edited_dirty_paths", [])),
        "ready_for_final_publication": readiness.get("ready_for_final_publication"),
        "release_blocker_count": readiness.get("release_blocker_count"),
        "source_release_blocker_count": readiness.get("source_release_blocker_count"),
        "paper_release_blocker_count": readiness.get("paper_release_blocker_count"),
        "unreleased_changelog_nonempty": readiness.get("unreleased_changelog_nonempty"),
        "interpretation": snapshot.get("interpretation"),
    }


def _data_provenance_summary() -> dict[str, Any]:
    manifest = RESULTS_DIR / "data_provenance_audit.json"
    if not manifest.exists():
        return {
            "present": False,
            "note": "Run `replication/scripts/data_provenance_audit.py`.",
        }
    data = _json(manifest)
    summary = data.get("summary", {})
    return {
        "present": True,
        "status": data.get("status"),
        "scoped_data_file_count": summary.get("scoped_data_file_count"),
        "csv_file_count": summary.get("csv_file_count"),
        "json_file_count": summary.get("json_file_count"),
        "packaged_public_dataset_csv_count": summary.get(
            "packaged_public_dataset_csv_count"
        ),
        "public_original_extract_csv_count": summary.get(
            "public_original_extract_csv_count"
        ),
        "same_byte_r_stata_fixture_csv_count": summary.get(
            "same_byte_r_stata_fixture_csv_count"
        ),
        "reference_fixture_csv_count": summary.get("reference_fixture_csv_count"),
        "forbidden_raw_member_count": summary.get("forbidden_raw_member_count"),
        "high_risk_path_hit_count": summary.get("high_risk_path_hit_count"),
        "csv_parse_failure_count": summary.get("csv_parse_failure_count"),
        "unknown_category_count": summary.get("unknown_category_count"),
        "failures": data.get("failures", []),
    }


def _claim_lint_summary() -> dict[str, Any]:
    manifest = RESULTS_DIR / "claim_lint.json"
    if not manifest.exists():
        return {
            "present": False,
            "note": "Run `replication/scripts/validate_claims.py` to lint validation claims.",
        }
    data = _json(manifest)
    return {
        "present": True,
        "status": data.get("status"),
        "checked_files": len(data.get("checked_files", [])),
        "historical_drift_files": len(data.get("historical_drift_files", [])),
        "failures": data.get("failures", []),
    }


def _validation_evidence_summary() -> dict[str, Any]:
    manifest = RESULTS_DIR / "validation_evidence_audit.json"
    if not manifest.exists():
        return {
            "present": False,
            "note": "Run `replication/scripts/validation_evidence_audit.py`.",
        }
    data = _json(manifest)
    summary = data.get("summary", {})
    return {
        "present": True,
        "status": data.get("status"),
        "certified_validated_symbols": summary.get("certified_validated_symbols"),
        "certified_symbols": summary.get("certified_symbols"),
        "validated_symbols": summary.get("validated_symbols"),
        "missing_validation_notes": summary.get("missing_validation_notes"),
        "certified_without_certified_grade_evidence": summary.get(
            "certified_without_certified_grade_evidence"
        ),
        "validated_without_validated_grade_evidence": summary.get(
            "validated_without_validated_grade_evidence"
        ),
        "supplemental_only_symbols": summary.get("supplemental_only_symbols"),
        "symbols_with_supplemental_notes": summary.get(
            "symbols_with_supplemental_notes"
        ),
        "symbols_with_limitations": summary.get("symbols_with_limitations"),
        "failures": data.get("failures", []),
    }


def _methodological_gap_summary() -> dict[str, Any]:
    manifest = RESULTS_DIR / "methodological_gap_ledger.json"
    if not manifest.exists():
        return {
            "present": False,
            "note": "Run `replication/scripts/methodological_gap_ledger.py`.",
        }
    data = _json(manifest)
    summary = data.get("summary", {})
    return {
        "present": True,
        "status": data.get("status"),
        "methodological_gap_count": summary.get("methodological_gap_count"),
        "classified_gap_count": summary.get("classified_gap_count"),
        "uncategorized_gap_count": summary.get("uncategorized_gap_count"),
        "metadata_guard_count": summary.get("metadata_guard_count"),
        "metadata_guard_failures": summary.get("metadata_guard_failures"),
        "non_circular_guard_count": summary.get("non_circular_guard_count"),
        "non_circular_guard_failures": summary.get(
            "non_circular_guard_failures"
        ),
        "reference_disagreement_guard_count": summary.get(
            "reference_disagreement_guard_count"
        ),
        "reference_disagreement_guard_failures": summary.get(
            "reference_disagreement_guard_failures"
        ),
        "category_counts": summary.get("category_counts", {}),
        "failures": data.get("failures", []),
    }


def _stata_bridge_summary() -> dict[str, Any]:
    manifest = RESULTS_DIR / "stata_bridge_audit.json"
    if not manifest.exists():
        return {
            "present": False,
            "note": "Run `replication/scripts/stata_bridge_audit.py`.",
        }
    data = _json(manifest)
    summary = data.get("summary", {})
    return {
        "present": True,
        "status": data.get("status"),
        "stata_modules": summary.get("stata_modules"),
        "r_joined_stata_modules": summary.get("r_joined_stata_modules"),
        "py_stata_only_modules": summary.get("py_stata_only_modules", []),
        "repro_report_modules": summary.get("repro_report_modules"),
        "license_boundary": summary.get("license_boundary"),
        "failures": data.get("failures", []),
    }


def _stata_rerun_protocol_summary() -> dict[str, Any]:
    manifest = RESULTS_DIR / "stata_rerun_protocol.json"
    if not manifest.exists():
        return {
            "present": False,
            "note": "Run `replication/scripts/stata_rerun_protocol.py`.",
        }
    data = _json(manifest)
    summary = data.get("summary", {})
    return {
        "present": True,
        "status": data.get("status"),
        "stata_modules": summary.get("stata_modules"),
        "r_joined_stata_modules": summary.get("r_joined_stata_modules"),
        "repro_report_modules": summary.get("repro_report_modules"),
        "reproduced_report_rows": summary.get("reproduced_report_rows"),
        "non_reproduced_report_rows": summary.get("non_reproduced_report_rows"),
        "checklist_item_count": summary.get("checklist_item_count"),
        "command_count": summary.get("command_count"),
        "requires_stata_license": summary.get("requires_stata_license"),
        "jss_upload_blocking": summary.get("jss_upload_blocking"),
        "absence_of_stata_is_optional_skip": summary.get(
            "absence_of_stata_is_optional_skip"
        ),
        "claimed_current_machine_live_rerun": summary.get(
            "claimed_current_machine_live_rerun"
        ),
        "no_section_4_7_headline_depends_on_live_stata": summary.get(
            "no_section_4_7_headline_depends_on_live_stata"
        ),
        "failures": data.get("failures", []),
    }


def _agent_interface_summary() -> dict[str, Any]:
    manifest = RESULTS_DIR / "agent_interface_audit.json"
    if not manifest.exists():
        return {
            "present": False,
            "note": "Run `replication/scripts/agent_interface_audit.py`.",
        }
    data = _json(manifest)
    schema = data.get("schema_quality", {})
    trace = data.get("agent_trace", {})
    return {
        "present": True,
        "status": data.get("status"),
        "public_surface": schema.get("public_surface"),
        "curated_agent_card": schema.get("curated_agent_card"),
        "parameter_total": schema.get("parameter_total"),
        "parameter_with_description": schema.get("parameter_with_description"),
        "parameter_with_default": schema.get("parameter_with_default"),
        "parameter_with_enum": schema.get("parameter_with_enum"),
        "trace_tools": trace.get("tool_count"),
        "trace_audit_checks": trace.get("audit_checks"),
        "trace_citation_keys": trace.get("citation_keys", []),
        "trace_bibtex_entry_count": trace.get("bibtex_entry_count"),
        "trace_bibtex_source": trace.get("bibtex_source"),
        "trace_stale_handle_is_error": trace.get("stale_handle_is_error"),
        "trace_stale_handle_hint_present": bool(trace.get("stale_handle_hint")),
        "failures": data.get("failures", []),
    }


def _agent_benchmark_protocol_summary() -> dict[str, Any]:
    manifest = RESULTS_DIR / "agent_benchmark_protocol.json"
    if not manifest.exists():
        return {
            "present": False,
            "note": "Run `replication/scripts/agent_benchmark_protocol.py`.",
        }
    data = _json(manifest)
    summary = data.get("summary", {})
    return {
        "present": True,
        "status": data.get("status"),
        "arm_count": summary.get("arm_count"),
        "task_family_count": summary.get("task_family_count"),
        "scoring_dimension_count": summary.get("scoring_dimension_count"),
        "validity_control_count": summary.get("validity_control_count"),
        "minimum_report_item_count": summary.get("minimum_report_item_count"),
        "jss_upload_blocking": summary.get("jss_upload_blocking"),
        "jss_claimed_behavioral_result": summary.get(
            "jss_claimed_behavioral_result"
        ),
        "failures": data.get("failures", []),
    }


def _experiment_triage_summary() -> dict[str, Any]:
    manifest = RESULTS_DIR / "experiment_triage.json"
    if not manifest.exists():
        return {
            "present": False,
            "note": "Run `replication/scripts/experiment_triage.py`.",
        }
    data = _json(manifest)
    summary = data.get("summary", {})
    return {
        "present": True,
        "status": data.get("status"),
        "item_count": summary.get("item_count"),
        "expected_item_ids": summary.get("expected_item_ids"),
        "item_ids": summary.get("item_ids"),
        "item_identity_ok": summary.get("item_identity_ok"),
        "pass_items": summary.get("pass_items"),
        "failed_items": summary.get("failed_items"),
        "classification_counts": summary.get("classification_counts", {}),
        "jss_upload_blocking_item_count": summary.get(
            "jss_upload_blocking_item_count"
        ),
        "jss_upload_blocking_items": summary.get(
            "jss_upload_blocking_items", []
        ),
        "failures": data.get("failures", []),
    }


def _release_boundary_summary() -> dict[str, Any]:
    manifest = RESULTS_DIR / "release_boundary_audit.json"
    if not manifest.exists():
        return {
            "present": False,
            "note": "Run `replication/scripts/release_boundary_audit.py`.",
        }
    data = _json(manifest)
    summary = data.get("summary", {})
    return {
        "present": True,
        "status": data.get("status"),
        "package_version": summary.get("package_version"),
        "source_version": summary.get("source_version"),
        "version_consistent": summary.get("version_consistent"),
        "ready_for_final_publication": summary.get("ready_for_final_publication"),
        "release_blocker_count": summary.get("release_blocker_count"),
        "unreleased_changelog_nonempty": summary.get(
            "unreleased_changelog_nonempty"
        ),
        "checked_files": len(data.get("checked_files", [])),
        "failures": data.get("failures", []),
    }


def _house_style_summary() -> dict[str, Any]:
    manifest = RESULTS_DIR / "jss_house_style_audit.json"
    if not manifest.exists():
        return {
            "present": False,
            "note": "Run `replication/scripts/jss_house_style_audit.py`.",
        }
    data = _json(manifest)
    summary = data.get("summary", {})
    return {
        "present": True,
        "status": data.get("status"),
        "check_count": len(data.get("checks", [])),
        "checked_files": len(summary.get("checked_files", [])),
        "active_section_count": summary.get("active_section_count"),
        "draft_marker_hits": summary.get("draft_marker_hits"),
        "marketing_claim_hits": summary.get("marketing_claim_hits"),
        "overconfidence_claim_hits": summary.get("overconfidence_claim_hits"),
        "defensive_tone_hits": summary.get("defensive_tone_hits"),
        "macro_counts": summary.get("macro_counts", {}),
        "anchor_failure_count": summary.get("anchor_failure_count"),
        "failures": data.get("failures", []),
    }


def _bibliography_metadata_summary() -> dict[str, Any]:
    manifest = RESULTS_DIR / "bibliography_metadata_audit.json"
    if not manifest.exists():
        return {
            "present": False,
            "note": "Run `replication/scripts/bibliography_metadata_audit.py`.",
        }
    data = _json(manifest)
    compiled = data.get("compiled_bibliography", {})
    return {
        "present": True,
        "status": data.get("status"),
        "active_tex_files": len(data.get("active_tex_files", [])),
        "active_cited_key_count": data.get("active_cited_key_count"),
        "submission_bib_entry_count": data.get("submission_bib_entry_count"),
        "archival_bib_entry_count": data.get("archival_bib_entry_count"),
        "doi_entry_count": data.get("doi_entry_count"),
        "url_entry_count": data.get("url_entry_count"),
        "locator_entry_count": data.get("locator_entry_count"),
        "reserved_entry_count": len(data.get("reserved_entry_keys", [])),
        "no_doi_entry_count": data.get("no_doi_entry_count"),
        "no_doi_manual_verification_count": data.get(
            "no_doi_manual_verification_count"
        ),
        "active_missing_from_submission_bib": len(
            data.get("active_missing_from_submission_bib", [])
        ),
        "duplicate_keys": len(data.get("duplicate_keys", [])),
        "field_failures": len(data.get("field_failures", [])),
        "compiled_bbl_present": compiled.get("present"),
        "compiled_bibitem_count": compiled.get("bibitem_count"),
        "failures": data.get("failures", []),
    }


def _submission_risk_ledger_summary() -> dict[str, Any]:
    manifest = RESULTS_DIR / "submission_risk_ledger.json"
    if not SUBMISSION_ARCHIVE.exists() or not SUBMISSION_ARCHIVE_MANIFEST.exists():
        return {
            "present": False,
            "note": (
                "No submission archive is available; run `make submission-ready` "
                "or `make verify-submission-package` to generate the upload ledger."
            ),
        }
    if not manifest.exists():
        return {
            "present": False,
            "note": "Run `replication/scripts/submission_risk_ledger.py`.",
        }
    data = _json(manifest)
    risks = data.get("documented_nonblocking_risks", [])
    return {
        "present": True,
        "status": data.get("status"),
        "jss_upload_blocker_count": data.get("jss_upload_blocker_count"),
        "final_tagged_release_blocker_count": data.get(
            "final_tagged_release_blocker_count"
        ),
        "expected_final_tagged_release_blocker_ids": data.get(
            "expected_final_tagged_release_blocker_ids"
        ),
        "final_tagged_release_blocker_ids": data.get(
            "final_tagged_release_blocker_ids"
        ),
        "final_tagged_release_blocker_identity_ok": data.get(
            "final_tagged_release_blocker_identity_ok"
        ),
        "nonblocking_risk_count": len(risks),
        "nonblocking_risks": [risk.get("risk") for risk in risks],
        "expected_documented_nonblocking_risk_ids": data.get(
            "expected_documented_nonblocking_risk_ids"
        ),
        "documented_nonblocking_risk_ids": data.get(
            "documented_nonblocking_risk_ids"
        ),
        "documented_nonblocking_risk_identity_ok": data.get(
            "documented_nonblocking_risk_identity_ok"
        ),
        "archive_file_count": data.get("archive", {}).get("file_count"),
        "archive_size_mib": data.get("archive", {}).get("size_mib"),
        "archive_size_mb_decimal": data.get("archive", {}).get("size_mb_decimal"),
        "active_external_review_artifacts_present": data.get("archive", {}).get(
            "active_external_review_artifacts_present", []
        ),
        "legacy_manuscript_sources_present": data.get("archive", {}).get(
            "legacy_manuscript_sources_present", []
        ),
    }


def _reviewer_evidence_map_summary() -> dict[str, Any]:
    manifest = RESULTS_DIR / "reviewer_evidence_map.json"
    if not SUBMISSION_ARCHIVE.exists() or not SUBMISSION_ARCHIVE_MANIFEST.exists():
        return {
            "present": False,
            "note": (
                "No submission archive is available; run `make submission-ready` "
                "or `make verify-submission-package` to generate the reviewer map."
            ),
        }
    if not manifest.exists():
        return {
            "present": False,
            "note": "Run `replication/scripts/reviewer_evidence_map.py`.",
        }
    data = _json(manifest)
    summary = data.get("summary", {})
    return {
        "present": True,
        "status": data.get("status"),
        "card_count": summary.get("card_count"),
        "expected_card_ids": summary.get("expected_card_ids"),
        "card_ids": summary.get("card_ids"),
        "card_identity_ok": summary.get("card_identity_ok"),
        "route_count": summary.get("route_count"),
        "expected_route_ids": summary.get("expected_route_ids"),
        "route_ids": summary.get("route_ids"),
        "route_identity_ok": summary.get("route_identity_ok"),
        "pass_cards": summary.get("pass_cards"),
        "failed_cards": summary.get("failed_cards"),
        "failed_routes": summary.get("failed_routes"),
        "jss_upload_blockers": summary.get("jss_upload_blockers"),
        "final_tagged_cut_pending_items": summary.get(
            "final_tagged_cut_pending_items"
        ),
        "documented_nonblocking_risk_count": summary.get(
            "documented_nonblocking_risk_count"
        ),
        "documented_nonblocking_risk_ids": summary.get(
            "documented_nonblocking_risk_ids"
        ),
        "documented_nonblocking_risk_identity_ok": summary.get(
            "documented_nonblocking_risk_identity_ok"
        ),
        "archive_file_count": summary.get("archive_file_count"),
        "pdf_text_chars": summary.get("pdf_text_chars"),
        "missing_pdf_boundary_snippets": summary.get(
            "missing_pdf_boundary_snippets"
        ),
        "archive_evidence_present": summary.get("archive_evidence_present"),
        "archive_evidence_paths_checked": summary.get(
            "archive_evidence_paths_checked"
        ),
        "archive_evidence_paths_resolved": summary.get(
            "archive_evidence_paths_resolved"
        ),
        "archive_evidence_paths_missing": summary.get(
            "archive_evidence_paths_missing"
        ),
        "pdf_pages": summary.get("pdf_pages"),
    }


def _editor_screening_summary() -> dict[str, Any]:
    manifest = RESULTS_DIR / "editor_screening_checklist.json"
    if not SUBMISSION_ARCHIVE.exists() or not SUBMISSION_ARCHIVE_MANIFEST.exists():
        return {
            "present": False,
            "note": (
                "No submission archive is available; run `make submission-ready` "
                "or `make verify-submission-package` to generate the editor checklist."
            ),
        }
    if not manifest.exists():
        return {
            "present": False,
            "note": "Run `replication/scripts/editor_screening_checklist.py`.",
        }
    data = _json(manifest)
    summary = data.get("summary", {})
    return {
        "present": True,
        "status": data.get("status"),
        "item_count": summary.get("item_count"),
        "expected_item_ids": summary.get("expected_item_ids"),
        "item_ids": summary.get("item_ids"),
        "item_identity_ok": summary.get("item_identity_ok"),
        "pass_items": summary.get("pass_items"),
        "failed_items": summary.get("failed_items"),
        "jss_upload_blockers": summary.get("jss_upload_blockers"),
        "archive_file_count": summary.get("archive_file_count"),
        "archive_size_mib": summary.get("archive_size_mib"),
        "archive_size_mb_decimal": summary.get("archive_size_mb_decimal"),
        "page_count": summary.get("page_count"),
        "reviewer_card_count": summary.get("reviewer_card_count"),
        "final_tagged_cut_runbook_steps": summary.get(
            "final_tagged_cut_runbook_steps"
        ),
        "archive_evidence_paths_checked": summary.get(
            "archive_evidence_paths_checked"
        ),
        "archive_evidence_paths_resolved": summary.get(
            "archive_evidence_paths_resolved"
        ),
        "archive_evidence_paths_missing": summary.get(
            "archive_evidence_paths_missing"
        ),
    }


def _reproduction_environment_summary() -> dict[str, Any]:
    manifest = RESULTS_DIR / "reproduction_environment_audit.json"
    if not manifest.exists():
        return {
            "present": False,
            "note": "Run `replication/scripts/reproduction_environment_audit.py`.",
        }
    data = _json(manifest)
    return {
        "present": True,
        "status": data.get("status"),
        "docker_base_image": data.get("dockerfile", {}).get("base_image"),
        "python_requirement_packages": data.get("requirements", {}).get(
            "package_count"
        ),
        "requirements_version_comment_ok": data.get("requirements", {}).get(
            "version_comment_ok"
        ),
        "makefile_targets": data.get("makefile", {}).get("target_count"),
        "paper_readme_commands": data.get("reviewer_readmes", {}).get(
            "paper_readme_command_count"
        ),
        "manuscript_readme_commands": data.get("reviewer_readmes", {}).get(
            "manuscript_readme_command_count"
        ),
        "paper_readme_missing_commands": data.get("reviewer_readmes", {}).get(
            "paper_readme_missing_commands", []
        ),
        "manuscript_readme_missing_commands": data.get(
            "reviewer_readmes", {}
        ).get("manuscript_readme_missing_commands", []),
        "tier1_transcript_no_r_stata": data.get("tier1_transcript_no_r_stata"),
        "tier1_live_external_call_count": data.get("reproduce", {}).get(
            "tier1_live_external_call_count"
        ),
        "renv_lock_present": data.get("renv_lock_present"),
        "stata_environment_present": data.get("stata_environment_present"),
        "seeded_stochastic_files": data.get("random_seeding", {}).get(
            "seeded_stochastic_file_count"
        ),
        "unseeded_stochastic_files": data.get("random_seeding", {}).get(
            "unseeded_stochastic_file_count"
        ),
        "failures": data.get("failures", []),
    }


def _pdf_render_summary() -> dict[str, Any]:
    manifest = RESULTS_DIR / "pdf_render_audit.json"
    if not manifest.exists():
        return {
            "present": False,
            "note": "Run `replication/scripts/pdf_render_audit.py`.",
        }
    data = _json(manifest)
    summary = data.get("summary", {})
    renderer = data.get("renderer", {})
    return {
        "present": True,
        "status": data.get("status"),
        "renderer": renderer.get("name"),
        "renderer_path": renderer.get("path"),
        "dpi": data.get("dpi"),
        "page_count": summary.get("page_count"),
        "sampled_pages": summary.get("sampled_pages", []),
        "rendered_page_count": summary.get("rendered_page_count"),
        "min_width": summary.get("min_width"),
        "min_height": summary.get("min_height"),
        "min_ink_ratio": summary.get("min_ink_ratio"),
        "max_dark_ratio": summary.get("max_dark_ratio"),
        "max_white_ratio": summary.get("max_white_ratio"),
        "full_document_rendered_page_count": summary.get(
            "full_document_rendered_page_count"
        ),
        "full_document_failure_count": summary.get("full_document_failure_count"),
        "full_document_min_width": summary.get("full_document_min_width"),
        "full_document_min_height": summary.get("full_document_min_height"),
        "full_document_min_ink_ratio": summary.get("full_document_min_ink_ratio"),
        "full_document_max_dark_ratio": summary.get("full_document_max_dark_ratio"),
        "full_document_max_white_ratio": summary.get("full_document_max_white_ratio"),
        "failure_count": summary.get("failure_count"),
        "failures": data.get("failures", []),
    }


def _pdf_visual_check_protocol_summary() -> dict[str, Any]:
    manifest = RESULTS_DIR / "pdf_visual_check_protocol.json"
    if not manifest.exists():
        return {
            "present": False,
            "note": "Run `replication/scripts/pdf_visual_check_protocol.py`.",
        }
    data = _json(manifest)
    summary = data.get("summary", {})
    return {
        "present": True,
        "status": data.get("status"),
        "page_count": summary.get("page_count"),
        "sampled_pages": summary.get("sampled_pages", []),
        "checklist_item_count": summary.get("checklist_item_count"),
        "pdf_render_status": summary.get("pdf_render_status"),
        "pdf_render_failure_count": summary.get("pdf_render_failure_count"),
        "page_inventory_count": summary.get("page_inventory_count"),
        "page_inventory_text_pages": summary.get("page_inventory_text_pages"),
        "page_inventory_section_markers": summary.get(
            "page_inventory_section_markers",
            [],
        ),
        "manual_visual_check_status": summary.get("manual_visual_check_status"),
        "claimed_manual_acceptance": summary.get("claimed_manual_acceptance"),
        "recorded_by_this_protocol": summary.get("recorded_by_this_protocol"),
        "manual_action_required_before_upload": summary.get(
            "manual_action_required_before_upload"
        ),
        "machine_render_not_human_review": summary.get(
            "machine_render_not_human_review"
        ),
        "jss_upload_blocking": summary.get("jss_upload_blocking"),
        "failures": data.get("failures", []),
    }


def _formal_compliance_summary() -> dict[str, Any]:
    manifest = RESULTS_DIR / "jss_formal_compliance_audit.json"
    if not manifest.exists():
        return {
            "present": False,
            "note": "Run `replication/scripts/jss_formal_compliance_audit.py`.",
        }
    data = _json(manifest)
    checks = data.get("checks", [])
    passed = sum(1 for item in checks if item.get("ok") is True)
    pending = sum(1 for item in checks if item.get("ok") is None)
    failed = sum(1 for item in checks if item.get("ok") is False)
    return {
        "present": True,
        "status": data.get("status"),
        "checks": len(checks),
        "passed": passed,
        "pending": pending,
        "failed": failed,
        "archive_present": data.get("archive_present"),
        "page_count": data.get("page_count"),
        "official_sources_checked": data.get("official_sources_checked"),
        "failures": data.get("failures", []),
    }


def _manuscript_artifact_summary() -> dict[str, Any]:
    manifest = RESULTS_DIR / "manuscript_artifact_audit.json"
    if not manifest.exists():
        return {
            "present": False,
            "note": "Run `replication/scripts/manuscript_artifact_audit.py`.",
        }
    data = _json(manifest)
    compact_coverage = data.get("compact_section_coverage", {})
    return {
        "present": True,
        "status": data.get("status"),
        "active_sections": len(data.get("active_sections", [])),
        "table_inputs": len(data.get("table_inputs", [])),
        "figures": len(data.get("figures", [])),
        "artifact_count": data.get("artifact_count"),
        "hash_mismatches": data.get("hash_mismatches"),
        "float_labels": len(data.get("active_float_labels", [])),
        "narrative_refs": len(data.get("narrative_float_refs", [])),
        "missing_narrative_refs": len(data.get("missing_narrative_refs", [])),
        "dangling_float_refs": len(data.get("dangling_float_refs", [])),
        "worked_example_scripts": len(
            data.get("worked_examples", {}).get("scripts_present", [])
        ),
        "worked_example_script_mentions": len(
            data.get("worked_examples", {}).get("script_mentions", [])
        ),
        "worked_example_labels": len(
            data.get("worked_examples", {}).get("labels_present", [])
        ),
        "worked_example_count_claim_present": data.get("worked_examples", {}).get(
            "count_claim_present"
        ),
        "compact_section_coverage_ok": compact_coverage.get("ok"),
        "compact_sections_checked": compact_coverage.get("sections_checked"),
        "compact_sections_passed": compact_coverage.get("sections_passed"),
        "compact_missing_anchors": compact_coverage.get("missing_anchor_count"),
        "failures": data.get("failures", []),
    }


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    commands = {
        "orig_parity_compare": _run([sys.executable, "tests/orig_parity/compare_orig.py"]),
        "r_stata_parity_compare": _run([sys.executable, "tests/r_parity/compare.py"]),
        # compare.py joins the *committed* Python and R JSONs, so it stays
        # green when the package under audit no longer produces the
        # committed Python numbers. That hid a 6.0e-4 ETWFE SE drift through
        # the whole 1.30.x cycle. Re-run every Python-side module against
        # the tree being audited (staging dirs, no files rewritten).
        "python_parity_reproduce": _run(
            [sys.executable, "tests/r_parity/verify_reproduce_py.py", "--no-report"]
        ),
        "methodological_gap_ledger": _run(
            [sys.executable, "Paper-JSS/replication/scripts/methodological_gap_ledger.py"]
        ),
        "stata_bridge_audit": _run(
            [sys.executable, "Paper-JSS/replication/scripts/stata_bridge_audit.py"]
        ),
        "reproduction_environment_audit": _run(
            [
                sys.executable,
                "Paper-JSS/replication/scripts/reproduction_environment_audit.py",
            ]
        ),
        "stata_rerun_protocol": _run(
            [
                sys.executable,
                "Paper-JSS/replication/scripts/stata_rerun_protocol.py",
            ]
        ),
        "jss_reproduction_environment_contract": _run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/test_jss_reproduction_environment.py",
                "-o",
                "addopts=",
            ]
        ),
        "jss_optional_io_engine_import": _run(
            [sys.executable, "-c", "import pyarrow"]
        ),
        "jss_rddensity_io_contract": _run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/test_rddensity_io.py",
                "-o",
                "addopts=",
            ]
        ),
        "performance_compare": _run([sys.executable, "tests/perf/compare_perf.py"]),
        "manuscript_artifact_audit": _run(
            [
                sys.executable,
                "Paper-JSS/replication/scripts/manuscript_artifact_audit.py",
            ]
        ),
        "data_provenance_audit": _run(
            [
                sys.executable,
                "Paper-JSS/replication/scripts/data_provenance_audit.py",
            ]
        ),
        "schema_bundle_check": _run(
            [sys.executable, "scripts/dump_schemas.py", "--check"]
        ),
        # The replacement table names ~150 sp.* entry points against their R
        # and Stata counterparts. Drift-checking it here is what keeps the
        # manuscript's coverage claim from advertising functions that a
        # registry rename has since removed.
        "replacement_table_check": _run(
            [
                sys.executable,
                "Paper-JSS/replication/scripts/build_replacement_table.py",
                "--check",
            ]
        ),
        "schema_quality": _run([sys.executable, "scripts/schema_quality.py"]),
        "agent_interface_audit": _run(
            [sys.executable, "Paper-JSS/replication/scripts/agent_interface_audit.py"]
        ),
        "agent_benchmark_protocol": _run(
            [
                sys.executable,
                "Paper-JSS/replication/scripts/agent_benchmark_protocol.py",
            ]
        ),
        "jss_style_guard": _run(
            [sys.executable, "Paper-JSS/replication/scripts/verify_jss_style.py"]
        ),
        "listings_execute_audit": _run(
            [sys.executable, "Paper-JSS/replication/scripts/listings_execute_audit.py"]
        ),
        "claim_linter": _run([sys.executable, "Paper-JSS/replication/scripts/validate_claims.py"]),
        "validation_evidence_audit": _run(
            [sys.executable, "Paper-JSS/replication/scripts/validation_evidence_audit.py"]
        ),
        "stability_audit_json": _run([sys.executable, "scripts/stability_audit.py", "--json"]),
        "stability_audit_check": _run([sys.executable, "scripts/stability_audit.py", "--check"]),
        "jss_validation_api": _run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/test_jss_validation_api.py",
                "-o",
                "addopts=",
            ]
        ),
        "jss_release_manifest_contract": _run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/test_jss_release_manifest.py",
                "-k",
                "not test_submission_package_verifier_pins_page_and_claim_guards",
                "-o",
                "addopts=",
            ]
        ),
        # Refresh after the mutating audit steps above so the full audit,
        # release-boundary audit, and packaged source snapshot share one
        # release-blocker denominator.
        "source_snapshot_manifest": _run(
            [
                sys.executable,
                "Paper-JSS/replication/scripts/source_snapshot_manifest.py",
            ]
        ),
        "release_boundary_audit": _run(
            [sys.executable, "Paper-JSS/replication/scripts/release_boundary_audit.py"]
        ),
        "experiment_triage": _run(
            [sys.executable, "Paper-JSS/replication/scripts/experiment_triage.py"]
        ),
        "pdf_render_audit": _run(
            [sys.executable, "Paper-JSS/replication/scripts/pdf_render_audit.py"]
        ),
        "pdf_visual_check_protocol": _run(
            [
                sys.executable,
                "Paper-JSS/replication/scripts/pdf_visual_check_protocol.py",
            ]
        ),
        "jss_formal_compliance_audit": _run(
            [
                sys.executable,
                "Paper-JSS/replication/scripts/jss_formal_compliance_audit.py",
            ]
        ),
        "jss_house_style_audit": _run(
            [
                sys.executable,
                "Paper-JSS/replication/scripts/jss_house_style_audit.py",
            ]
        ),
        "bibliography_metadata_audit": _run(
            [
                sys.executable,
                "Paper-JSS/replication/scripts/bibliography_metadata_audit.py",
            ]
        ),
    }
    if SUBMISSION_ARCHIVE.exists() and SUBMISSION_ARCHIVE_MANIFEST.exists():
        commands["submission_risk_ledger"] = _run(
            [sys.executable, "Paper-JSS/replication/scripts/submission_risk_ledger.py"]
        )
        commands["reviewer_evidence_map"] = _run(
            [sys.executable, "Paper-JSS/replication/scripts/reviewer_evidence_map.py"]
        )
        commands["editor_screening_checklist"] = _run(
            [
                sys.executable,
                "Paper-JSS/replication/scripts/editor_screening_checklist.py",
            ]
        )

    failures = {name: res for name, res in commands.items() if res["returncode"] != 0}
    try:
        stability = json.loads(commands["stability_audit_json"]["output"])
    except json.JSONDecodeError:
        stability = {"parse_error": commands["stability_audit_json"]["output_tail"]}

    audit = {
        "generated_at_unix": _generated_at_unix(),
        "python": sys.version.split()[0],
        "root": str(ROOT),
        "paper_dir": str(PAPER_DIR),
        "commands": commands,
        "summary": {
            "ok": not failures,
            "failed_steps": sorted(failures),
            "original_parity_rows": _count_orig_rows(),
            "track_a": _count_parity_verdicts(),
            "track_b": _coverage_summary(),
            "track_c": _performance_summary(),
            "stability": stability.get("parity_coverage", stability),
            "stability_auto_unbacked_breakdown": stability.get(
                "auto_unbacked_breakdown", {}
            ),
            "stability_evidence_paths": stability.get("evidence_paths", {}),
            "working_tree_size_mib": _working_tree_size_summary_mib(),
            "submission_package": _submission_package_summary(),
            "source_snapshot": _source_snapshot_summary(),
            "data_provenance": _data_provenance_summary(),
            "claim_lint": _claim_lint_summary(),
            "validation_evidence": _validation_evidence_summary(),
            "methodological_gap_ledger": _methodological_gap_summary(),
            "stata_bridge": _stata_bridge_summary(),
            "stata_rerun_protocol": _stata_rerun_protocol_summary(),
            "agent_interface": _agent_interface_summary(),
            "agent_benchmark_protocol": _agent_benchmark_protocol_summary(),
            "experiment_triage": _experiment_triage_summary(),
            "release_boundary": _release_boundary_summary(),
            "house_style": _house_style_summary(),
            "bibliography_metadata": _bibliography_metadata_summary(),
            "submission_risk_ledger": _submission_risk_ledger_summary(),
            "reviewer_evidence_map": _reviewer_evidence_map_summary(),
            "editor_screening": _editor_screening_summary(),
            "reproduction_environment": _reproduction_environment_summary(),
            "pdf_render": _pdf_render_summary(),
            "pdf_visual_check_protocol": _pdf_visual_check_protocol_summary(),
            "manuscript_artifacts": _manuscript_artifact_summary(),
            "formal_compliance": _formal_compliance_summary(),
        },
    }

    summary = audit["summary"]
    submission_package = summary.get("submission_package", {})
    source_snapshot = summary.get("source_snapshot", {})
    audit.update(
        {
            "status": "PASS" if summary["ok"] else "FAIL",
            "package_size_mib": submission_package.get("size_mib"),
            "package_size_mb_decimal": submission_package.get("size_mb_decimal"),
            "package_file_count": submission_package.get("file_count"),
            "final_publication_gate_ready": source_snapshot.get(
                "ready_for_final_publication"
            ),
            "gate_blocker_paths": source_snapshot.get("release_blocker_count"),
        }
    )

    out_json = RESULTS_DIR / "jss_full_audit.json"
    out_md = RESULTS_DIR / "jss_full_audit.md"
    out_json.write_text(json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8")

    submission_package_size = _format_size_pair(
        summary["submission_package"].get("size_mib"),
        summary["submission_package"].get("size_mb_decimal"),
    )
    lines = [
        "# JSS Full Validation Audit",
        "",
        f"Status: {'PASS' if summary['ok'] else 'FAIL'}",
        f"Original-data parity rows: {summary['original_parity_rows']}",
        (
            "Track A modules: "
            f"{summary['track_a']['modules']} "
            f"(machine={summary['track_a']['machine_modules']}, "
            f"iterative={summary['track_a']['iterative_modules']}, "
            f"moderate={summary['track_a']['moderate_modules']}, "
            f"methodological/T4={summary['track_a']['gap_modules']})"
        ),
        (
            "Track B materialized nominal rows: "
            f"{summary['track_b']['b1000_rows']} "
            f"(coverage range {summary['track_b']['b1000_min_rate']:.3f}-"
            f"{summary['track_b']['b1000_max_rate']:.3f})"
        ),
        f"Track C modules: {len(summary['track_c']['rows'])}",
        (
            "Stability audit: "
            f"{summary['stability'].get('registry_validated_symbols', 'n/a')} "
            "registry certified/validated symbols; "
            f"{summary['stability'].get('unbacked_handwritten', 'n/a')} "
            "hand-written stable symbols still unbacked; "
            f"{summary['stability'].get('unbacked_auto', 'n/a')} "
            "stable auto-registered symbols still unbacked"
        ),
        (
            "API-stable denominator: "
            + (
                f"{summary['stability_auto_unbacked_breakdown'].get('classlike_symbol_count', 0)} "
                "class-like / "
                f"{summary['stability_auto_unbacked_breakdown'].get('functionlike_symbol_count', 0)} "
                "function-like auto-unbacked symbols; top categories="
                + ", ".join(
                    f"{name}:{count}"
                    for name, count in list(
                        summary['stability_auto_unbacked_breakdown']
                        .get('category_counts', {})
                        .items()
                    )[:6]
                )
                if summary.get("stability_auto_unbacked_breakdown")
                else "not available"
            )
        ),
        (
            "Evidence paths: "
            f"{summary['stability_evidence_paths'].get('unique', 'n/a')} "
            "unique registry evidence paths; missing="
            f"{len(summary['stability_evidence_paths'].get('missing', []))}"
        ),
        (
            "Submission package: "
            + (
                f"{submission_package_size}, "
                f"{summary['submission_package']['file_count']} files, "
                f"within 50 MB={summary['submission_package']['within_jss_attachment_limit']}; "
                "registry evidence files="
                f"{summary['submission_package'].get('registry_evidence_file_count')}; "
                "ASCII-normalized source files="
                f"{summary['submission_package'].get('ascii_normalized_source_file_count')}; "
                "ASCII data suffixes="
                f"{','.join(summary['submission_package'].get('ascii_data_suffixes') or [])}"
                if summary["submission_package"].get("present")
                else "not built"
            )
        ),
        (
            "Data provenance audit: "
            + (
                f"{summary['data_provenance']['status']} "
                f"(scoped_files={summary['data_provenance']['scoped_data_file_count']}; "
                f"csv={summary['data_provenance']['csv_file_count']}; "
                "public_datasets="
                f"{summary['data_provenance']['packaged_public_dataset_csv_count']}; "
                "original_extracts="
                f"{summary['data_provenance']['public_original_extract_csv_count']}; "
                "r_stata_csv="
                f"{summary['data_provenance']['same_byte_r_stata_fixture_csv_count']}; "
                "forbidden_raw="
                f"{summary['data_provenance']['forbidden_raw_member_count']}; "
                "private_path_hits="
                f"{summary['data_provenance']['high_risk_path_hit_count']}; "
                "unknown="
                f"{summary['data_provenance']['unknown_category_count']})"
                if summary["data_provenance"].get("present")
                else "not run"
            )
        ),
        (
            "Source snapshot: "
            + (
                f"version={summary['source_snapshot']['package_metadata_version']}, "
                f"package_commit={summary['source_snapshot']['short_commit']}, "
                f"paper_commit={summary['source_snapshot']['paper_short_commit']}, "
                f"clean={summary['source_snapshot']['is_clean']}, "
                f"unreleased_changes={summary['source_snapshot']['contains_unreleased_source_changes']}, "
                f"version_consistent={summary['source_snapshot']['version_consistent_inside_source']}, "
                "final_publication_gate_ready="
                f"{summary['source_snapshot']['ready_for_final_publication']}, "
                "gate_blocker_paths="
                f"{summary['source_snapshot']['release_blocker_count']}"
                if summary["source_snapshot"].get("present")
                else "not generated"
            )
        ),
        (
            "Claim linter: "
            + (
                f"{summary['claim_lint']['status']} "
                f"({summary['claim_lint']['checked_files']} files checked; "
                "historical_drift_files="
                f"{summary['claim_lint']['historical_drift_files']})"
                if summary["claim_lint"].get("present")
                else "not run"
            )
        ),
        (
            "Schema bundle check: "
            + ("PASS" if commands["schema_bundle_check"]["returncode"] == 0 else "FAIL")
        ),
        (
            "Validation evidence audit: "
            + (
                f"{summary['validation_evidence']['status']} "
                f"({summary['validation_evidence']['certified_validated_symbols']} "
                "certified/validated, "
                f"missing_notes={summary['validation_evidence']['missing_validation_notes']}, "
                "certified_without_grade="
                f"{summary['validation_evidence']['certified_without_certified_grade_evidence']}, "
                "validated_without_grade="
                f"{summary['validation_evidence']['validated_without_validated_grade_evidence']}, "
                "supplemental_only="
                f"{summary['validation_evidence']['supplemental_only_symbols']})"
                if summary["validation_evidence"].get("present")
                else "not run"
            )
        ),
        (
            "Methodological/T4 ledger: "
            + (
                f"{summary['methodological_gap_ledger']['status']} "
                f"({summary['methodological_gap_ledger']['classified_gap_count']}/"
                f"{summary['methodological_gap_ledger']['methodological_gap_count']} "
                "classified, uncategorized="
                f"{summary['methodological_gap_ledger']['uncategorized_gap_count']}, "
                "metadata_guard_failures="
                f"{summary['methodological_gap_ledger']['metadata_guard_failures']}, "
                "non_circular_native_guards="
                f"{summary['methodological_gap_ledger']['non_circular_guard_count']}, "
                "non_circular_guard_failures="
                f"{summary['methodological_gap_ledger']['non_circular_guard_failures']}, "
                "reference_disagreement_guards="
                f"{summary['methodological_gap_ledger']['reference_disagreement_guard_count']}, "
                "reference_disagreement_guard_failures="
                f"{summary['methodological_gap_ledger']['reference_disagreement_guard_failures']})"
                if summary["methodological_gap_ledger"].get("present")
                else "not run"
            )
        ),
        (
            "Stata bridge audit: "
            + (
                f"{summary['stata_bridge']['status']} "
                f"({summary['stata_bridge']['stata_modules']} frozen modules; "
                f"{summary['stata_bridge']['r_joined_stata_modules']} R-joined; "
                "Py-Stata-only="
                f"{','.join(summary['stata_bridge']['py_stata_only_modules']) or 'none'}; "
                f"repro_report={summary['stata_bridge']['repro_report_modules']})"
                if summary["stata_bridge"].get("present")
                else "not run"
            )
        ),
        (
            "Stata rerun protocol: "
            + (
                f"{summary['stata_rerun_protocol']['status']} "
                f"(modules={summary['stata_rerun_protocol']['stata_modules']}; "
                "r_joined="
                f"{summary['stata_rerun_protocol']['r_joined_stata_modules']}; "
                "repro_report="
                f"{summary['stata_rerun_protocol']['repro_report_modules']}; "
                "non_reproduced="
                f"{summary['stata_rerun_protocol']['non_reproduced_report_rows']}; "
                "checklist_items="
                f"{summary['stata_rerun_protocol']['checklist_item_count']}; "
                "requires_license="
                f"{summary['stata_rerun_protocol']['requires_stata_license']}; "
                "claimed_live_rerun="
                f"{summary['stata_rerun_protocol']['claimed_current_machine_live_rerun']}; "
                "upload_blocking="
                f"{summary['stata_rerun_protocol']['jss_upload_blocking']})"
                if summary["stata_rerun_protocol"].get("present")
                else "not run"
            )
        ),
        (
            "Agent interface audit: "
            + (
                f"{summary['agent_interface']['status']} "
                f"({summary['agent_interface']['public_surface']} schemas; "
                f"{summary['agent_interface']['parameter_total']} params; "
                f"trace_tools={summary['agent_interface']['trace_tools']}; "
                f"trace_citations="
                f"{','.join(summary['agent_interface']['trace_citation_keys'])}; "
                "trace_bibtex="
                f"{summary['agent_interface']['trace_bibtex_entry_count']} "
                f"from {summary['agent_interface']['trace_bibtex_source']}; "
                "trace_stale_handle_error="
                f"{summary['agent_interface']['trace_stale_handle_is_error']}; "
                "trace_stale_handle_hint="
                f"{summary['agent_interface']['trace_stale_handle_hint_present']})"
                if summary["agent_interface"].get("present")
                else "not run"
            )
        ),
        (
            "Agent benchmark protocol: "
            + (
                f"{summary['agent_benchmark_protocol']['status']} "
                f"(arms={summary['agent_benchmark_protocol']['arm_count']}; "
                "task_families="
                f"{summary['agent_benchmark_protocol']['task_family_count']}; "
                "scoring_dimensions="
                f"{summary['agent_benchmark_protocol']['scoring_dimension_count']}; "
                "validity_controls="
                f"{summary['agent_benchmark_protocol']['validity_control_count']}; "
                "jss_upload_blocking="
                f"{summary['agent_benchmark_protocol']['jss_upload_blocking']}; "
                "claimed_behavioural_result="
                f"{summary['agent_benchmark_protocol']['jss_claimed_behavioral_result']})"
                if summary["agent_benchmark_protocol"].get("present")
                else "not run"
            )
        ),
        (
            "Experiment triage: "
            + (
                f"{summary['experiment_triage']['status']} "
                f"(items={summary['experiment_triage']['item_count']}; "
                f"pass={summary['experiment_triage']['pass_items']}; "
                f"failed={summary['experiment_triage']['failed_items']}; "
                "upload_blocking="
                f"{summary['experiment_triage']['jss_upload_blocking_item_count']}; "
                f"classes={summary['experiment_triage']['classification_counts']})"
                if summary["experiment_triage"].get("present")
                else "not run"
            )
        ),
        (
            "Release boundary audit: "
            + (
                f"{summary['release_boundary']['status']} "
                f"(version={summary['release_boundary']['package_version']}, "
                f"final_publication_gate_ready="
                f"{summary['release_boundary']['ready_for_final_publication']}, "
                f"gate_blocker_paths="
                f"{summary['release_boundary']['release_blocker_count']}, "
                f"checked_files={summary['release_boundary']['checked_files']})"
                if summary["release_boundary"].get("present")
                else "not run"
            )
        ),
        (
            "JSS house-style audit: "
            + (
                f"{summary['house_style']['status']} "
                "(checks="
                f"{summary['house_style']['check_count']}; "
                "active_sections="
                f"{summary['house_style']['active_section_count']}; "
                "draft_markers="
                f"{summary['house_style']['draft_marker_hits']}; "
                "marketing_hits="
                f"{summary['house_style']['marketing_claim_hits']}; "
                "overconfidence_hits="
                f"{summary['house_style']['overconfidence_claim_hits']}; "
                "defensive_tone_hits="
                f"{summary['house_style']['defensive_tone_hits']}; "
                "anchor_failures="
                f"{summary['house_style']['anchor_failure_count']})"
                if summary["house_style"].get("present")
                else "not run"
            )
        ),
        (
            "Bibliography metadata audit: "
            + (
                f"{summary['bibliography_metadata']['status']} "
                "(active_cites="
                f"{summary['bibliography_metadata']['active_cited_key_count']}; "
                "bib_entries="
                f"{summary['bibliography_metadata']['submission_bib_entry_count']}; "
                "reserved="
                f"{summary['bibliography_metadata']['reserved_entry_count']}; "
                "doi_entries="
                f"{summary['bibliography_metadata']['doi_entry_count']}; "
                "no_doi_manual="
                f"{summary['bibliography_metadata']['no_doi_manual_verification_count']}/"
                f"{summary['bibliography_metadata']['no_doi_entry_count']}; "
                "missing="
                f"{summary['bibliography_metadata']['active_missing_from_submission_bib']}; "
                "duplicates="
                f"{summary['bibliography_metadata']['duplicate_keys']}; "
                "field_failures="
                f"{summary['bibliography_metadata']['field_failures']})"
                if summary["bibliography_metadata"].get("present")
                else "not run"
            )
        ),
        (
            "Submission risk ledger: "
            + (
                f"{summary['submission_risk_ledger']['status']} "
                "(upload_blockers="
                f"{summary['submission_risk_ledger']['jss_upload_blocker_count']}; "
                "final_tagged_cut_pending_items="
                f"{summary['submission_risk_ledger']['final_tagged_release_blocker_count']}; "
                "final_tagged_cut_identity="
                f"{'confirmed' if summary['submission_risk_ledger'].get('final_tagged_release_blocker_identity_ok') else 'drift'}; "
                "nonblocking_risks="
                f"{summary['submission_risk_ledger']['nonblocking_risk_count']}; "
                "nonblocking_risk_identity="
                f"{'confirmed' if summary['submission_risk_ledger'].get('documented_nonblocking_risk_identity_ok') else 'drift'}; "
                "active_external_present="
                f"{len(summary['submission_risk_ledger']['active_external_review_artifacts_present'])}; "
                "legacy_sections_present="
                f"{len(summary['submission_risk_ledger']['legacy_manuscript_sources_present'])})"
                if summary["submission_risk_ledger"].get("present")
                else "not run"
            )
        ),
        (
            "Reviewer evidence map: "
            + (
                f"{summary['reviewer_evidence_map']['status']} "
                "(cards="
                f"{summary['reviewer_evidence_map']['card_count']}; "
                "routes="
                f"{summary['reviewer_evidence_map']['route_count']}; "
                "pass_cards="
                f"{summary['reviewer_evidence_map']['pass_cards']}; "
                "failed_cards="
                f"{summary['reviewer_evidence_map']['failed_cards']}; "
                "failed_routes="
                f"{summary['reviewer_evidence_map']['failed_routes']}; "
                "upload_blockers="
                f"{summary['reviewer_evidence_map']['jss_upload_blockers']}; "
                "archive_files="
                f"{summary['reviewer_evidence_map']['archive_file_count']})"
                if summary["reviewer_evidence_map"].get("present")
                else "not run"
            )
        ),
        (
            "Editor screening checklist: "
            + (
                f"{summary['editor_screening']['status']} "
                "(items="
                f"{summary['editor_screening']['item_count']}; "
                "pass_items="
                f"{summary['editor_screening']['pass_items']}; "
                "failed_items="
                f"{summary['editor_screening']['failed_items']}; "
                "upload_blockers="
                f"{summary['editor_screening']['jss_upload_blockers']}; "
                "archive_files="
                f"{summary['editor_screening']['archive_file_count']})"
                if summary["editor_screening"].get("present")
                else "not run"
            )
        ),
        (
            "Reproduction environment audit: "
            + (
                f"{summary['reproduction_environment']['status']} "
                f"(docker="
                f"{summary['reproduction_environment']['docker_base_image']}; "
                "requirements="
                f"{summary['reproduction_environment']['python_requirement_packages']}; "
                "requirements_version="
                f"{summary['reproduction_environment']['requirements_version_comment_ok']}; "
                "make_targets="
                f"{summary['reproduction_environment']['makefile_targets']}; "
                "paper_readme_commands="
                f"{summary['reproduction_environment']['paper_readme_commands']}; "
                "manuscript_readme_commands="
                f"{summary['reproduction_environment']['manuscript_readme_commands']}; "
                "tier1_no_r_stata="
                f"{summary['reproduction_environment']['tier1_transcript_no_r_stata']}; "
                "tier1_live_external="
                f"{summary['reproduction_environment']['tier1_live_external_call_count']}; "
                "renv="
                f"{summary['reproduction_environment']['renv_lock_present']}; "
                "stata_env="
                f"{summary['reproduction_environment']['stata_environment_present']}; "
                "seeded_rng="
                f"{summary['reproduction_environment']['seeded_stochastic_files']}; "
                "unseeded_rng="
                f"{summary['reproduction_environment']['unseeded_stochastic_files']})"
                if summary["reproduction_environment"].get("present")
                else "not run"
            )
        ),
        (
            "PDF render audit: "
            + (
                f"{summary['pdf_render']['status']} "
                f"(renderer={summary['pdf_render']['renderer']}; "
                f"pages={summary['pdf_render']['rendered_page_count']}/"
                f"{summary['pdf_render']['page_count']}; "
                "full_scan="
                f"{summary['pdf_render']['full_document_rendered_page_count']}/"
                f"{summary['pdf_render']['page_count']}; "
                "full_failures="
                f"{summary['pdf_render']['full_document_failure_count']}; "
                "sampled="
                f"{','.join(str(page) for page in summary['pdf_render']['sampled_pages'])}; "
                f"min_width={summary['pdf_render']['min_width']}; "
                f"min_height={summary['pdf_render']['min_height']}; "
                "min_ink_ratio="
                f"{summary['pdf_render']['min_ink_ratio']}; "
                "max_dark_ratio="
                f"{summary['pdf_render']['max_dark_ratio']}; "
                "failures="
                f"{summary['pdf_render']['failure_count']})"
                if summary["pdf_render"].get("present")
                else "not run"
            )
        ),
        (
            "PDF visual check protocol: "
            + (
                f"{summary['pdf_visual_check_protocol']['status']} "
                f"(pages={summary['pdf_visual_check_protocol']['page_count']}; "
                "checklist_items="
                f"{summary['pdf_visual_check_protocol']['checklist_item_count']}; "
                "page_inventory="
                f"{summary['pdf_visual_check_protocol']['page_inventory_count']}/"
                f"{summary['pdf_visual_check_protocol']['page_inventory_text_pages']}; "
                "manual_visual_check_status="
                f"{summary['pdf_visual_check_protocol']['manual_visual_check_status']}; "
                "claimed_manual_acceptance="
                f"{summary['pdf_visual_check_protocol']['claimed_manual_acceptance']}; "
                "jss_upload_blocking="
                f"{summary['pdf_visual_check_protocol']['jss_upload_blocking']})"
                if summary["pdf_visual_check_protocol"].get("present")
                else "not run"
            )
        ),
        (
            "Manuscript artifact audit: "
            + (
                f"{summary['manuscript_artifacts']['status']} "
                f"(sections={summary['manuscript_artifacts']['active_sections']}; "
                f"table_inputs={summary['manuscript_artifacts']['table_inputs']}; "
                f"figures={summary['manuscript_artifacts']['figures']}; "
                f"artifacts={summary['manuscript_artifacts']['artifact_count']}; "
                "hash_mismatches="
                f"{summary['manuscript_artifacts']['hash_mismatches']}; "
                f"float_labels={summary['manuscript_artifacts']['float_labels']}; "
                f"narrative_refs={summary['manuscript_artifacts']['narrative_refs']}; "
                "missing_refs="
                f"{summary['manuscript_artifacts']['missing_narrative_refs']}; "
                "dangling_refs="
                f"{summary['manuscript_artifacts']['dangling_float_refs']}; "
                "worked_example_scripts="
                f"{summary['manuscript_artifacts']['worked_example_scripts']}; "
                "worked_example_mentions="
                f"{summary['manuscript_artifacts']['worked_example_script_mentions']}; "
                "worked_example_labels="
                f"{summary['manuscript_artifacts']['worked_example_labels']}; "
                "compact_sections="
                f"{summary['manuscript_artifacts']['compact_sections_checked']}; "
                "compact_coverage="
                f"{summary['manuscript_artifacts']['compact_sections_passed']}; "
                "compact_missing_anchors="
                f"{summary['manuscript_artifacts']['compact_missing_anchors']})"
                if summary["manuscript_artifacts"].get("present")
                else "not run"
            )
        ),
        (
            "JSS formal compliance audit: "
            + (
                f"{summary['formal_compliance']['status']} "
                f"(checks={summary['formal_compliance']['checks']}; "
                f"passed={summary['formal_compliance']['passed']}; "
                f"pending={summary['formal_compliance']['pending']}; "
                f"archive={summary['formal_compliance']['archive_present']}; "
                f"pages={summary['formal_compliance']['page_count']}; "
                "official_sources_checked="
                f"{summary['formal_compliance']['official_sources_checked']})"
                if summary["formal_compliance"].get("present")
                else "not run"
            )
        ),
        "",
        "## Step Results",
        "",
    ]
    for name, res in commands.items():
        lines.append(
            f"- {name}: rc={res['returncode']} in {res['seconds']}s "
            f"(`{res['cmd']}`)"
        )
    lines.extend(
        [
            "",
            "## Working-Tree Size Hotspots Checked by Packager",
            "",
        ]
    )
    for key, value in summary["working_tree_size_mib"].items():
        lines.append(f"- {key}: {value} MiB")
    lines.append("")
    lines.append(f"Machine-readable detail: `{out_json.relative_to(PAPER_DIR)}`")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"OK -- wrote {out_json}")
    print(f"OK -- wrote {out_md}")
    if failures:
        print("FAIL -- failed steps: " + ", ".join(sorted(failures)), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Verify the built JSS submission archive is internally coherent."""
from __future__ import annotations

import json
from io import BytesIO
import os
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:  # _paths.py sits beside this script
    sys.path.insert(0, _SCRIPTS_DIR)

from _paths import release_version as _release_version
from _paths import expected_stata_module_count as _expected_stata
from _paths import expected_r_module_count as _expected_r

#: Release the manuscript describes; never hard-code it (see _paths).
RELEASE = _release_version()

HERE = Path(__file__).resolve().parent
PAPER_DIR = HERE.parents[1]
BUILD_DIR = PAPER_DIR / "build"
ARCHIVE = BUILD_DIR / "statspai-jss-submission.zip"
MANIFEST_JSON = BUILD_DIR / "statspai-jss-submission-manifest.json"
SOURCE_DATE_EPOCH = int(os.environ.get("SOURCE_DATE_EPOCH", "1780185600"))
FIXED_ZIP_DATETIME = time.gmtime(SOURCE_DATE_EPOCH)[:6]
EXPECTED_R_REPRO_MODULES = _expected_r()
EXPECTED_STATA_REPRO_MODULES = _expected_stata()
# Same-byte R/Stata fixture CSVs is a data-provenance count, not a module
# count: modules 76 (matrix inputs, no CSV) and 78 (two CSVs) break the
# one-CSV-per-module assumption, so this is tracked separately.
EXPECTED_R_STATA_FIXTURE_CSV_COUNT = 91
MANUAL_VISUAL_SPOT_CHECK_STATUS = "PENDING_MANUAL_REVIEW"
EXPECTED_FINAL_TAGGED_RELEASE_BLOCKER_IDS = [
    "clean_combined_worktree",
    "package_tag_at_head",
    "unreleased_changelog_finalized",
    "source_paths_finalized",
    "paper_paths_finalized",
]
EXPECTED_DOCUMENTED_NONBLOCKING_RISK_IDS = [
    "final_tagged_release_cut_pending",
    "registry_breadth_denominator_disclosed",
    "stata_tier3_requires_license",
    "methodological_t4_row_disclosed",
    "compact_text_may_feel_terse",
    "agent_interface_value_boundary",
]
EXPECTED_HARDENING_RISK_TITLES = [
    "Length risk is now largely controlled.",
    "Release boundary is now a consistency check.",
    "The harsh denominator remains ugly, but now auditable.",
    "One Track A row is methodological/T4 rather than deterministic.",
    "Stata reproducibility is re-derived, and licensed only for the rerun.",
    "Agent behavior is deferred.",
    "Final JSS class mode is now guarded.",
]
EXPECTED_RELEASE_BREAKDOWN_KEYS = [
    "hand_edited_status_counts",
    "generated_status_counts",
    "package_code_paths",
    "package_docs_paths",
    "validation_test_paths",
    "paper_manuscript_paths",
    "paper_replication_paths",
    "paper_other_paths",
]
EXPECTED_REVIEWER_CARD_IDS = [
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
]
EXPECTED_REVIEWER_ROUTE_IDS = [
    "editor_triage",
    "statistical_validation",
    "quick_reproduction",
    "agent_interface",
    "limitations_and_release_boundary",
]
EXPECTED_REVIEWER_ROUTE_README_LABELS = [
    "editor triage",
    "statistical validation",
    "quick reproduction",
    "agent-interface review",
    "limitations/release-boundary review",
]
EXPECTED_REVIEWER_CARD_README_LABELS = [
    "validation scope",
    "fast headline reproduction",
    "R/Stata comparison limits",
    "active table/figure provenance",
    "worked-example scope",
    "experiment triage",
    "archive boundary",
    "related-review and COI boundary",
    "source installability",
    "mechanical and contractual agent-interface claims",
    "limitations crosswalk",
    "maintenance and sustainability",
    "final tagged-cut cleanup",
]
EXPECTED_EDITOR_CHECKLIST_ITEM_IDS = [
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
]
EXPECTED_RESERVED_BIB_KEYS = ["brown2020language"]
EXPECTED_NO_DOI_BIB_KEYS = [
    "anthropic2024mcp",
    "bach2022doubleml",
    "berge2018efficient",
    "brown2020language",
    "card1995using",
    "chen2025efficient",
    "econml",
    "ghanem2026selection",
    "lalonde1986evaluating",
    "liang2023helm",
    "patil2023gorilla",
    "pedregosa2011scikit",
    "rios2022csdid",
]


def _is_ordered_expected_subset(observed: list[str], expected: list[str]) -> bool:
    return (
        all(item in expected for item in observed)
        and observed == [item for item in expected if item in observed]
    )


PDF_BOUNDARY_SNIPPETS = (
    "evidence tier that a user",
    "or an agent can query at call time",
    "certified/validated",
    "API-stable",
    "not parity-backed",
    f"This article describes StatsPAI {RELEASE}",
    f"tag v{RELEASE}",
    "not a behavioural claim",
    "matched arms, task families",
    # Trimmed to the clause that cannot straddle a float: the full
    # sentence ends one page and resumes after Table 15, so the
    # halves are separated in the PDF's reading order by the whole
    # table. The clause still pins the boundary statement.
    "before any behavioural claim",
    "software-interface contribution",
    "named rows and modules",
    "nine scoped limitation rows",
    "calibrated Basque replica",
    "no printed vignette anchor",
    "The unification itself has costs",
    "licence-free replication path",
    "reviewer evidence map and editor screening checklist",
)
PDF_STALE_PROSE_SNIPPETS = (
    "unflattering denominator",
    "hiding it would be worse",
    "silent wins",
    "users pay for",
    "must be read row by row",
    "limitations are blunt",
    "final manual PDF visual check, and the agent-interface value boundary",
    "pretending it is a strict R/Synth parity pass",
    "harshest reviewer",
)
PAPER_README_REVIEWER_COMMANDS = (
    "make reproduce-jss PYTHON=../.venv/bin/python",
    "make audit PYTHON=../.venv/bin/python",
    "../.venv/bin/python replication/reproduce.py --tier 1",
    "../.venv/bin/python replication/reproduce.py --tier 1 \\\n  --transcript replication/results/reproduce_tier1_output.txt",
    "../.venv/bin/python replication/reproduce.py --tier 2",
    "../.venv/bin/python replication/reproduce.py --tier 3",
    "STATA_EXE=/path/to/stata-mp ../.venv/bin/python replication/reproduce.py --tier 3",
    "make submission-ready PYTHON=../.venv/bin/python",
    "make submission-risk-ledger PYTHON=../.venv/bin/python",
    "make reviewer-evidence-map PYTHON=../.venv/bin/python",
    "make editor-screening-checklist PYTHON=../.venv/bin/python",
    "make manuscript-artifact-audit PYTHON=../.venv/bin/python",
    "make pdf-render-audit PYTHON=../.venv/bin/python",
    "make pdf-visual-check-protocol PYTHON=../.venv/bin/python",
    "make jss-formal-compliance-audit PYTHON=../.venv/bin/python",
    "make gap-ledger PYTHON=../.venv/bin/python",
    "make stata-bridge-audit PYTHON=../.venv/bin/python",
    "make stata-rerun-protocol PYTHON=../.venv/bin/python",
    "make agent-interface-audit PYTHON=../.venv/bin/python",
    "make agent-benchmark-protocol PYTHON=../.venv/bin/python",
    "make data-provenance-audit PYTHON=../.venv/bin/python",
    "make bibliography-metadata-audit PYTHON=../.venv/bin/python",
    "make release-audit PYTHON=../.venv/bin/python",
    "make release-boundary-audit PYTHON=../.venv/bin/python",
    "make reproduction-environment-audit PYTHON=../.venv/bin/python",
    "make jss-style PYTHON=../.venv/bin/python",
)
MANUSCRIPT_README_REVIEWER_COMMANDS = (
    "make reproduce-jss",
    "make reproduce-jss-full PYTHON=../.venv/bin/python",
    "make release-audit PYTHON=../.venv/bin/python",
    "make submission-ready PYTHON=../.venv/bin/python",
    "docker build -f Paper-JSS/replication/Dockerfile -t statspai-jss .",
    "docker run --rm statspai-jss",
    "cd Paper-JSS && make submission-ready PYTHON=../.venv/bin/python",
)

REQUIRED_MEMBERS = {
    "Paper-JSS/manuscript/main.tex",
    "Paper-JSS/manuscript/main.pdf",
    "Paper-JSS/manuscript/jss-bib.bib",
    "Paper-JSS/requirements-jss.txt",
    "Paper-JSS/replication/Dockerfile",
    "LICENSE",
    "pyproject.toml",
    "CITATION.cff",
    "src/statspai/CITATION.cff",
    "MIGRATION.md",
    "Paper-JSS/replication/results/jss_full_audit.md",
    "Paper-JSS/replication/results/jss_full_audit.json",
    "Paper-JSS/replication/results/claim_lint.md",
    "Paper-JSS/replication/results/claim_lint.json",
    "Paper-JSS/replication/results/agent_interface_audit.md",
    "Paper-JSS/replication/results/agent_benchmark_protocol.md",
    "Paper-JSS/replication/results/agent_benchmark_protocol.json",
    "Paper-JSS/replication/results/release_boundary_audit.md",
    "Paper-JSS/replication/results/release_boundary_audit.json",
    "Paper-JSS/replication/results/reproduction_environment_audit.md",
    "Paper-JSS/replication/results/pdf_render_audit.md",
    "Paper-JSS/replication/results/pdf_render_audit.json",
    "Paper-JSS/replication/results/pdf_visual_check_protocol.md",
    "Paper-JSS/replication/results/pdf_visual_check_protocol.json",
    "Paper-JSS/replication/results/manuscript_artifact_audit.md",
    "Paper-JSS/replication/results/manuscript_artifact_audit.json",
    "Paper-JSS/replication/results/data_provenance_audit.md",
    "Paper-JSS/replication/results/data_provenance_audit.json",
    "Paper-JSS/replication/results/jss_formal_compliance_audit.md",
    "Paper-JSS/replication/results/jss_formal_compliance_audit.json",
    "Paper-JSS/replication/results/jss_house_style_audit.md",
    "Paper-JSS/replication/results/jss_house_style_audit.json",
    "Paper-JSS/replication/results/bibliography_metadata_audit.md",
    "Paper-JSS/replication/results/bibliography_metadata_audit.json",
    "Paper-JSS/replication/results/experiment_triage.md",
    "Paper-JSS/replication/results/experiment_triage.json",
    "Paper-JSS/replication/results/submission_risk_ledger.md",
    "Paper-JSS/replication/results/submission_risk_ledger.json",
    "Paper-JSS/replication/results/reviewer_evidence_map.md",
    "Paper-JSS/replication/results/reviewer_evidence_map.json",
    "Paper-JSS/replication/results/editor_screening_checklist.md",
    "Paper-JSS/replication/results/editor_screening_checklist.json",
    "Paper-JSS/replication/results/reproduce_tier1_output.txt",
    "Paper-JSS/replication/results/methodological_gap_ledger.md",
    "Paper-JSS/replication/results/stata_bridge_audit.md",
    "Paper-JSS/replication/results/stata_rerun_protocol.md",
    "Paper-JSS/replication/results/stata_rerun_protocol.json",
    "Paper-JSS/replication/results/source_snapshot_manifest.json",
    "Paper-JSS/replication/results/source_snapshot_manifest.md",
    "Paper-JSS/replication/results/validation_evidence_audit.md",
    "Paper-JSS/replication/results/validation_evidence_audit.json",
    "Paper-JSS/replication/scripts/agent_interface_audit.py",
    "Paper-JSS/replication/scripts/agent_benchmark_protocol.py",
    "Paper-JSS/replication/scripts/jss_full_audit.py",
    "Paper-JSS/replication/scripts/jss_submission_package.py",
    "Paper-JSS/replication/scripts/methodological_gap_ledger.py",
    "Paper-JSS/replication/scripts/release_boundary_audit.py",
    "Paper-JSS/replication/scripts/reproduction_environment_audit.py",
    "Paper-JSS/replication/scripts/pdf_render_audit.py",
    "Paper-JSS/replication/scripts/pdf_visual_check_protocol.py",
    "Paper-JSS/replication/scripts/manuscript_artifact_audit.py",
    "Paper-JSS/replication/scripts/data_provenance_audit.py",
    "Paper-JSS/replication/scripts/jss_formal_compliance_audit.py",
    "Paper-JSS/replication/scripts/jss_house_style_audit.py",
    "Paper-JSS/replication/scripts/bibliography_metadata_audit.py",
    "Paper-JSS/replication/scripts/experiment_triage.py",
    "Paper-JSS/replication/scripts/submission_risk_ledger.py",
    "Paper-JSS/replication/scripts/reviewer_evidence_map.py",
    "Paper-JSS/replication/scripts/editor_screening_checklist.py",
    "Paper-JSS/replication/scripts/stata_bridge_audit.py",
    "Paper-JSS/replication/scripts/stata_rerun_protocol.py",
    "Paper-JSS/replication/scripts/source_snapshot_manifest.py",
    "Paper-JSS/replication/scripts/validate_claims.py",
    "Paper-JSS/replication/scripts/verify_jss_style.py",
    "Paper-JSS/replication/scripts/validation_evidence_audit.py",
    "Paper-JSS/replication/scripts/verify_submission_package.py",
    "schemas/index.json",
    "schemas/tools.json",
    "schemas/functions.json",
    "schemas/agent_cards.json",
    "schemas/result.schema.json",
    "src/statspai/__init__.py",
    "src/statspai/schemas/index.json",
    "src/statspai/schemas/tools.json",
    "src/statspai/schemas/functions.json",
    "src/statspai/schemas/agent_cards.json",
    "src/statspai/schemas/result.schema.json",
    "scripts/dump_schemas.py",
    "tests/test_api_stable_evidence.py",
    "tests/test_jss_formal_compliance.py",
    "tests/test_jss_manuscript_artifacts.py",
    "tests/test_jss_reproduction_environment.py",
    "tests/test_jss_validation_api.py",
    "tests/test_jss_release_manifest.py",
    "tests/test_augsynth_backend.py",
    "tests/test_gsynth_backend.py",
    "tests/test_honest_did_backend.py",
    "tests/test_rddensity_io.py",
    "tests/test_sdid_backend.py",
    "tests/test_synth_backend.py",
    "tests/test_stability_audit.py",
    "tests/test_schema_export.py",
    "docs/index.md",
    "docs/getting-started.md",
    "docs/guides/migration-from-r.md",
    "docs/guides/stability.md",
    "docs/jss_source_audit_dossier.md",
    "docs/reference/index.md",
    "tests/r_parity/README.md",
    "tests/r_parity/renv.lock",
    "tests/r_parity/R_ENVIRONMENT.md",
    "tests/r_parity/verify_reproduce.py",
    "tests/r_parity/results/REPRODUCIBILITY_REPORT.md",
    "tests/stata_parity/STATA_ENVIRONMENT.md",
    "tests/stata_parity/verify_reproduce_stata.py",
    "tests/stata_parity/results/REPRODUCIBILITY_REPORT_STATA.md",
    "tests/reference_parity/test_scm_recovery.py",
}

FORBIDDEN_PATTERNS = (
    re.compile(r"(^|/)__pycache__/"),
    re.compile(r"(^|/)[^/]+\.egg-info/"),
    re.compile(r"\.pyc$"),
    re.compile(r"\.DS_Store$"),
    re.compile(r"(^|/)\.gitignore$"),
    re.compile(r"^Paper-JSS/100-emails/"),
    re.compile(r"^Paper-JSS/build/"),
    re.compile(r"^Paper-JSS/DRAFT-NOTES\.md$"),
    re.compile(r"^Paper-JSS/JSS-research-plan\.md$"),
    re.compile(r"^Paper-JSS/JSS-1\.30-SUBMISSION-PLAN\.md$"),
    re.compile(r"^Paper-JSS/NEXT-STEPS\.md$"),
    re.compile(r"^Paper-JSS/REVIEW-IMPROVEMENTS\.md$"),
    re.compile(r"^Paper-JSS/REVIEW-ROUND2-HARSH-OPUS\.md$"),
    re.compile(r"^Paper-JSS/_convert_to_pdf\.py$"),
    re.compile(r"^Paper-JSS/_table_style\.tex$"),
    re.compile(r"^Paper-JSS/build_zh\.sh$"),
    re.compile(r"^Paper-JSS/colab_gpu_bench\.ipynb$"),
    re.compile(r"^Paper-JSS/htmlcov/"),
    re.compile(r"^Paper-JSS/md2pdf\.py$"),
    re.compile(r"^Paper-JSS/md_to_pdf\.py$"),
    re.compile(r"^Paper-JSS/manuscript/main\.md$"),
    # The long-form drafts of the compact sections, which main.tex does not
    # \input. appendix.tex used to be one of them; it is now compiled (it
    # carries the full Track A ledger), so it is no longer forbidden here
    # and is listed in ACTIVE_MANUSCRIPT_SECTION_MEMBERS instead.
    re.compile(
        r"^Paper-JSS/manuscript/sections/"
        r"(?:01-introduction|02-architecture|03-agent-facing|04-examples|"
        r"05-parity|08-computational-details|09-discussion)\.tex$"
    ),
    re.compile(r"^Paper-JSS/manuscript/main-zh-header\.tex$"),
    re.compile(r"^Paper-JSS/manuscript/main-zh\.md$"),
    re.compile(r"^Paper-JSS/manuscript/main-zh-raster\.pdf$"),
    re.compile(r"^Paper-JSS/manuscript/main-zh\.pdf$"),
    re.compile(
        r"^Paper-JSS/manuscript/.*(?:\u8bc4\u5ba1|\u4e2d\u6587).*\.(?:md|pdf|tex)$"
    ),
    re.compile(r"^Paper-JSS/notes/"),
    # Paper-JSS/parity/ held hand-maintained worklog drafts and stays out of
    # the archive, with one exception: replacement-table.md is now a
    # generated, drift-checked artifact (build_replacement_table.py, wired
    # into the full audit) and is the comparative-scope evidence JSS asks
    # for. Negative lookahead keeps the rest of the directory forbidden.
    re.compile(r"^Paper-JSS/parity/(?!replacement-table\.md$)"),
    re.compile(r"^Paper-JSS/references/"),
    re.compile(r"^Paper-JSS/Scott-Meeting-TODO"),
    re.compile(r"^Paper-JSS/StatsPAI-"),
    re.compile(r"^README_CN\.md$"),
    re.compile(r"^tests/r_parity/PARITY_WORKLOG_.*\.md$"),
    re.compile(r"^tests/r_parity/PARITY_TEST_WORKLOG_.*\.md$"),
    re.compile("^docs/jo" "ss_reviewer_guide\\.md$"),
    re.compile("^docs/jo" "ss_validation_dossier\\.md$"),
    re.compile(r"\.docx$"),
)

ACTIVE_EXTERNAL_REVIEW_ARTIFACTS_FORBIDDEN_IN_ARCHIVE = {
    "paper.md",
    "docs/jo" "ss_reviewer_guide.md",
    "docs/jo" "ss_validation_dossier.md",
}
ACTIVE_EXTERNAL_REVIEW_ARTIFACT_REASONS = {
    "paper.md": "active short software paper for the separate review",
    "docs/jo" "ss_reviewer_guide.md": "active reviewer guide for the separate review",
    "docs/jo" "ss_validation_dossier.md": (
        "active validation dossier for the separate review"
    ),
}

SOURCE_SNAPSHOT_FORBIDDEN_SNIPPETS = (
    "Paper-JSS/notes/",
    "jss-submission-hardening",
    "tier2-reproduction-output",
)

ARCHIVE_FORBIDDEN_CLAIM_SNIPPETS = (
    "Most Comprehensive",
    "most comprehensive",
    "most complete across ecosystems",
    "full coverage",
    "Python's first feature-complete implementation",
    "Python's first unified CATE learner race",
    "Python's first unified spatial econometrics package",
    "most feature-complete",
    "first power-analysis tool",
    "gold standard",
    "empirical research workflow",
    "No competing package",
    "No other package",
    "no other package has these",
    "No other econometrics package",
    "no other econometrics package",
    "unique to StatsPAI",
    "Unique to StatsPAI",
    "StatsPAI's unique differentiator",
    "any language -- offers this",
    "any language \u2014 offers this",
    "available in any language",
    "Every estimator returns a unified",
    "Every result object exposes " "the same interface",
    "common result contract",
    "common result objects",
    "across every registered estimator",
    "Every result object has:",
    "Every result object speaks the same export protocol",
    "Every result object follows the same contract",
    "A machine-readable schema of every estimator",
    "exposes every estimator",
    "consumes every estimator",
    "Every estimator returns a result",
    "work across all estimators",
    "included in all estimators",
    "Every estimator's coefficient",
    "verifying every estimator recovers",
    "every estimator the package already",
    "Coverage: every estimator",
    "call every StatsPAI function",
    "\u81ea\u7136\u8bed\u8a00\u8c03\u7528\u6bcf\u4e2a\u51fd\u6570",
    "1,018-function registry",
    "1,018 registered public functions",
    "1,018-function surface",
    "1018-function surface",
    "Tier-B 127 / 1018",
    "**249,457**",
    "86,397",
    "266k LOC (core) + 93k LOC (tests)",
    "266k \u884c\u6838\u5fc3\u4ee3\u7801 + 93k \u884c\u6d4b\u8bd5",
    "550+ top-level functions",
    "Py-Stata-primary",
    "reported 50 rendered modules",
    "43 of 50 rendered modules",
    "Track A parity headline at \\statspai{} 1.16.0",
    "55 \\proglang{R}-parity modules",
    "for 44 of them, plus the separate",
    "all 44 R-joined",
    "46 of 47 data-driven modules",
    "7,096",
    "7{,}096",
    "2,360 (33.3%)",
    "2,360\uff0833.3%\uff09",
    "2{,}360 (33.3\\%)",
    "206 (2.9%)",
    "206\uff082.9%\uff09",
    "all exported helpers are validated",
    "every exported helper is validated",
    "fully " "validated package",
    "Validation: " "validated.",
    "[experimental] " "[experimental]",
    "Validation: experimental.",
    "Validation: deprecated.",
    "For JO" "SS Reviewers",
    "JO" "SS Reviewer Guide",
    "JO" "SS Validation Dossier",
    "JO" "SS reviewer-facing documentation",
    "A JO" "SS paper for StatsPAI is currently under review",
    "submitted to JO" "SS remains open",
    "docs/jo" "ss_reviewer_guide.md",
    "docs/jo" "ss_validation_dossier.md",
    "release blocker",
    "release-blocking",
    "World-class",
    "world-class",
    "best-in-class",
    "battle-tested",
    "One-Click Comprehensive",
    "drop-in replacement",
    "publication-grade",
    "publication-ready",
    "manuscript-ready",
    "journal-ready",
    "one-click",
    "one click",
    "state-of-the-art",
    "state of the art",
    "full research workflow",
    "full-stack",
    "single, consistent Python API",
    "single unified API",
    "all in one place",
    "Stata has almost none",
    "R has them scattered",
    "matches R's 5-package spatial stack",
    "Neither Stata nor R",
    "R has no equivalent",
    "Stata requires paid add-ons",
    "one-call comprehensive",
    "comprehensive report",
    "Full Python replication",
    "Data-driven bandwidth with formal optimality",
    "Word + Excel + LaTeX + HTML in every function",
    "Every estimator: `.to_word()`",
    "StatsPAI: An Agent-" "Native Python Toolkit",
    "\u9996\u4e2a\u4e3a LLM",
    "\u4efb\u4f55\u8bed\u8a00\u7684\u5305",
    "\u4efb\u4f55\u8bed\u8a00\u91cc\u8986\u76d6\u6700\u5b8c\u6574",
    "\u672c\u8868\u4e2d\u8986\u76d6\u6700\u5e7f",
    "\u5b8c\u6574\u8986\u76d6",
    "\u6240\u6709\u4f30\u8ba1\u5668\u8fd4\u56de\u540c\u6837",
    "\u76f8\u540c\u7684\u7ed3\u679c\u5bf9\u8c61\u4e0e schema \u5951\u7ea6",
    "\u6bcf\u4e2a\u4f30\u8ba1\u5668\u90fd\u76f4\u63a5\u652f\u6301",
    "\u6bcf\u4e2a\u51fd\u6570\u90fd\u652f\u6301 Word",
    "\u540c\u7b49\u6216\u66f4\u5f3a",
)
PAPER_JSS_ARCHIVE_FORBIDDEN_MARKERS = (
    "CLAUDE" + ".md",
    "CITATION-" + "PENDING",
    "PENDING" + " REVIEW",
    "submission" + " draft",
    "time of this" + " draft",
    "current" + " draft",
    "draft" + " now",
    "review" + " draft",
    "source-snapshot" + " draft",
    "article " + "draft",
    "article-class " + "draft",
    "earlier " + "drafts",
    "draft " + "build",
    "draft " + "previously",
    "draft " + "used",
    "this " + "draft",
)
ARCHIVE_CLAIM_GUARD_ALLOWLIST = {
    "Paper-JSS/replication/results/claim_lint.json",
    "Paper-JSS/replication/results/claim_lint.md",
    "Paper-JSS/replication/scripts/validate_claims.py",
    "Paper-JSS/replication/scripts/verify_submission_package.py",
    "tests/test_jss_release_manifest.py",
}

R_PARITY_README_REQUIRED_NATIVE_ROWS = (
    "Historical verification worklog (not the current source-snapshot audit)",
    "modules 01--52",
    '| 07 | Classical SCM | `sp.synth(method="classic", backend="native")`',
    '| 09 | RD density (CJM) | `sp.rddensity(backend="native")`',
    '| 12 | Synthetic DID | `sp.sdid(backend="native")`',
    '| 18 | Augmented SCM | `sp.augsynth(backend="native")`',
    '| 19 | Generalized SCM | `sp.gsynth(backend="native")`',
    "| 50 | Arellano--Bond GMM | `sp.xtabond` | `plm::pgmm` |",
    '| 52 | Identified classical SCM DGP | `sp.synth(method="classic", backend="native")`',
)

R_PARITY_README_FORBIDDEN_BRIDGE_ROWS = (
    "Latest full verification record",
    '| 50 | Arellano-Bond GMM | `sp.xtabond`',
    '| 07 | Classical SCM | `sp.synth(method="classic", backend="synth")`',
    '| 09 | RD density (CJM) | `sp.rddensity(backend="r")`',
    '| 12 | Synthetic DID | `sp.sdid(backend="synthdid")`',
    '| 18 | Augmented SCM | `sp.augsynth(backend="augsynth")`',
    '| 19 | Generalized SCM | `sp.gsynth(backend="gsynth")`',
)

PACKAGE_SIZE_DISCLOSURE_MEMBERS = (
    "Paper-JSS/README.md",
    "Paper-JSS/cover-letter.md",
    "Paper-JSS/REVIEWER-HARDENING-AUDIT.md",
)
ARCHIVE_CLAIM_TEXT_SUFFIXES = {
    ".bib",
    ".cff",
    ".do",
    ".json",
    ".md",
    ".py",
    ".pyi",
    ".r",
    ".rst",
    ".sh",
    ".tex",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

REQUIRED_JSS_FRONT_MATTER = (
    "author",
    "Plainauthor",
    "title",
    "Plaintitle",
    "Shorttitle",
    "Abstract",
    "Keywords",
    "Plainkeywords",
    "Address",
)

ASCII_SOURCE_SUFFIXES = {".py", ".R", ".do", ".sh", ".toml"}
ASCII_DATA_SUFFIXES = {".csv", ".json", ".lock"}
SCHEMA_BUNDLE_FILES = {
    "index.json",
    "tools.json",
    "functions.json",
    "agent_cards.json",
    "result.schema.json",
}
SCHEMA_PAYLOAD_FILES = SCHEMA_BUNDLE_FILES - {"index.json"}
ACTIVE_MANUSCRIPT_SECTION_MEMBERS = {
    f"Paper-JSS/manuscript/sections/{name}"
    for name in (
        "01-introduction-compact.tex",
        "02-architecture-compact.tex",
        "03-agent-facing-compact.tex",
        "04-examples-compact.tex",
        "05-parity-compact.tex",
        "06-performance.tex",
        "07-agent-eval.tex",
        "08-computational-details-compact.tex",
        "09-discussion-compact.tex",
        # The parity appendix: the full Track A ledger, printed rather
        # than left in the archive (Section A of the manuscript).
        "appendix.tex",
    )
}
ACTIVE_COMPARATIVE_SCOPE_SNIPPETS = (
    r"\label{tab:related-software}",
    "Closest existing implementations and comparative scope",
    "Where it remains the reference choice",
    r"\statspai{} contribution and boundary",
    "integration-and-validation layer around reference software",
    r"not a claim that \statspai{} supersedes",
    r"\pkg{statsmodels}",
    r"\pkg{linearmodels}",
    r"\pkg{DoubleML}",
    r"\pkg{EconML}",
    r"\pkg{CausalML}",
    r"\pkg{DoWhy}",
    r"\pkg{differences}",
    r"\pkg{pyfixest}",
    r"\pkg{causalimpact}",
    r"\pkg{fixest}",
    r"\pkg{did}",
    r"\pkg{rdrobust}",
    r"\pkg{rddensity}",
    r"\pkg{Synth}",
    r"\pkg{synthdid}",
    r"\pkg{MatchIt}",
    r"\pkg{grf}",
    r"\code{csdid}",
    r"\code{reghdfe}",
    r"\code{sdid}",
    "T3 stochastic agreement",
    "T4",
    "separate licensed runtime",
    "larger dependency surface",
)
ACTIVE_SOURCE_SNAPSHOT_SCOPE_SNIPPETS = (
    "This article describes \\statspai{} \\StatsPAIVersion{}",
    "The unification itself has costs",
    # 1.29.0 ported the fect/interflex CV selectors; the manuscript now
    # discloses that they can only be graded T3 (random folds).
    "cross-validation selectors for the",
    "can only be graded T3",
)


def _fail(msg: str) -> int:
    print(f"FAIL -- {msg}", file=sys.stderr)
    return 1


def _read_member(zf: zipfile.ZipFile, name: str) -> str:
    with zf.open(name) as fh:
        return fh.read().decode("utf-8")


def _read_binary_member(zf: zipfile.ZipFile, name: str) -> bytes:
    with zf.open(name) as fh:
        return fh.read()


def _read_json_member(zf: zipfile.ZipFile, name: str) -> dict:
    return json.loads(_read_member(zf, name))


def _resolve_reviewer_evidence_member(rel_path: str, names: set[str]) -> str | None:
    rel_path = rel_path.strip()
    if not rel_path or rel_path.startswith("/") or ".." in Path(rel_path).parts:
        return None
    for candidate in (rel_path, f"Paper-JSS/{rel_path}"):
        if candidate in names:
            return candidate
    return None


def _full_audit_package_line_ok(
    audit: str,
    *,
    archive_size_mib: float,
    archive_size_mb_decimal: float,
    file_count: int,
    manifest: dict,
    tolerance: float = 0.02,
) -> bool:
    match = re.search(
        r"Submission package: (?P<mib>\d+\.\d{2}) MiB "
        r"\((?P<mb>\d+\.\d{2}) MB decimal\), "
        r"(?P<files>\d+) files, within 50 MB=True; "
        r"registry evidence files=(?P<evidence>\d+); "
        r"ASCII-normalized source files=(?P<ascii>\d+); "
        r"ASCII data suffixes=(?P<suffixes>[^\n]+)",
        audit,
    )
    if not match:
        return False
    mib = float(match.group("mib"))
    mb_decimal = float(match.group("mb"))
    suffixes = ",".join(manifest.get("ascii_data_suffixes") or [])
    return (
        abs(mib - archive_size_mib) <= tolerance
        and abs(mb_decimal - archive_size_mb_decimal) <= tolerance
        and int(match.group("files")) == file_count
        and int(match.group("evidence")) == manifest.get(
            "registry_evidence_file_count"
        )
        and int(match.group("ascii")) == manifest.get(
            "ascii_normalized_source_file_count"
        )
        and match.group("suffixes") == suffixes
    )


def _archive_size_count_disclosure_ok(
    text: str,
    *,
    archive_size_mib: float,
    archive_size_mb_decimal: float,
    file_count: int,
) -> bool:
    """Require archive-size prose to match the final zip's fixed-point values."""
    for match in re.finditer(
        r"(?P<mib>\d+\.\d{2}) MiB "
        r"\((?P<mb>\d+\.\d{2}) MB decimal\).*?"
        r"(?P<files>\d{1,3}(?:,\d{3})*|\d+) files",
        text,
        flags=re.DOTALL,
    ):
        files = int(match.group("files").replace(",", ""))
        if (
            float(match.group("mib")) == round(archive_size_mib, 2)
            and float(match.group("mb")) == round(archive_size_mb_decimal, 2)
            and files == file_count
        ):
            return True
    return False


def _strip_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        escaped = False
        kept = []
        for char in line:
            if char == "\\":
                escaped = not escaped
                kept.append(char)
                continue
            if char == "%" and not escaped:
                break
            escaped = False
            kept.append(char)
        lines.append("".join(kept))
    return "\n".join(lines)


def _has_nonempty_macro(text: str, name: str) -> bool:
    match = re.search(rf"\\{re.escape(name)}\s*\{{(?P<body>.*?)\}}", text, re.DOTALL)
    if not match:
        return False
    return bool(re.sub(r"\s+", "", match.group("body")))


def _status_and_path(display_path: str) -> tuple[str, str]:
    if " " not in display_path:
        return "", display_path
    return display_path.split(" ", 1)


def _repro_report_counts(report: str) -> dict[str, int]:
    rows = [
        line for line in report.splitlines()
        if line.startswith("| `") and line.count("|") >= 7
    ]
    reproduced = [line for line in rows if "reproduces" in line]
    return {
        "rows": len(rows),
        "reproduced": len(reproduced),
        "non_reproduced": len(rows) - len(reproduced),
    }


def _pdf_page_count(pdf_bytes: bytes) -> int:
    """Return a lightweight page count for the generated manuscript PDF."""
    try:
        from pypdf import PdfReader  # noqa: WPS433
    except Exception as exc:  # pragma: no cover - dependency contract guard
        raise RuntimeError(
            "pypdf is required to verify the JSS manuscript page count"
        ) from exc
    return len(PdfReader(BytesIO(pdf_bytes)).pages)


def _pdf_text(pdf_bytes: bytes) -> str:
    """Return extracted text for reviewer-visible manuscript boundary checks."""
    try:
        from pypdf import PdfReader  # noqa: WPS433
    except Exception as exc:  # pragma: no cover - dependency contract guard
        raise RuntimeError(
            "pypdf is required to verify the JSS manuscript PDF text"
        ) from exc
    return "\n".join(
        page.extract_text() or ""
        for page in PdfReader(BytesIO(pdf_bytes)).pages
    )


def _expected_pdf_render_pages(page_count: int) -> list[int]:
    if page_count <= 0:
        return []
    return sorted({1, min(2, page_count), max(1, (page_count + 1) // 2), page_count})


def _mentions_page_count(text: str, page_count: int) -> bool:
    """Accept either prose page-count or compound page-count wording."""
    return bool(re.search(rf"\b{page_count}\s*(?:pages|page)\b", text)) or bool(
        re.search(rf"\b{page_count}-page\b", text)
    )


def _has_snippet(text: str, snippet: str) -> bool:
    """Find reviewer-facing snippets without depending on TeX line wraps."""
    # pypdf can drop the space at a font switch ("live\\proglang{R}" extracts
    # as "liveR"), so also compare with all whitespace removed.
    return (
        snippet in text
        or snippet in re.sub(r"\s+", " ", text)
        or re.sub(r"\s+", "", snippet) in re.sub(r"\s+", "", text)
    )


def _duplicate_next_action_bullets(markdown: str) -> list[str]:
    """Return repeated bullets from the reviewer-facing Next Actions section."""
    marker = "## Next Actions"
    if marker not in markdown:
        return []
    tail = markdown.split(marker, 1)[1]
    bullets = [
        line.strip()
        for line in tail.splitlines()
        if line.lstrip().startswith("- ")
    ]
    seen: set[str] = set()
    duplicates: list[str] = []
    for bullet in bullets:
        if bullet in seen and bullet not in duplicates:
            duplicates.append(bullet)
        seen.add(bullet)
    return duplicates


def _hardening_risk_items(markdown: str) -> list[tuple[int, str]]:
    """Return numbered hard-reviewer risk titles from the reviewer audit."""
    start = "## Hard Reviewer Risks Still Open"
    end = "## Next Actions"
    if start not in markdown or end not in markdown:
        return []
    body = markdown.split(start, 1)[1].split(end, 1)[0]
    items: list[tuple[int, str]] = []
    for line in body.splitlines():
        match = re.match(r"^\s*(\d+)\.\s+\*\*(.+?)\*\*", line)
        if match:
            items.append((int(match.group(1)), match.group(2)))
    return items


def _json_null_paths(value: object, prefix: str = "$") -> list[str]:
    """Return JSON pointer-like paths whose value is null."""
    if value is None:
        return [prefix]
    if isinstance(value, dict):
        paths: list[str] = []
        for key, child in value.items():
            paths.extend(_json_null_paths(child, f"{prefix}.{key}"))
        return paths
    if isinstance(value, list):
        paths = []
        for index, child in enumerate(value):
            paths.extend(_json_null_paths(child, f"{prefix}[{index}]"))
        return paths
    return []


def _verify_extracted_schema_bundle() -> str | None:
    """Check the submitted archive regenerates its schema bundle after extraction."""
    with tempfile.TemporaryDirectory(prefix="statspai-jss-schema-") as tmp:
        root = Path(tmp) / "archive"
        with zipfile.ZipFile(ARCHIVE) as zf:
            zf.extractall(root)
        env = dict(os.environ)
        src = str(root / "src")
        env["PYTHONPATH"] = (
            src if not env.get("PYTHONPATH") else src + os.pathsep + env["PYTHONPATH"]
        )
        proc = subprocess.run(
            [sys.executable, "scripts/dump_schemas.py", "--check"],
            cwd=root,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=90,
            check=False,
        )
    if proc.returncode != 0:
        tail = "\n".join(proc.stdout.splitlines()[-20:])
        return "extracted archive schema bundle is stale:\n" + tail
    return None


def _verify_extracted_install_import(expected_version: str) -> str | None:
    """Check the submitted archive itself is installable after extraction."""
    with tempfile.TemporaryDirectory(prefix="statspai-jss-install-") as tmp:
        root = Path(tmp) / "archive"
        target = Path(tmp) / "target"
        target.mkdir()
        with zipfile.ZipFile(ARCHIVE) as zf:
            zf.extractall(root)
        install_cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--quiet",
            "--disable-pip-version-check",
            "--no-deps",
            "--target",
            str(target),
            str(root),
        ]
        install = subprocess.run(
            install_cmd,
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=180,
            check=False,
        )
        if install.returncode != 0:
            tail = "\n".join(install.stdout.splitlines()[-20:])
            return "extracted archive pip install failed:\n" + tail
        probe_code = (
            "import json\n"
            "import statspai as sp\n"
            "print(json.dumps({"
            "'version': getattr(sp, '__version__', None), "
            "'function_count': len(sp.list_functions())"
            "}, sort_keys=True))\n"
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = (
            str(target)
            if not env.get("PYTHONPATH")
            else str(target) + os.pathsep + env["PYTHONPATH"]
        )
        probe = subprocess.run(
            [sys.executable, "-c", probe_code],
            cwd=root,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=120,
            check=False,
        )
        if probe.returncode != 0:
            tail = "\n".join(probe.stdout.splitlines()[-20:])
            return "extracted archive import probe failed:\n" + tail
        try:
            payload = json.loads(probe.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError):
            return "extracted archive import probe emitted non-JSON output"
        scripts = {
            path.name
            for path in (target / "bin").glob("*")
            if path.is_file()
        }
        dist_infos = [path for path in target.glob("*.dist-info") if path.is_dir()]
        if payload.get("version") != expected_version:
            return (
                "extracted archive import version mismatch: "
                f"{payload.get('version')} != {expected_version}"
            )
        if payload.get("function_count", 0) < 1000:
            return (
                "extracted archive import exposes too few registry functions: "
                f"{payload.get('function_count')}"
            )
        if not {"statspai", "statspai-mcp"} <= scripts:
            return (
                "extracted archive install lacks console scripts: "
                f"{sorted(scripts)}"
            )
        if not dist_infos:
            return "extracted archive install did not create dist-info metadata"
    return None


def _archive_forbidden_claim_hits(zf: zipfile.ZipFile) -> list[str]:
    """Return package-facing claim snippets that must not ship in the archive."""
    hits: list[str] = []
    for info in zf.infolist():
        name = info.filename
        if name in ARCHIVE_CLAIM_GUARD_ALLOWLIST:
            continue
        if Path(name).suffix.lower() not in ARCHIVE_CLAIM_TEXT_SUFFIXES:
            continue
        try:
            text = zf.read(info).decode("utf-8")
        except UnicodeDecodeError:
            continue
        folded_text = text.casefold()
        for snippet in ARCHIVE_FORBIDDEN_CLAIM_SNIPPETS:
            folded_snippet = snippet.casefold()
            if folded_snippet not in folded_text:
                continue
            for line_no, line in enumerate(text.splitlines(), 1):
                if folded_snippet in line.casefold():
                    hits.append(f"{name}:{line_no}: {snippet}")
                    break
    return hits


def _paper_jss_forbidden_marker_hits(zf: zipfile.ZipFile) -> list[str]:
    """Return internal/pending/draft markers from Paper-JSS archive members."""
    hits: list[str] = []
    for info in zf.infolist():
        name = info.filename
        if not name.startswith("Paper-JSS/"):
            continue
        if Path(name).suffix.lower() not in ARCHIVE_CLAIM_TEXT_SUFFIXES:
            continue
        try:
            text = zf.read(info).decode("utf-8")
        except UnicodeDecodeError:
            continue
        folded_text = text.casefold()
        for marker in PAPER_JSS_ARCHIVE_FORBIDDEN_MARKERS:
            folded_marker = marker.casefold()
            if folded_marker not in folded_text:
                continue
            for line_no, line in enumerate(text.splitlines(), 1):
                if folded_marker in line.casefold():
                    hits.append(f"{name}:{line_no}: {marker}")
                    break
    return hits


def _source_snapshot_archive_required(rel: str) -> bool:
    """Whether a dirty source-snapshot path must be present in the archive."""
    return not any(pattern.search(rel) for pattern in FORBIDDEN_PATTERNS)


def main() -> int:
    if not ARCHIVE.exists():
        return _fail(f"archive not found: {ARCHIVE}")
    if not MANIFEST_JSON.exists():
        return _fail(f"manifest not found: {MANIFEST_JSON}")

    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
    archive_size_bytes = ARCHIVE.stat().st_size
    archive_size_mib = round(archive_size_bytes / (1024 * 1024), 2)
    archive_size_mb_decimal = round(archive_size_bytes / 1_000_000, 2)

    if manifest.get("source_date_epoch") != SOURCE_DATE_EPOCH:
        return _fail("manifest source_date_epoch does not match verifier setting")
    if manifest.get("zip_member_datetime") != list(FIXED_ZIP_DATETIME):
        return _fail("manifest zip_member_datetime does not match fixed timestamp")

    with zipfile.ZipFile(ARCHIVE) as zf:
        names = set(zf.namelist())
        non_deterministic_timestamps = [
            item.filename for item in zf.infolist()
            if item.date_time != FIXED_ZIP_DATETIME
        ]
        if non_deterministic_timestamps:
            return _fail(
                "archive members do not use fixed SOURCE_DATE_EPOCH "
                "zip timestamps: "
                + ", ".join(non_deterministic_timestamps[:20])
            )
        missing = sorted(REQUIRED_MEMBERS - names)
        if missing:
            return _fail("required archive members missing: " + ", ".join(missing))

        evidence_files = manifest.get("registry_evidence_files", [])
        if not evidence_files:
            return _fail("manifest does not list registry evidence files")
        missing_evidence = sorted(set(evidence_files) - names)
        if missing_evidence:
            return _fail(
                "registry evidence files missing from archive: "
                + ", ".join(missing_evidence[:20])
            )
        if manifest.get("registry_evidence_file_count") != len(evidence_files):
            return _fail("manifest evidence-file count does not match evidence list")
        if (
            set(manifest.get("active_manuscript_sections", []))
            != ACTIVE_MANUSCRIPT_SECTION_MEMBERS
        ):
            return _fail(
                "manifest active manuscript sections do not match verifier allow-list"
            )
        expected_archive_generated = {
            "README.md",
            "CITATION.cff",
            "src/statspai/CITATION.cff",
        }
        if set(manifest.get("jss_archive_generated_files", [])) != expected_archive_generated:
            return _fail(
                "manifest JSS archive generated files do not match verifier allow-list"
            )
        if (
            set(manifest.get("active_external_review_artifacts_excluded", []))
            != ACTIVE_EXTERNAL_REVIEW_ARTIFACTS_FORBIDDEN_IN_ARCHIVE
        ):
            return _fail(
                "manifest active external-review exclusions do not match verifier allow-list"
            )
        if (
            manifest.get("active_external_review_artifact_reasons")
            != ACTIVE_EXTERNAL_REVIEW_ARTIFACT_REASONS
        ):
            return _fail(
                "manifest active external-review exclusion reasons do not match verifier"
            )

        forbidden = sorted(
            name for name in names
            if any(pattern.search(name) for pattern in FORBIDDEN_PATTERNS)
        )
        if forbidden:
            return _fail("forbidden archive members present: " + ", ".join(forbidden[:12]))

        claim_hits = _archive_forbidden_claim_hits(zf)
        if claim_hits:
            return _fail(
                "archive contains forbidden package-facing claim snippets: "
                + "; ".join(claim_hits[:12])
            )

        paper_marker_hits = _paper_jss_forbidden_marker_hits(zf)
        if paper_marker_hits:
            return _fail(
                "Paper-JSS archive contains internal/pending/draft markers: "
                + "; ".join(paper_marker_hits[:12])
            )

        file_count = len(names)
        if file_count != manifest.get("file_count"):
            return _fail(
                f"manifest file_count={manifest.get('file_count')} but zip has {file_count}"
            )
        if archive_size_bytes != manifest.get("size_bytes"):
            return _fail(
                f"manifest size_bytes={manifest.get('size_bytes')} "
                f"but zip is {archive_size_bytes}"
            )
        if archive_size_mib != manifest.get("size_mb"):
            return _fail(
                f"manifest size_mb={manifest.get('size_mb')} "
                f"but zip is {archive_size_mib} MiB"
            )
        if archive_size_mib != manifest.get("size_mib"):
            return _fail(
                f"manifest size_mib={manifest.get('size_mib')} "
                f"but zip is {archive_size_mib}"
            )
        if archive_size_mb_decimal != manifest.get("size_mb_decimal"):
            return _fail(
                "manifest size_mb_decimal="
                f"{manifest.get('size_mb_decimal')} but zip is "
                f"{archive_size_mb_decimal}"
            )
        size_text = (
            f"{archive_size_mib:.2f} MiB "
            f"({archive_size_mb_decimal:.2f} MB decimal)"
        )
        file_count_text = f"{file_count:,} files"
        for member in PACKAGE_SIZE_DISCLOSURE_MEMBERS:
            text = _read_member(zf, member)
            if not _archive_size_count_disclosure_ok(
                text,
                archive_size_mib=archive_size_mib,
                archive_size_mb_decimal=archive_size_mb_decimal,
                file_count=file_count,
            ):
                return _fail(
                    f"{member} does not report final archive size/count "
                    f"({size_text}, {file_count_text})"
                )
        if not manifest.get("within_jss_attachment_limit"):
            return _fail("manifest says archive exceeds JSS attachment limit")
        max_attachment_mb = float(manifest.get("max_attachment_mb", 50))
        if (
            archive_size_mib > max_attachment_mb
            or archive_size_mb_decimal > max_attachment_mb
        ):
            return _fail(
                "computed archive size exceeds JSS attachment limit under "
                "MiB or decimal-MB accounting"
            )
        if set(manifest.get("ascii_source_suffixes", [])) != ASCII_SOURCE_SUFFIXES:
            return _fail("manifest does not declare the expected ASCII source suffixes")
        if set(manifest.get("ascii_data_suffixes", [])) != ASCII_DATA_SUFFIXES:
            return _fail("manifest does not declare the expected ASCII data suffixes")
        normalized_sources = manifest.get("ascii_normalized_source_files", [])
        if manifest.get("ascii_normalized_source_file_count") != len(normalized_sources):
            return _fail("manifest ASCII-normalized source count does not match list")
        non_ascii_archive_files = []
        ascii_checked_suffixes = ASCII_SOURCE_SUFFIXES | ASCII_DATA_SUFFIXES
        for name in sorted(names):
            if Path(name).suffix not in ascii_checked_suffixes:
                continue
            try:
                zf.read(name).decode("ascii")
            except UnicodeDecodeError:
                non_ascii_archive_files.append(name)
        if non_ascii_archive_files:
            return _fail(
                "source/build/data files are not ASCII-clean inside archive: "
                + ", ".join(non_ascii_archive_files[:20])
            )
        root_schema = {Path(name).name for name in names if name.startswith("schemas/")}
        runtime_schema = {
            Path(name).name for name in names if name.startswith("src/statspai/schemas/")
        }
        if root_schema != SCHEMA_BUNDLE_FILES:
            return _fail(
                "root schema bundle file set mismatch: "
                + ", ".join(sorted(root_schema))
            )
        if runtime_schema != SCHEMA_BUNDLE_FILES:
            return _fail(
                "runtime schema bundle file set mismatch: "
                + ", ".join(sorted(runtime_schema))
            )
        root_index = json.loads(_read_member(zf, "schemas/index.json"))
        runtime_index = json.loads(_read_member(zf, "src/statspai/schemas/index.json"))
        for label, index in (("root", root_index), ("runtime", runtime_index)):
            if set(index.get("files", [])) != SCHEMA_PAYLOAD_FILES:
                return _fail(f"{label} schema index does not list the payload files")
            counts = index.get("counts", {})
            for key in ("tools", "functions", "agent_cards"):
                if not isinstance(counts.get(key), int) or counts.get(key) <= 0:
                    return _fail(f"{label} schema index lacks positive {key} count")
        if root_index != runtime_index:
            return _fail("root and runtime schema bundle indexes differ")

        archive_readme = _read_member(zf, "README.md")
        archive_readme_search_text = " ".join(archive_readme.split())
        for snippet in (
            "StatsPAI JSS Source Snapshot",
            "Paper-JSS/build/statspai-jss-submission-manifest.md",
            "generated metadata files",
            "active external-review exclusions",
            "paper.md",
            "docs/joss_*",
            "intentionally not included in this archive",
            "Minimal reviewer check from the extracted archive root",
            "cd Paper-JSS",
            "make reproduce-jss PYTHON=../.venv/bin/python",
            "make audit PYTHON=../.venv/bin/python",
        ):
            if snippet not in archive_readme_search_text:
                return _fail(f"archive root README lacks JSS boundary note: {snippet}")

        license_text = _read_member(zf, "LICENSE")
        if "MIT License" not in license_text or "Permission is hereby granted" not in license_text:
            return _fail("LICENSE inside archive is not the expected MIT license")
        pyproject = _read_member(zf, "pyproject.toml")
        if 'license = "MIT"' not in pyproject:
            return _fail("pyproject.toml does not declare the MIT license")
        if '"Development Status :: 3 - Alpha"' in pyproject:
            return _fail("pyproject.toml still declares an Alpha development classifier")
        if '"Development Status :: 4 - Beta"' not in pyproject:
            return _fail("pyproject.toml does not declare the reviewer-facing Beta classifier")
        pyproject_version = re.search(r'^version = "([^"]+)"$', pyproject, re.MULTILINE)
        if not pyproject_version:
            return _fail("pyproject.toml lacks a project version")
        if (
            'description = "Validation-tiered causal inference and econometrics workflows for Python"'
            not in pyproject
        ):
            return _fail("pyproject.toml does not use the scoped validation-tiered description")
        citation = _read_member(zf, "CITATION.cff")
        runtime_citation = _read_member(zf, "src/statspai/CITATION.cff")
        if citation != runtime_citation:
            return _fail("root and package CITATION.cff metadata differ")
        if f'version: "{pyproject_version.group(1)}"' not in citation:
            return _fail("CITATION.cff version does not match pyproject.toml")
        for snippet in (
            "cff-version: 1.2.0",
            "StatsPAI: A Unified, Agent-Native Python Toolkit for Causal Inference and Applied Econometrics",
            "preferred-citation:",
            "doi: \"10.21105/joss.10604\"",
            "repository-artifact: \"https://pypi.org/project/StatsPAI/\"",
            "license: MIT",
        ):
            if snippet not in citation:
                return _fail(f"CITATION.cff lacks {snippet!r}")
        if "Every estimator returns a unified" in citation:
            return _fail("CITATION.cff contains a blanket result-object claim")
        # The preferred citation is the published JOSS article (2026-09-03);
        # only review-stage placeholder wording is rejected here.
        for placeholder in (
            "under review",
            "forthcoming",
            "When the JO" "SS paper is accepted",
        ):
            if placeholder in citation:
                return _fail(
                    f"CITATION.cff still carries review-stage placeholder wording: {placeholder!r}"
                )

        audit = _read_member(zf, "Paper-JSS/replication/results/jss_full_audit.md")
        if "Status: PASS" not in audit:
            return _fail("jss_full_audit.md inside archive is not PASS")
        if not _full_audit_package_line_ok(
            audit,
            archive_size_mib=archive_size_mib,
            archive_size_mb_decimal=archive_size_mb_decimal,
            file_count=file_count,
            manifest=manifest,
        ):
            return _fail(
                "jss_full_audit.md package line is stale beyond the fixed-point "
                "archive-size tolerance"
            )
        stability_doc = _read_member(zf, "docs/guides/stability.md")
        dossier_doc = _read_member(zf, "docs/jss_source_audit_dossier.md")
        expected_evidence_phrase = (
            f"{manifest.get('registry_evidence_file_count')} such registry "
            "evidence files"
        )
        if expected_evidence_phrase not in stability_doc:
            return _fail(
                "stability guide does not report the final registry evidence "
                f"file count ({expected_evidence_phrase})"
            )
        if (
            "JSS source-snapshot validation audit (2026-06-28)" not in stability_doc
            or "2026-05-31" in stability_doc
        ):
            return _fail("stability guide carries a stale JSS audit date")
        if (
            "JSS source-snapshot audit date: 2026-06-28" not in dossier_doc
            or "2026-05-31" in dossier_doc
        ):
            return _fail("JSS source-audit dossier carries a stale audit date")
        if "Source snapshot:" not in audit or "version_consistent=True" not in audit:
            return _fail("jss_full_audit.md lacks a version-consistent source snapshot line")
        if (
            "final_publication_gate_ready=" not in audit
            or "gate_blocker_paths=" not in audit
        ):
            return _fail("jss_full_audit.md lacks final-publication gate fields")
        audit_blockers = re.search(r"gate_blocker_paths=(\d+)", audit)
        manifest_blockers = (
            manifest.get("source_snapshot", {}) or {}
        ).get("release_blocker_count")
        if audit_blockers and manifest_blockers is not None:
            if int(audit_blockers.group(1)) != int(manifest_blockers):
                return _fail(
                    "jss_full_audit.md gate_blocker_paths does not match "
                    "submission manifest"
                )
        if "Claim linter: PASS" not in audit:
            return _fail("jss_full_audit.md does not report a passing claim linter")
        if "historical_drift_files=10" not in audit:
            return _fail(
                "jss_full_audit.md does not expose historical claim-lint scope"
            )
        risk_ledger = _read_member(
            zf,
            "Paper-JSS/replication/results/submission_risk_ledger.md",
        )
        # The ledger emits `final_tagged_release_cut_pending` only while the
        # final cut is pending (see submission_risk_ledger.py); an archive
        # built from the tagged, clean tree carries the other risks only.
        # Gate the expected identity the same way so completing the cut
        # cannot turn this verifier red.
        final_cut_pending = "Final tagged-cut pending items: 0" not in risk_ledger
        expected_risk_ids = [
            risk_id
            for risk_id in EXPECTED_DOCUMENTED_NONBLOCKING_RISK_IDS
            if risk_id != "final_tagged_release_cut_pending" or final_cut_pending
        ]
        if "Status: PASS" not in risk_ledger:
            return _fail("submission_risk_ledger.md inside archive is not PASS")
        if "JSS upload blockers: 0" not in risk_ledger:
            return _fail("submission_risk_ledger.md reports JSS upload blockers")
        # A source-snapshot archive lists the pending final-cut items and the
        # `final_tagged_release_cut_pending` risk; an archive built from the
        # tagged, clean tree has none to list (pending items: 0) and the
        # ledger drops that risk row. Both are valid; only the missing
        # section is not.
        if "Final tagged-cut pending items:" not in risk_ledger or (
            "final_tagged_release_cut_pending" not in risk_ledger
            and "Final tagged-cut pending items: 0" not in risk_ledger
        ):
            return _fail(
                "submission_risk_ledger.md does not separate final tagged-cut pending items"
            )
        if "Final tagged-cut check identity: confirmed" not in risk_ledger:
            return _fail(
                "submission_risk_ledger.md does not confirm final tagged-cut check identity"
            )
        if "Documented nonblocking risk identity: confirmed" not in risk_ledger:
            return _fail(
                "submission_risk_ledger.md does not confirm nonblocking risk identity"
            )
        risk_ledger_json = _read_json_member(
            zf,
            "Paper-JSS/replication/results/submission_risk_ledger.json",
        )
        for blocker_id in risk_ledger_json.get("final_tagged_release_blocker_ids", []):
            if f"`{blocker_id}`" not in risk_ledger:
                return _fail(
                    f"submission_risk_ledger.md lacks final-cut check {blocker_id!r}"
                )
        for risk_id in expected_risk_ids:
            if f"`{risk_id}`" not in risk_ledger:
                return _fail(
                    f"submission_risk_ledger.md lacks nonblocking risk {risk_id!r}"
                )
        if "Keep the agent section mechanical and contractual unless" not in risk_ledger:
            return _fail(
                "submission_risk_ledger.md has stale agent-interface risk wording"
            )
        if risk_ledger_json.get("status") != "PASS":
            return _fail("submission_risk_ledger.json status is not PASS")
        if risk_ledger_json.get("jss_upload_blocker_count") != 0:
            return _fail("submission_risk_ledger.json reports upload blockers")
        if (
            final_cut_pending
            and risk_ledger_json.get("final_tagged_release_blocker_count", 0) < 1
        ):
            return _fail(
                "submission_risk_ledger.json does not record pending final tagged-cut items"
            )
        if (
            not final_cut_pending
            and risk_ledger_json.get("final_tagged_release_blocker_count", 0) != 0
        ):
            return _fail(
                "submission_risk_ledger.json and .md disagree on pending final tagged-cut items"
            )
        if (
            risk_ledger_json.get("expected_final_tagged_release_blocker_ids")
            != EXPECTED_FINAL_TAGGED_RELEASE_BLOCKER_IDS
        ):
            return _fail(
                "submission_risk_ledger.json expected final-cut check list is stale"
            )
        if not _is_ordered_expected_subset(
            risk_ledger_json.get("final_tagged_release_blocker_ids", []),
            EXPECTED_FINAL_TAGGED_RELEASE_BLOCKER_IDS,
        ):
            return _fail(
                "submission_risk_ledger.json final-cut pending checks are not "
                "an ordered subset of the expected release checks"
            )
        if risk_ledger_json.get("final_tagged_release_blocker_identity_ok") is not True:
            return _fail(
                "submission_risk_ledger.json reports final-cut check identity drift"
            )
        # The ledger records the master expectation (all six ids); the
        # gated list is what its own identity check and the map compare.
        if (
            risk_ledger_json.get("expected_documented_nonblocking_risk_ids")
            != EXPECTED_DOCUMENTED_NONBLOCKING_RISK_IDS
        ):
            return _fail(
                "submission_risk_ledger.json expected nonblocking risk list is stale"
            )
        if (
            risk_ledger_json.get("documented_nonblocking_risk_ids")
            != expected_risk_ids
        ):
            return _fail(
                "submission_risk_ledger.json nonblocking risk identity/order drift"
            )
        if risk_ledger_json.get("documented_nonblocking_risk_identity_ok") is not True:
            return _fail(
                "submission_risk_ledger.json reports nonblocking risk identity drift"
            )
        agent_risk_details = [
            risk
            for risk in risk_ledger_json.get("documented_nonblocking_risks", [])
            if risk.get("risk") == "agent_interface_value_boundary"
        ]
        if len(agent_risk_details) != 1:
            return _fail(
                "submission_risk_ledger.json lacks one agent-interface risk detail"
            )
        agent_risk_next_action = agent_risk_details[0].get("next_action", "")
        if (
            "mechanical and contractual" not in agent_risk_next_action
            or "deferred benchmark protocol labelled as protocol" not in agent_risk_next_action
        ):
            return _fail(
                "submission_risk_ledger.json has stale agent-interface next action"
            )
        stata_risk_details = [
            risk
            for risk in risk_ledger_json.get("documented_nonblocking_risks", [])
            if risk.get("risk") == "stata_tier3_requires_license"
        ]
        if len(stata_risk_details) != 1:
            return _fail("submission_risk_ledger.json lacks one Stata risk detail")
        stata_risk_text = (
            stata_risk_details[0].get("evidence", "")
            + " "
            + stata_risk_details[0].get("next_action", "")
        )
        for snippet in (
            "licensed rerun protocol packaged",
            "stata_rerun_protocol.md",
            "missing Stata as an optional-runtime skip",
        ):
            if snippet not in stata_risk_text:
                return _fail(
                    "submission_risk_ledger.json has stale Stata protocol "
                    f"wording: {snippet!r}"
                )
        compact_risk_details = [
            risk
            for risk in risk_ledger_json.get("documented_nonblocking_risks", [])
            if risk.get("risk") == "compact_text_may_feel_terse"
        ]
        if len(compact_risk_details) != 1:
            return _fail(
                "submission_risk_ledger.json lacks one compact-text risk detail"
            )
        compact_next_action = compact_risk_details[0].get("next_action", "")
        if (
            "final full-document human visual spot-check" not in compact_next_action
            or "pdf_visual_check_protocol.md" not in compact_next_action
            or "PDF render audit" not in compact_next_action
        ):
            return _fail(
                "submission_risk_ledger.json lacks the PDF manual visual-check next action"
            )
        source_snapshot_summary = risk_ledger_json.get("source_snapshot", {})
        final_cut_requirements = source_snapshot_summary.get(
            "final_publication_requirements"
        )
        if not isinstance(final_cut_requirements, list):
            return _fail(
                "submission_risk_ledger.json lacks final-publication requirements"
            )
        strict_release_command = source_snapshot_summary.get(
            "strict_release_command"
        )
        final_cut_runbook = risk_ledger_json.get("final_tagged_cut_runbook")
        if not isinstance(final_cut_runbook, dict):
            return _fail(
                "submission_risk_ledger.json lacks final tagged-cut runbook"
            )
        if final_cut_runbook.get("requirements") != final_cut_requirements:
            return _fail(
                "submission_risk_ledger.json runbook requirements drift from "
                "source snapshot"
            )
        if final_cut_runbook.get("step_count") != len(final_cut_requirements):
            return _fail(
                "submission_risk_ledger.json final tagged-cut runbook step "
                "count is stale"
            )
        runbook_steps = final_cut_runbook.get("steps")
        if not isinstance(runbook_steps, list):
            return _fail(
                "submission_risk_ledger.json final tagged-cut runbook lacks steps"
            )
        if [item.get("action") for item in runbook_steps] != final_cut_requirements:
            return _fail(
                "submission_risk_ledger.json final tagged-cut runbook steps "
                "drift from requirements"
            )
        if final_cut_runbook.get("strict_release_command") != strict_release_command:
            return _fail(
                "submission_risk_ledger.json final tagged-cut runbook strict "
                "command drift"
            )
        release_breakdown = source_snapshot_summary.get(
            "release_blocker_breakdown"
        )
        if not isinstance(release_breakdown, dict):
            return _fail(
                "submission_risk_ledger.json lacks final tagged-cut breakdown"
            )
        missing_breakdown_keys = [
            key for key in EXPECTED_RELEASE_BREAKDOWN_KEYS
            if key not in release_breakdown
        ]
        if missing_breakdown_keys:
            return _fail(
                "submission_risk_ledger.json final tagged-cut breakdown is "
                "missing keys: " + ", ".join(missing_breakdown_keys)
            )
        if "## Final Tagged-Cut Breakdown" not in risk_ledger:
            return _fail(
                "submission_risk_ledger.md lacks final tagged-cut breakdown"
            )
        for snippet in (
            "Hand-edited status counts",
            "Generated status counts",
            "Package code/script paths",
            "Package docs paths",
            "Validation test/data paths",
            "Paper manuscript paths",
            "Paper replication paths",
            "Paper other paths",
        ):
            if snippet not in risk_ledger:
                return _fail(
                    "submission_risk_ledger.md lacks final tagged-cut "
                    f"breakdown row: {snippet}"
                )
        if "## Final Tagged-Cut Runbook" not in risk_ledger:
            return _fail(
                "submission_risk_ledger.md lacks final tagged-cut runbook"
            )
        for index, requirement in enumerate(final_cut_requirements, start=1):
            if f"{index}. {requirement}" not in risk_ledger:
                return _fail(
                    "submission_risk_ledger.md lacks final tagged-cut "
                    f"runbook step {index}"
                )
        if f"Strict release guard: `{strict_release_command}`" not in risk_ledger:
            return _fail(
                "submission_risk_ledger.md lacks final tagged-cut strict "
                "release guard"
            )
        archive_risks = risk_ledger_json.get("archive", {})
        if archive_risks.get("active_external_review_artifacts_present"):
            return _fail(
                "submission_risk_ledger.json sees active JOSS artifacts in archive"
            )
        if archive_risks.get("legacy_manuscript_sources_present"):
            return _fail(
                "submission_risk_ledger.json sees dormant full manuscript sources in archive"
            )
        expected_risk_line = (
            "Submission risk ledger: PASS "
            f"(upload_blockers={risk_ledger_json.get('jss_upload_blocker_count')}; "
            "final_tagged_cut_pending_items="
            f"{risk_ledger_json.get('final_tagged_release_blocker_count')}; "
            "final_tagged_cut_identity=confirmed; "
            "nonblocking_risks="
            f"{len(risk_ledger_json.get('documented_nonblocking_risks', []))}; "
            "nonblocking_risk_identity=confirmed; "
            "active_external_present=0; legacy_sections_present=0)"
        )
        if expected_risk_line not in audit:
            return _fail(
                "jss_full_audit.md does not summarize the submission risk ledger"
            )
        data_provenance = _read_member(
            zf,
            "Paper-JSS/replication/results/data_provenance_audit.md",
        )
        data_provenance_json = _read_json_member(
            zf,
            "Paper-JSS/replication/results/data_provenance_audit.json",
        )
        data_summary = data_provenance_json.get("summary", {})
        if "Status: PASS" not in data_provenance:
            return _fail("data_provenance_audit.md inside archive is not PASS")
        if data_provenance_json.get("status") != "PASS":
            return _fail("data_provenance_audit.json status is not PASS")
        expected_data_summary = {
            "packaged_public_dataset_csv_count": 9,
            "public_original_extract_csv_count": 7,
            "same_byte_r_stata_fixture_csv_count": EXPECTED_R_STATA_FIXTURE_CSV_COUNT,
            "reference_fixture_csv_count": 229,
            "forbidden_raw_member_count": 0,
            "high_risk_path_hit_count": 0,
            "csv_parse_failure_count": 0,
            "unknown_category_count": 0,
            "self_audit_json_excluded_from_data_counts": True,
        }
        for key, expected in expected_data_summary.items():
            if data_summary.get(key) != expected:
                return _fail(
                    "data_provenance_audit.json has stale summary "
                    f"{key}: {data_summary.get(key)!r}"
                )
        if data_summary.get("csv_file_count", 0) < 100:
            return _fail("data_provenance_audit.json reports too few CSV files")
        required_data_categories = {
            "packaged_public_dataset_csv",
            "public_original_extract_csv",
            "same_byte_r_stata_fixture_csv",
            "reference_fixture_csv",
            "generated_r_parity_result_json",
            "generated_stata_result_json",
            "generated_original_parity_result_json",
            "generated_paper_audit_or_example_json",
            "schema_bundle_json",
            "runtime_schema_bundle_json",
        }
        category_counts = data_summary.get("category_counts", {})
        missing_categories = sorted(required_data_categories - set(category_counts))
        if missing_categories:
            return _fail(
                "data_provenance_audit.json lacks category counts: "
                + ", ".join(missing_categories)
            )
        for snippet in (
            "Forbidden raw-data members: `0`",
            "High-risk private/credential path hits: `0`",
            "CSV parse failures: `0`",
            "Unknown categories: `0`",
            "Packaged public dataset CSVs: `9`",
            "Public original-data extract CSVs: `7`",
            f"Same-byte R/Stata fixture CSVs: `{EXPECTED_R_STATA_FIXTURE_CSV_COUNT}`",
            "Failures: none",
        ):
            if snippet not in data_provenance:
                return _fail(
                    "data_provenance_audit.md lacks summary snippet: "
                    + snippet
                )
        data_doc_snippets = (
            f"{data_summary.get('scoped_data_file_count')} scoped data/result files",
            f"{data_summary.get('csv_file_count')} CSV files",
            (
                f"{data_summary.get('packaged_public_dataset_csv_count')} "
                "packaged public dataset CSVs"
            ),
            (
                f"{data_summary.get('public_original_extract_csv_count')} "
                "public original-data extract CSVs"
            ),
            (
                f"{data_summary.get('same_byte_r_stata_fixture_csv_count')} "
                "same-byte R/Stata fixture CSVs"
            ),
            f"{data_summary.get('reference_fixture_csv_count')} reference fixture CSVs",
            "zero forbidden raw-data members",
            "zero high-risk private/credential path hits",
            "zero CSV parse failures",
            "zero unknown categories",
        )
        for rel in ("Paper-JSS/README.md", "Paper-JSS/REVIEWER-HARDENING-AUDIT.md"):
            text = _read_member(zf, rel)
            for snippet in data_doc_snippets:
                if snippet not in text:
                    return _fail(
                        f"{rel} has stale data provenance summary: {snippet!r}"
                    )
        if (
            "Data provenance audit: PASS" not in audit
            or f"scoped_files={data_summary.get('scoped_data_file_count')}" not in audit
            or "public_datasets=9" not in audit
            or "original_extracts=7" not in audit
            or f"r_stata_csv={EXPECTED_R_STATA_FIXTURE_CSV_COUNT}" not in audit
            or "forbidden_raw=0" not in audit
            or "private_path_hits=0" not in audit
            or "unknown=0" not in audit
        ):
            return _fail(
                "jss_full_audit.md does not report a passing data provenance audit"
            )
        reviewer_map = _read_member(
            zf,
            "Paper-JSS/replication/results/reviewer_evidence_map.md",
        )
        if "Status: PASS" not in reviewer_map:
            return _fail("reviewer_evidence_map.md inside archive is not PASS")
        for card_id in EXPECTED_REVIEWER_CARD_IDS:
            if f"`{card_id}`" not in reviewer_map:
                return _fail(f"reviewer_evidence_map.md lacks card id {card_id!r}")
        if "## Suggested Review Routes" not in reviewer_map:
            return _fail("reviewer_evidence_map.md lacks suggested review routes")
        for route_id in EXPECTED_REVIEWER_ROUTE_IDS:
            if f"`{route_id}`" not in reviewer_map:
                return _fail(
                    f"reviewer_evidence_map.md lacks route id {route_id!r}"
                )
        for snippet in (
            "fast upload-readiness and JSS-form check",
            "audit the statistical evidence",
            "without live R or Stata",
            "not behavioural agent performance",
            "source-snapshot wording",
        ):
            if snippet not in reviewer_map:
                return _fail(
                    f"reviewer_evidence_map.md lacks route wording {snippet!r}"
                )
        for snippet in (
            "What exactly is validated, and what is only API-stable?",
            "Can headline Section 4-7 numbers be checked quickly?",
            "Where do R/Stata comparisons stop being equality claims?",
            "Do active tables and figures map to generators?",
            "Do the worked examples match executable scripts and manuscript claims?",
            "Which high-ROI experiments are implemented, bounded, or deferred?",
            "Is the submitted archive bounded and free of review-lane spillover?",
            (
                "Are the related JOSS publication and conflict disclosures "
                "visible without modifying the archived JOSS files?"
            ),
            "Can the submitted source be installed and imported?",
            "Are agent-facing claims mechanical rather than behavioural?",
            (
                "Where are the compact paper's limitations and residual risks "
                "made explicit?"
            ),
            (
                "Is the validated core maintainable if the current maintainer "
                "or commercial sponsor changes?"
            ),
            "What remains after upload before a final tagged release?",
        ):
            if snippet not in reviewer_map:
                return _fail(f"reviewer_evidence_map.md lacks {snippet!r}")
        reviewer_map_json = _read_json_member(
            zf,
            "Paper-JSS/replication/results/reviewer_evidence_map.json",
        )
        reviewer_summary = reviewer_map_json.get("summary", {})
        if reviewer_map_json.get("status") != "PASS":
            return _fail("reviewer_evidence_map.json status is not PASS")
        if reviewer_summary.get("card_count", 0) < len(EXPECTED_REVIEWER_CARD_IDS):
            return _fail("reviewer_evidence_map.json has too few reviewer cards")
        reviewer_card_ids = [
            card.get("id") for card in reviewer_map_json.get("cards", [])
        ]
        reviewer_cards = reviewer_map_json.get("cards", [])
        if reviewer_card_ids != EXPECTED_REVIEWER_CARD_IDS:
            return _fail(
                "reviewer_evidence_map.json card identity/order drift: "
                + ", ".join(str(card_id) for card_id in reviewer_card_ids)
            )
        if reviewer_summary.get("expected_card_ids") != EXPECTED_REVIEWER_CARD_IDS:
            return _fail("reviewer_evidence_map.json expected card id list is stale")
        if reviewer_summary.get("card_ids") != EXPECTED_REVIEWER_CARD_IDS:
            return _fail("reviewer_evidence_map.json card id summary is stale")
        if reviewer_summary.get("card_identity_ok") is not True:
            return _fail("reviewer_evidence_map.json reports card identity drift")
        if reviewer_summary.get("route_count") != len(EXPECTED_REVIEWER_ROUTE_IDS):
            return _fail("reviewer_evidence_map.json has stale route count")
        if (
            reviewer_summary.get("expected_route_ids")
            != EXPECTED_REVIEWER_ROUTE_IDS
        ):
            return _fail("reviewer_evidence_map.json expected route id list is stale")
        if reviewer_summary.get("route_ids") != EXPECTED_REVIEWER_ROUTE_IDS:
            return _fail("reviewer_evidence_map.json route id summary is stale")
        if reviewer_summary.get("route_identity_ok") is not True:
            return _fail("reviewer_evidence_map.json reports route identity drift")
        if reviewer_summary.get("failed_routes") != 0:
            return _fail("reviewer_evidence_map.json reports failed routes")
        if reviewer_summary.get("failed_cards") != 0:
            return _fail("reviewer_evidence_map.json reports failed cards")
        if reviewer_summary.get("jss_upload_blockers") != 0:
            return _fail("reviewer_evidence_map.json reports upload blockers")
        if reviewer_summary.get("pdf_text_chars", 0) <= 0:
            return _fail("reviewer_evidence_map.json does not expose PDF text")
        if reviewer_summary.get("missing_pdf_boundary_snippets") != 0:
            return _fail(
                "reviewer_evidence_map.json reports missing PDF boundary snippets"
            )
        cross_language_cards = [
            card for card in reviewer_cards
            if card.get("id") == "cross_language_limits"
        ]
        if len(cross_language_cards) != 1:
            return _fail("reviewer_evidence_map.json lacks one cross-language card")
        cross_language_card = cross_language_cards[0]
        cross_metrics = cross_language_card.get("metrics", {})
        for required_path in (
            "replication/results/methodological_gap_ledger.md",
            "replication/results/stata_bridge_audit.md",
            "replication/results/stata_rerun_protocol.md",
            "manuscript/tables/track_a_cross_language_snapshot.tex",
        ):
            if required_path not in cross_language_card.get("primary_evidence", []):
                return _fail(
                    "cross-language reviewer card does not point to "
                    f"{required_path}"
                )
        expected_cross_metrics = {
            "methodological_gap_count": 1,
            "classified_gap_count": 1,
            "uncategorized_gap_count": 0,
            "stata_modules": EXPECTED_STATA_REPRO_MODULES,
            "r_joined_stata_modules": EXPECTED_STATA_REPRO_MODULES,
            "stata_rerun_protocol_status": "PASS",
            "stata_rerun_protocol_checklist_items": 8,
            "stata_rerun_requires_license": True,
            "stata_rerun_upload_blocking": False,
            "stata_rerun_claimed_live_rerun": False,
            "stata_rerun_non_reproduced_rows": 0,
        }
        stale_cross_metrics = [
            key
            for key, expected in expected_cross_metrics.items()
            if cross_metrics.get(key) != expected
        ]
        if stale_cross_metrics:
            return _fail(
                "cross-language reviewer card has stale metrics: "
                + ", ".join(stale_cross_metrics)
            )
        for snippet in (
            "### cross_language_limits",
            "- `stata_rerun_protocol_status`: `PASS`",
            "- `stata_rerun_requires_license`: `True`",
            "- `stata_rerun_upload_blocking`: `False`",
            "- `stata_rerun_claimed_live_rerun`: `False`",
        ):
            if snippet not in reviewer_map:
                return _fail(f"reviewer_evidence_map.md lacks {snippet!r}")
        experiment_cards = [
            card for card in reviewer_cards
            if card.get("id") == "experiment_triage"
        ]
        if len(experiment_cards) != 1:
            return _fail("reviewer_evidence_map.json lacks one experiment triage card")
        experiment_card = experiment_cards[0]
        experiment_metrics = experiment_card.get("metrics", {})
        if "replication/results/experiment_triage.md" not in experiment_card.get(
            "primary_evidence", []
        ):
            return _fail("experiment triage card does not point to experiment_triage.md")
        if "replication/scripts/experiment_triage.py" not in experiment_card.get(
            "primary_evidence", []
        ):
            return _fail("experiment triage card does not point to its generator")
        if "replication/results/agent_benchmark_protocol.md" not in experiment_card.get(
            "primary_evidence", []
        ):
            return _fail(
                "experiment triage card does not point to agent_benchmark_protocol.md"
            )
        if experiment_metrics.get("triage_items") != 8:
            return _fail("experiment triage card reports stale item count")
        if experiment_metrics.get("triage_failed_items") != 0:
            return _fail("experiment triage card reports failed items")
        if experiment_metrics.get("jss_upload_blocking_item_count") != 0:
            return _fail("experiment triage card reports upload-blocking items")
        if experiment_metrics.get("agent_protocol_arms") != 3:
            return _fail("experiment triage card reports stale agent protocol arms")
        if experiment_metrics.get("agent_protocol_task_families") != 5:
            return _fail(
                "experiment triage card reports stale agent protocol task families"
            )
        if experiment_metrics.get("agent_protocol_jss_upload_blocking") is not False:
            return _fail(
                "experiment triage card marks the agent protocol as upload-blocking"
            )
        experiment_triage_md = _read_member(
            zf,
            "Paper-JSS/replication/results/experiment_triage.md",
        )
        experiment_triage_json = _read_json_member(
            zf,
            "Paper-JSS/replication/results/experiment_triage.json",
        )
        agent_protocol_md = _read_member(
            zf,
            "Paper-JSS/replication/results/agent_benchmark_protocol.md",
        )
        agent_protocol_json = _read_json_member(
            zf,
            "Paper-JSS/replication/results/agent_benchmark_protocol.json",
        )
        if "mechanical and contractual interface audit" not in experiment_triage_md:
            return _fail(
                "experiment_triage.md lacks the contractual agent-interface boundary"
            )
        if "same validation ledger as human calls" not in experiment_triage_md:
            return _fail(
                "experiment_triage.md does not tie agent evidence to the validation ledger"
            )
        if "packaged deferred benchmark protocol" not in experiment_triage_md:
            return _fail(
                "experiment_triage.md does not point to the deferred benchmark protocol"
            )
        if "Deferred Behavioural Agent Benchmark Protocol" not in agent_protocol_md:
            return _fail("agent_benchmark_protocol.md lacks the protocol title")
        if "not a completed JSS result" not in agent_protocol_md:
            return _fail(
                "agent_benchmark_protocol.md lacks the completed-result boundary"
            )
        if "matched arms" not in agent_protocol_md or "leakage controls" not in agent_protocol_md:
            return _fail(
                "agent_benchmark_protocol.md lacks design/control wording"
            )
        agent_protocol_summary = agent_protocol_json.get("summary", {})
        expected_protocol_metrics = {
            "arm_count": 3,
            "task_family_count": 5,
            "scoring_dimension_count": 6,
            "validity_control_count": 6,
            "jss_upload_blocking": False,
            "jss_claimed_behavioral_result": False,
        }
        for key, expected in expected_protocol_metrics.items():
            if agent_protocol_summary.get(key) != expected:
                return _fail(
                    "agent_benchmark_protocol.json has stale metric "
                    f"{key}: {agent_protocol_summary.get(key)!r} != {expected!r}"
                )
        if agent_protocol_json.get("status") != "PASS":
            return _fail("agent_benchmark_protocol.json status is not PASS")
        behavioural_items = [
            item
            for item in experiment_triage_json.get("items", [])
            if item.get("id") == "behavioural_agent_benchmark"
        ]
        if len(behavioural_items) != 1:
            return _fail("experiment_triage.json lacks one behavioural-agent item")
        behavioural_answer = behavioural_items[0].get("answer", "")
        if (
            "mechanical and contractual interface audit" not in behavioural_answer
            or "same validation ledger as human calls" not in behavioural_answer
            or "packaged deferred benchmark protocol" not in behavioural_answer
        ):
            return _fail(
                "experiment_triage.json agent item has stale boundary wording"
            )
        behavioural_metrics = behavioural_items[0].get("metrics", {})
        if (
            behavioural_metrics.get("protocol_arms") != 3
            or behavioural_metrics.get("protocol_task_families") != 5
            or behavioural_metrics.get("protocol_scoring_dimensions") != 6
            or behavioural_metrics.get("protocol_validity_controls") != 6
            or behavioural_metrics.get("protocol_jss_upload_blocking") is not False
            or behavioural_metrics.get("protocol_claimed_behavioural_result") is not False
        ):
            return _fail(
                "experiment_triage.json behavioural-agent protocol metrics are stale"
            )
        experiment_classes = experiment_metrics.get("classification_counts", {})
        for class_id in (
            "implemented",
            "implemented_with_boundary",
            "external_runtime_documented",
            "deferred_to_separate_benchmark",
            "not_a_jss_claim",
            "post_upload_release_work",
        ):
            if class_id not in experiment_classes:
                return _fail(
                    "experiment triage card lacks classification " + class_id
                )
        archive_cards = [
            card for card in reviewer_cards
            if card.get("id") == "archive_boundary"
        ]
        if len(archive_cards) != 1:
            return _fail("reviewer_evidence_map.json lacks one archive-boundary card")
        archive_card = archive_cards[0]
        archive_metrics = archive_card.get("metrics", {})
        if "replication/results/data_provenance_audit.md" not in archive_card.get(
            "primary_evidence", []
        ):
            return _fail(
                "archive reviewer card does not point to data_provenance_audit.md"
            )
        for snippet in (
            "data-provenance audit",
            "forbidden raw-data formats",
            "private or credential path hits",
        ):
            if snippet not in archive_card.get("answer_boundary", ""):
                return _fail(
                    "archive reviewer card has stale data provenance boundary "
                    f"wording: {snippet!r}"
                )
            if snippet not in reviewer_map:
                return _fail(
                    "reviewer_evidence_map.md lacks archive data provenance "
                    f"wording: {snippet!r}"
                )
        expected_archive_data_metrics = {
            "data_provenance_status": "PASS",
            "data_provenance_packaged_public_datasets": 9,
            "data_provenance_public_original_extracts": 7,
            "data_provenance_r_stata_fixture_csv": EXPECTED_R_STATA_FIXTURE_CSV_COUNT,
            "data_provenance_forbidden_raw_members": 0,
            "data_provenance_high_risk_path_hits": 0,
            "data_provenance_unknown_categories": 0,
        }
        for key, expected in expected_archive_data_metrics.items():
            if archive_metrics.get(key) != expected:
                return _fail(
                    "archive reviewer card has stale data provenance metric "
                    f"{key}: {archive_metrics.get(key)!r}"
                )
        for snippet in (
            "### archive_boundary",
            "- `data_provenance_status`: `PASS`",
            "- `data_provenance_packaged_public_datasets`: `9`",
            "- `data_provenance_public_original_extracts`: `7`",
            f"- `data_provenance_r_stata_fixture_csv`: `{EXPECTED_R_STATA_FIXTURE_CSV_COUNT}`",
            "- `data_provenance_forbidden_raw_members`: `0`",
            "- `data_provenance_high_risk_path_hits`: `0`",
            "- `data_provenance_unknown_categories`: `0`",
        ):
            if snippet not in reviewer_map:
                return _fail(
                    f"reviewer_evidence_map.md lacks {snippet!r}"
                )
        reviewer_routes = reviewer_map_json.get("review_routes", [])
        reviewer_route_ids = [route.get("id") for route in reviewer_routes]
        if reviewer_route_ids != EXPECTED_REVIEWER_ROUTE_IDS:
            return _fail(
                "reviewer_evidence_map.json route identity/order drift: "
                + ", ".join(str(route_id) for route_id in reviewer_route_ids)
            )
        expected_route_first_reads = {
            "editor_triage": "replication/results/editor_screening_checklist.md",
            "statistical_validation": (
                "replication/results/validation_evidence_audit.md"
            ),
            "quick_reproduction": "replication/results/reproduce_tier1_output.txt",
            "agent_interface": "replication/results/agent_interface_audit.md",
            "limitations_and_release_boundary": (
                "manuscript/sections/09-discussion-compact.tex"
            ),
        }
        for route in reviewer_routes:
            route_id = route.get("id", "<missing-id>")
            if route.get("status") != "PASS":
                return _fail(
                    f"reviewer_evidence_map.json route {route_id!r} is not PASS"
                )
            if route.get("first_read") != expected_route_first_reads.get(route_id):
                return _fail(
                    f"reviewer_evidence_map.json route {route_id!r} "
                    "has stale first-read path"
                )
            if route.get("missing_cards"):
                return _fail(
                    f"reviewer_evidence_map.json route {route_id!r} "
                    "reports missing evidence cards"
                )
            unknown_cards = [
                card_id for card_id in route.get("evidence_cards", [])
                if card_id not in EXPECTED_REVIEWER_CARD_IDS
            ]
            if unknown_cards:
                return _fail(
                    f"reviewer_evidence_map.json route {route_id!r} "
                    "points to unknown cards: " + ", ".join(unknown_cards)
                )
        agent_cards = [
            card for card in reviewer_cards
            if card.get("id") == "agent_interface_boundary"
        ]
        if len(agent_cards) != 1:
            return _fail("reviewer_evidence_map.json lacks one agent-interface card")
        agent_boundary = agent_cards[0].get("answer_boundary", "")
        if (
            "mechanical and contractual interface" not in agent_boundary
            or "same validation ledger as human calls" not in agent_boundary
            or "deferred benchmark protocol" not in agent_boundary
        ):
            return _fail("agent-interface reviewer card has stale boundary wording")
        if "mechanical and contractual interface" not in reviewer_map:
            return _fail("reviewer_evidence_map.md lacks contractual agent wording")
        if "deferred benchmark protocol" not in reviewer_map:
            return _fail("reviewer_evidence_map.md lacks deferred benchmark protocol wording")
        agent_metrics = agent_cards[0].get("metrics", {})
        if (
            agent_metrics.get("protocol_arms") != 3
            or agent_metrics.get("protocol_task_families") != 5
            or agent_metrics.get("protocol_scoring_dimensions") != 6
            or agent_metrics.get("protocol_validity_controls") != 6
            or agent_metrics.get("protocol_claimed_behavioural_result") is not False
        ):
            return _fail("agent-interface reviewer card protocol metrics are stale")
        if "replication/results/agent_benchmark_protocol.md" not in agent_cards[0].get(
            "primary_evidence", []
        ):
            return _fail(
                "agent-interface reviewer card does not point to agent_benchmark_protocol.md"
            )
        related_review_cards = [
            card for card in reviewer_cards
            if card.get("id") == "related_review_coi_boundary"
        ]
        if len(related_review_cards) != 1:
            return _fail(
                "reviewer_evidence_map.json lacks one related-review/COI card"
            )
        related_review_card = related_review_cards[0]
        related_review_metrics = related_review_card.get("metrics", {})
        for required_path in (
            "cover-letter.md",
            "replication/results/jss_formal_compliance_audit.md",
            "replication/results/release_boundary_audit.md",
            "README.md",
        ):
            if required_path not in related_review_card.get("primary_evidence", []):
                return _fail(
                    "related-review reviewer card does not point to "
                    f"{required_path}"
                )
        expected_related_review_metrics = {
            "related_review_check": True,
            "source_snapshot_boundary_check": True,
            "release_boundary_status": "PASS",
            "active_external_present": 0,
        }
        stale_related_review_metrics = [
            key
            for key, expected in expected_related_review_metrics.items()
            if related_review_metrics.get(key) != expected
        ]
        if stale_related_review_metrics:
            return _fail(
                "related-review reviewer card has stale metrics: "
                + ", ".join(stale_related_review_metrics)
            )
        for snippet in (
            "### related_review_coi_boundary",
            "- `related_review_check`: `True`",
            "- `source_snapshot_boundary_check`: `True`",
            "- `release_boundary_status`: `PASS`",
            "- `active_external_present`: `0`",
        ):
            if snippet not in reviewer_map:
                return _fail(f"reviewer_evidence_map.md lacks {snippet!r}")
        software_cards = [
            card for card in reviewer_cards
            if card.get("id") == "software_installability"
        ]
        if len(software_cards) != 1:
            return _fail("reviewer_evidence_map.json lacks one software card")
        software_card = software_cards[0]
        software_metrics = software_card.get("metrics", {})
        if "manuscript/main.pdf" not in software_card.get("primary_evidence", []):
            return _fail("software reviewer card does not point to main.pdf")
        if "replication/results/pdf_render_audit.md" not in software_card.get(
            "primary_evidence", []
        ):
            return _fail("software reviewer card does not point to PDF render audit")
        if "replication/results/pdf_visual_check_protocol.md" not in (
            software_card.get("primary_evidence", [])
        ):
            return _fail(
                "software reviewer card does not point to PDF visual-check protocol"
            )
        if "source-synchronized polished PDF prose" not in software_card.get(
            "answer_boundary", ""
        ):
            return _fail("software reviewer card lacks PDF prose freshness boundary")
        if "source-synchronized polished PDF prose" not in reviewer_map:
            return _fail("reviewer_evidence_map.md lacks PDF prose freshness boundary")
        if software_metrics.get("formal_checks") != 23:
            return _fail("software reviewer card has stale formal-check count")
        if software_metrics.get("pdf_text_chars", 0) <= 0:
            return _fail("software reviewer card does not expose PDF text")
        if software_metrics.get("pdf_boundary_snippets") != len(PDF_BOUNDARY_SNIPPETS):
            return _fail("software reviewer card has stale PDF boundary count")
        if software_metrics.get("missing_pdf_boundary_snippets") != []:
            return _fail(
                "software reviewer card reports missing PDF boundary snippets"
            )
        if software_metrics.get("pdf_stale_prose_hits") != []:
            return _fail("software reviewer card reports stale PDF prose")
        if software_metrics.get("pdf_render_status") != "PASS":
            return _fail("software reviewer card does not expose passing PDF render audit")
        if software_metrics.get("pdf_render_failures") != 0:
            return _fail("software reviewer card reports PDF render failures")
        if software_metrics.get("pdf_rendered_pages", 0) < 4:
            return _fail("software reviewer card reports too few rendered PDF pages")
        if (
            software_metrics.get("pdf_full_document_rendered_pages")
            != reviewer_summary.get("pdf_pages")
        ):
            return _fail(
                "software reviewer card reports stale full-document PDF render count"
            )
        if software_metrics.get("pdf_full_document_failures") != 0:
            return _fail(
                "software reviewer card reports full-document PDF render failures"
            )
        if software_metrics.get("pdf_render_min_width", 0) < 600:
            return _fail("software reviewer card reports narrow PDF renders")
        if software_metrics.get("pdf_render_min_height", 0) < 800:
            return _fail("software reviewer card reports short PDF renders")
        if software_metrics.get("manual_visual_spot_check_required") is not True:
            return _fail(
                "software reviewer card lost the manual visual-check requirement"
            )
        if (
            software_metrics.get("manual_visual_spot_check_status")
            != MANUAL_VISUAL_SPOT_CHECK_STATUS
        ):
            return _fail(
                "software reviewer card has stale manual visual-check status"
            )
        if software_metrics.get("machine_render_not_human_review") is not True:
            return _fail(
                "software reviewer card conflates machine render with human review"
            )
        if software_metrics.get("pdf_visual_protocol_status") != "PASS":
            return _fail(
                "software reviewer card does not expose passing PDF visual protocol"
            )
        if software_metrics.get("pdf_visual_protocol_page_count") != (
            reviewer_summary.get("pdf_pages")
        ):
            return _fail("software reviewer card has stale PDF visual page count")
        if software_metrics.get("pdf_visual_protocol_checklist_items", 0) < 10:
            return _fail(
                "software reviewer card reports too few PDF visual checklist items"
            )
        if (
            software_metrics.get("pdf_visual_protocol_manual_status")
            != MANUAL_VISUAL_SPOT_CHECK_STATUS
        ):
            return _fail("software reviewer card has stale PDF visual protocol status")
        if (
            software_metrics.get("pdf_visual_protocol_claimed_manual_acceptance")
            is not False
        ):
            return _fail("software reviewer card falsely claims manual PDF acceptance")
        if (
            software_metrics.get("pdf_visual_protocol_recorded_by_protocol")
            is not False
        ):
            return _fail(
                "software reviewer card falsely records completed PDF visual review"
            )
        if software_metrics.get("pdf_visual_protocol_jss_upload_blocking") is not False:
            return _fail("software reviewer card makes PDF visual protocol upload-blocking")
        limitations_cards = [
            card for card in reviewer_cards
            if card.get("id") == "limitations_crosswalk"
        ]
        if len(limitations_cards) != 1:
            return _fail("reviewer_evidence_map.json lacks one limitations card")
        limitations_card = limitations_cards[0]
        limitations_metrics = limitations_card.get("metrics", {})
        for required_path in (
            "manuscript/sections/09-discussion-compact.tex",
            "REVIEWER-HARDENING-AUDIT.md",
            "replication/results/submission_risk_ledger.md",
            "replication/results/pdf_visual_check_protocol.md",
            "replication/results/validation_evidence_audit.md",
        ):
            if required_path not in limitations_card.get("primary_evidence", []):
                return _fail(
                    "limitations reviewer card does not point to "
                    f"{required_path}"
                )
        if limitations_metrics.get("pdf_pages", 999) > 52:
            return _fail("limitations reviewer card has stale PDF page count")
        if limitations_metrics.get("documented_nonblocking_risk_count") != len(
            expected_risk_ids
        ):
            return _fail(
                "limitations reviewer card has stale nonblocking risk count"
            )
        if limitations_metrics.get("documented_nonblocking_risk_ids") != (
            expected_risk_ids
        ):
            return _fail("limitations reviewer card has stale risk identity")
        if limitations_metrics.get("symbols_with_limitations", 0) <= 0:
            return _fail("limitations reviewer card does not expose scoped limitations")
        if limitations_metrics.get("pdf_visual_protocol_status") != "PASS":
            return _fail("limitations reviewer card does not expose PDF visual protocol")
        if limitations_metrics.get("pdf_visual_protocol_checklist_items", 0) < 10:
            return _fail(
                "limitations reviewer card reports too few PDF visual checklist items"
            )
        if (
            limitations_metrics.get("pdf_visual_protocol_manual_status")
            != MANUAL_VISUAL_SPOT_CHECK_STATUS
        ):
            return _fail("limitations reviewer card has stale PDF visual status")
        for snippet in (
            "- `pdf_text_chars`:",
            f"- `pdf_boundary_snippets`: `{len(PDF_BOUNDARY_SNIPPETS)}`",
            "- `missing_pdf_boundary_snippets`: `[]`",
            "- `pdf_render_status`: `PASS`",
            "- `pdf_render_failures`: `0`",
            "- `pdf_visual_protocol_status`: `PASS`",
            "- `pdf_visual_protocol_manual_status`: `PENDING_MANUAL_REVIEW`",
            "### limitations_crosswalk",
            "- `symbols_with_limitations`:",
        ):
            if snippet not in reviewer_map:
                return _fail(f"reviewer_evidence_map.md lacks {snippet!r}")
        if (
            reviewer_summary.get("documented_nonblocking_risk_ids")
            != expected_risk_ids
        ):
            return _fail(
                "reviewer_evidence_map.json nonblocking risk identity summary is stale"
            )
        if reviewer_summary.get("documented_nonblocking_risk_identity_ok") is not True:
            return _fail(
                "reviewer_evidence_map.json reports nonblocking risk identity drift"
            )
        reviewer_risk_details = reviewer_summary.get(
            "documented_nonblocking_risk_details"
        )
        ledger_risk_details = risk_ledger_json.get(
            "documented_nonblocking_risks", []
        )
        if not isinstance(reviewer_risk_details, list):
            return _fail(
                "reviewer_evidence_map.json does not expose nonblocking risk details"
            )
        if [item.get("risk") for item in reviewer_risk_details] != (
            expected_risk_ids
        ):
            return _fail(
                "reviewer_evidence_map.json nonblocking risk details are stale"
            )
        if reviewer_risk_details != ledger_risk_details:
            return _fail(
                "reviewer_evidence_map.json nonblocking risk details do not "
                "match submission_risk_ledger.json"
            )
        maintenance_cards = [
            card for card in reviewer_cards
            if card.get("id") == "maintenance_sustainability"
        ]
        if len(maintenance_cards) != 1:
            return _fail(
                "reviewer_evidence_map.json lacks one maintenance/sustainability card"
            )
        maintenance_card = maintenance_cards[0]
        maintenance_metrics = maintenance_card.get("metrics", {})
        for required_path in (
            "manuscript/sections/09-discussion-compact.tex",
            "LICENSE",
            "replication/results/manuscript_artifact_audit.md",
            "replication/results/reproduction_environment_audit.md",
        ):
            if required_path not in maintenance_card.get("primary_evidence", []):
                return _fail(
                    "maintenance reviewer card does not point to "
                    f"{required_path}"
                )
        expected_maintenance_metrics = {
            "mit_forkable": True,
            "regression_tests": True,
            "scripted_parity": True,
            "license_file": True,
            "artifact_hash_mismatches": 0,
            "tier1_complete": True,
            "r_reproduced_modules": EXPECTED_R_REPRO_MODULES,
            "stata_reproduced_modules": EXPECTED_STATA_REPRO_MODULES,
        }
        stale_maintenance_metrics = [
            key
            for key, expected in expected_maintenance_metrics.items()
            if maintenance_metrics.get(key) != expected
        ]
        if stale_maintenance_metrics:
            return _fail(
                "maintenance reviewer card has stale metrics: "
                + ", ".join(stale_maintenance_metrics)
            )
        for snippet in (
            "### maintenance_sustainability",
            "- `mit_forkable`: `True`",
            "- `regression_tests`: `True`",
            "- `scripted_parity`: `True`",
            f"- `r_reproduced_modules`: `{EXPECTED_R_REPRO_MODULES}`",
            f"- `stata_reproduced_modules`: `{EXPECTED_STATA_REPRO_MODULES}`",
        ):
            if snippet not in reviewer_map:
                return _fail(f"reviewer_evidence_map.md lacks {snippet!r}")
        final_cut_cards = [
            card for card in reviewer_cards
            if card.get("id") == "final_cut_boundary"
        ]
        if len(final_cut_cards) != 1:
            return _fail("reviewer_evidence_map.json lacks one final-cut card")
        final_cut_metrics = final_cut_cards[0].get("metrics", {})
        final_cut_answer = final_cut_cards[0].get("answer_boundary", "")
        if "pending source/tag/changelog items" in final_cut_answer:
            return _fail(
                "final-cut reviewer card has stale pending-item prose"
            )
        final_cut_answer_snippet = (
            "pending worktree, tag, changelog, and Paper-JSS finalization items"
        )
        if final_cut_answer_snippet not in final_cut_answer:
            return _fail(
                "final-cut reviewer card does not name Paper-JSS finalization "
                "as pending nonblocking work"
            )
        if final_cut_answer_snippet not in reviewer_map:
            return _fail(
                "reviewer_evidence_map.md has stale final-cut pending prose"
            )
        if final_cut_metrics.get("final_tagged_cut_breakdown") != release_breakdown:
            return _fail(
                "final-cut reviewer card does not expose final tagged-cut "
                "breakdown from the risk ledger"
            )
        if final_cut_metrics.get("final_tagged_cut_runbook_step_count") != len(
            final_cut_requirements
        ):
            return _fail(
                "final-cut reviewer card has stale final tagged-cut runbook "
                "step count"
            )
        if final_cut_metrics.get("final_tagged_cut_runbook") != final_cut_runbook:
            return _fail(
                "final-cut reviewer card does not expose the risk-ledger "
                "runbook"
            )
        if final_cut_metrics.get("strict_release_command") != strict_release_command:
            return _fail(
                "final-cut reviewer card has stale strict release command"
            )
        if final_cut_metrics.get("documented_nonblocking_risk_count") != len(
            expected_risk_ids
        ):
            return _fail("final-cut reviewer card has stale nonblocking risk count")
        if final_cut_metrics.get("documented_nonblocking_risk_details") != (
            ledger_risk_details
        ):
            return _fail(
                "final-cut reviewer card does not expose risk-ledger details"
            )
        if "## Final-Cut Nonblocking Risk Details" not in reviewer_map:
            return _fail(
                "reviewer_evidence_map.md lacks final-cut nonblocking risk table"
            )
        if (
            f"- `documented_nonblocking_risk_count`: "
            f"`{len(expected_risk_ids)}`"
            not in reviewer_map
        ):
            return _fail(
                "reviewer_evidence_map.md lacks nonblocking risk count metric"
            )
        if (
            f"- `final_tagged_cut_runbook_step_count`: "
            f"`{len(final_cut_requirements)}`"
            not in reviewer_map
        ):
            return _fail(
                "reviewer_evidence_map.md lacks final tagged-cut runbook count"
            )
        if "## Final Tagged-Cut Runbook" not in reviewer_map:
            return _fail(
                "reviewer_evidence_map.md lacks final tagged-cut runbook"
            )
        for index, requirement in enumerate(final_cut_requirements, start=1):
            if f"{index}. {requirement}" not in reviewer_map:
                return _fail(
                    "reviewer_evidence_map.md lacks final tagged-cut "
                    f"runbook step {index}"
                )
        if f"Strict release guard: `{strict_release_command}`" not in reviewer_map:
            return _fail(
                "reviewer_evidence_map.md lacks final tagged-cut strict "
                "release guard"
            )
        for item in ledger_risk_details:
            risk_id = item.get("risk")
            evidence = item.get("evidence")
            next_action = item.get("next_action")
            if f"`{risk_id}`" not in reviewer_map:
                return _fail(
                    f"reviewer_evidence_map.md lacks nonblocking risk {risk_id!r}"
                )
            for snippet in (evidence, next_action):
                if not isinstance(snippet, str) or snippet not in reviewer_map:
                    return _fail(
                        "reviewer_evidence_map.md lacks nonblocking risk "
                        f"detail for {risk_id!r}"
                    )
        missing_review_evidence = []
        for card in reviewer_map_json.get("cards", []):
            card_id = card.get("id", "<missing-id>")
            for rel_path in card.get("primary_evidence", []):
                if _resolve_reviewer_evidence_member(rel_path, names) is None:
                    missing_review_evidence.append(f"{card_id}:{rel_path}")
        for route in reviewer_map_json.get("review_routes", []):
            route_id = route.get("id", "<missing-route-id>")
            for rel_path in route.get("primary_evidence", []):
                if _resolve_reviewer_evidence_member(rel_path, names) is None:
                    missing_review_evidence.append(f"{route_id}:{rel_path}")
        if missing_review_evidence:
            return _fail(
                "reviewer_evidence_map.json points outside the submission archive: "
                + ", ".join(missing_review_evidence)
            )
        if reviewer_summary.get("archive_evidence_paths_missing") not in (0, None):
            return _fail(
                "reviewer_evidence_map.json reports missing archive evidence paths"
            )
        checked_paths = reviewer_summary.get("archive_evidence_paths_checked")
        resolved_paths = reviewer_summary.get("archive_evidence_paths_resolved")
        if (
            checked_paths is not None
            and resolved_paths is not None
            and checked_paths != resolved_paths
        ):
            return _fail(
                "reviewer_evidence_map.json archive evidence path summary is stale"
            )
        if (
            reviewer_summary.get("archive_file_count")
            != risk_ledger_json.get("archive", {}).get("file_count")
        ):
            return _fail(
                "reviewer_evidence_map.json archive count does not match "
                "submission risk ledger"
            )
        expected_reviewer_map_line = (
            "Reviewer evidence map: PASS "
            f"(cards={reviewer_summary.get('card_count')}; "
            f"routes={reviewer_summary.get('route_count')}; "
            f"pass_cards={reviewer_summary.get('pass_cards')}; "
            f"failed_cards={reviewer_summary.get('failed_cards')}; "
            f"failed_routes={reviewer_summary.get('failed_routes')}; "
            f"upload_blockers={reviewer_summary.get('jss_upload_blockers')}; "
            f"archive_files={reviewer_summary.get('archive_file_count')})"
        )
        if expected_reviewer_map_line not in audit:
            return _fail(
                "jss_full_audit.md does not summarize the reviewer evidence map"
            )
        editor_map = _read_member(
            zf,
            "Paper-JSS/replication/results/editor_screening_checklist.md",
        )
        if "Status: PASS" not in editor_map:
            return _fail(
                "editor_screening_checklist.md inside archive is not PASS"
            )
        for item_id in EXPECTED_EDITOR_CHECKLIST_ITEM_IDS:
            if f"`{item_id}`" not in editor_map:
                return _fail(
                    "editor_screening_checklist.md lacks item id "
                    f"{item_id!r}"
                )
        for snippet in (
            "Does the submitted PDF look like a JSS article?",
            "Are license and citation metadata explicit?",
            "Can the submitted source be installed/imported?",
            "Is there a short reviewer reproduction path?",
            "Is the upload archive bounded and review-lane clean?",
            "Are related-review and COI disclosures explicit?",
            "Can reviewers navigate evidence without guessing?",
            "Is upload readiness separated from final release cutting?",
            "Are residual risks disclosed without hiding upload blockers?",
            "Do active tables and figures map to generators?",
            "Are platform dependencies and RNG boundaries explicit?",
        ):
            if snippet not in editor_map:
                return _fail(
                    f"editor_screening_checklist.md lacks {snippet!r}"
                )
        editor_json = _read_json_member(
            zf,
            "Paper-JSS/replication/results/editor_screening_checklist.json",
        )
        editor_summary = editor_json.get("summary", {})
        if editor_json.get("status") != "PASS":
            return _fail("editor_screening_checklist.json status is not PASS")
        editor_item_ids = [
            item.get("id") for item in editor_json.get("items", [])
        ]
        if editor_item_ids != EXPECTED_EDITOR_CHECKLIST_ITEM_IDS:
            return _fail(
                "editor_screening_checklist.json item identity/order drift: "
                + ", ".join(str(item_id) for item_id in editor_item_ids)
            )
        if (
            editor_summary.get("expected_item_ids")
            != EXPECTED_EDITOR_CHECKLIST_ITEM_IDS
        ):
            return _fail(
                "editor_screening_checklist.json expected item id list is stale"
            )
        if editor_summary.get("item_ids") != EXPECTED_EDITOR_CHECKLIST_ITEM_IDS:
            return _fail(
                "editor_screening_checklist.json item id summary is stale"
            )
        if editor_summary.get("item_identity_ok") is not True:
            return _fail(
                "editor_screening_checklist.json reports item identity drift"
            )
        if (
            editor_summary.get("item_count")
            != len(EXPECTED_EDITOR_CHECKLIST_ITEM_IDS)
        ):
            return _fail(
                "editor_screening_checklist.json has stale item count"
            )
        for item in editor_json.get("items", []):
            item_id = item.get("id", "<missing-id>")
            metrics = item.get("metrics", {})
            for key, value in metrics.items():
                if value is None:
                    return _fail(
                        "editor_screening_checklist.json has null metric "
                        f"{item_id}.{key}"
                    )
        if editor_summary.get("failed_items") != 0:
            return _fail(
                "editor_screening_checklist.json reports failed items"
            )
        if editor_summary.get("jss_upload_blockers") != 0:
            return _fail(
                "editor_screening_checklist.json reports upload blockers"
            )
        if (
            editor_summary.get("reviewer_card_count")
            != len(EXPECTED_REVIEWER_CARD_IDS)
        ):
            return _fail(
                "editor_screening_checklist.json has stale reviewer card count"
            )
        if (
            editor_summary.get("reviewer_route_count")
            != len(EXPECTED_REVIEWER_ROUTE_IDS)
        ):
            return _fail(
                "editor_screening_checklist.json has stale reviewer route count"
            )
        editor_items = editor_json.get("items", [])
        editor_by_id = {item.get("id"): item for item in editor_items}
        if set(editor_by_id) != set(EXPECTED_EDITOR_CHECKLIST_ITEM_IDS):
            return _fail("editor_screening_checklist.json item lookup is stale")
        if editor_summary.get("tier1_step_summary") in (None, "unknown"):
            return _fail(
                "editor_screening_checklist.json lacks Tier-1 step summary"
            )
        if (
            editor_summary.get("manual_visual_spot_check_status")
            != MANUAL_VISUAL_SPOT_CHECK_STATUS
        ):
            return _fail(
                "editor_screening_checklist.json has stale manual visual-check status"
            )
        if editor_summary.get("pdf_visual_protocol_status") != "PASS":
            return _fail(
                "editor_screening_checklist.json lacks a passing PDF visual protocol"
            )
        if editor_summary.get("pdf_visual_protocol_checklist_items", 0) < 10:
            return _fail(
                "editor_screening_checklist.json reports too few PDF visual "
                "checklist items"
            )
        expected_card_answer = (
            f"{len(EXPECTED_REVIEWER_CARD_IDS)} stable PASS cards"
        )
        expected_route_answer = (
            f"{len(EXPECTED_REVIEWER_ROUTE_IDS)} suggested review routes"
        )
        expected_editor_answer_snippets = {
            "jss_pdf_front_matter": [
                f"{editor_summary.get('page_count')} pages",
                "packaged PDF visual-check protocol",
                "upload-time manual action",
            ],
            "reproduction_quick_path": [
                f"{editor_summary.get('tier1_step_summary')} reviewer transcript",
            ],
            "archive_size_boundary": [
                file_count_text,
                "data-provenance report",
                "zero forbidden raw-data members",
                "zero private/credential path hits",
                "zero unknown categories",
            ],
            "evidence_navigation": [
                expected_card_answer,
                expected_route_answer,
            ],
            "related_review_coi": [
                "doi.org/10.21105/joss.10604",
                "shares no table, figure, simulation, or parity ledger",
            ],
            "final_release_boundary": [
                f"{editor_summary.get('jss_upload_blockers')} JSS upload blockers",
                (
                    f"{editor_summary.get('final_tagged_cut_pending_items')} "
                    "currently pending final tagged-cut checks"
                ),
                (
                    f"{editor_summary.get('final_tagged_cut_runbook_steps')} "
                    "final tagged-release runbook steps"
                ),
                (
                    f"{editor_summary.get('source_release_pending_paths')} "
                    "pending source/test/docs blockers"
                ),
                (
                    f"{editor_summary.get('paper_release_pending_paths')} "
                    "Paper-JSS finalization paths"
                ),
            ],
            "nonblocking_risk_crosswalk": [
                (
                    f"{editor_summary.get('documented_nonblocking_risk_count')} "
                    "documented nonblocking risks"
                ),
                f"{editor_summary.get('jss_upload_blockers')} JSS upload blockers",
                "final tagged-release cleanup",
                "registry-breadth denominator disclosure",
                "Stata Tier 3 license boundary",
                "methodological/T4 disclosure",
                "compact-text/PDF-review boundary",
                "PDF-visible evidence routing",
                "page-inventory navigation",
                "final manual PDF visual-check protocol",
                "agent-interface value boundary",
            ],
        }
        for item_id, snippets in expected_editor_answer_snippets.items():
            answer = editor_by_id[item_id].get("answer", "")
            for snippet in snippets:
                if snippet not in answer:
                    return _fail(
                        "editor_screening_checklist.json has stale "
                        f"{item_id} prose: {snippet!r}"
                    )
                if snippet not in editor_map:
                    return _fail(
                        "editor_screening_checklist.md has stale "
                        f"{item_id} prose: {snippet!r}"
                    )
        stale_editor_risk_phrase = (
            "page-inventory navigation, and the final manual PDF visual-check "
            "protocol, and agent-interface value boundary"
        )
        if (
            stale_editor_risk_phrase
            in editor_by_id["nonblocking_risk_crosswalk"].get("answer", "")
            or stale_editor_risk_phrase in editor_map
        ):
            return _fail(
                "editor_screening_checklist carries stale ambiguous "
                "nonblocking-risk prose"
            )
        archive_editor_answer = editor_by_id.get("archive_size_boundary", {}).get(
            "answer", ""
        )
        if not _archive_size_count_disclosure_ok(
            archive_editor_answer,
            archive_size_mib=archive_size_mib,
            archive_size_mb_decimal=archive_size_mb_decimal,
            file_count=file_count,
        ):
            return _fail(
                "editor_screening_checklist.json has stale "
                f"archive_size_boundary size/count prose: {size_text}, "
                f"{file_count_text}"
            )
        if not _archive_size_count_disclosure_ok(
            editor_map,
            archive_size_mib=archive_size_mib,
            archive_size_mb_decimal=archive_size_mb_decimal,
            file_count=file_count,
        ):
            return _fail(
                "editor_screening_checklist.md has stale "
                f"archive_size_boundary size/count prose: {size_text}, "
                f"{file_count_text}"
            )
        archive_editor_item = editor_by_id.get("archive_size_boundary", {})
        archive_editor_metrics = archive_editor_item.get("metrics", {})
        if "replication/results/data_provenance_audit.md" not in (
            archive_editor_item.get("primary_evidence", [])
        ):
            return _fail(
                "archive-size editor item does not point to "
                "data_provenance_audit.md"
            )
        expected_archive_editor_metrics = {
            "data_provenance_status": "PASS",
            "data_provenance_packaged_public_datasets": 9,
            "data_provenance_public_original_extracts": 7,
            "data_provenance_r_stata_fixture_csv": EXPECTED_R_STATA_FIXTURE_CSV_COUNT,
            "data_provenance_forbidden_raw_members": 0,
            "data_provenance_high_risk_path_hits": 0,
            "data_provenance_unknown_categories": 0,
        }
        for key, expected in expected_archive_editor_metrics.items():
            if archive_editor_metrics.get(key) != expected:
                return _fail(
                    "archive-size editor item has stale data provenance "
                    f"metric {key}: {archive_editor_metrics.get(key)!r}"
                )
        for snippet in (
            "### archive_size_boundary",
            "- `data_provenance_status`: `PASS`",
            "- `data_provenance_packaged_public_datasets`: `9`",
            "- `data_provenance_public_original_extracts`: `7`",
            f"- `data_provenance_r_stata_fixture_csv`: `{EXPECTED_R_STATA_FIXTURE_CSV_COUNT}`",
            "- `data_provenance_forbidden_raw_members`: `0`",
            "- `data_provenance_high_risk_path_hits`: `0`",
            "- `data_provenance_unknown_categories`: `0`",
        ):
            if snippet not in editor_map:
                return _fail(
                    f"editor_screening_checklist.md lacks {snippet!r}"
                )
        if editor_summary.get("final_tagged_cut_runbook_steps") != len(
            final_cut_requirements
        ):
            return _fail(
                "editor_screening_checklist.json has stale final-cut runbook count"
            )
        if editor_summary.get("final_tagged_cut_pending_items") != risk_ledger_json.get(
            "final_tagged_release_blocker_count"
        ):
            return _fail(
                "editor_screening_checklist.json has stale final-cut pending count"
            )
        source_readiness = risk_ledger_json.get("source_snapshot", {})
        if editor_summary.get("source_release_pending_paths") != source_readiness.get(
            "source_release_blocker_count"
        ):
            return _fail(
                "editor_screening_checklist.json has stale source-release "
                "pending-path count"
            )
        submission_status = str(
            source_readiness.get("submission_archive_status")
            or source_snapshot_json.get("jss_source_snapshot", {}).get(
                "submission_archive_status", ""
            )
        )
        if "not a JSS upload reproducibility failure" not in submission_status:
            return _fail(
                "editor_screening_checklist.json lacks source-snapshot upload "
                "boundary disclosure for pending source-release paths"
            )
        if (
            editor_summary.get("source_release_pending_paths", 0) > 0
            and risk_ledger_json.get("final_tagged_release_blocker_identity_ok")
            is not True
        ):
            return _fail(
                "editor_screening_checklist.json reports pending source-release "
                "paths without final-cut blocker identity confirmation"
            )
        if editor_summary.get("paper_release_pending_paths") != source_readiness.get(
            "paper_release_blocker_count"
        ):
            return _fail(
                "editor_screening_checklist.json has stale Paper-JSS release "
                "pending-path count"
            )
        if (
            editor_summary.get("documented_nonblocking_risk_count")
            != len(expected_risk_ids)
        ):
            return _fail(
                "editor_screening_checklist.json has stale nonblocking-risk count"
            )
        if (
            editor_summary.get("documented_nonblocking_risk_ids")
            != expected_risk_ids
        ):
            return _fail(
                "editor_screening_checklist.json has stale nonblocking-risk ids"
            )
        risk_crosswalk = editor_by_id.get("nonblocking_risk_crosswalk", {})
        risk_metrics = risk_crosswalk.get("metrics", {})
        if (
            risk_metrics.get("risks_with_next_action_count")
            != len(expected_risk_ids)
        ):
            return _fail(
                "editor_screening_checklist.json reports nonblocking risks "
                "without next actions"
            )
        if risk_metrics.get("documented_nonblocking_risk_identity_ok") is not True:
            return _fail(
                "editor_screening_checklist.json reports nonblocking-risk "
                "identity drift"
            )
        if editor_summary.get("archive_evidence_paths_missing") not in (0, None):
            return _fail(
                "editor_screening_checklist.json reports missing archive "
                "evidence paths"
            )
        editor_checked_paths = editor_summary.get("archive_evidence_paths_checked")
        editor_resolved_paths = editor_summary.get("archive_evidence_paths_resolved")
        if (
            editor_checked_paths is not None
            and editor_resolved_paths is not None
            and editor_checked_paths != editor_resolved_paths
        ):
            return _fail(
                "editor_screening_checklist.json archive evidence path "
                "summary is stale"
            )
        if (
            editor_summary.get("archive_file_count")
            != risk_ledger_json.get("archive", {}).get("file_count")
        ):
            return _fail(
                "editor_screening_checklist.json archive count does not match "
                "submission risk ledger"
            )
        if (
            editor_summary.get("archive_size_mib")
            != risk_ledger_json.get("archive", {}).get("size_mib")
        ):
            return _fail(
                "editor_screening_checklist.json archive MiB size does not "
                "match submission risk ledger"
            )
        if (
            editor_summary.get("archive_size_mb_decimal")
            != risk_ledger_json.get("archive", {}).get("size_mb_decimal")
        ):
            return _fail(
                "editor_screening_checklist.json archive decimal MB size does "
                "not match submission risk ledger"
            )
        platform_item = editor_by_id.get("platform_dependency_boundary", {})
        platform_metrics = platform_item.get("metrics", {})
        if "replication/results/stata_rerun_protocol.md" not in platform_item.get(
            "primary_evidence", []
        ):
            return _fail(
                "platform-dependency editor item does not point to "
                "stata_rerun_protocol.md"
            )
        expected_platform_metrics = {
            "stata_rerun_protocol_status": "PASS",
            "stata_rerun_requires_license": True,
            "stata_rerun_upload_blocking": False,
            "stata_rerun_claimed_live_rerun": False,
            "stata_rerun_checklist_items": 8,
        }
        for key, expected in expected_platform_metrics.items():
            if platform_metrics.get(key) != expected:
                return _fail(
                    "editor_screening_checklist.json has stale Stata rerun "
                    f"metric {key}: {platform_metrics.get(key)!r}"
                )
        for snippet in (
            "Stata Tier-3 rerun protocol",
            "licensed optional rerun path",
            "without making missing Stata an upload blocker",
            "replication/results/stata_rerun_protocol.md",
            "- `stata_rerun_protocol_status`: `PASS`",
            "- `stata_rerun_requires_license`: `True`",
            "- `stata_rerun_upload_blocking`: `False`",
            "- `stata_rerun_claimed_live_rerun`: `False`",
        ):
            if snippet not in editor_map:
                return _fail(
                    f"editor_screening_checklist.md lacks {snippet!r}"
                )
        missing_editor_evidence = []
        for item in editor_json.get("items", []):
            item_id = item.get("id", "<missing-id>")
            for rel_path in item.get("primary_evidence", []):
                if rel_path.startswith("build/"):
                    continue
                if _resolve_reviewer_evidence_member(rel_path, names) is None:
                    missing_editor_evidence.append(f"{item_id}:{rel_path}")
        if missing_editor_evidence:
            return _fail(
                "editor_screening_checklist.json points outside the "
                "submission archive: " + ", ".join(missing_editor_evidence)
            )
        expected_editor_line = (
            "Editor screening checklist: PASS "
            f"(items={editor_summary.get('item_count')}; "
            f"pass_items={editor_summary.get('pass_items')}; "
            f"failed_items={editor_summary.get('failed_items')}; "
            f"upload_blockers={editor_summary.get('jss_upload_blockers')}; "
            f"archive_files={editor_summary.get('archive_file_count')})"
        )
        if expected_editor_line not in audit:
            return _fail(
                "jss_full_audit.md does not summarize the editor screening "
                "checklist"
            )
        if "Schema bundle check: PASS" not in audit:
            return _fail("jss_full_audit.md does not report a passing schema bundle check")
        if "Validation evidence audit: PASS" not in audit:
            return _fail(
                "jss_full_audit.md does not report a passing validation evidence audit"
            )
        if (
            "API-stable denominator:" not in audit
            or "class-like /" not in audit
            or "function-like auto-unbacked symbols" not in audit
            or "top categories=" not in audit
        ):
            return _fail(
                "jss_full_audit.md does not expose the API-stable denominator breakdown"
            )
        if "Methodological/T4 ledger: PASS" not in audit:
            return _fail("jss_full_audit.md does not report a passing methodological/T4 ledger")
        if (
            "non_circular_native_guards=1" not in audit
            or "non_circular_guard_failures=0" not in audit
        ):
            return _fail(
                "jss_full_audit.md does not expose non-circular native guards"
            )
        if (
            "reference_disagreement_guards=1" not in audit
            or "reference_disagreement_guard_failures=0" not in audit
        ):
            return _fail(
                "jss_full_audit.md does not expose SCM reference-disagreement guards"
            )
        if "Stata bridge audit: PASS" not in audit:
            return _fail("jss_full_audit.md does not report a passing Stata bridge audit")
        if (
            "Stata rerun protocol: PASS" not in audit
            or f"modules={EXPECTED_STATA_REPRO_MODULES}" not in audit
            or f"r_joined={EXPECTED_STATA_REPRO_MODULES}" not in audit
            or f"repro_report={EXPECTED_STATA_REPRO_MODULES}" not in audit
            or "non_reproduced=0" not in audit
            or "checklist_items=8" not in audit
            or "requires_license=True" not in audit
            or "claimed_live_rerun=False" not in audit
            or "upload_blocking=False" not in audit
        ):
            return _fail(
                "jss_full_audit.md does not report the Stata rerun protocol"
            )
        if "Agent interface audit: PASS" not in audit:
            return _fail(
                "jss_full_audit.md does not report a passing agent interface audit"
            )
        if (
            "Agent benchmark protocol: PASS" not in audit
            or "jss_upload_blocking=False" not in audit
            or "claimed_behavioural_result=False" not in audit
        ):
            return _fail(
                "jss_full_audit.md does not report the deferred agent benchmark protocol"
            )
        if "Release boundary audit: PASS" not in audit:
            return _fail(
                "jss_full_audit.md does not report a passing release boundary audit"
            )
        if "checked_files=8" not in audit:
            return _fail(
                "jss_full_audit.md does not report the JSS/JOSS release "
                "boundary audit scope"
            )
        house_style_md = _read_member(
            zf,
            "Paper-JSS/replication/results/jss_house_style_audit.md",
        )
        if "Status: PASS" not in house_style_md:
            return _fail("jss_house_style_audit.md inside archive is not PASS")
        house_style_json = _read_json_member(
            zf,
            "Paper-JSS/replication/results/jss_house_style_audit.json",
        )
        house_style_summary = house_style_json.get("summary", {})
        if house_style_json.get("status") != "PASS":
            return _fail("jss_house_style_audit.json status is not PASS")
        if house_style_summary.get("active_section_count") != 9:
            return _fail("jss_house_style_audit.json has stale active section count")
        if house_style_summary.get("draft_marker_hits") != 0:
            return _fail("jss_house_style_audit.json reports draft markers")
        if house_style_summary.get("marketing_claim_hits") != 0:
            return _fail("jss_house_style_audit.json reports marketing claims")
        if house_style_summary.get("overconfidence_claim_hits") != 0:
            return _fail(
                "jss_house_style_audit.json reports overconfident proof/guarantee wording"
            )
        if house_style_summary.get("defensive_tone_hits") != 0:
            return _fail(
                "jss_house_style_audit.json reports defensive or casual reviewer-facing phrasing"
            )
        if house_style_summary.get("anchor_failure_count") != 0:
            return _fail("jss_house_style_audit.json reports missing anchors")
        macro_counts = house_style_summary.get("macro_counts", {})
        if (
            macro_counts.get("proglang", 0) < 50
            or macro_counts.get("pkg", 0) < 80
            or macro_counts.get("code", 0) < 150
        ):
            return _fail("jss_house_style_audit.json reports weak JSS macro counts")
        if (
            "JSS house-style audit: PASS" not in audit
            or "draft_markers=0" not in audit
            or "marketing_hits=0" not in audit
            or "overconfidence_hits=0" not in audit
            or "defensive_tone_hits=0" not in audit
            or "anchor_failures=0" not in audit
        ):
            return _fail("jss_full_audit.md does not summarize the house-style audit")
        bibliography_md = _read_member(
            zf,
            "Paper-JSS/replication/results/bibliography_metadata_audit.md",
        )
        bibliography_json = _read_json_member(
            zf,
            "Paper-JSS/replication/results/bibliography_metadata_audit.json",
        )
        if "Status: PASS" not in bibliography_md:
            return _fail("bibliography_metadata_audit.md inside archive is not PASS")
        if bibliography_json.get("status") != "PASS":
            return _fail("bibliography_metadata_audit.json status is not PASS")
        # Asserted as an invariant, not as a literal. A hard-coded count
        # (it was 59) fails on every legitimate new citation and says
        # "stale" when the manuscript simply cites one more paper. What
        # must hold is that every key the active manuscript cites is in
        # the derived submission bib and resolves in the compiled
        # bibliography -- i.e. no "?" reaches the PDF.
        active_cited = bibliography_json.get("active_cited_key_count")
        if not isinstance(active_cited, int) or active_cited < 1:
            return _fail("bibliography metadata audit reports no active citations")
        # The audit reports this as a list of keys (older runs wrote a
        # count), so accept either shape and require it to be empty.
        missing_active = bibliography_json.get(
            "active_missing_from_submission_bib", []
        )
        missing_count = (
            len(missing_active)
            if isinstance(missing_active, (list, tuple))
            else int(missing_active or 0)
        )
        if missing_count:
            return _fail(
                "bibliography metadata audit reports active citations missing "
                f"from the derived submission bib: {missing_active}"
            )
        if bibliography_json.get("submission_bib_entry_count", 0) < active_cited:
            return _fail(
                "derived submission bib has fewer entries "
                f"({bibliography_json.get('submission_bib_entry_count')}) than "
                f"the active manuscript cites ({active_cited})"
            )
        # Invariants rather than literals, for the reason given above: the
        # derived submission bib is exactly the keys the active manuscript
        # cites plus the reserved keeps, and every entry either carries a
        # DOI or is registered in the no-DOI list with a manual reason.
        # The previous fixed 60/60/47 triple made "cite one more paper"
        # indistinguishable from "the bibliography pipeline broke".
        submission_entries = bibliography_json.get("submission_bib_entry_count")
        expected_entries = active_cited + len(EXPECTED_RESERVED_BIB_KEYS)
        if submission_entries != expected_entries:
            return _fail(
                f"derived submission bib has {submission_entries} entries but the "
                f"active manuscript cites {active_cited} keys plus "
                f"{len(EXPECTED_RESERVED_BIB_KEYS)} reserved keep(s)"
            )
        if not bibliography_json.get("archival_bib_entry_count"):
            return _fail("archival bib is empty; the long-form sections cite nothing")
        doi_entries = bibliography_json.get("doi_entry_count", 0)
        no_doi_entries_count = bibliography_json.get("no_doi_entry_count", 0)
        if doi_entries + no_doi_entries_count != submission_entries:
            return _fail(
                f"submission bib entries ({submission_entries}) is not the sum of "
                f"DOI-bearing ({doi_entries}) and registered no-DOI "
                f"({no_doi_entries_count}) entries"
            )
        if bibliography_json.get("active_missing_from_submission_bib"):
            return _fail("bibliography metadata audit reports missing active citations")
        if bibliography_json.get("active_archival_only_keys"):
            return _fail("bibliography metadata audit reports archival-only active keys")
        if bibliography_json.get("duplicate_keys"):
            return _fail("bibliography metadata audit reports duplicate keys")
        if bibliography_json.get("field_failures"):
            return _fail("bibliography metadata audit reports missing bib fields")
        if bibliography_json.get("reserved_entry_keys") != EXPECTED_RESERVED_BIB_KEYS:
            return _fail("bibliography metadata audit reserved key identity drift")
        no_doi_entries = bibliography_json.get("no_doi_entries", [])
        no_doi_keys = sorted(entry.get("key") for entry in no_doi_entries)
        if no_doi_keys != EXPECTED_NO_DOI_BIB_KEYS:
            return _fail("bibliography metadata audit no-DOI key identity drift")
        if bibliography_json.get("no_doi_entry_count") != len(EXPECTED_NO_DOI_BIB_KEYS):
            return _fail("bibliography metadata audit has stale no-DOI count")
        if bibliography_json.get("no_doi_manual_verification_count") != len(
            EXPECTED_NO_DOI_BIB_KEYS
        ):
            return _fail("bibliography metadata audit lost no-DOI manual reasons")
        if bibliography_json.get("missing_no_doi_reasons"):
            return _fail("bibliography metadata audit reports missing no-DOI reasons")
        compiled_bib = bibliography_json.get("compiled_bibliography", {})
        # Every cited key must print exactly one \bibitem, and nothing
        # else may: that is what rules out a "?" in the PDF and a
        # silently-carried unused entry alike.
        if compiled_bib.get("present") is True and (
            compiled_bib.get("bibitem_count") != active_cited
            or compiled_bib.get("thebibliography_count") != active_cited
        ):
            return _fail(
                "compiled bibliography has "
                f"{compiled_bib.get('bibitem_count')} entries but the active "
                f"manuscript cites {active_cited} keys"
            )
        for snippet in (
            f"Active cited keys: {active_cited}",
            f"Submission bibliography entries: {submission_entries}",
            "Reserved entries: 1 (brown2020language)",
            "No-DOI entries with manual reasons: 13/13",
            "`lalonde1986evaluating`",
        ):
            if snippet not in bibliography_md:
                return _fail(f"bibliography metadata audit lacks {snippet!r}")
        if (
            "Bibliography metadata audit: PASS" not in audit
            or f"active_cites={active_cited}" not in audit
            or f"bib_entries={submission_entries}" not in audit
            or "reserved=1" not in audit
            or f"doi_entries={doi_entries}" not in audit
            or (
                f"no_doi_manual={len(EXPECTED_NO_DOI_BIB_KEYS)}/"
                f"{len(EXPECTED_NO_DOI_BIB_KEYS)}"
            )
            not in audit
            or "missing=0" not in audit
            or "duplicates=0" not in audit
            or "field_failures=0" not in audit
        ):
            return _fail(
                "jss_full_audit.md does not summarize bibliography metadata audit"
            )
        if (
            "Reproduction environment audit: PASS" not in audit
            or (
                f"paper_readme_commands={len(PAPER_README_REVIEWER_COMMANDS)}"
                not in audit
            )
            or (
                "manuscript_readme_commands="
                f"{len(MANUSCRIPT_README_REVIEWER_COMMANDS)}"
                not in audit
            )
            or "requirements_version=True" not in audit
        ):
            return _fail(
                "jss_full_audit.md does not report a passing reproduction environment audit"
            )
        if (
            "PDF render audit: PASS" not in audit
            or "failures=0" not in audit
            or f"full_scan={reviewer_summary.get('pdf_pages')}/" not in audit
            or "full_failures=0" not in audit
        ):
            return _fail("jss_full_audit.md does not report a passing PDF render audit")
        if (
            "PDF visual check protocol: PASS" not in audit
            or f"pages={reviewer_summary.get('pdf_pages')}" not in audit
            or "checklist_items=12" not in audit
            or f"page_inventory={reviewer_summary.get('pdf_pages')}/" not in audit
            or f"manual_visual_check_status={MANUAL_VISUAL_SPOT_CHECK_STATUS}" not in audit
            or "claimed_manual_acceptance=False" not in audit
            or "jss_upload_blocking=False" not in audit
        ):
            return _fail(
                "jss_full_audit.md does not report the PDF visual-check protocol"
            )
        if (
            "tier1_no_r_stata=True" not in audit
            or "tier1_live_external=0" not in audit
        ):
            return _fail(
                "jss_full_audit.md does not expose the no-R/no-Stata Tier-1 "
                "headline path"
            )
        # Counts derived from the audit's own JSON rather than pinned as
        # literals: adding a table or a section is a normal manuscript
        # edit, and pinning 10/18/9 made every such edit report itself as
        # a provenance failure. The parts that must hold regardless are
        # the zero-valued ones -- no hash mismatch, no missing or dangling
        # cross-reference, no section without its anchors.
        artifact_json = _read_json_member(
            zf,
            "Paper-JSS/replication/results/manuscript_artifact_audit.json",
        )
        artifact_counts = {
            "artifacts": artifact_json.get("artifact_count"),
            "float_labels": len(artifact_json.get("active_float_labels") or []),
            "narrative_refs": len(artifact_json.get("narrative_float_refs") or []),
            "compact_sections": (artifact_json.get("compact_section_coverage") or {}).get(
                "sections_checked"
            ),
            "compact_coverage": (artifact_json.get("compact_section_coverage") or {}).get(
                "sections_passed"
            ),
        }
        if (
            "Manuscript artifact audit: PASS" not in audit
            or "hash_mismatches=0" not in audit
            or "missing_refs=0" not in audit
            or "dangling_refs=0" not in audit
            or "compact_missing_anchors=0" not in audit
            or any(
                value is not None and f"{name}={value}" not in audit
                for name, value in artifact_counts.items()
            )
        ):
            return _fail(
                "jss_full_audit.md does not report passing manuscript artifact provenance"
            )
        if (
            "JSS formal compliance audit: PASS" not in audit
            or "checks=23" not in audit
            or "passed=23" not in audit
            or "pending=0" not in audit
            or "archive=True" not in audit
            or "official_sources_checked=2026-08-09" not in audit
        ):
            return _fail(
                "jss_full_audit.md has stale JSS formal compliance summary"
            )
        if "unseeded_rng=0" not in audit:
            return _fail(
                "jss_full_audit.md does not expose seeded stochastic "
                "reproduction status"
            )
        full_audit_json = _read_json_member(
            zf,
            "Paper-JSS/replication/results/jss_full_audit.json",
        )
        if full_audit_json.get("status") != "PASS":
            return _fail("jss_full_audit.json lacks top-level PASS status")
        full_submission_package = (
            full_audit_json.get("summary", {}).get("submission_package", {})
        )
        full_audit_size_bytes = full_submission_package.get("size_bytes")
        if not isinstance(full_audit_size_bytes, int) or full_audit_size_bytes <= 0:
            return _fail(
                "jss_full_audit.json summary.submission_package.size_bytes is "
                "not a positive integer"
            )
        if abs(full_audit_size_bytes - archive_size_bytes) > 16 * 1024:
            return _fail(
                "jss_full_audit.json summary.submission_package.size_bytes is "
                "stale relative to final archive bytes"
            )
        full_commands = full_audit_json.get("commands", {})
        full_ledger_command = full_commands.get("submission_risk_ledger")
        if (
            not isinstance(full_ledger_command, dict)
            or full_ledger_command.get("returncode") != 0
        ):
            return _fail(
                "jss_full_audit.json does not record a passing upload-ledger refresh"
            )
        full_reviewer_map_command = full_commands.get("reviewer_evidence_map")
        if (
            not isinstance(full_reviewer_map_command, dict)
            or full_reviewer_map_command.get("returncode") != 0
        ):
            return _fail(
                "jss_full_audit.json does not record a passing reviewer-map refresh"
            )
        full_pdf_render_command = full_commands.get("pdf_render_audit")
        if (
            not isinstance(full_pdf_render_command, dict)
            or full_pdf_render_command.get("returncode") != 0
        ):
            return _fail(
                "jss_full_audit.json does not record a passing PDF render audit"
            )
        full_pdf_visual_command = full_commands.get("pdf_visual_check_protocol")
        if (
            not isinstance(full_pdf_visual_command, dict)
            or full_pdf_visual_command.get("returncode") != 0
        ):
            return _fail(
                "jss_full_audit.json does not record a passing PDF visual protocol"
            )
        full_stata_protocol_command = full_commands.get("stata_rerun_protocol")
        if (
            not isinstance(full_stata_protocol_command, dict)
            or full_stata_protocol_command.get("returncode") != 0
        ):
            return _fail(
                "jss_full_audit.json does not record a passing Stata rerun "
                "protocol"
            )
        full_house_style_command = full_commands.get("jss_house_style_audit")
        if (
            not isinstance(full_house_style_command, dict)
            or full_house_style_command.get("returncode") != 0
        ):
            return _fail(
                "jss_full_audit.json does not record a passing house-style audit"
            )
        full_bibliography_command = full_commands.get("bibliography_metadata_audit")
        if (
            not isinstance(full_bibliography_command, dict)
            or full_bibliography_command.get("returncode") != 0
        ):
            return _fail(
                "jss_full_audit.json does not record a passing bibliography "
                "metadata audit"
            )
        full_data_provenance_command = full_commands.get("data_provenance_audit")
        if (
            not isinstance(full_data_provenance_command, dict)
            or full_data_provenance_command.get("returncode") != 0
        ):
            return _fail(
                "jss_full_audit.json does not record a passing data provenance audit"
            )
        full_editor_command = full_commands.get("editor_screening_checklist")
        if (
            not isinstance(full_editor_command, dict)
            or full_editor_command.get("returncode") != 0
        ):
            return _fail(
                "jss_full_audit.json does not record a passing editor "
                "screening refresh"
            )
        expected_full_audit_scalars = {
            "package_size_mib": archive_size_mib,
            "package_size_mb_decimal": archive_size_mb_decimal,
            "package_file_count": file_count,
            "final_publication_gate_ready": (
                manifest.get("source_snapshot", {}) or {}
            ).get("ready_for_final_publication"),
            "gate_blocker_paths": manifest_blockers,
        }
        for key, expected in expected_full_audit_scalars.items():
            if full_audit_json.get(key) != expected:
                return _fail(
                    f"jss_full_audit.json top-level {key} does not match "
                    "submission manifest"
                )
        full_summary = full_audit_json.get("summary", {})
        full_bibliography_summary = full_summary.get("bibliography_metadata", {})
        # Mirrors the standalone audit rather than repeating literals: the
        # counts move whenever the manuscript cites one more paper, and
        # this check exists to catch the rollup disagreeing with the audit
        # it summarises, not to freeze the bibliography's size.
        expected_full_bibliography_summary = {
            "status": "PASS",
            "active_cited_key_count": active_cited,
            "submission_bib_entry_count": submission_entries,
            "archival_bib_entry_count": bibliography_json.get(
                "archival_bib_entry_count"
            ),
            "doi_entry_count": doi_entries,
            "reserved_entry_count": len(EXPECTED_RESERVED_BIB_KEYS),
            "no_doi_entry_count": len(EXPECTED_NO_DOI_BIB_KEYS),
            "no_doi_manual_verification_count": len(EXPECTED_NO_DOI_BIB_KEYS),
            "active_missing_from_submission_bib": 0,
            "duplicate_keys": 0,
            "field_failures": 0,
        }
        for key, expected in expected_full_bibliography_summary.items():
            if full_bibliography_summary.get(key) != expected:
                return _fail(
                    "jss_full_audit.json has stale bibliography metadata "
                    f"summary for {key}: {full_bibliography_summary.get(key)}"
                )
        full_data_provenance_summary = full_summary.get("data_provenance", {})
        expected_full_data_provenance_summary = {
            "status": "PASS",
            "packaged_public_dataset_csv_count": 9,
            "public_original_extract_csv_count": 7,
            "same_byte_r_stata_fixture_csv_count": EXPECTED_R_STATA_FIXTURE_CSV_COUNT,
            "forbidden_raw_member_count": 0,
            "high_risk_path_hit_count": 0,
            "csv_parse_failure_count": 0,
            "unknown_category_count": 0,
        }
        for key, expected in expected_full_data_provenance_summary.items():
            if full_data_provenance_summary.get(key) != expected:
                return _fail(
                    "jss_full_audit.json has stale data provenance summary "
                    f"{key}: {full_data_provenance_summary.get(key)!r}"
                )
        full_stata_protocol_summary = full_summary.get("stata_rerun_protocol", {})
        expected_full_stata_protocol_summary = {
            "status": "PASS",
            "stata_modules": EXPECTED_STATA_REPRO_MODULES,
            "r_joined_stata_modules": EXPECTED_STATA_REPRO_MODULES,
            "repro_report_modules": EXPECTED_STATA_REPRO_MODULES,
            "reproduced_report_rows": EXPECTED_STATA_REPRO_MODULES,
            "non_reproduced_report_rows": 0,
            "checklist_item_count": 8,
            "command_count": 4,
            "requires_stata_license": True,
            "jss_upload_blocking": False,
            "absence_of_stata_is_optional_skip": True,
            "claimed_current_machine_live_rerun": False,
            "no_section_4_7_headline_depends_on_live_stata": True,
        }
        for key, expected in expected_full_stata_protocol_summary.items():
            if full_stata_protocol_summary.get(key) != expected:
                return _fail(
                    "jss_full_audit.json has stale Stata rerun protocol "
                    f"summary {key}: {full_stata_protocol_summary.get(key)!r}"
                )
        full_reproduction_environment = full_summary.get(
            "reproduction_environment", {}
        )
        if (
            full_reproduction_environment.get("tier1_transcript_no_r_stata")
            is not True
            or full_reproduction_environment.get("tier1_live_external_call_count")
            != 0
        ):
            return _fail(
                "jss_full_audit.json does not expose a no-R/no-Stata Tier-1 "
                "headline path"
            )

        main_tex = _strip_comments(_read_member(zf, "Paper-JSS/manuscript/main.tex"))
        main_pdf = _read_binary_member(zf, "Paper-JSS/manuscript/main.pdf")
        try:
            manuscript_page_count = _pdf_page_count(main_pdf)
            manuscript_pdf_text = _pdf_text(main_pdf)
        except RuntimeError as exc:
            return _fail(str(exc))
        if manuscript_page_count <= 0:
            return _fail("main.pdf page count could not be determined")
        if manuscript_page_count > 52:
            return _fail(
                f"main.pdf is {manuscript_page_count} pages, above the "
                "local conservative 52-page screening ceiling"
            )
        expected_formal_audit_summary = (
            "JSS formal compliance audit: PASS "
            "(checks=23; passed=23; pending=0; archive=True; "
            f"pages={manuscript_page_count}; "
            "official_sources_checked=2026-08-09)"
        )
        if expected_formal_audit_summary not in audit:
            return _fail(
                "jss_full_audit.md formal-compliance page/count summary "
                "is stale"
            )
        fixed_pdf_date = b"D:20260531000000Z"
        if (
            b"/CreationDate (" + fixed_pdf_date + b")" not in main_pdf
            or b"/ModDate (" + fixed_pdf_date + b")" not in main_pdf
        ):
            return _fail(
                "main.pdf does not use the fixed SOURCE_DATE_EPOCH "
                "timestamp"
            )
        missing_pdf_boundary_snippets = [
            snippet for snippet in PDF_BOUNDARY_SNIPPETS
            if not _has_snippet(manuscript_pdf_text, snippet)
        ]
        if missing_pdf_boundary_snippets:
            return _fail(
                "main.pdf lacks reviewer-visible boundary snippets: "
                + ", ".join(missing_pdf_boundary_snippets)
            )
        stale_pdf_prose_hits = [
            snippet for snippet in PDF_STALE_PROSE_SNIPPETS
            if _has_snippet(manuscript_pdf_text, snippet)
        ]
        if stale_pdf_prose_hits:
            return _fail(
                "main.pdf contains stale defensive manuscript prose: "
                + ", ".join(stale_pdf_prose_hits)
            )
        pdf_render_md = _read_member(
            zf,
            "Paper-JSS/replication/results/pdf_render_audit.md",
        )
        pdf_render_json = _read_json_member(
            zf,
            "Paper-JSS/replication/results/pdf_render_audit.json",
        )
        pdf_render_summary = pdf_render_json.get("summary", {})
        manual_visual = pdf_render_json.get("manual_preupload_visual_check", {})
        expected_render_pages = _expected_pdf_render_pages(manuscript_page_count)
        if "Status: PASS" not in pdf_render_md:
            return _fail("pdf_render_audit.md inside archive is not PASS")
        if pdf_render_json.get("status") != "PASS":
            return _fail("pdf_render_audit.json status is not PASS")
        if pdf_render_summary.get("page_count") != manuscript_page_count:
            return _fail("pdf_render_audit page count does not match main.pdf")
        if pdf_render_summary.get("sampled_pages") != expected_render_pages:
            return _fail("pdf_render_audit sampled page identity drift")
        if pdf_render_summary.get("rendered_page_count") != len(expected_render_pages):
            return _fail("pdf_render_audit did not render every expected sample page")
        if pdf_render_summary.get("failure_count") != 0:
            return _fail("pdf_render_audit reports failures")
        if (
            pdf_render_summary.get("full_document_rendered_page_count")
            != manuscript_page_count
        ):
            return _fail("pdf_render_audit did not scan every PDF page")
        if pdf_render_summary.get("full_document_failure_count") != 0:
            return _fail("pdf_render_audit reports full-document render failures")
        renderer = pdf_render_json.get("renderer", {})
        if renderer.get("name") != "pdftoppm" or not renderer.get("path"):
            return _fail("pdf_render_audit does not record the Poppler renderer")
        if pdf_render_json.get("dpi", 0) < 100:
            return _fail("pdf_render_audit uses too low a rendering DPI")
        if pdf_render_summary.get("min_width", 0) < 600:
            return _fail("pdf_render_audit reports implausibly narrow renders")
        if pdf_render_summary.get("min_height", 0) < 800:
            return _fail("pdf_render_audit reports implausibly short renders")
        if pdf_render_summary.get("min_ink_ratio", 0) <= 0.004:
            return _fail("pdf_render_audit reports blank-looking renders")
        if pdf_render_summary.get("max_dark_ratio", 1) >= 0.55:
            return _fail("pdf_render_audit reports overwhelmingly dark renders")
        if pdf_render_summary.get("max_white_ratio", 1) >= 0.995:
            return _fail("pdf_render_audit reports nearly blank renders")
        if pdf_render_summary.get("full_document_min_width", 0) < 600:
            return _fail(
                "pdf_render_audit reports implausibly narrow full-document renders"
            )
        if pdf_render_summary.get("full_document_min_height", 0) < 800:
            return _fail(
                "pdf_render_audit reports implausibly short full-document renders"
            )
        if pdf_render_summary.get("full_document_min_ink_ratio", 0) <= 0.004:
            return _fail("pdf_render_audit reports blank-looking full-document renders")
        if pdf_render_summary.get("full_document_max_dark_ratio", 1) >= 0.55:
            return _fail(
                "pdf_render_audit reports overwhelmingly dark full-document renders"
            )
        if pdf_render_summary.get("full_document_max_white_ratio", 1) >= 0.995:
            return _fail("pdf_render_audit reports nearly blank full-document renders")
        rendered_pages = [page.get("page") for page in pdf_render_json.get("pages", [])]
        if rendered_pages != expected_render_pages:
            return _fail("pdf_render_audit page rows do not match expected samples")
        if any(page.get("ok") is not True for page in pdf_render_json.get("pages", [])):
            return _fail("pdf_render_audit contains a non-passing page row")
        full_document_pages = pdf_render_json.get("full_document_pages", [])
        if [page.get("page") for page in full_document_pages] != list(
            range(1, manuscript_page_count + 1)
        ):
            return _fail("pdf_render_audit full-document page rows are incomplete")
        if any(page.get("ok") is not True for page in full_document_pages):
            return _fail(
                "pdf_render_audit contains a non-passing full-document page row"
            )
        if manual_visual.get("required") is not True:
            return _fail("pdf_render_audit lost the manual visual-check requirement")
        if manual_visual.get("recorded_by_this_audit") is not False:
            return _fail("pdf_render_audit falsely records a human visual check")
        if (
            manual_visual.get("status") != MANUAL_VISUAL_SPOT_CHECK_STATUS
            or pdf_render_summary.get("manual_visual_spot_check_status")
            != MANUAL_VISUAL_SPOT_CHECK_STATUS
        ):
            return _fail("pdf_render_audit has stale manual visual-check status")
        if (
            manual_visual.get("machine_render_not_human_review") is not True
            or pdf_render_summary.get("machine_render_not_human_review") is not True
        ):
            return _fail("pdf_render_audit conflates machine render with human review")
        for snippet in (
            f"PDF pages: {manuscript_page_count}",
            "Sampled pages: " + ", ".join(str(page) for page in expected_render_pages),
            f"Rendered pages: {len(expected_render_pages)}",
            f"Full-document machine scan: {manuscript_page_count}/{manuscript_page_count} pages; failures=0",
            f"Manual pre-upload visual check: {MANUAL_VISUAL_SPOT_CHECK_STATUS}",
            "does not certify the final full-document human visual spot-check",
            "Failures: none",
        ):
            if snippet not in pdf_render_md:
                return _fail(f"pdf_render_audit.md lacks {snippet!r}")
        pdf_visual_md = _read_member(
            zf,
            "Paper-JSS/replication/results/pdf_visual_check_protocol.md",
        )
        pdf_visual_json = _read_json_member(
            zf,
            "Paper-JSS/replication/results/pdf_visual_check_protocol.json",
        )
        pdf_visual_summary = pdf_visual_json.get("summary", {})
        pdf_visual_boundary = pdf_visual_json.get("boundary", {})
        if "Status: PASS" not in pdf_visual_md:
            return _fail("pdf_visual_check_protocol.md inside archive is not PASS")
        if pdf_visual_json.get("status") != "PASS":
            return _fail("pdf_visual_check_protocol.json status is not PASS")
        if pdf_visual_json.get("main_pdf") != "manuscript/main.pdf":
            return _fail("pdf_visual_check_protocol points to the wrong PDF")
        if (
            pdf_visual_json.get("pdf_render_audit")
            != "replication/results/pdf_render_audit.json"
        ):
            return _fail("pdf_visual_check_protocol points to the wrong render audit")
        if pdf_visual_summary.get("page_count") != manuscript_page_count:
            return _fail("pdf_visual_check_protocol page count does not match main.pdf")
        if pdf_visual_summary.get("sampled_pages") != expected_render_pages:
            return _fail("pdf_visual_check_protocol sampled-page identity drift")
        if pdf_visual_summary.get("pdf_render_status") != "PASS":
            return _fail("pdf_visual_check_protocol does not read a passing render audit")
        if pdf_visual_summary.get("pdf_render_failure_count") != 0:
            return _fail("pdf_visual_check_protocol reports render failures")
        if (
            pdf_visual_summary.get("full_document_machine_scan_pages")
            != manuscript_page_count
        ):
            return _fail(
                "pdf_visual_check_protocol has stale full-document scan page count"
            )
        if pdf_visual_summary.get("full_document_machine_scan_failures") != 0:
            return _fail(
                "pdf_visual_check_protocol reports full-document scan failures"
            )
        if (
            pdf_visual_summary.get("full_document_machine_scan_not_human_review")
            is not True
        ):
            return _fail(
                "pdf_visual_check_protocol conflates full scan with human review"
            )
        checklist = pdf_visual_json.get("checklist", [])
        if len(checklist) != pdf_visual_summary.get("checklist_item_count"):
            return _fail("pdf_visual_check_protocol checklist count is stale")
        if len(checklist) < 10:
            return _fail("pdf_visual_check_protocol checklist is too thin")
        checklist_ids = [item.get("id") for item in checklist]
        for item_id in (
            "open_packaged_pdf",
            "page_count_matches_audits",
            "archive_manifest_crosscheck",
            "use_page_inventory",
            "all_pages_nonblank",
            "front_matter_and_metadata",
            "text_and_equation_layout",
            "tables_figures_captions",
            "links_references_citations",
            "boundary_text_visible",
            "compare_machine_samples",
            "record_human_acceptance",
        ):
            if item_id not in checklist_ids:
                return _fail(
                    "pdf_visual_check_protocol lacks checklist item "
                    f"{item_id!r}"
                )
        inventory_items = [
            item for item in checklist if item.get("id") == "use_page_inventory"
        ]
        if len(inventory_items) != 1:
            return _fail("pdf_visual_check_protocol lacks one inventory item")
        inventory_action = inventory_items[0].get("action", "")
        for snippet in ("generated page inventory", "section starts", "references"):
            if snippet not in inventory_action:
                return _fail(
                    "pdf_visual_check_protocol inventory item lacks "
                    f"{snippet!r}"
                )
        archive_items = [
            item for item in checklist if item.get("id") == "archive_manifest_crosscheck"
        ]
        if len(archive_items) != 1:
            return _fail("pdf_visual_check_protocol lacks one archive-manifest item")
        archive_action = archive_items[0].get("action", "")
        for snippet in (
            "build/statspai-jss-submission.zip",
            "build/statspai-jss-submission-manifest.md",
            "Paper-JSS/manuscript/main.pdf",
            "archive size and file count",
        ):
            if snippet not in archive_action:
                return _fail(
                    "pdf_visual_check_protocol archive item lacks "
                    f"{snippet!r}"
                )
        boundary_items = [
            item for item in checklist if item.get("id") == "boundary_text_visible"
        ]
        if len(boundary_items) != 1:
            return _fail("pdf_visual_check_protocol lacks one boundary-text item")
        boundary_action = boundary_items[0].get("action", "")
        for snippet in (
            "validation-tier",
            "source-snapshot",
            "data-provenance",
            "agent-claim",
            "final manual PDF visual-check",
        ):
            if snippet not in boundary_action:
                return _fail(
                    "pdf_visual_check_protocol boundary item lacks "
                    f"{snippet!r}"
                )
        for key in (
            "manual_visual_check_required",
            "manual_action_required_before_upload",
            "machine_render_not_human_review",
        ):
            if pdf_visual_boundary.get(key) is not True:
                return _fail(f"pdf_visual_check_protocol has stale boundary {key}")
            if pdf_visual_summary.get(key) is not True:
                return _fail(f"pdf_visual_check_protocol has stale summary {key}")
        if (
            pdf_visual_boundary.get("manual_visual_check_status")
            != MANUAL_VISUAL_SPOT_CHECK_STATUS
            or pdf_visual_summary.get("manual_visual_check_status")
            != MANUAL_VISUAL_SPOT_CHECK_STATUS
        ):
            return _fail("pdf_visual_check_protocol has stale manual status")
        for key in ("claimed_manual_acceptance", "recorded_by_this_protocol"):
            if pdf_visual_boundary.get(key) is not False:
                return _fail(f"pdf_visual_check_protocol falsely sets boundary {key}")
            if pdf_visual_summary.get(key) is not False:
                return _fail(f"pdf_visual_check_protocol falsely sets summary {key}")
        if (
            pdf_visual_boundary.get("jss_upload_blocking") is not False
            or pdf_visual_summary.get("jss_upload_blocking") is not False
        ):
            return _fail("pdf_visual_check_protocol is incorrectly upload-blocking")
        for key, expected in (
            ("archive_name", "build/statspai-jss-submission.zip"),
            ("archive_manifest", "build/statspai-jss-submission-manifest.md"),
            ("packaged_pdf_member", "Paper-JSS/manuscript/main.pdf"),
        ):
            if pdf_visual_boundary.get(key) != expected:
                return _fail(
                    "pdf_visual_check_protocol has stale archive boundary "
                    f"{key}"
                )
            if pdf_visual_summary.get(key) != expected:
                return _fail(
                    "pdf_visual_check_protocol has stale archive summary "
                    f"{key}"
                )
        page_inventory = pdf_visual_json.get("page_inventory", [])
        if len(page_inventory) != manuscript_page_count:
            return _fail("pdf_visual_check_protocol page inventory is incomplete")
        if [row.get("page") for row in page_inventory] != list(
            range(1, manuscript_page_count + 1)
        ):
            return _fail("pdf_visual_check_protocol page inventory order drifted")
        if pdf_visual_summary.get("page_inventory_count") != manuscript_page_count:
            return _fail("pdf_visual_check_protocol summary has stale inventory count")
        if pdf_visual_summary.get("page_inventory_text_pages") != manuscript_page_count:
            return _fail("pdf_visual_check_protocol reports text-sparse pages")
        if pdf_visual_summary.get("page_inventory_min_text_chars", 0) <= 50:
            return _fail("pdf_visual_check_protocol reports too little page text")
        expected_inventory_markers = {
            "front_matter",
            "introduction",
            "software_architecture",
            "agent_registry_api",
            "worked_examples",
            "validation_evidence",
            "performance",
            "agent_interface_checks",
            "computational_details",
            "discussion",
            "references",
        }
        observed_inventory_markers = set(
            pdf_visual_summary.get("page_inventory_section_markers", [])
        )
        if not expected_inventory_markers.issubset(observed_inventory_markers):
            return _fail(
                "pdf_visual_check_protocol inventory missing section markers: "
                + ", ".join(sorted(expected_inventory_markers - observed_inventory_markers))
            )
        if pdf_visual_summary.get("page_inventory_float_marker_count", 0) < 16:
            return _fail("pdf_visual_check_protocol sees too few table/figure markers")
        if any(row.get("text_chars", 0) <= 50 for row in page_inventory):
            return _fail("pdf_visual_check_protocol has a text-sparse page row")
        for snippet in (
            f"PDF pages: `{manuscript_page_count}`",
            "Manual visual check status: `PENDING_MANUAL_REVIEW`",
            "Expected archive: `build/statspai-jss-submission.zip`",
            "Expected archive manifest: `build/statspai-jss-submission-manifest.md`",
            "Packaged PDF member: `Paper-JSS/manuscript/main.pdf`",
            f"Full-document machine scan pages: `{manuscript_page_count}`",
            "Full-document machine scan failures: `0`",
            "Full-document machine scan is not human review: `True`",
            "Claimed manual acceptance: `False`",
            "Recorded by this protocol: `False`",
            "Manual action required before upload: `True`",
            "Machine render is not human review: `True`",
            "JSS upload blocking: `False`",
            "validation-tier, source-snapshot, data-provenance",
            "agent-claim, and final manual PDF visual-check boundary wording",
            "## Page Inventory",
            "`page_inventory_count`",
            "`archive_manifest_crosscheck`",
            "`use_page_inventory`",
            "front_matter",
            "references",
            "final full-document human visual spot-check",
            "does not certify that a human visual review has already been completed",
            "Failures: none",
        ):
            if snippet not in pdf_visual_md:
                return _fail(f"pdf_visual_check_protocol.md lacks {snippet!r}")
        if r"\documentclass[article]{jss}" not in main_tex:
            return _fail("main.tex does not use submission-facing JSS article class")
        if r"\documentclass[article,nojss]{jss}" in main_tex:
            return _fail("main.tex uses nojss vignette mode")
        missing_front_matter = [
            name for name in REQUIRED_JSS_FRONT_MATTER
            if not _has_nonempty_macro(main_tex, name)
        ]
        if missing_front_matter:
            return _fail(
                "main.tex is missing JSS front-matter macros: "
                + ", ".join(f"\\{name}" for name in missing_front_matter)
            )
        if not re.search(r"\\bibliography\s*\{\s*jss-bib\s*\}", main_tex):
            return _fail("main.tex does not include \\bibliography{jss-bib}")
        section_members = {
            name for name in names
            if name.startswith("Paper-JSS/manuscript/sections/")
            and name.endswith(".tex")
        }
        if section_members != ACTIVE_MANUSCRIPT_SECTION_MEMBERS:
            extra = sorted(section_members - ACTIVE_MANUSCRIPT_SECTION_MEMBERS)
            missing_active = sorted(ACTIVE_MANUSCRIPT_SECTION_MEMBERS - section_members)
            return _fail(
                "archive manuscript sections do not match active main.tex inputs; "
                f"extra={extra[:12]}, missing={missing_active[:12]}"
            )
        input_sections = {
            f"Paper-JSS/manuscript/{match}"
            for match in re.findall(r"\\input\{(sections/[^}]+\.tex)\}", main_tex)
        }
        if input_sections != ACTIVE_MANUSCRIPT_SECTION_MEMBERS:
            extra = sorted(input_sections - ACTIVE_MANUSCRIPT_SECTION_MEMBERS)
            missing_active = sorted(ACTIVE_MANUSCRIPT_SECTION_MEMBERS - input_sections)
            return _fail(
                "main.tex active section inputs do not match verifier allow-list; "
                f"extra={extra[:12]}, missing={missing_active[:12]}"
            )
        comp_details = _read_member(
            zf,
            "Paper-JSS/manuscript/sections/08-computational-details-compact.tex",
        )
        if "JSS one-hour threshold" not in comp_details:
            return _fail(
                "computational details do not frame Tier-1 timing against "
                "the JSS one-hour threshold"
            )
        if "are the acceptance evidence, and\neach is regenerated rather than quoted" not in comp_details:
            return _fail(
                "computational details do not separate broad pytest sweeps "
                "from the JSS reviewer evidence contract"
            )
        if re.search(r"Tier~?1 steps passing in \d+(?:\.\d+)? minutes", comp_details):
            return _fail(
                "computational details pin a machine-specific Tier-1 minute count"
            )
        for stale_test_total in (
            "5,424 passed",
            "44 skipped",
            "13 deselected",
            "1 expected failure in 20 minutes",
        ):
            if stale_test_total in comp_details:
                return _fail(
                    "computational details pin a brittle historical pytest total: "
                    + stale_test_total
                )
        active_manuscript = "\n".join(
            _strip_comments(_read_member(zf, member))
            for member in sorted(ACTIVE_MANUSCRIPT_SECTION_MEMBERS)
        )
        # Track-B rates are generated into an active nested table input rather
        # than copied into the section prose. Include that rendered source in
        # the package-level drift check.
        active_manuscript += "\n" + _strip_comments(
            _read_member(
                zf,
                "Paper-JSS/manuscript/tables/track_b_monte_carlo.tex",
            )
        )
        for snippet in ACTIVE_COMPARATIVE_SCOPE_SNIPPETS:
            if not _has_snippet(active_manuscript, snippet):
                message = (
                    "active manuscript lacks reviewer-facing comparative scope evidence"
                )
                return _fail(f"{message}: {snippet!r}")
        for snippet in ACTIVE_SOURCE_SNAPSHOT_SCOPE_SNIPPETS:
            if not _has_snippet(active_manuscript, snippet):
                message = (
                    "active manuscript lacks reviewer-facing source-snapshot "
                    "boundary evidence"
                )
                return _fail(f"{message}: {snippet!r}")
        track_b_nominal = _read_json_member(
            zf,
            "tests/coverage_monte_carlo/results_b1000/coverage_b1000.json",
        )
        if len(track_b_nominal) != 12:
            return _fail(
                "Track B B=1000 nominal artifact count is not twelve rows"
            )
        if "twelve \\(B=1{,}000\\) rows" not in active_manuscript:
            return _fail(
                "active manuscript does not state the twelve-row Track B "
                "B=1000 artifact boundary"
            )
        for row in track_b_nominal:
            rate = row.get("rate")
            draws = row.get("B")
            if draws != 1000:
                return _fail(
                    "Track B nominal artifact row does not use B=1000: "
                    f"{row.get('name')}"
                )
            if f"{rate:.3f}" not in active_manuscript:
                return _fail(
                    "active manuscript does not report Track B nominal "
                    f"artifact rate {rate:.3f} for {row.get('name')}"
                )
        for stale_track_b_claim in (
            "three " "cheap",
            "three" "-row",
            "materialized " "three",
            "B=200 cap",
        ):
            if stale_track_b_claim in active_manuscript:
                return _fail(
                    "active manuscript contains stale Track B artifact "
                    f"boundary: {stale_track_b_claim}"
                )

        claim_lint = _read_member(zf, "Paper-JSS/replication/results/claim_lint.md")
        if "Status: PASS" not in claim_lint:
            return _fail("claim_lint.md inside archive is not PASS")
        if "Historical drift files: 10" not in claim_lint:
            return _fail("claim_lint.md does not report historical drift scope")
        if "Dynamic counts:" not in claim_lint:
            return _fail("claim_lint.md does not report dynamic validation counts")
        claim_lint_json = _read_json_member(
            zf,
            "Paper-JSS/replication/results/claim_lint.json",
        )
        historical_claim_files = set(claim_lint_json.get("historical_drift_files", []))
        if len(historical_claim_files) != 10:
            return _fail("claim_lint.json has unexpected historical drift scope")
        for historical_file in (
            "Paper-JSS/JSS-research-plan.md",
            "Paper-JSS/NEXT-STEPS.md",
        ):
            if historical_file not in historical_claim_files:
                return _fail(
                    "claim_lint.json does not include excluded planning note "
                    f"{historical_file}"
                )
        claim_counts = claim_lint_json.get("claim_counts", {})
        stability = full_summary.get("stability", {})
        evidence_paths = full_summary.get("stability_evidence_paths", {})
        validation_summary = full_summary.get("validation_evidence", {})
        agent_summary = full_summary.get("agent_interface", {})
        expected_claim_counts = {
            "registry": agent_summary.get("public_surface"),
            "certified_validated": validation_summary.get(
                "certified_validated_symbols"
            ),
            "unbacked_auto": stability.get("unbacked_auto"),
            "unbacked_handwritten": stability.get("unbacked_handwritten"),
            "registry_evidence_unique": evidence_paths.get("unique"),
        }
        for key, expected in expected_claim_counts.items():
            if claim_counts.get(key) != expected:
                return _fail(
                    "claim_lint.json dynamic counts do not match "
                    f"jss_full_audit for {key}: "
                    f"{claim_counts.get(key)!r} != {expected!r}"
                )
        status_count_keys = ("certified", "validated", "api_stable", "experimental")
        if any(not isinstance(claim_counts.get(key), int) for key in status_count_keys):
            return _fail("claim_lint.json lacks integer validation-status tier counts")
        if sum(claim_counts[key] for key in status_count_keys) != claim_counts.get("registry"):
            return _fail("claim_lint.json validation-status tier counts do not sum to registry")
        if (
            claim_counts["certified"] + claim_counts["validated"]
            != claim_counts.get("certified_validated")
        ):
            return _fail(
                "claim_lint.json certified + validated does not equal "
                "certified_validated"
            )
        if (
            claim_counts.get("registry_evidence_unique")
            != manifest.get("registry_evidence_file_count")
        ):
            return _fail(
                "claim_lint.json registry evidence count does not match "
                "submission manifest"
            )

        cover_letter = _read_member(zf, "Paper-JSS/cover-letter.md")
        for snippet in (
            "Date placeholder",
            "placeholder editor",
            "Replace placeholder",
            "GPU placeholder notebook",
            "placeholder notebook",
            "Draft prepared",
            "JOSS paper paper",
        ):
            if snippet.lower() in cover_letter.lower():
                return _fail(f"cover letter still contains stale text: {snippet}")
        if not re.search(
            r"(?m)^(?:January|February|March|April|May|June|July|August|"
            r"September|October|November|December) [0-9]{1,2}, 2026$",
            cover_letter,
        ):
            return _fail("cover letter lacks a complete 2026 submission date")
        if "MIT licence, which is GPL-compatible" not in cover_letter:
            return _fail("cover letter lacks GPL-compatible license disclosure")
        if (
            "every Section 4--7 headline number was" not in cover_letter
            or "rebuilt without R or Stata" not in cover_letter
        ):
            return _fail(
                "cover letter does not disclose the no-R/no-Stata Tier-1 "
                "headline path"
            )
        if "mechanical and contractual framing" not in cover_letter:
            return _fail(
                "cover letter lacks contractual agent-interface framing"
            )
        cover_norm = re.sub(r"\s+", " ", cover_letter)
        if (
            "final full-document visual spot-check remains an upload-time manual action"
            not in cover_norm
            or "rather than a machine-verified PASS" not in cover_norm
            or "representative PDF pages and an all-page machine scan"
            not in cover_norm
            or f"{manuscript_page_count}-row page inventory" not in cover_norm
        ):
            return _fail(
                "cover letter lacks the PDF manual visual-check/page-inventory boundary"
            )
        expected_size_text = (
            f"{archive_size_mib:.2f} MiB "
            f"({archive_size_mb_decimal:.2f} MB decimal)"
        )
        expected_file_text = f"{file_count:,} files"
        reproduction_environment_for_cover = _read_member(
            zf,
            "Paper-JSS/replication/results/reproduction_environment_audit.md",
        )
        r_modules = re.search(
            r"R reproduced modules:\s*(\d+)/\d+",
            reproduction_environment_for_cover,
        )
        stata_modules = re.search(
            r"Stata reproduced modules:\s*(\d+)/\d+",
            reproduction_environment_for_cover,
        )
        tier1_transcript_for_cover = _read_member(
            zf,
            "Paper-JSS/replication/results/reproduce_tier1_output.txt",
        )
        tier1_match = re.search(
            r"(\d+/\d+) steps passed",
            tier1_transcript_for_cover,
        )
        registry_count = claim_counts.get("registry")
        parameter_total = agent_summary.get("parameter_total")
        if not isinstance(registry_count, int) or not isinstance(parameter_total, int):
            return _fail("cannot derive cover letter registry/schema counts")
        if not r_modules or not stata_modules or not tier1_match:
            return _fail("cannot derive cover letter reproduction counts")
        cover_expected_snippets = [
            f"{manuscript_page_count} pages",
            expected_file_text,
            f"{registry_count:,} registered public functions",
            f"{registry_count:,} public functions",
            f"{parameter_total:,} schema parameters",
            f"tagged {pyproject_version.group(1)}\nrelease",
            f"{r_modules.group(1)}-module R-parity",
            f"{stata_modules.group(1)}-module Stata bridge",
            tier1_match.group(1),
            "13 PASS evidence cards",
            "5 suggested review routes",
            "editor triage",
            "statistical validation",
            "quick reproduction",
            "agent-interface review",
            "limitations/release-boundary review",
            "pdf_visual_check_protocol",
            "claimed_manual_acceptance=False",
            "stata_rerun_protocol",
            "missing Stata is an optional-runtime skip",
            "jss_upload_blocking=False",
            "data_provenance_audit",
            "9 packaged public dataset CSVs",
            "7 public original-data extract CSVs",
            f"{EXPECTED_R_STATA_FIXTURE_CSV_COUNT} same-byte R/Stata fixture CSVs",
            "zero forbidden raw-data members",
            "zero private/credential path hits",
            "zero unknown categories",
        ]
        missing_cover_snippets = [
            snippet for snippet in cover_expected_snippets
            if not _has_snippet(cover_letter, snippet)
        ]
        if missing_cover_snippets:
            return _fail(
                "cover letter numeric summary is stale: "
                + ", ".join(missing_cover_snippets)
            )
        if not _archive_size_count_disclosure_ok(
            cover_letter,
            archive_size_mib=archive_size_mib,
            archive_size_mb_decimal=archive_size_mb_decimal,
            file_count=file_count,
        ):
            return _fail(
                "cover letter numeric summary has stale archive size/count: "
                f"{expected_size_text}, {expected_file_text}"
            )
        for snippet in (
            "published in the *Journal of Open Source",
            "doi.org/10.21105/joss.10604",
            "cites the JOSS paper explicitly",
            "disclosed explicitly to the editors",
            "StatsPAI Inc.",
            "CoPaper.AI",
            "No external funder",
        ):
            if snippet not in cover_norm:
                return _fail(
                    "cover letter lacks related-review/COI disclosure: "
                    + snippet
                )
        for rel in (
            "Paper-JSS/README.md",
            "Paper-JSS/cover-letter.md",
            "Paper-JSS/REVIEWER-HARDENING-AUDIT.md",
        ):
            text = _read_member(zf, rel)
            if not _archive_size_count_disclosure_ok(
                text,
                archive_size_mib=archive_size_mib,
                archive_size_mb_decimal=archive_size_mb_decimal,
                file_count=file_count,
            ):
                return _fail(
                    f"{rel} does not report final archive size/count "
                    f"({expected_size_text}, {expected_file_text})"
                )
        hardening_audit = _read_member(
            zf,
            "Paper-JSS/REVIEWER-HARDENING-AUDIT.md",
        )
        if (
            "source-snapshot evidence remains the 2026-06-28 source snapshot"
            in hardening_audit
        ):
            return _fail(
                "REVIEWER-HARDENING-AUDIT.md has stale source-snapshot "
                "header wording"
            )
        for snippet in (
            "Last updated: 2026-09-23",
            f"describes the tagged {RELEASE} release",
        ):
            if snippet not in hardening_audit:
                return _fail(
                    "REVIEWER-HARDENING-AUDIT.md lacks current release "
                    f"header boundary: {snippet!r}"
                )
        risk_items = _hardening_risk_items(hardening_audit)
        risk_numbers = [number for number, _title in risk_items]
        risk_titles = [title for _number, title in risk_items]
        expected_numbers = list(range(1, len(EXPECTED_HARDENING_RISK_TITLES) + 1))
        if risk_numbers != expected_numbers:
            return _fail(
                "REVIEWER-HARDENING-AUDIT.md hard-reviewer risk numbers "
                f"drift: expected={expected_numbers}, observed={risk_numbers}"
            )
        if risk_titles != EXPECTED_HARDENING_RISK_TITLES:
            return _fail(
                "REVIEWER-HARDENING-AUDIT.md hard-reviewer risk titles "
                "drift: " + "; ".join(risk_titles)
            )
        duplicate_actions = _duplicate_next_action_bullets(hardening_audit)
        if duplicate_actions:
            return _fail(
                "REVIEWER-HARDENING-AUDIT.md has duplicate Next Actions: "
                + "; ".join(duplicate_actions)
            )
        if "five expected final tagged-cut pending checks" in hardening_audit:
            return _fail(
                "REVIEWER-HARDENING-AUDIT.md conflates expected final-cut "
                "requirements with currently pending checks"
            )
        if "four currently pending final tagged-cut checks" in hardening_audit:
            return _fail(
                "REVIEWER-HARDENING-AUDIT.md has stale final-cut pending "
                "check count"
            )
        if (
            "five expected final tagged-cut requirement identities"
            not in hardening_audit
            or "five currently pending final tagged-cut checks"
            not in hardening_audit
            or "five-step ordered final tagged-cut runbook"
            not in hardening_audit
        ):
            return _fail(
                "REVIEWER-HARDENING-AUDIT.md lacks precise final-cut "
                "requirement/pending/runbook count wording"
            )
        for snippet in (
            "mechanical and contractual rather than behavioural",
            "mechanical and contractual agent-interface claims",
            "mechanical and contractual boundary",
            "same validation ledger as human calls",
            "deferred benchmark protocol rather than a completed behavioural result",
            "keep the deferred protocol as protocol",
            "manual visual-check boundary",
            "cover-letter PDF visual-check boundary",
            "PDF visual-check protocol",
            f"all {manuscript_page_count} pages",
            "claimed_manual_acceptance=False",
        ):
            if snippet not in hardening_audit:
                return _fail(
                    "REVIEWER-HARDENING-AUDIT.md lacks contractual agent "
                    f"wording: {snippet!r}"
                )
        for snippet in (
            "Stata rerun protocol",
            "stata_rerun_protocol",
            "requires_stata_license=True",
            "jss_upload_blocking=False",
            "claimed_current_machine_live_rerun=False",
            "missing Stata as an optional-runtime skip",
        ):
            if snippet not in hardening_audit:
                return _fail(
                    "REVIEWER-HARDENING-AUDIT.md lacks Stata protocol "
                    f"wording: {snippet!r}"
                )
        for snippet in (
            "data provenance audit",
            "data_provenance_audit",
            "forbidden_raw_member_count=0",
            "zero forbidden raw-data members",
            "zero high-risk private/credential path hits",
            "zero unknown categories",
            "same-byte R/Stata fixture CSVs",
        ):
            if snippet not in hardening_audit:
                return _fail(
                    "REVIEWER-HARDENING-AUDIT.md lacks data provenance "
                    f"wording: {snippet!r}"
                )
        for rel in (
            "Paper-JSS/README.md",
            "Paper-JSS/cover-letter.md",
            "Paper-JSS/REVIEWER-HARDENING-AUDIT.md",
            "Paper-JSS/manuscript/README.md",
        ):
            if not _mentions_page_count(_read_member(zf, rel), manuscript_page_count):
                return _fail(
                    f"{rel} does not report the live main.pdf page count "
                    f"({manuscript_page_count})"
                )
        paper_readme = _read_member(zf, "Paper-JSS/README.md")
        if (
            "../docs/jss_source_audit_dossier.md" not in paper_readme
            or "packaged as\n`docs/jss_source_audit_dossier.md` in the archive"
            not in paper_readme
        ):
            return _fail(
                "Paper-JSS/README.md does not expose the archive-relative "
                "JSS source dossier path"
            )
        for command in PAPER_README_REVIEWER_COMMANDS:
            if command not in paper_readme:
                return _fail(
                    "Paper-JSS/README.md lacks reviewer command: " + command
                )
        for snippet in (
            "mechanical and contractual agent-interface boundary",
            "mechanical and contractual schema/MCP/citation/result-handle interface",
            "deferred benchmark protocol, not a completed behavioural result",
            "thirteen expected PASS cards",
            "five suggested review routes",
            "eleven expected PASS items",
            "nonblocking-risk crosswalk",
            "archive boundary, related-review and COI boundary, source installability",
            "limitations crosswalk, maintenance and sustainability, and final tagged-cut cleanup",
            "machine-render-versus-human-visual-check boundary",
            "manual visual spot-check boundary",
            "PDF visual-check protocol",
            f"all {manuscript_page_count} PDF pages",
            "full-document machine scan",
            f"`{manuscript_page_count}/{manuscript_page_count}` pages",
            "claimed_manual_acceptance=False",
            "Licensed Stata Tier-3 Rerun Protocol",
            "stata_rerun_protocol",
            "requires_stata_license",
            "claimed_current_machine_live_rerun=False",
            "Data Provenance Audit",
            "data_provenance_audit",
            "9 packaged public dataset CSVs",
            "7 public original-data extract CSVs",
            f"{EXPECTED_R_STATA_FIXTURE_CSV_COUNT} same-byte R/Stata fixture CSVs",
            "zero forbidden raw-data members",
            "zero high-risk private/credential path hits",
            "zero unknown categories",
            "raw binary/statistical data formats",
        ):
            if not _has_snippet(paper_readme, snippet):
                return _fail(
                    "Paper-JSS/README.md lacks updated agent/reviewer-map "
                    f"wording: {snippet!r}"
                )
        if _has_snippet(
            paper_readme,
            "archive boundary, source installability, mechanical and contractual "
            "agent-interface claims, limitations crosswalk, and final tagged-cut cleanup",
        ):
            return _fail(
                "Paper-JSS/README.md has stale reviewer-map summary prose"
            )
        if "ten expected PASS items" in paper_readme:
            return _fail(
                "Paper-JSS/README.md has stale editor-screening item count"
            )
        missing_route_labels = [
            label
            for label in EXPECTED_REVIEWER_ROUTE_README_LABELS
            if not _has_snippet(paper_readme, label)
        ]
        if missing_route_labels:
            return _fail(
                "Paper-JSS/README.md reviewer-map prose omits route labels: "
                + ", ".join(missing_route_labels)
            )
        missing_card_labels = [
            label
            for label in EXPECTED_REVIEWER_CARD_README_LABELS
            if not _has_snippet(paper_readme, label)
        ]
        if missing_card_labels:
            return _fail(
                "Paper-JSS/README.md reviewer-map prose omits card labels: "
                + ", ".join(missing_card_labels)
            )
        manuscript_readme = _read_member(zf, "Paper-JSS/manuscript/README.md")
        for command in MANUSCRIPT_README_REVIEWER_COMMANDS:
            if command not in manuscript_readme:
                return _fail(
                    "Paper-JSS/manuscript/README.md lacks reviewer command: "
                    + command
                )
        external_review_artifacts = sorted(
            ACTIVE_EXTERNAL_REVIEW_ARTIFACTS_FORBIDDEN_IN_ARCHIVE & names
        )
        if external_review_artifacts:
            return _fail(
                "archive includes active external-review artifacts reserved "
                "for the separate software review: "
                + ", ".join(external_review_artifacts)
            )
        if (
            "every Section 4--7 headline number rebuilt without" not in manuscript_readme
            or "R or Stata" not in manuscript_readme
        ):
            return _fail(
                "manuscript README does not disclose the no-R/no-Stata "
                "Tier-1 headline path"
            )
        if (
            not _has_snippet(
                manuscript_readme,
                f"reviewer evidence map reports PASS with {len(EXPECTED_REVIEWER_CARD_IDS)} cards and 0 failed cards",
            )
            or not _has_snippet(
                manuscript_readme,
                "without expanding the compact PDF",
            )
        ):
            return _fail(
                "manuscript README does not route compact-PDF reviewer "
                "questions to the evidence map"
            )
        for stale_shard_claim in (
            "CCT/Lee focused pytest shard passed",
            "JSS validation/API/RD-density shard passed",
        ):
            if stale_shard_claim in manuscript_readme:
                return _fail(
                    "manuscript README contains a brittle historical pytest "
                    f"pass-count claim: {stale_shard_claim}"
                )

        agent_interface = _read_member(
            zf,
            "Paper-JSS/replication/results/agent_interface_audit.md",
        )
        if "Status: PASS" not in agent_interface:
            return _fail("agent_interface_audit.md inside archive is not PASS")
        if "mechanical and contractual schema/MCP/citation evidence only" not in agent_interface:
            return _fail("agent_interface_audit.md lacks contractual scope")
        agent_params = agent_summary.get("parameter_total")
        agent_described = agent_summary.get("parameter_with_description")
        if agent_params is None or agent_described is None:
            return _fail("jss_full_audit.json lacks live agent schema counts")
        expected_agent_schema_line = (
            f"Parameters with descriptions: {agent_described}/{agent_params} "
            f"({100 * agent_described / agent_params:.1f}%)"
        )
        if expected_agent_schema_line not in agent_interface:
            return _fail("agent_interface_audit.md does not pin live schema counts")
        if "Citation keys: callaway2021difference, rambachan2023more" not in agent_interface:
            return _fail("agent_interface_audit.md does not verify trace citations")
        if "BibTeX entries resolved: 2 from paper.bib" not in agent_interface:
            return _fail("agent_interface_audit.md does not verify BibTeX resolution")
        if "Stale-handle error envelope: isError=True" not in agent_interface:
            return _fail(
                "agent_interface_audit.md does not verify stale-handle error envelope"
            )
        if "hint_present=True" not in agent_interface:
            return _fail(
                "agent_interface_audit.md does not report an actionable stale-handle hint"
            )
        if "trace_bibtex=2 from paper.bib" not in audit:
            return _fail("jss_full_audit.md does not report trace BibTeX resolution")
        if (
            agent_summary.get("trace_stale_handle_is_error") is not True
            or agent_summary.get("trace_stale_handle_hint_present") is not True
        ):
            return _fail(
                "jss_full_audit.json lacks stale-handle error-envelope summary"
            )
        if (
            "trace_stale_handle_error=True" not in audit
            or "trace_stale_handle_hint=True" not in audit
        ):
            return _fail(
                "jss_full_audit.md does not report stale-handle error-envelope summary"
            )

        release_boundary = _read_member(
            zf,
            "Paper-JSS/replication/results/release_boundary_audit.md",
        )
        release_boundary_json = _read_json_member(
            zf,
            "Paper-JSS/replication/results/release_boundary_audit.json",
        )
        if "Status: PASS" not in release_boundary:
            return _fail("release_boundary_audit.md inside archive is not PASS")
        if "Ready for final publication release:" not in release_boundary:
            return _fail("release_boundary_audit.md does not expose release readiness")
        if (
            "fails if source-snapshot evidence is framed as already released"
            not in release_boundary
        ):
            return _fail("release_boundary_audit.md lacks source-snapshot boundary scope")
        if "Disclosure files checked: 8" not in release_boundary:
            return _fail(
                "release_boundary_audit.md does not report the JSS/JOSS "
                "disclosure check"
            )
        checked_release_boundary = set(release_boundary_json.get("checked_files", []))
        if len(checked_release_boundary) != 8:
            return _fail(
                "release_boundary_audit.json has unexpected checked file count"
            )
        if "docs/jss_source_audit_dossier.md" not in checked_release_boundary:
            return _fail(
                "release_boundary_audit.json does not include the JSS source dossier"
            )

        reproduction_environment = _read_member(
            zf,
            "Paper-JSS/replication/results/reproduction_environment_audit.md",
        )
        reproduction_environment_json = _read_json_member(
            zf,
            "Paper-JSS/replication/results/reproduction_environment_audit.json",
        )
        reproduction_readmes = reproduction_environment_json.get(
            "reviewer_readmes", {}
        )
        if "Status: PASS" not in reproduction_environment:
            return _fail("reproduction_environment_audit.md inside archive is not PASS")
        if reproduction_environment_json.get("status") != "PASS":
            return _fail("reproduction_environment_audit.json inside archive is not PASS")
        if reproduction_readmes.get("paper_readme_command_count") != len(
            PAPER_README_REVIEWER_COMMANDS
        ):
            return _fail(
                "reproduction_environment_audit.json has stale Paper-JSS "
                "README reviewer command count"
            )
        if reproduction_readmes.get("manuscript_readme_command_count") != len(
            MANUSCRIPT_README_REVIEWER_COMMANDS
        ):
            return _fail(
                "reproduction_environment_audit.json has stale manuscript "
                "README reviewer command count"
            )
        if reproduction_readmes.get("paper_readme_missing_commands"):
            return _fail(
                "reproduction_environment_audit.json reports missing "
                "Paper-JSS README reviewer commands"
            )
        if reproduction_readmes.get("manuscript_readme_missing_commands"):
            return _fail(
                "reproduction_environment_audit.json reports missing "
                "manuscript README reviewer commands"
            )
        if (
            "Reviewer README commands checked: "
            f"{len(PAPER_README_REVIEWER_COMMANDS)}"
        ) not in reproduction_environment:
            return _fail(
                "reproduction_environment_audit.md has stale Paper-JSS "
                "README reviewer command count"
            )
        if (
            "Manuscript README commands checked: "
            f"{len(MANUSCRIPT_README_REVIEWER_COMMANDS)}"
        ) not in reproduction_environment:
            return _fail(
                "reproduction_environment_audit.md has stale manuscript "
                "README reviewer command count"
            )
        if "Docker base image: python:3.12-slim" not in reproduction_environment:
            return _fail("reproduction_environment_audit.md lacks Docker base image")
        if "Requirements source version comment: True" not in reproduction_environment:
            return _fail(
                "reproduction_environment_audit.md lacks requirements "
                "source-version check"
            )
        if "R lockfile present: True" not in reproduction_environment:
            return _fail("reproduction_environment_audit.md lacks R lockfile check")
        if "R environment note present: True" not in reproduction_environment:
            return _fail("reproduction_environment_audit.md lacks R environment check")
        if "R reproducibility report present: True" not in reproduction_environment:
            return _fail("reproduction_environment_audit.md lacks R repro-report check")
        if f"R reproduced modules: {EXPECTED_R_REPRO_MODULES}/{EXPECTED_R_REPRO_MODULES}" not in reproduction_environment:
            return _fail("reproduction_environment_audit.md lacks complete R module count")
        if "R non-reproduced rows: 0" not in reproduction_environment:
            return _fail("reproduction_environment_audit.md reports R repro drift/skips")
        if "Stata environment note present: True" not in reproduction_environment:
            return _fail("reproduction_environment_audit.md lacks Stata environment check")
        if "Stata reproducibility report present: True" not in reproduction_environment:
            return _fail("reproduction_environment_audit.md lacks Stata repro-report check")
        if f"Stata reproduced modules: {EXPECTED_STATA_REPRO_MODULES}/{EXPECTED_STATA_REPRO_MODULES}" not in reproduction_environment:
            return _fail("reproduction_environment_audit.md lacks complete Stata module count")
        if "Stata non-reproduced rows: 0" not in reproduction_environment:
            return _fail("reproduction_environment_audit.md reports Stata repro drift/skips")
        if "Tier-1 reviewer transcript present: True" not in reproduction_environment:
            return _fail("reproduction_environment_audit.md lacks Tier-1 transcript check")
        if "Tier-1 reviewer transcript complete: True" not in reproduction_environment:
            return _fail("reproduction_environment_audit.md lacks completed transcript check")
        if "Tier-1 transcript states no R/Stata headline path: True" not in reproduction_environment:
            return _fail(
                "reproduction_environment_audit.md does not prove the Tier-1 "
                "headline path is no-R/no-Stata"
            )
        if "Tier-1 live R/Stata dependency markers: 0" not in reproduction_environment:
            return _fail(
                "reproduction_environment_audit.md does not expose live "
                "R/Stata dependency markers"
            )
        if "Seeded stochastic reproduction files:" not in reproduction_environment:
            return _fail(
                "reproduction_environment_audit.md lacks stochastic-seed audit"
            )
        if "Unseeded stochastic reproduction files: 0" not in reproduction_environment:
            return _fail(
                "reproduction_environment_audit.md does not prove all stochastic "
                "paper-reproduction files are seeded"
            )

        manuscript_artifact = _read_member(
            zf,
            "Paper-JSS/replication/results/manuscript_artifact_audit.md",
        )
        manuscript_artifact_json = _read_json_member(
            zf,
            "Paper-JSS/replication/results/manuscript_artifact_audit.json",
        )
        if "Status: PASS" not in manuscript_artifact:
            return _fail("manuscript_artifact_audit.md inside archive is not PASS")
        # Counts read from the audit's own JSON, for the same reason as
        # the rollup checks above: a new table or section is an ordinary
        # edit, and freezing 10/18/18/9 turned each one into a spurious
        # "stale artifact" failure. The zero-valued lines stay literal --
        # those are the invariants.
        _mac = manuscript_artifact_json.get("compact_section_coverage") or {}
        for snippet in (
            f"Generated artifacts checked: {manuscript_artifact_json.get('artifact_count')}",
            "Hash mismatches: 0",
            "Active table/figure labels: "
            f"{len(manuscript_artifact_json.get('active_float_labels') or [])}",
            "Narrative table/figure references: "
            f"{len(manuscript_artifact_json.get('narrative_float_refs') or [])}",
            "Missing narrative references: 0",
            "Dangling narrative references: 0",
            "Worked-example scripts present: 7/7",
            "Worked-example script mentions: 7/7",
            "Worked-example subsection labels: 7/7",
            "Worked-example count claim present: True",
            f"Compact section coverage: {_mac.get('sections_passed')}/"
            f"{_mac.get('sections_checked')}",
            "Compact section missing anchors: 0",
            "Compact narrative coverage:",
            "track_a_cross_language_snapshot.tex",
            "track_c_perf.tex",
            "ex07_agent_trace.tex",
            "track_c_loglog.pdf",
        ):
            if snippet not in manuscript_artifact:
                return _fail(f"manuscript artifact audit lacks {snippet!r}")
        # Sizes are the manuscript's, not the verifier's, to pin: what has
        # to hold is that every generated artifact is hash-checked and
        # every float is both labelled and referenced.
        if not manuscript_artifact_json.get("artifact_count"):
            return _fail("manuscript artifact audit checks no generated artifacts")
        if manuscript_artifact_json.get("hash_mismatches") != 0:
            return _fail("manuscript artifact audit reports hash mismatches")
        float_labels = manuscript_artifact_json.get("active_float_labels", [])
        narrative_refs = manuscript_artifact_json.get("narrative_float_refs", [])
        if not float_labels:
            return _fail("manuscript artifact audit finds no labelled floats")
        if len(narrative_refs) != len(float_labels):
            return _fail(
                f"manuscript artifact audit finds {len(float_labels)} labelled "
                f"floats but {len(narrative_refs)} narrative references"
            )
        if manuscript_artifact_json.get("missing_narrative_refs"):
            return _fail("manuscript artifact audit reports missing narrative refs")
        if manuscript_artifact_json.get("dangling_float_refs"):
            return _fail("manuscript artifact audit reports dangling float refs")
        worked_examples = manuscript_artifact_json.get("worked_examples", {})
        if worked_examples.get("expected_count") != 7:
            return _fail("manuscript artifact audit has wrong worked-example count")
        if len(worked_examples.get("scripts_present", [])) != 7:
            return _fail("manuscript artifact audit does not find seven example scripts")
        if len(worked_examples.get("script_mentions", [])) != 7:
            return _fail("manuscript artifact audit does not find seven script mentions")
        if len(worked_examples.get("labels_present", [])) != 7:
            return _fail("manuscript artifact audit does not find seven example labels")
        if worked_examples.get("count_claim_present") is not True:
            return _fail("manuscript artifact audit does not find the seven-example claim")
        compact_coverage = manuscript_artifact_json.get("compact_section_coverage", {})
        if compact_coverage.get("ok") is not True:
            return _fail("manuscript artifact audit reports compact section gaps")
        sections_checked = compact_coverage.get("sections_checked")
        if not sections_checked:
            return _fail("manuscript artifact audit checks no compact sections")
        if compact_coverage.get("sections_passed") != sections_checked:
            return _fail(
                f"manuscript artifact audit passes "
                f"{compact_coverage.get('sections_passed')} of "
                f"{sections_checked} compact sections"
            )
        if compact_coverage.get("missing_anchor_count") != 0:
            return _fail("manuscript artifact audit reports missing compact anchors")
        compact_rows = compact_coverage.get("rows", [])
        compact_sections = [row.get("section") for row in compact_rows]
        expected_compact_sections = sorted(
            member.removeprefix("Paper-JSS/manuscript/")
            for member in ACTIVE_MANUSCRIPT_SECTION_MEMBERS
        )
        if compact_sections != expected_compact_sections:
            return _fail("manuscript artifact audit compact section order drift")
        for row in compact_rows:
            section = row.get("section")
            role = row.get("role")
            if not section or f"`{section}`" not in manuscript_artifact:
                return _fail(
                    "manuscript artifact audit Markdown lacks compact section "
                    f"{section!r}"
                )
            if not role or role not in manuscript_artifact:
                return _fail(
                    "manuscript artifact audit Markdown lacks compact role "
                    f"for {section!r}"
                )
        generated_pdf_figures = [
            name
            for name in names
            if (
                name.startswith("Paper-JSS/manuscript/figures/")
                and name.endswith(".pdf")
            )
        ]
        generated_pdf_figures.append("tests/perf/figures/track_c_loglog.pdf")
        timestamped_pdf_figures = [
            name
            for name in sorted(generated_pdf_figures)
            if b"/CreationDate" in _read_binary_member(zf, name)
        ]
        if timestamped_pdf_figures:
            return _fail(
                "generated PDF figures contain non-deterministic "
                "CreationDate metadata: " + ", ".join(timestamped_pdf_figures)
            )

        formal_compliance = _read_member(
            zf,
            "Paper-JSS/replication/results/jss_formal_compliance_audit.md",
        )
        formal_json = _read_json_member(
            zf,
            "Paper-JSS/replication/results/jss_formal_compliance_audit.json",
        )
        if "Status: PASS" not in formal_compliance:
            return _fail("jss_formal_compliance_audit.md inside archive is not PASS")
        for snippet in (
            "Official JSS pages checked: 2026-08-09",
            "PDF manuscript in JSS LaTeX article style",
            "LaTeX build log is free of blocking layout/reference errors",
            "PDF-visible validation/source/data/agent boundaries are present",
            "PDF text is synchronized with polished manuscript prose",
            "rendered PDF page-sample sanity check passes",
            "JSS markup macros and labelled floats are used",
            "source code is packaged for installation",
            "pip --no-deps --target install/import probe ok=True",
            "GPL-compatible software license is clearly indicated",
            "software citation metadata is included",
            "standalone replication script covers manuscript results",
            "short reviewer replication path completes within one hour",
            "existing implementations and comparative scope are discussed",
            "related-software table",
            "StatsPAI contribution/boundary language",
            "missing_related_tokens=[]",
            "source-snapshot and final-release boundaries are explicit",
            "version_consistent=True",
            "platform dependencies and RNG seeds are disclosed",
            "cover letter numeric summary is synchronized with generated audit artifacts",
            "cover letter PDF visual-check boundary is explicit",
            "cover letter related-review and conflict disclosures are explicit",
            "active manuscript tables and figures map to generators",
            "JSS attachment size and archive source set are bounded",
            "ASCII source/data contract is enforced inside the archive",
        ):
            if snippet not in formal_compliance:
                return _fail(f"formal compliance audit lacks {snippet!r}")
        if formal_json.get("archive_present") is not True:
            return _fail("formal compliance audit did not inspect the final archive")
        if formal_json.get("page_count") != manuscript_page_count:
            return _fail(
                "formal compliance page count does not match main.pdf page count"
            )
        if formal_json.get("pdf_text_chars", 0) <= 0:
            return _fail("formal compliance audit did not extract main.pdf text")
        if formal_json.get("missing_pdf_boundary_snippets"):
            return _fail(
                "formal compliance audit reports missing PDF boundary snippets"
            )
        if formal_json.get("pdf_stale_prose_hits"):
            return _fail("formal compliance audit reports stale PDF prose")
        formal_pdf_render = formal_json.get("pdf_render", {})
        if formal_pdf_render.get("status") != "PASS":
            return _fail("formal compliance audit does not report PDF render PASS")
        if formal_pdf_render.get("page_count") != manuscript_page_count:
            return _fail("formal compliance PDF render page count is stale")
        if formal_pdf_render.get("failure_count") != 0:
            return _fail("formal compliance PDF render row reports failures")
        if formal_pdf_render.get("sampled_pages") != expected_render_pages:
            return _fail("formal compliance PDF render sampled pages are stale")
        if (
            formal_pdf_render.get("full_document_rendered_page_count")
            != manuscript_page_count
        ):
            return _fail("formal compliance PDF render full scan count is stale")
        if formal_pdf_render.get("full_document_failure_count") != 0:
            return _fail("formal compliance PDF render full scan reports failures")
        if any(item.get("ok") is not True for item in formal_json.get("checks", [])):
            return _fail("formal compliance audit has non-passing checks")
        install_probe = formal_json.get("install_probe", {})
        if (
            install_probe.get("ok") is not True
            or install_probe.get("version") != pyproject_version.group(1)
            or install_probe.get("function_count", 0) < 1000
            or not {"statspai", "statspai-mcp"} <= set(install_probe.get("scripts", []))
            or not install_probe.get("dist_infos")
        ):
            return _fail("formal compliance install/import probe is not passing")

        transcript = _read_member(
            zf,
            "Paper-JSS/replication/results/reproduce_tier1_output.txt",
        )
        for snippet in (
            "StatsPAI JSS replication -- Tier 1",
            "causal-forest AIPW recovery",
            "JSS headline-count guard",
            "reproduction environment audit",
            "verify_citations.py",
            "SUMMARY",
            "RESULT: OK -- all required steps reproduced.",
            "Every Section 4-7 headline number was rebuilt without R or Stata.",
        ):
            if snippet not in transcript:
                return _fail(f"Tier-1 reviewer transcript lacks {snippet!r}")
        transcript_summary = re.search(
            r"(?P<passed>\d+)/(?P<total>\d+) steps passed in "
            r"(?P<minutes>[0-9.]+) min",
            transcript,
        )
        if not transcript_summary:
            return _fail("Tier-1 reviewer transcript lacks pass-count summary")
        passed = int(transcript_summary.group("passed"))
        total = int(transcript_summary.group("total"))
        minutes = float(transcript_summary.group("minutes"))
        if passed != total or total < 20:
            return _fail(
                "Tier-1 reviewer transcript does not report all steps passing"
            )
        if minutes > 60.0:
            return _fail(
                "Tier-1 reviewer transcript exceeds the one-hour reviewer path"
            )

        reproduce = _read_member(zf, "Paper-JSS/replication/reproduce.py")
        if "JSS one-hour threshold" not in reproduce:
            return _fail(
                "replication/reproduce.py does not frame Tier-1 timing against "
                "the JSS one-hour threshold"
            )
        if re.search(r"records 23/23 steps in \d+(?:\.\d+)? minutes", reproduce):
            return _fail(
                "replication/reproduce.py pins a machine-specific Tier-1 minute count"
            )

        dockerfile = _read_member(zf, "Paper-JSS/replication/Dockerfile")
        if "Paper-JSS/requirements-jss.txt" not in dockerfile:
            return _fail("Dockerfile does not install Paper-JSS/requirements-jss.txt")
        for snippet in (
            "COPY tests ./tests",
            "COPY scripts ./scripts",
            "COPY docs ./docs",
            "poppler-utils",
            "python -m pip install --upgrade pip setuptools wheel",
            'CMD ["make", "reproduce-jss-full"]',
        ):
            if snippet not in dockerfile:
                return _fail(f"Dockerfile lacks full-audit container snippet: {snippet}")
        requirements = _read_member(zf, "Paper-JSS/requirements-jss.txt")
        for package in (
            "numpy",
            "pandas",
            "statsmodels",
            "linearmodels",
            "rdrobust",
            "Pillow",
            "pyarrow",
            "pytest",
            "pytest-cov",
            "setuptools",
            "wheel",
        ):
            if package not in requirements:
                return _fail(f"requirements-jss.txt lacks {package}")
        if (
            "local StatsPAI 1.20.0 tree" not in requirements
            or "local StatsPAI 1.16.1 tree" in requirements
        ):
            return _fail("requirements-jss.txt carries a stale StatsPAI version comment")

        r_env = _read_member(zf, "tests/r_parity/R_ENVIRONMENT.md")
        for snippet in ("R 4.5.2", "renv.lock", "verify_reproduce.py"):
            if snippet not in r_env:
                return _fail(f"R_ENVIRONMENT.md lacks {snippet}")
        r_report = _read_member(zf, "tests/r_parity/results/REPRODUCIBILITY_REPORT.md")
        if "Generated by `tests/r_parity/verify_reproduce.py`" not in r_report:
            return _fail("R reproducibility report lacks generator provenance")
        r_counts = _repro_report_counts(r_report)
        if r_counts["reproduced"] != EXPECTED_R_REPRO_MODULES:
            return _fail(
                "R reproducibility report reproduced "
                f"{r_counts['reproduced']} modules, expected "
                f"{EXPECTED_R_REPRO_MODULES}"
            )
        if r_counts["non_reproduced"] != 0:
            return _fail(
                "R reproducibility report contains non-reproduced rows: "
                f"{r_counts['non_reproduced']}"
            )
        stata_env_file = _read_member(zf, "tests/stata_parity/STATA_ENVIRONMENT.md")
        for snippet in ("Stata 18", "Edition | MP", "verify_reproduce_stata.py"):
            if snippet not in stata_env_file:
                return _fail(f"STATA_ENVIRONMENT.md lacks {snippet}")
        stata_report = _read_member(
            zf,
            "tests/stata_parity/results/REPRODUCIBILITY_REPORT_STATA.md",
        )
        if "Generated by `tests/stata_parity/verify_reproduce_stata.py`" not in stata_report:
            return _fail("Stata reproducibility report lacks generator provenance")
        stata_counts = _repro_report_counts(stata_report)
        if stata_counts["reproduced"] != EXPECTED_STATA_REPRO_MODULES:
            return _fail(
                "Stata reproducibility report reproduced "
                f"{stata_counts['reproduced']} modules, expected "
                f"{EXPECTED_STATA_REPRO_MODULES}"
            )
        if stata_counts["non_reproduced"] != 0:
            return _fail(
                "Stata reproducibility report contains non-reproduced rows: "
                f"{stata_counts['non_reproduced']}"
            )

        validation_evidence = _read_member(
            zf,
            "Paper-JSS/replication/results/validation_evidence_audit.md",
        )
        if "Status: PASS" not in validation_evidence:
            return _fail("validation_evidence_audit.md inside archive is not PASS")
        if "Missing validation notes: 0" not in validation_evidence:
            return _fail(
                "validation_evidence_audit.md does not prove notes for every "
                "certified/validated symbol"
            )
        if "Certified without certified-grade evidence: 0" not in validation_evidence:
            return _fail(
                "validation_evidence_audit.md does not prove R/Stata parity "
                "evidence for certified symbols"
            )
        if "Validated without validated-grade evidence: 0" not in validation_evidence:
            return _fail(
                "validation_evidence_audit.md does not prove qualifying "
                "reference/external/known-truth/coverage evidence for "
                "validated symbols"
            )
        if "Supplemental-only certified/validated symbols: 0" not in validation_evidence:
            return _fail(
                "validation_evidence_audit.md leaves certified/validated "
                "symbols backed only by supplemental evidence"
            )
        if (
            "## Qualifying Evidence Note Kinds" not in validation_evidence
            or "## Supplemental Evidence Note Kinds" not in validation_evidence
            or "## Symbols With Scoped Limitations" not in validation_evidence
            or "## Validated-Tier Symbols" not in validation_evidence
        ):
            return _fail(
                "validation_evidence_audit.md does not separate qualifying "
                "evidence kinds, supplemental notes, scoped limitations, "
                "and validated-tier rows"
            )
        if "blanket parity or validation claims" not in validation_evidence:
            return _fail(
                "validation_evidence_audit.md does not explain scoped "
                "limitations as non-blanket evidence"
            )
        if "Evidence path scope: certified/validated symbols only" not in validation_evidence:
            return _fail(
                "validation_evidence_audit.md does not distinguish "
                "certified/validated evidence paths from package-wide "
                "registry evidence files"
            )
        validation_evidence_json = _read_json_member(
            zf,
            "Paper-JSS/replication/results/validation_evidence_audit.json",
        )
        validation_evidence_summary = validation_evidence_json.get("summary", {})
        for key in (
            "certified_validated_symbols",
            "certified_symbols",
            "validated_symbols",
            "missing_validation_notes",
            "certified_without_certified_grade_evidence",
            "validated_without_validated_grade_evidence",
            "supplemental_only_symbols",
            "symbols_with_limitations",
            "unique_evidence_paths",
        ):
            if validation_evidence_json.get(key) != validation_evidence_summary.get(key):
                return _fail(
                    "validation_evidence_audit.json lacks top-level "
                    f"{key} matching summary"
                )
        if validation_evidence_json.get(
            "missing_evidence_path_count"
        ) != validation_evidence_summary.get("missing_evidence_paths"):
            return _fail(
                "validation_evidence_audit.json lacks top-level "
                "missing_evidence_path_count matching summary"
            )
        if validation_evidence_summary.get("supplemental_only_symbols") != 0:
            return _fail(
                "validation_evidence_audit.json reports certified/validated "
                "symbols backed only by supplemental evidence"
            )
        if validation_evidence_summary.get(
            "validated_without_validated_grade_evidence"
        ) != 0:
            return _fail(
                "validation_evidence_audit.json reports validated symbols "
                "without status-grade evidence"
            )
        if "other" in validation_evidence_summary.get(
            "qualifying_note_kind_symbols", {}
        ):
            return _fail(
                "validation_evidence_audit.json classifies 'other' as "
                "qualifying evidence"
            )
        limited_rows = [
            row for row in validation_evidence_json.get("rows", [])
            if row.get("limitations")
        ]
        if len(limited_rows) != validation_evidence_summary.get(
            "symbols_with_limitations"
        ):
            return _fail(
                "validation_evidence_audit.json limitation rows do not "
                "match the summary count"
            )
        if not any(row.get("name") == "rddensity" for row in limited_rows):
            return _fail(
                "validation_evidence_audit.json does not expose the "
                "rddensity scoped limitation row"
            )

        gap_ledger = _read_member(
            zf,
            "Paper-JSS/replication/results/methodological_gap_ledger.md",
        )
        gap_ledger_json = _read_json_member(
            zf,
            "Paper-JSS/replication/results/methodological_gap_ledger.json",
        )
        if "Status: PASS" not in gap_ledger:
            return _fail("methodological_gap_ledger.md inside archive is not PASS")
        if "Uncategorized gaps: 0" not in gap_ledger:
            return _fail("methodological_gap_ledger.md leaves uncategorized gaps")
        if "methodological/T4 Track A disclosures" not in gap_ledger:
            return _fail(
                "methodological_gap_ledger.md does not frame methodological/T4 "
                "disclosure scope"
            )
        for snippet in (
            "validation_tier=`identification_dependent_native`",
            "reference_backend=`Synth`",
            "Non-circular native guard",
            "Reference disagreement guard",
            "py-Stata rel",
            "R-Stata rel",
            "native tracks Stata synth",
            "unique convex-hull SCM",
            "uniquely identified convex-hull DGP",
        ):
            if snippet not in gap_ledger:
                return _fail(
                    f"methodological_gap_ledger.md lacks required T4 metadata guard: {snippet}"
                )
        gap_null_paths = _json_null_paths(gap_ledger_json)
        if gap_null_paths:
            return _fail(
                "methodological_gap_ledger.json contains reviewer-facing nulls: "
                + ", ".join(gap_null_paths[:20])
            )
        scm_recovery = _read_member(zf, "tests/reference_parity/test_scm_recovery.py")
        for snippet in (
            "test_classic_scm_unique_solution",
            "test_scm_family_recovers_known_att",
        ):
            if snippet not in scm_recovery:
                return _fail(
                    "SCM recovery guard lacks required known-truth test: "
                    + snippet
                )

        r_parity_readme = _read_member(zf, "tests/r_parity/README.md")
        missing_native_rows = [
            row for row in R_PARITY_README_REQUIRED_NATIVE_ROWS
            if row not in r_parity_readme
        ]
        if missing_native_rows:
            return _fail(
                "tests/r_parity/README.md does not identify native Python "
                "rows for loose/reference-bridge modules: "
                + "; ".join(missing_native_rows)
            )
        stale_bridge_rows = [
            row for row in R_PARITY_README_FORBIDDEN_BRIDGE_ROWS
            if row in r_parity_readme
        ]
        if stale_bridge_rows:
            return _fail(
                "tests/r_parity/README.md presents reference-backend escape "
                "hatches as Python-side parity rows: "
                + "; ".join(stale_bridge_rows)
            )

        stata_bridge = _read_member(
            zf,
            "Paper-JSS/replication/results/stata_bridge_audit.md",
        )
        stata_bridge_json = _read_json_member(
            zf,
            "Paper-JSS/replication/results/stata_bridge_audit.json",
        )
        if "Status: PASS" not in stata_bridge:
            return _fail("stata_bridge_audit.md inside archive is not PASS")
        if f"Stata modules: {EXPECTED_STATA_REPRO_MODULES}" not in stata_bridge:
            return _fail(
                "stata_bridge_audit.md does not report "
                f"{EXPECTED_STATA_REPRO_MODULES} Stata modules"
            )
        if (
            f"R-joined Stata modules: {EXPECTED_STATA_REPRO_MODULES}"
            not in stata_bridge
        ):
            return _fail(
                "stata_bridge_audit.md does not report "
                f"{EXPECTED_STATA_REPRO_MODULES} R-joined modules"
            )
        if "Py-Stata-only migration modules: none" not in stata_bridge:
            return _fail("stata_bridge_audit.md does not report no Py-Stata-only rows")
        if "requires a" not in stata_bridge or "separate Stata license" not in stata_bridge:
            return _fail("stata_bridge_audit.md lacks the Stata license boundary")
        stata_null_paths = _json_null_paths(stata_bridge_json)
        if stata_null_paths:
            return _fail(
                "stata_bridge_audit.json contains reviewer-facing nulls: "
                + ", ".join(stata_null_paths[:20])
            )

        stata_protocol = _read_member(
            zf,
            "Paper-JSS/replication/results/stata_rerun_protocol.md",
        )
        stata_protocol_json = _read_json_member(
            zf,
            "Paper-JSS/replication/results/stata_rerun_protocol.json",
        )
        stata_protocol_summary = stata_protocol_json.get("summary", {})
        stata_protocol_boundary = stata_protocol_json.get("boundary", {})
        if "Status: PASS" not in stata_protocol:
            return _fail("stata_rerun_protocol.md inside archive is not PASS")
        if stata_protocol_json.get("status") != "PASS":
            return _fail("stata_rerun_protocol.json status is not PASS")
        expected_stata_protocol_boundary = {
            "requires_stata_license": True,
            "jss_upload_blocking": False,
            "absence_of_stata_is_optional_skip": True,
            "claimed_current_machine_live_rerun": False,
            "frozen_json_do_provenance_is_upload_evidence": True,
            "no_section_4_7_headline_depends_on_live_stata": True,
            "expected_stata_modules": EXPECTED_STATA_REPRO_MODULES,
        }
        for key, expected in expected_stata_protocol_boundary.items():
            if stata_protocol_boundary.get(key) != expected:
                return _fail(
                    "stata_rerun_protocol.json has stale boundary "
                    f"{key}: {stata_protocol_boundary.get(key)!r}"
                )
            if stata_protocol_summary.get(key) != expected:
                return _fail(
                    "stata_rerun_protocol.json has stale summary boundary "
                    f"{key}: {stata_protocol_summary.get(key)!r}"
                )
        expected_stata_protocol_summary = {
            "stata_bridge_status": "PASS",
            "reproduction_environment_status": "PASS",
            "stata_modules": EXPECTED_STATA_REPRO_MODULES,
            "r_joined_stata_modules": EXPECTED_STATA_REPRO_MODULES,
            "repro_report_modules": EXPECTED_STATA_REPRO_MODULES,
            "reproduced_report_rows": EXPECTED_STATA_REPRO_MODULES,
            "non_reproduced_report_rows": 0,
            "checklist_item_count": 8,
            "command_count": 4,
        }
        for key, expected in expected_stata_protocol_summary.items():
            if stata_protocol_summary.get(key) != expected:
                return _fail(
                    "stata_rerun_protocol.json has stale summary "
                    f"{key}: {stata_protocol_summary.get(key)!r}"
                )
        expected_stata_protocol_commands = {
            "paper_tier3_driver": (
                "STATA_EXE=/path/to/stata-mp ../.venv/bin/python "
                "replication/reproduce.py --tier 3"
            ),
            "direct_stata_verifier": (
                "STATA_EXE=/path/to/stata-mp .venv/bin/python "
                "tests/stata_parity/verify_reproduce_stata.py"
            ),
            "refresh_stata_environment_note": (
                "stata-mp -q -b do tests/stata_parity/_capture_stata_env.do && "
                ".venv/bin/python tests/stata_parity/_gen_stata_env.py"
            ),
            "audit_frozen_bridge": (
                "make stata-bridge-audit PYTHON=../.venv/bin/python"
            ),
        }
        observed_stata_protocol_commands = {
            item.get("id"): item.get("command")
            for item in stata_protocol_json.get("commands", [])
        }
        if observed_stata_protocol_commands != expected_stata_protocol_commands:
            return _fail("stata_rerun_protocol.json command set drifted")
        stata_protocol_checklist_ids = [
            item.get("id") for item in stata_protocol_json.get("checklist", [])
        ]
        expected_stata_protocol_checklist_ids = [
            "confirm_license",
            "inspect_environment",
            "run_tier3_or_direct_verifier",
            "compare_report_counts",
            "inspect_drift_rows",
            "preserve_golden_files",
            "interpret_missing_stata",
            "rerun_jss_gates",
        ]
        if stata_protocol_checklist_ids != expected_stata_protocol_checklist_ids:
            return _fail("stata_rerun_protocol.json checklist identity drifted")
        for snippet in (
            "requires_stata_license",
            "jss_upload_blocking",
            "claimed_current_machine_live_rerun",
            "STATA_EXE=/path/to/stata-mp ../.venv/bin/python replication/reproduce.py --tier 3",
            "tests/stata_parity/verify_reproduce_stata.py",
            "Failures: none",
        ):
            if snippet not in stata_protocol:
                return _fail(f"stata_rerun_protocol.md lacks {snippet!r}")

        snapshot = _read_member(
            zf,
            "Paper-JSS/replication/results/source_snapshot_manifest.md",
        )
        snapshot_json = json.loads(
            _read_member(
                zf,
                "Paper-JSS/replication/results/source_snapshot_manifest.json",
            )
        )
        snapshot_json_text = json.dumps(snapshot_json, sort_keys=True)
        for snippet in SOURCE_SNAPSHOT_FORBIDDEN_SNIPPETS:
            if snippet in snapshot or snippet in snapshot_json_text:
                return _fail(
                    "source_snapshot_manifest leaks local-only reviewer notes: "
                    + snippet
                )
        snapshot_payload = snapshot_json.get("jss_source_snapshot", {})
        watched_dirty_paths = snapshot_payload.get("watched_dirty_paths", [])
        if "Version-consistent inside source: `True`" not in snapshot:
            return _fail("source_snapshot_manifest.md does not confirm version consistency")
        if "Ready for final publication release:" not in snapshot:
            return _fail("source_snapshot_manifest.md lacks release-readiness status")
        if "JSS submission archive status:" not in snapshot:
            return _fail("source_snapshot_manifest.md lacks JSS submission status")
        if "not a JSS upload reproducibility failure" not in snapshot:
            return _fail(
                "source_snapshot_manifest.md does not separate submission "
                "reproducibility from the final tagged-release gate"
            )
        if "Display path redactions:" not in snapshot:
            return _fail("source_snapshot_manifest.md lacks display-path redaction note")
        if "Active external-review filenames are omitted" not in snapshot:
            return _fail(
                "source_snapshot_manifest.md does not explain active "
                "external-review omissions"
            )
        if "retired external-review filenames are displayed under" not in snapshot:
            return _fail(
                "source_snapshot_manifest.md does not explain retired-path "
                "display aliases"
            )
        if "D tests/test_external_reviewer_followups.py" in snapshot:
            return _fail(
                "source_snapshot_manifest.md makes the current external "
                "reviewer follow-up test look deleted"
            )
        retired_external_dirty = any(
            "tests/retired-external-reviewer-followups.py" in item
            for item in watched_dirty_paths
        )
        if (
            retired_external_dirty
            and "D tests/retired-external-reviewer-followups.py" not in snapshot
        ):
            return _fail(
                "source_snapshot_manifest.md lacks the retired external-review "
                "test deletion alias"
            )
        if "Final publication gate:" not in snapshot:
            return _fail("source_snapshot_manifest.md lacks final publication gate")
        for snippet in (
            "Final publication checklist:",
            "Final-publication gate blocker breakdown:",
            "`clean_combined_worktree`",
            "`package_tag_at_head`",
            "`versions_consistent`",
            "`unreleased_changelog_finalized`",
            "`source_paths_finalized`",
            "`paper_paths_finalized`",
        ):
            if snippet not in snapshot:
                return _fail(f"source_snapshot_manifest.md lacks {snippet}")
        snapshot_breakdown = snapshot_json.get("release_readiness", {}).get(
            "release_blocker_breakdown"
        )
        if snapshot_breakdown != release_breakdown:
            return _fail(
                "submission_risk_ledger.json final tagged-cut breakdown does "
                "not match source_snapshot_manifest.json"
            )
        snapshot_blockers = re.search(
            r"Final-publication gate blocker paths: `(\d+)`", snapshot
        )
        if audit_blockers and snapshot_blockers:
            if int(audit_blockers.group(1)) != int(snapshot_blockers.group(1)):
                return _fail(
                    "jss_full_audit.md gate_blocker_paths does not match "
                    "source_snapshot_manifest.md"
                )
        snapshot_archive_paths = []
        snapshot = snapshot_payload
        redaction_note = str(snapshot.get("display_path_redaction_note", ""))
        if (
            "Active external-review filenames are omitted" not in redaction_note
            or "retired-external aliases" not in redaction_note
        ):
            return _fail(
                "source_snapshot_manifest.json lacks active/retired external-review note"
            )
        if (
            "D tests/test_external_reviewer_followups.py"
            in snapshot.get("watched_dirty_paths", [])
        ):
            return _fail(
                "source_snapshot_manifest.json marks the current external "
                "reviewer follow-up test as deleted"
            )
        for key in ("hand_edited_dirty_paths", "displayed_generated_dirty_paths"):
            for item in snapshot.get(key, []):
                status, rel = _status_and_path(item)
                if status.startswith("D"):
                    continue
                snapshot_archive_paths.append(rel)
        missing_release_blockers = [
            rel for rel in sorted(set(snapshot_archive_paths))
            if _source_snapshot_archive_required(rel) and rel not in names
        ]
        if missing_release_blockers:
            return _fail(
                "source-snapshot listed paths missing from archive: "
                + ", ".join(sorted(missing_release_blockers)[:20])
            )

    extracted_schema_error = _verify_extracted_schema_bundle()
    if extracted_schema_error:
        return _fail(extracted_schema_error)
    extracted_install_error = _verify_extracted_install_import(
        pyproject_version.group(1)
    )
    if extracted_install_error:
        return _fail(extracted_install_error)

    print(
        f"OK -- verified {ARCHIVE} "
        f"({archive_size_mib:.2f} MiB / {archive_size_mb_decimal:.2f} MB, "
        f"{file_count} files)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

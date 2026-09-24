"""Audit data and generated-result provenance for the JSS archive.

The submission archive contains public extracts, calibrated replicas,
synthetic fixtures, generated parity outputs, schemas, and lockfiles.  This
report makes that boundary explicit for reviewers without claiming that every
CSV is an original-data replication dataset.
"""
from __future__ import annotations

import csv
import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any

import jss_submission_package as package

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
OUT_JSON = RESULTS_DIR / "data_provenance_audit.json"
OUT_MD = RESULTS_DIR / "data_provenance_audit.md"
SOURCE_DATE_EPOCH = os.environ.get("SOURCE_DATE_EPOCH")

DATA_SUFFIXES = {".csv", ".json", ".lock"}
RAW_TABLE_SUFFIXES = {".csv"}
FORBIDDEN_RAW_SUFFIXES = {
    ".dta",
    ".rds",
    ".rda",
    ".sav",
    ".sas7bdat",
    ".xlsx",
    ".xls",
    ".parquet",
    ".feather",
}
HIGH_RISK_PATH_TOKENS = (
    "private",
    "confidential",
    "secret",
    "credential",
    "password",
    "token",
    "proprietary",
)
EXPECTED_SOURCE_DATASETS = {
    "src/statspai/datasets/data/california_prop99.csv",
    "src/statspai/datasets/data/card_1995.csv",
    "src/statspai/datasets/data/lalonde_matchit.csv",
    "src/statspai/datasets/data/lee_2008_senate.csv",
    "src/statspai/datasets/data/nhefs.csv",
    "src/statspai/datasets/data/castle_2013.csv",
    "src/statspai/datasets/data/sasp_panel.csv",
    "src/statspai/datasets/data/texas_prison.csv",
    "src/statspai/datasets/data/thornton_hiv.csv",
}
EXPECTED_ORIGINAL_PARITY_EXTRACTS = {
    "tests/orig_parity/data/01_card_original.csv",
    "tests/orig_parity/data/02_mpdta_original.csv",
    "tests/orig_parity/data/03_basque_original.csv",
    "tests/orig_parity/data/04_lalonde_original.csv",
    "tests/orig_parity/data/04b_nsw_psid_original.csv",
    "tests/orig_parity/data/05_lee_original.csv",
    "tests/orig_parity/data/06_nhefs_ch12_ipw.csv",
}
EXPECTED_R_PARITY_CSV_COUNT = 91

DATA_SOURCE_NOTES = {
    "src/statspai/datasets/data/california_prop99.csv": (
        "Public ADH California Proposition 99 panel bundled for exact "
        "paper replication when simulated=False."
    ),
    "src/statspai/datasets/data/card_1995.csv": (
        "Card (1995) NLSYM extract, matching the package data loader."
    ),
    "src/statspai/datasets/data/lalonde_matchit.csv": (
        "Dehejia-Wahba/MatchIt Lalonde extract used by matching examples."
    ),
    "src/statspai/datasets/data/lee_2008_senate.csv": (
        "Public Lee-style RD Senate extract used for redistribution-safe RD."
    ),
    "src/statspai/datasets/data/nhefs.csv": (
        "Public NHEFS extract from the causaldata/What If g-methods canon."
    ),
    "src/statspai/datasets/data/castle_2013.csv": (
        "Cheng and Hoekstra (2013) castle-doctrine state panel, the "
        "dataset behind chapter 9 of Cunningham's Causal Inference: The "
        "Mixtape; loaded by sp.datasets.castle_doctrine()."
    ),
    "src/statspai/datasets/data/sasp_panel.csv": (
        "Survey of Adult Service Providers session panel from Cunningham "
        "and Kendall's work, redistributed with Causal Inference: The "
        "Mixtape; loaded by sp.datasets.sasp_panel()."
    ),
    "src/statspai/datasets/data/texas_prison.csv": (
        "Texas 1993 prison-capacity expansion panel used in chapter 10 of "
        "Causal Inference: The Mixtape; loaded by "
        "sp.datasets.texas_prison()."
    ),
    "src/statspai/datasets/data/thornton_hiv.csv": (
        "Thornton (2008) HIV-incentive experiment extract redistributed "
        "with Causal Inference: The Mixtape; loaded by "
        "sp.datasets.thornton_hiv()."
    ),
    "tests/orig_parity/data/01_card_original.csv": (
        "R-package Card extract used for original-data parity."
    ),
    "tests/orig_parity/data/02_mpdta_original.csv": (
        "did::mpdta extract used for original-data staggered-DiD parity."
    ),
    "tests/orig_parity/data/03_basque_original.csv": (
        "Synth::basque extract used for original-data SCM parity."
    ),
    "tests/orig_parity/data/04_lalonde_original.csv": (
        "Lalonde experimental extract used for original-data parity."
    ),
    "tests/orig_parity/data/04b_nsw_psid_original.csv": (
        "NSW/PSID comparison extract used for observational matching parity."
    ),
    "tests/orig_parity/data/05_lee_original.csv": (
        "rdrobust::RDsenate public extract used for RD parity."
    ),
    "tests/orig_parity/data/06_nhefs_ch12_ipw.csv": (
        "NHEFS chapter-12 IPW extract used for g-methods parity."
    ),
}


def _generated_at_unix() -> int:
    if SOURCE_DATE_EPOCH is not None:
        return int(SOURCE_DATE_EPOCH)
    return int(time.time())


def _archive_candidate_files() -> list[Path]:
    registry_evidence_files = package._registry_evidence_files()
    source_snapshot_files = package._source_snapshot_listed_files()
    candidates = list(package._iter_files(package.PAPER_INCLUDE_DIRS + package.PAPER_INCLUDE_FILES))
    candidates.extend(package._iter_files(package.ROOT_INCLUDE_DIRS + package.ROOT_INCLUDE_FILES))
    candidates.extend(registry_evidence_files)
    candidates.extend(source_snapshot_files)
    return sorted(
        {
            path.resolve()
            for path in candidates
            if path.exists() and path.is_file() and not package._excluded(path)
        }
    )


def _arcname(path: Path) -> str:
    return package._arcname(path)


def _classify(arcname: str) -> str:
    suffix = Path(arcname).suffix
    if arcname in EXPECTED_SOURCE_DATASETS:
        return "packaged_public_dataset_csv"
    if arcname in EXPECTED_ORIGINAL_PARITY_EXTRACTS:
        return "public_original_extract_csv"
    if arcname.startswith("tests/r_parity/data/") and suffix == ".csv":
        return "same_byte_r_stata_fixture_csv"
    # The option-parity suite (82-87) checks Stata option/convention
    # handling rather than a new estimator, and its fixtures are read by
    # both sides from the same bytes exactly as tests/r_parity/data/ is.
    if arcname.startswith("tests/stata_parity/option_parity/") and suffix == ".csv":
        return "same_byte_r_stata_fixture_csv"
    if arcname.startswith("tests/reference_parity/_fixtures/") and suffix == ".csv":
        return "reference_fixture_csv"
    if arcname.startswith("tests/coverage_monte_carlo/results_b1000/"):
        return "generated_monte_carlo_result_json"
    if arcname.startswith("tests/perf/results/"):
        return "generated_performance_result_json"
    if arcname.startswith("tests/orig_parity/results/"):
        return "generated_original_parity_result_json"
    if arcname.startswith("tests/r_parity/results/"):
        return "generated_r_parity_result_json"
    if arcname.startswith("tests/stata_parity/results/"):
        return "generated_stata_result_json"
    if arcname.startswith("tests/reference_parity/_fixtures/") and suffix == ".json":
        return "reference_result_json"
    if arcname in {
        "tests/r_parity/renv.lock",
        "tests/r_parity/TIER_A_FIXTURE_LOCK.json",
    }:
        return "environment_or_fixture_lock"
    if arcname.startswith("Paper-JSS/replication/results/") and suffix == ".json":
        return "generated_paper_audit_or_example_json"
    if arcname.startswith("schemas/") and suffix == ".json":
        return "schema_bundle_json"
    if arcname.startswith("src/statspai/schemas/") and suffix == ".json":
        return "runtime_schema_bundle_json"
    if suffix == ".json":
        return "other_generated_or_schema_json"
    if suffix == ".lock":
        return "environment_lockfile"
    return "unknown"


def _csv_profile(path: Path) -> dict[str, Any]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            return {"parseable": False, "rows": 0, "columns": 0, "header": []}
        rows = sum(1 for _row in reader)
    return {
        "parseable": True,
        "rows": rows,
        "columns": len(header),
        "header": header[:20],
    }


def _build_payload() -> dict[str, Any]:
    failures: list[str] = []
    candidates = _archive_candidate_files()
    scoped_files = [
        path for path in candidates
        if path.suffix in DATA_SUFFIXES and path.resolve() != OUT_JSON.resolve()
    ]
    forbidden_raw_members = [
        _arcname(path) for path in candidates
        if path.suffix.lower() in FORBIDDEN_RAW_SUFFIXES
    ]
    high_risk_path_hits = [
        _arcname(path) for path in scoped_files
        if any(token in _arcname(path).lower() for token in HIGH_RISK_PATH_TOKENS)
    ]

    rows: list[dict[str, Any]] = []
    csv_failures: list[str] = []
    category_counts: Counter[str] = Counter()
    suffix_counts: Counter[str] = Counter()
    total_bytes = 0
    largest: list[tuple[int, str]] = []
    source_dataset_rows: list[dict[str, Any]] = []

    for path in scoped_files:
        arcname = _arcname(path)
        category = _classify(arcname)
        category_counts[category] += 1
        suffix_counts[path.suffix] += 1
        size = path.stat().st_size
        total_bytes += size
        largest.append((size, arcname))
        profile: dict[str, Any] | None = None
        if path.suffix == ".csv":
            profile = _csv_profile(path)
            if not profile["parseable"] or profile["columns"] <= 0:
                csv_failures.append(arcname)
        row = {
            "path": arcname,
            "category": category,
            "suffix": path.suffix,
            "size_bytes": size,
        }
        if profile:
            row.update(
                {
                    "rows": profile["rows"],
                    "columns": profile["columns"],
                    "header_preview": profile["header"],
                }
            )
        rows.append(row)
        if arcname in DATA_SOURCE_NOTES:
            source_dataset_rows.append(
                {
                    "path": arcname,
                    "category": category,
                    "source_note": DATA_SOURCE_NOTES[arcname],
                    "rows": profile["rows"] if profile else None,
                    "columns": profile["columns"] if profile else None,
                }
            )

    scoped_paths = {row["path"] for row in rows}
    missing_source_datasets = sorted(EXPECTED_SOURCE_DATASETS - scoped_paths)
    missing_original_extracts = sorted(EXPECTED_ORIGINAL_PARITY_EXTRACTS - scoped_paths)
    unknown_category_paths = [
        row["path"] for row in rows
        if row["category"] == "unknown"
    ]
    if missing_source_datasets:
        failures.append(
            "missing packaged public dataset CSVs: "
            + ", ".join(missing_source_datasets)
        )
    if missing_original_extracts:
        failures.append(
            "missing public original-data extract CSVs: "
            + ", ".join(missing_original_extracts)
        )
    if category_counts["same_byte_r_stata_fixture_csv"] != EXPECTED_R_PARITY_CSV_COUNT:
        failures.append(
            "R/Stata same-byte fixture CSV count drifted: "
            f"{category_counts['same_byte_r_stata_fixture_csv']} != "
            f"{EXPECTED_R_PARITY_CSV_COUNT}"
        )
    if forbidden_raw_members:
        failures.append(
            "forbidden raw binary/statistical data members present: "
            + ", ".join(forbidden_raw_members[:20])
        )
    if high_risk_path_hits:
        failures.append(
            "high-risk private/credential path tokens found: "
            + ", ".join(high_risk_path_hits[:20])
        )
    if csv_failures:
        failures.append(
            "CSV files with missing/invalid headers: " + ", ".join(csv_failures[:20])
        )
    if unknown_category_paths:
        failures.append(
            "unclassified data/result members: " + ", ".join(unknown_category_paths[:20])
        )

    summary = {
        "prospective_archive_file_count": len(candidates),
        "scoped_data_file_count": len(scoped_files),
        "csv_file_count": suffix_counts.get(".csv", 0),
        "json_file_count": suffix_counts.get(".json", 0),
        "lockfile_count": suffix_counts.get(".lock", 0),
        "total_data_bytes": total_bytes,
        "largest_data_files": [
            {"path": arcname, "size_bytes": size}
            for size, arcname in sorted(largest, reverse=True)[:10]
        ],
        "category_counts": dict(sorted(category_counts.items())),
        "suffix_counts": dict(sorted(suffix_counts.items())),
        "packaged_public_dataset_csv_count": category_counts[
            "packaged_public_dataset_csv"
        ],
        "public_original_extract_csv_count": category_counts[
            "public_original_extract_csv"
        ],
        "same_byte_r_stata_fixture_csv_count": category_counts[
            "same_byte_r_stata_fixture_csv"
        ],
        "reference_fixture_csv_count": category_counts["reference_fixture_csv"],
        "generated_result_json_count": sum(
            count for category, count in category_counts.items()
            if category.startswith("generated_")
        ),
        "forbidden_raw_member_count": len(forbidden_raw_members),
        "high_risk_path_hit_count": len(high_risk_path_hits),
        "csv_parse_failure_count": len(csv_failures),
        "unknown_category_count": len(unknown_category_paths),
        "self_audit_json_excluded_from_data_counts": True,
    }
    return {
        "generated_at_unix": _generated_at_unix(),
        "status": "PASS" if not failures else "FAIL",
        "scope": (
            "Prospective JSS archive data/result members, using the same "
            "include/exclude rules as jss_submission_package.py. Generated "
            "data_provenance_audit.json is excluded from its own data counts."
        ),
        "summary": summary,
        "source_dataset_rows": sorted(source_dataset_rows, key=lambda row: row["path"]),
        "data_members": sorted(rows, key=lambda row: row["path"]),
        "forbidden_raw_members": forbidden_raw_members,
        "high_risk_path_hits": high_risk_path_hits,
        "csv_failures": csv_failures,
        "unknown_category_paths": unknown_category_paths,
        "failures": failures,
    }


def _write_markdown(payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Data Provenance Audit",
        "",
        f"Status: {payload['status']}",
        "",
        payload["scope"],
        "",
        "## Summary",
        "",
        f"- Prospective archive files: `{summary['prospective_archive_file_count']}`",
        f"- Scoped data/result files: `{summary['scoped_data_file_count']}`",
        f"- CSV files: `{summary['csv_file_count']}`",
        f"- JSON files: `{summary['json_file_count']}`",
        f"- Lockfiles: `{summary['lockfile_count']}`",
        f"- Packaged public dataset CSVs: `{summary['packaged_public_dataset_csv_count']}`",
        f"- Public original-data extract CSVs: `{summary['public_original_extract_csv_count']}`",
        f"- Same-byte R/Stata fixture CSVs: `{summary['same_byte_r_stata_fixture_csv_count']}`",
        f"- Reference fixture CSVs: `{summary['reference_fixture_csv_count']}`",
        f"- Generated result JSON files: `{summary['generated_result_json_count']}`",
        f"- Forbidden raw-data members: `{summary['forbidden_raw_member_count']}`",
        f"- High-risk private/credential path hits: `{summary['high_risk_path_hit_count']}`",
        f"- CSV parse failures: `{summary['csv_parse_failure_count']}`",
        f"- Unknown categories: `{summary['unknown_category_count']}`",
        "",
        "## Boundary",
        "",
        "- Original-data claims are limited to public package extracts and documented public-data rows.",
        "- Calibrated replicas and synthetic fixtures are classified separately from original-data extracts.",
        "- The audit rejects raw binary/statistical data formats such as Stata, RDS, SAS, Excel, parquet, and feather files in the prospective archive.",
        "- The audit rejects private, confidential, secret, credential, password, token, or proprietary path tokens in scoped data/result members.",
        "",
        "## Category Counts",
        "",
        "| Category | Count |",
        "|---|---:|",
    ]
    for category, count in summary["category_counts"].items():
        lines.append(f"| `{category}` | {count} |")
    lines.extend(["", "## Public Source Rows", "", "| Path | Category | Rows | Columns | Source note |", "|---|---|---:|---:|---|"])
    for row in payload["source_dataset_rows"]:
        note = str(row["source_note"]).replace("|", r"\|")
        lines.append(
            "| "
            f"`{row['path']}` | `{row['category']}` | "
            f"{row.get('rows')} | {row.get('columns')} | {note} |"
        )
    lines.extend(["", "## Largest Data/Result Files", "", "| Path | Bytes |", "|---|---:|"])
    for row in summary["largest_data_files"]:
        lines.append(f"| `{row['path']}` | {row['size_bytes']} |")
    lines.append("")
    if payload["failures"]:
        lines.append("Failures:")
        lines.extend(f"- {failure}" for failure in payload["failures"])
    else:
        lines.append("Failures: none")
    lines.extend(["", f"Machine-readable detail: `{OUT_JSON.relative_to(PAPER_DIR)}`"])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = _build_payload()
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(payload)
    print(f"OK -- wrote {OUT_JSON}")
    print(f"OK -- wrote {OUT_MD}")
    if payload["failures"]:
        print("FAIL -- data provenance audit has stale or unsafe archive data evidence")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

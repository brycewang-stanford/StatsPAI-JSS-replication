"""Build a size-checked JSS submission archive.

JSS attachments are size constrained, so the working ``Paper-JSS`` tree
must not be zipped wholesale: ``.git/``, coverage HTML, and the local
reference cache dominate the size and are not needed by reviewers.  This
script creates a reviewer archive that contains the manuscript source,
generated PDF, replication scripts/results, and the StatsPAI source tree
plus validation tests needed to audit the claims.
"""
from __future__ import annotations

import json
import re
import os
import sys
import time
import unicodedata
import zipfile
from pathlib import Path
from typing import Iterable

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:  # _paths.py sits beside this script; importlib loaders do not add the script dir
    sys.path.insert(0, _SCRIPTS_DIR)

from _paths import PAPER_ROOT as _PAPER_ROOT
from _paths import statspai_root as _statspai_root


HERE = Path(__file__).resolve().parent
PAPER_DIR = _PAPER_ROOT
ROOT = _statspai_root()  # see _paths.py: worktree-safe
BUILD_DIR = PAPER_DIR / "build"
ARCHIVE = BUILD_DIR / "statspai-jss-submission.zip"
MANIFEST_JSON = BUILD_DIR / "statspai-jss-submission-manifest.json"
MANIFEST_MD = BUILD_DIR / "statspai-jss-submission-manifest.md"
MAX_ATTACHMENT_MB = 50.0
SOURCE_DATE_EPOCH = int(os.environ.get("SOURCE_DATE_EPOCH", "1780185600"))
FIXED_ZIP_DATETIME = time.gmtime(SOURCE_DATE_EPOCH)[:6]
EVIDENCE_PATH_RE = re.compile(r"(?P<path>(?:tests|scripts|Paper-JSS)/[^\s,;:)`]+\.py)")
ASCII_SOURCE_SUFFIXES = {".py", ".R", ".do", ".sh", ".toml"}
ASCII_DATA_SUFFIXES = {".csv", ".json", ".lock"}

ASCII_TRANSLITERATION = str.maketrans({
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
    "\u2013": "-",
    "\u2014": "--",
    "\u2015": "--",
    "\u2212": "-",
    "\u2026": "...",
    "\u00d7": "x",
    "\u00b7": "*",
    "\u2248": "~",
    "\u2264": "<=",
    "\u2265": ">=",
    "\u2260": "!=",
    "\u2261": "==",
    "\u221e": "inf",
    "\u2208": "in",
    "\u2190": "<-",
    "\u2192": "->",
    "\u2194": "<->",
    "\u21d2": "=>",
    "\u221a": "sqrt",
    "\u2211": "sum",
    "\u222b": "integral",
    "\u2202": "partial",
    "\u22a5": "perp",
    "\u201c": '"',
    "\u201d": '"',
    "\u2018": "'",
    "\u2019": "'",
    "\u00a7": "Section ",
    "\u00b1": "+/-",
    "\u2022": "*",
    "\u26a0": "WARNING",
    "\u2705": "OK",
    "\u2713": "OK",
    "\ufe0f": "",
    "\u2500": "-",
    "\u2501": "-",
    "\u2550": "=",
    "\u2502": "|",
    "\u2503": "|",
    "\u250c": "+",
    "\u2510": "+",
    "\u2514": "+",
    "\u2518": "+",
    "\u251c": "+",
    "\u2524": "+",
    "\u253c": "+",
    "\u2554": "+",
    "\u2557": "+",
    "\u255a": "+",
    "\u255d": "+",
    "\u2551": "|",
    "\u03b1": "alpha",
    "\u03b2": "beta",
    "\u03b3": "gamma",
    "\u03b4": "delta",
    "\u03b5": "epsilon",
    "\u03b7": "eta",
    "\u03b8": "theta",
    "\u03ba": "kappa",
    "\u03bb": "lambda",
    "\u03bc": "mu",
    "\u03bd": "nu",
    "\u03c0": "pi",
    "\u03c1": "rho",
    "\u03c3": "sigma",
    "\u03c4": "tau",
    "\u03c6": "phi",
    "\u03c7": "chi",
    "\u03c8": "psi",
    "\u03c9": "omega",
    "\u0393": "Gamma",
    "\u0394": "Delta",
    "\u03a3": "Sigma",
    "\u03a6": "Phi",
    "\u03a8": "Psi",
    "\u03a9": "Omega",
    "\u2080": "0",
    "\u2081": "1",
    "\u2082": "2",
    "\u2083": "3",
    "\u2084": "4",
    "\u2085": "5",
    "\u2086": "6",
    "\u2087": "7",
    "\u2088": "8",
    "\u2089": "9",
    "\u00b9": "1",
    "\u00b2": "2",
    "\u00b3": "3",
    "\u2070": "0",
    "\u2074": "4",
    "\u2075": "5",
    "\u2076": "6",
    "\u2077": "7",
    "\u2078": "8",
    "\u2079": "9",
    "\u207b": "-",
})


def _generated_at_unix() -> int:
    return SOURCE_DATE_EPOCH


PAPER_INCLUDE_DIRS = [
    PAPER_DIR / "manuscript" / "sections",
    PAPER_DIR / "manuscript" / "tables",
    PAPER_DIR / "manuscript" / "figures",
    PAPER_DIR / "replication",
]

PAPER_INCLUDE_FILES = [
    PAPER_DIR / "Makefile",
    PAPER_DIR / "requirements-jss.txt",
    PAPER_DIR / "README.md",
    PAPER_DIR / "cover-letter.md",
    PAPER_DIR / "JOSS-JSS-OVERLAP.md",
    PAPER_DIR / "REVIEWER-HARDENING-AUDIT.md",
    PAPER_DIR / "manuscript" / "main.tex",
    PAPER_DIR / "manuscript" / "main.pdf",
    PAPER_DIR / "manuscript" / "generated_claims.tex",
    PAPER_DIR / "manuscript" / "README.md",
    PAPER_DIR / "manuscript" / "jss.cls",
    PAPER_DIR / "manuscript" / "jss.bst",
    PAPER_DIR / "manuscript" / "jss-bib.bib",
    PAPER_DIR / "manuscript" / "jsslogo.jpg",
]

ACTIVE_MANUSCRIPT_SECTION_FILES = {
    PAPER_DIR / "manuscript" / "sections" / name
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
        # The parity appendix, compiled into main.tex since the full
        # Track A ledger moved out of the archive and into the PDF.
        "appendix.tex",
    )
}

INACTIVE_MANUSCRIPT_SECTION_FILES = {
    PAPER_DIR / "manuscript" / "sections" / name
    for name in (
        "01-introduction.tex",
        "02-architecture.tex",
        "03-agent-facing.tex",
        "04-examples.tex",
        "05-parity.tex",
        "08-computational-details.tex",
        "09-discussion.tex",
    )
}

ROOT_INCLUDE_DIRS = [
    ROOT / "src",
    ROOT / "schemas",
    ROOT / "tests" / "reference_parity",
    ROOT / "tests" / "external_parity",
    ROOT / "tests" / "coverage_monte_carlo",
    ROOT / "tests" / "r_parity",
    ROOT / "tests" / "stata_parity",
    ROOT / "tests" / "orig_parity",
    ROOT / "tests" / "perf",
]

PAPER_EXTRA_INCLUDE_FILES = [
    PAPER_DIR / "parity" / "replacement-table.md",
    PAPER_DIR / "replication" / "scripts" / "build_replacement_table.py",
]

ROOT_INCLUDE_FILES = [
    ROOT / "pyproject.toml",
    ROOT / "LICENSE",
    ROOT / "CITATION.cff",
    ROOT / "README.md",
    ROOT / "CHANGELOG.md",
    ROOT / "MIGRATION.md",
    ROOT / "tests" / "conftest.py",
    ROOT / "tests" / "test_api_stable_evidence.py",
    ROOT / "tests" / "test_jss_reproduction_environment.py",
    ROOT / "tests" / "test_jss_formal_compliance.py",
    ROOT / "tests" / "test_jss_manuscript_artifacts.py",
    ROOT / "tests" / "test_jss_validation_api.py",
    ROOT / "tests" / "test_jss_release_manifest.py",
    ROOT / "tests" / "test_augsynth_backend.py",
    ROOT / "tests" / "test_gsynth_backend.py",
    ROOT / "tests" / "test_honest_did_backend.py",
    ROOT / "tests" / "test_sdid_backend.py",
    ROOT / "tests" / "test_synth_backend.py",
    ROOT / "tests" / "test_rddensity_io.py",
    ROOT / "tests" / "test_stability_audit.py",
    ROOT / "tests" / "test_schema_export.py",
    ROOT / "scripts" / "dump_schemas.py",
    ROOT / "scripts" / "schema_quality.py",
    ROOT / "scripts" / "stability_audit.py",
    ROOT / "scripts" / "registry_stats.py",
    ROOT / "docs" / "index.md",
    ROOT / "docs" / "getting-started.md",
    ROOT / "docs" / "guides" / "migration-from-r.md",
    ROOT / "docs" / "guides" / "stability.md",
    ROOT / "docs" / "jss_source_audit_dossier.md",
    ROOT / "docs" / "reference" / "index.md",
]

EXCLUDED_PARTS = {
    ".git",
    ".github",
    "ci",
    ".pytest_cache",
    "__pycache__",
    "StatsPAI.egg-info",
    ".mypy_cache",
    ".ruff_cache",
    "100-emails",
    "htmlcov",
    # Scratch output of the three reproducibility verifiers:
    # verify_reproduce.py (R), verify_reproduce_py.py (StatsPAI, staged
    # under _repro_check/py/) and verify_reproduce_stata.py re-derive each
    # golden into a staging dir so the committed artifact is never
    # clobbered. The staging copies are transient duplicates of evidence
    # the archive already carries, and they are gitignored, so a reviewer
    # who runs the verifiers should not see the archive's file count and
    # size move underneath them. Every verifier stages *inside* this one
    # directory so this single rule covers all of them.
    "_repro_check",
    # Third-party Stata ado files that tests/stata_parity/86_fect.do installs
    # from GitHub into a local, gitignored adopath (fect_stata plus the SSC
    # helper _gwtmean). The do-file re-installs them on demand, so the archive
    # carries our driver, not a vendored copy of someone else's package.
    "_ado_fect",
    "notes",
    "parity",
    "references",
    "build",
}

EXCLUDED_SUFFIXES = {
    ".aux",
    ".blg",
    ".fdb_latexmk",
    ".fls",
    ".log",
    ".out",
    ".zip",
    ".pyc",
}

EXCLUDED_NAMES = {
    ".DS_Store",
    ".gitignore",
}

ACTIVE_EXTERNAL_REVIEW_FILES = {
    ROOT / "paper.md",
    ROOT / "docs" / ("jo" "ss_reviewer_guide.md"),
    ROOT / "docs" / ("jo" "ss_validation_dossier.md"),
}
ACTIVE_EXTERNAL_REVIEW_FILE_REASONS = {
    "paper.md": "active short software paper for the separate review",
    "docs/jo" "ss_reviewer_guide.md": "active reviewer guide for the separate review",
    "docs/jo" "ss_validation_dossier.md": (
        "active validation dossier for the separate review"
    ),
}

EXCLUDED_FILES = {
    # JOSS-facing root documents stay out of the JSS archive even when the
    # source-snapshot manifest lists them as hand-edited (dirty) paths.
    ROOT / "README_CN.md",
    ROOT / "docs" / "joss_reviewer_guide.md",
    ROOT / "docs" / "joss_validation_dossier.md",
    PAPER_DIR / "DRAFT-NOTES.md",
    PAPER_DIR / "JSS-research-plan.md",
    PAPER_DIR / "JSS-1.30-SUBMISSION-PLAN.md",
    PAPER_DIR / "NEXT-STEPS.md",
    PAPER_DIR / "REVIEW-IMPROVEMENTS.md",
    PAPER_DIR / "REVIEW-ROUND2-HARSH-OPUS.md",
    PAPER_DIR / "_convert_to_pdf.py",
    PAPER_DIR / "_table_style.tex",
    PAPER_DIR / "build_zh.sh",
    PAPER_DIR / "colab_gpu_bench.ipynb",
    PAPER_DIR / "md2pdf.py",
    PAPER_DIR / "md_to_pdf.py",
    PAPER_DIR / "manuscript" / "main.md",
    PAPER_DIR / "manuscript" / "main-zh-header.tex",
    PAPER_DIR / "manuscript" / "main-zh.md",
    PAPER_DIR / "manuscript" / "main-zh-raster.pdf",
    PAPER_DIR / "manuscript" / "main-zh.pdf",
    PAPER_DIR / "manuscript" / "\u8bc4\u5ba1\u610f\u89c1-\u4e2d\u6587.md",
} | INACTIVE_MANUSCRIPT_SECTION_FILES | ACTIVE_EXTERNAL_REVIEW_FILES


def _registry_evidence_files() -> list[Path]:
    """Return concrete source files referenced by registry evidence notes."""
    sys.path.insert(0, str(ROOT / "src"))
    import statspai as sp  # noqa: WPS433

    sp.list_functions()  # force lazy registry population and evidence hooks
    from statspai.registry import _REGISTRY  # noqa: WPS433

    files: set[Path] = set()
    missing: set[str] = set()
    for spec in _REGISTRY.values():
        for note in list(getattr(spec, "validation_notes", []) or []):
            for match in EVIDENCE_PATH_RE.finditer(note):
                rel = match.group("path")
                path = ROOT / rel
                if path.exists():
                    files.add(path)
                else:
                    missing.add(rel)
    if missing:
        missing_list = ", ".join(sorted(missing)[:20])
        raise FileNotFoundError(
            "registry evidence notes reference missing files: "
            f"{missing_list}"
        )
    return sorted(files)


def _source_snapshot_listed_files() -> list[Path]:
    """Return existing files listed in the source-snapshot manifest."""
    path = PAPER_DIR / "replication" / "results" / "source_snapshot_manifest.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    files: set[Path] = set()
    snapshot = data.get("jss_source_snapshot", {})
    for key in ("hand_edited_dirty_paths", "displayed_generated_dirty_paths"):
        for item in snapshot.get(key, []):
            if " " not in item:
                continue
            status, rel = item.split(" ", 1)
            if status.startswith("D"):
                continue
            if rel.startswith("Paper-JSS/"):
                candidate = PAPER_DIR / rel.removeprefix("Paper-JSS/")
            else:
                candidate = ROOT / rel
            if candidate.exists() and candidate.is_file():
                files.add(candidate)
    return sorted(files)


def _iter_files(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if not path.exists():
            continue
        if path.is_file():
            yield path
        else:
            for child in path.rglob("*"):
                if child.is_file():
                    yield child


# ``parity`` is in EXCLUDED_PARTS because that directory used to hold
# hand-maintained worklog drafts. It now also holds one generated,
# drift-checked artifact -- the audit-grade replacement table, regenerated by
# replication/scripts/build_replacement_table.py and checked by the full
# audit -- which is exactly the "existing implementations and comparative
# scope" evidence JSS asks for, so that one file is re-admitted by name.
PARITY_INCLUDE_FILES = {
    PAPER_DIR / "parity" / "replacement-table.md",
}


def _excluded(path: Path) -> bool:
    if path in PARITY_INCLUDE_FILES:
        return False
    if any(part in EXCLUDED_PARTS for part in path.parts):
        return True
    if (
        path.parent == ROOT / "tests" / "r_parity"
        and (
            path.name.startswith("PARITY_WORKLOG_")
            or path.name.startswith("PARITY_TEST_WORKLOG_")
        )
        and path.suffix == ".md"
    ):
        return True
    if path in EXCLUDED_FILES:
        return True
    if (
        PAPER_DIR / "manuscript" in path.parents
        and path.suffix.lower() in {".md", ".pdf", ".tex"}
        and any(token in path.name for token in ("\u8bc4\u5ba1", "\u4e2d\u6587"))
    ):
        return True
    if path.name in EXCLUDED_NAMES:
        return True
    if path.suffix in EXCLUDED_SUFFIXES:
        return True
    return False


def _arcname(path: Path) -> str:
    if path.is_relative_to(PAPER_DIR):
        return str(Path("Paper-JSS") / path.relative_to(PAPER_DIR))
    return str(path.relative_to(ROOT))


def _ascii_source_bytes(path: Path) -> tuple[bytes | None, bool]:
    """Return ASCII-normalized source bytes for the JSS archive if needed."""
    if path.suffix not in ASCII_SOURCE_SUFFIXES:
        return None, False
    data = path.read_bytes()
    try:
        data.decode("ascii")
        return None, False
    except UnicodeDecodeError:
        text = data.decode("utf-8")
    text = text.replace("\u5f85\u6838\u9a8c", "pending verification")
    text = text.translate(ASCII_TRANSLITERATION)
    text = unicodedata.normalize("NFKD", text)
    return text.encode("ascii", "ignore"), True


def _jss_archive_root_readme_bytes() -> bytes:
    """Return a JSS-safe root README for the submission archive only."""
    text = """# StatsPAI JSS Source Snapshot

This root README is generated only for the JSS submission archive. It keeps
`pyproject.toml` installable while avoiding the live repository README's
separate active software-review navigation.

For this archive, start with:

- `Paper-JSS/README.md` for reviewer commands and replication tiers.
- `Paper-JSS/manuscript/main.pdf` for the JSS manuscript.
- `Paper-JSS/cover-letter.md` for submission disclosures.
- `docs/jss_source_audit_dossier.md` for the package-facing source audit.
- `Paper-JSS/build/statspai-jss-submission-manifest.md` next to this zip
  for the archive member list, generated metadata files, and active
  external-review exclusions.

Minimal reviewer check from the extracted archive root:

```bash
cd Paper-JSS
make reproduce-jss PYTHON=../.venv/bin/python
make audit PYTHON=../.venv/bin/python
```

The JSS manuscript uses a validation-tiered claim: certified and validated
registry entries have explicit evidence, while API-stable breadth is not
presented as numerical validation.

The active external-review materials (`paper.md` and `docs/joss_*`) are
intentionally not included in this archive.
"""
    return text.encode("ascii")


def _jss_archive_citation_bytes() -> bytes:
    """Return citation metadata without active external-review placeholders."""
    text = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    marker = "# When the JO" "SS paper is accepted"
    if marker in text:
        text = text.split(marker, 1)[0].rstrip() + "\n"
    # The archive is ASCII by contract; the root file's comments may use
    # typographic dashes. Transliterate rather than fail the package build.
    text = text.replace("\u2014", "--").replace("\u2013", "-")
    return text.encode("ascii")


def _zip_info(path: Path, arcname: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo.from_file(path, arcname)
    info.date_time = FIXED_ZIP_DATETIME
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def main() -> int:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    if ARCHIVE.exists():
        ARCHIVE.unlink()

    registry_evidence_files = _registry_evidence_files()
    source_snapshot_listed_files = _source_snapshot_listed_files()
    candidates = list(_iter_files(PAPER_INCLUDE_DIRS + PAPER_INCLUDE_FILES))
    candidates.extend(_iter_files(PAPER_EXTRA_INCLUDE_FILES))
    candidates.extend(_iter_files(ROOT_INCLUDE_DIRS + ROOT_INCLUDE_FILES))
    candidates.extend(registry_evidence_files)
    candidates.extend(source_snapshot_listed_files)
    files = sorted({path.resolve() for path in candidates if not _excluded(path)})
    registry_evidence_rel = sorted(
        str(path.relative_to(ROOT))
        for path in registry_evidence_files
        if not _excluded(path)
    )

    ascii_normalized_source_files: list[str] = []
    jss_archive_generated_files: list[str] = []
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            arcname = _arcname(path)
            if path == ROOT / "README.md":
                jss_archive_generated_files.append(arcname)
                zf.writestr(_zip_info(path, arcname), _jss_archive_root_readme_bytes())
                continue
            if path in {
                ROOT / "CITATION.cff",
                ROOT / "src" / "statspai" / "CITATION.cff",
            }:
                jss_archive_generated_files.append(arcname)
                zf.writestr(_zip_info(path, arcname), _jss_archive_citation_bytes())
                continue
            normalized, changed = _ascii_source_bytes(path)
            if changed and normalized is not None:
                ascii_normalized_source_files.append(arcname)
                zf.writestr(_zip_info(path, arcname), normalized)
            else:
                zf.writestr(_zip_info(path, arcname), path.read_bytes())

    size_bytes = ARCHIVE.stat().st_size
    size_mib = size_bytes / (1024 * 1024)
    size_mb_decimal = size_bytes / 1_000_000
    source_snapshot = PAPER_DIR / "replication" / "results" / "source_snapshot_manifest.json"
    source_snapshot_summary = None
    if source_snapshot.exists():
        data = json.loads(source_snapshot.read_text(encoding="utf-8"))
        source_snapshot_summary = {
            "package_metadata_version": data.get("package_metadata_version"),
            "source_init_version": data.get("source_init_version"),
            "schema_bundle_version": data.get("schema_bundle_version"),
            "package_source_short_commit": data.get("package_git", {}).get("short_commit")
            or data.get("git", {}).get("short_commit"),
            "paper_short_commit": data.get("paper_git", {}).get("short_commit"),
            "is_clean": data.get("git", {}).get("is_clean"),
            "contains_unreleased_source_changes": data.get("jss_source_snapshot", {}).get(
                "contains_unreleased_source_changes"
            ),
            "ready_for_final_publication": data.get("release_readiness", {}).get(
                "ready_for_final_publication"
            ),
            "release_blocker_count": data.get("release_readiness", {}).get(
                "release_blocker_count"
            ),
            "unreleased_changelog_nonempty": data.get("release_readiness", {}).get(
                "unreleased_changelog_nonempty"
            ),
        }
    manifest = {
        "generated_at_unix": _generated_at_unix(),
        "source_date_epoch": SOURCE_DATE_EPOCH,
        "zip_member_datetime": list(FIXED_ZIP_DATETIME),
        "archive": str(ARCHIVE),
        "size_bytes": size_bytes,
        "size_mb": round(size_mib, 2),
        "size_mib": round(size_mib, 2),
        "size_mb_decimal": round(size_mb_decimal, 2),
        "max_attachment_mb": MAX_ATTACHMENT_MB,
        "within_jss_attachment_limit": (
            size_mib <= MAX_ATTACHMENT_MB
            and size_mb_decimal <= MAX_ATTACHMENT_MB
        ),
        "file_count": len(files),
        "included_roots": [
            "Paper-JSS/manuscript",
            "Paper-JSS/replication",
            "src/statspai",
            "root final-publication-gate paths listed by source_snapshot_manifest",
            "generated artifacts listed by source_snapshot_manifest",
            "tests/{test_api_stable_evidence.py,test_augsynth_backend.py,test_gsynth_backend.py,test_honest_did_backend.py,test_jss_formal_compliance.py,test_jss_manuscript_artifacts.py,test_jss_reproduction_environment.py,test_jss_validation_api.py,test_jss_release_manifest.py,test_rddensity_io.py,test_sdid_backend.py,test_synth_backend.py,test_stability_audit.py}",
            "tests/{reference_parity,external_parity,coverage_monte_carlo,r_parity,stata_parity,orig_parity,perf}",
        ],
        "active_manuscript_sections": [
            _arcname(path)
            for path in sorted(ACTIVE_MANUSCRIPT_SECTION_FILES)
        ],
        "registry_evidence_file_count": len(registry_evidence_rel),
        "registry_evidence_files": registry_evidence_rel,
        "ascii_source_suffixes": sorted(ASCII_SOURCE_SUFFIXES),
        "ascii_data_suffixes": sorted(ASCII_DATA_SUFFIXES),
        "ascii_normalized_source_file_count": len(ascii_normalized_source_files),
        "ascii_normalized_source_files": sorted(ascii_normalized_source_files),
        "jss_archive_generated_files": sorted(jss_archive_generated_files),
        "active_external_review_artifacts_excluded": sorted(
            ACTIVE_EXTERNAL_REVIEW_FILE_REASONS
        ),
        "active_external_review_artifact_reasons": (
            ACTIVE_EXTERNAL_REVIEW_FILE_REASONS
        ),
        "excluded": sorted(EXCLUDED_PARTS),
        "excluded_names": sorted(EXCLUDED_NAMES),
        "excluded_files": [
            "Paper-JSS/DRAFT-NOTES.md",
            "Paper-JSS/JSS-1.30-SUBMISSION-PLAN.md",
            "Paper-JSS/JSS-research-plan.md",
            "Paper-JSS/NEXT-STEPS.md",
            "Paper-JSS/REVIEW-IMPROVEMENTS.md",
            "Paper-JSS/REVIEW-ROUND2-HARSH-OPUS.md",
            "Paper-JSS/_convert_to_pdf.py",
            "Paper-JSS/_table_style.tex",
            "Paper-JSS/build_zh.sh",
            "Paper-JSS/colab_gpu_bench.ipynb",
            "Paper-JSS/md2pdf.py",
            "Paper-JSS/md_to_pdf.py",
            "Paper-JSS/manuscript/main.md",
            "Paper-JSS/manuscript/main-zh-header.tex",
            "Paper-JSS/manuscript/main-zh.md",
            "Paper-JSS/manuscript/main-zh-raster.pdf",
            "Paper-JSS/manuscript/main-zh.pdf",
            "Paper-JSS/manuscript/\u8bc4\u5ba1\u610f\u89c1-\u4e2d\u6587.md",
            "README_CN.md",
        ]
        + [
            _arcname(path)
            for path in sorted(INACTIVE_MANUSCRIPT_SECTION_FILES)
        ],
        "source_snapshot": source_snapshot_summary,
    }
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    lines = [
        "# StatsPAI JSS Submission Package",
        "",
        f"Archive: `{ARCHIVE.name}`",
        (
            f"Size: {size_mib:.2f} MiB "
            f"({size_mb_decimal:.2f} MB decimal) / {MAX_ATTACHMENT_MB:.0f} MB"
        ),
        f"Files: {len(files)}",
        f"Within JSS attachment limit: {manifest['within_jss_attachment_limit']}",
        "",
        "Included roots:",
    ]
    lines.extend(f"- `{item}`" for item in manifest["included_roots"])
    lines.extend(
        [
            "",
            "Registry evidence files:",
            f"- {manifest['registry_evidence_file_count']} files referenced by registry validation notes",
            "",
            "JSS ASCII source-code normalization:",
            f"- {manifest['ascii_normalized_source_file_count']} source/build files normalized inside the archive",
            f"- suffixes checked: {', '.join(manifest['ascii_source_suffixes'])}",
            f"- data/result suffixes verified by package checker: {', '.join(manifest['ascii_data_suffixes'])}",
            "",
            "JSS archive generated files:",
            f"- {len(manifest['jss_archive_generated_files'])} root/package metadata files generated specifically for the JSS archive",
        ]
    )
    lines.extend(
        [
            "",
            "Active external-review artifacts excluded:",
        ]
    )
    lines.extend(
        f"- `{item}` -- {manifest['active_external_review_artifact_reasons'][item]}"
        for item in manifest["active_external_review_artifacts_excluded"]
    )
    lines.extend(["", "Excluded working-tree bulk:"])
    lines.extend(f"- `{item}`" for item in manifest["excluded"])
    lines.extend(["", "Excluded control files:"])
    lines.extend(f"- `{item}`" for item in manifest["excluded_names"])
    lines.extend(["", "Excluded historical/convenience drafts:"])
    lines.extend(f"- `{item}`" for item in manifest["excluded_files"])
    if source_snapshot_summary:
        lines.extend(
            [
                "",
                "Source snapshot:",
                f"- package metadata version: `{source_snapshot_summary['package_metadata_version']}`",
                f"- source `__version__`: `{source_snapshot_summary['source_init_version']}`",
                f"- schema bundle version: `{source_snapshot_summary['schema_bundle_version']}`",
                f"- package-source git commit: `{source_snapshot_summary['package_source_short_commit']}`",
                f"- Paper-JSS git commit: `{source_snapshot_summary['paper_short_commit']}`",
                f"- clean working tree: `{source_snapshot_summary['is_clean']}`",
                f"- contains unreleased source changes: `{source_snapshot_summary['contains_unreleased_source_changes']}`",
                f"- ready for final publication release: `{source_snapshot_summary['ready_for_final_publication']}`",
                f"- final-publication gate blocker paths: `{source_snapshot_summary['release_blocker_count']}`",
                f"- unreleased CHANGELOG nonempty: `{source_snapshot_summary['unreleased_changelog_nonempty']}`",
            ]
        )
    MANIFEST_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        f"OK -- wrote {ARCHIVE} "
        f"({size_mib:.2f} MiB / {size_mb_decimal:.2f} MB, {len(files)} files)"
    )
    print(f"OK -- wrote {MANIFEST_JSON}")
    print(f"OK -- wrote {MANIFEST_MD}")
    if not manifest["within_jss_attachment_limit"]:
        print(
            f"FAIL -- archive exceeds {MAX_ATTACHMENT_MB:.0f} MB JSS attachment limit",
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

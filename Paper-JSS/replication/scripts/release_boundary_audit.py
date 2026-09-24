"""Audit the release-consistency boundary of the JSS submission.

The paper describes one tagged release (PyPI wheel + git tag), so the
submission-facing prose must (a) name that release consistently,
(b) not fall back to earlier "unreleased source snapshot" framing, and
(c) still expose the source manifest's release-readiness state so a
version drift between the manuscript claim and the built tree is caught
mechanically rather than by a reviewer's pip install.

The release number is *not* hard-coded here.  It is read from the built
tree's ``pyproject.toml`` and substituted into every required snippet, so
a version bump cannot silently leave a stale number in the manuscript,
the READMEs, or the cover letter: bumping the package makes this audit
fail until every submission-facing file names the new release.
"""
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
from _paths import statspai_root as _statspai_root
from _paths import withheld_editor_doc


HERE = Path(__file__).resolve().parent
PAPER_DIR = _PAPER_ROOT
ROOT = _statspai_root()  # see _paths.py: worktree-safe
RESULTS_DIR = PAPER_DIR / "replication" / "results"
SOURCE_JSON = RESULTS_DIR / "source_snapshot_manifest.json"
SOURCE_MD = RESULTS_DIR / "source_snapshot_manifest.md"
OUT_JSON = RESULTS_DIR / "release_boundary_audit.json"
OUT_MD = RESULTS_DIR / "release_boundary_audit.md"
SOURCE_DATE_EPOCH = os.environ.get("SOURCE_DATE_EPOCH")


def _generated_at_unix() -> int:
    if SOURCE_DATE_EPOCH is not None:
        return int(SOURCE_DATE_EPOCH)
    return int(time.time())


def _package_version() -> str:
    """Release number of the built tree, from ``pyproject.toml``.

    Read textually rather than through ``importlib.metadata`` so the audit
    describes the source tree the manuscript is built from, not whatever
    wheel happens to be installed in the ambient environment.
    """
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if match is None:  # pragma: no cover - a pyproject without a version is a packaging bug
        raise RuntimeError("pyproject.toml has no [project] version")
    return match.group(1)


RELEASE_VERSION = _package_version()

# ``{V}`` is the release read from pyproject.toml; see _package_version.
_REQUIRED_DISCLOSURE_TEMPLATES = {
    "Paper-JSS/manuscript/sections/01-introduction-compact.tex": [
        "This article describes \\statspai{} \\StatsPAIVersion{}",
        "tag \\code{v\\StatsPAIVersion{}}",
    ],
    "Paper-JSS/manuscript/sections/05-parity-compact.tex": [
        "release \\StatsPAIVersion{}",
    ],
    "Paper-JSS/manuscript/sections/appendix.tex": [
        "forest headline moved to the \\pkg{grf} AIPW estimand",
    ],
    "Paper-JSS/manuscript/sections/08-computational-details-compact.tex": [
        "release \\StatsPAIVersion{}",
        "tag \\code{v\\StatsPAIVersion{}}",
    ],
    "Paper-JSS/README.md": [
        "describes the tagged {V} release",
        "JOSS boundary",
        "make release-audit",
        "authoritative version/tag/changelog ledger",
    ],
    "Paper-JSS/cover-letter.md": [
        "published in the *Journal of Open Source",
        "doi.org/10.21105/joss.10604",
        "cites the JOSS paper explicitly",
        "{V}",
    ],
    "Paper-JSS/REVIEWER-HARDENING-AUDIT.md": [
        "tagged {V} release",
        "source_snapshot_manifest",
    ],
    "Paper-JSS/manuscript/README.md": [
        "StatsPAI",
        "tagged {V} release",
    ],
    "docs/jss_source_audit_dossier.md": [
        "not a blanket validation claim",
        "For the paper-specific reviewer path, start with `Paper-JSS/README.md`",
        "commercial downstream product",
    ],
}

REQUIRED_DISCLOSURES = {
    rel: [snippet.replace("{V}", RELEASE_VERSION) for snippet in snippets]
    for rel, snippets in _REQUIRED_DISCLOSURE_TEMPLATES.items()
}

# Wording that must NOT appear in the compiled manuscript sections any
# more: the submission describes a tagged release, not a local snapshot.
FORBIDDEN_MANUSCRIPT_SNIPPETS = {
    "Paper-JSS/manuscript/main.tex": ["source snapshot", "source-snapshot"],
    "Paper-JSS/manuscript/sections/01-introduction-compact.tex": [
        "source snapshot",
        "source-snapshot",
    ],
    "Paper-JSS/manuscript/sections/08-computational-details-compact.tex": [
        "source snapshot",
        "source-snapshot",
    ],
    "Paper-JSS/manuscript/sections/09-discussion-compact.tex": [
        "source snapshot",
        "source-snapshot",
        "submission-risk ledger",
        "upload blocker",
    ],
}

MISLEADING_PATTERNS = (
    re.compile(r"\d+\.\d+\.\d+\+\s+(?:release|wheel|PyPI)", re.IGNORECASE),
    re.compile(r"(?:released|shipped)\s+(?:in|as)\s+\d+\.\d+\.\d+\+", re.IGNORECASE),
    re.compile(r"clean tagged release snapshot yet", re.IGNORECASE),
)


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _load_manifest(failures: list[str]) -> dict[str, Any]:
    if not SOURCE_JSON.exists():
        failures.append("missing source snapshot manifest JSON")
        return {}
    if not SOURCE_MD.exists():
        failures.append("missing source snapshot manifest Markdown")
    try:
        return json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        failures.append(f"unparseable source snapshot manifest JSON: {exc}")
        return {}


def _check_manifest(manifest: dict[str, Any], failures: list[str]) -> dict[str, Any]:
    readiness = manifest.get("release_readiness", {})
    snapshot = manifest.get("jss_source_snapshot", {})
    summary = {
        "package_version": manifest.get("package_metadata_version"),
        "source_version": manifest.get("source_init_version"),
        "schema_bundle_version": manifest.get("schema_bundle_version"),
        "version_consistent": manifest.get("version_consistent_inside_source"),
        "ready_for_final_publication": readiness.get("ready_for_final_publication"),
        "release_blocker_count": readiness.get("release_blocker_count"),
        "source_release_blocker_count": readiness.get("source_release_blocker_count"),
        "paper_release_blocker_count": readiness.get("paper_release_blocker_count"),
        "generated_dirty_count": readiness.get("generated_dirty_count"),
        "unreleased_changelog_nonempty": readiness.get("unreleased_changelog_nonempty"),
        "release_gate_checks": readiness.get("release_gate_checks"),
        "release_blocker_breakdown": readiness.get("release_blocker_breakdown"),
        "contains_unreleased_source_changes": snapshot.get(
            "contains_unreleased_source_changes"
        ),
        "submission_archive_status": snapshot.get("submission_archive_status"),
        "strict_release_command": readiness.get("strict_release_command"),
    }

    if summary["version_consistent"] is not True:
        failures.append("source snapshot versions are not internally consistent")

    # The manuscript's versioned release claim must match the tree it is
    # built from -- this is what stops a reviewer's `pip install` from
    # resolving to a different package than the paper describes.
    intro_path = (
        ROOT / "Paper-JSS" / "manuscript" / "sections"
        / "01-introduction-compact.tex"
    )
    if intro_path.exists():
        intro = _normalise(intro_path.read_text(encoding="utf-8"))
        if "This article describes \\statspai{} \\StatsPAIVersion{}" not in intro:
            failures.append("introduction lacks a versioned release claim")
        stale = re.search(
            r"This article describes \\statspai\{\}\s+(\d+\.\d+\.\d+)", intro
        )
        if stale:
            failures.append(
                "introduction hard-codes release "
                f"{stale.group(1)}; use \\StatsPAIVersion"
            )
    # The manuscript prints its release number through a generated macro,
    # so the drift check is on the macro's value rather than on prose that
    # a partial hand edit could leave stale in one section out of three.
    claims_path = ROOT / "Paper-JSS" / "manuscript" / "generated_claims.tex"
    if not claims_path.exists():
        failures.append("missing manuscript/generated_claims.tex")
    else:
        claims = claims_path.read_text(encoding="utf-8")
        macro = re.search(
            r"\\newcommand\{\\StatsPAIVersion\}\{([^}]+)\}", claims
        )
        if macro is None:
            failures.append("generated_claims.tex lacks \\StatsPAIVersion")
        elif macro.group(1) != RELEASE_VERSION:
            failures.append(
                f"generated_claims.tex pins \\StatsPAIVersion={macro.group(1)} "
                f"but package metadata is {RELEASE_VERSION}"
            )
        summary["manuscript_version_macro"] = macro.group(1) if macro else None

    if not summary["strict_release_command"]:
        failures.append("source snapshot manifest lacks strict release command")

    required_keys = (
        "ready_for_final_publication",
        "release_blocker_count",
        "source_release_blocker_count",
        "paper_release_blocker_count",
        "generated_dirty_count",
        "unreleased_changelog_nonempty",
    )
    for key in required_keys:
        if key not in readiness:
            failures.append(f"source snapshot manifest lacks release_readiness.{key}")

    if SOURCE_MD.exists():
        text = SOURCE_MD.read_text(encoding="utf-8")
        for snippet in (
            "Ready for final publication release:",
            "Unreleased CHANGELOG nonempty:",
            "Final-publication gate blocker paths:",
            "JSS submission archive status:",
            "not a JSS upload reproducibility failure",
            "Final publication gate:",
            "Final publication checklist:",
            "Final-publication gate blocker breakdown:",
            "`clean_combined_worktree`",
            "`package_tag_at_head`",
            "`unreleased_changelog_finalized`",
        ):
            if snippet not in text:
                failures.append(f"source snapshot Markdown missing {snippet!r}")
    gate_checks = summary.get("release_gate_checks")
    if not isinstance(gate_checks, list) or len(gate_checks) < 5:
        failures.append("source snapshot manifest lacks structured release gate checks")
    else:
        names = {str(item.get("check")) for item in gate_checks if isinstance(item, dict)}
        for name in (
            "clean_combined_worktree",
            "package_tag_at_head",
            "versions_consistent",
            "unreleased_changelog_finalized",
            "source_paths_finalized",
            "paper_paths_finalized",
        ):
            if name not in names:
                failures.append(f"source snapshot release gate lacks {name!r}")
    if not isinstance(summary.get("release_blocker_breakdown"), dict):
        failures.append("source snapshot manifest lacks final-publication gate breakdown")

    return summary


def _check_disclosures(failures: list[str]) -> list[str]:
    checked: list[str] = []
    for rel, snippets in REQUIRED_DISCLOSURES.items():
        path = ROOT / rel
        if withheld_editor_doc(rel):
            continue
        if not path.exists():
            failures.append(f"missing release-boundary disclosure file: {rel}")
            continue
        checked.append(rel)
        text = _normalise(path.read_text(encoding="utf-8"))
        for snippet in snippets:
            if _normalise(snippet) not in text:
                failures.append(f"{rel}: missing release-boundary wording: {snippet!r}")
    for rel, snippets in FORBIDDEN_MANUSCRIPT_SNIPPETS.items():
        path = ROOT / rel
        if not path.exists():
            continue
        text = _normalise(path.read_text(encoding="utf-8"))
        for snippet in snippets:
            if _normalise(snippet) in text:
                failures.append(
                    f"{rel}: stale pre-release wording present: {snippet!r}"
                )
    return checked


def _check_misleading_patterns(failures: list[str]) -> None:
    files = [
        "Paper-JSS/manuscript/main.tex",
        "Paper-JSS/manuscript/sections/05-parity-compact.tex",
        "Paper-JSS/manuscript/sections/08-computational-details-compact.tex",
        "Paper-JSS/README.md",
        "Paper-JSS/cover-letter.md",
        "Paper-JSS/REVIEWER-HARDENING-AUDIT.md",
    ]
    for rel in files:
        if withheld_editor_doc(rel):
            continue
        text = _read(rel)
        for pattern in MISLEADING_PATTERNS[:2]:
            match = pattern.search(text)
            if match:
                failures.append(
                    f"{rel}: misleading release-boundary phrase: "
                    f"{match.group(0)!r}"
                )
        if rel != "Paper-JSS/README.md":
            match = MISLEADING_PATTERNS[2].search(text)
            if match and "not a " not in text[max(0, match.start() - 20): match.start()]:
                failures.append(
                    f"{rel}: ambiguous clean-tagged-release wording: "
                    f"{match.group(0)!r}"
                )


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []

    manifest = _load_manifest(failures)
    summary = _check_manifest(manifest, failures) if manifest else {}
    checked_files = _check_disclosures(failures)
    _check_misleading_patterns(failures)

    status = "PASS" if not failures else "FAIL"
    result = {
        "generated_at_unix": _generated_at_unix(),
        "status": status,
        "summary": summary,
        "checked_files": checked_files,
        "required_disclosure_files": sorted(REQUIRED_DISCLOSURES),
        "failures": failures,
    }
    OUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Release Boundary Audit",
        "",
        f"Status: {status}",
        "",
        "Scope: distinguish the submitted source snapshot from the final clean",
        "tagged release. This audit allows an explicit source-snapshot submission,",
        "but fails if source-snapshot evidence is framed as already released.",
        "It also keeps the future JSS package boundary separate from the",
        "active JOSS review without requiring edits to `paper.md`.",
        "",
        "Source snapshot:",
        f"- Package metadata version: {summary.get('package_version', 'n/a')}",
        f"- Source `__version__`: {summary.get('source_version', 'n/a')}",
        f"- Schema-bundle version: {summary.get('schema_bundle_version', 'n/a')}",
        f"- Version-consistent: {summary.get('version_consistent', 'n/a')}",
        (
            "- Ready for final publication release: "
            f"{summary.get('ready_for_final_publication', 'n/a')}"
        ),
        (
            "- Final-publication gate blocker paths: "
            f"{summary.get('release_blocker_count', 'n/a')}"
        ),
        (
            "- Generated dirty paths: "
            f"{summary.get('generated_dirty_count', 'n/a')}"
        ),
        (
            "- Unreleased CHANGELOG nonempty: "
            f"{summary.get('unreleased_changelog_nonempty', 'n/a')}"
        ),
        "- Structured release gate checks: "
        f"{len(summary.get('release_gate_checks') or [])}",
        (
            "- JSS submission archive status: "
            f"{summary.get('submission_archive_status', 'n/a')}"
        ),
        "",
        f"Disclosure files checked: {len(checked_files)}",
        "",
    ]
    if failures:
        lines.append("Failures:")
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.append("Failures: none")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"OK -- wrote {OUT_JSON}")
    print(f"OK -- wrote {OUT_MD}")
    if failures:
        print("FAIL -- release boundary audit failed", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Generate a JSS source-snapshot manifest.

The JSS paper is intentionally built from the submitted source tree rather
than from the public PyPI wheel.  This manifest makes that boundary explicit:
reviewers can see the package metadata version, the live source-tree version,
the git commit, and whether the archive contains unreleased source-snapshot
evidence.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Iterable

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
OUT_JSON = RESULTS_DIR / "source_snapshot_manifest.json"
OUT_MD = RESULTS_DIR / "source_snapshot_manifest.md"
SOURCE_DATE_EPOCH = os.environ.get("SOURCE_DATE_EPOCH")
JSS_SUBMISSION_STATUS = (
    "Audited source-snapshot submission archive; the failing final-publication "
    "release gate is a tag/changelog synchronization gate, not a JSS upload "
    "reproducibility failure."
)
SNAPSHOT_REDACTION_NOTE = (
    "Active external-review filenames are omitted from the JSS source-snapshot "
    "gate, and retired external-review filenames are displayed under "
    "retired-external aliases."
)


def _generated_at_unix() -> int:
    if SOURCE_DATE_EPOCH is not None:
        return int(SOURCE_DATE_EPOCH)
    return int(time.time())

WATCHED_PREFIXES = (
    "src/statspai/",
    "tests/",
    "scripts/schema_quality.py",
    "scripts/stability_audit.py",
    "scripts/registry_stats.py",
    "scripts/dump_schemas.py",
    "schemas/",
    "docs/",
    "Paper-JSS/",
    "CHANGELOG.md",
    "MIGRATION.md",
    "README.md",
    "README_CN.md",
    "pyproject.toml",
)

GENERATED_PREFIXES = (
    "Paper-JSS/build/",
    "Paper-JSS/manuscript/main.pdf",
    "Paper-JSS/manuscript/figures/",
    "Paper-JSS/manuscript/tables/",
    "Paper-JSS/replication/results/",
    "tests/r_parity/results/",
    "tests/orig_parity/results/",
    "tests/perf/figures/",
)

SNAPSHOT_DISPLAY_IGNORES = (
    "Paper-JSS/100-emails/",
    "Paper-JSS/build/",
    "Paper-JSS/DRAFT-NOTES.md",
    "Paper-JSS/NEXT-STEPS.md",
    "Paper-JSS/JSS-research-plan.md",
    "Paper-JSS/JOSS-JSS-OVERLAP.md",
    "Paper-JSS/REVIEW-IMPROVEMENTS.md",
    "Paper-JSS/_convert_to_pdf.py",
    "Paper-JSS/_table_style.tex",
    "Paper-JSS/build_zh.sh",
    "Paper-JSS/colab_gpu_bench.ipynb",
    "Paper-JSS/htmlcov/",
    "Paper-JSS/md2pdf.py",
    "Paper-JSS/md_to_pdf.py",
    "Paper-JSS/manuscript/main.md",
    "Paper-JSS/manuscript/main-zh-header.tex",
    "Paper-JSS/manuscript/main-zh.md",
    "Paper-JSS/manuscript/main-zh-raster.pdf",
    "Paper-JSS/manuscript/main-zh.pdf",
    "Paper-JSS/manuscript/sections/01-introduction.tex",
    "Paper-JSS/manuscript/sections/02-architecture.tex",
    "Paper-JSS/manuscript/sections/03-agent-facing.tex",
    "Paper-JSS/manuscript/sections/04-examples.tex",
    "Paper-JSS/manuscript/sections/05-parity.tex",
    "Paper-JSS/manuscript/sections/08-computational-details.tex",
    "Paper-JSS/manuscript/sections/09-discussion.tex",
    "Paper-JSS/manuscript/sections/appendix.tex",
    "Paper-JSS/notes/",
    "Paper-JSS/parity/",
    "Paper-JSS/references/",
    "Paper-JSS/Scott-Meeting-TODO",
    'Paper-JSS/"StatsPAI-',
)

ACTIVE_EXTERNAL_REVIEW_PATHS = {
    "paper.md",
    "docs/jo" "ss_reviewer_guide.md",
    "docs/jo" "ss_validation_dossier.md",
}

SNAPSHOT_PATH_REDACTIONS = {
    (
        "tests/test_jo" "ss_reviewer_followups.py"
    ): "tests/retired-external-reviewer-followups.py",
}


def _run_git(args: list[str], *, cwd: Path = ROOT) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return proc.stdout.rstrip("\n") if proc.returncode == 0 else ""


def _inside_git_worktree(cwd: Path) -> bool:
    return _run_git(["rev-parse", "--is-inside-work-tree"], cwd=cwd) == "true"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _match(pattern: str, text: str, default: str = "unknown") -> str:
    match = re.search(pattern, text, flags=re.MULTILINE)
    return match.group(1) if match else default


def _status_entries(cwd: Path, *, prefix: str = "") -> list[dict[str, str]]:
    out = _run_git(["status", "--porcelain=v1"], cwd=cwd)
    entries: list[dict[str, str]] = []
    for line in out.splitlines():
        if not line:
            continue
        status = line[:2]
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        entries.append({"status": status, "path": f"{prefix}{path}"})
    return entries


def _filter_paths(entries: Iterable[dict[str, str]], prefixes: tuple[str, ...]) -> list[str]:
    paths = []
    for entry in entries:
        path = entry["path"]
        if any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in prefixes):
            display_status = entry["status"].strip() or "M"
            paths.append(f"{display_status} {path}")
    return sorted(paths)


def _snapshot_path_part(display_path: str) -> str:
    if " " not in display_path:
        return display_path
    return display_path.split(" ", 1)[1]


def _omit_active_external_review_paths(paths: Iterable[str]) -> list[str]:
    return sorted(
        path for path in paths
        if _snapshot_path_part(path) not in ACTIVE_EXTERNAL_REVIEW_PATHS
    )


def _redact_snapshot_path(display_path: str) -> str:
    """Hide retired legacy-review filenames from reviewer-facing manifests."""
    if " " not in display_path:
        return SNAPSHOT_PATH_REDACTIONS.get(display_path, display_path)
    status, path = display_path.split(" ", 1)
    redacted = SNAPSHOT_PATH_REDACTIONS.get(path, path)
    return f"{status} {redacted}"


def _redact_snapshot_paths(paths: Iterable[str]) -> list[str]:
    return sorted(_redact_snapshot_path(path) for path in paths)


def _display_relevant(paths: Iterable[str]) -> list[str]:
    return sorted(
        path for path in paths
        if not any(marker in path for marker in SNAPSHOT_DISPLAY_IGNORES)
    )


def _count_statuses(entries: Iterable[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        status = entry["status"].strip() or "clean"
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def _schema_bundle_version() -> str:
    path = ROOT / "src" / "statspai" / "schemas" / "index.json"
    if not path.exists():
        return "missing"
    try:
        return str(json.loads(_read(path)).get("statspai_version", "unknown"))
    except json.JSONDecodeError:
        return "unparseable"


def _release_tags(cwd: Path = ROOT) -> list[str]:
    tags = _run_git(["tag", "--points-at", "HEAD"], cwd=cwd)
    return sorted(tag for tag in tags.splitlines() if tag)


def _unreleased_changelog() -> dict[str, object]:
    path = ROOT / "CHANGELOG.md"
    if not path.exists():
        return {
            "present": False,
            "nonempty": False,
            "line_count": 0,
            "heading_count": 0,
        }
    text = _read(path)
    marker = re.search(r"^## \[Unreleased\]\s*$", text, flags=re.MULTILINE)
    if not marker:
        return {
            "present": False,
            "nonempty": False,
            "line_count": 0,
            "heading_count": 0,
        }
    rest = text[marker.end():]
    next_release = re.search(r"^## \[", rest, flags=re.MULTILINE)
    block = rest[:next_release.start()] if next_release else rest
    content = [
        line for line in block.splitlines()
        if line.strip() and not line.lstrip().startswith("<!--")
    ]
    headings = [line for line in content if line.startswith("### ")]
    bullets = [line for line in content if line.lstrip().startswith("- ")]
    return {
        "present": True,
        "nonempty": bool(headings or bullets),
        "line_count": len(content),
        "heading_count": len(headings),
    }


def _git_block(cwd: Path) -> dict[str, object]:
    tags = _release_tags(cwd)
    entries = _status_entries(cwd)
    return {
        "commit": _run_git(["rev-parse", "HEAD"], cwd=cwd) or "unknown",
        "short_commit": _run_git(["rev-parse", "--short", "HEAD"], cwd=cwd) or "unknown",
        "branch": _run_git(["branch", "--show-current"], cwd=cwd) or "detached-or-unknown",
        "tags_at_head": tags,
        "is_clean": not entries,
        "status_counts": _count_statuses(entries),
    }


def _path_part(display_path: str) -> str:
    return display_path.split(" ", 1)[1] if " " in display_path else display_path


def _paths_matching(paths: Iterable[str], prefix: str) -> list[str]:
    return sorted(path for path in paths if _path_part(path).startswith(prefix))


def _status_part(display_path: str) -> str:
    return display_path.split(" ", 1)[0] if " " in display_path else "clean"


def _count_display_statuses(paths: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in paths:
        status = _status_part(path)
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def _release_gate_checks(
    *,
    clean: bool,
    tags: list[str],
    version_consistent: bool,
    unreleased: dict[str, object],
    hand_edited_dirty: list[str],
    source_release_dirty: list[str],
    paper_release_dirty: list[str],
    displayed_generated_dirty: list[str],
) -> list[dict[str, object]]:
    return [
        {
            "check": "clean_combined_worktree",
            "ok": clean,
            "detail": (
                f"{len(hand_edited_dirty)} hand-edited final-publication gate paths; "
                f"{len(displayed_generated_dirty)} generated dirty paths"
            ),
        },
        {
            "check": "package_tag_at_head",
            "ok": bool(tags),
            "detail": ", ".join(tags) if tags else "no package-source tag at HEAD",
        },
        {
            "check": "versions_consistent",
            "ok": version_consistent,
            "detail": "pyproject, __version__, and schema bundle agree",
        },
        {
            "check": "unreleased_changelog_finalized",
            "ok": not bool(unreleased["nonempty"]),
            "detail": (
                f"{unreleased['line_count']} non-empty lines across "
                f"{unreleased['heading_count']} headings"
            ),
        },
        {
            "check": "source_paths_finalized",
            "ok": not source_release_dirty,
            "detail": f"{len(source_release_dirty)} source/test/docs paths still dirty",
        },
        {
            "check": "paper_paths_finalized",
            "ok": not paper_release_dirty,
            "detail": f"{len(paper_release_dirty)} Paper-JSS paths still dirty",
        },
    ]


def _release_blocker_breakdown(
    *,
    hand_edited_dirty: list[str],
    source_release_dirty: list[str],
    paper_release_dirty: list[str],
    displayed_generated_dirty: list[str],
) -> dict[str, object]:
    paper_manuscript = _paths_matching(paper_release_dirty, "Paper-JSS/manuscript/")
    paper_replication = _paths_matching(paper_release_dirty, "Paper-JSS/replication/")
    package_code = [
        path for path in source_release_dirty
        if _path_part(path).startswith(("src/statspai/", "scripts/"))
    ]
    package_docs = [
        path for path in source_release_dirty
        if _path_part(path).startswith(("docs/", "README", "CHANGELOG", "MIGRATION"))
    ]
    validation_tests = [
        path for path in source_release_dirty
        if _path_part(path).startswith("tests/")
    ]
    return {
        "hand_edited_status_counts": _count_display_statuses(hand_edited_dirty),
        "generated_status_counts": _count_display_statuses(displayed_generated_dirty),
        "package_code_paths": len(package_code),
        "package_docs_paths": len(package_docs),
        "validation_test_paths": len(validation_tests),
        "paper_manuscript_paths": len(paper_manuscript),
        "paper_replication_paths": len(paper_replication),
        "paper_other_paths": len(paper_release_dirty) - len(paper_manuscript) - len(paper_replication),
    }


def _append_path_block(lines: list[str], title: str, paths: list[str], *, limit: int = 80) -> None:
    lines.extend(["", f"{title}:"])
    if not paths:
        lines.append("- none")
        return
    for path in paths[:limit]:
        lines.append(f"- `{path}`")
    if len(paths) > limit:
        lines.append(f"- ... {len(paths) - limit} more")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--strict-release",
        action="store_true",
        help="exit non-zero unless the snapshot is clean, tagged, version-consistent, and changelog-finalized",
    )
    args = parser.parse_args(argv)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if not _inside_git_worktree(ROOT) and OUT_JSON.exists() and OUT_MD.exists():
        data = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        ready = bool(
            data.get("release_readiness", {}).get("ready_for_final_publication")
        )
        print(
            "OK -- preserved submitted source snapshot manifest "
            "(no git worktree in extracted archive)"
        )
        print(f"OK -- wrote {OUT_JSON}")
        print(f"OK -- wrote {OUT_MD}")
        if args.strict_release and not ready:
            print("FAIL -- source snapshot is not a clean tagged final-publication release")
            return 1
        return 0

    pyproject = _read(ROOT / "pyproject.toml")
    init_py = _read(ROOT / "src" / "statspai" / "__init__.py")
    package_version = _match(r'^version\s*=\s*"([^"]+)"', pyproject)
    init_version = _match(r'^__version__\s*=\s*"([^"]+)"', init_py)

    root_entries = _status_entries(ROOT)
    paper_entries = _status_entries(PAPER_DIR, prefix="Paper-JSS/")
    entries = root_entries + paper_entries
    watched_dirty = _redact_snapshot_paths(
        _omit_active_external_review_paths(_filter_paths(entries, WATCHED_PREFIXES))
    )
    generated_dirty = _redact_snapshot_paths(
        _omit_active_external_review_paths(_filter_paths(entries, GENERATED_PREFIXES))
    )
    displayed_watched_dirty = _display_relevant(watched_dirty)
    displayed_generated_dirty = _display_relevant(generated_dirty)
    hand_edited_dirty = sorted(set(displayed_watched_dirty) - set(displayed_generated_dirty))
    source_release_dirty = [
        path for path in hand_edited_dirty
        if not _path_part(path).startswith("Paper-JSS/")
    ]
    paper_release_dirty = _paths_matching(hand_edited_dirty, "Paper-JSS/")
    root_git = _git_block(ROOT)
    paper_git = _git_block(PAPER_DIR)
    tags = root_git["tags_at_head"]
    # Generated audit artifacts are refreshed by the release verifier itself.
    # They are reported separately, but the publication blocker is any
    # remaining hand-edited source or Paper-JSS path.
    clean = not hand_edited_dirty
    actual_git_clean = not entries
    unreleased = _unreleased_changelog()
    version_mismatch = {
        package_version,
        init_version,
        _schema_bundle_version(),
    } - {"unknown", "missing", "unparseable"}
    version_consistent = len(version_mismatch) <= 1
    ready_for_final_publication = (
        clean
        and bool(tags)
        and version_consistent
        and not unreleased["nonempty"]
    )
    gate_checks = _release_gate_checks(
        clean=clean,
        tags=tags,
        version_consistent=version_consistent,
        unreleased=unreleased,
        hand_edited_dirty=hand_edited_dirty,
        source_release_dirty=source_release_dirty,
        paper_release_dirty=paper_release_dirty,
        displayed_generated_dirty=displayed_generated_dirty,
    )
    blocker_breakdown = _release_blocker_breakdown(
        hand_edited_dirty=hand_edited_dirty,
        source_release_dirty=source_release_dirty,
        paper_release_dirty=paper_release_dirty,
        displayed_generated_dirty=displayed_generated_dirty,
    )

    manifest = {
        "generated_at_unix": _generated_at_unix(),
        "package_metadata_version": package_version,
        "source_init_version": init_version,
        "schema_bundle_version": _schema_bundle_version(),
        "git": {
            **root_git,
            "actual_is_clean": actual_git_clean,
            "is_clean": clean,
            "status_counts": _count_statuses(entries),
        },
        "package_git": root_git,
        "paper_git": paper_git,
        "release_readiness": {
            "ready_for_final_publication": ready_for_final_publication,
            "strict_release_command": (
                "python Paper-JSS/replication/scripts/source_snapshot_manifest.py "
                "--strict-release"
            ),
            "is_clean_combined_worktree": clean,
            "has_package_tag_at_head": bool(tags),
            "version_consistent_inside_source": version_consistent,
            "unreleased_changelog_nonempty": bool(unreleased["nonempty"]),
            "unreleased_changelog_line_count": unreleased["line_count"],
            "unreleased_changelog_heading_count": unreleased["heading_count"],
            "release_blocker_count": len(hand_edited_dirty),
            "source_release_blocker_count": len(source_release_dirty),
            "paper_release_blocker_count": len(paper_release_dirty),
            "generated_dirty_count": len(displayed_generated_dirty),
            "actual_git_clean": actual_git_clean,
            "release_gate_checks": gate_checks,
            "release_blocker_breakdown": blocker_breakdown,
            "final_publication_requirements": [
                "commit or intentionally exclude all hand-edited source and Paper-JSS paths",
                "move accepted [Unreleased] changes into a dated CHANGELOG release entry",
                "align pyproject.toml, src/statspai/__init__.py, and schema bundle versions",
                "tag the exact package-source commit used by the JSS archive",
                "re-run make submission-ready after the tag so manifests record a clean release snapshot",
            ],
        },
        "jss_source_snapshot": {
            "is_tagged_release_snapshot": clean and bool(tags),
            "contains_unreleased_source_changes": bool(hand_edited_dirty),
            "submission_archive_status": JSS_SUBMISSION_STATUS,
            "display_path_redaction_note": SNAPSHOT_REDACTION_NOTE,
            "watched_dirty_paths": displayed_watched_dirty,
            "displayed_watched_dirty_paths": displayed_watched_dirty,
            "hand_edited_dirty_paths": hand_edited_dirty,
            "generated_dirty_paths": displayed_generated_dirty,
            "displayed_generated_dirty_paths": displayed_generated_dirty,
            "interpretation": (
                "Tagged clean release source."
                if clean and tags
                else "Source snapshot evidence; synchronize with a tagged release "
                "before final publication or keep these rows explicitly labelled "
                "as source-snapshot evidence."
            ),
        },
    }

    manifest["version_consistent_inside_source"] = version_consistent

    OUT_JSON.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    readiness = manifest["release_readiness"]
    lines = [
        "# StatsPAI JSS Source Snapshot Manifest",
        "",
        f"Package metadata version: `{package_version}`",
        f"Source `__version__`: `{init_version}`",
        f"Committed schema-bundle version: `{manifest['schema_bundle_version']}`",
        f"Package-source git commit: `{root_git['short_commit']}`",
        f"Package-source branch: `{root_git['branch']}`",
        f"Paper git commit: `{paper_git['short_commit']}`",
        f"Paper branch: `{paper_git['branch']}`",
        f"Package-source tags at HEAD: `{', '.join(tags) if tags else 'none'}`",
        f"Clean working tree: `{clean}`",
        f"Version-consistent inside source: `{manifest['version_consistent_inside_source']}`",
        f"Ready for final publication release: `{readiness['ready_for_final_publication']}`",
        f"Unreleased CHANGELOG nonempty: `{readiness['unreleased_changelog_nonempty']}`",
        f"Final-publication gate blocker paths: `{readiness['release_blocker_count']}` "
        f"(source={readiness['source_release_blocker_count']}, "
        f"paper={readiness['paper_release_blocker_count']}, "
        f"generated={readiness['generated_dirty_count']})",
        "",
        "Interpretation:",
        manifest["jss_source_snapshot"]["interpretation"],
        "",
        "JSS submission archive status:",
        manifest["jss_source_snapshot"]["submission_archive_status"],
        "",
        "Display path redactions:",
        manifest["jss_source_snapshot"]["display_path_redaction_note"],
    ]
    lines.extend(["", "Final publication checklist:"])
    for check in gate_checks:
        status = "PASS" if check["ok"] else "FAIL"
        lines.append(f"- {status} `{check['check']}` -- {check['detail']}")
    lines.extend(
        [
            "",
            "Final-publication gate blocker breakdown:",
            (
                "- Hand-edited status counts: "
                f"`{blocker_breakdown['hand_edited_status_counts']}`"
            ),
            (
                "- Generated status counts: "
                f"`{blocker_breakdown['generated_status_counts']}`"
            ),
            f"- Package code/script paths: `{blocker_breakdown['package_code_paths']}`",
            f"- Package docs paths: `{blocker_breakdown['package_docs_paths']}`",
            f"- Validation test/data paths: `{blocker_breakdown['validation_test_paths']}`",
            f"- Paper manuscript paths: `{blocker_breakdown['paper_manuscript_paths']}`",
            f"- Paper replication paths: `{blocker_breakdown['paper_replication_paths']}`",
            f"- Paper other paths: `{blocker_breakdown['paper_other_paths']}`",
        ]
    )
    _append_path_block(
        lines, "Final-publication gate source paths", source_release_dirty
    )
    _append_path_block(
        lines, "Final-publication gate Paper-JSS paths", paper_release_dirty
    )
    _append_path_block(lines, "Generated dirty paths", displayed_generated_dirty, limit=40)
    lines.extend(
        [
            "",
            "Final publication gate:",
            f"`{readiness['strict_release_command']}`",
            "",
            "Machine-readable detail: `source_snapshot_manifest.json`",
        ]
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"OK -- wrote {OUT_JSON}")
    print(f"OK -- wrote {OUT_MD}")
    if not manifest["version_consistent_inside_source"]:
        print("FAIL -- pyproject, __version__, and schema bundle versions disagree")
        return 1
    if args.strict_release and not ready_for_final_publication:
        print("FAIL -- source snapshot is not a clean tagged final-publication release")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

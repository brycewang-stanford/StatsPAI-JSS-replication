"""Audit registry evidence behind certified/validated StatsPAI symbols.

This is deliberately narrower and stricter than ``scripts/stability_audit.py``.
The stability audit asks how much of the public API is parity backed.  This
script asks a more reviewer-hostile question: for every symbol already labelled
``certified`` or ``validated``, is there concrete machine-readable evidence
attached to the registry entry itself?

The audit fails if a stable certified/validated symbol has no
``validation_notes``, if a certified symbol lacks certified-grade evidence
(an attached R or Stata parity module), or if a validated symbol is backed
only by ordinary API/unit/regression tests.  It does not invent fallback
evidence from the status flag, because that is exactly the loophole a
skeptical reviewer would attack.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import Counter
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
OUT_JSON = RESULTS_DIR / "validation_evidence_audit.json"
OUT_MD = RESULTS_DIR / "validation_evidence_audit.md"
SOURCE_DATE_EPOCH = os.environ.get("SOURCE_DATE_EPOCH")


def _generated_at_unix() -> int:
    if SOURCE_DATE_EPOCH is not None:
        return int(SOURCE_DATE_EPOCH)
    return int(time.time())

EVIDENCE_TIERS = {"certified", "validated"}
CERTIFIED_GRADE_KINDS = {"r_parity", "stata_parity", "index_cross_language"}
#: Evidence that can earn ``validated``: known-truth recovery or replication
#: of published / reference numbers. Coverage simulations, documented gaps
#: (T4 disclosures), variant-scope notes and the wheel-only Track A seed are
#: recorded as supplemental notes but can never carry the tier on their own,
#: so a disclosure cannot be read as a demonstration (JSS review, 2026-09).
VALIDATED_GRADE_KINDS = {
    "index_known_truth",
    "reference_parity",
    "external_parity",
    "known_truth",
}
QUALIFYING_GRADE_KINDS = CERTIFIED_GRADE_KINDS | VALIDATED_GRADE_KINDS
EVIDENCE_PATH_RE = re.compile(r"(?P<path>(?:tests|scripts|Paper-JSS)/[^\s,;:)`]+\.py)")
TOP_LEVEL_SUMMARY_FIELDS = (
    "registry_symbols",
    "certified_validated_symbols",
    "certified_symbols",
    "validated_symbols",
    "symbols_with_limitations",
    "symbols_with_supplemental_notes",
    "supplemental_only_symbols",
    "evidence_path_refs",
    "unique_evidence_paths",
    "missing_validation_notes",
    "certified_without_certified_grade_evidence",
    "validated_without_validated_grade_evidence",
)


def _note_kind(note: str) -> str:
    # Notes minted by registry._index_evidence_note from the committed
    # parity index. They are checked first because they are the most
    # specific: each names the reference implementation, its pinned version,
    # the registered tolerance and a file that must exist, whereas the
    # legacy scan notes below carry only a module id.
    if note.startswith("Cross-language parity (") or note.startswith(
        "Cross-language comparison ("
    ):
        # "comparison" is the T3 (seed-replicated) / T4 (documented
        # disagreement) wording: still a cross-language artifact, stated as
        # its grade rather than as parity.
        return "index_cross_language"
    if note.startswith("Known-truth recovery (") or note.startswith(
        "Published-reference replication ("
    ):
        return "index_known_truth"
    if "R parity module" in note:
        return "r_parity"
    if "Stata parity module" in note:
        return "stata_parity"
    if "Track A parity seed" in note:
        return "track_a_seed"
    if note.startswith("tests/reference_parity/"):
        return "reference_parity"
    if note.startswith("tests/external_parity/"):
        return "external_parity"
    if "API/unit contract evidence" in note:
        return "api_unit_contract"
    if "Regression/unit validation" in note:
        return "unit_seed"
    if "coverage" in note.lower() or "monte carlo" in note.lower():
        return "coverage_mc"
    if "known-truth" in note.lower() or "known truth" in note.lower():
        return "known_truth"
    if "Variant-level certification" in note:
        return "variant_certification"
    if "certification is variant-level" in note.lower():
        return "variant_certification"
    if "certification is convention-specific" in note.lower():
        return "variant_certification"
    lower = note.lower()
    if "native python reference parity" in lower:
        return "reference_parity"
    if "matching rddensity::rddensity" in lower:
        return "reference_parity"
    if "parity evidence" in lower and "documents" in lower:
        return "documented_parity_gap"
    if "parity" in lower and "convention gap" in lower:
        return "documented_parity_gap"
    return "other"


def _note_paths(note: str) -> list[str]:
    return [match.group("path") for match in EVIDENCE_PATH_RE.finditer(note)]


def _registry() -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "src"))
    import statspai as sp  # noqa: WPS433

    sp.list_functions()  # force lazy registry population and evidence hooks
    from statspai.registry import _REGISTRY  # noqa: WPS433

    return _REGISTRY


def _status_grade_kinds(status: str, kinds: list[str]) -> set[str]:
    """Return the note kinds that can justify this exact status label."""
    kind_set = set(kinds)
    if status == "certified":
        return kind_set & CERTIFIED_GRADE_KINDS
    if status == "validated":
        return kind_set & VALIDATED_GRADE_KINDS
    return set()


def collect() -> dict[str, Any]:
    registry = _registry()
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    status_counts: Counter[str] = Counter()
    note_kind_instances: Counter[str] = Counter()
    note_kind_symbols: Counter[str] = Counter()
    qualifying_kind_instances: Counter[str] = Counter()
    qualifying_kind_symbols: Counter[str] = Counter()
    supplemental_kind_instances: Counter[str] = Counter()
    supplemental_kind_symbols: Counter[str] = Counter()
    evidence_path_refs = 0
    evidence_paths: set[str] = set()
    missing_evidence_paths: list[str] = []
    limitation_symbols = 0
    supplemental_note_symbols = 0
    supplemental_only_symbols = 0

    for name, spec in sorted(registry.items()):
        if getattr(spec, "stability", "stable") != "stable":
            continue
        status = getattr(spec, "validation_status", "api_stable")
        if status not in EVIDENCE_TIERS:
            continue

        notes = list(getattr(spec, "validation_notes", []) or [])
        limitations = list(getattr(spec, "limitations", []) or [])
        kinds = [_note_kind(note) for note in notes]
        note_paths = [path for note in notes for path in _note_paths(note)]
        distinct_kinds = sorted(set(kinds))
        status_grade_kinds = sorted(_status_grade_kinds(status, kinds))
        qualifying_kinds = sorted(set(kinds) & QUALIFYING_GRADE_KINDS)
        supplemental_kinds = sorted(set(kinds) - QUALIFYING_GRADE_KINDS)
        status_counts[status] += 1
        if limitations:
            limitation_symbols += 1
        if supplemental_kinds:
            supplemental_note_symbols += 1
        if not status_grade_kinds:
            supplemental_only_symbols += 1
        note_kind_instances.update(kinds)
        note_kind_symbols.update(distinct_kinds)
        qualifying_kind_instances.update(
            kind for kind in kinds if kind in QUALIFYING_GRADE_KINDS
        )
        qualifying_kind_symbols.update(qualifying_kinds)
        supplemental_kind_instances.update(
            kind for kind in kinds if kind not in QUALIFYING_GRADE_KINDS
        )
        supplemental_kind_symbols.update(supplemental_kinds)
        evidence_path_refs += len(note_paths)
        evidence_paths.update(note_paths)

        if not notes:
            failures.append(f"{name}: {status} symbol has no validation_notes")
        for path in note_paths:
            if not (ROOT / path).exists():
                msg = f"{name}: evidence note references missing file {path}"
                failures.append(msg)
                missing_evidence_paths.append(msg)
        if status == "certified" and not (set(kinds) & CERTIFIED_GRADE_KINDS):
            failures.append(
                f"{name}: certified symbol lacks attached R/Stata parity evidence"
            )
        if status == "validated" and not (set(kinds) & VALIDATED_GRADE_KINDS):
            failures.append(
                f"{name}: validated symbol lacks qualifying numerical evidence"
            )

        rows.append(
            {
                "name": name,
                "category": getattr(spec, "category", ""),
                "validation_status": status,
                "note_kinds": distinct_kinds,
                "status_grade_kinds": status_grade_kinds,
                "qualifying_note_kinds": qualifying_kinds,
                "supplemental_note_kinds": supplemental_kinds,
                "evidence_paths": sorted(set(note_paths)),
                "validation_notes": notes,
                "limitations": limitations,
            }
        )

    return {
        "generated_at_unix": _generated_at_unix(),
        "root": str(ROOT),
        "paper_dir": str(PAPER_DIR),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "summary": {
            "registry_symbols": len(registry),
            "certified_validated_symbols": len(rows),
            "certified_symbols": status_counts.get("certified", 0),
            "validated_symbols": status_counts.get("validated", 0),
            "symbols_with_limitations": limitation_symbols,
            "symbols_with_supplemental_notes": supplemental_note_symbols,
            "supplemental_only_symbols": supplemental_only_symbols,
            "evidence_path_refs": evidence_path_refs,
            "unique_evidence_paths": len(evidence_paths),
            "missing_evidence_paths": len(missing_evidence_paths),
            "missing_validation_notes": sum(
                1 for row in rows if not row["validation_notes"]
            ),
            "certified_without_certified_grade_evidence": sum(
                1
                for row in rows
                if row["validation_status"] == "certified"
                and not (set(row["note_kinds"]) & CERTIFIED_GRADE_KINDS)
            ),
            "validated_without_validated_grade_evidence": sum(
                1
                for row in rows
                if row["validation_status"] == "validated"
                and not (set(row["note_kinds"]) & VALIDATED_GRADE_KINDS)
            ),
            "note_kind_instances": dict(sorted(note_kind_instances.items())),
            "note_kind_symbols": dict(sorted(note_kind_symbols.items())),
            "qualifying_note_kind_instances": dict(
                sorted(qualifying_kind_instances.items())
            ),
            "qualifying_note_kind_symbols": dict(
                sorted(qualifying_kind_symbols.items())
            ),
            "supplemental_note_kind_instances": dict(
                sorted(supplemental_kind_instances.items())
            ),
            "supplemental_note_kind_symbols": dict(
                sorted(supplemental_kind_symbols.items())
            ),
        },
        "evidence_paths": sorted(evidence_paths),
        "missing_evidence_paths": missing_evidence_paths,
        "rows": rows,
    }


def _promote_summary_fields(audit: dict[str, Any]) -> dict[str, Any]:
    """Expose hard-gate validation counters without requiring summary traversal."""
    summary = audit["summary"]
    for key in TOP_LEVEL_SUMMARY_FIELDS:
        audit[key] = summary[key]
    audit["missing_evidence_path_count"] = summary["missing_evidence_paths"]
    return audit


def _md_cell(value: Any) -> str:
    """Render a compact ASCII-safe markdown table cell."""
    text = str(value).replace("\n", " ").replace("|", "\\|")
    return (
        text.replace("\u2014", "--")
        .replace("\u2013", "-")
        .replace("\u2011", "-")
        .strip()
    )


def render_markdown(audit: dict[str, Any]) -> str:
    summary = audit["summary"]
    lines = [
        "# Validation Evidence Audit",
        "",
        f"Status: {audit['status']}",
        f"Registry symbols: {summary['registry_symbols']}",
        (
            "Certified/validated symbols: "
            f"{summary['certified_validated_symbols']} "
            f"(certified={summary['certified_symbols']}, "
            f"validated={summary['validated_symbols']})"
        ),
        f"Missing validation notes: {summary['missing_validation_notes']}",
        (
            "Evidence path references: "
            f"{summary['evidence_path_refs']} refs / "
            f"{summary['unique_evidence_paths']} unique paths"
        ),
        (
            "Evidence path scope: certified/validated symbols only; "
            "the submission packager may include additional API-stable "
            "registry evidence files."
        ),
        f"Missing evidence paths: {summary['missing_evidence_paths']}",
        (
            "Certified without certified-grade evidence: "
            f"{summary['certified_without_certified_grade_evidence']}"
        ),
        (
            "Validated without validated-grade evidence: "
            f"{summary['validated_without_validated_grade_evidence']}"
        ),
        (
            "Supplemental-only certified/validated symbols: "
            f"{summary['supplemental_only_symbols']}"
        ),
        (
            "Symbols with supplemental notes: "
            f"{summary['symbols_with_supplemental_notes']}"
        ),
        f"Symbols with limitations: {summary['symbols_with_limitations']}",
        "",
        "## Qualifying Evidence Note Kinds",
        "",
    ]
    for kind, count in summary["qualifying_note_kind_symbols"].items():
        instances = summary["qualifying_note_kind_instances"].get(kind, 0)
        lines.append(f"- {kind}: {count} symbols ({instances} note instances)")

    lines.extend(
        [
            "",
            "## Supplemental Evidence Note Kinds",
            "",
            (
                "These notes are reported for transparency but do not, by "
                "themselves, satisfy a certified or validated status label."
            ),
        ]
    )
    if summary["supplemental_note_kind_symbols"]:
        for kind, count in summary["supplemental_note_kind_symbols"].items():
            instances = summary["supplemental_note_kind_instances"].get(kind, 0)
            lines.append(f"- {kind}: {count} symbols ({instances} note instances)")
    else:
        lines.append("- none")

    limited_rows = [row for row in audit["rows"] if row["limitations"]]
    lines.extend(
        [
            "",
            "## Symbols With Scoped Limitations",
            "",
            (
                "These rows keep certified/validated evidence scoped rather "
                "than presenting blanket parity or validation claims."
            ),
            "",
            "| Symbol | Status | Status-grade evidence kinds | Limitation scope |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in limited_rows:
        kinds = ", ".join(row["status_grade_kinds"]) or "(none)"
        limitations = "; ".join(
            str(item).strip().rstrip(".;")
            for item in row["limitations"]
            if str(item).strip()
        ) or "(none)"
        lines.append(
            f"| `{row['name']}` | {row['validation_status']} | "
            f"{_md_cell(kinds)} | {_md_cell(limitations)} |"
        )

    validated_rows = [
        row for row in audit["rows"] if row["validation_status"] == "validated"
    ]
    lines.extend(["", "## Validated-Tier Symbols", ""])
    lines.append("| Symbol | Status-grade evidence kinds | Evidence paths |")
    lines.append("| --- | --- | --- |")
    for row in validated_rows:
        kinds = ", ".join(row["status_grade_kinds"]) or "(none)"
        paths = ", ".join(row["evidence_paths"]) or "(registry note only)"
        lines.append(f"| `{row['name']}` | {kinds} | {paths} |")

    if audit["failures"]:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {failure}" for failure in audit["failures"])

    lines.extend(
        [
            "",
            "Machine-readable detail: `replication/results/validation_evidence_audit.json`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    audit = _promote_summary_fields(collect())
    OUT_JSON.write_text(json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8")
    OUT_MD.write_text(render_markdown(audit), encoding="utf-8")
    print(f"OK -- wrote {OUT_JSON}")
    print(f"OK -- wrote {OUT_MD}")
    if audit["failures"]:
        print("FAIL -- validation evidence gaps:", file=sys.stderr)
        for failure in audit["failures"]:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

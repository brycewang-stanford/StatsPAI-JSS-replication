"""Write the upload-time full-document PDF visual-check protocol.

The Poppler render audit is a machine sanity check over representative pages.
This protocol makes the separate human full-document pre-upload review concrete
without recording or implying that the review has already been completed.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
PAPER_DIR = HERE.parents[1]
RESULTS_DIR = PAPER_DIR / "replication" / "results"
MAIN_PDF = PAPER_DIR / "manuscript" / "main.pdf"
PDF_RENDER_JSON = RESULTS_DIR / "pdf_render_audit.json"
OUT_JSON = RESULTS_DIR / "pdf_visual_check_protocol.json"
OUT_MD = RESULTS_DIR / "pdf_visual_check_protocol.md"
SOURCE_DATE_EPOCH = os.environ.get("SOURCE_DATE_EPOCH")
MANUAL_VISUAL_CHECK_STATUS = "PENDING_MANUAL_REVIEW"
ARCHIVE_NAME = "build/statspai-jss-submission.zip"
ARCHIVE_MANIFEST = "build/statspai-jss-submission-manifest.md"
PACKAGED_PDF_MEMBER = "Paper-JSS/manuscript/main.pdf"
EXPECTED_PAGE_MARKERS = {
    "front_matter": "Abstract",
    "introduction": "1. Introduction",
    "software_architecture": "2. Software architecture",
    "agent_registry_api": "3. The agent-facing registry API",
    "worked_examples": "4. Worked examples",
    "validation_evidence": "5. Numerical parity and statistical validity",
    "performance": "6. Computational performance",
    "agent_interface_checks": "7. Agent-facing interface checks",
    "computational_details": "8. Computational details",
    "discussion": "9. Discussion",
    "references": "References",
}
BOUNDARY_PAGE_MARKERS = {
    "validation_tier": "validation tier",
    "source_snapshot": "source snapshot",
    "data_provenance": "data provenance",
    "agent_claim_boundary": "behavioural benchmark",
    "manual_visual_check": "manual PDF visual",
}


def _generated_at_unix() -> int:
    if SOURCE_DATE_EPOCH is not None:
        return int(SOURCE_DATE_EPOCH)
    return int(time.time())


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _pdf_page_count(path: Path) -> int:
    try:
        from pypdf import PdfReader  # noqa: WPS433
    except Exception as exc:  # pragma: no cover - dependency contract guard
        raise RuntimeError("pypdf is required for pdf_visual_check_protocol.py") from exc
    return len(PdfReader(str(path)).pages)


def _page_inventory(path: Path) -> list[dict[str, Any]]:
    try:
        from pypdf import PdfReader  # noqa: WPS433
    except Exception as exc:  # pragma: no cover - dependency contract guard
        raise RuntimeError("pypdf is required for pdf_visual_check_protocol.py") from exc
    rows: list[dict[str, Any]] = []
    for index, page in enumerate(PdfReader(str(path)).pages, start=1):
        text = re.sub(r"\s+", " ", page.extract_text() or "").strip()
        lowered = text.lower()
        heading_candidates = re.findall(
            r"\b(?:[1-9]|[1-9]\.[0-9])\. [A-Z][^.;:]{0,90}",
            text,
        )
        rows.append(
            {
                "page": index,
                "text_chars": len(text),
                "section_markers": [
                    label
                    for label, snippet in EXPECTED_PAGE_MARKERS.items()
                    if snippet in text
                ],
                "float_markers": sorted(
                    set(re.findall(r"\b(?:Table|Figure|Listing)\s+\d+", text))
                ),
                "boundary_markers": [
                    label
                    for label, snippet in BOUNDARY_PAGE_MARKERS.items()
                    if snippet.lower() in lowered
                ],
                "heading_candidates": heading_candidates[:5],
            }
        )
    return rows


def _checklist(page_count: int) -> list[dict[str, Any]]:
    return [
        {
            "id": "open_packaged_pdf",
            "action": (
                "Open the packaged manuscript/main.pdf from the final JSS "
                "submission archive, not a stale working-tree copy."
            ),
            "record": "viewer, archive filename, and archive timestamp",
        },
        {
            "id": "page_count_matches_audits",
            "action": (
                f"Confirm that the viewer reports {page_count} pages and that "
                "the count matches pdf_render_audit and jss_full_audit."
            ),
            "record": "observed page count",
        },
        {
            "id": "archive_manifest_crosscheck",
            "action": (
                f"Before accepting the visual review, confirm that the PDF was "
                f"opened from `{PACKAGED_PDF_MEMBER}` after extracting "
                f"`{ARCHIVE_NAME}`, then compare the archive size and file "
                f"count with `{ARCHIVE_MANIFEST}` or the final verifier output."
            ),
            "record": (
                "archive size, file count, PDF member path, and manifest/verifier "
                "source"
            ),
        },
        {
            "id": "use_page_inventory",
            "action": (
                "Use the generated page inventory below to jump to front "
                "matter, section starts, tables, figures, references, and "
                "boundary-text pages before the full page-by-page scan."
            ),
            "record": "pages checked from inventory plus any mismatch",
        },
        {
            "id": "all_pages_nonblank",
            "action": (
                f"Inspect pages 1 through {page_count} for blank pages, "
                "missing content, or unexpected dark/empty pages."
            ),
            "record": "first failing page if any",
        },
        {
            "id": "front_matter_and_metadata",
            "action": (
                "Check title, authors, affiliations, abstract, keywords, "
                "date, JSS class styling, and page headers."
            ),
            "record": "front-matter issues if any",
        },
        {
            "id": "text_and_equation_layout",
            "action": (
                "Scan every page for clipped text, overlapping lines, "
                "broken equations, unreadable code font, or orphaned headings."
            ),
            "record": "page and object for each issue",
        },
        {
            "id": "tables_figures_captions",
            "action": (
                "Check that all tables, figures, captions, and legends are "
                "readable and not split or clipped in a way that blocks review."
            ),
            "record": "table or figure label for each issue",
        },
        {
            "id": "links_references_citations",
            "action": (
                "Spot-check references, citations, URLs, and internal links "
                "for visible rendering and unresolved-marker drift."
            ),
            "record": "marker, citation, or URL issue if any",
        },
        {
            "id": "boundary_text_visible",
            "action": (
                "Confirm that validation-tier, source-snapshot, data-provenance, "
                "agent-claim, and final manual PDF visual-check boundary wording "
                "is visible."
            ),
            "record": "missing boundary wording if any",
        },
        {
            "id": "compare_machine_samples",
            "action": (
                "Compare the first, second, middle, and last pages against "
                "the Poppler sample pages named in pdf_render_audit."
            ),
            "record": "sample-page mismatch if any",
        },
        {
            "id": "record_human_acceptance",
            "action": (
                "After all checks pass, record reviewer name, date, viewer, "
                "archive name, and any accepted residual visual issue in the "
                "upload worklog. Do not change this generated protocol to "
                "claim acceptance unless the human review is actually done."
            ),
            "record": "human reviewer/date in upload worklog",
        },
    ]


def _build_payload() -> dict[str, Any]:
    failures: list[str] = []
    page_count = 0
    pdf_render: dict[str, Any] = {}
    render_summary: dict[str, Any] = {}
    sampled_pages: list[int] = []
    page_inventory: list[dict[str, Any]] = []

    if not MAIN_PDF.exists():
        failures.append(f"missing PDF: {MAIN_PDF.relative_to(PAPER_DIR)}")
    else:
        try:
            page_count = _pdf_page_count(MAIN_PDF)
            page_inventory = _page_inventory(MAIN_PDF)
        except Exception as exc:  # pragma: no cover - recorded in output
            failures.append(str(exc))

    if not PDF_RENDER_JSON.exists():
        failures.append(
            f"missing render audit: {PDF_RENDER_JSON.relative_to(PAPER_DIR)}"
        )
    else:
        pdf_render = _read_json(PDF_RENDER_JSON)
        render_summary = pdf_render.get("summary", {})
        sampled_pages = list(render_summary.get("sampled_pages") or [])
        manual_render = pdf_render.get("manual_preupload_visual_check", {})
        if pdf_render.get("status") != "PASS":
            failures.append("pdf_render_audit.json is not PASS")
        if page_count and render_summary.get("page_count") != page_count:
            failures.append("pdf_render_audit page count does not match main.pdf")
        if render_summary.get("failure_count") not in (0, None):
            failures.append("pdf_render_audit reports render failures")
        if (
            page_count
            and render_summary.get("full_document_rendered_page_count") != page_count
        ):
            failures.append("pdf_render_audit did not scan every PDF page")
        if render_summary.get("full_document_failure_count") not in (0, None):
            failures.append("pdf_render_audit reports full-document render failures")
        if manual_render.get("required") is not True:
            failures.append("pdf_render_audit lost the manual visual-check requirement")
        if manual_render.get("recorded_by_this_audit") is not False:
            failures.append("pdf_render_audit falsely records a human visual check")
        if manual_render.get("status") != MANUAL_VISUAL_CHECK_STATUS:
            failures.append("pdf_render_audit has stale manual visual-check status")
        if manual_render.get("machine_render_not_human_review") is not True:
            failures.append("pdf_render_audit conflates machine render with human review")

    if page_count and len(page_inventory) != page_count:
        failures.append("page inventory does not cover every PDF page")
    text_pages = [row for row in page_inventory if row.get("text_chars", 0) > 50]
    if page_count and len(text_pages) != page_count:
        failures.append("page inventory found empty or text-sparse pages")
    detected_markers = sorted(
        {
            marker
            for row in page_inventory
            for marker in row.get("section_markers", [])
        }
    )
    missing_markers = sorted(set(EXPECTED_PAGE_MARKERS) - set(detected_markers))
    if missing_markers:
        failures.append(
            "page inventory is missing expected manuscript markers: "
            + ", ".join(missing_markers)
        )

    checklist = _checklist(page_count)
    boundary = {
        "manual_visual_check_required": True,
        "manual_visual_check_status": MANUAL_VISUAL_CHECK_STATUS,
        "claimed_manual_acceptance": False,
        "recorded_by_this_protocol": False,
        "manual_action_required_before_upload": True,
        "machine_render_not_human_review": True,
        "jss_upload_blocking": False,
        "archive_name": ARCHIVE_NAME,
        "archive_manifest": ARCHIVE_MANIFEST,
        "packaged_pdf_member": PACKAGED_PDF_MEMBER,
        "scope": (
            "Protocol for the final full-document human visual spot-check "
            "before JSS upload; not a completed acceptance record."
        ),
    }
    summary = {
        "page_count": page_count,
        "sampled_pages": sampled_pages,
        "checklist_item_count": len(checklist),
        "pdf_render_status": pdf_render.get("status"),
        "pdf_render_failure_count": (
            pdf_render.get("summary", {}).get("failure_count")
        ),
        "full_document_machine_scan_pages": render_summary.get(
            "full_document_rendered_page_count"
        ),
        "full_document_machine_scan_failures": render_summary.get(
            "full_document_failure_count"
        ),
        "full_document_machine_scan_not_human_review": True,
        "page_inventory_count": len(page_inventory),
        "page_inventory_text_pages": len(text_pages),
        "page_inventory_min_text_chars": min(
            (row.get("text_chars", 0) for row in page_inventory),
            default=0,
        ),
        "page_inventory_section_markers": detected_markers,
        "page_inventory_float_marker_count": sum(
            len(row.get("float_markers", [])) for row in page_inventory
        ),
        **boundary,
    }
    return {
        "generated_at_unix": _generated_at_unix(),
        "status": "PASS" if not failures else "FAIL",
        "main_pdf": str(MAIN_PDF.relative_to(PAPER_DIR)),
        "pdf_render_audit": str(PDF_RENDER_JSON.relative_to(PAPER_DIR)),
        "boundary": boundary,
        "summary": summary,
        "checklist": checklist,
        "page_inventory": page_inventory,
        "primary_evidence": [
            "manuscript/main.pdf",
            "replication/results/pdf_render_audit.md",
            "replication/results/pdf_render_audit.json",
        ],
        "failures": failures,
    }


def _write_markdown(payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    boundary = payload["boundary"]
    lines = [
        "# PDF Visual Check Protocol",
        "",
        f"Status: {payload['status']}",
        "",
        boundary["scope"],
        "This generated file does not certify that a human visual review has "
        "already been completed.",
        "",
        "## Boundary",
        "",
        f"- Main PDF: `{payload['main_pdf']}`",
        f"- PDF render audit: `{payload['pdf_render_audit']}`",
        f"- Expected archive: `{boundary['archive_name']}`",
        f"- Expected archive manifest: `{boundary['archive_manifest']}`",
        f"- Packaged PDF member: `{boundary['packaged_pdf_member']}`",
        f"- PDF pages: `{summary['page_count']}`",
        "- Sampled pages from machine render audit: `"
        + ", ".join(str(page) for page in summary["sampled_pages"])
        + "`",
        f"- Manual visual check status: `{boundary['manual_visual_check_status']}`",
        "- Full-document machine scan pages: `"
        f"{summary['full_document_machine_scan_pages']}`",
        "- Full-document machine scan failures: `"
        f"{summary['full_document_machine_scan_failures']}`",
        "- Full-document machine scan is not human review: `"
        f"{summary['full_document_machine_scan_not_human_review']}`",
        f"- Claimed manual acceptance: `{boundary['claimed_manual_acceptance']}`",
        f"- Recorded by this protocol: `{boundary['recorded_by_this_protocol']}`",
        "- Manual action required before upload: "
        f"`{boundary['manual_action_required_before_upload']}`",
        "- Machine render is not human review: "
        f"`{boundary['machine_render_not_human_review']}`",
        f"- JSS upload blocking: `{boundary['jss_upload_blocking']}`",
        "",
        "## Checklist",
        "",
        "| Item | Action | Record |",
        "|---|---|---|",
    ]
    for item in payload["checklist"]:
        lines.append(
            f"| `{item['id']}` | {item['action']} | {item['record']} |"
        )
    lines.extend(
        [
            "",
            "## Page Inventory",
            "",
            "| Page | Text chars | Section markers | Float markers | Boundary markers |",
            "|---:|---:|---|---|---|",
        ]
    )
    for row in payload["page_inventory"]:
        lines.append(
            "| {page} | {text_chars} | {sections} | {floats} | {boundaries} |".format(
                page=row["page"],
                text_chars=row["text_chars"],
                sections=", ".join(row["section_markers"]) or "--",
                floats=", ".join(row["float_markers"]) or "--",
                boundaries=", ".join(row["boundary_markers"]) or "--",
            )
        )
    lines.extend(["", "## Metrics", ""])
    for key, value in summary.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    if payload["failures"]:
        lines.append("Failures:")
        lines.extend(f"- {failure}" for failure in payload["failures"])
    else:
        lines.append("Failures: none")
    lines.extend(
        [
            "",
            f"Machine-readable detail: `{OUT_JSON.relative_to(PAPER_DIR)}`",
        ]
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = _build_payload()
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(payload)
    print(f"OK -- wrote {OUT_JSON}")
    print(f"OK -- wrote {OUT_MD}")
    if payload["failures"]:
        print("FAIL -- PDF visual-check protocol has stale or missing evidence")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

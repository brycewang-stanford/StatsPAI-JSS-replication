"""Render-sanity audit for the active JSS manuscript PDF.

Text extraction already proves that the reviewer-visible boundary wording is
present. This audit adds a layout-facing guard by rendering representative
pages with Poppler and checking that the raster outputs are plausible,
nonblank, and not overwhelmingly dark.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
PAPER_DIR = HERE.parents[1]
RESULTS_DIR = PAPER_DIR / "replication" / "results"
MAIN_PDF = PAPER_DIR / "manuscript" / "main.pdf"
TMP_ROOT = PAPER_DIR / "tmp" / "pdfs"
OUT_JSON = RESULTS_DIR / "pdf_render_audit.json"
OUT_MD = RESULTS_DIR / "pdf_render_audit.md"
SOURCE_DATE_EPOCH = os.environ.get("SOURCE_DATE_EPOCH")
DPI = 110
MIN_WIDTH = 600
MIN_HEIGHT = 800
MIN_INK_RATIO = 0.004
MAX_DARK_RATIO = 0.55
MAX_WHITE_RATIO = 0.995
MANUAL_VISUAL_SPOT_CHECK_STATUS = "PENDING_MANUAL_REVIEW"
MANUAL_VISUAL_SPOT_CHECK_NOTE = (
    "This machine render audit checks representative raster-page samples and "
    "runs all-page raster sanity thresholds; it does not certify the final "
    "full-document human visual spot-check before JSS upload."
)


def _generated_at_unix() -> int:
    if SOURCE_DATE_EPOCH is not None:
        return int(SOURCE_DATE_EPOCH)
    return int(time.time())


def _find_executable(name: str) -> Path | None:
    candidates = [
        shutil.which(name),
        f"/opt/homebrew/bin/{name}",
        f"/usr/local/bin/{name}",
        f"/usr/bin/{name}",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists() and os.access(path, os.X_OK):
            return path
    return None


def _tool_version(path: Path) -> str:
    proc = subprocess.run(
        [str(path), "-v"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return " ".join(proc.stdout.split())[:240]


def _pdf_page_count(path: Path) -> int:
    try:
        from pypdf import PdfReader  # noqa: WPS433
    except Exception as exc:  # pragma: no cover - dependency contract guard
        raise RuntimeError("pypdf is required for pdf_render_audit.py") from exc
    return len(PdfReader(str(path)).pages)


def _sample_pages(page_count: int) -> list[int]:
    if page_count <= 0:
        return []
    return sorted({1, min(2, page_count), max(1, (page_count + 1) // 2), page_count})


def _full_document_pages(page_count: int) -> list[int]:
    if page_count <= 0:
        return []
    return list(range(1, page_count + 1))


def _render_page(pdftoppm: Path, page: int, out_prefix: Path) -> tuple[Path, str]:
    proc = subprocess.run(
        [
            str(pdftoppm),
            "-png",
            "-r",
            str(DPI),
            "-f",
            str(page),
            "-l",
            str(page),
            "-singlefile",
            str(MAIN_PDF),
            str(out_prefix),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    rendered = out_prefix.with_suffix(".png")
    if proc.returncode != 0:
        raise RuntimeError(
            f"pdftoppm failed for page {page}: {proc.stdout.strip()}"
        )
    if not rendered.exists():
        raise RuntimeError(f"pdftoppm did not create {rendered}")
    return rendered, proc.stdout.strip()


def _image_metrics(path: Path) -> dict[str, Any]:
    try:
        from PIL import Image  # noqa: WPS433
    except Exception as exc:  # pragma: no cover - dependency contract guard
        raise RuntimeError("Pillow is required for pdf_render_audit.py") from exc

    with Image.open(path) as image:
        gray = image.convert("L")
        width, height = gray.size
        histogram = gray.histogram()

    pixels = width * height
    dark = sum(histogram[:35])
    white = sum(histogram[250:])
    ink = pixels - white
    return {
        "width": width,
        "height": height,
        "pixel_count": pixels,
        "ink_ratio": round(ink / pixels, 6),
        "dark_ratio": round(dark / pixels, 6),
        "white_ratio": round(white / pixels, 6),
    }


def _check_metrics(page: int, metrics: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if metrics["width"] < MIN_WIDTH:
        failures.append(f"page {page} rendered width below {MIN_WIDTH}px")
    if metrics["height"] < MIN_HEIGHT:
        failures.append(f"page {page} rendered height below {MIN_HEIGHT}px")
    if metrics["ink_ratio"] <= MIN_INK_RATIO:
        failures.append(f"page {page} looks blank")
    if metrics["dark_ratio"] >= MAX_DARK_RATIO:
        failures.append(f"page {page} looks overwhelmingly dark")
    if metrics["white_ratio"] >= MAX_WHITE_RATIO:
        failures.append(f"page {page} is almost entirely white")
    return failures


def _summary_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "min_width": min((item.get("width", 0) for item in rows), default=0),
        "min_height": min((item.get("height", 0) for item in rows), default=0),
        "min_ink_ratio": min(
            (item.get("ink_ratio", 0.0) for item in rows),
            default=0.0,
        ),
        "max_dark_ratio": max(
            (item.get("dark_ratio", 0.0) for item in rows),
            default=0.0,
        ),
        "max_white_ratio": max(
            (item.get("white_ratio", 0.0) for item in rows),
            default=0.0,
        ),
    }


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    pages: list[dict[str, Any]] = []
    full_document_pages: list[dict[str, Any]] = []

    pdftoppm = _find_executable("pdftoppm")
    page_count = 0
    sampled_pages: list[int] = []
    full_page_numbers: list[int] = []
    if not MAIN_PDF.exists():
        failures.append(f"missing manuscript PDF: {MAIN_PDF.relative_to(PAPER_DIR)}")
    else:
        try:
            page_count = _pdf_page_count(MAIN_PDF)
            sampled_pages = _sample_pages(page_count)
            full_page_numbers = _full_document_pages(page_count)
        except Exception as exc:  # pragma: no cover - recorded in output
            failures.append(str(exc))
    if pdftoppm is None:
        failures.append(
            "pdftoppm not found; install Poppler (macOS: brew install poppler, "
            "Debian/Ubuntu: apt-get install poppler-utils)"
        )

    if pdftoppm is not None and MAIN_PDF.exists() and full_page_numbers:
        with tempfile.TemporaryDirectory(prefix="render-", dir=TMP_ROOT) as tmp:
            tmpdir = Path(tmp)
            for page in full_page_numbers:
                try:
                    rendered, output = _render_page(
                        pdftoppm,
                        page,
                        tmpdir / f"main-page-{page:03d}",
                    )
                    metrics = _image_metrics(rendered)
                    page_failures = _check_metrics(page, metrics)
                    failures.extend(page_failures)
                    row = {
                        "page": page,
                        "output": output,
                        **metrics,
                        "ok": not page_failures,
                        "failures": page_failures,
                    }
                    full_document_pages.append(row)
                    if page in sampled_pages:
                        pages.append(dict(row))
                except Exception as exc:  # pragma: no cover - recorded in output
                    message = f"page {page} render failed: {exc}"
                    failures.append(message)
                    row = {"page": page, "ok": False, "failures": [message]}
                    full_document_pages.append(row)
                    if page in sampled_pages:
                        pages.append(dict(row))

    status = "PASS" if not failures else "FAIL"
    sample_metrics = _summary_metrics(pages)
    full_metrics = _summary_metrics(full_document_pages)
    full_document_failure_count = sum(
        1 for item in full_document_pages if item.get("ok") is not True
    )
    summary = {
        "page_count": page_count,
        "sampled_pages": sampled_pages,
        "rendered_page_count": len(pages),
        **sample_metrics,
        "full_document_rendered_page_count": len(full_document_pages),
        "full_document_failure_count": full_document_failure_count,
        "full_document_min_width": full_metrics["min_width"],
        "full_document_min_height": full_metrics["min_height"],
        "full_document_min_ink_ratio": full_metrics["min_ink_ratio"],
        "full_document_max_dark_ratio": full_metrics["max_dark_ratio"],
        "full_document_max_white_ratio": full_metrics["max_white_ratio"],
        "failure_count": len(failures),
        "manual_visual_spot_check_status": MANUAL_VISUAL_SPOT_CHECK_STATUS,
        "machine_render_not_human_review": True,
    }
    result = {
        "generated_at_unix": _generated_at_unix(),
        "status": status,
        "main_pdf": str(MAIN_PDF.relative_to(PAPER_DIR)),
        "renderer": {
            "name": "pdftoppm",
            "path": str(pdftoppm) if pdftoppm else None,
            "version": _tool_version(pdftoppm) if pdftoppm else None,
        },
        "dpi": DPI,
        "thresholds": {
            "min_width": MIN_WIDTH,
            "min_height": MIN_HEIGHT,
            "min_ink_ratio": MIN_INK_RATIO,
            "max_dark_ratio": MAX_DARK_RATIO,
            "max_white_ratio": MAX_WHITE_RATIO,
        },
        "summary": summary,
        "manual_preupload_visual_check": {
            "required": True,
            "status": MANUAL_VISUAL_SPOT_CHECK_STATUS,
            "recorded_by_this_audit": False,
            "machine_render_not_human_review": True,
            "note": MANUAL_VISUAL_SPOT_CHECK_NOTE,
        },
        "pages": pages,
        "full_document_pages": full_document_pages,
        "failures": failures,
    }
    OUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# PDF Render Audit",
        "",
        f"Status: {status}",
        f"Renderer: {result['renderer']['path'] or 'not found'}",
        f"Renderer version: {result['renderer']['version'] or 'n/a'}",
        f"DPI: {DPI}",
        f"PDF pages: {page_count}",
        "Sampled pages: " + ", ".join(str(page) for page in sampled_pages),
        f"Rendered pages: {len(pages)}",
        (
            "Full-document machine scan: "
            f"{summary['full_document_rendered_page_count']}/{page_count} pages; "
            f"failures={summary['full_document_failure_count']}; "
            f"min_width={summary['full_document_min_width']}; "
            f"min_height={summary['full_document_min_height']}; "
            "min_ink_ratio="
            f"{summary['full_document_min_ink_ratio']:.6f}; "
            "max_dark_ratio="
            f"{summary['full_document_max_dark_ratio']:.6f}; "
            "max_white_ratio="
            f"{summary['full_document_max_white_ratio']:.6f}"
        ),
        (
            "Metrics: "
            f"min_width={summary['min_width']}, "
            f"min_height={summary['min_height']}, "
            f"min_ink_ratio={summary['min_ink_ratio']:.6f}, "
            f"max_dark_ratio={summary['max_dark_ratio']:.6f}, "
            f"max_white_ratio={summary['max_white_ratio']:.6f}"
        ),
        (
            "Manual pre-upload visual check: "
            f"{MANUAL_VISUAL_SPOT_CHECK_STATUS} -- "
            f"{MANUAL_VISUAL_SPOT_CHECK_NOTE}"
        ),
        "",
        "| Page | Status | Size | Ink ratio | Dark ratio | White ratio |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for item in pages:
        lines.append(
            "| "
            f"{item.get('page')} | "
            f"{'PASS' if item.get('ok') else 'FAIL'} | "
            f"{item.get('width', 'n/a')}x{item.get('height', 'n/a')} | "
            f"{item.get('ink_ratio', 0.0):.6f} | "
            f"{item.get('dark_ratio', 0.0):.6f} | "
            f"{item.get('white_ratio', 0.0):.6f} |"
        )
    lines.append("")
    if failures:
        lines.append("Failures:")
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.append("Failures: none")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"OK -- wrote {OUT_JSON}")
    print(f"OK -- wrote {OUT_MD}")
    if failures:
        print("FAIL -- PDF render audit failed", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

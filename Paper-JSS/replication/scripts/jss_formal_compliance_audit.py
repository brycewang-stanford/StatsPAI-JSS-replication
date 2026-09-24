"""Aggregate formal JSS submission requirements into one reviewer report.

The heavy checks already live in narrower scripts: style, package,
reproduction environment, claim linting, and source-snapshot audits.  This
script gives reviewers one machine-readable place to see the official JSS
checklist mapped to the submitted StatsPAI evidence.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from io import BytesIO
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:  # _paths.py sits beside this script; importlib loaders do not add the script dir
    sys.path.insert(0, _SCRIPTS_DIR)

from _paths import PAPER_ROOT as _PAPER_ROOT
from _paths import release_version as _release_version
from _paths import statspai_root as _statspai_root

#: Release the manuscript describes; never hard-code it (see _paths).
RELEASE = _release_version()

#: Local screening ceiling on the manuscript's page count. JSS publishes
#: software articles of varying length and its author guidance sets no
#: hard cap, so this is conservative rather than normative. It was raised
#: from 38 to 52 when Section 4 gained printed code-and-output
#: transcripts and the parity ledger moved into an appendix -- both of
#: which a JSS reviewer asks for, neither of which is padding. Emitted in
#: the payload so tests read it back instead of repeating the number.
PAGE_CEILING = 52


HERE = Path(__file__).resolve().parent
PAPER_DIR = _PAPER_ROOT
ROOT = _statspai_root()  # see _paths.py: worktree-safe
RESULTS_DIR = PAPER_DIR / "replication" / "results"
OUT_JSON = RESULTS_DIR / "jss_formal_compliance_audit.json"
OUT_MD = RESULTS_DIR / "jss_formal_compliance_audit.md"
SOURCE_DATE_EPOCH = os.environ.get("SOURCE_DATE_EPOCH")


def _generated_at_unix() -> int:
    if SOURCE_DATE_EPOCH is not None:
        return int(SOURCE_DATE_EPOCH)
    return int(time.time())

MANUSCRIPT_DIR = PAPER_DIR / "manuscript"
MAIN_TEX = PAPER_DIR / "manuscript" / "main.tex"
MAIN_PDF = PAPER_DIR / "manuscript" / "main.pdf"
MAIN_LOG = PAPER_DIR / "manuscript" / "main.log"
PYPROJECT = ROOT / "pyproject.toml"
LICENSE = ROOT / "LICENSE"
CITATION = ROOT / "CITATION.cff"
COVER_LETTER = PAPER_DIR / "cover-letter.md"
REPRODUCE = PAPER_DIR / "replication" / "reproduce.py"
MAKEFILE = PAPER_DIR / "Makefile"
PACKAGE_MANIFEST = PAPER_DIR / "build" / "statspai-jss-submission-manifest.json"
REPRO_ENV_JSON = RESULTS_DIR / "reproduction_environment_audit.json"
MANUSCRIPT_ARTIFACT_JSON = RESULTS_DIR / "manuscript_artifact_audit.json"
PDF_RENDER_JSON = RESULTS_DIR / "pdf_render_audit.json"
AGENT_INTERFACE_JSON = RESULTS_DIR / "agent_interface_audit.json"
TIER1_TRANSCRIPT = RESULTS_DIR / "reproduce_tier1_output.txt"
SOURCE_SNAPSHOT_JSON = RESULTS_DIR / "source_snapshot_manifest.json"

DOC_HELP_FILES = {
    "README.md": ROOT / "README.md",
    "docs/getting-started.md": ROOT / "docs" / "getting-started.md",
    "docs/reference/index.md": ROOT / "docs" / "reference" / "index.md",
    "docs/guides/stability.md": ROOT / "docs" / "guides" / "stability.md",
}

OFFICIAL_SOURCES = [
    {
        "name": "JSS submissions checklist",
        "url": "https://www.jstatsoft.org/about/submissions",
    },
    {
        "name": "JSS information for authors",
        "url": "https://www.jstatsoft.org/authors",
    },
    {
        "name": "JSS style guide",
        "url": "https://www.jstatsoft.org/style",
    },
    {
        "name": "JSS submission guide",
        "url": "https://www.jstatsoft.org/guides/submission",
    },
]
OFFICIAL_SOURCES_CHECKED = "2026-08-09"

REQUIRED_FRONT_MATTER = (
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

COMPARATIVE_SCOPE_SNIPPETS = (
    r"\label{tab:related-software}",
    "Closest existing implementations and comparative scope",
    "surveyed in May 2026",
    "Where it remains the reference choice",
    r"\statspai{} contribution and boundary",
    "integration-and-validation layer around reference software",
    r"not a claim that \statspai{} supersedes",
    "T3 stochastic agreement",
    "T4",
    "separate licensed runtime",
    "larger dependency surface",
    "Comparison with existing platforms and prior art",
)

COMPARATIVE_PACKAGE_SNIPPETS = (
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
)

BLOCKING_LOG_PATTERNS = (
    re.compile(r"^! ", re.MULTILINE),
    re.compile(r"Overfull \\[hv]box"),
    re.compile(r"LaTeX Warning: Citation .* undefined"),
    re.compile(r"LaTeX Warning: Reference .* undefined"),
    re.compile(r"Package natbib Warning: Citation .* undefined"),
    re.compile(r"There were undefined (?:references|citations)"),
    re.compile(r"Rerun to get cross-references right"),
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
    "pretending it is a strict R/Synth parity pass",
    "harshest reviewer",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _project_version(pyproject_text: str) -> str | None:
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject_text, re.MULTILINE)
    if not match:
        return None
    return match.group(1)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(_read(path))


def _strip_comments(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        escaped = False
        kept: list[str] = []
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


def _comma(value: Any) -> str:
    return f"{int(value):,}" if isinstance(value, int) else str(value)


def _pdf_page_count(path: Path) -> int | None:
    try:
        from pypdf import PdfReader  # noqa: WPS433
    except Exception:
        return None
    return len(PdfReader(BytesIO(path.read_bytes())).pages)


#: The JSS running heads, which sit between the halves of any sentence
#: that straddles a page break. Left in place they make a boundary
#: snippet unfindable for reasons that have nothing to do with whether
#: the manuscript says it -- "before any behavioural claim | 32 StatsPAI:
#: Validation-Tiered Python Causal Inference | is made" is present in the
#: paper and absent from a naive substring search.
_RUNNING_HEAD = re.compile(
    r"^\s*(?:\d+\s+StatsPAI:.*|Journal of Statistical Software\s+\d+)\s*$",
    re.MULTILINE,
)


def _pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader  # noqa: WPS433
    except Exception:
        return ""
    raw = "\n".join(
        page.extract_text() or ""
        for page in PdfReader(BytesIO(path.read_bytes())).pages
    )
    return _RUNNING_HEAD.sub(" ", raw)


def _latex_log_failures(path: Path = MAIN_LOG) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    failures: list[str] = []
    for pattern in BLOCKING_LOG_PATTERNS:
        if pattern.search(text):
            failures.append(pattern.pattern)
    return failures


def _make_targets(text: str) -> set[str]:
    targets: set[str] = set()
    for line in text.splitlines():
        if not line or line.startswith(("\t", " ", "#", ".")):
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)\s*:", line)
        if match:
            targets.add(match.group(1))
    return targets


def _active_manuscript_text(main_tex: str) -> str:
    """Return main.tex plus all recursively active inputs for JSS checks."""
    parts = [main_tex]
    seen: set[Path] = set()

    def add_inputs(text: str, parent: Path) -> None:
        for rel in re.findall(r"\\input\{(?P<rel>[^}]+)\}", text):
            candidates = (MANUSCRIPT_DIR / rel, parent / rel)
            child = next((path.resolve() for path in candidates if path.exists()), None)
            if child is None or child in seen:
                continue
            seen.add(child)
            child_text = _strip_comments(_read(child))
            parts.append(child_text)
            add_inputs(child_text, child.parent)

    add_inputs(main_tex, MANUSCRIPT_DIR)
    return "\n".join(parts)


def _caption_label_failures(text: str) -> list[str]:
    failures: list[str] = []
    for env in ("table", "longtable", "figure"):
        pattern = re.compile(
            rf"\\begin\{{{env}\}}(?P<body>.*?)\\end\{{{env}\}}",
            re.DOTALL,
        )
        for idx, match in enumerate(pattern.finditer(text), start=1):
            body = match.group("body")
            if r"\caption" in body and r"\label" not in body:
                failures.append(f"{env} #{idx} has caption without label")
            caption_pos = body.find(r"\caption")
            if caption_pos < 0:
                continue
            if env == "table":
                content_positions = [
                    body.rfind(r"\end{tabular}"),
                    body.rfind(r"\end{longtable}"),
                    body.rfind(r"\input{"),
                ]
            elif env == "longtable":
                # See verify_jss_style.py for the full reasoning: a
                # longtable's head/foot blocks are definitions near the top
                # of the environment whose content renders at the bottom of
                # a page, so raw source order cannot tell a top caption from
                # a bottom one. The caption prints below the table exactly
                # when it sits inside the \endlastfoot definition.
                head_end = max(body.rfind(r"\endhead"), body.rfind(r"\endfoot"))
                last_foot = body.rfind(r"\endlastfoot")
                if last_foot >= 0 and head_end < caption_pos < last_foot:
                    continue
                content_positions = [
                    body.rfind(r"\bottomrule"),
                    last_foot,
                ]
            else:
                content_positions = [body.rfind(r"\includegraphics")]
            content_pos = max(content_positions)
            if content_pos >= 0 and caption_pos < content_pos:
                failures.append(
                    f"{env} #{idx} caption precedes content; "
                    "JSS requires captions below floats"
                )
    return failures


def _tier1_transcript_summary(text: str) -> dict[str, Any]:
    match = re.search(
        r"(?P<passed>\d+)/(?P<total>\d+) steps passed in "
        r"(?P<minutes>[0-9.]+) min",
        text,
    )
    if not match:
        return {
            "passed": None,
            "total": None,
            "minutes": None,
            "complete": False,
            "within_one_hour": False,
        }
    passed = int(match.group("passed"))
    total = int(match.group("total"))
    minutes = float(match.group("minutes"))
    return {
        "passed": passed,
        "total": total,
        "minutes": minutes,
        "complete": passed == total and total > 0,
        "within_one_hour": minutes <= 60.0,
    }


def _has_snippet(text: str, snippet: str) -> bool:
    """Find reviewer-facing snippets without depending on TeX line wraps."""
    # pypdf can drop the space at a font switch (e.g. "live\\proglang{R}"
    # extracts as "liveR"), so also compare with all whitespace removed.
    return (
        snippet in text
        or snippet in re.sub(r"\s+", " ", text)
        or re.sub(r"\s+", "", snippet) in re.sub(r"\s+", "", text)
    )


def _archive_size_disclosure_ok(
    text: str,
    *,
    expected_mib: float,
    expected_mb_decimal: float,
) -> tuple[bool, str]:
    """Check that upload-size disclosure matches the generated manifest."""
    normalized = re.sub(r"\s+", " ", text)
    matches = [
        (float(match.group("mib")), float(match.group("mb")))
        for match in re.finditer(
            r"(?P<mib>\d+\.\d{2}) MiB "
            r"\((?P<mb>\d+\.\d{2}) MB decimal\)",
            normalized,
        )
    ]
    expected = (round(expected_mib, 2), round(expected_mb_decimal, 2))
    ok = expected in matches
    return (
        ok,
        "cover-letter archive-size disclosures="
        f"{matches or []}; expected={expected_mib:.2f} MiB "
        f"({expected_mb_decimal:.2f} MB decimal); "
        "exact fixed-point match required.",
    )


def _missing_comparative_scope(text: str) -> list[str]:
    """Return missing reviewer-facing comparative-scope evidence."""
    snippets = COMPARATIVE_SCOPE_SNIPPETS + COMPARATIVE_PACKAGE_SNIPPETS
    return [snippet for snippet in snippets if not _has_snippet(text, snippet)]


def _check(name: str, ok: bool, evidence: str, failures: list[str]) -> dict[str, Any]:
    if not ok:
        failures.append(name)
    return {"requirement": name, "ok": bool(ok), "evidence": evidence}


def _optional_check(name: str, ok: bool | None, evidence: str) -> dict[str, Any]:
    return {"requirement": name, "ok": ok, "evidence": evidence}


def _output_tail(text: str, n: int = 20) -> str:
    return "\n".join(text.splitlines()[-n:])


def _display_command(cmd: list[str], tmp_path: Path | None = None) -> str:
    text = " ".join(cmd)
    if SOURCE_DATE_EPOCH is not None and tmp_path is not None:
        text = text.replace(str(tmp_path), "<tmp>")
    return text


def _install_import_probe() -> dict[str, Any]:
    """Install the source package into a temporary target and import it."""
    with tempfile.TemporaryDirectory(prefix="statspai-jss-install-") as tmp:
        tmp_path = Path(tmp)
        target = tmp_path / "target"
        target.mkdir()
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
            str(ROOT),
        ]
        install_command = _display_command(install_cmd, tmp_path)
        try:
            install = subprocess.run(
                install_cmd,
                cwd=tmp_path,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=180,
                check=False,
            )
        except Exception as exc:  # pragma: no cover - defensive environment guard
            return {
                "ok": False,
                "install_command": install_command,
                "error": repr(exc),
            }

        dist_infos = sorted(path.name for path in target.glob("*.dist-info"))
        script_dir = target / "bin"
        scripts = sorted(path.name for path in script_dir.glob("*")) if script_dir.exists() else []
        if install.returncode != 0:
            return {
                "ok": False,
                "install_command": install_command,
                "install_returncode": install.returncode,
                "install_output_tail": _output_tail(install.stdout),
                "dist_infos": dist_infos,
                "scripts": scripts,
            }

        probe_code = (
            "import json\n"
            "import statspai as sp\n"
            "print(json.dumps({"
            "'version': getattr(sp, '__version__', None), "
            "'function_count': len(sp.list_functions())"
            "}, sort_keys=True))\n"
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = (
            str(target)
            + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        )
        probe = subprocess.run(
            [sys.executable, "-c", probe_code],
            cwd=tmp_path,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=120,
            check=False,
        )
        import_payload: dict[str, Any] = {}
        if probe.stdout.strip():
            try:
                import_payload = json.loads(probe.stdout.strip().splitlines()[-1])
            except json.JSONDecodeError:
                import_payload = {}
        expected_version = _project_version(pyproject_text=_read(PYPROJECT))
        return {
            "ok": (
                probe.returncode == 0
                and bool(dist_infos)
                and import_payload.get("version") == expected_version
                and import_payload.get("function_count", 0) >= 1000
                and {"statspai", "statspai-mcp"} <= set(scripts)
            ),
            "expected_version": expected_version,
            "install_command": install_command,
            "install_returncode": install.returncode,
            "install_output_tail": _output_tail(install.stdout),
            "import_returncode": probe.returncode,
            "import_output_tail": _output_tail(probe.stdout),
            "dist_infos": dist_infos,
            "scripts": scripts,
            **import_payload,
        }


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    checks: list[dict[str, Any]] = []

    main_tex = _strip_comments(_read(MAIN_TEX)) if MAIN_TEX.exists() else ""
    active_manuscript = _active_manuscript_text(main_tex)
    page_count = _pdf_page_count(MAIN_PDF) if MAIN_PDF.exists() else None
    pdf_text = _pdf_text(MAIN_PDF) if MAIN_PDF.exists() else ""
    missing_pdf_boundary_snippets = [
        snippet for snippet in PDF_BOUNDARY_SNIPPETS
        if not _has_snippet(pdf_text, snippet)
    ]
    pdf_stale_prose_hits = [
        snippet for snippet in PDF_STALE_PROSE_SNIPPETS
        if _has_snippet(pdf_text, snippet)
    ]
    pdf_render = _read_json(PDF_RENDER_JSON) if PDF_RENDER_JSON.exists() else {}
    pdf_render_summary = pdf_render.get("summary", {})
    expected_render_pages = (
        sorted({1, min(2, page_count), max(1, (page_count + 1) // 2), page_count})
        if page_count
        else []
    )
    missing_front_matter = [
        name for name in REQUIRED_FRONT_MATTER if not _has_nonempty_macro(main_tex, name)
    ]
    markup_counts = {
        name: active_manuscript.count(f"\\{name}{{")
        for name in ("proglang", "pkg", "code")
    }
    caption_label_failures = _caption_label_failures(active_manuscript)
    latex_log_failures = _latex_log_failures()
    checks.append(
        _check(
            "PDF manuscript in JSS LaTeX article style",
            bool(
                MAIN_PDF.exists()
                and page_count
                and page_count <= PAGE_CEILING
                and r"\documentclass[article]{jss}" in main_tex
                and r"\documentclass[article,nojss]{jss}" not in main_tex
                and not missing_front_matter
                and re.search(r"\\bibliography\s*\{\s*jss-bib\s*\}", main_tex)
            ),
            (
                f"main.pdf pages={page_count}; class=article jss; "
                f"missing_front_matter={missing_front_matter or []}"
            ),
            failures,
        )
    )
    checks.append(
        _check(
            "LaTeX build log is free of blocking layout/reference errors",
            not latex_log_failures,
            (
                f"main.log present={MAIN_LOG.exists()}; "
                f"blocking_patterns={latex_log_failures or []}; "
                "underfull boxes are not treated as blocking."
            ),
            failures,
        )
    )
    checks.append(
        _check(
            "PDF-visible validation/source/data/agent boundaries are present",
            bool(pdf_text and not missing_pdf_boundary_snippets),
            (
                "main.pdf text contains validation-tier, API-stable denominator, "
                "source-snapshot/release, data-provenance, and mechanical-agent "
                "boundary snippets; "
                f"missing={missing_pdf_boundary_snippets or []}."
            ),
            failures,
        )
    )
    checks.append(
        _check(
            "PDF text is synchronized with polished manuscript prose",
            bool(pdf_text and not pdf_stale_prose_hits),
            (
                "main.pdf text is checked for stale defensive reviewer-facing "
                f"phrases; stale_hits={pdf_stale_prose_hits or []}."
            ),
            failures,
        )
    )
    checks.append(
        _check(
            "rendered PDF page-sample sanity check passes",
            bool(
                pdf_render.get("status") == "PASS"
                and pdf_render_summary.get("page_count") == page_count
                and pdf_render_summary.get("sampled_pages") == expected_render_pages
                and pdf_render_summary.get("rendered_page_count")
                == len(expected_render_pages)
                and pdf_render_summary.get("failure_count") == 0
                and pdf_render_summary.get("min_width", 0) >= 600
                and pdf_render_summary.get("min_height", 0) >= 800
                and pdf_render_summary.get("min_ink_ratio", 0) > 0.004
                and pdf_render_summary.get("max_dark_ratio", 1) < 0.55
                and pdf_render_summary.get("max_white_ratio", 1) < 0.995
                and pdf_render_summary.get("full_document_rendered_page_count")
                == page_count
                and pdf_render_summary.get("full_document_failure_count") == 0
                and pdf_render_summary.get("full_document_min_width", 0) >= 600
                and pdf_render_summary.get("full_document_min_height", 0) >= 800
                and pdf_render_summary.get("full_document_min_ink_ratio", 0) > 0.004
                and pdf_render_summary.get("full_document_max_dark_ratio", 1) < 0.55
                and pdf_render_summary.get("full_document_max_white_ratio", 1) < 0.995
            ),
            (
                "pdf_render_audit renders representative pages and rejects "
                "blank, overwhelmingly dark, or implausibly small rasters, "
                "then scans every PDF page with the same machine thresholds; "
                f"status={pdf_render.get('status')}; "
                f"sampled={pdf_render_summary.get('sampled_pages')}; "
                f"rendered={pdf_render_summary.get('rendered_page_count')}; "
                "full_scan="
                f"{pdf_render_summary.get('full_document_rendered_page_count')}/"
                f"{page_count}; "
                "full_failures="
                f"{pdf_render_summary.get('full_document_failure_count')}; "
                f"min_width={pdf_render_summary.get('min_width')}; "
                f"min_height={pdf_render_summary.get('min_height')}; "
                f"min_ink_ratio={pdf_render_summary.get('min_ink_ratio')}; "
                f"max_dark_ratio={pdf_render_summary.get('max_dark_ratio')}; "
                f"failures={pdf_render_summary.get('failure_count')}."
            ),
            failures,
        )
    )
    checks.append(
        _check(
            "JSS markup macros and labelled floats are used",
            bool(
                all(count > 0 for count in markup_counts.values())
                and not caption_label_failures
            ),
            (
                "active manuscript markup counts="
                f"{markup_counts}; caption_label_failures="
                f"{caption_label_failures or []}."
            ),
            failures,
        )
    )

    pyproject = _read(PYPROJECT) if PYPROJECT.exists() else ""
    license_text = _read(LICENSE) if LICENSE.exists() else ""
    citation_text = _read(CITATION) if CITATION.exists() else ""
    cover_letter = _read(COVER_LETTER) if COVER_LETTER.exists() else ""
    install_probe = _install_import_probe()
    source_package_static_ok = bool(
        (ROOT / "src" / "statspai").is_dir()
        and "[build-system]" in pyproject
        and 'build-backend = "setuptools.build_meta"' in pyproject
        and '[tool.setuptools.packages.find]' in pyproject
        and 'where = ["src"]' in pyproject
        and '[project.scripts]' in pyproject
        and '"Development Status :: 4 - Beta"' in pyproject
        and '"Development Status :: 3 - Alpha"' not in pyproject
    )
    checks.append(
        _check(
            "source code is packaged for installation",
            source_package_static_ok and install_probe.get("ok") is True,
            (
                "pyproject.toml uses setuptools, src layout, and console "
                "entry points; development classifier is Beta rather than "
                "Alpha; pip --no-deps --target install/import probe "
                f"ok={install_probe.get('ok')}; "
                f"version={install_probe.get('version')}; "
                f"functions={install_probe.get('function_count')}; "
                f"scripts={install_probe.get('scripts')}; "
                f"dist_infos={install_probe.get('dist_infos')}."
            ),
            failures,
        )
    )
    missing_help = [rel for rel, path in DOC_HELP_FILES.items() if not path.exists()]
    reference_text = (
        _read(DOC_HELP_FILES["docs/reference/index.md"])
        if DOC_HELP_FILES["docs/reference/index.md"].exists()
        else ""
    )
    stability_text = (
        _read(DOC_HELP_FILES["docs/guides/stability.md"])
        if DOC_HELP_FILES["docs/guides/stability.md"].exists()
        else ""
    )
    checks.append(
        _check(
            "formatted package help/documentation files are included",
            bool(
                not missing_help
                and "sp.list_functions" in reference_text
                and "sp.describe_function" in reference_text
                and "sp.function_schema" in reference_text
                and "validation_status" in stability_text
                and "api_stable" in stability_text
            ),
            (
                "README plus getting-started, reference, and stability docs "
                f"present; missing_help={missing_help or []}."
            ),
            failures,
        )
    )
    checks.append(
        _check(
            "GPL-compatible software license is clearly indicated",
            bool(
                "MIT License" in license_text
                and 'license = "MIT"' in pyproject
                and "MIT licence, which is GPL-compatible"
                in cover_letter
            ),
            "LICENSE, pyproject.toml, and cover letter all identify MIT/GPL compatibility.",
            failures,
        )
    )
    checks.append(
        _check(
            "software citation metadata is included",
            bool(
                "cff-version: 1.2.0" in citation_text
                and "repository-artifact: \"https://pypi.org/project/StatsPAI/\""
                in citation_text
                and "license: MIT" in citation_text
            ),
            "Root CITATION.cff identifies the software, license, code repository, and PyPI artifact.",
            failures,
        )
    )

    reproduce = _read(REPRODUCE) if REPRODUCE.exists() else ""
    makefile = _read(MAKEFILE) if MAKEFILE.exists() else ""
    transcript = _read(TIER1_TRANSCRIPT) if TIER1_TRANSCRIPT.exists() else ""
    tier1_summary = _tier1_transcript_summary(transcript)
    targets = _make_targets(makefile)
    checks.append(
        _check(
            "standalone replication script covers manuscript results",
            bool(
                REPRODUCE.exists()
                and {"reproduce-tier1", "reproduce-tier2", "reproduce-tier3"}
                <= targets
                and tier1_summary["complete"] is True
                and "Every Section 4-7 headline number was rebuilt without R or Stata."
                in transcript
                and "RESULT: OK -- all required steps reproduced." in transcript
            ),
            "replication/reproduce.py plus Makefile tiers; Tier-1 transcript is complete.",
            failures,
        )
    )
    checks.append(
        _check(
            "reviewer output transcript for standalone replication script is included",
            bool(
                TIER1_TRANSCRIPT.exists()
                and tier1_summary["complete"] is True
                and "RESULT: OK -- all required steps reproduced." in transcript
            ),
            (
                "Tier-1 transcript file is included and records "
                f"{tier1_summary['passed']}/{tier1_summary['total']} "
                "successful steps."
            ),
            failures,
        )
    )
    checks.append(
        _check(
            "short reviewer replication path completes within one hour",
            bool(
                tier1_summary["complete"] is True
                and tier1_summary["within_one_hour"] is True
            ),
            (
                "Tier-1 transcript reports "
                f"{tier1_summary['passed']}/{tier1_summary['total']} steps in "
                f"{tier1_summary['minutes']} minutes; JSS asks for a short "
                "reviewer-verification path when full replication is heavier."
            ),
            failures,
        )
    )
    checks.append(
        _check(
            "existing implementations and comparative scope are discussed",
            not (missing_comparative := _missing_comparative_scope(active_manuscript)),
            (
                "Active manuscript includes a related-software table with "
                "cross-ecosystem comparators, reference-choice boundaries, "
                "StatsPAI contribution/boundary language, empirical-comparison "
                "pointers, and explicit non-supersession/T3/T4/licensing "
                f"limits; missing_related_tokens={missing_comparative or []}."
            ),
            failures,
        )
    )
    checks.append(
        _check(
            "Monte Carlo content is framed as validation rather than a standalone simulation study",
            bool(
                _has_snippet(cover_letter, "not an estimator-research paper")
                and _has_snippet(active_manuscript, "representative, not exhaustive")
                and _has_snippet(
                    active_manuscript,
                    r"Track B checks 95\% interval coverage on known DGPs",
                )
                and _has_snippet(
                    active_manuscript,
                    "descriptive failure-mode checks, not pass/fail calibration claims",
                )
            ),
            (
                "JSS discourages extensive simulation studies; the cover letter "
                "and active manuscript frame the Monte Carlo rows as validation "
                "artifacts and failure-mode guards, not as a new-estimator "
                "simulation campaign."
            ),
            failures,
        )
    )

    source_snapshot = (
        _read_json(SOURCE_SNAPSHOT_JSON) if SOURCE_SNAPSHOT_JSON.exists() else {}
    )
    source_payload = source_snapshot.get("jss_source_snapshot", {})
    checks.append(
        _check(
            "source-snapshot and final-release boundaries are explicit",
            bool(
                source_snapshot.get("version_consistent_inside_source") is True
                and "not a JSS upload reproducibility failure"
                in str(source_payload.get("submission_archive_status", ""))
                and _has_snippet(
                    active_manuscript,
                    "This article describes \\statspai{} \\StatsPAIVersion{}",
                )
                and _has_snippet(
                    active_manuscript,
                    "tag \\code{v\\StatsPAIVersion{}}",
                )
            ),
            (
                "active manuscript separates the audited upload archive from "
                "later tag/changelog/release-cut cleanup; "
                "snapshot_status="
                f"{source_payload.get('submission_archive_status')}; "
                "version_consistent="
                f"{source_snapshot.get('version_consistent_inside_source')}."
            ),
            failures,
        )
    )

    repro_env = _read_json(REPRO_ENV_JSON) if REPRO_ENV_JSON.exists() else {}
    rng = repro_env.get("random_seeding", {})
    manuscript_artifacts = (
        _read_json(MANUSCRIPT_ARTIFACT_JSON)
        if MANUSCRIPT_ARTIFACT_JSON.exists()
        else {}
    )
    checks.append(
        _check(
            "platform dependencies and RNG seeds are disclosed",
            bool(
                repro_env.get("status") == "PASS"
                and repro_env.get("renv_lock_present") is True
                and repro_env.get("stata_environment_present") is True
                and "every Section 4--7 headline number was" in cover_letter
                and "rebuilt without R or Stata" in cover_letter
                and rng.get("unseeded_stochastic_file_count") == 0
            ),
            (
                "reproduction_environment_audit records Docker/Python/R/Stata "
                "contracts and the cover letter discloses the no-R/no-Stata "
                "Tier-1 headline path; "
                f"unseeded_rng={rng.get('unseeded_stochastic_file_count')}."
            ),
            failures,
        )
    )
    agent_interface = (
        _read_json(AGENT_INTERFACE_JSON) if AGENT_INTERFACE_JSON.exists() else {}
    )
    agent_schema = agent_interface.get("schema_quality", {})
    cover_letter_expected_snippets = [
        f"{page_count} pages" if page_count else "",
        (
            f"{tier1_summary['passed']}/{tier1_summary['total']}"
            if tier1_summary["total"]
            else ""
        ),
        (
            f"{repro_env.get('r_reproduced_modules')}-module R-parity"
            if repro_env.get("r_reproduced_modules") is not None
            else ""
        ),
        (
            f"{repro_env.get('stata_reproduced_modules')}-module Stata bridge"
            if repro_env.get("stata_reproduced_modules") is not None
            else ""
        ),
        (
            f"{_comma(agent_schema.get('public_surface'))} registered public functions"
            if agent_schema.get("public_surface") is not None
            else ""
        ),
        (
            f"{_comma(agent_schema.get('public_surface'))} public functions"
            if agent_schema.get("public_surface") is not None
            else ""
        ),
        (
            f"{_comma(agent_schema.get('parameter_total'))} schema parameters"
            if agent_schema.get("parameter_total") is not None
            else ""
        ),
        (
            f"tagged {source_snapshot.get('source_init_version')} release"
            if source_snapshot.get("source_init_version")
            else ""
        ),
        "13 PASS evidence cards",
        "5 suggested review routes",
        "editor triage",
        "statistical validation",
        "quick reproduction",
        "agent-interface review",
        "limitations/release-boundary review",
    ]
    cover_letter_archive_size_ok = True
    cover_letter_archive_size_evidence = "package manifest absent; size not checked"
    if PACKAGE_MANIFEST.exists():
        package_manifest = _read_json(PACKAGE_MANIFEST)
        if (
            package_manifest.get("size_mib") is not None
            and package_manifest.get("size_mb_decimal") is not None
        ):
            (
                cover_letter_archive_size_ok,
                cover_letter_archive_size_evidence,
            ) = _archive_size_disclosure_ok(
                cover_letter,
                expected_mib=float(package_manifest.get("size_mib")),
                expected_mb_decimal=float(
                    package_manifest.get("size_mb_decimal")
                ),
            )
        if package_manifest.get("file_count") is not None:
            cover_letter_expected_snippets.append(
                f"{_comma(package_manifest.get('file_count'))} files"
            )
    cover_letter_expected_snippets = [
        snippet for snippet in cover_letter_expected_snippets if snippet
    ]
    missing_cover_letter_snippets = [
        snippet for snippet in cover_letter_expected_snippets
        if not _has_snippet(cover_letter, snippet)
    ]
    if not cover_letter_archive_size_ok:
        missing_cover_letter_snippets.append("archive-size disclosure exact match")
    checks.append(
        _check(
            "cover letter numeric summary is synchronized with generated audit artifacts",
            bool(
                cover_letter_expected_snippets
                and cover_letter_archive_size_ok
                and not missing_cover_letter_snippets
            ),
            (
                "cover-letter expected snippets="
                f"{cover_letter_expected_snippets}; "
                f"missing={missing_cover_letter_snippets or []}; "
                f"{cover_letter_archive_size_evidence}"
            ),
            failures,
        )
    )
    cover_letter_pdf_boundary_snippets = [
        "pdf_render_audit.{json,md}",
        "representative PDF pages and an all-page machine scan",
        "final full-document visual spot-check remains an upload-time manual action",
        f"{page_count}-row page inventory",
        "rather than a machine-verified PASS",
    ]
    missing_cover_letter_pdf_boundary = [
        snippet
        for snippet in cover_letter_pdf_boundary_snippets
        if not _has_snippet(cover_letter, snippet)
    ]
    checks.append(
        _check(
            "cover letter PDF visual-check boundary is explicit",
            not missing_cover_letter_pdf_boundary,
            (
                "cover-letter PDF/manual-review snippets="
                f"{cover_letter_pdf_boundary_snippets}; "
                f"missing={missing_cover_letter_pdf_boundary or []}."
            ),
            failures,
        )
    )
    editor_disclosure_snippets = [
        "published in the *Journal of Open Source",
        "doi.org/10.21105/joss.10604",
        "cites the JOSS paper explicitly",
        "disclosed explicitly to the editors",
        "StatsPAI Inc.",
        "CoPaper.AI",
        "No external funder",
        "MIT licence",
    ]
    missing_editor_disclosures = [
        snippet for snippet in editor_disclosure_snippets
        if not _has_snippet(cover_letter, snippet)
    ]
    checks.append(
        _check(
            "cover letter related-review and conflict disclosures are explicit",
            not missing_editor_disclosures,
            (
                "cover-letter related-review/COI snippets="
                f"{editor_disclosure_snippets}; "
                f"missing={missing_editor_disclosures or []}."
            ),
            failures,
        )
    )
    checks.append(
        _check(
            "active manuscript tables and figures map to generators and prose",
            bool(
                manuscript_artifacts.get("status") == "PASS"
                and manuscript_artifacts.get("artifact_count", 0) >= 1
                and manuscript_artifacts.get("hash_mismatches") == 0
                and manuscript_artifacts.get("missing_narrative_refs") == []
                and manuscript_artifacts.get("dangling_float_refs") == []
                and manuscript_artifacts.get("compact_section_coverage", {}).get("ok")
                is True
            ),
            (
                "manuscript_artifact_audit maps active table/figure inputs "
                f"to generators; artifacts={manuscript_artifacts.get('artifact_count')}; "
                f"hash_mismatches={manuscript_artifacts.get('hash_mismatches')}; "
                "float_labels="
                f"{len(manuscript_artifacts.get('active_float_labels', []))}; "
                "missing_refs="
                f"{len(manuscript_artifacts.get('missing_narrative_refs', []))}; "
                "dangling_refs="
                f"{len(manuscript_artifacts.get('dangling_float_refs', []))}; "
                "compact_sections="
                f"{manuscript_artifacts.get('compact_section_coverage', {}).get('sections_passed')}/"
                f"{manuscript_artifacts.get('compact_section_coverage', {}).get('sections_checked')}; "
                "compact_missing_anchors="
                f"{manuscript_artifacts.get('compact_section_coverage', {}).get('missing_anchor_count')}."
            ),
            failures,
        )
    )

    if PACKAGE_MANIFEST.exists():
        manifest = _read_json(PACKAGE_MANIFEST)
        archive_size_mib = manifest.get("size_mib", manifest.get("size_mb", 1000))
        archive_size_mb_decimal = manifest.get(
            "size_mb_decimal",
            archive_size_mib,
        )
        archive_size_bytes = manifest.get("size_bytes", 0)
        archive_present: bool | None = True
        checks.append(
            _check(
                "JSS attachment size and archive source set are bounded",
                bool(
                    manifest.get("within_jss_attachment_limit") is True
                    and archive_size_bytes > 0
                    and archive_size_mib <= 50
                    and archive_size_mb_decimal <= 50
                    and manifest.get("registry_evidence_file_count", 0) > 0
                    and "src/statspai" in manifest.get("included_roots", [])
                ),
                (
                    f"archive={archive_size_mib} MiB "
                    f"({archive_size_mb_decimal} MB decimal); "
                    f"files={manifest.get('file_count')}; "
                    f"evidence_files={manifest.get('registry_evidence_file_count')}"
                ),
                failures,
            )
        )
        checks.append(
            _check(
                "ASCII source/data contract is enforced inside the archive",
                bool(
                    set(manifest.get("ascii_source_suffixes", []))
                    == {".R", ".do", ".py", ".sh", ".toml"}
                    and set(manifest.get("ascii_data_suffixes", []))
                    == {".csv", ".json", ".lock"}
                ),
                (
                    "submission packager normalizes source suffixes and the "
                    "verifier decodes checked source/data files as ASCII."
                ),
                failures,
            )
        )
    else:
        archive_present = False
        checks.append(
            _optional_check(
                "JSS attachment size and archive source set are bounded",
                None,
                "submission archive has not been built in this tree yet.",
            )
        )
        checks.append(
            _optional_check(
                "ASCII source/data contract is enforced inside the archive",
                None,
                "submission archive has not been built in this tree yet.",
            )
        )

    status = "PASS" if not failures else "FAIL"
    result = {
        "generated_at_unix": _generated_at_unix(),
        "official_sources_checked": OFFICIAL_SOURCES_CHECKED,
        "official_sources": OFFICIAL_SOURCES,
        "status": status,
        "archive_present": archive_present,
        "page_count": page_count,
        "page_ceiling": PAGE_CEILING,
        "pdf_text_chars": len(pdf_text),
        "pdf_boundary_snippets": list(PDF_BOUNDARY_SNIPPETS),
        "missing_pdf_boundary_snippets": missing_pdf_boundary_snippets,
        "pdf_stale_prose_snippets": list(PDF_STALE_PROSE_SNIPPETS),
        "pdf_stale_prose_hits": pdf_stale_prose_hits,
        "pdf_render": {
            "status": pdf_render.get("status"),
            "page_count": pdf_render_summary.get("page_count"),
            "sampled_pages": pdf_render_summary.get("sampled_pages", []),
            "rendered_page_count": pdf_render_summary.get("rendered_page_count"),
            "failure_count": pdf_render_summary.get("failure_count"),
            "min_width": pdf_render_summary.get("min_width"),
            "min_height": pdf_render_summary.get("min_height"),
            "min_ink_ratio": pdf_render_summary.get("min_ink_ratio"),
            "max_dark_ratio": pdf_render_summary.get("max_dark_ratio"),
            "max_white_ratio": pdf_render_summary.get("max_white_ratio"),
            "full_document_rendered_page_count": pdf_render_summary.get(
                "full_document_rendered_page_count"
            ),
            "full_document_failure_count": pdf_render_summary.get(
                "full_document_failure_count"
            ),
            "full_document_min_width": pdf_render_summary.get(
                "full_document_min_width"
            ),
            "full_document_min_height": pdf_render_summary.get(
                "full_document_min_height"
            ),
            "full_document_min_ink_ratio": pdf_render_summary.get(
                "full_document_min_ink_ratio"
            ),
            "full_document_max_dark_ratio": pdf_render_summary.get(
                "full_document_max_dark_ratio"
            ),
            "full_document_max_white_ratio": pdf_render_summary.get(
                "full_document_max_white_ratio"
            ),
        },
        "tier1_transcript": tier1_summary,
        "install_probe": install_probe,
        "checks": checks,
        "failures": failures,
    }
    OUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# JSS Formal Compliance Audit",
        "",
        f"Status: {status}",
        f"Official JSS pages checked: {OFFICIAL_SOURCES_CHECKED}",
        "",
        "Official sources:",
    ]
    lines.extend(f"- {item['name']}: {item['url']}" for item in OFFICIAL_SOURCES)
    lines.extend(["", "Checklist:"])
    for check in checks:
        if check["ok"] is True:
            marker = "PASS"
        elif check["ok"] is False:
            marker = "FAIL"
        else:
            marker = "PENDING"
        lines.append(f"- {marker} -- {check['requirement']}: {check['evidence']}")
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
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

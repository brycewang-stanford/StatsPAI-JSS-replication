"""Check the active manuscript uses submission-facing JSS style scaffolding."""
from __future__ import annotations

import re
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
PAPER_DIR = HERE.parents[1]
MAIN_TEX = PAPER_DIR / "manuscript" / "main.tex"
MANUSCRIPT_DIR = PAPER_DIR / "manuscript"
MAIN_LOG = PAPER_DIR / "manuscript" / "main.log"

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

FORBIDDEN_REDEFINITIONS = (
    "code",
    "pkg",
    "proglang",
    "email",
    "doi",
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
    pattern = re.compile(rf"\\{re.escape(name)}\s*\{{(?P<body>.*?)\}}", re.DOTALL)
    match = pattern.search(text)
    if not match:
        return False
    body = re.sub(r"\s+", "", match.group("body"))
    return bool(body)


def _latex_log_failures(path: Path = MAIN_LOG) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    failures: list[str] = []
    for pattern in BLOCKING_LOG_PATTERNS:
        if pattern.search(text):
            failures.append(pattern.pattern)
    return failures


def _active_manuscript_text(main_tex: str) -> str:
    """Return main.tex plus all recursively active inputs for style checks."""
    parts = [main_tex]
    seen: set[Path] = set()

    def add_inputs(text: str, parent: Path) -> None:
        for rel in re.findall(r"\\input\{(?P<rel>[^}]+)\}", text):
            candidates = (MANUSCRIPT_DIR / rel, parent / rel)
            child = next((path.resolve() for path in candidates if path.exists()), None)
            if child is None or child in seen:
                continue
            seen.add(child)
            child_text = _strip_comments(child.read_text(encoding="utf-8"))
            parts.append(child_text)
            add_inputs(child_text, child.parent)

    add_inputs(main_tex, MANUSCRIPT_DIR)
    return "\n".join(parts)


def _float_style_failures(text: str) -> list[str]:
    failures: list[str] = []
    for env in ("table", "longtable", "figure"):
        pattern = re.compile(
            rf"\\begin\{{{env}\}}(?P<body>.*?)\\end\{{{env}\}}",
            re.DOTALL,
        )
        for idx, match in enumerate(pattern.finditer(text), start=1):
            body = match.group("body")
            if r"\caption" in body and r"\label" not in body:
                failures.append(f"{env} #{idx} has a caption but no label")
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
                # A longtable's caption placement cannot be read off source
                # order: \endfirsthead / \endhead / \endfoot / \endlastfoot
                # are *definitions* near the top of the environment whose
                # content renders at the top or bottom of each page. The
                # caption prints below the table exactly when it sits inside
                # the last-foot definition, i.e. after \endhead (or \endfoot)
                # and before \endlastfoot. Comparing raw offsets instead
                # rejects every possible placement, which is how a correct
                # bottom caption came to be reported as a top caption.
                head_end = max(body.rfind(r"\endhead"), body.rfind(r"\endfoot"))
                last_foot = body.rfind(r"\endlastfoot")
                if last_foot >= 0 and head_end < caption_pos < last_foot:
                    continue  # caption is inside \endlastfoot: renders below
                content_positions = [
                    body.rfind(r"\bottomrule"),
                    last_foot,
                ]
            else:
                content_positions = [body.rfind(r"\includegraphics")]
            content_pos = max(content_positions)
            if content_pos >= 0 and caption_pos < content_pos:
                failures.append(
                    f"{env} #{idx} caption precedes its content; "
                    "JSS requires captions below tables and figures"
                )
    return failures


def main() -> int:
    raw_text = MAIN_TEX.read_text(encoding="utf-8")
    text = _strip_comments(raw_text)
    active_text = _active_manuscript_text(text)
    match = re.search(r"\\documentclass(?:\[(?P<opts>[^\]]*)\])?\{(?P<class>[^}]*)\}", text)
    if not match:
        print(f"FAIL -- no documentclass found in {MAIN_TEX}", file=sys.stderr)
        return 1

    cls = match.group("class").strip()
    opts = {
        opt.strip()
        for opt in (match.group("opts") or "").split(",")
        if opt.strip()
    }
    failures: list[str] = []
    if cls != "jss":
        failures.append(f"document class is {cls!r}, expected 'jss'")
    if "article" not in opts:
        failures.append("documentclass options must include 'article'")
    if "nojss" in opts:
        failures.append("'nojss' is for package-vignette derivatives, not the JSS manuscript")
    if opts != {"article"}:
        failures.append(
            f"documentclass options are {sorted(opts)!r}, expected exactly ['article']"
        )

    missing_front_matter = [
        name for name in REQUIRED_FRONT_MATTER
        if not _has_nonempty_macro(text, name)
    ]
    if missing_front_matter:
        failures.append(
            "missing or empty JSS front-matter macros: "
            + ", ".join(f"\\{name}" for name in missing_front_matter)
        )

    if r"\begin{document}" not in text or r"\end{document}" not in text:
        failures.append("manuscript must contain \\begin{document} and \\end{document}")

    if not re.search(r"\\bibliography\s*\{\s*jss-bib\s*\}", text):
        failures.append("manuscript must include BibTeX via \\bibliography{jss-bib}")

    markup_counts = {
        name: active_text.count(f"\\{name}{{")
        for name in ("proglang", "pkg", "code")
    }
    missing_markup = [name for name, count in markup_counts.items() if count == 0]
    if missing_markup:
        failures.append(
            "active manuscript does not use required JSS markup macros: "
            + ", ".join(f"\\{name}" for name in missing_markup)
        )

    float_style_failures = _float_style_failures(active_text)
    if float_style_failures:
        failures.append(
            "JSS float-style failures: " + "; ".join(float_style_failures)
        )

    redefined = [
        name for name in FORBIDDEN_REDEFINITIONS
        if re.search(rf"\\(?:newcommand|renewcommand|def)\s*\{{?\\{re.escape(name)}\}}?", text)
    ]
    if redefined:
        failures.append(
            "do not redefine JSS-provided macros: "
            + ", ".join(f"\\{name}" for name in redefined)
        )

    log_failures = _latex_log_failures()
    if log_failures:
        failures.append(
            "LaTeX build log contains blocking layout/reference errors: "
            + ", ".join(log_failures)
        )

    if failures:
        for failure in failures:
            print(f"FAIL -- {failure}", file=sys.stderr)
        return 1
    print(
        f"OK -- {MAIN_TEX.relative_to(PAPER_DIR)} uses "
        "\\documentclass[article]{jss} with complete JSS front matter; "
        "markup counts="
        + ", ".join(f"{name}:{count}" for name, count in markup_counts.items())
        + "; floats are labelled and captions follow their content"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Audit JSS-facing house-style and polish risks in the active submission.

This is intentionally narrower than claim linting. It checks for reviewer-facing
rough edges that are easy to reintroduce while iterating on a compact JSS paper:
draft markers, marketing phrasing, weak JSS macro hygiene, and missing disclosure
anchors in the active manuscript and upload-facing notes.
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
OUT_JSON = RESULTS_DIR / "jss_house_style_audit.json"
OUT_MD = RESULTS_DIR / "jss_house_style_audit.md"
SOURCE_DATE_EPOCH = os.environ.get("SOURCE_DATE_EPOCH")

ACTIVE_SECTION_FILES = [
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
    )
]

ACTIVE_STYLE_FILES = [
    PAPER_DIR / "manuscript" / "main.tex",
    PAPER_DIR / "manuscript" / "jss-bib.bib",
    PAPER_DIR / "manuscript" / "README.md",
    PAPER_DIR / "README.md",
    PAPER_DIR / "cover-letter.md",
    PAPER_DIR / "REVIEWER-HARDENING-AUDIT.md",
    PAPER_DIR / "requirements-jss.txt",
    *ACTIVE_SECTION_FILES,
]

DRAFT_MARKER_PATTERNS = (
    r"\bTODO\b",
    r"\bTBD\b",
    r"\bFIXME\b",
    r"lorem ipsum",
    r"placeholder",
    r"under construction",
    r"do not submit",
    "CITATION-" + "PENDING",
    r"article[- ]class " + "draft",
    r"article " + "draft",
    r"review " + "draft",
    r"earlier " + "drafts",
    r"draft " + "build",
    r"draft " + "previously",
    r"draft " + "used",
    r"\bthis " + r"draft\b",
)

MARKETING_PATTERNS = (
    r"world[- ]class",
    r"best[- ]in[- ]class",
    "gold" + r" standard",
    r"drop[- ]in replacement",
    r"state[- ]of[- ]the[- ]art",
    r"publication[- ]ready",
    r"journal[- ]ready",
    r"one[- ]click",
    "most" + r" comprehensive",
    r"feature[- ]complete",
)

OVERCONFIDENCE_PATTERNS = (
    r"audit artifacts that prove",
    r"transcript proves",
    r"\baudit prove that\b",
    r"\bare proven from the submitted archive",
    r"\bledger proves\b",
    r"\baudit proves\b",
    r"stronger current guarantee",
    r"This guarantees that",
)

DEFENSIVE_TONE_PATTERNS = (
    r"unflattering denominator",
    r"hiding it would be worse",
    r"silent wins",
    r"users pay for",
    r"must be read row by row",
    r"limitations are blunt",
    r"pretend(?:ing)?",
    r"harshest reviewer",
)

REQUIRED_ANCHORS = {
    "manuscript/sections/01-introduction-compact.tex": (
        "integration-and-validation layer around reference software",
        "contribution and boundary",
        "reference implementations in their home domains",
        "read in three layers",
        "replication archive",
        "reviewer evidence map and editor screening checklist",
        "statistical evidence",
        "stable software infrastructure",
    ),
    "manuscript/sections/05-parity-compact.tex": (
        "certified/validated",
        "API-stable",
        "not parity-backed",
    ),
    "manuscript/sections/03-agent-facing-compact.tex": (
        "software-interface contribution",
        "tool discovery, failure recovery, result reuse, and citation",
        "schema/MCP/citation reproducibility",
    ),
    "manuscript/sections/07-agent-eval.tex": (
        "The JSS contribution here is contractual",
        "same validation ledger",
        "rather than from a separate\nprompt-engineering layer",
    ),
    "manuscript/sections/09-discussion-compact.tex": (
        "not a new-estimator paper",
        "main limitations are as follows",
        "named rows and modules in the validation-suite evidence",
        "nine scoped limitation rows",
        "named function, evidence grade",
        "only one Track~A row remains a methodological/T4 disclosure",
        "data-dependent non-uniqueness",
        "remaining\nclassical-SCM reference-disagreement disclosure",
        "The unification itself has costs",
        "Conflict of interest",
        "AI usage disclosure",
    ),
    "cover-letter.md": (
        "published in the *Journal of Open Source",
        "cites the JOSS paper explicitly",
        "final full-document visual spot-check",
        "page inventory",
        "Conflicts of interest",
        "MIT licence",
    ),
}

MIN_MACRO_COUNTS = {
    "proglang": 50,
    "pkg": 80,
    "code": 150,
}


def _generated_at_unix() -> int:
    if SOURCE_DATE_EPOCH is not None:
        return int(SOURCE_DATE_EPOCH)
    return int(time.time())


def _rel(path: Path) -> str:
    return str(path.relative_to(PAPER_DIR))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _has_snippet(text: str, snippet: str) -> bool:
    return snippet in text or snippet in re.sub(r"\s+", " ", text)


def _pattern_hits(patterns: tuple[str, ...]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for path in ACTIVE_STYLE_FILES:
        text = _read(path)
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern in patterns:
                if re.search(pattern, line, flags=re.IGNORECASE):
                    hits.append(
                        {
                            "path": _rel(path),
                            "line": lineno,
                            "pattern": pattern,
                            "text": line.strip(),
                        }
                    )
    return hits


def _macro_counts() -> dict[str, int]:
    text = "\n".join(_read(path) for path in [PAPER_DIR / "manuscript" / "main.tex", *ACTIVE_SECTION_FILES])
    return {
        "proglang": text.count(r"\proglang{"),
        "pkg": text.count(r"\pkg{"),
        "code": text.count(r"\code{"),
    }


def _anchor_failures() -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for rel_path, snippets in REQUIRED_ANCHORS.items():
        path = PAPER_DIR / rel_path
        text = _read(path)
        missing = [snippet for snippet in snippets if not _has_snippet(text, snippet)]
        if missing:
            failures.append({"path": rel_path, "missing": missing})
    return failures


def _check(name: str, ok: bool, evidence: str, failures: list[str]) -> dict[str, Any]:
    if not ok:
        failures.append(name)
    return {"requirement": name, "ok": bool(ok), "evidence": evidence}


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    missing_files = [_rel(path) for path in ACTIVE_STYLE_FILES if not path.exists()]
    draft_hits = _pattern_hits(DRAFT_MARKER_PATTERNS) if not missing_files else []
    marketing_hits = _pattern_hits(MARKETING_PATTERNS) if not missing_files else []
    overconfidence_hits = _pattern_hits(OVERCONFIDENCE_PATTERNS) if not missing_files else []
    defensive_tone_hits = _pattern_hits(DEFENSIVE_TONE_PATTERNS) if not missing_files else []
    macro_counts = _macro_counts() if not missing_files else {}
    macro_failures = [
        f"{name}={macro_counts.get(name, 0)} < {minimum}"
        for name, minimum in MIN_MACRO_COUNTS.items()
        if macro_counts.get(name, 0) < minimum
    ]
    anchor_failures = _anchor_failures() if not missing_files else []

    checks = [
        _check(
            "active JSS style files are present",
            not missing_files,
            f"missing={missing_files}",
            failures,
        ),
        _check(
            "active JSS files are free of draft markers",
            not draft_hits,
            f"hits={len(draft_hits)}",
            failures,
        ),
        _check(
            "active JSS files avoid marketing-style claims",
            not marketing_hits,
            f"hits={len(marketing_hits)}",
            failures,
        ),
        _check(
            "upload-facing prose avoids overconfident proof or guarantee wording",
            not overconfidence_hits,
            f"hits={len(overconfidence_hits)}",
            failures,
        ),
        _check(
            "upload-facing prose avoids defensive or casual reviewer-facing phrasing",
            not defensive_tone_hits,
            f"hits={len(defensive_tone_hits)}",
            failures,
        ),
        _check(
            "active manuscript keeps JSS macro density",
            not macro_failures,
            f"macro_counts={macro_counts}; thresholds={MIN_MACRO_COUNTS}; failures={macro_failures}",
            failures,
        ),
        _check(
            "upload-facing prose retains contribution, boundary, and disclosure anchors",
            not anchor_failures,
            f"anchor_failures={anchor_failures}",
            failures,
        ),
    ]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "generated_at_unix": _generated_at_unix(),
        "status": status,
        "summary": {
            "checked_files": [_rel(path) for path in ACTIVE_STYLE_FILES],
            "active_section_count": len(ACTIVE_SECTION_FILES),
            "draft_marker_hits": len(draft_hits),
            "marketing_claim_hits": len(marketing_hits),
            "overconfidence_claim_hits": len(overconfidence_hits),
            "defensive_tone_hits": len(defensive_tone_hits),
            "macro_counts": macro_counts,
            "macro_thresholds": MIN_MACRO_COUNTS,
            "macro_failures": macro_failures,
            "anchor_failure_count": len(anchor_failures),
        },
        "checks": checks,
        "draft_marker_hits": draft_hits,
        "marketing_claim_hits": marketing_hits,
        "overconfidence_claim_hits": overconfidence_hits,
        "defensive_tone_hits": defensive_tone_hits,
        "anchor_failures": anchor_failures,
        "failures": failures,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# JSS House-Style Audit",
        "",
        f"Status: {status}",
        f"Checked files: {len(payload['summary']['checked_files'])}",
        f"Active sections: {len(ACTIVE_SECTION_FILES)}",
        f"Draft-marker hits: {len(draft_hits)}",
        f"Marketing-claim hits: {len(marketing_hits)}",
        f"Overconfidence-claim hits: {len(overconfidence_hits)}",
        f"Defensive-tone hits: {len(defensive_tone_hits)}",
        "Macro counts: "
        + ", ".join(f"{name}={value}" for name, value in macro_counts.items()),
        f"Anchor failures: {len(anchor_failures)}",
        "",
        "## Checks",
        "",
        "| Requirement | Status | Evidence |",
        "|---|---:|---|",
    ]
    for check in checks:
        lines.append(
            "| "
            + check["requirement"]
            + " | "
            + ("PASS" if check["ok"] else "FAIL")
            + " | "
            + str(check["evidence"]).replace("|", r"\|")
            + " |"
        )
    if draft_hits or marketing_hits or overconfidence_hits or defensive_tone_hits or anchor_failures:
        lines.extend(["", "## Failures", ""])
        for item in draft_hits:
            lines.append(f"- draft marker `{item['pattern']}` at `{item['path']}:{item['line']}`")
        for item in marketing_hits:
            lines.append(f"- marketing phrase `{item['pattern']}` at `{item['path']}:{item['line']}`")
        for item in overconfidence_hits:
            lines.append(f"- overconfident proof/guarantee wording `{item['pattern']}` at `{item['path']}:{item['line']}`")
        for item in defensive_tone_hits:
            lines.append(f"- defensive or casual phrasing `{item['pattern']}` at `{item['path']}:{item['line']}`")
        for item in anchor_failures:
            lines.append(f"- missing anchors in `{item['path']}`: {item['missing']}")
    else:
        lines.extend(["", "Failures: none"])
    lines.append("")
    lines.append(f"Machine-readable detail: `{OUT_JSON.relative_to(PAPER_DIR)}`")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"OK -- wrote {OUT_JSON}")
    print(f"OK -- wrote {OUT_MD}")
    if failures:
        print("FAIL -- JSS house-style audit found reviewer-facing polish issues")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

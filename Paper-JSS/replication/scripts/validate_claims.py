"""Lint reviewer-facing validation claims for the JSS submission.

This guard keeps the paper from drifting back to a blanket "Validated"
claim. It scans submission-facing/package-facing files for required scoped
language, and selected historical drafts for dangerous stale claims only.
"""

from __future__ import annotations

import json
import os
import argparse
import re
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:  # _paths.py sits beside this script; importlib loaders do not add the script dir
    sys.path.insert(0, _SCRIPTS_DIR)

from _paths import PAPER_ROOT as PAPER_DIR
from _paths import expected_stata_module_count as _expected_stata
from _paths import expected_r_module_count as _expected_r
from _paths import release_version as _release_version
from _paths import resolve_claim_path as _resolve
from _paths import statspai_root

ROOT = statspai_root()
RESULTS_DIR = PAPER_DIR / "replication" / "results"
OUT_JSON = RESULTS_DIR / "claim_lint.json"
OUT_MD = RESULTS_DIR / "claim_lint.md"
SOURCE_DATE_EPOCH = os.environ.get("SOURCE_DATE_EPOCH")



def _snippet(*parts: str) -> str:
    """Compose stale-claim sentinels without leaving grep-visible claims."""
    return "".join(parts)


CLAIM_FILES = [
    "Paper-JSS/manuscript/main.tex",
    "Paper-JSS/manuscript/sections/01-introduction-compact.tex",
    "Paper-JSS/manuscript/sections/02-architecture-compact.tex",
    "Paper-JSS/manuscript/sections/05-parity-compact.tex",
    "Paper-JSS/manuscript/sections/09-discussion-compact.tex",
    "Paper-JSS/manuscript/tables/track_a_cross_language_snapshot.tex",
    "Paper-JSS/manuscript/tables/appendix_b_parity.tex",
    "Paper-JSS/README.md",
    "Paper-JSS/cover-letter.md",
    "Paper-JSS/REVIEWER-HARDENING-AUDIT.md",
    "Paper-JSS/manuscript/README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "CONTRIBUTORS.md",
    "papers/run_replication.py",
    "papers/run_experiments.py",
    "tools/audit_citations.py",
    "src/statspai/diagnostics/rddensity.py",
    "src/statspai/synth/sdid.py",
    "src/statspai/smart/assumptions.py",
    "src/statspai/smart/compare.py",
    "src/statspai/smart/recommend.py",
    "src/statspai/smart/__init__.py",
    "src/statspai/smart/publication.py",
    "src/statspai/smart/sensitivity.py",
    "pyproject.toml",
    "docs/index.md",
    "docs/getting-started.md",
    "docs/guides/stability.md",
    "docs/guides/agent_native_workflow.md",
    "docs/guides/synth.md",
    "docs/agent_cards_spec.md",
    "docs/reference/index.md",
    "docs/reference/decomposition.md",
    "docs/reference/synth.md",
    "docs/stats.md",
    "docs/jss_source_audit_dossier.md",
]

JOSS_PROTECTED_FILES = [
    "paper.md",
    "README.md",
    "README_CN.md",
    "CITATION.cff",
    "src/statspai/CITATION.cff",
    "docs/joss_reviewer_guide.md",
    "docs/joss_validation_dossier.md",
    "StatsPAI_full_data_analysis_skill/SKILL.md",
]

HISTORICAL_DRIFT_FILES = [
    "Paper-JSS/JSS-research-plan.md",
    "Paper-JSS/NEXT-STEPS.md",
    "Paper-JSS/manuscript/main-zh.md",
    "Paper-JSS/manuscript/sections/01-introduction.tex",
    "Paper-JSS/manuscript/sections/02-architecture.tex",
    "Paper-JSS/manuscript/sections/03-agent-facing.tex",
    "Paper-JSS/manuscript/sections/04-examples.tex",
    "Paper-JSS/manuscript/sections/05-parity.tex",
    "Paper-JSS/manuscript/sections/08-computational-details.tex",
    "Paper-JSS/manuscript/sections/appendix.tex",
]

FORBIDDEN_SNIPPETS = [
    "Validated Python Workflows",
    r"Validated \proglang{Python} Workflows",
    "A Validated Python Interface",
    _snippet("fully ", "validated package"),
    "Development Status :: 3 - Alpha",
    # NB: the project is JOSS-primary again; the JSS source snapshot under
    # Paper-JSS/ is a secondary artifact, so mentioning JOSS / the JOSS
    # reviewer guide in submission-facing docs is permitted. Only blanket
    # over-claims below remain forbidden.
    "JOSS paper paper",
    "final manual PDF visual check, and the agent-interface value boundary",
    "source-snapshot evidence remains the 2026-06-28 source snapshot",
    "four currently pending final tagged-cut checks",
    "7,096",
    "7{,}096",
    "2,360 (33.3%)",
    "2,360（33.3%）",
    "2{,}360 (33.3\\%)",
    "206 (2.9%)",
    "206（2.9%）",
    "550+ top-level functions",
    "all exported helpers are validated",
    "every exported helper is validated",
    "Every estimator returns a unified ``CausalResult``",
    _snippet("Every result object exposes ", "the same interface"),
    "common result contract",
    "common result objects",
    _snippet("shared result-", "object contract"),
    _snippet("same result-", "object contract"),
    "one result-object contract",
    "The same result objects expose",
    "across every registered estimator",
    "Every result object has:",
    "Every result object speaks the same export protocol",
    "Every result object follows the same contract",
    "Most Comprehensive",
    "most comprehensive",
    "most complete across ecosystems",
    "full coverage",
    "Python's first feature-complete implementation",
    "Python's first unified CATE learner race",
    "Python's first unified spatial econometrics package",
    "most feature-complete RD package",
    "first power-analysis tool",
    "gold standard",
    "empirical research workflow",
    "publication-grade",
    "publication-ready",
    "manuscript-ready",
    "journal-ready",
    "one-click",
    "one click",
    "One-Click Comprehensive",
    "state-of-the-art",
    "state of the art",
    "full research workflow",
    "full-stack",
    "single, consistent Python API",
    "single unified API",
    "all in one place",
    "Stata has almost none",
    "R has them scattered",
    "matches R's 5-package spatial stack",
    "Neither Stata nor R",
    "R has no equivalent",
    "Stata requires paid add-ons",
    "one-call comprehensive",
    "comprehensive report",
    "No competing package",
    "No other package",
    "No other package does this",
    "no other package has these",
    "No other econometrics package",
    "no other econometrics package",
    "unique to StatsPAI",
    "Unique to StatsPAI",
    "StatsPAI's unique differentiator",
    "any language — offers this",
    "available in any language",
    "Word + Excel + LaTeX + HTML in every function",
    "Every estimator: `.to_word()`",
    "Full Python replication",
    "Data-driven bandwidth with formal optimality",
    _snippet("StatsPAI: An Agent-", "Native Python Toolkit"),
    "full applied-econometrics surface",
    "Public estimators return structured result objects rather than raw tuples",
    "all variants return compatible result objects",
    "首个为 LLM",
    "任何语言的包都没有这个能力",
    "任何语言里覆盖最完整",
    "本表中覆盖最广",
    "完整覆盖",
    "所有估计器返回同样",
    _snippet("所有估计器共享一个公共结果对象", "契约"),
    "相同的结果对象与 schema 契约",
    "每个估计器都直接支持",
    "每个函数都支持 Word",
    "同等或更强的功能覆盖",
    "Cross-validated against Stata/R reference values",
    "forest row remains a T4 stochastic calibration disclosure",
    "T4 stochastic calibration disclosure",
    "T4 stochastic-calibration disclosure",
    "`13_causal_forest` remains the only methodological-difference tier",
    "methodological-difference tolerance",
    (
        "still presented as a stochastic calibration disclosure rather than "
        "as a strict cross-language equality win"
    ),
    "The remaining priority is forest AIPW calibration",
    _snippet("AIPW vs grf, \\(z{=}0.69\\); ", "pass"),
    (
        _snippet("Causal forest (AIPW) & rel $\\le 0.037$ {\\footnotesize ")
        + _snippet("(clean-overlap AIPW vs grf; recovers truth)} & ")
        + _snippet("\\emph{no canonical ref} & \\textbf{", "PASS}")
    ),
    "cells are placeholders pending",
    "GPU placeholder notebook",
    "placeholder notebook",
    "short reviewer guide",
    "JSS validation dossier",
    _snippet("36 R-", "parity modules"),
    _snippet("21 Stata-", "parity modules"),
    "A100 row pending separate run",
    "tiers (6 / 26 / 10 / 9 on the 51 R-joined modules)",
    _snippet("T4_native_", "regularisation_disclosure"),
    _snippet("sdid_", "regularisation_convention_gap"),
    _snippet("regularisation-zeta ", "convention gap"),
    _snippet(
        "Native SDID remains a ",
        "regularisation-zeta convention disclosure",
    ),
    "12 / 26 / 10 / 3 on the 51 R-joined modules",
    "13 / 26 / 10 / 2 on the 51 R-joined modules",
    "11 / 26 / 10 / 4 on the 51 R-joined modules",
    "11 / 27 / 10 / 3 on the 51 R-joined modules",
    "12 / 27 / 10 / 2 on the 51 R-joined modules",
    "55 \\proglang{R}-parity modules",
    "for 44 of them, plus the separate",
    "all 44 R-joined",
    "46 of 47 data-driven modules",
    "5{,}424 passed",
    "5{,}424 个通过",
    "44 个跳过",
    "55 模块 **R** 对齐夹具",
    "44 模块精选 **Stata** 桥接",
    "48 receive a pass-type verdict, 3 are T4",
    "49 receive a pass-type verdict, 2 are T4",
    _snippet("50 receive a pass-type verdict, ", "1 is a T4"),
    "50 receive a pass-type verdict, 1 is labelled",
    "50 receive a pass-type verdict",
    "51 \\proglang{R}-parity modules",
    "the 51 R-parity modules",
    "augmented-SCM and generalized-SCM Basque rows are also T4",
    "augmented SCM and generalized SCM are native convention gaps",
    "all three loose/stochastic Track A rows are classified",
    "Three Track A rows remain loose/stochastic rather than deterministic",
    "four methodological/T4 Track A rows are classified",
    "Four Track A rows are methodological/T4 rather than deterministic",
    "both loose/stochastic Track A rows are classified",
    "Two Track A rows remain loose/stochastic rather than deterministic",
    "two methodological/T4 Track A rows are classified",
    "Two Track A rows are methodological/T4 rather than deterministic",
    "generalized SCM keeps a factor-normalisation T4 disclosure",
    "generalized SCM is a native factor-convention gap",
    "gsynth_native_factor_convention_gap",
    "remaining SCM-family default gaps",
    "augsynth reference backend",
    "gsynth reference backend",
    "T4_native_selector_disclosure",
    "rddensity_bandwidth_selector_gap",
    "default-bandwidth convention gap",
    "native default bandwidth selector and local-density estimates can differ",
    "native evidence is conclusion-level, not selector/test-statistic parity",
    "dependency-light RD bandwidths differ from CCT defaults unless",
    "validated-or-better`.  Each may only go up",
    "certified` / `validated-or-better`.  Each may only go up",
]

HISTORICAL_FORBIDDEN_SNIPPETS = FORBIDDEN_SNIPPETS + [
    _snippet("模块 13 从 ", "GAP"),
    "模块 13 仍作为 T4 随机森林校准披露",
    "paper2026jo" "ss",
    "9 行现在标为约定缺口而非通过",
    _snippet("48", " \\code{certified} symbols"),
    _snippet("196", " \\code{validated} symbols"),
    _snippet("773", " \\code{api\\_stable} symbols"),
    _snippet("772", " \\code{api\\_stable} symbols"),
    _snippet("48", " certified"),
    _snippet("196", " validated"),
    _snippet("773", " API-stable"),
    _snippet("772", " API-stable"),
    _snippet("245", " registry symbols are certified/validated"),
    _snippet("245", " certified/validated registry symbols"),
]

def _registry_evidence_snippets() -> list[str]:
    """The stability guide's evidence-file count, read from the built package.

    The count is a property of the archive, so the packager's manifest is
    its only source of truth; a literal here went stale at every release
    (422, then 473, while the archive shipped 483). Before the first
    package build there is no manifest, and verify_submission_package.py
    enforces the same sentence against the manifest it builds.
    """
    manifest = PAPER_DIR / "build" / "statspai-jss-submission-manifest.json"
    if not manifest.exists():
        return []
    count = json.loads(manifest.read_text(encoding="utf-8")).get(
        "registry_evidence_file_count"
    )
    return [f"{count} such registry evidence files"] if count else []


REQUIRED_SNIPPETS = {
    "Paper-JSS/manuscript/main.tex": [
        "Validation-Tiered",
        "evidence tier that a user or an agent can query at call time",
        "licence-free replication path",
    ],
    "Paper-JSS/manuscript/sections/05-parity-compact.tex": [
        "(together \\RegistryCertifiedValidated{})",
        "\\RegistryAutoUnbacked{} stable auto-registered\nsymbols are API-stable but not parity-backed",
        "stochastic T3 equivalence claim",
        "\\RParityPassCount{} receive a pass-type verdict",
        "two\nnon-T2 Track A rows",
        "is a T4\nidentification/reference-disagreement disclosure",
        "calibrated Basque replica",
        "Native \\code{sp.augsynth} now ports \\pkg{augsynth}",
        "Native \\code{sp.gsynth} now ports \\pkg{gsynth}",
        "one specification, two data sets",
        "no printed vignette anchor",
    ],
    "Paper-JSS/manuscript/sections/02-architecture-compact.tex": [
        "Mature estimator paths return",
        "remain\nregistered with explicit stability and validation\nmetadata",
        "validated or mature variants return compatible result surfaces",
    ],
    "Paper-JSS/manuscript/sections/01-introduction-compact.tex": [
        "evidence tier rather than a blanket claim over the whole API surface",
        "the full census opens Section~\\ref{sec:parity}",
        "integration-and-validation layer around reference software",
        "Where it remains the reference choice",
        "contribution and boundary",
        "records disagreements as ledger entries rather than",
        "strict parity claims",
        "standardizes cross-family handoffs",
    ],
    "Paper-JSS/manuscript/sections/03-agent-facing-compact.tex": [
        "software-interface contribution",
        "tool discovery, failure recovery, result reuse, and citation",
        "schema/MCP/citation reproducibility",
    ],
    "Paper-JSS/manuscript/sections/07-agent-eval.tex": [
        "To make that deferral auditable",
        "agent\\_benchmark\\_protocol.md",
        "matched arms, task families, scoring dimensions, leakage controls",
        "before any behavioural claim is made",
    ],
    "Paper-JSS/manuscript/tables/track_a_cross_language_snapshot.tex": [
        "T3; seed-replicated",
        "Basque replica",
        "mpdta} replica",
    ],
    "Paper-JSS/manuscript/tables/appendix_b_parity.tex": [
        "Causal forest (AIPW)",
        "T3; single draw per engine",
        "\\textbf{PASS}",
    ],
    "Paper-JSS/manuscript/sections/09-discussion-compact.tex": [
        "\\RegistryAutoUnbacked{} stable auto-registered symbols remain API-stable but not parity-backed",
        "validated claim is limited to certified/validated entries",
        "named rows and modules in the validation-suite evidence",
        "nine scoped limitation rows",
        "named function, evidence grade",
        "The unification itself has costs",
        "cross-validation selectors",
        "data-dependent non-uniqueness",
    ],
    "Paper-JSS/README.md": [
        'validated" as a registry evidence tier, not as a blanket claim',
        "certified/validated symbols and",
    ],
    "Paper-JSS/cover-letter.md": [
        "Validation-Tiered Python Workflows",
        'validated" is used as a scoped evidence claim',
        "common reporting surface for mature estimator results",
        "shared surface and evidence ledger make cross-family handoffs auditable",
        "reference implementations in their home domains",
        f"complete {_expected_r()}/{_expected_r()} R modules and {_expected_stata()}/{_expected_stata()} Stata modules",
        "final full-document visual spot-check remains an upload-time manual action",
        "page inventory",
    ],
        "Paper-JSS/REVIEWER-HARDENING-AUDIT.md": [
            "Last updated: 2026-09-23",
            f"describes the tagged {_release_version()} release",
            "one methodological/T4 Track A row is classified",
            "One Track A row is methodological/T4 rather than deterministic",
        ],
    "docs/guides/stability.md": [
        "API lifecycle",
        "numerical validation evidence",
        "api_stable",
        "not numerically validated",
        *_registry_evidence_snippets(),
        "JSS source-snapshot validation audit (2026-06-28)",
    ],
    "docs/guides/agent_native_workflow.md": [
        "`validation_status`",
        "treat `api_stable` as an API contract rather than numerical validation",
    ],
    "docs/agent_cards_spec.md": [
        "Validation-status counts are evidence-audit outputs, not vanity floors",
        "they may go down when a function is honestly demoted",
    ],
    "README.md": [
        "`validation_status` distinguishes certified/validated evidence from API-stable breadth",
    ],
    "README_CN.md": [
        "`validation_status`",
        "certified / validated / api_stable",
        "docs/jss_source_audit_dossier.md",
    ],
    "CHANGELOG.md": [
        "`13_causal_forest` is now a T3 combined-Monte-Carlo-error pass",
        "72 / 7 / 1 / 1 on the 81 R-joined modules",
        "active Track C table is generated from measured CPU benchmarks",
        'sp.synth(method="classic", backend="synth")',
    ],
    "src/statspai/diagnostics/rddensity.py": [
        "rdbwdensity combination",
        "backend='r'",
    ],
    "src/statspai/synth/sdid.py": [
        'backend="synthdid"',
        "native implementation is validation-tiered separately",
    ],
    "src/statspai/smart/assumptions.py": [
        "registered workflow for checking common assumption",
    ],
    "src/statspai/smart/compare.py": [
        "registered workflow for running several estimators",
        "Multi-method comparison with agreement diagnostics",
    ],
    "src/statspai/smart/recommend.py": [
        "registered workflow helper",
        "validation status",
    ],
    "src/statspai/smart/__init__.py": [
        "Registered workflow helpers",
        "replication support",
    ],
    "src/statspai/smart/publication.py": [
        "registered venue-specific checklists",
    ],
    "src/statspai/smart/sensitivity.py": [
        "multi-axis sensitivity workflow",
    ],
    "pyproject.toml": [
        "Validation-tiered causal inference and econometrics workflows for Python",
        "Development Status :: 4 - Beta",
    ],
    "docs/index.md": [
        "Validation-tiered Python workflows",
        "Registered functions are discoverable programmatically",
    ],
    "docs/guides/synth.md": [
        "Validation status remains method-specific",
        "broad API coverage is not a blanket parity claim",
    ],
    "docs/reference/decomposition.md": [
        "method-level validation metadata",
    ],
    "docs/reference/synth.md": [
        "validation-tier metadata",
    ],
    "docs/stats.md": [
        "Supported result objects",
    ],
    "docs/jss_source_audit_dossier.md": [
        "JSS Source-Audit Dossier",
        "not a blanket validation claim",
        "JSS source-snapshot audit date: 2026-06-28",
        "Tier 1 path intentionally does not require live R or Stata",
        "commercial downstream product",
    ],
}


def _claim_counts() -> dict[str, int]:
    sys.path.insert(0, str(ROOT / "scripts"))
    import stability_audit  # noqa: WPS433

    sys.path.insert(0, str(ROOT / "src"))
    import statspai as sp  # noqa: WPS433

    stats = stability_audit.collect()
    validation_counts = Counter(
        sp.describe_function(name).get("validation_status", "unknown")
        for name in sp.list_functions()
    )
    return {
        "registry": stats["totals"]["registry"],
        "certified_validated": stats["parity_coverage"]["registry_validated_symbols"],
        "certified": validation_counts["certified"],
        "validated": validation_counts["validated"],
        "api_stable": validation_counts["api_stable"],
        "experimental": validation_counts["experimental"],
        "unbacked_auto": stats["parity_coverage"]["unbacked_auto"],
        "unbacked_handwritten": stats["parity_coverage"]["unbacked_handwritten"],
        "registry_evidence_unique": stats["evidence_paths"]["unique"],
        # Track A ledger size, read from the committed result files rather
        # than from a generated audit, so the pin is not circular.
        "r_modules": len(
            list((ROOT / "tests" / "r_parity" / "results").glob("*_py.json"))
        ),
        "stata_modules": len(
            list((ROOT / "tests" / "stata_parity" / "results").glob("*_Stata.json"))
        ),
    }


def _dynamic_required_snippets(counts: dict[str, int]) -> dict[str, list[str]]:
    certified = counts["certified_validated"]
    unbacked_auto = counts["unbacked_auto"]
    registry = counts["registry"]
    claim_file_count = len(CLAIM_FILES)
    registry_text = f"{registry:,}"
    certified_n = counts["certified"]
    validated_n = counts["validated"]
    api_stable_n = counts["api_stable"]
    experimental_n = counts["experimental"]
    r_modules = counts["r_modules"]
    stata_modules = counts["stata_modules"]
    status_sentence = (
        f"{certified_n} certified symbols, {validated_n} validated symbols, "
        f"{api_stable_n} API-stable symbols, and {experimental_n} "
        "experimental symbols"
    )
    tex_status_sentence = (
        f"{certified_n} \\code{{certified}} symbols, {validated_n} "
        f"\\code{{validated}} symbols, {api_stable_n} "
        f"\\code{{api\\_stable}} symbols, and {experimental_n} "
        "\\code{experimental} symbols"
    )
    markdown_status_sentence = (
        f"{certified_n} `certified`, {validated_n} `validated`, "
        f"{api_stable_n} `api_stable`, and {experimental_n} "
        "`experimental` registry symbols"
    )
    return {
        "Paper-JSS/cover-letter.md": [
            status_sentence,
        ],
        "Paper-JSS/manuscript/README.md": [
            f"claim-lint PASS across {claim_file_count} submission-facing files",
            f"all {certified} certified/validated symbols",
            f"{certified} registry symbols with certified/validated evidence",
            f"{unbacked_auto} stable auto-registered symbols",
            "reviewer evidence map reports PASS with 13 cards and 0 failed cards",
            "without expanding the compact PDF",
        ],
        "Paper-JSS/manuscript/sections/05-parity-compact.tex": [
            "(together \\RegistryCertifiedValidated{})",
            "the remaining \\RegistryAutoUnbacked{} stable auto-registered symbols are API-stable but not parity-backed",
        ],
        "Paper-JSS/manuscript/sections/09-discussion-compact.tex": [
            "\\RegistryAutoUnbacked{} stable auto-registered symbols remain API-stable but not parity-backed",
            "nine scoped limitation rows",
            "named function, evidence grade",
        ],
        "Paper-JSS/README.md": [
            (
                f"{certified} certified/validated symbols and {unbacked_auto} "
                "stable auto-registered symbols"
            ),
            (
                f"the status counts are {certified_n} `certified`, "
                f"{validated_n} `validated`, {api_stable_n} `api_stable`, "
                f"and {experimental_n} `experimental`"
            ),
            f"all {stata_modules} committed Stata JSONs",
        ],
        "Paper-JSS/REVIEWER-HARDENING-AUDIT.md": [
            (f"{certified} registry symbols with certified/validated " "evidence"),
            (f"{unbacked_auto} stable auto-registered symbols still " "unbacked"),
            "Last updated: 2026-09-23",
            f"describes the tagged {_release_version()} release",
            (
                "reports `PASS` across the upload-facing claim surface"
            ),
            f"{r_modules} Track A modules",
            f"{r_modules} R modules and {stata_modules} R-joined Stata references",
            f"{stata_modules} JSONs, matching do-files",
        ],
        "docs/guides/stability.md": [
            f"Current JSS source-snapshot audit counts:",
            markdown_status_sentence,
            f"{unbacked_auto} stable auto-registered symbols",
        ],
        "docs/jss_source_audit_dossier.md": [
            f"{registry_text} registered public functions",
            markdown_status_sentence,
            f"{certified} symbols",
            f"{unbacked_auto} stable auto-registered symbols",
            f"{counts['registry_evidence_unique']} registry-evidence source files",
        ],
    }


def _merge_required_snippets(
    base: dict[str, list[str]],
    dynamic: dict[str, list[str]],
) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {key: list(value) for key, value in base.items()}
    for rel, snippets in dynamic.items():
        merged.setdefault(rel, [])
        for snippet in snippets:
            if snippet not in merged[rel]:
                merged[rel].append(snippet)
    return merged


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _read(rel: str) -> str:
    return _resolve(rel).read_text(encoding="utf-8")


def _contains_forbidden_snippet(text: str, snippet: str) -> bool:
    return snippet.casefold() in text.casefold()



def _generated_at_unix() -> int:
    if SOURCE_DATE_EPOCH is not None:
        return int(SOURCE_DATE_EPOCH)
    return int(time.time())

_NUMBER_RE = re.compile(r"\d[\d,]*")


def _numeric_pattern(snippet: str) -> "tuple[re.Pattern[str], list[str]]":
    """A regex matching ``snippet`` up to its numbers and its whitespace.

    Returns the pattern plus the numbers the snippet requires, in order.
    Whitespace becomes ``\s+`` so a requirement written on one line still
    matches prose that wraps across two, and every number becomes a
    capturing group so the rewrite can substitute digits in place and
    leave the surrounding line breaks exactly as they were.
    """
    wanted = _NUMBER_RE.findall(snippet)
    parts, last = [], 0
    for m in _NUMBER_RE.finditer(snippet):
        parts.append(re.escape(snippet[last : m.start()]))
        parts.append(r"([\d,]+)")
        last = m.end()
    parts.append(re.escape(snippet[last:]))
    pattern = "".join(parts)
    # Escaped literal whitespace -> flexible whitespace.
    pattern = re.sub(r"(?:\\[ ]|\s)+", r"\\s+", pattern)
    return re.compile(pattern), wanted


def _rewrite_stale_numbers(rel: str, snippet: str) -> str:
    """Bring one required claim string up to date, digits only.

    Returns a status string. The rewrite is refused unless exactly one
    span in the file matches the requirement's shape: a claim sentence
    that appears twice, or not at all, is an editorial question rather
    than a stale number, and guessing at it is how a generator starts
    writing prose nobody reviewed.
    """
    path = _resolve(rel)
    if not path.exists():
        return f"skip (missing file): {rel}"
    text = path.read_text(encoding="utf-8")
    pattern, wanted = _numeric_pattern(snippet)
    if not wanted:
        return f"skip (no numbers to update): {rel}"
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        return f"skip ({len(matches)} shape matches, need exactly 1): {rel}"
    m = matches[0]
    span = m.group(0)
    rebuilt, cursor = [], 0
    for i, wanted_value in enumerate(wanted, start=1):
        a, b = m.start(i) - m.start(), m.end(i) - m.start()
        rebuilt.append(span[cursor:a])
        rebuilt.append(wanted_value)
        cursor = b
    rebuilt.append(span[cursor:])
    new_span = "".join(rebuilt)
    if new_span == span:
        return f"no change: {rel}"
    path.write_text(text[: m.start()] + new_span + text[m.end() :], encoding="utf-8")
    return f"updated: {rel}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help=(
            "bring stale registry counts in the prose files up to date, "
            "rewriting digits in place. Only spans that match a required "
            "claim's exact shape are touched; anything ambiguous is "
            "reported and left alone."
        ),
    )
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    checked: list[str] = []
    protected_joss_files: list[str] = []
    counts = _claim_counts()
    rewrites: list[str] = []
    required_snippets = _merge_required_snippets(
        REQUIRED_SNIPPETS,
        _dynamic_required_snippets(counts),
    )

    for rel in CLAIM_FILES:
        path = _resolve(rel)
        if not path.exists():
            failures.append(f"missing claim file: {rel}")
            continue
        text = _read(rel)
        checked.append(rel)
        for snippet in FORBIDDEN_SNIPPETS:
            if _contains_forbidden_snippet(text, snippet):
                failures.append(f"{rel}: forbidden blanket claim found: {snippet!r}")

    for rel in JOSS_PROTECTED_FILES:
        if _resolve(rel).exists():
            protected_joss_files.append(rel)

    drift_checked: list[str] = []
    for rel in HISTORICAL_DRIFT_FILES:
        path = _resolve(rel)
        if not path.exists():
            continue
        text = _read(rel)
        drift_checked.append(rel)
        for snippet in HISTORICAL_FORBIDDEN_SNIPPETS:
            if _contains_forbidden_snippet(text, snippet):
                failures.append(
                    f"{rel}: stale historical-draft claim found: {snippet!r}"
                )

    for rel, snippets in required_snippets.items():
        path = _resolve(rel)
        if not path.exists():
            failures.append(f"missing required claim file: {rel}")
            continue
        text_norm = _normalise(_read(rel))
        for snippet in snippets:
            if _normalise(snippet) in text_norm:
                continue
            if args.write:
                status = _rewrite_stale_numbers(rel, snippet)
                rewrites.append(status)
                if status.startswith("updated"):
                    # Re-read: a later snippet in the same file must see
                    # the edit this one just made.
                    text_norm = _normalise(_read(rel))
                    if _normalise(snippet) in text_norm:
                        continue
            failures.append(
                f"{rel}: required scoped-validation wording missing: {snippet!r}"
            )

    status = "PASS" if not failures else "FAIL"
    result = {
        "generated_at_unix": _generated_at_unix(),
        "status": status,
        "claim_counts": counts,
        "checked_files": checked,
        "protected_joss_files": protected_joss_files,
        "historical_drift_files": drift_checked,
        "forbidden_snippet_count": len(FORBIDDEN_SNIPPETS),
        "historical_forbidden_snippet_count": len(HISTORICAL_FORBIDDEN_SNIPPETS),
        "required_snippet_files": sorted(required_snippets),
        "failures": failures,
    }
    OUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# JSS Validation-Claim Lint",
        "",
        f"Status: {status}",
        f"Checked files: {len(checked)}",
        f"JOSS-protected files: {len(protected_joss_files)}",
        f"Historical drift files: {len(drift_checked)}",
        (
            "Dynamic counts: "
            f"{counts['certified']} certified; "
            f"{counts['validated']} validated; "
            f"{counts['api_stable']} API-stable; "
            f"{counts['experimental']} experimental; "
            f"{counts['certified_validated']} certified/validated; "
            f"{counts['unbacked_auto']} API-stable auto-registered but "
            "not parity-backed; "
            f"{counts['unbacked_handwritten']} unbacked hand-written stable"
        ),
        "",
        "Purpose: keep the JSS submission from drifting back to a blanket",
        "`Validated` claim; `validated` must remain an evidence tier with",
        "the harsh certified/validated versus API-stable denominator visible.",
        "Files that define the active JOSS review are listed separately and",
        "are not required to carry JSS manuscript boundary wording.",
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
    if rewrites:
        # Say what was rewritten. A tool that edits prose silently is
        # worse than one that refuses to: the whole point of --write is
        # that the change is reviewable in the diff that follows.
        print(f"--write touched {len(rewrites)} claim(s):")
        for line in rewrites:
            print(f"  {line}")
    if failures:
        print("FAIL -- validation-claim lint failed", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

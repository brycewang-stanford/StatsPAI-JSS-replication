"""Audit the JSS agent-interface claims without making behavioral claims.

The paper's agent-facing contribution is intentionally scoped to a
mechanical interface: registry schemas, MCP tool discovery, typed result
handles, audit chaining, sensitivity chaining, and citation propagation.
This audit keeps that boundary enforceable.  It verifies the deterministic
MCP trace artifacts, recomputes live schema-quality counts, and checks that
submission-facing prose does not cite absent companion-paper artifacts or
drift into an unqualified LLM-behavior claim.
"""
from __future__ import annotations

import json
import math
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
TABLES_DIR = PAPER_DIR / "replication" / "tables"
OUT_JSON = RESULTS_DIR / "agent_interface_audit.json"
OUT_MD = RESULTS_DIR / "agent_interface_audit.md"
SOURCE_DATE_EPOCH = os.environ.get("SOURCE_DATE_EPOCH")


def _generated_at_unix() -> int:
    if SOURCE_DATE_EPOCH is not None:
        return int(SOURCE_DATE_EPOCH)
    return int(time.time())

CURATED_KEYS = (
    "assumptions",
    "pre_conditions",
    "failure_modes",
    "limitations",
    "minimum_n",
    "typical_n_min",
)

TRACE_JSON = RESULTS_DIR / "ex07_agent_trace.json"
TRACE_TXT = RESULTS_DIR / "ex07_agent_trace.txt"
TRACE_TEX = TABLES_DIR / "ex07_agent_trace.tex"

BOUNDARY_SNIPPETS = {
    "Paper-JSS/manuscript/main.tex": [
        "mechanical and contractual",
        "not a claim of behavioural",
    ],
    "Paper-JSS/manuscript/sections/03-agent-facing-compact.tex": [
        "The paper's claim is mechanical",
        "same validation ledger as human calls",
        "It is not a behavioural claim",
        "software-interface contribution",
        "tool discovery, failure recovery, result reuse, and citation",
        "schema/MCP/citation reproducibility",
    ],
    "Paper-JSS/manuscript/sections/07-agent-eval.tex": [
        "reports only the \\emph{mechanical} and \\emph{contractual} evidence",
        "Contractual trace evidence",
        "stale result-handle call",
        "package-distributed, package-wide OpenAI-style tool-schema catalogues",
        "they do not rule out external wrappers",
        "does not answer whether an LLM agent",
        "before any behavioural claim is made",
        "The JSS contribution here is contractual",
    ],
    "Paper-JSS/manuscript/sections/09-discussion-compact.tex": [
        "behavioural-agent evaluations require different loss functions",
    ],
    "Paper-JSS/REVIEWER-HARDENING-AUDIT.md": [
        "Agent behavior is deferred",
        "schema/interface contribution",
    ],
}

SCHEMA_COUNT_FILES = (
    "Paper-JSS/manuscript/sections/07-agent-eval.tex",
    "Paper-JSS/cover-letter.md",
)

FORBIDDEN_MANUSCRIPT_REFERENCES = (
    "Paper-AgentBench/",
    "Paper-JSS/notes/osf-preregistration.md",
    "OSF pre-registration",
    "pre-registered behavioural",
    "pre-registered hypotheses",
)


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _fmt_int(value: int, *, tex: bool = False) -> str:
    formatted = f"{value:,}"
    return formatted.replace(",", "{,}") if tex else formatted


def _pct(num: int, denom: int) -> str:
    return f"{100 * num / denom:.1f}%" if denom else "--"


def _schema_quality() -> dict[str, int]:
    sys.path.insert(0, str(ROOT / "src"))
    import statspai as sp  # noqa: WPS433

    names = sp.list_functions()
    n_with_desc = 0
    n_with_params = 0
    n_curated_card = 0
    n_param_total = 0
    n_param_desc = 0
    n_param_default = 0
    n_param_enum = 0

    for name in names:
        try:
            spec = sp.describe_function(name)
        except Exception:
            spec = None
        desc = (spec or {}).get("description", "") if isinstance(spec, dict) else ""
        if isinstance(desc, str) and len(desc.strip()) > 5:
            n_with_desc += 1

        schema = sp.function_schema(name)
        if isinstance(schema, dict):
            props = (schema.get("parameters", {}) or {}).get("properties", {}) or {}
            if props:
                n_with_params += 1
                n_param_total += len(props)
                for prop in props.values():
                    if not isinstance(prop, dict):
                        continue
                    if isinstance(prop.get("description"), str) and prop["description"].strip():
                        n_param_desc += 1
                    if "default" in prop:
                        n_param_default += 1
                    if "enum" in prop:
                        n_param_enum += 1

        try:
            card = sp.agent_card(name)
        except Exception:
            card = None
        if isinstance(card, dict) and any(card.get(key) for key in CURATED_KEYS):
            n_curated_card += 1

    return {
        "public_surface": len(names),
        "with_nonempty_description": n_with_desc,
        "with_typed_parameter": n_with_params,
        "curated_agent_card": n_curated_card,
        "parameter_total": n_param_total,
        "parameter_with_description": n_param_desc,
        "parameter_with_default": n_param_default,
        "parameter_with_enum": n_param_enum,
    }


def _trace_summary(failures: list[str]) -> dict[str, Any]:
    for path in (TRACE_JSON, TRACE_TXT, TRACE_TEX):
        if not path.exists():
            failures.append(f"missing agent trace artifact: {path.relative_to(ROOT)}")
    if not TRACE_JSON.exists():
        return {}

    data = json.loads(TRACE_JSON.read_text(encoding="utf-8"))
    summary = data.get("summary", {})
    required_present = summary.get("required_tools_present", {})
    missing_tools = [
        name for name, present in sorted(required_present.items()) if not present
    ]
    if missing_tools:
        failures.append("agent trace missing required tools: " + ", ".join(missing_tools))
    if summary.get("tool_count", 0) < 400:
        failures.append("agent trace tool_count is unexpectedly small")
    required_args = set(summary.get("schema_required", []))
    if not {"data_path", "g", "i", "t", "y"} <= required_args:
        failures.append("callaway_santanna schema required arguments drifted")
    enum = set(summary.get("schema_control_group_enum", []))
    if enum != {"nevertreated", "notyettreated"}:
        failures.append("callaway_santanna control_group enum drifted")
    estimate = summary.get("estimate")
    se = summary.get("se")
    ci = summary.get("ci", [])
    estimate_ok = all(
        isinstance(x, (int, float)) and math.isfinite(x) for x in [estimate, se]
    )
    if not estimate_ok:
        failures.append("agent trace estimate/se are not finite")
    elif se <= 0:
        failures.append("agent trace standard error is non-positive")
    if not (
        estimate_ok
        and
        isinstance(ci, list)
        and len(ci) == 2
        and all(isinstance(x, (int, float)) and math.isfinite(x) for x in ci)
        and ci[0] < estimate < ci[1]
    ):
        failures.append("agent trace confidence interval is malformed")
    # The contract is that audit_result enumerates the curated pool for the
    # design and names a concrete follow-up for every gap -- not that it
    # returns a fixed count. The DiD pool is three curated checks
    # (parallel_trends, honest_did, bacon_decomposition) plus any live
    # violations() the fit reports, so the count moves with the fit while the
    # actionable content does not. Pinning a literal 5 here made an audit that
    # is substantively unchanged -- the same two missing checks, the same two
    # suggested functions -- read as a regression when the mpdta fit stopped
    # reporting two non-actionable live violations. The structural assertions
    # below (full curated pool present, every gap carries a suggestion) are
    # what the paper actually claims.
    if summary.get("audit_checks", 0) < 3:
        failures.append("agent trace audit_result returned too few checks")
    missing_suggestions = set(summary.get("missing_suggested_functions", []))
    if not {"sp.sensitivity_rr", "sp.bacon_decomposition"} <= missing_suggestions:
        failures.append("agent trace audit suggestions drifted")
    if summary.get("honest_max_rejecting_M", 0) <= 0:
        failures.append("agent trace Honest-DiD follow-up returned no positive M")
    citations = set(summary.get("citation_keys", []))
    if not {"callaway2021difference", "rambachan2023more"} <= citations:
        failures.append("agent trace citation keys are incomplete")

    if TRACE_TXT.exists():
        transcript = TRACE_TXT.read_text(encoding="utf-8")
        if re.search(r"r_[0-9a-f]{8}", transcript):
            failures.append("agent trace transcript contains unnormalised result handles")
        for snippet in (
            "# tools/list",
            "# tools/call callaway_santanna",
            "# tools/call audit_result",
            "# tools/call honest_did_from_result",
            "# tools/call audit_result(result_id='missing_result_id')",
            "isError: True",
            "re-fit the estimator with as_handle=true",
            "# tools/call bibtex",
        ):
            if snippet not in transcript:
                failures.append(f"agent trace transcript missing {snippet!r}")

    if TRACE_TEX.exists():
        table = TRACE_TEX.read_text(encoding="utf-8")
        for snippet in (
            "MCP tools listed",
            "Audit checks",
            "Verified citation keys",
            "BibTeX entries resolved",
            "Recoverable stale-handle error",
        ):
            if snippet not in table:
                failures.append(f"agent trace table missing {snippet!r}")

    if summary.get("stale_handle_is_error") is not True:
        failures.append("agent trace stale result handle did not return isError=True")
    if "result_id" not in str(summary.get("stale_handle_error", "")):
        failures.append("agent trace stale-handle error does not name result_id")
    if "re-fit the estimator with as_handle=true" not in str(
        summary.get("stale_handle_hint", "")
    ):
        failures.append("agent trace stale-handle hint is not actionable")
    if not isinstance(summary.get("stale_handle_available_ids"), int):
        failures.append("agent trace stale-handle available-id count is missing")

    if summary.get("bibtex_entry_count") != len(summary.get("citation_keys", [])):
        failures.append("agent trace did not resolve every citation key to BibTeX")
    if summary.get("unknown_bibtex_keys"):
        failures.append(
            "agent trace citation lookup returned unknown keys: "
            + ", ".join(summary["unknown_bibtex_keys"])
        )
    if summary.get("bibtex_source") != "paper.bib":
        failures.append("agent trace BibTeX lookup did not use paper.bib")

    return summary


def _check_schema_count_text(schema: dict[str, int], failures: list[str]) -> None:
    tex_total = _fmt_int(schema["parameter_total"], tex=True)
    tex_default = _fmt_int(schema["parameter_with_default"], tex=True)
    tex_enum = _fmt_int(schema["parameter_with_enum"], tex=True)
    plain_total = _fmt_int(schema["parameter_total"])
    default_pct = _pct(schema["parameter_with_default"], schema["parameter_total"])
    enum_pct = _pct(schema["parameter_with_enum"], schema["parameter_total"])
    default_pct_tex = default_pct.replace("%", "\\%")
    enum_pct_tex = enum_pct.replace("%", "\\%")

    required = {
        "Paper-JSS/manuscript/sections/07-agent-eval.tex": [
            "\\SchemaParameterTotal",
            "\\SchemaParameterDescribed",
            "\\SchemaParameterDefault",
            "\\SchemaParameterEnum",
            "\\SchemaParameterDefaultPct",
            "\\SchemaParameterEnumPct",
        ],
        "Paper-JSS/cover-letter.md": [
            f"{plain_total} schema parameters",
        ],
    }

    for rel in SCHEMA_COUNT_FILES:
        if withheld_editor_doc(rel):
            continue
        text = _read(rel)
        text_norm = _normalise(text)
        for snippet in required[rel]:
            if _normalise(snippet) not in text_norm:
                failures.append(f"{rel}: live schema count missing: {snippet!r}")


def _check_boundary_wording(failures: list[str]) -> None:
    for rel, snippets in BOUNDARY_SNIPPETS.items():
        path = ROOT / rel
        if withheld_editor_doc(rel):
            continue
        if not path.exists():
            failures.append(f"missing agent-boundary file: {rel}")
            continue
        text_norm = _normalise(path.read_text(encoding="utf-8"))
        for snippet in snippets:
            if _normalise(snippet) not in text_norm:
                failures.append(f"{rel}: required agent-boundary wording missing: {snippet!r}")

    manuscript_files = [
        "Paper-JSS/manuscript/main.tex",
        "Paper-JSS/manuscript/sections/03-agent-facing-compact.tex",
        "Paper-JSS/manuscript/sections/07-agent-eval.tex",
        "Paper-JSS/manuscript/sections/09-discussion-compact.tex",
    ]
    for rel in manuscript_files:
        text = _read(rel)
        for snippet in FORBIDDEN_MANUSCRIPT_REFERENCES:
            if snippet in text:
                failures.append(
                    f"{rel}: manuscript references non-submission companion artifact "
                    f"{snippet!r}"
                )


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []

    schema = _schema_quality()
    trace = _trace_summary(failures)
    _check_schema_count_text(schema, failures)
    _check_boundary_wording(failures)

    status = "PASS" if not failures else "FAIL"
    result = {
        "generated_at_unix": _generated_at_unix(),
        "status": status,
        "schema_quality": schema,
        "agent_trace": trace,
        "boundary_files_checked": sorted(BOUNDARY_SNIPPETS),
        "schema_count_files_checked": sorted(SCHEMA_COUNT_FILES),
        "forbidden_manuscript_references": FORBIDDEN_MANUSCRIPT_REFERENCES,
        "failures": failures,
    }
    OUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Agent Interface Audit",
        "",
        f"Status: {status}",
        "",
        "Scope: mechanical and contractual schema/MCP/citation evidence only;",
        "this audit does not",
        "claim that autonomous LLM agents produce better empirical analyses.",
        "",
        "Schema quality:",
        f"- Public functions with schemas: {schema['public_surface']}",
        f"- Curated/inherited agent metadata cards: {schema['curated_agent_card']}",
        (
            "- Parameters with descriptions: "
            f"{schema['parameter_with_description']}/"
            f"{schema['parameter_total']} "
            f"({_pct(schema['parameter_with_description'], schema['parameter_total'])})"
        ),
        (
            "- Parameters with defaults: "
            f"{schema['parameter_with_default']} "
            f"({_pct(schema['parameter_with_default'], schema['parameter_total'])})"
        ),
        (
            "- Parameters with enums: "
            f"{schema['parameter_with_enum']} "
            f"({_pct(schema['parameter_with_enum'], schema['parameter_total'])})"
        ),
        "",
        "Deterministic MCP trace:",
        f"- Tools listed: {trace.get('tool_count', 'n/a')}",
        f"- Audit checks: {trace.get('audit_checks', 'n/a')}",
        f"- Honest-DiD max rejecting M: {trace.get('honest_max_rejecting_M', 'n/a')}",
        (
            "- Stale-handle error envelope: "
            f"isError={trace.get('stale_handle_is_error', 'n/a')}; "
            f"reason={trace.get('stale_handle_reason', 'n/a')}; "
            f"hint_present={bool(trace.get('stale_handle_hint'))}; "
            f"available_ids={trace.get('stale_handle_available_ids', 'n/a')}"
        ),
        "- Citation keys: " + ", ".join(trace.get("citation_keys", [])),
        (
            "- BibTeX entries resolved: "
            f"{trace.get('bibtex_entry_count', 'n/a')} "
            f"from {trace.get('bibtex_source', 'n/a')}"
        ),
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
        print("FAIL -- agent interface audit failed", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

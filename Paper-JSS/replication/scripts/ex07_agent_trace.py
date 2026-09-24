r"""
StatsPAI JSS replication script -- Section 7 / Appendix agent trace.

Runs a deterministic MCP JSON-RPC trace against the live StatsPAI
agent server, normalises ephemeral result handles, and writes:

    replication/results/ex07_agent_trace.json
    replication/results/ex07_agent_trace.txt
    replication/tables/ex07_agent_trace.tex

The production CausalAgentBench RCT is intentionally not run here;
this script is the executable smoke trace that verifies the agent
surface can chain schema discovery, estimation, audit, sensitivity,
recoverable error routing, and citation metadata without an LLM or API
budget.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

import statspai as sp
from statspai.agent.mcp_server import handle_request


HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE.parent / "results"
TABLES_DIR = HERE.parent / "tables"


def _rpc(method: str, params: dict[str, Any] | None = None, request_id: int = 1) -> dict:
    request = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params or {},
    }
    response = handle_request(json.dumps(request))
    if response is None:
        raise RuntimeError(f"{method} returned no response")
    return json.loads(response)


def _content_payload(response: dict) -> dict:
    text = response["result"]["content"][0]["text"]
    return json.loads(text)


def _normalise_ids(text: str) -> str:
    ids: dict[str, str] = {}

    def repl(match: re.Match[str]) -> str:
        raw = match.group(0)
        if raw not in ids:
            ids[raw] = f"r_{len(ids) + 1:02d}"
        return ids[raw]

    return re.sub(r"r_[0-9a-f]{8}", repl, text)


def _tex_escape(value: str) -> str:
    return (
        value.replace("\\", "\\textbackslash{}")
        .replace("&", "\\&")
        .replace("%", "\\%")
        .replace("_", "\\_")
        .replace("#", "\\#")
    )


def run() -> dict:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        data_path = Path(tmp) / "mpdta.csv"
        sp.datasets.mpdta().to_csv(data_path, index=False)

        tools = _rpc("tools/list", {}, 1)
        tool_names = [tool["name"] for tool in tools["result"]["tools"]]

        callaway_tool = next(
            tool for tool in tools["result"]["tools"]
            if tool["name"] == "callaway_santanna"
        )
        schema = callaway_tool["inputSchema"]

        fit_response = _rpc(
            "tools/call",
            {
                "name": "callaway_santanna",
                "arguments": {
                    "data_path": str(data_path),
                    "y": "lemp",
                    "g": "first_treat",
                    "t": "year",
                    "i": "countyreal",
                    "estimator": "reg",
                    "control_group": "nevertreated",
                    "as_handle": True,
                    "detail": "minimal",
                },
            },
            3,
        )
        fit = _content_payload(fit_response)
        result_id = fit["result_id"]

        audit_response = _rpc(
            "tools/call",
            {
                "name": "audit_result",
                "arguments": {"result_id": result_id},
            },
            4,
        )
        audit = _content_payload(audit_response)

        honest_response = _rpc(
            "tools/call",
            {
                "name": "honest_did_from_result",
                "arguments": {
                    "result_id": result_id,
                    "method": "SD",
                    "e": 0,
                    "as_handle": True,
                    "detail": "minimal",
                },
            },
            5,
        )
        honest = _content_payload(honest_response)

    missing = [
        check.get("suggest_function")
        for check in audit.get("checks", [])
        if check.get("status") == "missing" and check.get("suggest_function")
    ]
    missing = [str(x) for x in missing]
    cited_keys = sorted(
        set(fit.get("citations", {}).get("keys", []))
        | set(honest.get("citations", {}).get("keys", []))
    )
    stale_handle_response = _rpc(
        "tools/call",
        {
            "name": "audit_result",
            "arguments": {"result_id": "missing_result_id"},
        },
        6,
    )
    stale_handle_payload = stale_handle_response["result"]["structuredContent"]

    bibtex_response = _rpc(
        "tools/call",
        {
            "name": "bibtex",
            "arguments": {"keys": cited_keys},
        },
        7,
    )
    bibtex = _content_payload(bibtex_response)

    summary = {
        "tool_count": len(tool_names),
        "required_tools_present": {
            "callaway_schema_in_manifest": bool(schema),
            "callaway_santanna": "callaway_santanna" in tool_names,
            "audit_result": "audit_result" in tool_names,
            "honest_did_from_result": "honest_did_from_result" in tool_names,
            "bibtex": "bibtex" in tool_names,
        },
        "schema_required": schema.get("required", []),
        "schema_control_group_enum": schema
        .get("properties", {})
        .get("control_group", {})
        .get("enum", []),
        "estimate": float(fit["estimate"]),
        "se": float(fit["se"]),
        "ci": [float(fit["ci"][0]), float(fit["ci"][1])],
        "audit_checks": len(audit.get("checks", [])),
        "missing_suggested_functions": missing,
        "honest_max_rejecting_M": float(honest.get("max_rejecting_M", 0.0)),
        "citation_keys": cited_keys,
        "bibtex_entry_count": sum(
            1 for entry in bibtex.get("bibtex", {}).values() if entry
        ),
        "unknown_bibtex_keys": list(bibtex.get("unknown_keys", [])),
        "bibtex_source": bibtex.get("source"),
        "stale_handle_is_error": bool(
            stale_handle_response["result"].get("isError")
        ),
        "stale_handle_error": stale_handle_payload.get("error", ""),
        "stale_handle_reason": stale_handle_payload.get("reason", ""),
        "stale_handle_hint": stale_handle_payload.get("hint", ""),
        "stale_handle_available_ids": len(
            stale_handle_payload.get("available_result_ids", [])
        ),
    }

    transcript = f"""# Deterministic MCP trace generated by ex07_agent_trace.py
# User prompt
What is the staggered DiD effect of treatment on lemp in mpdta.csv?
Run the appropriate estimator and recommend any required diagnostics.

# tools/list
tools returned: {summary['tool_count']}
required tools present: {summary['required_tools_present']}

# tools/list manifest entry for callaway_santanna
required arguments: {summary['schema_required']}
control_group enum: {summary['schema_control_group_enum']}

# tools/call callaway_santanna(..., as_handle=true)
result_id: r_01
estimate: {summary['estimate']:.6f}
se: {summary['se']:.6f}
ci95: [{summary['ci'][0]:.6f}, {summary['ci'][1]:.6f}]
citation keys: {fit.get('citations', {}).get('keys', [])}

# tools/call audit_result(result_id='r_01')
checks returned: {summary['audit_checks']}
missing suggested functions: {summary['missing_suggested_functions']}

# tools/call honest_did_from_result(result_id='r_01', method='SD', e=0)
result_id: r_02
restriction: {honest.get('restriction')}
max rejecting M: {summary['honest_max_rejecting_M']:.6f}
citation keys: {honest.get('citations', {}).get('keys', [])}

# tools/call audit_result(result_id='missing_result_id')
isError: {summary['stale_handle_is_error']}
error: {summary['stale_handle_error']}
reason: {summary['stale_handle_reason']}
hint: {summary['stale_handle_hint']}
available result ids: {summary['stale_handle_available_ids']}

# tools/call bibtex(keys={summary['citation_keys']})
resolved entries: {summary['bibtex_entry_count']}
unknown keys: {summary['unknown_bibtex_keys']}
source: {summary['bibtex_source']}

# assistant final answer
The Callaway-Sant'Anna simple ATT on lemp is {summary['estimate']:.4f}
(SE {summary['se']:.4f}, 95% CI [{summary['ci'][0]:.4f}, {summary['ci'][1]:.4f}]).
The audit recommends follow-up diagnostics {summary['missing_suggested_functions']}.
The handle-based Honest-DiD follow-up remains significant for smoothness
violations up to M={summary['honest_max_rejecting_M']:.4f}; citations are
verified by resolving {summary['citation_keys']} against {summary['bibtex_source']}.
"""

    out = {
        "summary": summary,
        "transcript": transcript,
        "raw_shapes": {
            "tools_list_keys": list(tools["result"].keys()),
            "fit_payload_keys": list(fit.keys()),
            "audit_payload_keys": list(audit.keys()),
            "honest_payload_keys": list(honest.keys()),
        },
    }
    return out


def write_outputs(results: dict) -> None:
    transcript = _normalise_ids(results["transcript"])
    results = dict(results)
    results["transcript"] = transcript
    (RESULTS_DIR / "ex07_agent_trace.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    (RESULTS_DIR / "ex07_agent_trace.txt").write_text(
        transcript, encoding="utf-8"
    )

    summary = results["summary"]
    rows = [
        ("MCP tools listed", str(summary["tool_count"])),
        (
            "Estimate",
            f"{summary['estimate']:.4f} (SE {summary['se']:.4f})",
        ),
        ("Audit checks", str(summary["audit_checks"])),
        ("Honest-DiD max rejecting M", f"{summary['honest_max_rejecting_M']:.4f}"),
        (
            "Recoverable stale-handle error",
            f"isError={summary['stale_handle_is_error']}; hint present",
        ),
        ("Verified citation keys", ", ".join(summary["citation_keys"])),
        ("BibTeX entries resolved", str(summary["bibtex_entry_count"])),
    ]
    body = "\n".join(
        f"    {_tex_escape(label)} & {_tex_escape(value)} \\\\"
        for label, value in rows
    )
    tex = (
        "\\begin{tabular}{ll}\n"
        "    \\toprule\n"
        "    Trace item & Value \\\\\n"
        "    \\midrule\n"
        f"{body}\n"
        "    \\bottomrule\n"
        "\\end{tabular}\n"
    )
    (TABLES_DIR / "ex07_agent_trace.tex").write_text(tex, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true", help="print JSON")
    args = parser.parse_args()

    results = run()
    write_outputs(results)

    summary = results["summary"]
    failed_tools = [
        name for name, present in summary["required_tools_present"].items()
        if not present
    ]
    if failed_tools:
        print("FAIL: missing tools " + ", ".join(failed_tools), file=sys.stderr)
        return 1
    if summary["honest_max_rejecting_M"] <= 0:
        print("FAIL: honest_did_from_result returned no positive M", file=sys.stderr)
        return 1
    if not summary["stale_handle_is_error"]:
        print("FAIL: stale handle did not return an MCP error result", file=sys.stderr)
        return 1
    if "result_id" not in summary["stale_handle_error"]:
        print("FAIL: stale handle error does not name result_id", file=sys.stderr)
        return 1
    if "re-fit" not in summary["stale_handle_hint"]:
        print("FAIL: stale handle hint does not tell the agent how to recover", file=sys.stderr)
        return 1
    if not {"callaway2021difference", "rambachan2023more"} <= set(
        summary["citation_keys"]
    ):
        print("FAIL: citation keys missing from trace", file=sys.stderr)
        return 1

    if args.pretty:
        print(json.dumps(results, indent=2))
    else:
        print("OK -- wrote", RESULTS_DIR / "ex07_agent_trace.json")
        print("OK -- wrote", RESULTS_DIR / "ex07_agent_trace.txt")
        print("OK -- wrote", TABLES_DIR / "ex07_agent_trace.tex")
    return 0


if __name__ == "__main__":
    sys.exit(main())

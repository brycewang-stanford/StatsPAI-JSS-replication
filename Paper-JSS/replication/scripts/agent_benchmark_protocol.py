"""Write the deferred behavioural-agent benchmark protocol.

The JSS manuscript claims a mechanical and contractual agent-facing
interface, not behavioural LLM performance.  This protocol makes the
deferred benchmark concrete enough for reviewers to audit the boundary
without treating it as a completed JSS result.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
PAPER_DIR = HERE.parents[1]
RESULTS_DIR = PAPER_DIR / "replication" / "results"
OUT_JSON = RESULTS_DIR / "agent_benchmark_protocol.json"
OUT_MD = RESULTS_DIR / "agent_benchmark_protocol.md"
SOURCE_DATE_EPOCH = os.environ.get("SOURCE_DATE_EPOCH")


def _generated_at_unix() -> int:
    if SOURCE_DATE_EPOCH is not None:
        return int(SOURCE_DATE_EPOCH)
    return int(time.time())


def _protocol() -> dict[str, Any]:
    arms = [
        {
            "id": "statspai_mcp",
            "description": (
                "Tool-using agent with the StatsPAI MCP registry, result "
                "handles, typed errors, and citation resolver enabled."
            ),
        },
        {
            "id": "python_notebook_baseline",
            "description": (
                "Matched agent budget using Python notebooks and general "
                "statistics packages without the StatsPAI registry contract."
            ),
        },
        {
            "id": "reference_package_baseline",
            "description": (
                "Matched agent budget using reference R/Python package "
                "documentation through a notebook or MCP shim."
            ),
        },
    ]
    task_families = [
        "estimator discovery and valid estimator selection",
        "causal workflow execution with a fixed dataset and rubric",
        "result-handle audit and sensitivity-analysis follow-through",
        "citation resolution without hallucinated references",
        "recoverable error handling after stale or invalid handles",
    ]
    scoring_dimensions = [
        "correct estimand and estimator choice",
        "successful executable analysis without hidden manual repair",
        "numerical agreement with a locked reference answer",
        "assumption and limitation disclosure quality",
        "citation fidelity and bibliography completeness",
        "recoverable-error handling and next-step quality",
    ]
    validity_controls = [
        "freeze model releases, prompts, tool budgets, and random seeds",
        "use held-out tasks not seen during schema or prompt development",
        "match wall-clock and tool-call budgets across arms",
        "score with blinded rubrics before reading tool traces",
        "separate benchmark construction from manuscript claim wording",
        "report failures and abstentions rather than only successful traces",
    ]
    minimum_report = [
        "pre-registered task set and scoring rubric",
        "arm-level success rates with uncertainty intervals",
        "per-task failure taxonomy and representative transcripts",
        "runtime/tool-call budgets and model versions",
        "all prompts, schemas, datasets, and scorer code",
    ]
    boundary = {
        "jss_claimed_behavioral_result": False,
        "jss_upload_blocking": False,
        "current_jss_evidence": (
            "mechanical and contractual schema/MCP/citation evidence only"
        ),
        "deferred_result_destination": "separate behavioural benchmark package",
    }
    return {
        "generated_at_unix": _generated_at_unix(),
        "status": "PASS",
        "boundary": boundary,
        "arms": arms,
        "task_families": task_families,
        "scoring_dimensions": scoring_dimensions,
        "validity_controls": validity_controls,
        "minimum_report": minimum_report,
        "summary": {
            "arm_count": len(arms),
            "task_family_count": len(task_families),
            "scoring_dimension_count": len(scoring_dimensions),
            "validity_control_count": len(validity_controls),
            "minimum_report_item_count": len(minimum_report),
            "jss_upload_blocking": boundary["jss_upload_blocking"],
            "jss_claimed_behavioral_result": boundary[
                "jss_claimed_behavioral_result"
            ],
        },
        "primary_evidence": [
            "manuscript/sections/07-agent-eval.tex",
            "replication/results/agent_interface_audit.md",
            "replication/results/ex07_agent_trace.txt",
            "replication/results/experiment_triage.md",
        ],
        "failures": [],
    }


def _write_markdown(payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    boundary = payload["boundary"]
    lines = [
        "# Deferred Behavioural Agent Benchmark Protocol",
        "",
        f"Status: {payload['status']}",
        "",
        "This protocol is included to make the deferred behavioural benchmark "
        "concrete. It is not a completed JSS result and it is not an upload "
        "blocker for the source-snapshot submission.",
        "It specifies matched arms, task families, scoring dimensions, "
        "leakage controls, and minimum report items for a separate study.",
        "",
        "## Boundary",
        "",
        f"- JSS claimed behavioural result: `{boundary['jss_claimed_behavioral_result']}`",
        f"- JSS upload blocking: `{boundary['jss_upload_blocking']}`",
        f"- Current JSS evidence: {boundary['current_jss_evidence']}",
        f"- Deferred result destination: {boundary['deferred_result_destination']}",
        "",
        "## Benchmark Arms",
        "",
        "| Arm | Description |",
        "|---|---|",
    ]
    lines.extend(
        f"| `{arm['id']}` | {arm['description']} |"
        for arm in payload["arms"]
    )
    lines.extend(["", "## Task Families", ""])
    lines.extend(f"- {item}" for item in payload["task_families"])
    lines.extend(["", "## Scoring Dimensions", ""])
    lines.extend(f"- {item}" for item in payload["scoring_dimensions"])
    lines.extend(["", "## Validity Controls", ""])
    lines.extend(f"- {item}" for item in payload["validity_controls"])
    lines.extend(["", "## Minimum Report", ""])
    lines.extend(f"- {item}" for item in payload["minimum_report"])
    lines.extend(
        [
            "",
            "## Metrics",
            "",
            f"- `arm_count`: `{summary['arm_count']}`",
            f"- `task_family_count`: `{summary['task_family_count']}`",
            f"- `scoring_dimension_count`: `{summary['scoring_dimension_count']}`",
            f"- `validity_control_count`: `{summary['validity_control_count']}`",
            f"- `minimum_report_item_count`: `{summary['minimum_report_item_count']}`",
            "",
            f"Machine-readable detail: `{OUT_JSON.relative_to(PAPER_DIR)}`",
        ]
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = _protocol()
    failures: list[str] = []
    if payload["summary"]["arm_count"] < 3:
        failures.append("benchmark protocol must include at least three arms")
    if payload["summary"]["task_family_count"] < 5:
        failures.append("benchmark protocol must include at least five task families")
    if payload["summary"]["scoring_dimension_count"] < 6:
        failures.append("benchmark protocol must include at least six scoring dimensions")
    if payload["summary"]["validity_control_count"] < 6:
        failures.append("benchmark protocol must include at least six validity controls")
    if payload["summary"]["jss_upload_blocking"] is not False:
        failures.append("deferred behavioural benchmark must not block JSS upload")
    if payload["summary"]["jss_claimed_behavioral_result"] is not False:
        failures.append("JSS manuscript must not claim behavioural benchmark results")
    payload["failures"] = failures
    payload["status"] = "PASS" if not failures else "FAIL"
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(payload)
    print(f"OK -- wrote {OUT_JSON}")
    print(f"OK -- wrote {OUT_MD}")
    if failures:
        print("FAIL -- behavioural agent benchmark protocol is incomplete")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

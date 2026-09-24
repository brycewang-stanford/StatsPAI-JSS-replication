# Deferred Behavioural Agent Benchmark Protocol

Status: PASS

This protocol is included to make the deferred behavioural benchmark concrete. It is not a completed JSS result and it is not an upload blocker for the source-snapshot submission.
It specifies matched arms, task families, scoring dimensions, leakage controls, and minimum report items for a separate study.

## Boundary

- JSS claimed behavioural result: `False`
- JSS upload blocking: `False`
- Current JSS evidence: mechanical and contractual schema/MCP/citation evidence only
- Deferred result destination: separate behavioural benchmark package

## Benchmark Arms

| Arm | Description |
|---|---|
| `statspai_mcp` | Tool-using agent with the StatsPAI MCP registry, result handles, typed errors, and citation resolver enabled. |
| `python_notebook_baseline` | Matched agent budget using Python notebooks and general statistics packages without the StatsPAI registry contract. |
| `reference_package_baseline` | Matched agent budget using reference R/Python package documentation through a notebook or MCP shim. |

## Task Families

- estimator discovery and valid estimator selection
- causal workflow execution with a fixed dataset and rubric
- result-handle audit and sensitivity-analysis follow-through
- citation resolution without hallucinated references
- recoverable error handling after stale or invalid handles

## Scoring Dimensions

- correct estimand and estimator choice
- successful executable analysis without hidden manual repair
- numerical agreement with a locked reference answer
- assumption and limitation disclosure quality
- citation fidelity and bibliography completeness
- recoverable-error handling and next-step quality

## Validity Controls

- freeze model releases, prompts, tool budgets, and random seeds
- use held-out tasks not seen during schema or prompt development
- match wall-clock and tool-call budgets across arms
- score with blinded rubrics before reading tool traces
- separate benchmark construction from manuscript claim wording
- report failures and abstentions rather than only successful traces

## Minimum Report

- pre-registered task set and scoring rubric
- arm-level success rates with uncertainty intervals
- per-task failure taxonomy and representative transcripts
- runtime/tool-call budgets and model versions
- all prompts, schemas, datasets, and scorer code

## Metrics

- `arm_count`: `3`
- `task_family_count`: `5`
- `scoring_dimension_count`: `6`
- `validity_control_count`: `6`
- `minimum_report_item_count`: `5`

Machine-readable detail: `replication/results/agent_benchmark_protocol.json`

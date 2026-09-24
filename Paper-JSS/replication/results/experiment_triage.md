# JSS Experiment And Evidence Triage

Status: PASS
Triage items: 8
Expected item identity: confirmed
JSS upload-blocking gaps: 0

| Item | Status | Classification | Reviewer question | Boundary answer | Evidence |
|---|---:|---|---|---|---|
| `cross_language_parity` | PASS | `implemented_with_boundary` | Have the headline cross-language checks been run? | The JSS packet includes the 89-module R parity harness, 85 Stata bridges, and a classified T4 row rather than treating all comparisons as equality claims. | `replication/results/methodological_gap_ledger.md`<br>`replication/results/stata_bridge_audit.md`<br>`manuscript/tables/track_a_cross_language_snapshot.tex` |
| `monte_carlo_validation` | PASS | `implemented` | Are the simulation rows implemented as validation evidence? | The committed B=1000 Track-B artifacts cover all twelve nominal rows (with bias, Monte Carlo SD, SE calibration and interval length) plus three documented robustness failure-mode rows. | `tests/coverage_monte_carlo/results_b1000/coverage_b1000.json`<br>`tests/coverage_monte_carlo/results_b1000/coverage_robustness_b1000.json`<br>`manuscript/sections/05-parity-compact.tex` |
| `performance_benchmark` | PASS | `implemented` | Is there measured runtime evidence rather than anecdote? | Track C is a measured four-estimator benchmark with generated tables and a log-log figure; it is not framed as a universal speed claim. | `tests/perf/results/perf_table.md`<br>`manuscript/tables/track_c_perf.tex`<br>`manuscript/figures/track_c_loglog.pdf` |
| `tier1_reproduction` | PASS | `implemented` | Can a reviewer reproduce headline numbers without R or Stata? | Tier 1 rebuilds the Section 4-7 headline numbers with Python-only scripts and records a no-R/no-Stata transcript. | `replication/reproduce.py`<br>`replication/results/reproduce_tier1_output.txt`<br>`replication/results/reproduction_environment_audit.md` |
| `live_stata_rerun` | PASS | `external_runtime_documented` | Is a live Stata rerun required for JSS upload? | Live Stata re-execution is optional because it requires a separate license and an explicit `STATA_EXE` runtime; a missing-Stata skip is documented as not being live-rerun evidence. The upload includes frozen JSON, do-files, provenance, and a bridge audit for all 85 modules. | `replication/results/stata_bridge_audit.md`<br>`tests/stata_parity/README.md`<br>`tests/stata_parity/verify_reproduce_stata.py`<br>`replication/results/reproduction_environment_audit.md` |
| `behavioural_agent_benchmark` | PASS | `deferred_to_separate_benchmark` | Does the JSS paper need a behavioural LLM benchmark? | No behavioural agent-performance result is claimed here; the JSS evidence is a mechanical and contractual interface audit whose schemas, typed errors, handles, citations, and deterministic trace are inspectable in the same validation ledger as human calls, with a packaged deferred benchmark protocol specifying matched baselines, task families, scoring dimensions, and leakage controls for the separate behavioural study. | `replication/results/agent_interface_audit.md`<br>`replication/results/agent_benchmark_protocol.md`<br>`manuscript/sections/07-agent-eval.tex`<br>`replication/results/ex07_agent_trace.txt` |
| `full_registry_numeric_validation` | PASS | `not_a_jss_claim` | Does every registered public function need numerical validation? | No. The JSS claim is tiered: certified/validated symbols carry evidence notes, while API-stable breadth is disclosed as interface stability rather than numerical validation. | `replication/results/validation_evidence_audit.md`<br>`replication/results/claim_lint.md`<br>`docs/guides/stability.md` |
| `final_tagged_release` | PASS | `post_upload_release_work` | Does JSS upload require the final clean tagged release cut? | No. The JSS archive is an audited source snapshot; the clean worktree, changelog, and tag alignment remain listed as nonblocking final-release work. | `replication/results/release_boundary_audit.md`<br>`replication/results/source_snapshot_manifest.md`<br>`replication/results/submission_risk_ledger.md` |

## Metrics

### cross_language_parity
- `r_modules`: `89`
- `stata_modules`: `85`
- `r_joined_stata_modules`: `85`
- `methodological_gap_count`: `1`
- `uncategorized_gap_count`: `0`

### monte_carlo_validation
- `b1000_rows`: `12`
- `robustness_rows`: `3`
- `coverage_min`: `0.883`
- `coverage_max`: `0.968`

### performance_benchmark
- `performance_modules`: `5`

### tier1_reproduction
- `tier1_steps`: `24/24`
- `tier1_no_r_stata`: `True`
- `tier1_live_external_call_count`: `0`

### live_stata_rerun
- `stata_modules`: `85`
- `license_boundary`: `Frozen JSON/do-file/provenance audit only; re-running Stata requires a separate Stata license.`
- `live_rerun_command_documented`: `True`
- `missing_stata_skip_documented`: `True`
- `verifier_missing_runtime_returns_skip`: `True`

### behavioural_agent_benchmark
- `schema_files`: `1220`
- `schema_parameters`: `9436`
- `trace_tools`: `559`
- `trace_bibtex_entry_count`: `2`
- `protocol_arms`: `3`
- `protocol_task_families`: `5`
- `protocol_scoring_dimensions`: `6`
- `protocol_validity_controls`: `6`
- `protocol_jss_upload_blocking`: `False`
- `protocol_claimed_behavioural_result`: `False`

### full_registry_numeric_validation
- `certified_validated_symbols`: `556`
- `missing_validation_notes`: `0`
- `api_stable_symbols`: `661`
- `unbacked_auto_stable`: `568`

### final_tagged_release
- `release_boundary_status`: `PASS`
- `ready_for_final_publication`: `False`
- `release_blocker_count`: `109`
- `version_consistent`: `True`

Failures: none

Machine-readable detail: `replication/results/experiment_triage.json`

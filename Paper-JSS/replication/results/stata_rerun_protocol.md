# Stata Tier-3 Rerun Protocol

Status: PASS

Optional licensed Stata Tier-3 rerun protocol; the JSS upload evidence remains the frozen JSON/do/provenance bundle.
This generated file does not require Stata, does not mark absence of Stata as a JSS upload failure, and does not claim that this machine has completed a fresh licensed rerun.

## Boundary

- `requires_stata_license`: `True`
- `jss_upload_blocking`: `False`
- `absence_of_stata_is_optional_skip`: `True`
- `claimed_current_machine_live_rerun`: `False`
- `frozen_json_do_provenance_is_upload_evidence`: `True`
- `no_section_4_7_headline_depends_on_live_stata`: `True`
- `expected_stata_modules`: `85`

## Commands

| ID | CWD | Command | Purpose |
|---|---|---|---|
| `paper_tier3_driver` | `Paper-JSS` | `STATA_EXE=/path/to/stata-mp ../.venv/bin/python replication/reproduce.py --tier 3` | Runs Tier 1, Tier 2 if R is available, and the licensed Stata verifier through the paper reproduction driver. |
| `direct_stata_verifier` | `repository root` | `STATA_EXE=/path/to/stata-mp .venv/bin/python tests/stata_parity/verify_reproduce_stata.py` | Runs only the Stata parity verifier and rewrites the Stata reproducibility report from staged fresh outputs. |
| `refresh_stata_environment_note` | `repository root` | `stata-mp -q -b do tests/stata_parity/_capture_stata_env.do && .venv/bin/python tests/stata_parity/_gen_stata_env.py` | Optional: refreshes the Stata engine/ado inventory when a reviewer reruns under a different licensed Stata installation. |
| `audit_frozen_bridge` | `Paper-JSS` | `make stata-bridge-audit PYTHON=../.venv/bin/python` | Checks the frozen JSON/do/provenance bundle without requiring Stata; this remains the JSS upload evidence. |

## Checklist

| Item | Action | Record |
|---|---|---|
| `confirm_license` | Confirm that a licensed Stata executable is available and record the executable path used as STATA_EXE. | STATA_EXE path and Stata edition/version |
| `inspect_environment` | Read tests/stata_parity/STATA_ENVIRONMENT.md and decide whether to refresh the local ado inventory before rerunning. | whether environment note was refreshed |
| `run_tier3_or_direct_verifier` | Run either the Paper-JSS Tier-3 driver or the direct tests/stata_parity/verify_reproduce_stata.py command. | command, exit code, and elapsed time |
| `compare_report_counts` | Confirm that REPRODUCIBILITY_REPORT_STATA.md lists 85/85 reproduced modules and zero non-reproduced rows. | reproduced/non-reproduced counts |
| `inspect_drift_rows` | If any row drifts, inspect the module, Stata version, ado version, tolerance override, and generated log before changing golden JSON. | drift rationale or 'none' |
| `preserve_golden_files` | Do not overwrite committed *_Stata.json golden files unless the drift is explained and the manuscript/audits are refreshed in the same reviewed change. | golden files unchanged or justified refresh |
| `interpret_missing_stata` | If Stata is absent, record an optional-runtime skip rather than a JSS upload failure; no Section 4-7 headline number depends on live Stata. | skip reason if applicable |
| `rerun_jss_gates` | After any accepted Stata rerun update, rerun the Stata bridge audit and the JSS submission package verifier. | audit/verifier command results |

## Metrics

- `stata_bridge_status`: `PASS`
- `reproduction_environment_status`: `PASS`
- `stata_modules`: `85`
- `r_joined_stata_modules`: `85`
- `repro_report_modules`: `85`
- `reproduced_report_rows`: `85`
- `non_reproduced_report_rows`: `0`
- `checklist_item_count`: `8`
- `command_count`: `4`
- `requires_stata_license`: `True`
- `jss_upload_blocking`: `False`
- `absence_of_stata_is_optional_skip`: `True`
- `claimed_current_machine_live_rerun`: `False`
- `frozen_json_do_provenance_is_upload_evidence`: `True`
- `no_section_4_7_headline_depends_on_live_stata`: `True`
- `expected_stata_modules`: `85`

Failures: none

Machine-readable detail: `replication/results/stata_rerun_protocol.json`

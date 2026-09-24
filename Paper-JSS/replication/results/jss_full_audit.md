# JSS Full Validation Audit

Status: PASS
Original-data parity rows: 35
Track A modules: 89 (machine=80, iterative=7, moderate=1, methodological/T4=1)
Track B materialized nominal rows: 12 (coverage range 0.883-0.968)
Track C modules: 4
Stability audit: 556 registry certified/validated symbols; 0 hand-written stable symbols still unbacked; 568 stable auto-registered symbols still unbacked
API-stable denominator: 292 class-like / 276 function-like auto-unbacked symbols; top categories=agent:16, bartik:3, bayes:8, bridge:1, causal:214, censoring:1
Evidence paths: 490 unique registry evidence paths; missing=0
Submission package: not built
Data provenance audit: PASS (scoped_files=842; csv=344; public_datasets=9; original_extracts=7; r_stata_csv=91; forbidden_raw=0; private_path_hits=0; unknown=0)
Source snapshot: version=1.30.1, package_commit=d8868b6f, paper_commit=e9f3cce, clean=False, unreleased_changes=True, version_consistent=True, final_publication_gate_ready=False, gate_blocker_paths=109
Claim linter: PASS (37 files checked; historical_drift_files=10)
Schema bundle check: PASS
Validation evidence audit: PASS (556 certified/validated, missing_notes=0, certified_without_grade=0, validated_without_grade=0, supplemental_only=0)
Methodological/T4 ledger: PASS (1/1 classified, uncategorized=0, metadata_guard_failures=0, non_circular_native_guards=1, non_circular_guard_failures=0, reference_disagreement_guards=1, reference_disagreement_guard_failures=0)
Stata bridge audit: PASS (85 frozen modules; 85 R-joined; Py-Stata-only=none; repro_report=85)
Stata rerun protocol: PASS (modules=85; r_joined=85; repro_report=85; non_reproduced=0; checklist_items=8; requires_license=True; claimed_live_rerun=False; upload_blocking=False)
Agent interface audit: PASS (1220 schemas; 9436 params; trace_tools=559; trace_citations=callaway2021difference,rambachan2023more; trace_bibtex=2 from paper.bib; trace_stale_handle_error=True; trace_stale_handle_hint=True)
Agent benchmark protocol: PASS (arms=3; task_families=5; scoring_dimensions=6; validity_controls=6; jss_upload_blocking=False; claimed_behavioural_result=False)
Experiment triage: PASS (items=8; pass=8; failed=0; upload_blocking=0; classes={'deferred_to_separate_benchmark': 1, 'external_runtime_documented': 1, 'implemented': 3, 'implemented_with_boundary': 1, 'not_a_jss_claim': 1, 'post_upload_release_work': 1})
Release boundary audit: PASS (version=1.30.1, final_publication_gate_ready=False, gate_blocker_paths=109, checked_files=9)
JSS house-style audit: PASS (checks=7; active_sections=9; draft_markers=0; marketing_hits=0; overconfidence_hits=0; defensive_tone_hits=0; anchor_failures=0)
Bibliography metadata audit: PASS (active_cites=72; bib_entries=73; reserved=1; doi_entries=60; no_doi_manual=13/13; missing=0; duplicates=0; field_failures=0)
Submission risk ledger: not run
Reviewer evidence map: not run
Editor screening checklist: not run
Reproduction environment audit: PASS (docker=python:3.12-slim; requirements=23; requirements_version=True; make_targets=64; paper_readme_commands=26; manuscript_readme_commands=7; tier1_no_r_stata=True; tier1_live_external=0; renv=True; stata_env=True; seeded_rng=19; unseeded_rng=0)
PDF render audit: PASS (renderer=pdftoppm; pages=4/52; full_scan=52/52; full_failures=0; sampled=1,2,26,52; min_width=910; min_height=1287; min_ink_ratio=0.085421; max_dark_ratio=0.02163; failures=0)
PDF visual check protocol: PASS (pages=52; checklist_items=12; page_inventory=52/52; manual_visual_check_status=PENDING_MANUAL_REVIEW; claimed_manual_acceptance=False; jss_upload_blocking=False)
Manuscript artifact audit: PASS (sections=10; table_inputs=9; figures=3; artifacts=12; hash_mismatches=0; float_labels=21; narrative_refs=21; missing_refs=0; dangling_refs=0; worked_example_scripts=7; worked_example_mentions=7; worked_example_labels=7; compact_sections=10; compact_coverage=10; compact_missing_anchors=0)
JSS formal compliance audit: PASS (checks=23; passed=21; pending=2; archive=False; pages=52; official_sources_checked=2026-08-09)

## Step Results

- orig_parity_compare: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python tests/orig_parity/compare_orig.py`)
- r_stata_parity_compare: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python tests/r_parity/compare.py`)
- methodological_gap_ledger: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python Paper-JSS/replication/scripts/methodological_gap_ledger.py`)
- stata_bridge_audit: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python Paper-JSS/replication/scripts/stata_bridge_audit.py`)
- reproduction_environment_audit: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python Paper-JSS/replication/scripts/reproduction_environment_audit.py`)
- stata_rerun_protocol: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python Paper-JSS/replication/scripts/stata_rerun_protocol.py`)
- jss_reproduction_environment_contract: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python -m pytest -q tests/test_jss_reproduction_environment.py -o addopts=`)
- jss_optional_io_engine_import: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python -c import pyarrow`)
- jss_rddensity_io_contract: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python -m pytest -q tests/test_rddensity_io.py -o addopts=`)
- performance_compare: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python tests/perf/compare_perf.py`)
- manuscript_artifact_audit: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python Paper-JSS/replication/scripts/manuscript_artifact_audit.py`)
- data_provenance_audit: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python Paper-JSS/replication/scripts/data_provenance_audit.py`)
- schema_bundle_check: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python scripts/dump_schemas.py --check`)
- replacement_table_check: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python Paper-JSS/replication/scripts/build_replacement_table.py --check`)
- schema_quality: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python scripts/schema_quality.py`)
- agent_interface_audit: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python Paper-JSS/replication/scripts/agent_interface_audit.py`)
- agent_benchmark_protocol: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python Paper-JSS/replication/scripts/agent_benchmark_protocol.py`)
- jss_style_guard: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python Paper-JSS/replication/scripts/verify_jss_style.py`)
- listings_execute_audit: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python Paper-JSS/replication/scripts/listings_execute_audit.py`)
- claim_linter: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python Paper-JSS/replication/scripts/validate_claims.py`)
- validation_evidence_audit: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python Paper-JSS/replication/scripts/validation_evidence_audit.py`)
- stability_audit_json: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python scripts/stability_audit.py --json`)
- stability_audit_check: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python scripts/stability_audit.py --check`)
- jss_validation_api: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python -m pytest -q tests/test_jss_validation_api.py -o addopts=`)
- jss_release_manifest_contract: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python -m pytest -q tests/test_jss_release_manifest.py -k not test_submission_package_verifier_pins_page_and_claim_guards -o addopts=`)
- source_snapshot_manifest: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python Paper-JSS/replication/scripts/source_snapshot_manifest.py`)
- release_boundary_audit: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python Paper-JSS/replication/scripts/release_boundary_audit.py`)
- experiment_triage: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python Paper-JSS/replication/scripts/experiment_triage.py`)
- pdf_render_audit: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python Paper-JSS/replication/scripts/pdf_render_audit.py`)
- pdf_visual_check_protocol: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python Paper-JSS/replication/scripts/pdf_visual_check_protocol.py`)
- jss_formal_compliance_audit: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python Paper-JSS/replication/scripts/jss_formal_compliance_audit.py`)
- jss_house_style_audit: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python Paper-JSS/replication/scripts/jss_house_style_audit.py`)
- bibliography_metadata_audit: rc=0 in 0.0s (`<STATSPAI_ROOT>/.venv/bin/python Paper-JSS/replication/scripts/bibliography_metadata_audit.py`)

## Working-Tree Size Hotspots Checked by Packager

- .git: 0.0 MiB
- manuscript: 8.93 MiB
- references: 22.3 MiB
- replication: 2.56 MiB

Machine-readable detail: `replication/results/jss_full_audit.json`

# StatsPAI JSS Source Snapshot Manifest

Package metadata version: `1.30.1`
Source `__version__`: `1.30.1`
Committed schema-bundle version: `1.30.1`
Package-source git commit: `d8868b6f`
Package-source branch: `wt/jss-review-gpt6`
Paper git commit: `e9f3cce`
Paper branch: `wt/jss-review-gpt6`
Package-source tags at HEAD: `none`
Clean working tree: `False`
Version-consistent inside source: `True`
Ready for final publication release: `False`
Unreleased CHANGELOG nonempty: `True`
Final-publication gate blocker paths: `109` (source=80, paper=29, generated=52)

Interpretation:
Source snapshot evidence; synchronize with a tagged release before final publication or keep these rows explicitly labelled as source-snapshot evidence.

JSS submission archive status:
Audited source-snapshot submission archive; the failing final-publication release gate is a tag/changelog synchronization gate, not a JSS upload reproducibility failure.

Display path redactions:
Active external-review filenames are omitted from the JSS source-snapshot gate, and retired external-review filenames are displayed under retired-external aliases.

Final publication checklist:
- FAIL `clean_combined_worktree` -- 109 hand-edited final-publication gate paths; 52 generated dirty paths
- FAIL `package_tag_at_head` -- no package-source tag at HEAD
- PASS `versions_consistent` -- pyproject, __version__, and schema bundle agree
- FAIL `unreleased_changelog_finalized` -- 444 non-empty lines across 7 headings
- FAIL `source_paths_finalized` -- 80 source/test/docs paths still dirty
- FAIL `paper_paths_finalized` -- 29 Paper-JSS paths still dirty

Final-publication gate blocker breakdown:
- Hand-edited status counts: `{'??': 27, 'M': 70, 'MM': 12}`
- Generated status counts: `{'??': 2, 'M': 45, 'MM': 5}`
- Package code/script paths: `18`
- Package docs paths: `10`
- Validation test/data paths: `47`
- Paper manuscript paths: `11`
- Paper replication paths: `14`
- Paper other paths: `4`

Final-publication gate source paths:
- `?? src/statspai/did/_arp.py`
- `?? src/statspai/validation_scope.py`
- `?? tests/coverage_monte_carlo/mechanisms/`
- `?? tests/reference_parity/_fixtures/_generate_ebalance_weightit_R.R`
- `?? tests/reference_parity/_fixtures/_generate_grf_seed_mc_R.R`
- `?? tests/reference_parity/_fixtures/_generate_grf_seed_mc_py.py`
- `?? tests/reference_parity/_fixtures/_generate_honest_rm_R.R`
- `?? tests/reference_parity/_fixtures/_generate_iv_card_R.R`
- `?? tests/reference_parity/_fixtures/ebalance_lalonde.csv`
- `?? tests/reference_parity/_fixtures/ebalance_sim_cia.csv`
- `?? tests/reference_parity/_fixtures/ebalance_sim_het.csv`
- `?? tests/reference_parity/_fixtures/ebalance_weightit_R.json`
- `?? tests/reference_parity/_fixtures/grf_seed_mc_R.json`
- `?? tests/reference_parity/_fixtures/grf_seed_mc_m13_R.json`
- `?? tests/reference_parity/_fixtures/grf_seed_mc_m13_py.json`
- `?? tests/reference_parity/_fixtures/grf_seed_mc_py.json`
- `?? tests/reference_parity/_fixtures/honest_rm_R.json`
- `?? tests/reference_parity/_fixtures/iv_card.csv`
- `?? tests/reference_parity/_fixtures/iv_card_R.json`
- `?? tests/reference_parity/test_ebalance_weightit_parity.py`
- `?? tests/reference_parity/test_grf_seed_mc_equivalence.py`
- `?? tests/reference_parity/test_honest_rm_R_parity.py`
- `?? tests/reference_parity/test_iv_card_aer_parity.py`
- `?? tests/test_audit_applicability.py`
- `?? tests/test_parity_implementation_provenance.py`
- `?? tests/test_validation_scope.py`
- `M MIGRATION.md`
- `M README.md`
- `M README_CN.md`
- `M docs/guides/stability.md`
- `M docs/index.md`
- `M docs/jss_source_audit_dossier.md`
- `M docs/parity.md`
- `M docs/reference/index.md`
- `M pyproject.toml`
- `M schemas/agent_cards.json`
- `M schemas/functions.json`
- `M schemas/index.json`
- `M schemas/tools.json`
- `M src/statspai/__init__.py`
- `M src/statspai/_parity_index.json`
- `M src/statspai/agent/workflow_tools.py`
- `M src/statspai/core/next_steps.py`
- `M src/statspai/did/honest_did.py`
- `M src/statspai/dml/double_ml.py`
- `M src/statspai/forest/forest_inference.py`
- `M src/statspai/matching/ebalance.py`
- `M src/statspai/question/question.py`
- `M src/statspai/registry.py`
- `M src/statspai/schemas/agent_cards.json`
- `M src/statspai/schemas/functions.json`
- `M src/statspai/schemas/index.json`
- `M src/statspai/schemas/tools.json`
- `M src/statspai/smart/audit.py`
- `M tests/coverage_monte_carlo/FINDINGS.md`
- `M tests/coverage_monte_carlo/results_b1000/coverage_b1000.json`
- `M tests/coverage_monte_carlo/results_b1000/coverage_robustness_b1000.json`
- `M tests/coverage_monte_carlo/results_b1000/size_power_b1000.json`
- `M tests/coverage_monte_carlo/run_b1000.py`
- `M tests/coverage_monte_carlo/run_robustness_b1000.py`
- `M tests/coverage_monte_carlo/run_size_power_b1000.py`
- `M tests/coverage_monte_carlo/test_coverage.py`
- `M tests/r_parity/06_rd.py`
- `M tests/r_parity/10_honest_did.R`
- `M tests/r_parity/10_honest_did.py`
- `M tests/r_parity/21_honest_relmags.py`
- `M tests/r_parity/README.md`
- `M tests/r_parity/TIER_A_FIXTURE_LOCK.json`
- `M tests/reference_parity/test_did_synth_R_parity.py`
- `M tests/reference_parity/test_grf_parity.py`
- `M tests/reference_parity/test_honest_did_backend_parity.py`
- `M tests/test_jss_manuscript_artifacts.py`
- `M tests/test_jss_release_manifest.py`
- `M tests/test_parity_gap_boundaries.py`
- `M tests/test_parity_harness_contract.py`
- `M tests/test_question_dsl.py`
- `MM CHANGELOG.md`
- `MM docs/dev/r_parity_tolerances.md`
- `MM src/statspai/paper.bib`
- `MM tests/r_parity/compare.py`

Final-publication gate Paper-JSS paths:
- `?? Paper-JSS/replication/scripts/generate_forest_seed_table.py`
- `M Paper-JSS/Makefile`
- `M Paper-JSS/README.md`
- `M Paper-JSS/REVIEWER-HARDENING-AUDIT.md`
- `M Paper-JSS/manuscript/README.md`
- `M Paper-JSS/manuscript/jss-bib-archival.bib`
- `M Paper-JSS/manuscript/sections/03-agent-facing-compact.tex`
- `M Paper-JSS/manuscript/sections/04-examples-compact.tex`
- `M Paper-JSS/replication/reproduce.py`
- `M Paper-JSS/replication/scripts/ex03_csdid.py`
- `M Paper-JSS/replication/scripts/experiment_triage.py`
- `M Paper-JSS/replication/scripts/gen_appendix_parity.py`
- `M Paper-JSS/replication/scripts/generate_manuscript_claims.py`
- `M Paper-JSS/replication/scripts/generate_track_b_tables.py`
- `M Paper-JSS/replication/scripts/jss_formal_compliance_audit.py`
- `M Paper-JSS/replication/scripts/listings_execute_audit.py`
- `M Paper-JSS/replication/scripts/manuscript_artifact_audit.py`
- `M Paper-JSS/replication/scripts/release_boundary_audit.py`
- `M Paper-JSS/replication/scripts/validate_claims.py`
- `M Paper-JSS/replication/scripts/validation_evidence_audit.py`
- `M Paper-JSS/replication/scripts/verify_submission_package.py`
- `MM Paper-JSS/cover-letter.md`
- `MM Paper-JSS/manuscript/generated_claims.tex`
- `MM Paper-JSS/manuscript/jss-bib.bib`
- `MM Paper-JSS/manuscript/main.tex`
- `MM Paper-JSS/manuscript/sections/01-introduction-compact.tex`
- `MM Paper-JSS/manuscript/sections/05-parity-compact.tex`
- `MM Paper-JSS/manuscript/sections/08-computational-details-compact.tex`
- `MM Paper-JSS/manuscript/sections/09-discussion-compact.tex`

Generated dirty paths:
- `?? Paper-JSS/manuscript/tables/forest_seed_mc.tex`
- `?? tests/r_parity/results/_implementation_trace.json`
- `M Paper-JSS/manuscript/tables/appendix_b_parity.tex`
- `M Paper-JSS/manuscript/tables/track_a_cross_language_snapshot.tex`
- `M Paper-JSS/manuscript/tables/track_b_monte_carlo.tex`
- `M Paper-JSS/replication/results/agent_benchmark_protocol.json`
- `M Paper-JSS/replication/results/agent_interface_audit.json`
- `M Paper-JSS/replication/results/agent_interface_audit.md`
- `M Paper-JSS/replication/results/bibliography_metadata_audit.json`
- `M Paper-JSS/replication/results/bibliography_metadata_audit.md`
- `M Paper-JSS/replication/results/claim_lint.json`
- `M Paper-JSS/replication/results/claim_lint.md`
- `M Paper-JSS/replication/results/data_provenance_audit.json`
- `M Paper-JSS/replication/results/data_provenance_audit.md`
- `M Paper-JSS/replication/results/ex01_card.json`
- `M Paper-JSS/replication/results/ex03_csdid.json`
- `M Paper-JSS/replication/results/experiment_triage.json`
- `M Paper-JSS/replication/results/experiment_triage.md`
- `M Paper-JSS/replication/results/jss_formal_compliance_audit.json`
- `M Paper-JSS/replication/results/jss_formal_compliance_audit.md`
- `M Paper-JSS/replication/results/jss_full_audit.json`
- `M Paper-JSS/replication/results/jss_full_audit.md`
- `M Paper-JSS/replication/results/jss_house_style_audit.json`
- `M Paper-JSS/replication/results/jss_house_style_audit.md`
- `M Paper-JSS/replication/results/manuscript_artifact_audit.json`
- `M Paper-JSS/replication/results/manuscript_artifact_audit.md`
- `M Paper-JSS/replication/results/methodological_gap_ledger.json`
- `M Paper-JSS/replication/results/pdf_render_audit.json`
- `M Paper-JSS/replication/results/pdf_render_audit.md`
- `M Paper-JSS/replication/results/pdf_visual_check_protocol.json`
- `M Paper-JSS/replication/results/pdf_visual_check_protocol.md`
- `M Paper-JSS/replication/results/release_boundary_audit.json`
- `M Paper-JSS/replication/results/release_boundary_audit.md`
- `M Paper-JSS/replication/results/reproduction_environment_audit.json`
- `M Paper-JSS/replication/results/reproduction_environment_audit.md`
- `M Paper-JSS/replication/results/source_snapshot_manifest.json`
- `M Paper-JSS/replication/results/source_snapshot_manifest.md`
- `M Paper-JSS/replication/results/stata_bridge_audit.json`
- `M Paper-JSS/replication/results/stata_rerun_protocol.json`
- `M tests/r_parity/results/06_rd_py.json`
- ... 12 more

Final publication gate:
`python Paper-JSS/replication/scripts/source_snapshot_manifest.py --strict-release`

Machine-readable detail: `source_snapshot_manifest.json`

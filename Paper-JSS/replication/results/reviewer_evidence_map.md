# JSS Reviewer Evidence Map

Status: PASS
Reviewer evidence cards: 13
Suggested review routes: 5
Expected card identity: confirmed
Expected route identity: confirmed
JSS upload blockers: 0
Final tagged-cut pending items: 0
Archive evidence paths: 40/40 resolved

## Suggested Review Routes

| Route ID | Status | Use when | First read | Evidence cards | Gate |
|---|---:|---|---|---|---|
| `editor_triage` | PASS | You need a fast upload-readiness and JSS-form check before reading statistical detail. | `replication/results/editor_screening_checklist.md` | `software_installability`, `archive_boundary`, `related_review_coi_boundary`, `artifact_provenance`, `final_cut_boundary` | `make editor-screening-checklist + make verify-submission-package` |
| `statistical_validation` | PASS | You want to audit the statistical evidence before the software packaging evidence. | `replication/results/validation_evidence_audit.md` | `validation_scope`, `cross_language_limits`, `experiment_triage`, `limitations_crosswalk` | `make audit` |
| `quick_reproduction` | PASS | You need to reproduce the headline Section 4-7 numbers without live R or Stata. | `replication/results/reproduce_tier1_output.txt` | `headline_reproduction`, `worked_example_scope`, `artifact_provenance` | `make reproduce-jss-full` |
| `agent_interface` | PASS | You are checking the agent-facing contribution but not behavioural agent performance. | `replication/results/agent_interface_audit.md` | `agent_interface_boundary`, `experiment_triage` | `make agent-interface-audit` |
| `limitations_and_release_boundary` | PASS | You are checking residual risks, source-snapshot wording, and what remains after upload. | `manuscript/sections/09-discussion-compact.tex` | `limitations_crosswalk`, `maintenance_sustainability`, `final_cut_boundary`, `archive_boundary` | `make submission-risk-ledger + make release-boundary-audit` |

## Evidence Cards

| Card ID | Status | Reviewer question | Boundary answer | Primary evidence | Gate |
|---|---|---|---|---|---|
| `validation_scope` | PASS | What exactly is validated, and what is only API-stable? | Validated is an evidence tier limited to certified/validated registry entries; API-stable breadth is disclosed separately. | `replication/results/claim_lint.md`<br>`replication/results/validation_evidence_audit.md`<br>`docs/guides/stability.md` | `make audit -> claim_linter + validation_evidence_audit` |
| `headline_reproduction` | PASS | Can headline Section 4-7 numbers be checked quickly? | Tier 1 is the short reviewer path and does not require live R or Stata; Tier 2/3 are external-language reruns. | `replication/results/reproduce_tier1_output.txt`<br>`replication/results/reproduction_environment_audit.md`<br>`replication/reproduce.py` | `make reproduce-tier1-transcript + make audit` |
| `cross_language_limits` | PASS | Where do R/Stata comparisons stop being equality claims? | Track A separates machine/iterative/moderate agreement from the one methodological/T4 disclosure. | `replication/results/methodological_gap_ledger.md`<br>`replication/results/stata_bridge_audit.md`<br>`replication/results/stata_rerun_protocol.md`<br>`manuscript/tables/track_a_cross_language_snapshot.tex` | `make audit -> methodological_gap_ledger + stata_bridge_audit + stata_rerun_protocol` |
| `artifact_provenance` | PASS | Do active tables and figures map to generators? | The active manuscript inputs, generated tables, and figures are audited by label and generator path. | `replication/results/manuscript_artifact_audit.md`<br>`replication/scripts/manuscript_artifact_audit.py`<br>`manuscript/main.tex` | `make manuscript-artifact-audit` |
| `worked_example_scope` | PASS | Do the worked examples match executable scripts and manuscript claims? | The active manuscript reports seven worked examples; the artifact audit verifies the seven executable scripts, seven table/script mentions, seven active subsection labels, and the count claim. | `replication/results/manuscript_artifact_audit.md`<br>`replication/scripts/manuscript_artifact_audit.py`<br>`manuscript/sections/04-examples-compact.tex` | `make manuscript-artifact-audit + make audit` |
| `experiment_triage` | PASS | Which high-ROI experiments are implemented, bounded, or deferred? | The triage report separates implemented JSS evidence from external-runtime checks, behavioural agent benchmarking, API-breadth nonclaims, and post-upload release work; the deferred behavioural benchmark has a packaged protocol rather than an implied result. | `replication/results/experiment_triage.md`<br>`replication/results/agent_benchmark_protocol.md`<br>`replication/scripts/experiment_triage.py`<br>`replication/results/submission_risk_ledger.md` | `make experiment-triage + make reviewer-evidence-map` |
| `archive_boundary` | PASS | Is the submitted archive bounded and free of review-lane spillover? | The archive is a source snapshot with active external-review materials, local notes, and inactive draft sections excluded; the data-provenance audit classifies data/result members and rejects forbidden raw-data formats plus private or credential path hits. | `replication/results/submission_risk_ledger.md`<br>`replication/results/data_provenance_audit.md`<br>`README.md`<br>`replication/scripts/verify_submission_package.py` | `make verify-submission-package` |
| `related_review_coi_boundary` | PASS | Are the related JOSS publication and conflict disclosures visible without modifying the archived JOSS files? | The cover letter discloses the published JOSS paper, states that this manuscript cites it and shares no evidence table with it, and names the maintainer, commercial downstream product, license, and funding facts. | `cover-letter.md`<br>`replication/results/jss_formal_compliance_audit.md`<br>`replication/results/release_boundary_audit.md`<br>`README.md` | `make jss-formal-compliance-audit + make release-boundary-audit` |
| `software_installability` | PASS | Can the submitted source be installed and imported? | Formal compliance verifies JSS class/front matter, license, archive install/import, package help files, PDF-visible boundary text, source-synchronized polished PDF prose, Poppler-rendered PDF sample pages, and an all-page machine render scan; the packaged visual-check protocol adds a page-by-page inventory and makes the final full-document human spot-check actionable while keeping it an upload-time manual action rather than a machine-verified PASS. | `replication/results/jss_formal_compliance_audit.md`<br>`replication/results/pdf_render_audit.md`<br>`replication/results/pdf_visual_check_protocol.md`<br>`replication/scripts/jss_formal_compliance_audit.py`<br>`replication/scripts/pdf_render_audit.py`<br>`replication/scripts/pdf_visual_check_protocol.py`<br>`manuscript/main.pdf`<br>`pyproject.toml` | `make jss-formal-compliance-audit + make pdf-visual-check-protocol` |
| `agent_interface_boundary` | PASS | Are agent-facing claims mechanical rather than behavioural? | The paper audits a mechanical and contractual interface: schemas, typed errors, result handles, traceable tool calls, citation resolution, and the same validation ledger as human calls, rather than claiming agent performance; the archive also ships a deferred benchmark protocol with matched baselines, task families, scoring dimensions, and leakage controls for the separate behavioural study. | `replication/results/agent_interface_audit.md`<br>`replication/results/agent_benchmark_protocol.md`<br>`replication/results/ex07_agent_trace.txt`<br>`schemas/tools.json` | `make agent-interface-audit + make agent-benchmark-protocol` |
| `limitations_crosswalk` | PASS | Where are the compact paper's limitations and residual risks made explicit? | The compact discussion states the main limitations, while the hardening audit and risk ledger keep the residual reviewer risks visible without adding pages to the PDF. | `manuscript/sections/09-discussion-compact.tex`<br>`REVIEWER-HARDENING-AUDIT.md`<br>`replication/results/submission_risk_ledger.md`<br>`replication/results/pdf_visual_check_protocol.md`<br>`replication/results/validation_evidence_audit.md` | `make reviewer-evidence-map + make verify-submission-package` |
| `maintenance_sustainability` | PASS | Is the validated core maintainable if the current maintainer or commercial sponsor changes? | The sustainability claim is bounded: the Discussion states that the validated core is MIT-licensed and forkable, output-changing fixes are regression-tested, and cross-language parity is scripted with environment/provenance files. | `manuscript/sections/09-discussion-compact.tex`<br>`LICENSE`<br>`replication/results/manuscript_artifact_audit.md`<br>`replication/results/reproduction_environment_audit.md` | `make audit + make verify-submission-package` |
| `final_cut_boundary` | PASS | What remains after upload before a final tagged release? | The JSS upload snapshot is separate from final tagged-cut cleanup; pending worktree, tag, changelog, and Paper-JSS finalization items are listed as nonblocking final-cut work. | `replication/results/submission_risk_ledger.md`<br>`replication/results/source_snapshot_manifest.md`<br>`replication/results/release_boundary_audit.md` | `make submission-risk-ledger + make release-boundary-audit` |

## Machine-Readable Metrics

### validation_scope
- `claim_files_checked`: `37`
- `certified_validated_symbols`: `544`
- `api_stable_symbols`: `648`
- `unbacked_handwritten_stable`: `0`
- `unbacked_auto_stable`: `555`

### headline_reproduction
- `tier1_complete`: `True`
- `tier1_no_r_stata`: `True`
- `tier1_live_external_call_count`: `0`
- `r_reproduced_modules`: `89`
- `stata_reproduced_modules`: `85`

### cross_language_limits
- `methodological_gap_count`: `1`
- `classified_gap_count`: `1`
- `uncategorized_gap_count`: `0`
- `stata_modules`: `85`
- `r_joined_stata_modules`: `85`
- `stata_rerun_protocol_status`: `PASS`
- `stata_rerun_protocol_checklist_items`: `8`
- `stata_rerun_requires_license`: `True`
- `stata_rerun_upload_blocking`: `False`
- `stata_rerun_claimed_live_rerun`: `False`
- `stata_rerun_non_reproduced_rows`: `0`

### artifact_provenance
- `active_sections`: `10`
- `generated_artifacts`: `11`
- `float_labels`: `19`
- `missing_refs`: `0`
- `dangling_refs`: `0`

### worked_example_scope
- `expected_count`: `7`
- `scripts_present`: `7`
- `script_mentions`: `7`
- `table_script_mentions`: `7`
- `subsection_labels`: `7`
- `count_claim_present`: `True`

### experiment_triage
- `triage_items`: `8`
- `triage_pass_items`: `8`
- `triage_failed_items`: `0`
- `jss_upload_blocking_item_count`: `0`
- `classification_counts`: `{'deferred_to_separate_benchmark': 1, 'external_runtime_documented': 1, 'implemented': 3, 'implemented_with_boundary': 1, 'not_a_jss_claim': 1, 'post_upload_release_work': 1}`
- `item_ids`: `['cross_language_parity', 'monte_carlo_validation', 'performance_benchmark', 'tier1_reproduction', 'live_stata_rerun', 'behavioural_agent_benchmark', 'full_registry_numeric_validation', 'final_tagged_release']`
- `agent_protocol_arms`: `3`
- `agent_protocol_task_families`: `5`
- `agent_protocol_jss_upload_blocking`: `False`

### archive_boundary
- `jss_upload_blockers`: `0`
- `archive_file_count`: `2800`
- `archive_size_mib`: `24.21`
- `data_provenance_status`: `PASS`
- `data_provenance_scoped_data_files`: `819`
- `data_provenance_csv_files`: `336`
- `data_provenance_packaged_public_datasets`: `9`
- `data_provenance_public_original_extracts`: `7`
- `data_provenance_r_stata_fixture_csv`: `91`
- `data_provenance_forbidden_raw_members`: `0`
- `data_provenance_high_risk_path_hits`: `0`
- `data_provenance_unknown_categories`: `0`
- `active_external_present`: `0`
- `legacy_sections_present`: `0`

### related_review_coi_boundary
- `related_review_check`: `True`
- `related_review_evidence`: `cover-letter related-review/COI snippets=['published in the *Journal of Open Source', 'doi.org/10.21105/joss.10604', 'cites the JOSS paper explicitly', 'disclosed explicitly to the editors', 'StatsPAI Inc.', 'CoPaper.AI', 'No external funder', 'MIT licence']; missing=[].`
- `source_snapshot_boundary_check`: `True`
- `release_boundary_status`: `PASS`
- `active_external_present`: `0`

### software_installability
- `formal_checks`: `23`
- `page_count`: `52`
- `pdf_text_chars`: `148262`
- `pdf_boundary_snippets`: `18`
- `missing_pdf_boundary_snippets`: `[]`
- `pdf_stale_prose_hits`: `[]`
- `pdf_render_status`: `PASS`
- `pdf_rendered_pages`: `4`
- `pdf_render_sampled_pages`: `[1, 2, 26, 52]`
- `pdf_full_document_rendered_pages`: `52`
- `pdf_full_document_failures`: `0`
- `pdf_render_min_width`: `910`
- `pdf_render_min_height`: `1287`
- `pdf_render_min_ink_ratio`: `0.017252`
- `pdf_render_max_dark_ratio`: `0.022067`
- `pdf_render_failures`: `0`
- `manual_visual_spot_check_required`: `True`
- `manual_visual_spot_check_status`: `PENDING_MANUAL_REVIEW`
- `machine_render_not_human_review`: `True`
- `pdf_visual_protocol_status`: `PASS`
- `pdf_visual_protocol_page_count`: `52`
- `pdf_visual_protocol_checklist_items`: `12`
- `pdf_visual_protocol_page_inventory_count`: `52`
- `pdf_visual_protocol_page_inventory_text_pages`: `52`
- `pdf_visual_protocol_page_inventory_min_text_chars`: `491`
- `pdf_visual_protocol_page_inventory_float_markers`: `68`
- `pdf_visual_protocol_manual_status`: `PENDING_MANUAL_REVIEW`
- `pdf_visual_protocol_claimed_manual_acceptance`: `False`
- `pdf_visual_protocol_recorded_by_protocol`: `False`
- `pdf_visual_protocol_jss_upload_blocking`: `False`
- `archive_present`: `True`
- `official_sources_checked`: `2026-08-09`

### agent_interface_boundary
- `schema_files`: `1195`
- `parameter_total`: `9095`
- `trace_tools`: `559`
- `trace_bibtex_entry_count`: `2`
- `protocol_arms`: `3`
- `protocol_task_families`: `5`
- `protocol_scoring_dimensions`: `6`
- `protocol_validity_controls`: `6`
- `protocol_claimed_behavioural_result`: `False`

### limitations_crosswalk
- `pdf_pages`: `52`
- `documented_nonblocking_risk_count`: `5`
- `documented_nonblocking_risk_ids`: `['registry_breadth_denominator_disclosed', 'stata_tier3_requires_license', 'methodological_t4_row_disclosed', 'compact_text_may_feel_terse', 'agent_interface_value_boundary']`
- `pdf_visual_protocol_status`: `PASS`
- `pdf_visual_protocol_checklist_items`: `12`
- `pdf_visual_protocol_page_inventory_count`: `52`
- `pdf_visual_protocol_page_inventory_text_pages`: `52`
- `pdf_visual_protocol_manual_status`: `PENDING_MANUAL_REVIEW`
- `symbols_with_limitations`: `21`
- `certified_validated_symbols`: `544`
- `api_stable_symbols`: `648`
- `unbacked_auto_stable`: `555`

### maintenance_sustainability
- `mit_forkable`: `True`
- `regression_tests`: `True`
- `scripted_parity`: `True`
- `license_file`: `True`
- `artifact_hash_mismatches`: `0`
- `tier1_complete`: `True`
- `r_reproduced_modules`: `89`
- `stata_reproduced_modules`: `85`

### final_cut_boundary
- `final_tagged_cut_pending_items`: `0`
- `final_tagged_cut_identity_ok`: `True`
- `final_tagged_cut_check_ids`: `[]`
- `final_tagged_cut_breakdown`: `{'generated_status_counts': {'M': 28}, 'hand_edited_status_counts': {}, 'package_code_paths': 0, 'package_docs_paths': 0, 'paper_manuscript_paths': 0, 'paper_other_paths': 0, 'paper_replication_paths': 0, 'validation_test_paths': 0}`
- `final_tagged_cut_runbook_step_count`: `5`
- `strict_release_command`: `python Paper-JSS/replication/scripts/source_snapshot_manifest.py --strict-release`
- `documented_nonblocking_risk_identity_ok`: `True`
- `documented_nonblocking_risk_count`: `5`
- `documented_nonblocking_risk_ids`: `['registry_breadth_denominator_disclosed', 'stata_tier3_requires_license', 'methodological_t4_row_disclosed', 'compact_text_may_feel_terse', 'agent_interface_value_boundary']`
- `source_release_pending_paths`: `0`
- `paper_release_pending_paths`: `0`
- `ready_for_final_publication`: `True`

## Final Tagged-Cut Runbook

Nonblocking post-upload release-cut work; not a JSS source-snapshot upload blocker.

1. commit or intentionally exclude all hand-edited source and Paper-JSS paths
2. move accepted [Unreleased] changes into a dated CHANGELOG release entry
3. align pyproject.toml, src/statspai/__init__.py, and schema bundle versions
4. tag the exact package-source commit used by the JSS archive
5. re-run make submission-ready after the tag so manifests record a clean release snapshot

Strict release guard: `python Paper-JSS/replication/scripts/source_snapshot_manifest.py --strict-release`

## Final-Cut Nonblocking Risk Details

| Risk | Evidence | Next action |
|---|---|---|
| `registry_breadth_denominator_disclosed` | 544/1195 registry symbols are certified/validated; missing evidence paths=0 | Keep the validated-core framing and do not promote API-stable breadth without attached evidence notes. |
| `stata_tier3_requires_license` | 85/85 frozen Stata modules audited without live Stata; licensed rerun protocol packaged | Keep Tier 3 optional and keep the Stata license boundary explicit; use stata_rerun_protocol.md for any licensed reviewer rerun and treat missing Stata as an optional-runtime skip, not a JSS upload blocker. |
| `methodological_t4_row_disclosed` | 1/1 methodological/T4 rows classified; uncategorized=0 | Keep the T4 row as a disclosure unless a deterministic T2 bridge is added. |
| `compact_text_may_feel_terse` | active PDF has 52 pages; PDF-visible evidence-map/checklist routing present; packaged PDF visual-check protocol present; page inventory covers 52/52 pages | Keep additional reviewer evidence in replication/results and reviewer_evidence_map rather than expanding main.pdf; perform the final full-document human visual spot-check using pdf_visual_check_protocol.md and the PDF render audit before JSS upload. |
| `agent_interface_value_boundary` | 1195 schemas, 9095 documented parameters, and 559 trace tools audited without behavioural benchmark claims | Keep the agent section mechanical and contractual unless a behavioural benchmark is actually run and packaged; keep the deferred benchmark protocol labelled as protocol rather than a completed behavioural result. |

Failures: none

Machine-readable detail: `replication/results/reviewer_evidence_map.json`

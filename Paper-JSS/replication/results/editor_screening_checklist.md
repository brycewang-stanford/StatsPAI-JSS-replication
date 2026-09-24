# JSS Editor Screening Checklist

Status: PASS
Checklist items: 11
Expected item identity: confirmed
JSS upload blockers: 0
Archive evidence paths: 24/24 resolved

| Item ID | Status | Editor check | Answer | Primary evidence | Gate |
|---|---:|---|---|---|---|
| `jss_pdf_front_matter` | PASS | Does the submitted PDF look like a JSS article? | The active PDF uses the JSS article class, has complete front matter, is 52 pages, and passes representative-page plus full-document machine render sanity audits. The packaged PDF visual-check protocol adds a page-by-page inventory and makes the final full-document human spot-check actionable, but the check remains an upload-time manual action rather than a machine-verified PASS. | `manuscript/main.pdf`<br>`replication/results/jss_formal_compliance_audit.md`<br>`replication/results/pdf_render_audit.md`<br>`replication/results/pdf_visual_check_protocol.md` | `make verify + make jss-formal-compliance-audit + make pdf-visual-check-protocol` |
| `license_and_citation` | PASS | Are license and citation metadata explicit? | The source archive includes MIT license evidence, GPL-compatible license disclosure, and root CITATION.cff metadata. | `cover-letter.md`<br>`replication/results/jss_formal_compliance_audit.md`<br>`CITATION.cff`<br>`LICENSE` | `make jss-formal-compliance-audit` |
| `source_installability` | PASS | Can the submitted source be installed/imported? | The formal audit performs a no-deps source install/import probe against the packaged source and records the console scripts. | `pyproject.toml`<br>`src/statspai/__init__.py`<br>`replication/results/jss_formal_compliance_audit.md` | `make jss-formal-compliance-audit` |
| `reproduction_quick_path` | PASS | Is there a short reviewer reproduction path? | Tier 1 rebuilds the Section 4-7 headline numbers without live R or Stata and records a 24/24 reviewer transcript. | `replication/reproduce.py`<br>`replication/results/reproduce_tier1_output.txt`<br>`replication/results/reproduction_environment_audit.md` | `make reproduce-tier1-transcript + make audit` |
| `archive_size_boundary` | PASS | Is the upload archive bounded and review-lane clean? | The package is 24.21 MiB (25.38 MB decimal) with 2,800 files, under the 50 MB JSS limit, and excludes active external-review artifacts plus dormant manuscript drafts. The data-provenance report classifies archive data/result members and records zero forbidden raw-data members, zero private/credential path hits, and zero unknown categories. | `build/statspai-jss-submission-manifest.md`<br>`replication/results/submission_risk_ledger.md`<br>`replication/results/data_provenance_audit.md`<br>`replication/results/jss_full_audit.md` | `make data-provenance-audit + make verify-submission-package` |
| `related_review_coi` | PASS | Are related-review and COI disclosures explicit? | The cover letter discloses the published JOSS software paper (doi.org/10.21105/joss.10604), states that this manuscript cites it and shares no table, figure, simulation, or parity ledger with it, and names COI and funding/license facts. | `cover-letter.md`<br>`replication/results/jss_formal_compliance_audit.md`<br>`replication/results/release_boundary_audit.md` | `make jss-formal-compliance-audit + make release-boundary-audit` |
| `evidence_navigation` | PASS | Can reviewers navigate evidence without guessing? | The reviewer map has 13 stable PASS cards and 5 suggested review routes; every primary evidence path resolves inside the submission archive. | `replication/results/reviewer_evidence_map.md`<br>`replication/results/jss_full_audit.md` | `make reviewer-evidence-map + make verify-submission-package` |
| `final_release_boundary` | PASS | Is upload readiness separated from final release cutting? | The submission has 0 JSS upload blockers, 0 currently pending final tagged-cut checks, and 5 final tagged-release runbook steps explicitly listed as nonblocking. The source release path has 0 pending source/test/docs blockers, while 0 Paper-JSS finalization paths remain for the tagged release cut. | `replication/results/submission_risk_ledger.md`<br>`replication/results/source_snapshot_manifest.md`<br>`replication/results/release_boundary_audit.md` | `make submission-risk-ledger + make verify-submission-package` |
| `nonblocking_risk_crosswalk` | PASS | Are residual risks disclosed without hiding upload blockers? | The risk ledger lists 5 documented nonblocking risks with next actions and 0 JSS upload blockers: final tagged-release cleanup; registry-breadth denominator disclosure; Stata Tier 3 license boundary; methodological/T4 disclosure; compact-text/PDF-review boundary (PDF-visible evidence routing, page-inventory navigation, and final manual PDF visual-check protocol); and agent-interface value boundary. | `replication/results/submission_risk_ledger.md`<br>`replication/results/reviewer_evidence_map.md`<br>`manuscript/sections/09-discussion-compact.tex` | `make submission-risk-ledger + make reviewer-evidence-map` |
| `artifact_provenance` | PASS | Do active tables and figures map to generators? | The manuscript-artifact audit maps active tables/figures to generators, checks narrative references plus hashes, and guards compact-section contribution/evidence/boundary anchors. | `replication/results/manuscript_artifact_audit.md`<br>`manuscript/main.tex` | `make manuscript-artifact-audit` |
| `platform_dependency_boundary` | PASS | Are platform dependencies and RNG boundaries explicit? | The reproduction-environment audit verifies Docker/Python/R/Stata contracts, complete external-language ledgers, and zero unseeded stochastic reproduction scripts. The Stata Tier-3 rerun protocol records the licensed optional rerun path without making missing Stata an upload blocker. | `replication/results/reproduction_environment_audit.md`<br>`replication/results/stata_rerun_protocol.md`<br>`replication/Dockerfile`<br>`requirements-jss.txt` | `make reproduction-environment-audit + make stata-rerun-protocol` |

## Machine-Readable Metrics

### jss_pdf_front_matter
- `page_count`: `52`
- `pdf_render_status`: `PASS`
- `sampled_pages`: `[1, 2, 26, 52]`
- `full_document_machine_scan_pages`: `52`
- `full_document_machine_scan_failures`: `0`
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

### license_and_citation
- `license_check`: `True`
- `citation_check`: `True`

### source_installability
- `install_check`: `True`
- `package_version`: `1.30.1`
- `source_version`: `1.30.1`

### reproduction_quick_path
- `status`: `PASS`
- `tier1_no_r_stata`: `True`
- `tier1_live_external_call_count`: `0`
- `r_reproduced_modules`: `89`
- `stata_reproduced_modules`: `85`
- `tier1_step_summary`: `24/24`

### archive_size_boundary
- `size_mib`: `24.21`
- `size_mb_decimal`: `25.38`
- `file_count`: `2800`
- `data_provenance_status`: `PASS`
- `data_provenance_scoped_data_files`: `819`
- `data_provenance_csv_files`: `336`
- `data_provenance_packaged_public_datasets`: `9`
- `data_provenance_public_original_extracts`: `7`
- `data_provenance_r_stata_fixture_csv`: `91`
- `data_provenance_forbidden_raw_members`: `0`
- `data_provenance_high_risk_path_hits`: `0`
- `data_provenance_unknown_categories`: `0`
- `active_external_review_artifacts_present`: `[]`
- `legacy_manuscript_sources_present`: `[]`

### related_review_coi
- `related_review_check`: `True`
- `release_boundary_status`: `PASS`
- `checked_file_count`: `8`

### evidence_navigation
- `card_count`: `13`
- `failed_cards`: `0`
- `route_count`: `5`
- `failed_routes`: `0`
- `archive_evidence_paths_resolved`: `40`
- `archive_evidence_paths_checked`: `40`

### final_release_boundary
- `jss_upload_blockers`: `0`
- `final_tagged_cut_pending_items`: `0`
- `runbook_step_count`: `5`
- `ready_for_final_publication`: `True`
- `source_release_pending_paths`: `0`
- `paper_release_pending_paths`: `0`
- `submission_archive_status`: `Audited source-snapshot submission archive; the failing final-publication release gate is a tag/changelog synchronization gate, not a JSS upload reproducibility failure.`

### nonblocking_risk_crosswalk
- `documented_nonblocking_risk_count`: `5`
- `documented_nonblocking_risk_ids`: `['registry_breadth_denominator_disclosed', 'stata_tier3_requires_license', 'methodological_t4_row_disclosed', 'compact_text_may_feel_terse', 'agent_interface_value_boundary']`
- `documented_nonblocking_risk_identity_ok`: `True`
- `risks_with_next_action_count`: `5`
- `jss_upload_blockers`: `0`

### artifact_provenance
- `artifact_count`: `11`
- `hash_mismatches`: `0`
- `missing_refs`: `0`
- `dangling_refs`: `0`
- `compact_sections_checked`: `10`
- `compact_sections_passed`: `10`
- `compact_missing_anchors`: `0`

### platform_dependency_boundary
- `reproduction_status`: `PASS`
- `stata_rerun_protocol_status`: `PASS`
- `stata_rerun_requires_license`: `True`
- `stata_rerun_upload_blocking`: `False`
- `stata_rerun_claimed_live_rerun`: `False`
- `stata_rerun_checklist_items`: `8`
- `tier1_no_r_stata`: `True`
- `r_reproduced_modules`: `89`
- `stata_reproduced_modules`: `85`
- `stochastic_file_count`: `16`
- `unseeded_stochastic_file_count`: `0`
- `unseeded_stochastic_files`: `[]`

Failures: none

Machine-readable detail: `replication/results/editor_screening_checklist.json`

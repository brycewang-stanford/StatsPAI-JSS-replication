# StatsPAI JSS Source Snapshot Manifest

Package metadata version: `1.40.2`
Source `__version__`: `1.40.2`
Committed schema-bundle version: `1.40.2`
Package-source git commit: `25a9407ee`
Package-source branch: `detached-or-unknown`
Paper git commit: `2914195`
Paper branch: `editorial-1111`
Package-source tags at HEAD: `v1.40.2`
Clean working tree: `False`
Version-consistent inside source: `True`
Ready for final publication release: `False`
Unreleased CHANGELOG nonempty: `False`
Final-publication gate blocker paths: `28` (source=1, paper=27, generated=53)

Interpretation:
Source snapshot evidence; synchronize with a tagged release before final publication or keep these rows explicitly labelled as source-snapshot evidence.

JSS submission archive status:
Audited source-snapshot submission archive; the failing final-publication release gate is a tag/changelog synchronization gate, not a JSS upload reproducibility failure.

Display path redactions:
Active external-review filenames are omitted from the JSS source-snapshot gate, and retired external-review filenames are displayed under retired-external aliases.

Final publication checklist:
- FAIL `clean_combined_worktree` -- 28 hand-edited final-publication gate paths; 53 generated dirty paths
- PASS `package_tag_at_head` -- v1.40.2
- PASS `versions_consistent` -- pyproject, __version__, and schema bundle agree
- PASS `unreleased_changelog_finalized` -- 0 non-empty lines across 0 headings; 0 MIGRATION.md Unreleased sections
- FAIL `source_paths_finalized` -- 1 source/test/docs paths still dirty
- FAIL `paper_paths_finalized` -- 27 Paper-JSS paths still dirty

Final-publication gate blocker breakdown:
- Hand-edited status counts: `{'??': 4, 'M': 24}`
- Generated status counts: `{'??': 3, 'M': 50}`
- Package code/script paths: `0`
- Package docs paths: `0`
- Validation test/data paths: `1`
- Paper manuscript paths: `13`
- Paper replication paths: `10`
- Paper other paths: `4`

Final-publication gate source paths:
- `M tests/perf/compare_perf.py`

Final-publication gate Paper-JSS paths:
- `?? Paper-JSS/replication/scripts/dml_plr_designs.py`
- `?? Paper-JSS/replication/scripts/generate_dml_designs_table.py`
- `?? Paper-JSS/replication/scripts/sdid_drawwise_reference.R`
- `?? Paper-JSS/replication/scripts/sdid_drawwise_reference.py`
- `M Paper-JSS/Makefile`
- `M Paper-JSS/README.md`
- `M Paper-JSS/RELEASE-CHECKLIST.md`
- `M Paper-JSS/cover-letter.md`
- `M Paper-JSS/manuscript/README.md`
- `M Paper-JSS/manuscript/jss-bib-archival.bib`
- `M Paper-JSS/manuscript/jss-bib.bib`
- `M Paper-JSS/manuscript/main.tex`
- `M Paper-JSS/manuscript/sections/01-introduction-compact.tex`
- `M Paper-JSS/manuscript/sections/02-architecture-compact.tex`
- `M Paper-JSS/manuscript/sections/03-agent-facing-compact.tex`
- `M Paper-JSS/manuscript/sections/04-examples-compact.tex`
- `M Paper-JSS/manuscript/sections/05-parity-compact.tex`
- `M Paper-JSS/manuscript/sections/06-performance.tex`
- `M Paper-JSS/manuscript/sections/07-agent-eval.tex`
- `M Paper-JSS/manuscript/sections/08-computational-details-compact.tex`
- `M Paper-JSS/manuscript/sections/09-discussion-compact.tex`
- `M Paper-JSS/replication/reproduce.py`
- `M Paper-JSS/replication/scripts/generate_figures.py`
- `M Paper-JSS/replication/scripts/jss_submission_package.py`
- `M Paper-JSS/replication/scripts/listings_execute_audit.py`
- `M Paper-JSS/replication/scripts/manuscript_artifact_audit.py`
- `M Paper-JSS/replication/scripts/pdf_visual_check_protocol.py`

Generated dirty paths:
- `?? Paper-JSS/manuscript/tables/dml_plr_designs.tex`
- `?? Paper-JSS/replication/results/dml_plr_designs.json`
- `?? Paper-JSS/replication/results/sdid_drawwise_reference.json`
- `M Paper-JSS/manuscript/figures/ex02_basque_gap.pdf`
- `M Paper-JSS/manuscript/figures/ex02_basque_gap.png`
- `M Paper-JSS/manuscript/main.pdf`
- `M Paper-JSS/replication/results/bibliography_metadata_audit.json`
- `M Paper-JSS/replication/results/bibliography_metadata_audit.md`
- `M Paper-JSS/replication/results/data_provenance_audit.json`
- `M Paper-JSS/replication/results/data_provenance_audit.md`
- `M Paper-JSS/replication/results/editor_screening_checklist.json`
- `M Paper-JSS/replication/results/editor_screening_checklist.md`
- `M Paper-JSS/replication/results/experiment_triage.json`
- `M Paper-JSS/replication/results/experiment_triage.md`
- `M Paper-JSS/replication/results/jss_formal_compliance_audit.json`
- `M Paper-JSS/replication/results/jss_formal_compliance_audit.md`
- `M Paper-JSS/replication/results/jss_full_audit.json`
- `M Paper-JSS/replication/results/jss_full_audit.md`
- `M Paper-JSS/replication/results/jss_house_style_audit.json`
- `M Paper-JSS/replication/results/jss_house_style_audit.md`
- `M Paper-JSS/replication/results/listings_execute_audit.json`
- `M Paper-JSS/replication/results/listings_execute_audit.md`
- `M Paper-JSS/replication/results/manuscript_artifact_audit.json`
- `M Paper-JSS/replication/results/manuscript_artifact_audit.md`
- `M Paper-JSS/replication/results/pdf_render_audit.json`
- `M Paper-JSS/replication/results/pdf_render_audit.md`
- `M Paper-JSS/replication/results/pdf_visual_check_protocol.json`
- `M Paper-JSS/replication/results/pdf_visual_check_protocol.md`
- `M Paper-JSS/replication/results/release_boundary_audit.json`
- `M Paper-JSS/replication/results/release_boundary_audit.md`
- `M Paper-JSS/replication/results/reproduce_manifest.json`
- `M Paper-JSS/replication/results/reproduce_tier1_output.txt`
- `M Paper-JSS/replication/results/reproduction_environment_audit.json`
- `M Paper-JSS/replication/results/reproduction_environment_audit.md`
- `M Paper-JSS/replication/results/reviewer_evidence_map.json`
- `M Paper-JSS/replication/results/reviewer_evidence_map.md`
- `M Paper-JSS/replication/results/source_snapshot_manifest.json`
- `M Paper-JSS/replication/results/source_snapshot_manifest.md`
- `M Paper-JSS/replication/results/submission_risk_ledger.json`
- `M Paper-JSS/replication/results/submission_risk_ledger.md`
- ... 13 more

Final publication gate:
`python Paper-JSS/replication/scripts/source_snapshot_manifest.py --strict-release`

Machine-readable detail: `source_snapshot_manifest.json`

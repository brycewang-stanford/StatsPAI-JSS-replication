# StatsPAI JSS Source Snapshot Manifest

Package metadata version: `1.40.2`
Source `__version__`: `1.40.2`
Committed schema-bundle version: `1.40.2`
Package-source git commit: `25a9407ee`
Package-source branch: `detached-or-unknown`
Paper git commit: `9b46d9b`
Paper branch: `main`
Package-source tags at HEAD: `v1.40.2`
Clean working tree: `False`
Version-consistent inside source: `True`
Ready for final publication release: `False`
Unreleased CHANGELOG nonempty: `False`
Final-publication gate blocker paths: `1` (source=1, paper=0, generated=35)

Interpretation:
Source snapshot evidence; synchronize with a tagged release before final publication or keep these rows explicitly labelled as source-snapshot evidence.

JSS submission archive status:
Audited source-snapshot submission archive; the failing final-publication release gate is a tag/changelog synchronization gate, not a JSS upload reproducibility failure.

Display path redactions:
Active external-review filenames are omitted from the JSS source-snapshot gate, and retired external-review filenames are displayed under retired-external aliases.

Final publication checklist:
- FAIL `clean_combined_worktree` -- 1 hand-edited final-publication gate paths; 35 generated dirty paths
- PASS `package_tag_at_head` -- v1.40.2
- PASS `versions_consistent` -- pyproject, __version__, and schema bundle agree
- PASS `unreleased_changelog_finalized` -- 0 non-empty lines across 0 headings; 0 MIGRATION.md Unreleased sections
- FAIL `source_paths_finalized` -- 1 source/test/docs paths still dirty
- PASS `paper_paths_finalized` -- 0 Paper-JSS paths still dirty

Final-publication gate blocker breakdown:
- Hand-edited status counts: `{'M': 1}`
- Generated status counts: `{'M': 35}`
- Package code/script paths: `0`
- Package docs paths: `0`
- Validation test/data paths: `1`
- Paper manuscript paths: `0`
- Paper replication paths: `0`
- Paper other paths: `0`

Final-publication gate source paths:
- `M tests/perf/compare_perf.py`

Final-publication gate Paper-JSS paths:
- none

Generated dirty paths:
- `M Paper-JSS/replication/results/data_provenance_audit.json`
- `M Paper-JSS/replication/results/editor_screening_checklist.json`
- `M Paper-JSS/replication/results/editor_screening_checklist.md`
- `M Paper-JSS/replication/results/experiment_triage.json`
- `M Paper-JSS/replication/results/experiment_triage.md`
- `M Paper-JSS/replication/results/jss_formal_compliance_audit.json`
- `M Paper-JSS/replication/results/jss_formal_compliance_audit.md`
- `M Paper-JSS/replication/results/jss_full_audit.json`
- `M Paper-JSS/replication/results/jss_full_audit.md`
- `M Paper-JSS/replication/results/pdf_render_audit.json`
- `M Paper-JSS/replication/results/pdf_visual_check_protocol.json`
- `M Paper-JSS/replication/results/pdf_visual_check_protocol.md`
- `M Paper-JSS/replication/results/release_boundary_audit.json`
- `M Paper-JSS/replication/results/release_boundary_audit.md`
- `M Paper-JSS/replication/results/reproduce_manifest.json`
- `M Paper-JSS/replication/results/reproduce_tier1_output.txt`
- `M Paper-JSS/replication/results/reviewer_evidence_map.json`
- `M Paper-JSS/replication/results/reviewer_evidence_map.md`
- `M Paper-JSS/replication/results/source_snapshot_manifest.json`
- `M Paper-JSS/replication/results/source_snapshot_manifest.md`
- `M Paper-JSS/replication/results/submission_risk_ledger.json`
- `M Paper-JSS/replication/results/submission_risk_ledger.md`
- `M tests/perf/figures/track_c_loglog.pdf`
- `M tests/perf/figures/track_c_loglog.png`
- `M tests/perf/results/01_hdfe_R.json`
- `M tests/perf/results/01_hdfe_py.json`
- `M tests/perf/results/02_csdid_R.json`
- `M tests/perf/results/02_csdid_py.json`
- `M tests/perf/results/03_scm_R.json`
- `M tests/perf/results/03_scm_py.json`
- `M tests/perf/results/04_dml_doubleml_py.json`
- `M tests/perf/results/04_dml_py.json`
- `M tests/perf/results/_timed_path.json`
- `M tests/perf/results/perf_table.md`
- `M tests/perf/results/perf_table.tex`

Final publication gate:
`python Paper-JSS/replication/scripts/source_snapshot_manifest.py --strict-release`

Machine-readable detail: `source_snapshot_manifest.json`

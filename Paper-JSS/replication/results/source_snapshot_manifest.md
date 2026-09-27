# StatsPAI JSS Source Snapshot Manifest

Package metadata version: `1.32.0`
Source `__version__`: `1.32.0`
Committed schema-bundle version: `1.32.0`
Package-source git commit: `23da3621`
Package-source branch: `detached-or-unknown`
Paper git commit: `dc4bef2`
Paper branch: `wt/jss-final`
Package-source tags at HEAD: `v1.32.0`
Clean working tree: `False`
Version-consistent inside source: `True`
Ready for final publication release: `False`
Unreleased CHANGELOG nonempty: `False`
Final-publication gate blocker paths: `2` (source=0, paper=2, generated=30)

Interpretation:
Source snapshot evidence; synchronize with a tagged release before final publication or keep these rows explicitly labelled as source-snapshot evidence.

JSS submission archive status:
Audited source-snapshot submission archive; the failing final-publication release gate is a tag/changelog synchronization gate, not a JSS upload reproducibility failure.

Display path redactions:
Active external-review filenames are omitted from the JSS source-snapshot gate, and retired external-review filenames are displayed under retired-external aliases.

Final publication checklist:
- FAIL `clean_combined_worktree` -- 2 hand-edited final-publication gate paths; 30 generated dirty paths
- PASS `package_tag_at_head` -- v1.32.0
- PASS `versions_consistent` -- pyproject, __version__, and schema bundle agree
- PASS `unreleased_changelog_finalized` -- 0 non-empty lines across 0 headings; 0 MIGRATION.md Unreleased sections
- PASS `source_paths_finalized` -- 0 source/test/docs paths still dirty
- FAIL `paper_paths_finalized` -- 2 Paper-JSS paths still dirty

Final-publication gate blocker breakdown:
- Hand-edited status counts: `{'M': 2}`
- Generated status counts: `{'M': 30}`
- Package code/script paths: `0`
- Package docs paths: `0`
- Validation test/data paths: `0`
- Paper manuscript paths: `0`
- Paper replication paths: `2`
- Paper other paths: `0`

Final-publication gate source paths:
- none

Final-publication gate Paper-JSS paths:
- `M Paper-JSS/replication/scripts/render_cover_letter.py`
- `M Paper-JSS/replication/scripts/validate_claims.py`

Generated dirty paths:
- `M Paper-JSS/replication/results/agent_benchmark_protocol.json`
- `M Paper-JSS/replication/results/agent_interface_audit.json`
- `M Paper-JSS/replication/results/bibliography_metadata_audit.json`
- `M Paper-JSS/replication/results/claim_lint.json`
- `M Paper-JSS/replication/results/data_provenance_audit.json`
- `M Paper-JSS/replication/results/editor_screening_checklist.json`
- `M Paper-JSS/replication/results/editor_screening_checklist.md`
- `M Paper-JSS/replication/results/experiment_triage.json`
- `M Paper-JSS/replication/results/experiment_triage.md`
- `M Paper-JSS/replication/results/jss_formal_compliance_audit.json`
- `M Paper-JSS/replication/results/jss_formal_compliance_audit.md`
- `M Paper-JSS/replication/results/jss_full_audit.json`
- `M Paper-JSS/replication/results/jss_full_audit.md`
- `M Paper-JSS/replication/results/jss_house_style_audit.json`
- `M Paper-JSS/replication/results/listings_execute_audit.json`
- `M Paper-JSS/replication/results/listings_execute_audit.md`
- `M Paper-JSS/replication/results/manuscript_artifact_audit.json`
- `M Paper-JSS/replication/results/pdf_render_audit.json`
- `M Paper-JSS/replication/results/pdf_visual_check_protocol.json`
- `M Paper-JSS/replication/results/release_boundary_audit.json`
- `M Paper-JSS/replication/results/release_boundary_audit.md`
- `M Paper-JSS/replication/results/reproduce_tier1_output.txt`
- `M Paper-JSS/replication/results/reviewer_evidence_map.json`
- `M Paper-JSS/replication/results/reviewer_evidence_map.md`
- `M Paper-JSS/replication/results/source_snapshot_manifest.json`
- `M Paper-JSS/replication/results/source_snapshot_manifest.md`
- `M Paper-JSS/replication/results/stata_bridge_audit.json`
- `M Paper-JSS/replication/results/stata_rerun_protocol.json`
- `M Paper-JSS/replication/results/submission_risk_ledger.json`
- `M Paper-JSS/replication/results/submission_risk_ledger.md`

Final publication gate:
`python Paper-JSS/replication/scripts/source_snapshot_manifest.py --strict-release`

Machine-readable detail: `source_snapshot_manifest.json`

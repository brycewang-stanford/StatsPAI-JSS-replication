# JSS Submission Risk Ledger

Status: PASS

Scope: JSS source-snapshot upload readiness. Final tagged-release readiness is tracked separately and is not treated as a JSS upload reproducibility failure when the source-snapshot boundary remains explicit.

JSS upload blockers: 0
Final tagged-cut pending items: 0
Final tagged-cut check identity: confirmed
Documented nonblocking risk identity: confirmed

## Upload Readiness Checks

| Check | Status | Evidence |
|---|---:|---|
| `claim_lint_pass` | PASS | replication/results/claim_lint.json status=PASS |
| `validation_evidence_pass` | PASS | replication/results/validation_evidence_audit.json status=PASS |
| `methodological_gap_ledger_pass` | PASS | replication/results/methodological_gap_ledger.json status=PASS |
| `stata_bridge_pass` | PASS | replication/results/stata_bridge_audit.json status=PASS |
| `stata_rerun_protocol_pass` | PASS | replication/results/stata_rerun_protocol.json status=PASS |
| `agent_interface_pass` | PASS | replication/results/agent_interface_audit.json status=PASS |
| `release_boundary_pass` | PASS | replication/results/release_boundary_audit.json status=PASS |
| `reproduction_environment_pass` | PASS | replication/results/reproduction_environment_audit.json status=PASS |
| `manuscript_artifacts_pass` | PASS | replication/results/manuscript_artifact_audit.json status=PASS |
| `pdf_visual_check_protocol_pass` | PASS | replication/results/pdf_visual_check_protocol.json status=PASS |
| `jss_formal_compliance_pass` | PASS | replication/results/jss_formal_compliance_audit.json status=PASS |
| `archive_present` | PASS | build/statspai-jss-submission.zip |
| `archive_manifest_present` | PASS | build/statspai-jss-submission-manifest.json |
| `archive_within_50mb` | PASS | 24.21 MiB / 25.38 MB decimal |
| `active_manuscript_sections_only` | PASS | archive manifest lists the ten active manuscript inputs |
| `active_joss_artifacts_excluded` | PASS | active external-review artifacts are declared excluded from the JSS archive |
| `archive_forbidden_members_absent` | PASS | no JOSS artifacts, local notes, main.md, or dormant full sections in archive |
| `versions_consistent_inside_source` | PASS | package=1.30.1; source=1.30.1; schema=1.30.1 |
| `source_snapshot_submission_status_disclosed` | PASS | Audited source-snapshot submission archive; the failing final-publication release gate is a tag/changelog synchronization gate, not a JSS upload reproducibility failure. |
| `final_tagged_release_blocker_identity` | PASS | expected_ordered_subset_of=['clean_combined_worktree', 'package_tag_at_head', 'unreleased_changelog_finalized', 'source_paths_finalized', 'paper_paths_finalized']; observed=[] |
| `documented_nonblocking_risk_identity` | PASS | expected=['registry_breadth_denominator_disclosed', 'stata_tier3_requires_license', 'methodological_t4_row_disclosed', 'compact_text_may_feel_terse', 'agent_interface_value_boundary']; observed=['registry_breadth_denominator_disclosed', 'stata_tier3_requires_license', 'methodological_t4_row_disclosed', 'compact_text_may_feel_terse', 'agent_interface_value_boundary'] |

## Final Tagged-Cut Pending Items

None.

## Final Tagged-Cut Breakdown

| Bucket | Count/detail |
|---|---|
| Hand-edited status counts | `{}` |
| Generated status counts | `{'M': 28}` |
| Package code/script paths | `0` |
| Package docs paths | `0` |
| Validation test/data paths | `0` |
| Paper manuscript paths | `0` |
| Paper replication paths | `0` |
| Paper other paths | `0` |

## Final Tagged-Cut Runbook

These steps are nonblocking post-upload release-cut work, not JSS source-snapshot upload blockers.

1. commit or intentionally exclude all hand-edited source and Paper-JSS paths
2. move accepted [Unreleased] changes into a dated CHANGELOG release entry
3. align pyproject.toml, src/statspai/__init__.py, and schema bundle versions
4. tag the exact package-source commit used by the JSS archive
5. re-run make submission-ready after the tag so manifests record a clean release snapshot

Strict release guard: `python Paper-JSS/replication/scripts/source_snapshot_manifest.py --strict-release`

## Documented Nonblocking Risks

| Risk | Evidence | Next action |
|---|---|---|
| `registry_breadth_denominator_disclosed` | 544/1195 registry symbols are certified/validated; missing evidence paths=0 | Keep the validated-core framing and do not promote API-stable breadth without attached evidence notes. |
| `stata_tier3_requires_license` | 85/85 frozen Stata modules audited without live Stata; licensed rerun protocol packaged | Keep Tier 3 optional and keep the Stata license boundary explicit; use stata_rerun_protocol.md for any licensed reviewer rerun and treat missing Stata as an optional-runtime skip, not a JSS upload blocker. |
| `methodological_t4_row_disclosed` | 1/1 methodological/T4 rows classified; uncategorized=0 | Keep the T4 row as a disclosure unless a deterministic T2 bridge is added. |
| `compact_text_may_feel_terse` | active PDF has 52 pages; PDF-visible evidence-map/checklist routing present; packaged PDF visual-check protocol present; page inventory covers 52/52 pages | Keep additional reviewer evidence in replication/results and reviewer_evidence_map rather than expanding main.pdf; perform the final full-document human visual spot-check using pdf_visual_check_protocol.md and the PDF render audit before JSS upload. |
| `agent_interface_value_boundary` | 1195 schemas, 9095 documented parameters, and 559 trace tools audited without behavioural benchmark claims | Keep the agent section mechanical and contractual unless a behavioural benchmark is actually run and packaged; keep the deferred benchmark protocol labelled as protocol rather than a completed behavioural result. |

## Archive Summary

- Size: 24.21 MiB (25.38 MB decimal)
- Files: 2800
- Registry evidence files: 483
- Active external-review artifacts present: []
- Legacy manuscript sources present: []

## Source Snapshot Summary

- Package/source/schema versions: 1.30.1 / 1.30.1 / 1.30.1
- Package commit: a24a2534
- Paper commit: a8dc94a
- Ready for final publication release: True
- Strict release command: `python Paper-JSS/replication/scripts/source_snapshot_manifest.py --strict-release`

Machine-readable detail: `replication/results/submission_risk_ledger.json`

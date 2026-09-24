# JSS Formal Compliance Audit

Status: PASS
Official JSS pages checked: 2026-08-09

Official sources:
- JSS submissions checklist: https://www.jstatsoft.org/about/submissions
- JSS information for authors: https://www.jstatsoft.org/authors
- JSS style guide: https://www.jstatsoft.org/style
- JSS submission guide: https://www.jstatsoft.org/guides/submission

Checklist:
- PASS -- PDF manuscript in JSS LaTeX article style: main.pdf pages=52; class=article jss; missing_front_matter=[]
- PASS -- LaTeX build log is free of blocking layout/reference errors: main.log present=True; blocking_patterns=[]; underfull boxes are not treated as blocking.
- PASS -- PDF-visible validation/source/data/agent boundaries are present: main.pdf text contains validation-tier, API-stable denominator, source-snapshot/release, data-provenance, and mechanical-agent boundary snippets; missing=[].
- PASS -- PDF text is synchronized with polished manuscript prose: main.pdf text is checked for stale defensive reviewer-facing phrases; stale_hits=[].
- PASS -- rendered PDF page-sample sanity check passes: pdf_render_audit renders representative pages and rejects blank, overwhelmingly dark, or implausibly small rasters, then scans every PDF page with the same machine thresholds; status=PASS; sampled=[1, 2, 26, 52]; rendered=4; full_scan=52/52; full_failures=0; min_width=910; min_height=1287; min_ink_ratio=0.085421; max_dark_ratio=0.02163; failures=0.
- PASS -- JSS markup macros and labelled floats are used: active manuscript markup counts={'proglang': 157, 'pkg': 219, 'code': 518}; caption_label_failures=[].
- PASS -- source code is packaged for installation: pyproject.toml uses setuptools, src layout, and console entry points; development classifier is Beta rather than Alpha; pip --no-deps --target install/import probe ok=True; version=1.30.1; functions=1220; scripts=['statspai', 'statspai-mcp']; dist_infos=['statspai-1.30.1.dist-info'].
- PASS -- formatted package help/documentation files are included: README plus getting-started, reference, and stability docs present; missing_help=[].
- PASS -- GPL-compatible software license is clearly indicated: LICENSE, pyproject.toml, and cover letter all identify MIT/GPL compatibility.
- PASS -- software citation metadata is included: Root CITATION.cff identifies the software, license, code repository, and PyPI artifact.
- PASS -- standalone replication script covers manuscript results: replication/reproduce.py plus Makefile tiers; Tier-1 transcript is complete.
- PASS -- reviewer output transcript for standalone replication script is included: Tier-1 transcript file is included and records 24/24 successful steps.
- PASS -- short reviewer replication path completes within one hour: Tier-1 transcript reports 24/24 steps in 1.0 minutes; JSS asks for a short reviewer-verification path when full replication is heavier.
- PASS -- existing implementations and comparative scope are discussed: Active manuscript includes a related-software table with cross-ecosystem comparators, reference-choice boundaries, StatsPAI contribution/boundary language, empirical-comparison pointers, and explicit non-supersession/T3/T4/licensing limits; missing_related_tokens=[].
- PASS -- Monte Carlo content is framed as validation rather than a standalone simulation study: JSS discourages extensive simulation studies; the cover letter and active manuscript frame the Monte Carlo rows as validation artifacts and failure-mode guards, not as a new-estimator simulation campaign.
- PASS -- source-snapshot and final-release boundaries are explicit: active manuscript separates the audited upload archive from later tag/changelog/release-cut cleanup; snapshot_status=Audited source-snapshot submission archive; the failing final-publication release gate is a tag/changelog synchronization gate, not a JSS upload reproducibility failure.; version_consistent=True.
- PASS -- platform dependencies and RNG seeds are disclosed: reproduction_environment_audit records Docker/Python/R/Stata contracts and the cover letter discloses the no-R/no-Stata Tier-1 headline path; unseeded_rng=0.
- PASS -- cover letter numeric summary is synchronized with generated audit artifacts: cover-letter expected snippets=['52 pages', '24/24', '89-module R-parity', '85-module Stata bridge', '1,220 registered public functions', '1,220 public functions', '9,436 schema parameters', 'tagged 1.30.1 release', '13 PASS evidence cards', '5 suggested review routes', 'editor triage', 'statistical validation', 'quick reproduction', 'agent-interface review', 'limitations/release-boundary review']; missing=[]; package manifest absent; size not checked
- PASS -- cover letter PDF visual-check boundary is explicit: cover-letter PDF/manual-review snippets=['pdf_render_audit.{json,md}', 'representative PDF pages and an all-page machine scan', 'final full-document visual spot-check remains an upload-time manual action', '52-row page inventory', 'rather than a machine-verified PASS']; missing=[].
- PASS -- cover letter related-review and conflict disclosures are explicit: cover-letter related-review/COI snippets=['published in the *Journal of Open Source', 'doi.org/10.21105/joss.10604', 'cites the JOSS paper explicitly', 'disclosed explicitly to the editors', 'StatsPAI Inc.', 'CoPaper.AI', 'No external funder', 'MIT licence']; missing=[].
- PASS -- active manuscript tables and figures map to generators and prose: manuscript_artifact_audit maps active table/figure inputs to generators; artifacts=12; hash_mismatches=0; float_labels=21; missing_refs=0; dangling_refs=0; compact_sections=10/10; compact_missing_anchors=0.
- PENDING -- JSS attachment size and archive source set are bounded: submission archive has not been built in this tree yet.
- PENDING -- ASCII source/data contract is enforced inside the archive: submission archive has not been built in this tree yet.

Failures: none

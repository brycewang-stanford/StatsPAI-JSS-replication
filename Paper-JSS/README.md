# StatsPAI JSS Reviewer Quick Start

This directory contains the JSS manuscript, deterministic replication scripts, and the validation audit for the StatsPAI paper.

## JOSS boundary

The root `paper.md`, `paper.bib`, and the two root documentation files
whose names begin with `docs/joss_` are the archived materials of the
published JOSS article (Wang and Rozelle, 2026, *Journal of Open Source
Software* 11(125), 10604, <https://doi.org/10.21105/joss.10604>; review
thread openjournals/joss-reviews#10604). JSS work must not rewrite those
files or require a JSS boundary paragraph inside `paper.md`; corrections
to the published JOSS text go through the JOSS erratum process. JSS
claims should be scoped through this directory, the repository-root
`../docs/jss_source_audit_dossier.md` dossier (packaged as
`docs/jss_source_audit_dossier.md` in the archive), the JSS cover letter,
and the generated submission archive.

## Fast Review Path

From the repository root:

```bash
cd Paper-JSS
make reproduce-jss PYTHON=../.venv/bin/python
make audit PYTHON=../.venv/bin/python
```

The first command rebuilds the paper examples, figures, supplemental tables, compact-main PDF, citation verifier, and `replication/results/source_snapshot_manifest.{json,md}`. The second command reads the committed validation artifacts and writes `replication/results/jss_full_audit.{json,md}`, `replication/results/validation_evidence_audit.{json,md}`, `replication/results/methodological_gap_ledger.{json,md}`, `replication/results/stata_bridge_audit.{json,md}`, `replication/results/stata_rerun_protocol.{json,md}`, `replication/results/data_provenance_audit.{json,md}`, `replication/results/bibliography_metadata_audit.{json,md}`, `replication/results/agent_interface_audit.{json,md}`, `replication/results/agent_benchmark_protocol.{json,md}`, `replication/results/experiment_triage.{json,md}`, `replication/results/release_boundary_audit.{json,md}`, `replication/results/reproduction_environment_audit.{json,md}`, `replication/results/pdf_render_audit.{json,md}`, and `replication/results/pdf_visual_check_protocol.{json,md}`. If `build/statspai-jss-submission.zip` and its manifest already exist, `make audit` also refreshes `replication/results/submission_risk_ledger.{json,md}`, `replication/results/reviewer_evidence_map.{json,md}`, and `replication/results/editor_screening_checklist.{json,md}` after the source-snapshot and release-boundary checks, so the aggregate audit summary does not read stale upload/readability ledgers.

`make reproduce-jss` rebuilds the authoritative LaTeX/PDF manuscript. If
Pandoc is not installed, the Makefile skips only the local convenience
`manuscript/main.md` export, which is excluded from the JSS submission
archive.

## Single-Script Replication Tiers

The standalone driver makes external-language dependencies explicit:

```bash
cd Paper-JSS
../.venv/bin/python replication/reproduce.py --tier 1
../.venv/bin/python replication/reproduce.py --tier 1 \
  --transcript replication/results/reproduce_tier1_output.txt
../.venv/bin/python replication/reproduce.py --tier 2
../.venv/bin/python replication/reproduce.py --tier 3
STATA_EXE=/path/to/stata-mp ../.venv/bin/python replication/reproduce.py --tier 3
```

- Tier 1 needs Python only. It rebuilds the worked examples, figures, Track-A parity rollup, Track-C performance table/figure, supplemental tables, registry inventory, citation verifier, agent-interface audit, release-boundary audit, reproduction-environment audit, manuscript-artifact audit, and Python-side validation guards. The audited transcript target writes `replication/results/reproduce_tier1_output.txt`; the current transcript reports 24/24 steps passed (the added step executes every manuscript code listing verbatim), states that every Section 4-7 headline number was rebuilt without R or Stata, and ends with `RESULT: OK -- all required steps reproduced.` The reproduction-environment audit also inspects `tier1()` and fails if it contains live R/Stata dependency markers.
- Tier 2 additionally needs R and the packages pinned in `tests/r_parity/renv.lock`; it re-runs R reference checks on the committed CSV bytes. The reproduction-environment audit now requires the R reproducibility report to contain 89/89 reproduced modules and zero non-reproduced rows.
- Tier 3 additionally needs a Stata license; it re-runs the Stata bridge do-files when `STATA_EXE` names a local Stata executable or Stata is available on `PATH`. If no Stata executable is available, the tier records a documented optional-runtime skip; that skip is not evidence of a live Stata rerun. No main paper headline number depends on a paid Stata license, and the JSS upload evidence for this leg is the committed Stata JSON/do/provenance bundle plus `replication/results/stata_bridge_audit.md`. The generated `replication/results/stata_rerun_protocol.{json,md}` gives licensed reviewers the exact rerun commands, checklist, and drift-interpretation boundary without making missing Stata a JSS upload blocker or claiming a fresh live rerun on this machine.

## Submission Archive

```bash
cd Paper-JSS
make submission-ready PYTHON=../.venv/bin/python
```

This audited packaging target runs `reproduce-jss-full` and then rebuilds `build/statspai-jss-submission.zip`, so the archive contains the latest audit, reproduction, source-snapshot, evidence-map, PDF-review, and Tier-1 transcript artifacts. It excludes repository metadata, caches, prior build products, local notes, active external-review artifacts, and historical or inactive manuscript drafts, leaving one authoritative English manuscript and reviewer package. The current package is 24.21 MiB (25.38 MB decimal) with 2,800 files, including 483 registry evidence files referenced by validation notes. Use `make submission-package` only when the audit artifacts are already current and you need a quick zip refresh.

The generated root `README.md` inside the zip is a JSS-only release
entry point. It routes reviewers to `Paper-JSS/README.md`, the manuscript
PDF, the cover letter, and the source-audit dossier, and it now includes the
minimal extracted-archive check:

```bash
cd Paper-JSS
make reproduce-jss PYTHON=../.venv/bin/python
make audit PYTHON=../.venv/bin/python
```

`replication/scripts/verify_submission_package.py` also checks the JSS formalities that are easiest to miss at upload time: the archive must contain `LICENSE` and `pyproject.toml`, `pyproject.toml` must declare `license = "MIT"`, and the cover letter must state that the MIT licence is GPL-compatible.

It also verifies the reproduction environment advertised in the cover letter: `replication/Dockerfile`, `requirements-jss.txt`, `replication/reproduce.py`, the Tier-1 transcript, the R `renv.lock`, and `tests/stata_parity/STATA_ENVIRONMENT.md` must all be present and internally coherent. The audit parses the R and Stata reproducibility reports and requires complete 89/89 R-module and 85/85 frozen Stata-module reproduction ledgers with zero non-reproduced rows. The Dockerfile copies `src/`, `scripts/`, `tests/`, `docs/`, and `Paper-JSS/`, then defaults to `make reproduce-jss-full`.

## Data Provenance Audit

The data provenance audit classifies prospective JSS archive data/result members with the same include/exclude rules as `jss_submission_package.py` and excludes `data_provenance_audit.json` from its own data counts. The current report covers 819 scoped data/result files and 336 CSV files: 9 packaged public dataset CSVs, 7 public original-data extract CSVs, 91 same-byte R/Stata fixture CSVs, and 229 reference fixture CSVs. It reports zero forbidden raw-data members, zero high-risk private/credential path hits, zero CSV parse failures, and zero unknown categories. This keeps original-data claims limited to public package extracts and documented public-data rows, keeps calibrated/synthetic fixtures separate from original-data extracts, and rejects raw binary/statistical data formats such as Stata, RDS, SAS, Excel, parquet, and feather files in the prospective archive.

```bash
cd Paper-JSS
make data-provenance-audit PYTHON=../.venv/bin/python
```

## Bibliography Metadata Audit

The bibliography metadata audit parses the active LaTeX input graph rooted at `manuscript/main.tex`, checks it against the submission BibTeX file, and keeps the archival bibliography separated from the upload-facing references. The current report covers 70 active cited keys, 71 submission BibTeX entries, 58 archival entries, 58 DOI-bearing entries, one intentionally reserved submission entry, and thirteen no-DOI entries with manual verification reasons. It fails on missing active citations, archival-only active citations, duplicate keys, missing required BibTeX fields, stale compiled `.bbl` counts, or undocumented no-DOI entries.

That audit is offline and checks the *shape* of the bibliography; it cannot tell whether a DOI resolves to the paper the entry describes. `replication/scripts/verify_bib_against_crossref.py` does that against the live Crossref and DataCite registries, comparing title, first author, year (print or online) and container title for every DOI-bearing entry, and writes `replication/results/bibliography_registry_check.json`. It is deliberately **not** part of `make audit`: the audit chain must run offline and deterministically for a reviewer with no network. Run it by hand before submission and after adding any reference.

```bash
cd Paper-JSS
make bibliography-metadata-audit PYTHON=../.venv/bin/python
```

## Submission Risk Ledger

The generated ledger below separates JSS upload blockers from final
tagged-cut pending items. It must report zero JSS upload blockers while
still listing the nonblocking final-release work left by the current
source-snapshot cut, such as committing accepted edits, finalizing the
changelog, tagging the exact source commit, and rerunning
`make submission-ready` after the tag. The ledger also records the
expected final tagged-cut check ids, so a future refresh cannot silently
replace one pending release-cut item while preserving only the same
count. It also repeats the source-snapshot blocker breakdown by status
and bucket, so final-cut cleanup is actionable rather than only a total
path count. It also prints an ordered final tagged-cut runbook from the
same source-snapshot requirements, including the strict release guard
command, so post-acceptance cleanup is reproducible rather than only
described as a paragraph. Its documented nonblocking risks likewise use stable ids
covering the final cut, registry breadth denominator, licensed Stata
reruns, the methodological/T4 disclosure, compact-text terseness with
PDF-visible evidence routing, page-inventory navigation, and the final
manual PDF visual-check protocol, and the mechanical and contractual
agent-interface boundary.

```bash
cd Paper-JSS
make submission-risk-ledger PYTHON=../.venv/bin/python
```

`replication/results/submission_risk_ledger.{json,md}` is regenerated
during `make submission-ready` after an initial archive build and before
the final zip is written, so the submitted archive contains the ledger
for the exact files it packages. The final archive verifier fails if the
ledger reports any JSS upload blocker, if active JOSS artifacts appear
inside the JSS archive, or if dormant full-section manuscript drafts are
accidentally packaged. It also rejects stale final tagged-cut identity
metadata, stale final tagged-cut runbook metadata, or stale
documented-risk identity metadata in either the
packaged Markdown ledger or JSON ledger.
When an audited archive already exists, `make audit` refreshes this
ledger after the source-snapshot and release-boundary checks before
summarizing it in `jss_full_audit.md`.

## Reviewer Evidence Map

The generated reviewer evidence map is a compact navigation layer for
the current compact submission. It maps likely review questions to the exact
audit artifacts and gates that answer them: validation scope, fast
headline reproduction, R/Stata comparison limits, active table/figure
provenance, worked-example scope, experiment triage, archive boundary,
related-review and COI boundary, source installability, mechanical and
contractual agent-interface claims, limitations crosswalk, maintenance
and sustainability, and final tagged-cut cleanup. When a boundary
answer depends on reviewer-visible text, the map points to the rendered
PDF as primary evidence rather than only to the TeX source.
It also prints five suggested review routes -- editor triage,
statistical validation, quick reproduction, agent-interface review, and
limitations/release-boundary review -- so a reviewer can start from the
task they are trying to resolve rather than reading the evidence ledger
linearly.

```bash
cd Paper-JSS
make reviewer-evidence-map PYTHON=../.venv/bin/python
```

`replication/results/reviewer_evidence_map.{json,md}` must report the
thirteen expected PASS cards, five suggested review routes, zero failed
cards, zero failed routes, and zero JSS upload blockers. The final
archive verifier fails if this map is missing, has a stale card or route
identity/order, is stale relative to the submission-risk ledger, absent
from `jss_full_audit.md`, omits the PDF-visible boundary or Poppler
render metrics from the software-installability card, omits the
machine-render-versus-human-visual-check boundary or PDF visual-check
protocol, or points any primary-evidence path outside the submitted archive. The map covers
validation scope, fast headline reproduction, R/Stata comparison limits,
active table/figure provenance, worked-example scope, experiment triage,
archive boundary, related-review and COI boundary, source installability,
mechanical and contractual agent-interface claims, limitations crosswalk,
maintenance and sustainability, and final tagged-cut cleanup. The
final-cut card must also expose the six nonblocking risk details from
the submission-risk ledger -- risk id, evidence, and next action -- and
the Markdown map prints the same generated table for reviewers. When a
submission zip already exists, the map generator also records how many
primary evidence paths resolve inside that zip, so `make audit` catches
a stale reviewer-navigation path before the final package verifier runs.
The Markdown tables also expose each route/card id and status so the
human-readable map can be compared directly with the machine-readable
route and card contracts.
The final archive verifier also checks that
`REVIEWER-HARDENING-AUDIT.md` keeps the seven hard-reviewer risk titles
numbered in order, so this dossier cannot silently drop or renumber a
known objection while still passing package verification.

## Editor Screening Checklist

The generated editor screening checklist is a compact first-pass upload
packet for JSS editors. It routes the common initial checks -- JSS PDF
form, license and citation metadata, source installability, short
reproduction path, archive size and scope, related-review and conflict
disclosures, reviewer evidence navigation, final-release boundary,
nonblocking-risk crosswalk, artifact provenance, and platform/RNG
dependencies -- to the generated audit artifacts that document each
item.

```bash
cd Paper-JSS
make editor-screening-checklist PYTHON=../.venv/bin/python
```

`replication/results/editor_screening_checklist.{json,md}` must report
the eleven expected PASS items, zero failed items, zero JSS upload
blockers, and archive-resolved primary evidence paths. The PDF item must
point to both the Poppler render audit and the PDF visual-check protocol,
with `claimed_manual_acceptance=False` until the upload-time human review
is actually performed. The final archive
verifier fails if this checklist is missing, if its item identity/order
drifts, if any editor-screening item fails, if it is stale relative to
the submission-risk ledger or reviewer evidence map, if it loses the
manual visual spot-check boundary for the PDF item, or if
`jss_full_audit.md` does not summarize it as PASS.

## Manuscript Artifact Audit

The active compact PDF intentionally excludes the long-form draft sections, so the reviewer-facing artifact audit parses `manuscript/main.tex`, follows the ten active section inputs (nine compact sections plus Appendix A), and verifies that every external table and figure used by the active manuscript has a generator and source artifact. It currently checks the Track-A compact snapshot, Track-B Monte Carlo table, Track-C performance table, deterministic MCP trace table, and Track-C log-log figure, with byte-level hash guards for copied generated artifacts. It also enumerates all active table/figure labels, including labels inside generated table inputs, and fails if any lacks a narrative reference or if prose points to an inactive float. The same audit guards the seven-worked-example claim against drift in scripts, mentions, and active subsection labels. To keep the compact manuscript from becoming too terse, it also checks all ten active sections for contribution, evidence, and boundary anchors, and reports `Compact section coverage: 10/10` with zero missing anchors.

```bash
cd Paper-JSS
make manuscript-artifact-audit PYTHON=../.venv/bin/python
```

## PDF Render Audit

The formal audit extracts text from `manuscript/main.pdf` (the active PDF is 52 pages); the render audit adds a visual sanity guard. It renders the first, second, middle,
and last pages with Poppler `pdftoppm`, then scans all 52 PDF pages with
the same raster dimension and blank/dark-page thresholds. The generated
`replication/results/pdf_render_audit.{json,md}` records both the
sampled-page metrics and the full-document machine scan (`52/52` pages,
`0` failures). It also records that the final full-document human visual
spot-check is still an upload-time manual action and is not certified by
the machine render audit. The final package verifier rejects an archive
whose render audit is missing, stale against the packaged PDF page count,
reports any non-passing sampled or full-document page, or loses this
manual-check boundary.

```bash
cd Paper-JSS
make pdf-render-audit PYTHON=../.venv/bin/python
```

## PDF Visual Check Protocol

The visual-check protocol turns the upload-time human review into a
concrete checklist without recording a false machine pass. It reads the
active `manuscript/main.pdf` and `pdf_render_audit.json`, writes
`replication/results/pdf_visual_check_protocol.{json,md}`, and requires
`manual_visual_check_status=PENDING_MANUAL_REVIEW`,
`claimed_manual_acceptance=False`, and
`recorded_by_this_protocol=False`. The protocol now also extracts a
34-row page inventory from the active PDF, marking front matter,
section starts, table/figure/listing pages, references, and boundary-text
pages so the final human reviewer can navigate the compact paper without
guessing. The protocol lists the pages and objects that must be
inspected in the final archive PDF before JSS upload, including
validation-tier, source-snapshot, data-provenance, agent-claim, and final
manual PDF visual-check boundary wording; it does not certify that this
human review has already been completed. The final package verifier
rejects a package if this inventory does not cover every PDF page, loses
the major section/reference markers, or silently drops the inventory
checklist item.

```bash
cd Paper-JSS
make pdf-visual-check-protocol PYTHON=../.venv/bin/python
```

## Licensed Stata Tier-3 Rerun Protocol

The Stata bridge remains optional because a live rerun requires a
separate Stata license. The generated rerun protocol reads the frozen
Stata bridge audit, reproduction-environment audit, Stata environment
note, verifier script, and Stata reproducibility report, then writes
`replication/results/stata_rerun_protocol.{json,md}`. It must report
81 expected Stata modules, 81 reproduced report rows, zero
non-reproduced rows, `requires_stata_license=True`,
`jss_upload_blocking=False`, and
`claimed_current_machine_live_rerun=False`.

```bash
cd Paper-JSS
make stata-rerun-protocol PYTHON=../.venv/bin/python
```

## JSS Formal Compliance Audit

The aggregate checklist below maps the official JSS submission, author, style, and step-by-step guide requirements to local evidence: JSS-style PDF, PDF-visible validation/source/data/agent boundary text, rendered PDF page-sample sanity checks, source package, GPL-compatible license disclosure, citation metadata, standalone replication script, short reviewer transcript below one hour, discussion of comparable implementations and scope, source-snapshot versus final-release boundary disclosure, platform dependencies, RNG seeding, cover-letter numeric consistency, related-review and conflict disclosures, active manuscript artifact provenance, ASCII archive contract, and the 50 MB upload limit.

```bash
cd Paper-JSS
make jss-formal-compliance-audit PYTHON=../.venv/bin/python
```

## Methodological/T4 Track A Ledger

Track A rows with methodological/T4 tolerances or convention/identification disclosures are not treated as strict parity wins. The generated ledger below classifies each such row and fails if a new one is left uncategorized:

```bash
cd Paper-JSS
make gap-ledger PYTHON=../.venv/bin/python
```

## Stata Bridge Audit

Stata rows are frozen migration evidence because re-running them requires a paid Stata license. The audit below does not call Stata; it verifies that all 85 committed Stata JSONs have matching do-files, provenance, reproducibility-report rows, and R-side references, including the `50_xtabond` Arellano-Bond row through `plm::pgmm`. The `38_drdid` bridge is materialized from the canonical `drdid ... drimp` Stata command, `08_dml`, `18_augsynth`, `19_gsynth`, `31_dfl`, `32_rif`, `53_cr2`, `54_twoway_cluster`, and `56_multiway_cluster` are audited Stata/Mata algorithm bridges, `52_scm_unique` has an exact Stata `synth` bridge for the identified SCM fixture, and `54`/`56` retain `reghdfe` multiway-cluster SEs as diagnostic convention rows:

```bash
cd Paper-JSS
make stata-bridge-audit PYTHON=../.venv/bin/python
make stata-rerun-protocol PYTHON=../.venv/bin/python
```

## Agent Interface Audit

The JSS paper treats the agent-facing contribution as a mechanical and contractual schema/MCP/citation/result-handle interface, not as evidence that autonomous LLM agents make better empirical choices. The audit below verifies the deterministic MCP trace, live schema counts, citation keys resolved through `paper.bib`, and manuscript boundary wording so this claim cannot drift into behavioral overreach:

```bash
cd Paper-JSS
make agent-interface-audit PYTHON=../.venv/bin/python
make agent-benchmark-protocol PYTHON=../.venv/bin/python
```

`replication/results/agent_benchmark_protocol.{json,md}` is a deferred
benchmark protocol, not a completed behavioural result. It records the
matched arms, task families, scoring dimensions, leakage controls, and
minimum report items required for a later agent-behaviour study, while
marking that study as nonblocking for this JSS source-snapshot upload.

## Release Readiness

The archive describes the tagged 1.30.1 release (PyPI wheel and git tag v1.30.1). `replication/results/source_snapshot_manifest.{json,md}` reports package/source/schema versions, tags at HEAD, dirty-path counts, whether the top `[Unreleased]` changelog section is still populated, and the final-publication gate. The manifest includes a structured checklist for the release cut: hand-edited worktree blockers, package tag at `HEAD`, version consistency, finalized changelog, finalized package source paths, and finalized Paper-JSS paths.

```bash
cd Paper-JSS
make release-audit PYTHON=../.venv/bin/python
```

`replication/results/source_snapshot_manifest.{json,md}` is the authoritative version/tag/changelog ledger; the release-boundary audit checks that the manuscript's versioned release claim matches the built tree.

The release-boundary audit below fails if the manuscript's release claim drifts from the built tree or if stale pre-release snapshot framing reappears:

```bash
cd Paper-JSS
make release-boundary-audit PYTHON=../.venv/bin/python
```

## Reproduction Environment Audit

The Dockerfile, requirements file, and reviewer quick-start commands are
part of the reviewer contract. This audit checks that the Dockerfile
installs `requirements-jss.txt` and Poppler `poppler-utils`, copies the
source, scripts, tests, docs, and paper tree needed for
`make reproduce-jss-full`, that the
requirements include the core Python packages used by the manuscript
build and audit tests, including Pillow for the PDF render audit, that
the Tier-1 reviewer transcript is present
and complete, that the transcript shows the Section 4-7 headline path
ran without R or Stata, that the tiered reproduction driver preserves
the Python-only / R / Stata dependency boundary, and that the
reviewer-facing commands in this README and `manuscript/README.md`
remain synchronized with the Makefile and package verifier:

```bash
cd Paper-JSS
make reproduction-environment-audit PYTHON=../.venv/bin/python
```

## JSS Style Guard

The active manuscript uses `\documentclass[article]{jss}`, matching the JSS article template. The guard below fails if the manuscript drifts back to `nojss` vignette mode, drops required JSS front matter, or loses its `\bibliography{jss-bib}` hook:

```bash
cd Paper-JSS
make jss-style PYTHON=../.venv/bin/python
```

## Manuscript Length

`manuscript/main.tex` now compiles compact submission-facing versions of the introduction, architecture, agent API, worked-example, validation, computational-detail, and discussion sections. The longer source notes remain in `manuscript/sections/` for auditability, but they are not printed in the active 52-page PDF. The one printed appendix is the complete 89-module Track A ledger (Appendix A, generated by `replication/scripts/gen_appendix_parity.py`); the remaining detailed tables are generated and shipped as supplemental artifacts rather than printed in the main manuscript.

## What "Validated" Means Here

The paper uses "validated" as a registry evidence tier, not as a blanket claim about all exported helpers. The full audit currently reports 556 certified/validated symbols and 568 stable auto-registered symbols that remain API-stable but not parity-backed; the hand-written stable API surface now has zero unbacked entries because API-only helpers carry unit-contract evidence while remaining `api_stable`. In the live registry, the status counts are 414 `certified`, 142 `validated`, 661 `api_stable`, and 3 `experimental`. The full audit also decomposes the 641-symbol API-stable denominator into class-like/function-like and category counts, so the breadth claim stays auditable rather than becoming an unqualified validation claim. `replication/scripts/validation_evidence_audit.py` fails if any certified/validated symbol lacks registry-attached evidence notes, if a certified symbol lacks attached R/Stata parity-module evidence, or if a validated symbol is backed only by unit/regression tests. `scripts/stability_audit.py --check` fails if any hand-written stable API entry lacks attached evidence. `replication/scripts/validate_claims.py` fails if the active manuscript, cover letter, README, or stability guide drifts back to a blanket "Validated" claim. See `docs/guides/stability.md` and `Paper-JSS/REVIEWER-HARDENING-AUDIT.md`.

PYTHON ?= python3
LATEXMK ?= latexmk
PANDOC ?= pandoc
# manuscript/jss-bib.bib is DERIVED from the StatsPAI master paper.bib (StatsPAI
# CLAUDE.md section 10) by StatsPAI's tools/bib_subset.py; never hand-edit it.
# Regeneration needs a StatsPAI checkout: point STATSPAI_ROOT at it (default:
# this repo nested under StatsPAI/Paper-JSS). A standalone checkout ships the
# derived file as-is and the bib targets skip.
STATSPAI_ROOT ?= $(abspath ..)
BIB_TOOL ?= $(STATSPAI_ROOT)/tools/bib_subset.py
BIB_MASTER ?= $(STATSPAI_ROOT)/paper.bib
BIB_KEEP ?= brown2020language rios2022csdid
TEXLIVE_BIN ?= /usr/local/texlive/2024/bin/universal-darwin
STATSPAI_SRC ?= $(abspath ../src)
REPRO_TRANSCRIPT ?= replication/results/reproduce_tier1_output.txt
SOURCE_DATE_EPOCH ?= 1780185600
FORCE_SOURCE_DATE ?= 1
PATH := $(if $(wildcard $(TEXLIVE_BIN)),$(TEXLIVE_BIN):$(PATH),$(PATH))
PYTHONPATH := $(if $(wildcard $(STATSPAI_SRC)/statspai),$(STATSPAI_SRC):$(PYTHONPATH),$(PYTHONPATH))
export PYTHONPATH
export SOURCE_DATE_EPOCH FORCE_SOURCE_DATE

.PHONY: orig-parity-data headline-numbers-check appendices-check all reproduce-jss reproduce-jss-fast reproduce-jss-full reproduce-tier1 reproduce-tier1-transcript reproduce-tier2 reproduce-tier3 notebooks notebooks-execute replication figures appendices inventory performance-artifacts manuscript manuscript-claims manuscript-claims-check track-b-tables track-b-tables-check forest-seed-table forest-seed-table-check markdown pdf bib-split bib-split-check verify listings-execute-audit jss-style bibliography-metadata-audit jss-house-style-audit snapshot release-audit release-boundary-audit reproduction-environment-audit manuscript-artifact-audit data-provenance-audit pdf-render-audit pdf-visual-check-protocol jss-formal-compliance-audit validation-evidence gap-ledger stata-bridge-audit stata-rerun-protocol agent-interface-audit agent-benchmark-protocol experiment-triage submission-risk-ledger reviewer-evidence-map editor-screening-checklist audit submission-package verify-submission-package submission-ready arxiv clean

all: replication figures appendices inventory performance-artifacts manuscript verify snapshot

reproduce-jss: replication figures appendices inventory performance-artifacts pdf verify snapshot

reproduce-jss-fast: reproduce-jss

# Three-tier standalone driver (see replication/reproduce.py). Tier 1 needs
# neither R nor Stata and rebuilds every Section 4-7 headline number.
reproduce-tier1:
	$(PYTHON) replication/reproduce.py --tier 1

reproduce-tier1-transcript:
	$(PYTHON) replication/reproduce.py --tier 1 --transcript $(REPRO_TRANSCRIPT)

reproduce-tier2:
	$(PYTHON) replication/reproduce.py --tier 2

reproduce-tier3:
	$(PYTHON) replication/reproduce.py --tier 3

reproduce-jss-full: reproduce-jss reproduce-tier1-transcript audit

# Tier-B replication notebooks (one-click reviewer reproduction).
# `notebooks` regenerates the .ipynb from the single-source-of-truth builder;
# `notebooks-execute` runs them headless (drift guard) without rewriting them.
notebooks:
	$(PYTHON) ../scripts/build_replication_notebooks.py

notebooks-execute:
	cd .. && $(PYTHON) -m pytest tests/test_replication_notebooks.py -q --no-cov

replication:
	@set -e; \
	for script in replication/scripts/ex0*.py; do \
		echo "== $$script"; \
		$(PYTHON) "$$script"; \
	done

figures:
	$(PYTHON) replication/scripts/generate_figures.py

# The parity appendix is rendered rather than copied: the copy carried
# compare.py's own caption, which named a release and a module count the
# tree had long since moved past. gen_appendix_parity.py keeps the data
# rows generated and puts the caption on the same macros the body uses.
appendices:
	$(PYTHON) ../tests/r_parity/compare.py
	$(PYTHON) replication/scripts/gen_appendix_parity.py
	$(PYTHON) replication/scripts/gen_appendix_A.py
	$(PYTHON) replication/scripts/gen_appendix_C.py

appendices-check:
	$(PYTHON) replication/scripts/gen_appendix_parity.py --check

inventory:
	$(PYTHON) replication/scripts/generate_inventory.py

performance-artifacts:
	$(PYTHON) ../tests/perf/compare_perf.py

manuscript: markdown pdf

manuscript-claims:
	$(PYTHON) replication/scripts/generate_manuscript_claims.py

manuscript-claims-check:
	$(PYTHON) replication/scripts/generate_manuscript_claims.py --check

track-b-tables:
	$(PYTHON) replication/scripts/generate_track_b_tables.py

track-b-tables-check:
	$(PYTHON) replication/scripts/generate_track_b_tables.py --check

headline-parity-table:
	$(PYTHON) replication/scripts/generate_headline_parity_table.py

forest-seed-table:
	$(PYTHON) replication/scripts/generate_forest_seed_table.py

forest-seed-table-check:
	$(PYTHON) replication/scripts/generate_forest_seed_table.py --check

headline-parity-table-check:
	$(PYTHON) replication/scripts/generate_headline_parity_table.py --check

markdown:
	@if command -v $(PANDOC) >/dev/null 2>&1; then \
		cd manuscript && $(PANDOC) main.tex -o main.md; \
	else \
		echo "SKIP -- $(PANDOC) not found; main.md is an excluded convenience export"; \
	fi

# Regenerate manuscript/jss-bib.bib from the repo-root master paper.bib before
# every PDF build: exactly the keys main.tex (and its \input files) cite, plus
# $(BIB_KEEP). A \cite of a key missing from the master fails loudly here
# instead of surfacing as a "?" in the PDF -- add the reference to paper.bib
# (verified per CLAUDE.md section 10) and rerun.
# Two derived files: jss-bib.bib (what main.tex compiles: cited + $(BIB_KEEP))
# and jss-bib-archival.bib (keys cited only by the non-compiled long-form
# sections; everything cited anywhere minus jss-bib.bib). verify_citations.py
# checks the union, so a \cite in an archival section still resolves.
BIB_SUBMISSION_ARGS = --master $(BIB_MASTER) --roots manuscript/main.tex --out manuscript/jss-bib.bib --keep $(BIB_KEEP)
BIB_ARCHIVAL_ARGS = --master $(BIB_MASTER) --roots manuscript/main.tex $(wildcard manuscript/sections/*.tex) --minus manuscript/jss-bib.bib --out manuscript/jss-bib-archival.bib

bib-split:
	@if [ -f $(BIB_TOOL) ]; then \
		$(PYTHON) $(BIB_TOOL) extract $(BIB_SUBMISSION_ARGS) && \
		$(PYTHON) $(BIB_TOOL) extract $(BIB_ARCHIVAL_ARGS); \
	else \
		echo "SKIP -- $(BIB_TOOL) not present (submission tarball); jss-bib.bib is the shipped derived copy"; \
	fi

bib-split-check:
	@if [ -f $(BIB_TOOL) ]; then \
		$(PYTHON) $(BIB_TOOL) check $(BIB_SUBMISSION_ARGS) && \
		$(PYTHON) $(BIB_TOOL) check $(BIB_ARCHIVAL_ARGS); \
	else \
		echo "SKIP -- $(BIB_TOOL) not present; cannot check bib drift"; \
	fi

# latexmk skips a rebuild when main.pdf is newer than its sources, so a
# PDF built by hand outside this Makefile (without SOURCE_DATE_EPOCH)
# survives `make pdf` untouched and carries the local build clock into
# the submission. tests/test_jss_release_manifest.py then fails with an
# opaque byte assertion; check it here instead, where the fix is obvious.
pdf: bib-split manuscript-claims track-b-tables headline-parity-table forest-seed-table
	cd manuscript && $(LATEXMK) -pdf -interaction=nonstopmode main.tex
	@$(PYTHON) -c "import re,sys;d=open('manuscript/main.pdf','rb').read();m=re.search(rb'/CreationDate \(([^)]*)\)',d);ok=m and m.group(1)==b'D:20260531000000Z';sys.exit(0) if ok else sys.exit('FAIL -- main.pdf carries a local build clock (%s); run: rm manuscript/main.pdf && make pdf' % (m.group(1).decode() if m else 'none'))"

# arXiv preprint: a derivative of main.tex (nojss masthead, preprint
# footnote, flat tree + .bbl), rebuilt from the same sources as `pdf`.
# Output lands in build/arxiv/; see replication/scripts/build_arxiv.py.
arxiv: bib-split manuscript-claims track-b-tables headline-parity-table forest-seed-table
	$(PYTHON) replication/scripts/build_arxiv.py

verify: jss-style headline-numbers-check manuscript-claims-check track-b-tables-check headline-parity-table-check forest-seed-table-check appendices-check bib-split-check bibliography-metadata-audit listings-execute-audit

headline-numbers-check:
	$(PYTHON) replication/scripts/check_headline_numbers.py

listings-execute-audit:
	$(PYTHON) replication/scripts/listings_execute_audit.py
	@$(PYTHON) replication/scripts/verify_citations.py

jss-style:
	$(PYTHON) replication/scripts/verify_jss_style.py

bibliography-metadata-audit:
	$(PYTHON) replication/scripts/bibliography_metadata_audit.py

jss-house-style-audit:
	$(PYTHON) replication/scripts/jss_house_style_audit.py

snapshot:
	$(PYTHON) replication/scripts/source_snapshot_manifest.py

release-audit:
	$(PYTHON) replication/scripts/source_snapshot_manifest.py --strict-release

release-boundary-audit:
	$(PYTHON) replication/scripts/release_boundary_audit.py

reproduction-environment-audit:
	$(PYTHON) replication/scripts/reproduction_environment_audit.py

manuscript-artifact-audit:
	$(PYTHON) replication/scripts/manuscript_artifact_audit.py

# The NHEFS original-data extract is gitignored in StatsPAI (it is a
# byte-for-byte dump of the bundled sp.datasets.nhefs() CSV), so a fresh
# clone does not have it until the Python side of the module runs. The
# provenance audit requires it, so regenerate it first (~5 s, byte-stable).
orig-parity-data:
	cd $(STATSPAI_ROOT) && $(PYTHON) tests/orig_parity/06_nhefs_ch12_ipw.py >/dev/null

data-provenance-audit: orig-parity-data
	$(PYTHON) replication/scripts/data_provenance_audit.py

pdf-render-audit:
	$(PYTHON) replication/scripts/pdf_render_audit.py

pdf-visual-check-protocol: pdf-render-audit
	$(PYTHON) replication/scripts/pdf_visual_check_protocol.py

jss-formal-compliance-audit: manuscript-artifact-audit snapshot pdf-visual-check-protocol
	$(PYTHON) replication/scripts/jss_formal_compliance_audit.py

validation-evidence:
	$(PYTHON) replication/scripts/validation_evidence_audit.py

gap-ledger:
	$(PYTHON) replication/scripts/methodological_gap_ledger.py

stata-bridge-audit:
	$(PYTHON) replication/scripts/stata_bridge_audit.py

stata-rerun-protocol: stata-bridge-audit reproduction-environment-audit
	$(PYTHON) replication/scripts/stata_rerun_protocol.py

agent-interface-audit:
	$(PYTHON) replication/scripts/agent_interface_audit.py

agent-benchmark-protocol:
	$(PYTHON) replication/scripts/agent_benchmark_protocol.py

experiment-triage: agent-benchmark-protocol
	$(PYTHON) replication/scripts/experiment_triage.py

submission-risk-ledger:
	$(PYTHON) replication/scripts/submission_risk_ledger.py

reviewer-evidence-map:
	$(PYTHON) replication/scripts/reviewer_evidence_map.py

editor-screening-checklist:
	$(PYTHON) replication/scripts/editor_screening_checklist.py

replacement-table:
	$(PYTHON) replication/scripts/build_replacement_table.py

replacement-table-check:
	$(PYTHON) replication/scripts/build_replacement_table.py --check

audit: orig-parity-data
	$(PYTHON) replication/scripts/jss_full_audit.py

submission-package: snapshot bibliography-metadata-audit pdf-visual-check-protocol stata-rerun-protocol data-provenance-audit
	$(PYTHON) replication/scripts/jss_submission_package.py

verify-submission-package: submission-package
	$(PYTHON) replication/scripts/jss_full_audit.py
	$(PYTHON) replication/scripts/submission_risk_ledger.py
	$(PYTHON) replication/scripts/reviewer_evidence_map.py
	$(PYTHON) replication/scripts/editor_screening_checklist.py
	$(PYTHON) replication/scripts/jss_submission_package.py
	$(PYTHON) replication/scripts/verify_submission_package.py

submission-ready: reproduce-jss-full
	$(PYTHON) replication/scripts/source_snapshot_manifest.py
	$(PYTHON) replication/scripts/bibliography_metadata_audit.py
	$(PYTHON) replication/scripts/jss_submission_package.py
	$(PYTHON) replication/scripts/jss_full_audit.py
	$(PYTHON) replication/scripts/submission_risk_ledger.py
	$(PYTHON) replication/scripts/reviewer_evidence_map.py
	$(PYTHON) replication/scripts/editor_screening_checklist.py
	$(PYTHON) replication/scripts/jss_submission_package.py
	$(PYTHON) replication/scripts/verify_submission_package.py

clean:
	cd manuscript && $(LATEXMK) -C main.tex || true
	rm -rf manuscript/tmp

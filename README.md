# StatsPAI-JSS-replication

Replication materials for

> Biaoyue Wang and Scott Rozelle. *StatsPAI: Validation-Tiered Python
> Workflows for Causal Inference.* Preprint, submitted to the *Journal of
> Statistical Software*.

This repository is a frozen snapshot of the replication package that
accompanies the manuscript. The package itself is developed at
<https://github.com/brycewang-stanford/StatsPAI>.

| | |
| --- | --- |
| StatsPAI version string | 1.30.1 |
| StatsPAI source commit | [`e91ecdf6b4`](https://github.com/brycewang-stanford/StatsPAI/commit/e91ecdf6b41404ebf39c88b07a02c2b3f88c8890) |
| Relation to release tag | `src/` contains changes committed after release tag `v1.30.1`; the PyPI 1.30.1 wheel is **not** identical to this snapshot |
| Manuscript sources commit | `891131a250` (private manuscript repository) |

`src/statspai/` here is the source at that commit, and `pip install -e .`
installs exactly it; use it rather than the PyPI wheel to reproduce the
paper.

## Contents

| Path | What it is |
| --- | --- |
| `Paper-JSS/manuscript/` | LaTeX source and PDF of the manuscript |
| `Paper-JSS/replication/reproduce.py` | single-script, three-tier replication driver |
| `Paper-JSS/replication/scripts/` | worked examples, figure/table generators, audits |
| `Paper-JSS/replication/results/` | committed outputs, incl. the Tier-1 transcript |
| `Paper-JSS/README.md` | full reviewer guide: every tier, audit, and artifact |
| `src/statspai/` | the StatsPAI source snapshot the paper describes |
| `tests/r_parity/`, `tests/stata_parity/` | same-byte R / Stata parity modules, CSV fixtures, golden outputs |
| `tests/reference_parity/`, `tests/external_parity/`, `tests/coverage_monte_carlo/`, `tests/perf/` | known-truth recovery, published-number, Monte Carlo coverage, and performance evidence |

## Quick start (Python only, no R or Stata)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r Paper-JSS/requirements-jss.txt
pip install -e .
cd Paper-JSS
python replication/reproduce.py --tier 1
```

Tier 1 rebuilds every headline table and figure of Sections 4-7 from
Python alone; the committed transcript
(`Paper-JSS/replication/results/reproduce_tier1_output.txt`) shows the
expected output. Tier 2 (`--tier 2`) additionally re-runs the R references
(packages pinned in `tests/r_parity/renv.lock`); Tier 3 (`--tier 3`) re-runs
the Stata bridges and needs a Stata licence. See `Paper-JSS/README.md` for
details.

## Notes

* Machine-specific absolute paths in generated audit files have been
  replaced by `<STATSPAI_ROOT>` or `~`.
* Documents addressed to the journal editors (cover letter and related
  submission disclosures) are not part of this public snapshot; a few
  files in `Paper-JSS/` still mention them by name.
* Software is released under the MIT licence (`LICENSE`).

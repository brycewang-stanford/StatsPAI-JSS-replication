# Track A Methodological-Gap Ledger

Status: PASS
Source: `tests/r_parity/results/parity_table_3way.md`
Methodological/T4 rows: 1
Uncategorized gaps: 0

These rows are methodological/T4 Track A disclosures, not strict cross-language equality passes.
Each row must have an explicit reviewer-risk classification and a concrete
promotion path before the paper can describe it as deterministic T2 evidence.

| Module | Category | Required metadata | Non-circular native guard | Reference disagreement guard | Reviewer risk | Next action |
|---|---|---|---|---|---|---|
| `07_scm` | `classical_scm_reference_disagreement` | validation_tier=`identification_dependent_native`; reference_backend=`Synth`; solver_best_start=`dirichlet_3`; solver_near_best_start_count=`4`; solver_near_best_weight_class_count=`2`; solver_near_best_weight_l1_max=`0.00513`; weight_solution_nonunique=`True` | tests/r_parity/52_scm_unique.py::unique convex-hull SCM (module 52 certifies the native classical-SCM solver on a uniquely identified convex-hull DGP) | avg_post_gap: py-Stata rel=0.000417 (max 0.001); R-Stata rel=0.023 (min 0.01); native tracks Stata synth on the same ADH special-predictor spec, while R Synth and Stata synth choose measurably different local optima | Basque donor weights are not uniquely identified; R Synth and Stata synth choose measurably different optima, so native-vs-Synth equality is the wrong claim. | Keep the native Basque row as a T4 disclosure with deterministic multi-start diagnostics; use module 52_scm_unique and backend='synth' to separate solver correctness from exact Synth-number reproduction. |

# Reproduction Environment Audit

Status: PASS

Scope: static checks for the Dockerfile, Python requirements, Makefile
targets, tiered reproduction driver, reviewer transcript, R lockfile,
Stata environment note, and deterministic random seeds in stochastic
paper-reproduction scripts.

Docker base image: python:3.12-slim
Python requirement packages: 23
Requirements source version comment: True
Makefile targets: 65
Reviewer README commands checked: 26
Manuscript README commands checked: 7
Optional Pandoc Markdown export: True
Tier-1 reviewer transcript present: True
Tier-1 reviewer transcript complete: True
Tier-1 transcript states no R/Stata headline path: True
Tier-1 live R/Stata dependency markers: 0
Stata live-rerun command documented: True
Stata missing-runtime skip documented: True
Stata verifier missing-runtime returns skip: True
R lockfile present: True
R environment note present: True
R reproducibility report present: True
R reproduced modules: 89/89
R non-reproduced rows: 0
Stata environment note present: True
Stata reproducibility report present: True
Stata reproduced modules: 85/85
Stata non-reproduced rows: 0
Stochastic reproduction files checked: 19
Seeded stochastic reproduction files: 19
Unseeded stochastic reproduction files: 0

Failures: none

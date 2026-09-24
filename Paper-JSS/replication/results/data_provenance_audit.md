# Data Provenance Audit

Status: PASS

Prospective JSS archive data/result members, using the same include/exclude rules as jss_submission_package.py. Generated data_provenance_audit.json is excluded from its own data counts.

## Summary

- Prospective archive files: `2869`
- Scoped data/result files: `842`
- CSV files: `344`
- JSON files: `497`
- Lockfiles: `1`
- Packaged public dataset CSVs: `9`
- Public original-data extract CSVs: `7`
- Same-byte R/Stata fixture CSVs: `91`
- Reference fixture CSVs: `237`
- Generated result JSON files: `333`
- Forbidden raw-data members: `0`
- High-risk private/credential path hits: `0`
- CSV parse failures: `0`
- Unknown categories: `0`

## Boundary

- Original-data claims are limited to public package extracts and documented public-data rows.
- Calibrated replicas and synthetic fixtures are classified separately from original-data extracts.
- The audit rejects raw binary/statistical data formats such as Stata, RDS, SAS, Excel, parquet, and feather files in the prospective archive.
- The audit rejects private, confidential, secret, credential, password, token, or proprietary path tokens in scoped data/result members.

## Category Counts

| Category | Count |
|---|---:|
| `environment_or_fixture_lock` | 2 |
| `generated_monte_carlo_result_json` | 3 |
| `generated_original_parity_result_json` | 25 |
| `generated_paper_audit_or_example_json` | 32 |
| `generated_performance_result_json` | 9 |
| `generated_r_parity_result_json` | 179 |
| `generated_stata_result_json` | 85 |
| `other_generated_or_schema_json` | 10 |
| `packaged_public_dataset_csv` | 9 |
| `public_original_extract_csv` | 7 |
| `reference_fixture_csv` | 237 |
| `reference_result_json` | 143 |
| `runtime_schema_bundle_json` | 5 |
| `same_byte_r_stata_fixture_csv` | 91 |
| `schema_bundle_json` | 5 |

## Public Source Rows

| Path | Category | Rows | Columns | Source note |
|---|---|---:|---:|---|
| `src/statspai/datasets/data/california_prop99.csv` | `packaged_public_dataset_csv` | 1209 | 7 | Public ADH California Proposition 99 panel bundled for exact paper replication when simulated=False. |
| `src/statspai/datasets/data/card_1995.csv` | `packaged_public_dataset_csv` | 3010 | 9 | Card (1995) NLSYM extract, matching the package data loader. |
| `src/statspai/datasets/data/castle_2013.csv` | `packaged_public_dataset_csv` | 550 | 29 | Cheng and Hoekstra (2013) castle-doctrine state panel, the dataset behind chapter 9 of Cunningham's Causal Inference: The Mixtape; loaded by sp.datasets.castle_doctrine(). |
| `src/statspai/datasets/data/lalonde_matchit.csv` | `packaged_public_dataset_csv` | 614 | 11 | Dehejia-Wahba/MatchIt Lalonde extract used by matching examples. |
| `src/statspai/datasets/data/lee_2008_senate.csv` | `packaged_public_dataset_csv` | 1390 | 2 | Public Lee-style RD Senate extract used for redistribution-safe RD. |
| `src/statspai/datasets/data/nhefs.csv` | `packaged_public_dataset_csv` | 1629 | 67 | Public NHEFS extract from the causaldata/What If g-methods canon. |
| `src/statspai/datasets/data/sasp_panel.csv` | `packaged_public_dataset_csv` | 1787 | 31 | Survey of Adult Service Providers session panel from Cunningham and Kendall's work, redistributed with Causal Inference: The Mixtape; loaded by sp.datasets.sasp_panel(). |
| `src/statspai/datasets/data/texas_prison.csv` | `packaged_public_dataset_csv` | 816 | 24 | Texas 1993 prison-capacity expansion panel used in chapter 10 of Causal Inference: The Mixtape; loaded by sp.datasets.texas_prison(). |
| `src/statspai/datasets/data/thornton_hiv.csv` | `packaged_public_dataset_csv` | 4820 | 17 | Thornton (2008) HIV-incentive experiment extract redistributed with Causal Inference: The Mixtape; loaded by sp.datasets.thornton_hiv(). |
| `tests/orig_parity/data/01_card_original.csv` | `public_original_extract_csv` | 3010 | 9 | R-package Card extract used for original-data parity. |
| `tests/orig_parity/data/02_mpdta_original.csv` | `public_original_extract_csv` | 2500 | 6 | did::mpdta extract used for original-data staggered-DiD parity. |
| `tests/orig_parity/data/03_basque_original.csv` | `public_original_extract_csv` | 731 | 17 | Synth::basque extract used for original-data SCM parity. |
| `tests/orig_parity/data/04_lalonde_original.csv` | `public_original_extract_csv` | 614 | 11 | Lalonde experimental extract used for original-data parity. |
| `tests/orig_parity/data/04b_nsw_psid_original.csv` | `public_original_extract_csv` | 2675 | 12 | NSW/PSID comparison extract used for observational matching parity. |
| `tests/orig_parity/data/05_lee_original.csv` | `public_original_extract_csv` | 1390 | 2 | rdrobust::RDsenate public extract used for RD parity. |
| `tests/orig_parity/data/06_nhefs_ch12_ipw.csv` | `public_original_extract_csv` | 1566 | 67 | NHEFS chapter-12 IPW extract used for g-methods parity. |

## Largest Data/Result Files

| Path | Bytes |
|---|---:|
| `src/statspai/schemas/functions.json` | 2015104 |
| `schemas/functions.json` | 2015104 |
| `src/statspai/schemas/agent_cards.json` | 1888635 |
| `schemas/agent_cards.json` | 1888635 |
| `tests/reference_parity/_fixtures/spatial_survey_R.json` | 1770980 |
| `tests/reference_parity/_fixtures/grf_family_R.json` | 1462468 |
| `src/statspai/schemas/tools.json` | 1218857 |
| `schemas/tools.json` | 1218857 |
| `tests/reference_parity/_fixtures/grf_family_stat_data.csv` | 1084216 |
| `tests/reference_parity/_fixtures/did_synth_scpi_R.json` | 835308 |

Failures: none

Machine-readable detail: `replication/results/data_provenance_audit.json`

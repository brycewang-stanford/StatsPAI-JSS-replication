# Validation Evidence Audit

Status: PASS
Registry symbols: 1627
Certified/validated symbols: 981 (certified=494, validated=487)
Missing validation notes: 0
Evidence path references: 1971 refs / 741 unique paths
Evidence path scope: certified/validated symbols only; the submission packager may include additional API-stable registry evidence files.
Missing evidence paths: 0
Certified without certified-grade evidence: 0
Validated without validated-grade evidence: 0
Supplemental-only certified/validated symbols: 0
Symbols with supplemental notes: 218
Symbols with limitations: 29

## Qualifying Evidence Note Kinds

- external_parity: 83 symbols (120 note instances)
- index_cross_language: 495 symbols (543 note instances)
- index_known_truth: 494 symbols (494 note instances)
- r_parity: 84 symbols (84 note instances)
- reference_parity: 325 symbols (559 note instances)
- stata_parity: 80 symbols (80 note instances)

## Supplemental Evidence Note Kinds

These notes are reported for transparency but do not, by themselves, satisfy a certified or validated status label.
- api_unit_contract: 200 symbols (238 note instances)
- coverage_mc: 2 symbols (2 note instances)
- documented_parity_gap: 1 symbols (1 note instances)
- other: 14 symbols (35 note instances)
- variant_certification: 3 symbols (3 note instances)

## Symbols With Scoped Limitations

These rows keep certified/validated evidence scoped rather than presenting blanket parity or validation claims.

| Symbol | Status | Status-grade evidence kinds | Limitation scope |
| --- | --- | --- | --- |
| `callaway_santanna` | certified | index_cross_language, r_parity, stata_parity | clustervars accepts a cluster that varies within unit only with panel=False (repeated cross-sections, as Stata csdid without ivar()); on a panel the influence functions are per unit |
| `causal_forest` | certified | index_cross_language, r_parity | The AIPW ATE/ATT are validated against grf on clean-overlap designs only; under severe propensity-overlap loss the AIPW influence function inflates the standard error (conservative, over-covering inference), so inspect the sp.audit overlap diagnostic before interpreting the ATE on that kind of sample; The forest is compared with grf only statistically, not bit-for-bit: the AIPW ATE/ATT by seed-replicated equivalence (T3, within 0.1 sampling SE at 500-8,000 trees), CATE RMSE, pointwise variances and coverage by a stochastic screen; given a fitted forest, the inference operators match grf / sandwich to 1e-14; Doubly-robust averages (average_treatment_effect, best_linear_projection, rate) are not implemented for fe= forests, which have no propensity score; use sp.did_forest for group-time averages; For fe= forests the calibration slope tests for heterogeneity only; it comes from a globally within-transformed regression and does not de-attenuate CATE predictions |
| `cevae` | validated | index_known_truth | no numerical evidence -- only API/unit tests; no known-truth or cross-package comparison in the parity index, and estimates depend on network initialisation, training schedule and seed. Treat intervals as unvalidated and report results across seeds |
| `cfrnet` | validated | index_known_truth | no numerical evidence -- only API/unit tests; no known-truth or cross-package comparison in the parity index, and estimates depend on network initialisation, training schedule and seed. Treat intervals as unvalidated and report results across seeds |
| `cgs_continuous_did` | certified | index_cross_language, r_parity | standard errors come from the per-cell influence function; contdid routes its own through the pte aggregation layer, which is not implemented here; staggered designs aggregate cells with StatsPAI's own treated-count weights; only the per-cell estimator is pinned against the reference; the cck (nonparametric) dose estimator is not implemented |
| `continuous_did` | certified | index_cross_language | method='cgs' is an MVP -- 2-period design, OR only, bootstrap SE; full CGS parity (cohort aggregation, DR/IPW, analytical IF variance) is on the roadmap (see docs/rfc/continuous_did_cgs.md). Other modes (twfe / att_gt / dose_response) are stable |
| `ddd_heterogeneous` | certified | index_cross_language, r_parity | the placebo joint test is only produced on the bootstrap path; se='analytic' reports None for it, because that test needs the joint covariance of the placebo arms rather than of the DDD; control_group='notyettreated' is only partially comparable to triplediff 0.2.4: its per-control-cohort estimates agree exactly, but the reference misindexes the influence functions it combines, so the combined numbers differ by convention on cells where the comparison does not span the whole panel; the aggregation convention differs from triplediff::agg_ddd(type='simple'): the default weights cohorts by treated-eligible units; pass weight_by='cohort' to match the R package |
| `deepiv` | validated | index_known_truth | no numerical evidence -- only API/unit tests; no known-truth or cross-package comparison in the parity index, and estimates depend on network initialisation, training schedule and seed. Treat intervals as unvalidated and report results across seeds |
| `did_balance` | validated | index_known_truth | pooled multi-cohort balance is not implemented: one table per treated cohort only, because the normalized difference is a two-group statistic; only the reliability-weight variance correction is implemented for the weighted panel; survey-design (replicate-weight) variances are not supported; inference is not implemented: the normalized difference is reported as a descriptive effect size with no standard error or test, by design; the weighted denominator convention differs from cobalt::col_w_smd, which holds the pooled SD at its unweighted value; this follows Baker et al. (2026) instead, and the two coincide when unweighted |
| `did_imputation` | certified | index_cross_language, r_parity, stata_parity | R/Stata parity is for the documented untreated-only TWFE and simple ATT aggregation convention only; event-study and SE rows are backend-specific diagnostics |
| `distributional_did` | certified | index_cross_language | reports point estimates and standard errors only; the reference runs no test here and neither does this; simultaneous (uniform) confidence bands over bins are not implemented; the standard errors are pointwise only, so reading several bins at once overstates joint confidence |
| `dml` | certified | index_cross_language, r_parity, stata_parity | external_predictions, store_oof, and observation_ids are Python-only and absent from JSON/MCP inputs; external records accept no dict, JSON string, or file path; store_oof=True retains individual-level records for get_oof() and get_residuals() in memory only; ordinary serialization omits them; Retained IRM needs at least 10 rows per treatment arm in each training fold or raises DataInsufficient instead of fallback; internal explicit fold_indices require n_rep=1, while external repeated IRM records are allowed when the explicit partition is equivalent for every repeat |
| `dragonnet` | validated | index_known_truth | no numerical evidence -- only API/unit tests; no known-truth or cross-package comparison in the parity index, and estimates depend on network initialisation, training schedule and seed. Treat intervals as unvalidated and report results across seeds |
| `etwfe` | certified | index_cross_language, r_parity, stata_parity | cgroup='nevertreated' combined with panel=False (repeated cross-sections) is not yet supported; pass either panel=True with cgroup='nevertreated' or panel=False with cgroup='notyet'; family='poisson'/'logit' with panel=False or weights= is not yet supported; these raise rather than being silently ignored; linear hettype= combined with fe='cohort', panel=False or weights= is not yet supported (the jwdid design absorbs unit effects); these raise; fe='cohort' with a categorical xvar keeps one period slope per level, while R etwfe 0.6.2 gives the levels a single summed period slope, so the numbers can differ (documented reference difference); response-scale SEs under fe='unit' use the profiled delta method; Stata jwdid's margins holds the absorbed effects fixed (documented convention difference, point estimates agree); family='poisson'/'logit' reports an average marginal effect on the response scale (counts / probability) rather than a link-scale coefficient -- the R etwfe::emfx convention; weights= is not yet supported together with xvar or with family='poisson'/'logit'; both combinations raise; cgroup='nevertreated' combined with panel=False (repeated cross-sections) is not yet supported. Use panel=True with cgroup='nevertreated' or panel=False with cgroup='notyet' |
| `factorial_design` | validated | index_known_truth | Mixed-level fractions only as columns of L18; other mixed-level orthogonal arrays are not implemented; Minimum-aberration search only up to about 15 factors in 32 runs or 12 in 64; beyond that generators= is required |
| `fect` | certified | index_cross_language, r_parity, stata_parity | Inference is resampling-only (unit bootstrap or jackknife on request); the default returns point estimates only; cv=True selects r / lam over random holdout folds, so the selection is reproducible only with a fixed random_state; cross-language parity covers only fits at a user-supplied r / lam (the selector is checked by per-fold score equality with fect and a stochastic screen of the selection, not an equivalence test) |
| `functional_form_test` | certified | index_cross_language, r_parity | a large p-value is only a failure to reject, not evidence FOR functional-form insensitivity: the test has little power with few units or coarse bins; standard errors and the critical value are asymptotic; a bootstrap variant is not implemented |
| `gnn_causal` | validated | index_known_truth | no numerical evidence -- only API/unit tests; no known-truth or cross-package comparison in the parity index, and estimates depend on network initialisation, training schedule and seed. Treat intervals as unvalidated and report results across seeds |
| `hal_tmle` | validated | index_known_truth | variant='projection' raises NotImplementedError -- the Riesz-projection targeting step from Li-Qiu-Wang-vdL (2025) §3.2 is not yet ported (the v1.11.x code path was a no-op on the point estimate; see CHANGELOG). The implementation roadmap and parity-test gates are in docs/rfc/hal_tmle_projection.md |
| `llm_dag_validate` | validated | index_known_truth | LLM output is a proposal, not evidence -- only a heuristic step: it is not reproducible across model versions or providers, has no numerical evidence, and must be checked against domain knowledge and data (e.g. sp.llm_dag_validate) before it constrains an analysis |
| `match` | certified | index_cross_language | greedy nearest-neighbour matching without replacement is order-dependent: the m_order convention can differ across packages and materially moves the estimate (>5x spread on MatchIt::lalonde with Mahalanobis distance). m_order='data' and 'closest' reproduce MatchIt exactly; m_order='farthest' is StatsPAI's own dynamic rule and is not MatchIt-equivalent; bias_correction=True follows a different convention from Matching::Match's BiasAdjust: StatsPAI regresses on the full covariate vector with unweighted OLS over all controls, the reference regresses on the matching variables weighted by match counts, so bias-corrected estimates can differ from it by about 0.1%. The uncorrected estimate and its Abadie-Imbens standard error are exact |
| `pretrends_equivalence` | validated | index_known_truth | the TOST is computed only when tost_threshold is supplied; there is no universal outcome-scale default, so it is not invented |
| `principal_strat` | certified | index_cross_language | Always-survivor SACE under encouragement design (Mealli & Pacini 2013, partial identification) is not yet implemented; only AIR / Wald LATE point estimates (τ_Y on outcome, τ_S on the post-treatment stratum) are reported when an instrument is supplied |
| `rddensity` | certified | index_cross_language, r_parity, stata_parity | Certified native reference-parity evidence covers the default rddensity::rddensity unrestricted triangular-kernel selector and test path on the JSS Lee/RD Senate fixture. Manual side-specific bandwidths follow an explicit user-control convention, not a reference-parity guarantee; backend='r' remains available when direct R package execution is required |
| `rdrobust` | certified | index_cross_language, r_parity, stata_parity | the weighted rbc bootstrap is not supported -- passing weights= with bootstrap='rbc' raises MethodIncompatibility; R-parity certification applies only to the configurations enumerated by sp.validation_scope(function='rdrobust') -- the default native mserd / triangular / p=1 / nn path (Track A 06), a manual bandwidth, and the weighted rows -- other selectors, kernels and vce choices are pinned for sp.rdbwselect or not at all for this entry point |
| `space_filling` | validated | index_known_truth | Qualitative factors only with method='maxpro' and without a constraint |
| `spillover_did` | certified | index_cross_language | there is no reference implementation, so this carries design-recovery evidence only and no cross-language parity; ring boundaries are the analyst's choice; there is no selector, and a too-wide outer ring silently contaminates the clean controls; covariate adjustment is not implemented |
| `synth` | certified | index_cross_language, r_parity, stata_parity | Classical SCM certification is specification-specific: ADH/Synth parity requires passing the same special_predictors recipe; the default outcome-only V=I path is a documented Kaul-style convention; Default native classical SCM can differ from Synth on Basque-style panels by a documented local-optimum convention (the outer V optimisation has multiple near-equivalent minima); use backend='synth' or canonical special_predictors when exact R parity is required |
| `tarnet` | validated | index_known_truth | no numerical evidence -- only API/unit tests; no known-truth or cross-package comparison in the parity index, and estimates depend on network initialisation, training schedule and seed. Treat intervals as unvalidated and report results across seeds |

## Validated-Tier Symbols

| Symbol | Status-grade evidence kinds | Evidence paths |
| --- | --- | --- |
| `BartikIV` | index_known_truth | tests/reference_parity/test_akm_collinear_shares_R_parity.py |
| `DAG` | index_known_truth | tests/reference_parity/test_dag_instruments_dagitty_parity.py |
| `DoubleML` | index_known_truth | tests/reference_parity/test_dml_cluster_doubleml_parity.py |
| `RlassoRegressor` | index_known_truth | tests/reference_parity/test_yuksel_aydede_causal_ml_parity.py |
| `W` | index_known_truth | tests/reference_parity/test_spdep_parity.py |
| `a_learning` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py |
| `abc` | index_known_truth | tests/reference_parity/test_bayes_nonparametric_exact.py |
| `acf` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py, tests/test_prod_fn.py |
| `adaptive_inference` | index_known_truth | tests/reference_parity/test_oct2026_reanchor_known_truth.py, tests/test_wager_textbook_pass.py |
| `aggte` | index_known_truth, reference_parity | tests/external_parity/test_did_paper_gallery.py, tests/reference_parity/test_aggte_mpdta_parity.py, tests/reference_parity/test_aggte_r_did_parity.py, tests/reference_parity/test_aggte_vcov_r_parity.py, tests/reference_parity/test_castle_stata_parity.py |
| `aggte_from_influence` | index_known_truth | tests/reference_parity/test_aggte_r_did_parity.py, tests/test_cs_inference.py, tests/test_cs_rcs.py |
| `always_treat` | index_known_truth | tests/reference_parity/test_longitudinal_parity.py |
| `amplify` | index_known_truth | tests/reference_parity/test_rosenbaum_itos_parity.py |
| `ardl` | index_known_truth, reference_parity | tests/external_parity/test_dogan_python_econometrics.py, tests/reference_parity/test_dynamic_modelling_parity.py |
| `as_svrepdesign` | index_known_truth | tests/reference_parity/test_survey_replicate_parity.py |
| `assimilative_causal` | index_known_truth | tests/reference_parity/test_assimilation_parity.py |
| `auto_cate` | index_known_truth | tests/reference_parity/test_ml_causal_recovery_parity.py |
| `auto_cate_tuned` | index_known_truth | tests/reference_parity/test_ml_causal_recovery_parity_round2.py |
| `bagged_forecast` | index_known_truth | tests/test_forecasting_toolkit.py |
| `bal_tab` | index_known_truth | tests/reference_parity/test_weightit_cobalt_parity.py |
| `balance_diagnostics` | index_known_truth, reference_parity | tests/external_parity/test_barrett_causal_inference_in_r.py, tests/reference_parity/test_barrett_causal_inference_in_r_parity.py, tests/reference_parity/test_oct2026_fourth_pass.py |
| `balance_table` | index_known_truth | tests/external_parity/test_facure_causal_inference_in_python.py |
| `balance_vs_randomization` | index_known_truth | tests/reference_parity/test_rosenbaum_itos_parity.py |
| `balke_pearl` | index_known_truth | tests/reference_parity/test_oct2026_correctness_fixes.py |
| `bandit_allocate` | index_known_truth | tests/reference_parity/test_oct2026_reanchor_known_truth.py, tests/test_wager_textbook_pass.py |
| `bandit_experiment` | index_known_truth | tests/reference_parity/test_oct2026_reanchor_known_truth.py, tests/test_wager_textbook_pass.py |
| `bart` | index_known_truth | tests/reference_parity/test_bayes_nonparametric_exact.py |
| `bart_causal` | index_known_truth | tests/reference_parity/test_bart_causal_seed_screen.py |
| `bayes_arima` | index_known_truth | tests/reference_parity/test_bayes_timeseries_exact_posterior.py |
| `bayes_bootstrap` | index_known_truth | tests/reference_parity/test_bayes_regress_exact_posterior.py |
| `bayes_did` | index_known_truth | tests/reference_parity/test_oct2026_fourth_pass.py, tests/test_bayes_did.py, tests/test_low_cov_battery.py |
| `bayes_dml` | index_known_truth | tests/reference_parity/test_oct2026_fourth_pass.py, tests/test_bayes_dml.py |
| `bayes_factor` | index_known_truth | tests/reference_parity/test_bayes_regress_exact_posterior.py |
| `bayes_fuzzy_rd` | index_known_truth | tests/reference_parity/test_oct2026_fourth_pass.py, tests/test_bayes_fuzzy_rd.py |
| `bayes_hte_iv` | index_known_truth | tests/reference_parity/test_oct2026_fourth_pass.py |
| `bayes_its` | index_known_truth | tests/reference_parity/test_oct2026_fourth_pass.py |
| `bayes_iv` | index_known_truth | tests/reference_parity/test_bayes_diagnostics_parity.py, tests/test_bayes_iv.py, tests/test_bayes_iv_per_instrument.py |
| `bayes_ivreg` | index_known_truth | tests/reference_parity/test_bayes_regress_exact_posterior.py |
| `bayes_mixed` | index_known_truth, reference_parity | tests/external_parity/test_ramirez_hassan_bayes.py, tests/reference_parity/test_bayes_mixed_exact_posterior.py |
| `bayes_mixture` | index_known_truth | tests/reference_parity/test_bayes_latent_exact_posterior.py |
| `bayes_mnprobit` | index_known_truth | tests/reference_parity/test_bayes_latent_exact_posterior.py |
| `bayes_mte` | index_known_truth | tests/reference_parity/test_mte_local_iv_identity.py, tests/test_bayes_mte.py, tests/test_bayes_mte_multi_iv.py |
| `bayes_mvprobit` | index_known_truth | tests/reference_parity/test_bayes_latent_exact_posterior.py |
| `bayes_r2` | index_known_truth | tests/external_parity/test_gelman_ros_examples.py |
| `bayes_rd` | index_known_truth | tests/reference_parity/test_bayes_diagnostics_parity.py, tests/test_bayes_rd.py |
| `bayes_regress` | index_known_truth, reference_parity | tests/external_parity/test_gelman_ros_examples.py, tests/reference_parity/test_bayes_more_exact_posterior.py, tests/reference_parity/test_bayes_regress_exact_posterior.py, tests/reference_parity/test_bayes_workflow_exact_posterior.py, tests/reference_parity/test_oct2026_reanchor_known_truth.py |
| `bayes_shrink` | index_known_truth | tests/reference_parity/test_bayes_more_exact_posterior.py |
| `bayes_sur` | index_known_truth | tests/reference_parity/test_bayes_more_exact_posterior.py |
| `bayes_synth` | index_known_truth | tests/reference_parity/test_bayes_synth_parity.py |
| `bcf` | index_known_truth | tests/reference_parity/test_bcf_parity.py |
| `bcf_factor_exposure` | index_known_truth | tests/reference_parity/test_bcf_factor_exposure_parity.py, tests/test_bcf_ordinal.py |
| `bcf_longitudinal` | index_known_truth | tests/reference_parity/test_oct2026_third_pass.py, tests/test_bcf_longitudinal.py |
| `bcf_ordinal` | index_known_truth | tests/reference_parity/test_oct2026_third_pass.py, tests/test_bcf_ordinal.py |
| `bds` | index_known_truth, reference_parity | tests/external_parity/test_maitra_static_dynamic.py, tests/reference_parity/test_dynamic_modelling_parity.py |
| `best_linear_projection` | index_known_truth, reference_parity | tests/external_parity/test_dml_irm_blp_parity.py, tests/reference_parity/test_grf_family_operator_parity.py |
| `beveridge_nelson` | index_known_truth | tests/reference_parity/test_beveridge_nelson_parity.py |
| `beyond_average_late` | index_known_truth | tests/reference_parity/test_beyond_average_late_parity.py, tests/test_v101_verified_fixes.py |
| `bidirectional_pci` | index_known_truth | tests/reference_parity/test_proximal_parity.py, tests/test_proximal_frontiers.py |
| `bitest` | index_known_truth, reference_parity | tests/external_parity/test_gow_ding_accounting.py, tests/reference_parity/test_bitest_stata_parity.py |
| `bjs_pretrend_joint` | index_known_truth | tests/reference_parity/test_oct2026_second_pass.py |
| `blp_instruments` | index_known_truth | tests/reference_parity/test_berry_logit_pyblp_parity.py |
| `bootstrap` | index_known_truth | tests/reference_parity/test_bootstrap_parity.py, tests/test_round3.py |
| `bootstrap_edges` | index_known_truth | tests/reference_parity/test_hill_climb_bnlearn_parity.py |
| `bootstrap_series` | index_known_truth | tests/test_forecasting_toolkit.py |
| `boundary_rd` | index_known_truth | tests/reference_parity/test_rd_open_R_parity.py |
| `boxcox_lambda` | index_known_truth, reference_parity | tests/external_parity/test_hyndman_fpp_pythonic.py, tests/reference_parity/test_forecasting_r_parity.py |
| `bradford_hill` | index_known_truth | tests/reference_parity/test_bradford_hill_parity.py, tests/test_epi.py |
| `breakdown_frontier` | index_known_truth | tests/reference_parity/test_breakdown_frontier_parity.py |
| `bridge` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py, tests/test_bridge.py, tests/test_bridge_full.py |
| `bunching` | index_known_truth | tests/reference_parity/test_bunching_parity.py |
| `bvar` | index_known_truth | tests/reference_parity/test_timeseries_R_parity.py |
| `calibrate_cate` | index_known_truth | tests/reference_parity/test_panel_forest_recovery.py |
| `cardinality_match` | index_known_truth | tests/reference_parity/test_cardinality_match_parity.py |
| `cate_by_group` | index_known_truth | tests/reference_parity/test_closed_form_identities.py |
| `cate_gain_curve` | index_known_truth | tests/external_parity/test_facure_causal_inference_in_python.py |
| `cate_pretrend_test` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py, tests/test_forest_fe_imputation.py |
| `cate_summary` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py |
| `causal_bandit` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py, tests/test_causal_rl_core.py |
| `causal_discovery` | index_known_truth | tests/reference_parity/test_oct2026_fourth_pass.py |
| `causal_dqn` | index_known_truth | tests/reference_parity/test_oct2026_third_pass.py, tests/test_causal_rl.py |
| `causal_gap` | index_known_truth | tests/reference_parity/test_causal_gap_known_values.py |
| `causal_impact` | index_known_truth | tests/reference_parity/test_causal_impact_uncertainty.py, tests/test_causal_impact.py |
| `causal_kalman` | index_known_truth | tests/reference_parity/test_assimilation_parity.py |
| `causal_policy_forest` | index_known_truth | tests/reference_parity/test_ope_parity.py, tests/test_ope_extensions.py |
| `causal_rl_benchmark` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py |
| `causal_survival` | index_known_truth | tests/reference_parity/test_oct2026_second_pass.py |
| `causal_survival_forest` | index_known_truth | tests/reference_parity/test_grf_family_statistical_parity.py |
| `cdlz_bunching` | index_known_truth | tests/external_parity/test_cdlz_bunching_table1.py |
| `cevae` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py, tests/test_neural_causal_exports.py, tests/test_ope_cevae.py |
| `cfrnet` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py, tests/test_neural_causal.py, tests/test_neural_causal_exports.py |
| `check_absorbing` | index_known_truth | tests/reference_parity/test_absorbing_reference.py |
| `chow_test` | index_known_truth, reference_parity | tests/external_parity/test_maitra_static_dynamic.py, tests/reference_parity/test_dynamic_modelling_parity.py |
| `ci` | index_known_truth | tests/reference_parity/test_textbook_syllabus_stata_parity.py |
| `classical_decompose` | index_known_truth | tests/reference_parity/test_forecasting_r_parity.py |
| `clone_censor_weight` | index_known_truth | tests/reference_parity/test_target_trial_parity.py, tests/test_target_trial.py |
| `cluster_cate` | index_known_truth | tests/reference_parity/test_ml_causal_recovery_parity_round2.py |
| `cluster_cross_interference` | index_known_truth | tests/reference_parity/test_cluster_cross_interference_parity.py, tests/test_cluster_rct.py |
| `cluster_matched_pair` | index_known_truth | tests/reference_parity/test_closed_form_identities.py |
| `cluster_staggered_rollout` | index_known_truth | tests/reference_parity/test_oct2026_correctness_fixes.py |
| `cnsreg` | index_known_truth | tests/reference_parity/test_hansen_methods_stata_parity.py |
| `cohort_anchored_event_study` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py, tests/test_did_frontiers.py |
| `compare_event_study_conventions` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py, tests/test_did_event_study_conventions.py |
| `compare_metalearners` | index_known_truth | tests/reference_parity/test_oct2026_third_pass.py |
| `conformal` | index_known_truth | tests/reference_parity/test_linear_model_extensions_parity.py, tests/test_dispatchers_v150.py |
| `conformal_cate` | index_known_truth | tests/reference_parity/test_conformal_causal_parity.py |
| `conformal_continuous` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py, tests/test_conformal_extended.py |
| `conformal_counterfactual` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py |
| `conformal_debiased_ml` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py |
| `conformal_density_ite` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py |
| `conformal_fair_ite` | index_known_truth | tests/reference_parity/test_conformal_fair_ite_parity.py, tests/test_conformal_frontiers.py |
| `conformal_interference` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py, tests/test_conformal_extended.py |
| `conformal_ite` | index_known_truth | tests/reference_parity/test_conformal_ite_parity.py |
| `conformal_ite_interval` | index_known_truth | tests/reference_parity/test_conformal_causal_parity.py |
| `conformal_ite_multidp` | index_known_truth | tests/reference_parity/test_oct2026_third_pass.py |
| `conformal_regression` | index_known_truth, reference_parity | tests/external_parity/test_ding_linear_model.py, tests/reference_parity/test_linear_model_extensions_parity.py |
| `confounder_adjust` | index_known_truth, reference_parity | tests/external_parity/test_barrett_causal_inference_in_r.py, tests/reference_parity/test_barrett_causal_inference_in_r_parity.py |
| `confounder_tip` | index_known_truth, reference_parity | tests/external_parity/test_barrett_causal_inference_in_r.py, tests/reference_parity/test_barrett_causal_inference_in_r_parity.py |
| `contextual_bandit` | index_known_truth | tests/reference_parity/test_oct2026_reanchor_known_truth.py, tests/test_wager_textbook_pass.py |
| `continuous_iv_late` | index_known_truth | tests/reference_parity/test_continuous_iv_late_parity.py, tests/test_continuous_iv_late.py |
| `copula_sensitivity` | index_known_truth | tests/reference_parity/test_closed_form_identities.py |
| `cor_test` | index_known_truth | tests/reference_parity/test_effect_size_power_ttest_parity.py |
| `corrgram` | index_known_truth, reference_parity | tests/external_parity/test_maitra_static_dynamic.py, tests/reference_parity/test_dynamic_modelling_parity.py, tests/reference_parity/test_textbook_methods_stata_parity.py |
| `counterfactual_fairness` | index_known_truth | tests/reference_parity/test_fairness_parity.py, tests/test_fairness.py |
| `counterfactual_policy_optimization` | index_known_truth | tests/reference_parity/test_oct2026_second_pass.py, tests/test_causal_rl_core.py |
| `cs_jackknife` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py, tests/test_cs_jackknife.py, tests/test_cs_jackknife_reference.py |
| `cs_report` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py |
| `ctmle` | index_known_truth | tests/reference_parity/test_ctmle_R_parity.py |
| `dag` | index_known_truth, reference_parity | tests/external_parity/test_barrett_causal_inference_in_r.py, tests/reference_parity/test_barrett_causal_inference_in_r_parity.py, tests/reference_parity/test_dag_implications_dagitty_parity.py, tests/reference_parity/test_dag_instruments_dagitty_parity.py, tests/reference_parity/test_misc_sens_R_parity.py, tests/test_dag_recommend_and_tte_report.py, tests/test_dag_scm.py |
| `deepiv` | index_known_truth | tests/reference_parity/test_oct2026_fourth_pass.py |
| `demographic_parity` | index_known_truth | tests/reference_parity/test_fairness_parity.py, tests/test_fairness.py |
| `design_aberration` | index_known_truth | tests/reference_parity/test_joseph_doe_parity.py |
| `design_augment` | index_known_truth | tests/reference_parity/test_joseph_doe_parity.py |
| `design_criteria` | index_known_truth | tests/reference_parity/test_joseph_doe_parity.py |
| `design_robust_event_study` | index_known_truth | tests/reference_parity/test_oct2026_correctness_fixes.py, tests/test_did_frontiers.py |
| `diagnose` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py |
| `diagnose_result` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py, tests/test_diagnose_result_closed_loop.py, tests/test_workflow_sprint_b.py |
| `did` | index_known_truth | tests/reference_parity/test_cs_weighted_parity.py, tests/reference_parity/test_did_parity.py, tests/test_did.py |
| `did_analysis` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py, tests/test_cov95_did_analysis.py, tests/test_did_imputation_branches.py |
| `did_balance` | index_known_truth | tests/reference_parity/test_did_balance_parity.py |
| `did_bcf` | index_known_truth | tests/reference_parity/test_oct2026_second_pass.py, tests/test_cov95_did_r3_did_bcf.py, tests/test_did_frontiers.py |
| `did_calibrated_simulation` | index_known_truth | tests/reference_parity/test_oct2026_fourth_pass.py, tests/test_did_calibrated_simulation.py |
| `did_cluster_diagnostics` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py, tests/test_did_design_audit.py |
| `did_few_treated` | index_known_truth | tests/reference_parity/test_closed_form_identities.py, tests/test_did_few_treated.py |
| `did_forest` | index_known_truth | tests/reference_parity/test_panel_forest_recovery.py, tests/test_did_forest.py |
| `did_had` | index_known_truth, reference_parity | tests/external_parity/test_dcdh_did_textbook.py, tests/reference_parity/test_did_had_parity.py |
| `did_misclassified` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py, tests/test_did_frontiers.py |
| `did_report` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py |
| `did_summary` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py |
| `didregress` | index_known_truth | tests/reference_parity/test_didregress_dlang_stata.py |
| `difference_in_means` | index_known_truth, reference_parity | tests/external_parity/test_ding_first_course.py, tests/reference_parity/test_difference_in_means_estimatr.py, tests/reference_parity/test_lm_lin_estimatr_parity.py |
| `discos_test` | index_known_truth | tests/reference_parity/test_oct2026_fourth_pass.py |
| `disparity_decompose` | index_known_truth | tests/reference_parity/test_closed_form_identities.py |
| `dist_iv` | index_known_truth | tests/reference_parity/test_decomp_qte_parity.py |
| `distance_to_feature` | index_known_truth | tests/reference_parity/test_oct2026_fourth_pass.py |
| `distributional_te` | index_known_truth | tests/reference_parity/test_distributional_te_inference.py |
| `diversity_index` | index_known_truth | tests/reference_parity/test_closed_form_identities.py, tests/test_diversity_index.py |
| `dl_propensity_score` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py, tests/test_overlap_did.py |
| `dml_diagnostics` | index_known_truth | tests/reference_parity/test_ml_causal_dml_parity.py |
| `dnc_gnn_did` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py |
| `do_calculus_apply` | index_known_truth | tests/reference_parity/test_oct2026_second_pass.py |
| `do_rule1` | index_known_truth | tests/reference_parity/test_oct2026_second_pass.py |
| `do_rule2` | index_known_truth | tests/reference_parity/test_oct2026_second_pass.py |
| `do_rule3` | index_known_truth | tests/reference_parity/test_oct2026_second_pass.py |
| `doe_optimal` | index_known_truth | tests/reference_parity/test_joseph_doe_parity.py |
| `double_negative_control` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py |
| `dragonnet` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py, tests/test_neural_causal.py, tests/test_neural_causal_exports.py |
| `dynamic_dml` | index_known_truth | tests/reference_parity/test_dynamic_dml_econml_parity.py |
| `dynotears` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py, tests/test_causal_discovery_ts.py |
| `energy_distance` | index_known_truth | tests/reference_parity/test_barrett_causal_inference_in_r_parity.py |
| `equalized_odds` | index_known_truth | tests/reference_parity/test_fairness_parity.py, tests/test_fairness.py |
| `ess` | index_known_truth, reference_parity | tests/external_parity/test_barrett_causal_inference_in_r.py, tests/reference_parity/test_barrett_causal_inference_in_r_parity.py |
| `estat` | index_known_truth, reference_parity | tests/external_parity/test_ding_linear_model.py, tests/reference_parity/test_didregress_stata.py, tests/reference_parity/test_hansen_methods_stata_parity.py, tests/reference_parity/test_iv_stata_commands_parity.py, tests/reference_parity/test_linear_model_extensions_parity.py |
| `ets` | index_known_truth, reference_parity | tests/external_parity/test_hyndman_fpp_pythonic.py, tests/reference_parity/test_forecasting_r_parity.py |
| `evidence_factors` | index_known_truth | tests/reference_parity/test_rosenbaum_itos_parity.py |
| `evidence_without_injustice` | index_known_truth | tests/reference_parity/test_fairness_parity.py, tests/test_api_stable_evidence.py |
| `factor` | index_known_truth | tests/reference_parity/test_hansen_methods_stata_parity.py |
| `factor_importance` | index_known_truth | tests/reference_parity/test_joseph_doe_parity.py |
| `factorial_design` | index_known_truth | tests/reference_parity/test_joseph_doe_parity.py |
| `factorial_effects` | index_known_truth | tests/reference_parity/test_joseph_doe_parity.py |
| `fairness_audit` | index_known_truth | tests/reference_parity/test_fairness_parity.py, tests/test_fairness.py |
| `focal_cate` | index_known_truth | tests/reference_parity/test_ml_causal_recovery_parity_round2.py |
| `forecast_accuracy` | index_known_truth, reference_parity | tests/external_parity/test_hyndman_fpp_pythonic.py, tests/reference_parity/test_forecasting_r_parity.py |
| `forest_diagnostics` | index_known_truth | tests/reference_parity/test_ml_causal_R_parity.py |
| `forest_group_effects` | index_known_truth | tests/reference_parity/test_fe_forest_imputation_recovery.py, tests/test_forest_fe_imputation.py |
| `forest_policy_tree` | index_known_truth | tests/reference_parity/test_fe_forest_policy_recovery.py |
| `forest_support` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py, tests/test_forest_fe_imputation.py |
| `fortified_pci` | index_known_truth | tests/reference_parity/test_proximal_parity.py, tests/test_proximal_frontiers.py |
| `fourier_terms` | index_known_truth | tests/reference_parity/test_forecasting_r_parity.py |
| `from_r` | index_known_truth | tests/reference_parity/test_accounting_research_parity.py |
| `from_stata` | index_known_truth | tests/reference_parity/test_bitest_stata_parity.py |
| `front_door` | index_known_truth, reference_parity | tests/external_parity/test_ness_causal_ai.py, tests/reference_parity/test_front_door_parity.py, tests/test_front_door.py, tests/test_review_fixes_round2.py |
| `frontdoor` | index_known_truth | tests/reference_parity/test_frontdoor_parity.py |
| `general_bunching` | index_known_truth | tests/reference_parity/test_bunching_parity.py |
| `geolift` | index_known_truth | tests/reference_parity/test_geolift_parity.py |
| `ges` | index_known_truth | tests/reference_parity/test_ges_parity.py |
| `get_scores` | index_known_truth | tests/reference_parity/test_grf_family_operator_parity.py |
| `gformula_mc` | index_known_truth | tests/reference_parity/test_gformula_family_parity.py |
| `gnn_causal` | index_known_truth | tests/reference_parity/test_oct2026_third_pass.py |
| `gns` | index_known_truth | tests/reference_parity/test_spatial_durbin_error_Stata_parity.py |
| `gp_regress` | index_known_truth | tests/reference_parity/test_bayes_nonparametric_exact.py |
| `group_sequential` | index_known_truth | tests/reference_parity/test_group_sequential_stata_parity.py |
| `hal_tmle` | index_known_truth | tests/reference_parity/test_ml_causal_recovery_parity_round2.py, tests/test_hal_tmle.py |
| `hausman` | index_known_truth | tests/reference_parity/test_textbook_methods_stata_parity.py |
| `hausman_test` | index_known_truth | tests/reference_parity/test_diag_recovery_parity.py |
| `hierarchy` | index_known_truth | tests/external_parity/test_hyndman_fpp_pythonic.py |
| `honest_did_from_moments` | index_known_truth | tests/reference_parity/test_honest_did_moments_R_parity.py |
| `honest_did_from_result` | index_known_truth | tests/reference_parity/test_honest_did_moments_R_parity.py |
| `honest_variance` | index_known_truth | tests/reference_parity/test_forest_rate_honest_parity.py |
| `icp` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py, tests/test_icp.py |
| `ida` | index_known_truth | tests/reference_parity/test_ida_pcalg_parity.py |
| `identify_counterfactual` | index_known_truth | tests/test_counterfactual_identification.py |
| `identify_transport` | index_known_truth | tests/reference_parity/test_misc_sens_R_parity.py, tests/test_transport.py |
| `immortal_time_check` | index_known_truth | tests/reference_parity/test_target_trial_parity.py |
| `implied_weights` | index_known_truth, reference_parity | tests/external_parity/test_barrett_causal_inference_in_r.py, tests/reference_parity/test_barrett_causal_inference_in_r_parity.py |
| `influence_functions` | index_known_truth | tests/reference_parity/test_aggte_r_did_parity.py, tests/test_cs_inference.py, tests/test_cs_rcs.py |
| `instrumental_forest` | index_known_truth | tests/reference_parity/test_oct2026_second_pass.py |
| `interference` | index_known_truth | tests/reference_parity/test_interference_parity.py, tests/test_dispatchers_v150.py |
| `interference_test` | index_known_truth | tests/reference_parity/test_oct2026_reanchor_known_truth.py, tests/test_wager_textbook_pass.py |
| `invlogit` | index_known_truth | tests/reference_parity/test_oct2026_reanchor_known_truth.py |
| `inward_outward_spillover` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py, tests/test_interference_extensions.py |
| `iv_bounds` | index_known_truth | tests/reference_parity/test_oct2026_third_pass.py |
| `iv_compare` | index_known_truth | tests/iv/test_iv_diag.py, tests/reference_parity/test_oct2026_fourth_pass.py |
| `iv_forest` | index_known_truth | tests/reference_parity/test_grf_family_operator_parity.py |
| `ivqreg` | index_known_truth | tests/reference_parity/test_ivqreg_parity.py |
| `jackknife` | index_known_truth | tests/reference_parity/test_hansen_methods_stata_parity.py |
| `kan_dlate` | index_known_truth | tests/reference_parity/test_dist_iv_parity.py |
| `kernel_iv` | index_known_truth | tests/reference_parity/test_oct2026_third_pass.py, tests/test_iv_frontiers.py, tests/test_kernel_iv.py |
| `kfold` | index_known_truth, reference_parity | tests/external_parity/test_gelman_ros_examples.py, tests/reference_parity/test_bayes_workflow_exact_posterior.py |
| `kfold_split` | index_known_truth | tests/reference_parity/test_oct2026_reanchor_known_truth.py |
| `kink_unified` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py |
| `kitagawa_test` | index_known_truth | tests/reference_parity/test_oct2026_correctness_fixes.py |
| `l1_imbalance` | index_known_truth | tests/reference_parity/test_cem_k2k_parity.py |
| `lasso_iv` | index_known_truth | tests/reference_parity/test_lasso_iv_parity.py |
| `lasso_select` | index_known_truth | tests/reference_parity/test_lasso_select_parity.py |
| `levpet` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py, tests/test_prod_fn.py |
| `line_length_in_polygon` | index_known_truth | tests/reference_parity/test_oct2026_fourth_pass.py |
| `lingam` | index_known_truth | tests/reference_parity/test_causal_discovery_parity.py |
| `lisa_cluster_map` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py |
| `ljungbox` | index_known_truth, reference_parity | tests/external_parity/test_hyndman_fpp_pythonic.py, tests/reference_parity/test_forecasting_r_parity.py |
| `llm_dag_validate` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py, tests/test_llm_dag_loop.py |
| `lm_forest` | index_known_truth | tests/reference_parity/test_grf_family_statistical_parity.py |
| `lm_lin` | index_known_truth, reference_parity | tests/external_parity/test_ding_first_course.py, tests/reference_parity/test_ding_first_course_parity.py, tests/reference_parity/test_lm_lin_estimatr_parity.py, tests/reference_parity/test_yuksel_aydede_causal_ml_parity.py |
| `lmtp` | index_known_truth | tests/reference_parity/test_lmtp_parity.py |
| `loneway` | index_known_truth | tests/reference_parity/test_qiu_jiaping_methods_stata.py |
| `long_term_from_short` | index_known_truth | tests/reference_parity/test_surrogate_parity.py, tests/test_surrogate.py |
| `longitudinal_analyze` | index_known_truth | tests/reference_parity/test_longitudinal_parity.py, tests/test_longitudinal.py |
| `longitudinal_contrast` | index_known_truth | tests/reference_parity/test_longitudinal_parity.py, tests/test_longitudinal.py |
| `loo_predict` | index_known_truth | tests/reference_parity/test_oct2026_reanchor_known_truth.py |
| `loo_r2` | index_known_truth | tests/external_parity/test_gelman_ros_examples.py |
| `lpbwselect_ce_rot` | index_known_truth | tests/reference_parity/test_lprobust_cleanroom.py |
| `lpbwselect_imse_dpi` | index_known_truth | tests/reference_parity/test_lprobust_cleanroom.py |
| `lpbwselect_imse_rot` | index_known_truth | tests/reference_parity/test_lprobust_cleanroom.py |
| `lpbwselect_mse_dpi` | index_known_truth | tests/reference_parity/test_did_had_parity.py |
| `lpbwselect_mse_rot` | index_known_truth | tests/reference_parity/test_did_had_parity.py |
| `lpcmci` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py, tests/test_causal_discovery_ts.py |
| `lprobust_at_point` | index_known_truth | tests/reference_parity/test_lprobust_cleanroom.py |
| `ltmle_msm` | index_known_truth | tests/reference_parity/test_ltmle_msm_parity.py |
| `ltmle_survival` | index_known_truth | tests/reference_parity/test_ml_causal_recovery_parity_round2.py |
| `machado_mata` | index_known_truth | tests/reference_parity/test_decomp_qte_parity.py |
| `mad_sd` | index_known_truth | tests/external_parity/test_gelman_ros_examples.py |
| `marginal_policy_effect` | index_known_truth | tests/reference_parity/test_oct2026_reanchor_known_truth.py, tests/test_wager_textbook_pass.py |
| `matrix_completion` | index_known_truth | tests/reference_parity/test_matrix_completion_parity.py |
| `mdp_policy_value` | index_known_truth | tests/reference_parity/test_oct2026_reanchor_known_truth.py, tests/test_wager_textbook_pass.py |
| `mediate_paths` | index_known_truth | tests/reference_parity/test_mediate_paths_parity.py |
| `metafrontier` | index_known_truth | tests/reference_parity/test_frontier_efficiency_parity.py |
| `mi_test` | index_known_truth | tests/reference_parity/test_mi_test_parity.py |
| `mice` | index_known_truth | tests/reference_parity/test_imputation_parity.py |
| `mixture_design` | index_known_truth | tests/reference_parity/test_oct2026_reanchor_known_truth.py, tests/test_doe.py |
| `ml_bounds` | index_known_truth | tests/reference_parity/test_oct2026_second_pass.py |
| `mmhc` | index_known_truth | tests/reference_parity/test_mmhc_bnlearn_parity.py |
| `model_average` | index_known_truth | tests/reference_parity/test_hansen_methods_stata_parity.py |
| `morris_screening` | index_known_truth | tests/reference_parity/test_joseph_doe_parity.py |
| `mprobit` | index_known_truth | tests/reference_parity/test_hansen_methods_stata_parity.py |
| `mr_clust` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py, tests/test_mr_frontier.py |
| `mr_lap` | index_known_truth | tests/reference_parity/test_mr_lap_parity.py, tests/test_mr_frontier.py |
| `mswitch_lrtest` | index_known_truth | tests/reference_parity/test_oct2026_reanchor_known_truth.py, tests/test_mswitch_lrtest.py |
| `multi_arm_forest` | index_known_truth | tests/reference_parity/test_grf_family_statistical_parity.py |
| `multi_regression_forest` | index_known_truth | tests/reference_parity/test_oct2026_second_pass.py |
| `multi_score_rd` | index_known_truth | tests/reference_parity/test_oct2026_correctness_fixes.py |
| `ndiffs` | index_known_truth, reference_parity | tests/external_parity/test_hyndman_fpp_pythonic.py, tests/reference_parity/test_forecasting_r_parity.py |
| `negative_control_exposure` | index_known_truth | tests/reference_parity/test_closed_form_identities.py |
| `negative_control_outcome` | index_known_truth | tests/reference_parity/test_closed_form_identities.py |
| `network_exposure` | index_known_truth | tests/reference_parity/test_interference_parity.py, tests/test_dispatchers_v150.py, tests/test_wager_textbook_pass.py |
| `network_graph` | index_known_truth | tests/reference_parity/test_network_parity.py, tests/test_network.py |
| `network_hte` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py, tests/test_interference_extensions.py |
| `never_treat` | index_known_truth | tests/reference_parity/test_longitudinal_parity.py |
| `nlcom` | index_known_truth | tests/reference_parity/test_hansen_methods_stata_parity.py |
| `nls` | index_known_truth | tests/reference_parity/test_hansen_methods_stata_parity.py |
| `noether_test` | index_known_truth | tests/reference_parity/test_rosenbaum_itos_parity.py |
| `nonlinear_icp` | index_known_truth | tests/reference_parity/test_oct2026_second_pass.py |
| `notch` | index_known_truth | tests/reference_parity/test_notch_parity.py |
| `notears` | index_known_truth | tests/reference_parity/test_causal_discovery_parity.py |
| `nsdiffs` | index_known_truth, reference_parity | tests/external_parity/test_hyndman_fpp_pythonic.py, tests/reference_parity/test_forecasting_r_parity.py |
| `offline_safe_policy` | index_known_truth | tests/reference_parity/test_oct2026_third_pass.py |
| `opreg` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py, tests/test_prod_fn.py |
| `optimal_design` | index_known_truth | tests/reference_parity/test_closed_form_identities.py |
| `orthogonal_to_bias` | index_known_truth | tests/reference_parity/test_fairness_parity.py, tests/test_fairness.py |
| `outlier_indicator` | index_known_truth | tests/reference_parity/test_oct2026_third_pass.py |
| `overlap_weighted_did` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py, tests/test_overlap_did.py |
| `panel_compare` | index_known_truth | tests/reference_parity/test_oct2026_fourth_pass.py, tests/test_api_stable_evidence.py |
| `parallel_trends_robustness` | index_known_truth | tests/external_parity/test_rebel_canal_published.py |
| `partial_corr_pvalue` | index_known_truth | tests/reference_parity/test_closed_form_identities.py |
| `partial_identification` | index_known_truth | tests/reference_parity/test_closed_form_identities.py |
| `particle_filter` | index_known_truth | tests/reference_parity/test_assimilation_parity.py |
| `pate` | index_known_truth | tests/reference_parity/test_pate_parity.py |
| `pca` | index_known_truth | tests/reference_parity/test_hansen_methods_stata_parity.py |
| `pci_mtp` | index_known_truth | tests/reference_parity/test_oct2026_second_pass.py, tests/test_proximal_frontiers.py |
| `pcmci` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py |
| `peer_effects` | index_known_truth | tests/reference_parity/test_peer_effects_parity.py |
| `policy_targeting` | index_known_truth | tests/reference_parity/test_closed_form_identities.py |
| `policy_weight_ate` | index_known_truth | tests/reference_parity/test_policy_weight_parity.py |
| `policy_weight_marginal` | index_known_truth | tests/reference_parity/test_policy_weight_parity.py |
| `policy_weight_observed_prte` | index_known_truth | tests/reference_parity/test_policy_weight_parity.py |
| `policy_weight_prte` | index_known_truth | tests/reference_parity/test_oct2026_second_pass.py |
| `policy_weight_subsidy` | index_known_truth | tests/reference_parity/test_policy_weight_parity.py |
| `poststratify` | index_known_truth | tests/external_parity/test_gelman_ros_examples.py |
| `power` | index_known_truth, reference_parity | tests/external_parity/test_facure_causal_inference_in_python.py, tests/reference_parity/test_oct2026_second_pass.py |
| `power_did` | index_known_truth | tests/reference_parity/test_oct2026_second_pass.py |
| `power_iv` | index_known_truth | tests/reference_parity/test_oct2026_second_pass.py |
| `power_ols` | index_known_truth | tests/reference_parity/test_recovery_batch_parity.py |
| `power_rd` | index_known_truth | tests/reference_parity/test_oct2026_second_pass.py |
| `ppc` | index_known_truth | tests/external_parity/test_gelman_ros_examples.py |
| `ppi_mean` | index_known_truth | tests/reference_parity/test_closed_form_identities.py |
| `ppi_ols` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py |
| `prais` | index_known_truth | tests/reference_parity/test_textbook_methods_stata_parity.py |
| `predict_cate` | index_known_truth | tests/reference_parity/test_oct2026_fourth_pass.py |
| `pretrends_equivalence` | index_known_truth | tests/reference_parity/test_fect_equivalence_parity.py |
| `pretrends_summary` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py |
| `pretrends_test` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py, tests/test_cov95_did_pretrends.py, tests/test_cov95_did_r3_pretrends.py |
| `probability_forest` | index_known_truth | tests/reference_parity/test_oct2026_second_pass.py |
| `prod_fn` | index_known_truth | tests/reference_parity/test_structural_parity.py, tests/test_prod_fn.py |
| `propensity_score` | index_known_truth, reference_parity | tests/external_parity/test_barrett_causal_inference_in_r.py, tests/reference_parity/test_barrett_causal_inference_in_r_parity.py, tests/reference_parity/test_closed_form_identities.py, tests/reference_parity/test_yuksel_aydede_causal_ml_parity.py |
| `proximal` | index_known_truth | tests/reference_parity/test_proximal_parity.py, tests/test_proximal.py |
| `proximal_regression` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py |
| `proximal_surrogate_index` | index_known_truth | tests/reference_parity/test_surrogate_parity.py, tests/test_surrogate.py |
| `prtest` | index_known_truth | tests/reference_parity/test_textbook_syllabus_stata_parity.py |
| `ps_balance` | index_known_truth | tests/reference_parity/test_oct2026_fourth_pass.py |
| `ps_weights` | index_known_truth, reference_parity | tests/external_parity/test_barrett_causal_inference_in_r.py, tests/reference_parity/test_barrett_causal_inference_in_r_parity.py |
| `pscore` | index_known_truth | tests/reference_parity/test_qiu_jiaping_methods_stata.py |
| `pwcorr` | index_known_truth | tests/reference_parity/test_oct2026_third_pass.py |
| `q_learning` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py |
| `qqsynth` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py |
| `qte_hd_panel` | index_known_truth | tests/reference_parity/test_hd_panel_qte.py |
| `quantile_forest` | index_known_truth | tests/reference_parity/test_grf_family_statistical_parity.py |
| `quasi_untreated_test` | index_known_truth | tests/reference_parity/test_did_had_parity.py |
| `randomize` | index_known_truth | tests/reference_parity/test_closed_form_identities.py |
| `rank` | index_known_truth | tests/reference_parity/test_oct2026_third_pass.py |
| `rate_split` | index_known_truth | tests/reference_parity/test_fe_forest_rate_recovery.py, tests/test_forest_rate_fe.py |
| `rd` | index_known_truth | tests/reference_parity/test_oct2026_fourth_pass.py, tests/test_rd_dispatcher.py |
| `rd_bayes_hte` | index_known_truth | tests/reference_parity/test_oct2026_third_pass.py |
| `rd_boost` | index_known_truth | tests/reference_parity/test_oct2026_correctness_fixes.py |
| `rd_cate_summary` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py |
| `rd_compare` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py |
| `rd_diff_in_disc` | index_known_truth | tests/reference_parity/test_rd_diff_in_disc_Stata_parity.py |
| `rd_distribution` | index_known_truth | tests/reference_parity/test_oct2026_correctness_fixes.py |
| `rd_distributional_design` | index_known_truth | tests/reference_parity/test_oct2026_second_pass.py |
| `rd_external_validity` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py |
| `rd_extrapolate` | index_known_truth | tests/reference_parity/test_oct2026_correctness_fixes.py |
| `rd_flex` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py, tests/test_rd_polish.py |
| `rd_forest` | index_known_truth | tests/reference_parity/test_oct2026_correctness_fixes.py |
| `rd_interference` | index_known_truth | tests/reference_parity/test_oct2026_second_pass.py |
| `rd_lasso` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py |
| `rd_multi_extrapolate` | index_known_truth | tests/reference_parity/test_oct2026_second_pass.py |
| `rd_multi_score` | index_known_truth | tests/reference_parity/test_oct2026_correctness_fixes.py |
| `rd_optimized` | index_known_truth | tests/reference_parity/test_rd_optimized_optrdd.py, tests/test_wager_textbook_pass.py |
| `rd_robustness_table` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py |
| `rdbalance` | index_known_truth | tests/reference_parity/test_oct2026_second_pass.py |
| `rdbwsensitivity` | index_known_truth | tests/reference_parity/test_closed_form_identities.py |
| `rdit` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py |
| `rdplacebo` | index_known_truth | tests/reference_parity/test_closed_form_identities.py |
| `rdsummary` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py |
| `read_data` | index_known_truth | tests/external_parity/test_hansen_econometrics_logs.py |
| `reconcile` | index_known_truth, reference_parity | tests/external_parity/test_hyndman_fpp_pythonic.py, tests/reference_parity/test_forecasting_r_parity.py |
| `refute` | index_known_truth | tests/external_parity/test_ness_causal_ai.py |
| `regime` | index_known_truth | tests/reference_parity/test_longitudinal_parity.py, tests/test_longitudinal.py |
| `regression_forest` | index_known_truth | tests/reference_parity/test_oct2026_second_pass.py |
| `residual_balance` | index_known_truth | tests/reference_parity/test_residual_balance_balancehd.py |
| `result_card` | index_known_truth | tests/reference_parity/test_hdfe_fit_stats_reghdfe.py |
| `rmst` | index_known_truth | tests/reference_parity/test_survival_causal_parity.py |
| `robustness_report` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py |
| `rolling` | index_known_truth, reference_parity | tests/external_parity/test_maitra_static_dynamic.py, tests/reference_parity/test_dynamic_modelling_parity.py |
| `romano_wolf` | index_known_truth | tests/reference_parity/test_romano_wolf_parity.py |
| `rosenbaum_stratified` | index_known_truth | tests/reference_parity/test_rosenbaum_itos_parity.py |
| `rotemberg_summary` | index_known_truth | tests/reference_parity/test_rotemberg_summary_Stata_parity.py |
| `rwd_rct_concordance` | index_known_truth | tests/reference_parity/test_closed_form_identities.py, tests/test_evidence_synthesis.py |
| `savage_dickey` | index_known_truth | tests/reference_parity/test_bayes_regress_exact_posterior.py |
| `scalar_iv_projection` | index_known_truth | tests/reference_parity/test_oct2026_third_pass.py |
| `scigan` | index_known_truth | tests/reference_parity/test_oct2026_third_pass.py |
| `sdem` | index_known_truth | tests/reference_parity/test_spatial_durbin_error_Stata_parity.py |
| `sdtest` | index_known_truth | tests/reference_parity/test_textbook_syllabus_stata_parity.py |
| `seasonal_dummies` | index_known_truth | tests/test_forecasting_toolkit.py |
| `select_pci_proxies` | index_known_truth | tests/reference_parity/test_oct2026_second_pass.py |
| `selection_bounds` | index_known_truth | tests/reference_parity/test_selection_bounds_parity.py |
| `sensitivity_rr` | index_known_truth | tests/reference_parity/test_oct2026_fourth_pass.py, tests/test_api_stable_evidence.py |
| `sequential_design` | index_known_truth | tests/reference_parity/test_oct2026_reanchor_known_truth.py, tests/test_doe.py |
| `sequential_sdid` | index_known_truth | tests/reference_parity/test_synth_rest_R_parity.py, tests/test_sequential_sdid.py |
| `series` | index_known_truth | tests/external_parity/test_hansen_econometrics_logs.py |
| `share_within_buffer` | index_known_truth | tests/reference_parity/test_oct2026_fourth_pass.py |
| `sharp_ope_unobserved` | index_known_truth | tests/reference_parity/test_ope_parity.py, tests/test_ope_extensions.py |
| `shrinkage` | index_known_truth, reference_parity | tests/external_parity/test_dogan_python_econometrics.py, tests/reference_parity/test_yuksel_aydede_causal_ml_parity.py |
| `simple_forecast` | index_known_truth, reference_parity | tests/external_parity/test_hyndman_fpp_pythonic.py, tests/reference_parity/test_forecasting_r_parity.py |
| `sktest` | index_known_truth | tests/reference_parity/test_dynamic_modelling_parity.py |
| `snmm` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py |
| `sobol_indices` | index_known_truth | tests/reference_parity/test_joseph_doe_parity.py |
| `space_filling` | index_known_truth | tests/reference_parity/test_joseph_doe_parity.py |
| `spatial_did` | index_known_truth | tests/reference_parity/test_spatial_models_parity.py |
| `spec_curve` | index_known_truth | tests/reference_parity/test_spec_curve_fe_Stata_parity.py, tests/test_spec_curve.py |
| `spillover` | index_known_truth | tests/reference_parity/test_interference_parity.py, tests/test_dispatchers_v150.py, tests/test_phase9to14.py |
| `split_data` | index_known_truth | tests/reference_parity/test_joseph_doe_parity.py |
| `ssc` | index_known_truth | tests/reference_parity/test_ssc_presets_Stata_parity.py |
| `stata` | index_known_truth | tests/reference_parity/test_bitest_stata_parity.py |
| `stepwise` | index_known_truth, reference_parity | tests/external_parity/test_ding_linear_model.py, tests/reference_parity/test_linear_model_extensions_parity.py, tests/reference_parity/test_stepwise_parity.py |
| `stl` | index_known_truth, reference_parity | tests/external_parity/test_hyndman_fpp_pythonic.py, tests/reference_parity/test_forecasting_r_parity.py |
| `stochastic_dominance` | index_known_truth | tests/reference_parity/test_distributional_te_parity.py |
| `stochvol` | index_known_truth | tests/reference_parity/test_bayes_timeseries_exact_posterior.py |
| `structural_mdp` | index_known_truth | tests/reference_parity/test_oct2026_second_pass.py, tests/test_causal_rl_core.py |
| `stteffects` | index_known_truth | tests/reference_parity/test_survival_causal_parity.py |
| `suest` | index_known_truth | tests/reference_parity/test_suest_Stata_parity.py |
| `super_learner` | index_known_truth | tests/reference_parity/test_ml_causal_recovery_parity.py |
| `support_points` | index_known_truth | tests/reference_parity/test_joseph_doe_parity.py |
| `surrogate_index` | index_known_truth | tests/reference_parity/test_surrogate_parity.py, tests/test_surrogate.py |
| `survival_forest` | index_known_truth | tests/reference_parity/test_grf_family_statistical_parity.py |
| `survival_sensitivity` | index_known_truth | tests/reference_parity/test_misc_sens_R_parity.py |
| `svar` | index_known_truth, reference_parity | tests/external_parity/test_neusser_time_series.py, tests/reference_parity/test_textbook_syllabus_stata_parity.py, tests/reference_parity/test_ts_causal_parity.py |
| `svrepdesign` | index_known_truth | tests/reference_parity/test_survey_replicate_parity.py |
| `swig` | index_known_truth | tests/reference_parity/test_oct2026_second_pass.py, tests/test_dag_scm.py, tests/test_transport.py |
| `swilk` | index_known_truth, reference_parity | tests/external_parity/test_maitra_static_dynamic.py, tests/reference_parity/test_dynamic_modelling_parity.py, tests/reference_parity/test_textbook_syllabus_stata_parity.py |
| `switchback` | index_known_truth | tests/external_parity/test_facure_causal_inference_in_python.py |
| `switchback_design` | index_known_truth | tests/reference_parity/test_oct2026_reanchor_known_truth.py |
| `synth_compare` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py |
| `synth_experimental_design` | index_known_truth | tests/reference_parity/test_synth_rest_R_parity.py, tests/test_api_stable_evidence.py |
| `synth_mde` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py |
| `synth_power` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py |
| `synth_recommend` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py |
| `synth_report` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py |
| `synth_sensitivity` | index_known_truth | tests/reference_parity/test_oct2026_fifth_pass.py |
| `synth_survival` | index_known_truth | tests/reference_parity/test_synth_rest_R_parity.py, tests/test_synth_survival.py |
| `synth_ttest` | index_known_truth | tests/reference_parity/test_oct2026_reanchor_known_truth.py |
| `synthdid_placebo` | index_known_truth | tests/reference_parity/test_oct2026_fourth_pass.py |
| `tab` | index_known_truth | tests/reference_parity/test_textbook_syllabus_stata_parity.py |
| `target_trial_checklist` | index_known_truth | tests/reference_parity/test_target_trial_parity.py, tests/test_api_stable_evidence.py |
| `target_trial_emulate` | index_known_truth | tests/reference_parity/test_target_trial_parity.py |
| `target_trial_protocol` | index_known_truth | tests/reference_parity/test_target_trial_parity.py, tests/test_tierD_p2_target_trial_analytic.py, tests/test_v100_integration.py |
| `target_trial_report` | index_known_truth | tests/reference_parity/test_target_trial_parity.py, tests/test_api_stable_evidence.py |
| `tarnet` | index_known_truth | tests/reference_parity/test_oct2026_fourth_pass.py, tests/test_neural_causal.py, tests/test_neural_causal_exports.py |
| `te_rank` | index_known_truth | tests/reference_parity/test_closed_form_identities.py |
| `te_summary` | index_known_truth | tests/reference_parity/test_closed_form_identities.py |
| `threshold` | index_known_truth, reference_parity | tests/external_parity/test_hansen_econometrics_logs.py, tests/reference_parity/test_hansen_methods_stata_parity.py |
| `tighten_blocks` | index_known_truth | tests/reference_parity/test_rosenbaum_itos_parity.py |
| `translog_design` | index_known_truth | tests/reference_parity/test_translog_design_parity.py |
| `transport_generalize` | index_known_truth | tests/reference_parity/test_transport_parity.py |
| `trimming` | index_known_truth, reference_parity | tests/external_parity/test_barrett_causal_inference_in_r.py, tests/reference_parity/test_barrett_causal_inference_in_r_parity.py, tests/reference_parity/test_closed_form_identities.py |
| `truncated_product` | index_known_truth | tests/reference_parity/test_rosenbaum_itos_parity.py |
| `ts_features` | index_known_truth | tests/reference_parity/test_forecasting_r_parity.py |
| `tscv` | index_known_truth, reference_parity | tests/external_parity/test_hyndman_fpp_pythonic.py, tests/reference_parity/test_forecasting_r_parity.py |
| `ttest` | index_known_truth, reference_parity | tests/external_parity/test_ding_first_course.py, tests/reference_parity/test_difference_in_means_estimatr.py, tests/reference_parity/test_dynamic_modelling_parity.py, tests/reference_parity/test_ttest_known_values.py, tests/reference_parity/test_yuksel_aydede_causal_ml_parity.py |
| `tune_causal_forest` | index_known_truth | tests/test_tune_causal_forest.py |
| `twfe_decomposition` | index_known_truth | tests/reference_parity/test_dcdh_textbook_stata_parity.py |
| `two_criteria_match` | index_known_truth | tests/reference_parity/test_rosenbaum_itos_parity.py |
| `twowayfeweights` | index_known_truth, reference_parity | tests/external_parity/test_dcdh_did_textbook.py, tests/reference_parity/test_dcdh_textbook_stata_parity.py |
| `uniform_bands` | index_known_truth | tests/reference_parity/test_event_study_vcov_R_parity.py, tests/test_es_inference.py |
| `unitroot` | index_known_truth, reference_parity | tests/external_parity/test_hyndman_fpp_pythonic.py, tests/reference_parity/test_dynamic_modelling_parity.py, tests/reference_parity/test_hansen_methods_stata_parity.py, tests/reference_parity/test_textbook_syllabus_stata_parity.py |
| `validation_scope` | index_known_truth | tests/reference_parity/test_cs_options_R_parity.py |
| `variable_importance` | index_known_truth | tests/reference_parity/test_grf_family_operator_parity.py |
| `varsoc` | index_known_truth, reference_parity | tests/external_parity/test_hyndman_fpp_pythonic.py, tests/reference_parity/test_hansen_methods_stata_parity.py, tests/reference_parity/test_textbook_methods_stata_parity.py |
| `vcnet` | index_known_truth | tests/reference_parity/test_oct2026_third_pass.py |
| `vcov` | index_known_truth | tests/reference_parity/test_fixest_postestimation_parity.py |
| `vcov_compare` | index_known_truth | tests/reference_parity/test_vcov_refit_identity.py |
| `vec` | index_known_truth, reference_parity | tests/external_parity/test_dogan_python_econometrics.py, tests/reference_parity/test_dynamic_modelling_parity.py, tests/reference_parity/test_textbook_methods_stata_parity.py |
| `weighted_conformal_prediction` | index_known_truth | tests/reference_parity/test_conformal_causal_parity.py |
| `weighted_rank` | index_known_truth | tests/reference_parity/test_rosenbaum_itos_parity.py |
| `weighted_rank_power` | index_known_truth | tests/reference_parity/test_rosenbaum_itos_parity.py |
| `weightit` | index_known_truth | tests/reference_parity/test_weightit_cobalt_parity.py |
| `westfall_young` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py |
| `winsor` | index_known_truth, reference_parity | tests/external_parity/test_gow_ding_accounting.py, tests/reference_parity/test_accounting_research_parity.py, tests/reference_parity/test_winsor_winsor2_Stata_parity.py |
| `wooldridge_prod` | index_known_truth, reference_parity | tests/reference_parity/test_prodest_parity.py, tests/reference_parity/test_structural_parity.py, tests/test_prod_fn.py |
| `xlearner` | index_known_truth | tests/reference_parity/test_ml_causal_recovery_parity.py |
| `xtevent` | index_known_truth | tests/reference_parity/test_xtevent_Stata_parity.py |
| `xtevent_smpath` | index_known_truth | tests/reference_parity/test_xtevent_smpath_Stata_screen.py |
| `xthtaylor` | index_known_truth | tests/reference_parity/test_hansen_methods_stata_parity.py |
| `xtoverid` | index_known_truth | tests/reference_parity/test_textbook_methods_stata_parity.py |
| `xtserial` | index_known_truth | tests/reference_parity/test_textbook_methods_stata_parity.py |
| `xtsum` | index_known_truth | tests/reference_parity/test_textbook_methods_stata_parity.py |
| `yatchew_linearity_test` | index_known_truth | tests/reference_parity/test_did_had_parity.py |
| `yun_nonlinear` | index_known_truth | tests/reference_parity/test_closed_form_identities.py |
| `zero_first_stage` | index_known_truth | tests/reference_parity/test_frontier_known_truth_recovery.py, tests/test_zero_first_stage.py |
| `ztest` | index_known_truth | tests/reference_parity/test_textbook_syllabus_stata_parity.py |

Machine-readable detail: `replication/results/validation_evidence_audit.json`

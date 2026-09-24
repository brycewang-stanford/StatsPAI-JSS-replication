# Validation Evidence Audit

Status: PASS
Registry symbols: 1220
Certified/validated symbols: 556 (certified=414, validated=142)
Missing validation notes: 0
Evidence path references: 1467 refs / 427 unique paths
Evidence path scope: certified/validated symbols only; the submission packager may include additional API-stable registry evidence files.
Missing evidence paths: 0
Certified without certified-grade evidence: 0
Validated without validated-grade evidence: 0
Supplemental-only certified/validated symbols: 0
Symbols with supplemental notes: 168
Symbols with limitations: 21

## Qualifying Evidence Note Kinds

- external_parity: 7 symbols (8 note instances)
- index_cross_language: 415 symbols (463 note instances)
- index_known_truth: 149 symbols (149 note instances)
- r_parity: 88 symbols (100 note instances)
- reference_parity: 461 symbols (687 note instances)
- stata_parity: 84 symbols (96 note instances)

## Supplemental Evidence Note Kinds

These notes are reported for transparency but do not, by themselves, satisfy a certified or validated status label.
- api_unit_contract: 136 symbols (160 note instances)
- documented_parity_gap: 1 symbols (1 note instances)
- other: 1 symbols (2 note instances)
- track_a_seed: 31 symbols (31 note instances)
- variant_certification: 3 symbols (3 note instances)

## Symbols With Scoped Limitations

These rows keep certified/validated evidence scoped rather than presenting blanket parity or validation claims.

| Symbol | Status | Status-grade evidence kinds | Limitation scope |
| --- | --- | --- | --- |
| `callaway_santanna` | certified | index_cross_language, r_parity, stata_parity | clustervars is not yet supported with bstrap=False; the analytic standard errors do not account for within-cluster dependence, so the multiplier bootstrap is required |
| `causal_forest` | certified | index_cross_language, r_parity | The AIPW ATE/ATT are validated against grf on clean-overlap designs only; under severe propensity-overlap loss the AIPW influence function inflates the standard error (conservative, over-covering inference), so inspect the sp.audit overlap diagnostic before interpreting the ATE on that kind of sample; The forest is compared with grf only statistically (tier T3: RMSE, pointwise variances, coverage), not bit-for-bit; given a fitted forest, the inference operators match grf / sandwich to 1e-14; Doubly-robust averages (average_treatment_effect, best_linear_projection, rate) are not implemented for fe= forests, which have no propensity score; use sp.did_forest for group-time averages; For fe= forests the calibration slope tests for heterogeneity only; it comes from a globally within-transformed regression and does not de-attenuate CATE predictions |
| `cgs_continuous_did` | certified | index_cross_language, r_parity | standard errors come from the per-cell influence function; contdid routes its own through the pte aggregation layer, which is not implemented here; staggered designs aggregate cells with StatsPAI's own treated-count weights; only the per-cell estimator is pinned against the reference; the cck (nonparametric) dose estimator is not implemented |
| `continuous_did` | certified | index_cross_language | method='cgs' is an MVP -- 2-period design, OR only, bootstrap SE; full CGS parity (cohort aggregation, DR/IPW, analytical IF variance) is on the roadmap (see docs/rfc/continuous_did_cgs.md). Other modes (twfe / att_gt / dose_response) are stable |
| `ddd_heterogeneous` | certified | index_cross_language, r_parity | the placebo joint test is only produced on the bootstrap path; se='analytic' reports None for it, because that test needs the joint covariance of the placebo arms rather than of the DDD; control_group='notyettreated' is only partially comparable to triplediff 0.2.4: its per-control-cohort estimates agree exactly, but the reference misindexes the influence functions it combines, so the combined numbers differ by convention on cells where the comparison does not span the whole panel; the aggregation convention differs from triplediff::agg_ddd(type='simple'): the default weights cohorts by treated-eligible units; pass weight_by='cohort' to match the R package |
| `did_balance` | validated | index_known_truth, reference_parity | pooled multi-cohort balance is not implemented: one table per treated cohort only, because the normalized difference is a two-group statistic; only the reliability-weight variance correction is implemented for the weighted panel; survey-design (replicate-weight) variances are not supported; inference is not implemented: the normalized difference is reported as a descriptive effect size with no standard error or test, by design; the weighted denominator convention differs from cobalt::col_w_smd, which holds the pooled SD at its unweighted value; this follows Baker et al. (2026) instead, and the two coincide when unweighted |
| `did_imputation` | certified | index_cross_language, r_parity, stata_parity | R/Stata parity is for the documented untreated-only TWFE and simple ATT aggregation convention only; event-study and SE rows are backend-specific diagnostics |
| `distributional_did` | certified | index_cross_language | reports point estimates and standard errors only; the reference runs no test here and neither does this; simultaneous (uniform) confidence bands over bins are not implemented; the standard errors are pointwise only, so reading several bins at once overstates joint confidence |
| `dml` | certified | index_cross_language, r_parity, stata_parity | external_predictions, store_oof, and observation_ids are Python-only and absent from JSON/MCP inputs; external records accept no dict, JSON string, or file path; store_oof=True retains individual-level records for get_oof() and get_residuals() in memory only; ordinary serialization omits them; Retained IRM needs at least 10 rows per treatment arm in each training fold or raises DataInsufficient instead of fallback; internal explicit fold_indices require n_rep=1, while external repeated IRM records are allowed when the explicit partition is equivalent for every repeat |
| `etwfe` | certified | index_cross_language | cgroup='nevertreated' combined with panel=False (repeated cross-sections) is not yet supported; pass either panel=True with cgroup='nevertreated' or panel=False with cgroup='notyet'; family='poisson'/'logit' with xvar, panel=False, or cgroup='nevertreated' is not yet supported; these raise rather than being silently ignored; family='poisson'/'logit' reports an average marginal effect on the response scale (counts / probability) rather than a link-scale coefficient -- the R etwfe::emfx convention; weights= is not yet supported together with xvar or with family='poisson'/'logit'; both combinations raise; cgroup='nevertreated' combined with panel=False (repeated cross-sections) is not yet supported. Use panel=True with cgroup='nevertreated' or panel=False with cgroup='notyet' |
| `fect` | certified | index_cross_language, r_parity, stata_parity | Inference is resampling-only (unit bootstrap or jackknife on request); the default returns point estimates only; r and lam are user-supplied; fect's cross-validated choice of r / lambda is not yet supported |
| `functional_form_test` | certified | index_cross_language, r_parity | a large p-value is only a failure to reject, not evidence FOR functional-form insensitivity: the test has little power with few units or coarse bins; standard errors and the critical value are asymptotic; a bootstrap variant is not implemented |
| `hal_tmle` | validated | index_known_truth, reference_parity | variant='projection' raises NotImplementedError -- the Riesz-projection targeting step from Li-Qiu-Wang-vdL (2025) §3.2 is not yet ported (the v1.11.x code path was a no-op on the point estimate; see CHANGELOG). The implementation roadmap and parity-test gates are in docs/rfc/hal_tmle_projection.md |
| `match` | certified | index_cross_language | greedy nearest-neighbour matching without replacement is order-dependent: the m_order convention can differ across packages and materially moves the estimate (>5x spread on MatchIt::lalonde with Mahalanobis distance). m_order='data' and 'closest' reproduce MatchIt exactly; m_order='farthest' is StatsPAI's own dynamic rule and is not MatchIt-equivalent; bias_correction=True follows a different convention from Matching::Match's BiasAdjust: StatsPAI regresses on the full covariate vector with unweighted OLS over all controls, the reference regresses on the matching variables weighted by match counts, so bias-corrected estimates can differ from it by about 0.1%. The uncorrected estimate and its Abadie-Imbens standard error are exact |
| `network_exposure` | validated | index_known_truth, reference_parity | design='complete' is reserved but not implemented; passing it raises NotImplementedError. Use design='bernoulli' with p_treat=K/N as an approximation only if that matches the assignment mechanism you are willing to assume |
| `pretrends_equivalence` | validated | index_known_truth, reference_parity | the TOST is computed only when tost_threshold is supplied; there is no universal outcome-scale default, so it is not invented |
| `principal_strat` | certified | index_cross_language | Always-survivor SACE under encouragement design (Mealli & Pacini 2013, partial identification) is not yet implemented; only AIR / Wald LATE point estimates (τ_Y on outcome, τ_S on the post-treatment stratum) are reported when an instrument is supplied |
| `rddensity` | certified | index_cross_language, r_parity, stata_parity | Certified native reference-parity evidence covers the default rddensity::rddensity unrestricted triangular-kernel selector and test path on the JSS Lee/RD Senate fixture. Manual side-specific bandwidths follow an explicit user-control convention, not a reference-parity guarantee; backend='r' remains available when direct R package execution is required |
| `rdrobust` | certified | index_cross_language, r_parity, stata_parity | observation-level weights are not yet supported -- passing a weight column raises NotImplementedError; R-parity certification applies to bwselect='cct' or manually matched h/b bandwidths; the dependency-light default bwselect='mserd' uses StatsPAI's calibrated selector and can differ from rdrobust::rdrobust defaults |
| `spillover_did` | certified | index_cross_language | there is no reference implementation, so this carries design-recovery evidence only and no cross-language parity; ring boundaries are the analyst's choice; there is no selector, and a too-wide outer ring silently contaminates the clean controls; covariate adjustment is not implemented |
| `synth` | certified | index_cross_language, r_parity, stata_parity | Classical SCM certification is specification-specific: ADH/Synth parity requires passing the same special_predictors recipe; the default outcome-only V=I path is a documented Kaul-style convention; Default native classical SCM can differ from Synth on Basque-style panels by a documented local-optimum convention (the outer V optimisation has multiple near-equivalent minima); use backend='synth' or canonical special_predictors when exact R parity is required |

## Validated-Tier Symbols

| Symbol | Status-grade evidence kinds | Evidence paths |
| --- | --- | --- |
| `W` | index_known_truth, reference_parity | tests/reference_parity/test_spdep_parity.py |
| `aggte` | index_known_truth, reference_parity | tests/external_parity/test_honest_did_paper_parity.py, tests/reference_parity/test_aggte_mpdta_parity.py, tests/reference_parity/test_aggte_r_did_parity.py, tests/reference_parity/test_aggte_vcov_r_parity.py, tests/reference_parity/test_castle_stata_parity.py, tests/reference_parity/test_cs_base_period_parity.py |
| `aggte_from_influence` | index_known_truth, reference_parity | tests/reference_parity/test_aggte_r_did_parity.py, tests/test_cs_inference.py, tests/test_cs_rcs.py |
| `always_treat` | index_known_truth, reference_parity | tests/reference_parity/test_longitudinal_parity.py |
| `assimilative_causal` | index_known_truth, reference_parity | tests/reference_parity/test_assimilation_parity.py |
| `auto_cate` | index_known_truth, reference_parity | tests/reference_parity/test_ml_causal_recovery_parity.py |
| `auto_cate_tuned` | index_known_truth, reference_parity | tests/reference_parity/test_ml_causal_recovery_parity_round2.py |
| `bayes_iv` | index_known_truth, reference_parity | tests/reference_parity/test_bayes_diagnostics_parity.py, tests/test_bayes_iv.py, tests/test_bayes_iv_per_instrument.py |
| `bayes_rd` | index_known_truth, reference_parity | tests/reference_parity/test_bayes_diagnostics_parity.py, tests/test_bayes_rd.py |
| `bayes_synth` | index_known_truth, reference_parity | tests/reference_parity/test_bayes_synth_parity.py |
| `bcf` | index_known_truth, reference_parity | tests/reference_parity/test_bcf_parity.py |
| `bcf_factor_exposure` | index_known_truth, reference_parity | tests/reference_parity/test_bcf_factor_exposure_parity.py, tests/test_bcf_ordinal.py |
| `best_linear_projection` | index_known_truth, reference_parity | tests/reference_parity/test_grf_family_operator_parity.py |
| `beyond_average_late` | index_known_truth, reference_parity | tests/reference_parity/test_beyond_average_late_parity.py, tests/reference_parity/test_decomp_qte_parity.py, tests/reference_parity/test_dist_iv_parity.py, tests/test_v101_verified_fixes.py |
| `bidirectional_pci` | index_known_truth, reference_parity | tests/reference_parity/test_proximal_parity.py, tests/test_proximal_frontiers.py |
| `bootstrap` | index_known_truth, reference_parity | tests/reference_parity/test_bootstrap_parity.py, tests/test_round3.py |
| `boundary_rd` | index_known_truth, reference_parity | tests/reference_parity/test_rd_open_R_parity.py |
| `bradford_hill` | index_known_truth, reference_parity | tests/reference_parity/test_bradford_hill_parity.py, tests/test_epi.py |
| `breakdown_frontier` | index_known_truth, reference_parity | tests/reference_parity/test_breakdown_frontier_parity.py |
| `bunching` | index_known_truth, reference_parity | tests/reference_parity/test_bunching_parity.py |
| `bvar` | index_known_truth, reference_parity | tests/reference_parity/test_timeseries_R_parity.py, tests/reference_parity/test_timeseries_parity.py |
| `calibrate_cate` | index_known_truth, reference_parity | tests/reference_parity/test_panel_forest_recovery.py |
| `cardinality_match` | index_known_truth, reference_parity | tests/reference_parity/test_cardinality_match_parity.py |
| `causal_impact` | index_known_truth, reference_parity | tests/reference_parity/test_did_synth_misc_parity.py, tests/test_causal_impact.py |
| `causal_kalman` | index_known_truth, reference_parity | tests/reference_parity/test_assimilation_parity.py |
| `causal_policy_forest` | index_known_truth, reference_parity | tests/reference_parity/test_ope_parity.py, tests/test_ope_extensions.py |
| `causal_survival_forest` | index_known_truth, reference_parity | tests/reference_parity/test_grf_family_statistical_parity.py |
| `check_absorbing` | index_known_truth, reference_parity | tests/reference_parity/test_absorbing_reference.py |
| `clone_censor_weight` | index_known_truth, reference_parity | tests/reference_parity/test_target_trial_parity.py, tests/test_target_trial.py |
| `cluster_cate` | index_known_truth, reference_parity | tests/reference_parity/test_ml_causal_recovery_parity_round2.py |
| `cluster_cross_interference` | index_known_truth, reference_parity | tests/reference_parity/test_cluster_cross_interference_parity.py, tests/test_cluster_rct.py |
| `conformal_cate` | index_known_truth, reference_parity | tests/reference_parity/test_conformal_causal_parity.py |
| `conformal_fair_ite` | index_known_truth, reference_parity | tests/reference_parity/test_conformal_fair_ite_parity.py, tests/test_conformal_frontiers.py |
| `conformal_ite` | index_known_truth, reference_parity | tests/reference_parity/test_conformal_ite_parity.py |
| `conformal_ite_interval` | index_known_truth, reference_parity | tests/reference_parity/test_conformal_causal_parity.py |
| `continuous_iv_late` | index_known_truth, reference_parity | tests/reference_parity/test_continuous_iv_late_parity.py, tests/test_continuous_iv_late.py |
| `counterfactual_fairness` | index_known_truth, reference_parity | tests/reference_parity/test_fairness_parity.py, tests/test_fairness.py |
| `dag` | index_known_truth, reference_parity | tests/reference_parity/test_misc_sens_R_parity.py, tests/test_dag_recommend_and_tte_report.py, tests/test_dag_scm.py |
| `demographic_parity` | index_known_truth, reference_parity | tests/reference_parity/test_fairness_parity.py, tests/test_fairness.py |
| `did` | index_known_truth, reference_parity | tests/reference_parity/test_cs_weighted_parity.py, tests/reference_parity/test_did2x2_wild_parity.py, tests/reference_parity/test_did_parity.py, tests/reference_parity/test_sunab_weighted_parity.py, tests/test_did.py |
| `did_balance` | index_known_truth, reference_parity | tests/reference_parity/test_did_balance_parity.py |
| `did_forest` | index_known_truth, reference_parity | tests/reference_parity/test_panel_forest_recovery.py, tests/test_did_forest.py |
| `did_had` | index_known_truth, reference_parity | tests/reference_parity/test_did_had_parity.py |
| `dist_iv` | index_known_truth, reference_parity | tests/reference_parity/test_decomp_qte_parity.py, tests/reference_parity/test_dist_iv_parity.py |
| `distributional_te` | index_known_truth, reference_parity | tests/reference_parity/test_distributional_te_inference.py, tests/reference_parity/test_distributional_te_parity.py |
| `dml_diagnostics` | index_known_truth, reference_parity | tests/reference_parity/test_ml_causal_dml_parity.py |
| `dynamic_dml` | index_known_truth, reference_parity | tests/reference_parity/test_dynamic_dml_econml_parity.py |
| `equalized_odds` | index_known_truth, reference_parity | tests/reference_parity/test_fairness_parity.py, tests/test_fairness.py |
| `evidence_without_injustice` | index_known_truth, reference_parity | tests/reference_parity/test_fairness_parity.py, tests/test_api_stable_evidence.py |
| `fairness_audit` | index_known_truth, reference_parity | tests/reference_parity/test_fairness_parity.py, tests/test_fairness.py |
| `fci` | index_known_truth, reference_parity | tests/reference_parity/test_fci_parity.py |
| `focal_cate` | index_known_truth, reference_parity | tests/reference_parity/test_ml_causal_recovery_parity_round2.py |
| `forest_diagnostics` | index_known_truth, reference_parity | tests/reference_parity/test_ml_causal_R_parity.py |
| `forest_group_effects` | index_known_truth, reference_parity | tests/reference_parity/test_fe_forest_imputation_recovery.py, tests/test_forest_fe_imputation.py |
| `forest_policy_tree` | index_known_truth, reference_parity | tests/reference_parity/test_fe_forest_policy_recovery.py |
| `fortified_pci` | index_known_truth, reference_parity | tests/reference_parity/test_proximal_parity.py, tests/test_proximal_frontiers.py |
| `front_door` | index_known_truth, reference_parity | tests/reference_parity/test_front_door_parity.py, tests/test_front_door.py, tests/test_review_fixes_round2.py |
| `frontdoor` | index_known_truth, reference_parity | tests/reference_parity/test_frontdoor_parity.py |
| `general_bunching` | index_known_truth, reference_parity | tests/reference_parity/test_bunching_parity.py |
| `geolift` | index_known_truth, reference_parity | tests/reference_parity/test_geolift_parity.py |
| `ges` | index_known_truth, reference_parity | tests/reference_parity/test_ges_parity.py |
| `get_scores` | index_known_truth, reference_parity | tests/reference_parity/test_grf_family_operator_parity.py |
| `gformula_mc` | index_known_truth, reference_parity | tests/reference_parity/test_gformula_family_parity.py, tests/reference_parity/test_teffects_R_parity.py |
| `hal_tmle` | index_known_truth, reference_parity | tests/reference_parity/test_ml_causal_recovery_parity_round2.py, tests/test_hal_tmle.py |
| `hausman_test` | index_known_truth, reference_parity | tests/reference_parity/test_diag_recovery_parity.py |
| `honest_variance` | index_known_truth, reference_parity | tests/reference_parity/test_forest_rate_honest_parity.py, tests/reference_parity/test_ml_causal_R_parity.py |
| `identify_transport` | index_known_truth, reference_parity | tests/reference_parity/test_misc_sens_R_parity.py, tests/test_transport.py |
| `immortal_time_check` | index_known_truth, reference_parity | tests/reference_parity/test_target_trial_parity.py |
| `influence_functions` | index_known_truth, reference_parity | tests/reference_parity/test_aggte_r_did_parity.py, tests/test_cs_inference.py, tests/test_cs_rcs.py |
| `interference` | index_known_truth, reference_parity | tests/reference_parity/test_interference_parity.py, tests/test_dispatchers_v150.py |
| `iv_forest` | index_known_truth, reference_parity | tests/reference_parity/test_grf_family_operator_parity.py, tests/reference_parity/test_grf_family_statistical_parity.py |
| `ivqreg` | index_known_truth, reference_parity | tests/reference_parity/test_ivqreg_parity.py, tests/reference_parity/test_rd_iv_R_parity.py |
| `kan_dlate` | index_known_truth, reference_parity | tests/reference_parity/test_dist_iv_parity.py |
| `lasso_iv` | index_known_truth, reference_parity | tests/reference_parity/test_lasso_iv_parity.py |
| `lasso_select` | index_known_truth, reference_parity | tests/reference_parity/test_lasso_select_parity.py |
| `lingam` | index_known_truth, reference_parity | tests/reference_parity/test_causal_discovery_parity.py |
| `lm_forest` | index_known_truth, reference_parity | tests/reference_parity/test_grf_family_statistical_parity.py |
| `long_term_from_short` | index_known_truth, reference_parity | tests/reference_parity/test_surrogate_parity.py, tests/test_surrogate.py |
| `longitudinal_analyze` | index_known_truth, reference_parity | tests/reference_parity/test_longitudinal_parity.py, tests/test_longitudinal.py |
| `longitudinal_contrast` | index_known_truth, reference_parity | tests/reference_parity/test_longitudinal_parity.py, tests/test_longitudinal.py |
| `lpbwselect_mse_dpi` | index_known_truth, reference_parity | tests/reference_parity/test_did_had_parity.py, tests/reference_parity/test_lprobust_parity.py |
| `lprobust_at_point` | index_known_truth, reference_parity | tests/reference_parity/test_lprobust_parity.py |
| `ltmle_survival` | index_known_truth, reference_parity | tests/reference_parity/test_ml_causal_recovery_parity_round2.py |
| `machado_mata` | index_known_truth, reference_parity | tests/reference_parity/test_decomp_qte_parity.py |
| `matrix_completion` | index_known_truth, reference_parity | tests/reference_parity/test_matrix_completion_parity.py |
| `metafrontier` | index_known_truth, reference_parity | tests/reference_parity/test_frontier_efficiency_parity.py, tests/reference_parity/test_frontier_struct_R_parity.py |
| `mice` | index_known_truth, reference_parity | tests/reference_parity/test_imputation_parity.py |
| `mr_lap` | index_known_truth, reference_parity | tests/reference_parity/test_mr_lap_parity.py, tests/test_mr_frontier.py |
| `multi_arm_forest` | index_known_truth, reference_parity | tests/reference_parity/test_grf_family_statistical_parity.py |
| `network_exposure` | index_known_truth, reference_parity | tests/reference_parity/test_interference_parity.py, tests/test_dispatchers_v150.py |
| `network_graph` | index_known_truth, reference_parity | tests/reference_parity/test_network_parity.py, tests/test_network.py |
| `never_treat` | index_known_truth, reference_parity | tests/reference_parity/test_longitudinal_parity.py |
| `notch` | index_known_truth, reference_parity | tests/reference_parity/test_notch_parity.py |
| `notears` | index_known_truth, reference_parity | tests/reference_parity/test_causal_discovery_parity.py |
| `orthogonal_to_bias` | index_known_truth, reference_parity | tests/reference_parity/test_fairness_parity.py, tests/test_fairness.py |
| `parallel_trends_robustness` | external_parity, index_known_truth | tests/external_parity/test_rebel_canal_published.py |
| `particle_filter` | index_known_truth | tests/reference_parity/test_assimilation_parity.py |
| `pate` | index_known_truth, reference_parity | tests/reference_parity/test_pate_parity.py |
| `pc_algorithm` | index_known_truth, reference_parity | tests/reference_parity/test_causal_discovery_parity.py |
| `peer_effects` | index_known_truth, reference_parity | tests/reference_parity/test_peer_effects_parity.py |
| `policy_weight_ate` | index_known_truth, reference_parity | tests/reference_parity/test_policy_weight_parity.py |
| `policy_weight_marginal` | index_known_truth, reference_parity | tests/reference_parity/test_policy_weight_parity.py |
| `policy_weight_observed_prte` | index_known_truth, reference_parity | tests/reference_parity/test_policy_weight_parity.py |
| `policy_weight_subsidy` | index_known_truth, reference_parity | tests/reference_parity/test_policy_weight_parity.py |
| `power_ols` | index_known_truth, reference_parity | tests/reference_parity/test_recovery_batch_parity.py |
| `pretrends_equivalence` | index_known_truth, reference_parity | tests/reference_parity/test_fect_equivalence_parity.py |
| `prod_fn` | index_known_truth, reference_parity | tests/reference_parity/test_structural_parity.py, tests/test_prod_fn.py |
| `proximal` | index_known_truth, reference_parity | tests/reference_parity/test_proximal_parity.py, tests/test_proximal.py |
| `proximal_surrogate_index` | index_known_truth, reference_parity | tests/reference_parity/test_surrogate_parity.py, tests/test_surrogate.py |
| `qte_hd_panel` | index_known_truth, reference_parity | tests/reference_parity/test_hd_panel_qte.py |
| `quantile_forest` | index_known_truth, reference_parity | tests/reference_parity/test_grf_family_statistical_parity.py |
| `quasi_untreated_test` | index_known_truth, reference_parity | tests/reference_parity/test_did_had_parity.py |
| `rate_split` | index_known_truth, reference_parity | tests/reference_parity/test_fe_forest_rate_recovery.py, tests/test_forest_rate_fe.py |
| `regime` | index_known_truth, reference_parity | tests/reference_parity/test_longitudinal_parity.py, tests/test_longitudinal.py |
| `romano_wolf` | index_known_truth, reference_parity | tests/reference_parity/test_romano_wolf_parity.py |
| `selection_bounds` | index_known_truth, reference_parity | tests/reference_parity/test_selection_bounds_parity.py |
| `sequential_sdid` | index_known_truth, reference_parity | tests/reference_parity/test_synth_rest_R_parity.py, tests/test_sequential_sdid.py |
| `sharp_ope_unobserved` | index_known_truth, reference_parity | tests/reference_parity/test_ope_parity.py, tests/test_ope_extensions.py |
| `spatial_did` | index_known_truth, reference_parity | tests/reference_parity/test_spatial_models_parity.py, tests/reference_parity/test_spillover_rings.py |
| `spillover` | index_known_truth, reference_parity | tests/reference_parity/test_interference_parity.py, tests/test_dispatchers_v150.py, tests/test_phase9to14.py |
| `stepwise` | index_known_truth, reference_parity | tests/reference_parity/test_stepwise_parity.py |
| `stochastic_dominance` | index_known_truth, reference_parity | tests/reference_parity/test_distributional_te_parity.py |
| `super_learner` | index_known_truth, reference_parity | tests/reference_parity/test_ml_causal_recovery_parity.py |
| `surrogate_index` | index_known_truth, reference_parity | tests/reference_parity/test_surrogate_parity.py, tests/test_surrogate.py |
| `survival_forest` | index_known_truth, reference_parity | tests/reference_parity/test_grf_family_statistical_parity.py |
| `survival_sensitivity` | index_known_truth, reference_parity | tests/reference_parity/test_misc_sens_R_parity.py |
| `synth_experimental_design` | index_known_truth, reference_parity | tests/reference_parity/test_synth_rest_R_parity.py, tests/test_api_stable_evidence.py |
| `synth_power` | index_known_truth, reference_parity | tests/reference_parity/test_synth_rest_R_parity.py |
| `synth_survival` | index_known_truth, reference_parity | tests/reference_parity/test_synth_rest_R_parity.py, tests/test_synth_survival.py |
| `target_trial_checklist` | index_known_truth, reference_parity | tests/reference_parity/test_target_trial_parity.py, tests/test_api_stable_evidence.py |
| `target_trial_emulate` | index_known_truth, reference_parity | tests/reference_parity/test_target_trial_parity.py |
| `target_trial_protocol` | index_known_truth, reference_parity | tests/reference_parity/test_target_trial_parity.py, tests/test_tierD_p2_target_trial_analytic.py, tests/test_v100_integration.py |
| `target_trial_report` | index_known_truth, reference_parity | tests/reference_parity/test_target_trial_parity.py, tests/test_api_stable_evidence.py |
| `translog_design` | index_known_truth, reference_parity | tests/reference_parity/test_translog_design_parity.py |
| `transport_generalize` | index_known_truth, reference_parity | tests/reference_parity/test_transport_parity.py |
| `twfe_decomposition` | index_known_truth, reference_parity | tests/reference_parity/test_did_synth_R_parity.py |
| `validation_scope` | index_known_truth, reference_parity | tests/reference_parity/test_iv_card_aer_parity.py |
| `variable_importance` | index_known_truth, reference_parity | tests/reference_parity/test_grf_family_operator_parity.py |
| `weighted_conformal_prediction` | index_known_truth, reference_parity | tests/reference_parity/test_conformal_causal_parity.py |
| `wooldridge_prod` | index_known_truth, reference_parity | tests/reference_parity/test_prodest_parity.py, tests/reference_parity/test_structural_parity.py, tests/test_prod_fn.py |
| `xlearner` | index_known_truth, reference_parity | tests/reference_parity/test_ml_causal_recovery_parity.py |
| `yatchew_linearity_test` | index_known_truth, reference_parity | tests/reference_parity/test_did_had_parity.py |

Machine-readable detail: `replication/results/validation_evidence_audit.json`

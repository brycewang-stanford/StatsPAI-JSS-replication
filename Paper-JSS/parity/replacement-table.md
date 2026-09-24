# StatsPAI to R / Stata replacement table

**Generated file — do not edit by hand.** Regenerate with:

```bash
cd Paper-JSS
python replication/scripts/build_replacement_table.py
python replication/scripts/build_replacement_table.py --check   # drift check
```

This is the audit-grade detail behind the coverage table in the
manuscript's architecture section. Each row states which R package or Stata
command a StatsPAI entry point is meant to replace, what kind of
relationship that is, and — this is the part no human hand-maintains — what
committed numerical evidence backs it.

The Evidence column is derived, never asserted. Every `sp.` name in the
table is checked against the live registry (`statspai.list_functions()`),
and the tier and test path come from `src/statspai/_parity_index.json`,
which is itself generated from the committed parity artifacts by
`scripts/build_parity_index.py`. A row naming a function that does not
exist renders as a hard failure and makes the generator exit non-zero, so
the table cannot drift back into advertising `sp.` entry points a reader
cannot call.

## Reading the columns

**Relationship** is editorial judgement about scope:

- **equivalent** — same estimand and same default options as the reference.
- **subset** — a documented subset of the reference's option surface.
- **superset** — all of the reference's options plus additional methodology.
- **partial** — implemented, but the cross-language comparison is not
  like-for-like (different estimand, convention, or no packaged reference).
- **new** — no canonical reference implementation exists to compare against.

**Evidence** is the strongest committed numerical artifact across the row's
entry points:

- **bit-exact** — matches a named R or Stata reference to the machine
  tolerance tier (rel ≤ 1e-6) on identical CSV bytes.
- **aligned** — matches a named reference inside a documented looser
  tolerance (iterative, cross-fit, or methodological tier).
- **published** — reproduces published paper numbers.
- **analytical** — recovers a known population parameter or closed-form
  identity on a deterministic DGP; no cross-package reference exists.
- **test-covered, not tier-graded** — a committed test exercises the
  function, but the parity index carries no graded artifact for it. This is
  weaker than a tolerance-checked comparison and is labelled separately so
  it cannot be read as one.
- **no numerical evidence registered** — the function is registered and
  callable but carries no qualifying numerical artifact and no test names
  it directly. This is stated rather than hidden; it is the honest reading
  of the API-stable tier.

A row whose evidence is *analytical* is not a weaker version of a
cross-language check. For estimators with no reference implementation
anywhere — `sp.das_gupta`, `sp.zisf`, the neural-causal family — recovery of
a known truth on a controlled DGP is the only evidence that can exist.

## Summary

- Rows: 149
- Relationship: 130 equivalent; 1 subset; 5 superset; 7 partial; 6 new
- Evidence tier: 121 bit-exact; 16 aligned; 7 test-covered, not tier-graded; 5 analytical

## Table

| Domain | R package / function | Stata command | StatsPAI | Relationship | Evidence |
| --- | --- | --- | --- | --- | --- |
| OLS | `stats::lm`, `sandwich::vcovHC` | `regress, robust` | `sp.regress` | equivalent | **bit-exact** — vs `lm + sandwich::vcovHC` — `tests/r_parity/01_ols.py` |
| OLS clusters | `sandwich::vcovCL` | `regress, vce(cluster id)` | `sp.regress(vce="cluster", cluster_id=...)` | equivalent | **bit-exact** — vs `lm + sandwich::vcovHC` — `tests/r_parity/01_ols.py` |
| Robust SE family (HC2/HC3) | `sandwich::vcovHC` | `regress, vce(hc2)`/`vce(hc3)` | `sp.regress(robust="hc2"|"hc3")` | equivalent | **bit-exact** — vs `lm + sandwich::vcovHC` — `tests/r_parity/01_ols.py` |
| Multiway cluster SE | `sandwich::vcovCL` | `vcemway`, `reghdfe` | `sp.multiway_cluster_vcov`, `sp.twoway_cluster` | equivalent | **bit-exact** — vs `sandwich::vcovCL(cluster=~g1+g2+g3)` — `tests/r_parity/56_multiway_cluster.py` Stata side is an audited CGM/Mata bridge; `reghdfe` SEs kept as a diagnostic row |
| CR2/CR3 cluster SE | `clubSandwich::vcovCR` | --- (Stata built-in is CR1) | `sp.cr2_se`, `sp.cr3_jackknife_vcov` | superset | **bit-exact** — vs `clubSandwich::vcovCR(type="CR2"/"CR3")` — `tests/r_parity/53_cr2.py` Stata has no built-in CR2/CR3; the bridge implements clubSandwich's algebra |
| Wild cluster bootstrap | `fwildclusterboot::boottest` | `boottest` | `sp.wild_cluster_bootstrap`, `sp.wild_cluster_ci_inv` | equivalent | **bit-exact** — vs `R fwildclusterboot::boottest; Stata boottest (WCR, Rademacher, full enumeration)` — `tests/reference_parity/test_inference_sens_R_parity.py` |
| 2SLS | `AER::ivreg`, `ivreg::ivreg` | `ivregress 2sls` | `sp.iv` | equivalent | **bit-exact** — vs `AER::ivreg` — `tests/r_parity/02_iv.py` |
| LIML | `ivmodel::LIML` | `ivregress liml, small` | `sp.liml` | equivalent | **bit-exact** — vs `ivmodel::LIML` — `tests/r_parity/59_liml.py` |
| Anderson--Rubin weak-IV inference | `ivmodel::AR.test` | `weakiv` | `sp.anderson_rubin_test`, `sp.anderson_rubin_ci` | equivalent | **bit-exact** — vs `R ivmodel::AR.test` — `tests/reference_parity/test_weakiv_meta_parity.py` |
| JIVE / UJIVE | `SteinIV::jive.est` | `jive` | `sp.jive` | equivalent | **bit-exact** — vs `Stata jive 1.0.2 (Stata Journal st0108) ujive1 / ujive2` — `tests/reference_parity/test_rd_iv_R_parity.py` |
| GMM | `gmm::gmm` | `gmm` | `sp.gmm` | subset | **bit-exact** — vs `Stata 18 gmm (linear and exponential-mean IV; twostep, igmm, onestep); R gmm::gmm` — `tests/reference_parity/test_panel_gmm_stata_parity.py` linear and nonlinear moment conditions; Stata's `gmm` option surface is wider |
| Three-stage least squares | `systemfit::systemfit` | `reg3` | `sp.three_sls` | equivalent | **bit-exact** — vs `R systemfit::systemfit(method='3SLS')` — `tests/reference_parity/test_threesls_parity.py` |
| SUR | `systemfit::systemfit` | `sureg` | `sp.sureg` | equivalent | **bit-exact** — vs `systemfit::systemfit(method="SUR", noDfCor)` — `tests/r_parity/60_sureg.py` Sigma divisor n (`sureg` default / `noDfCor`) |
| HDFE FE | `fixest::feols` | `reghdfe` | `sp.feols`, `sp.hdfe_ols`, `sp.absorb_ols` | equivalent | **bit-exact** — vs `fixest::feols` — `tests/r_parity/03_hdfe.py` |
| HDFE Poisson | `fixest::fepois` | `ppmlhdfe` | `sp.ppmlhdfe`, `sp.fepois` | equivalent | **bit-exact** — vs `fixest::fepois` — `tests/r_parity/37_ppmlhdfe.py` |
| Panel: FE/RE | `plm::plm` | `xtreg, fe`/`xtreg, re` | `sp.panel(model="fe"|"re")` | equivalent | **bit-exact** — vs `plm::plm + plm::phtest` — `tests/r_parity/35_panel.py` |
| Panel: dynamic GMM | `plm::pgmm` | `xtabond`, `xtdpdsys` | `sp.xtabond`, `sp.xtdpdsys`, `sp.xtlsdvc` | equivalent | **bit-exact** — vs `plm::pgmm` — `tests/r_parity/50_xtabond.py` |
| Panel: FGLS | `plm::pggls` | `xtgls` | `sp.panel_fgls` | equivalent | **bit-exact** — vs `Stata 18 xtgls, panels(hetero)` — `tests/reference_parity/test_panel_stata_parity.py` |
| Panel: unit roots | `plm::purtest` | `xtunitroot` | `sp.panel_unitroot`, `sp.ips` | equivalent | **bit-exact** — vs `plm::purtest 2.6.7; Stata 18 xtunitroot` — `tests/reference_parity/test_timeseries_R_parity.py` |
| Newey--West HAC | `sandwich::NeweyWest` | `newey` | `sp.regress` | equivalent | **bit-exact** — vs `lm + sandwich::vcovHC` — `tests/r_parity/01_ols.py` |
| Probit/Logit | `stats::glm(family=binomial)` | `probit`, `logit` | `sp.probit`, `sp.logit`, `sp.glm` | equivalent | **bit-exact** — vs `stats::glm(family=binomial("probit"))` — `tests/r_parity/48_probit.py` |
| Poisson/NegBin | `stats::glm`, `MASS::glm.nb` | `poisson`, `nbreg` | `sp.poisson`, `sp.nbreg` | equivalent | **bit-exact** — vs `stats::glm(family=poisson())` — `tests/r_parity/58_poisson.py` |
| Zero-inflated count | `pscl::zeroinfl` | `zip`, `zinb` | `sp.zip_model`, `sp.zinb` | equivalent | **bit-exact** — vs `pscl::zeroinfl(dist="poisson")` — `tests/r_parity/63_zip.py` |
| Ordered / multinomial | `MASS::polr`, `nnet::multinom` | `ologit`, `oprobit`, `mlogit` | `sp.ologit`, `sp.oprobit`, `sp.mlogit` | equivalent | **bit-exact** — vs `MASS::polr(method="logistic")` — `tests/r_parity/45_ologit.py` |
| Conditional logit | `survival::clogit` | `clogit` | `sp.clogit` | equivalent | **bit-exact** — vs `survival::clogit` — `tests/r_parity/46_clogit.py` |
| Heckman | `sampleSelection::heckit` | `heckman` | `sp.heckman` | equivalent | **bit-exact** — vs `sampleSelection::heckit` — `tests/r_parity/43_heckman.py` |
| Tobit | `censReg::censReg` | `tobit` | `sp.tobit` | equivalent | **bit-exact** — vs `censReg::censReg` — `tests/r_parity/41_tobit.py` |
| Truncated regression | `truncreg::truncreg` | `truncreg, ll(0)` | `sp.truncreg` | equivalent | **bit-exact** — vs `truncreg::truncreg(method="NR")` — `tests/r_parity/62_truncreg.py` |
| Beta regression | `betareg::betareg` | `betareg` | `sp.betareg` | equivalent | **bit-exact** — vs `betareg::betareg(link.phi="log")` — `tests/r_parity/61_betareg.py` betareg SEs are expected-information (documented) |
| Fractional response | `stats::glm(quasibinomial)` | `fracreg` | `sp.fracreg` | equivalent | **bit-exact** — vs `stats::glm(quasibinomial('logit')) [fractional response]` — `tests/reference_parity/test_glm_ext_parity.py` |
| Quantile regression | `quantreg::rq` | `qreg`, `sqreg`, `ivqreg` | `sp.qreg`, `sp.sqreg`, `sp.ivqreg` | equivalent | **bit-exact** — vs `quantreg::rq` — `tests/r_parity/40_qreg.py` |
| Bivariate probit | `GJRM::gjrm` | `biprobit` | `sp.biprobit` | equivalent | **bit-exact** — vs `R VGAM::vglm(binom2.rho) bivariate probit` — `tests/reference_parity/test_biprobit_parity.py` |
| Endogenous treatment | `sampleSelection` | `etregress` | `sp.etregress` | equivalent | **bit-exact** — vs `Stata 18 MP official `etregress` (Maddala 1983 model)` — `tests/reference_parity/test_etregress_stata_parity.py` |
| **DiD: classical 2x2** | `did2s::did2s` | `didregress` | `sp.did_2x2` | equivalent | **bit-exact** — vs `Stata 18 MP regress [aw=w], robust (aweight HC1)` — `tests/reference_parity/test_did2x2_ddd_weighted_robust_parity.py` |
| **DiD: Callaway--Sant'Anna** | `did::att_gt` + `aggte` | `csdid` | `sp.callaway_santanna` + `sp.aggte` | equivalent | **bit-exact** — vs `did::att_gt + aggte` — `tests/r_parity/04_csdid.py` modulo the simple-ATT variance convention |
| **DiD: doubly robust 2x2** | `DRDID::drdid` | `drdid` | `sp.drdid` | equivalent | **bit-exact** — vs `DRDID::drdid_imp_panel` — `tests/r_parity/38_drdid.py` |
| **DiD: Sun--Abraham** | `fixest::sunab` | `eventstudyinteract` | `sp.sun_abraham` | equivalent | **bit-exact** — vs `fixest::sunab` — `tests/r_parity/05_sunab.py` |
| **DiD: Borusyak imputation** | `didimputation::did_imputation` | `did_imputation` | `sp.did_imputation`, `sp.bjs_pretrend_joint` | equivalent | **bit-exact** — vs `didimputation::did_imputation` — `tests/r_parity/16_bjs.py` |
| **DiD: Gardner two-stage** | `did2s::did2s` | `did2s` | `sp.gardner_did` | equivalent | **bit-exact** — vs `did2s::did2s` — `tests/r_parity/73_did2s.py` point estimate machine-level; SE is a documented convention gap |
| **DiD: dCDH DID_M** | `DIDmultiplegt` (0.1.4) | `did_multiplegt_old` | `sp.did_multiplegt` | equivalent | **bit-exact** — vs `DIDmultiplegt::did_multiplegt (archived 0.1.4)` — `tests/r_parity/81_didm.py` |
| **DiD: dCDH intertemporal** | `DIDmultiplegtDYN` | `did_multiplegt_dyn` | `sp.did_multiplegt_dyn` | equivalent | **bit-exact** — vs `DIDmultiplegtDYN::did_multiplegt_dyn` — `tests/r_parity/78_multiplegt_dyn.py` |
| **DiD: ETWFE** | `etwfe::etwfe` | `jwdid` | `sp.etwfe`, `sp.wooldridge_did` | equivalent | **bit-exact** — vs `etwfe::etwfe + emfx` — `tests/r_parity/17_etwfe.py` |
| **DiD: stacked** | hand-written `fixest` stack | hand-built stack + `reghdfe` | `sp.stacked_did` | equivalent | **bit-exact** — vs `hand-written stack + fixest::feols` — `tests/r_parity/75_stacked.py` no packaged owner in either language; all three sides are independent constructions |
| **DiD: triple differences** | `triplediff::ddd` | --- (no Stata package) | `sp.ddd`, `sp.ddd_heterogeneous` | equivalent | **bit-exact** — vs `Stata 18 MP regress [aw=w], robust (aweight HC1)` — `tests/reference_parity/test_did2x2_ddd_weighted_robust_parity.py` |
| **DiD: continuous treatment** | `contdid::cont_did` | --- (no Stata package) | `sp.continuous_did`, `sp.cgs_continuous_did` | equivalent | **bit-exact** — vs `fixest::feols(y ~ dose:post | id + time) (method='twfe')` — `tests/reference_parity/test_did_synth_didvar_parity.py` |
| **DiD: changes-in-changes** | `qte::CiC` | `cic` | `sp.cic` | equivalent | **aligned** — vs `qte::CiC` — `tests/r_parity/74_cic.py` documented inverse-CDF tie-break gap on the median and the ATT |
| **DiD: Honest** | `HonestDiD::createSensitivityResults_*` | `honestdid` | `sp.honest_did` | equivalent | **bit-exact** — vs `HonestDiD::createSensitivityResults (exact quantile) + closed form at M = 0` — `tests/r_parity/10_honest_did.py` |
| **DiD: pretrends power** | `pretrends::pretrends` | `pretrends` | `sp.pretrends_power`, `sp.pretrends_slope_for_power`, `sp.pretrends_test` | equivalent | **aligned** — vs `pretrends::pretrends / pretrends::slope_for_power (GitHub, not CRAN)` — `tests/r_parity/76_pretrends.py` |
| **DiD: functional-form test** | `didFF::didFF` | --- (no Stata package) | `sp.functional_form_test` | equivalent | **aligned** — vs `didFF::didFF` — `tests/r_parity/79_didff.py` |
| **DiD: Bacon decomposition** | `bacondecomp::bacon` | `bacondecomp` | `sp.bacon_decomposition` | equivalent | **bit-exact** — vs `bacondecomp::bacon` — `tests/r_parity/20_bacon.py` |
| **DiD: local projections** | `lpirfs`-style LP-DiD | `lpdid` | `sp.lp_did` | equivalent | **bit-exact** — vs `direct transcription (no LP-DiD R package installed); Stata side uses the authors' lpdid` — `tests/r_parity/83_lpdid.py` |
| **RD: bias-corrected robust** | `rdrobust::rdrobust` | `rdrobust` | `sp.rdrobust` | equivalent | **bit-exact** — vs `rdrobust::rdrobust` — `tests/r_parity/06_rd.py` |
| **RD: density manipulation** | `rddensity::rddensity` | `rddensity` | `sp.rddensity`, `sp.rdplotdensity` | equivalent | **bit-exact** — vs `rddensity::rddensity` — `tests/r_parity/09_rddensity.py` |
| **RD: bandwidth selection** | `rdrobust::rdbwselect` | `rdbwselect` | `sp.rdbwselect` | equivalent | **bit-exact** — vs `rdrobust::rdbwselect; Stata side uses the authors' rdbwselect ado. certwo is R-only: Stata rdbwselect 10.0.0 exits r(3200) on it, including on the package's own rdrobust_senate.dta` — `tests/r_parity/88_rdbwselect.py` |
| **RD: power / sample size** | `rdpower::rdpower` | `rdpower`, `rdsampsi` | `sp.rdpower`, `sp.rdsampsi` | equivalent | **bit-exact** — vs `rdpower::rdpower 3.0 (Cattaneo, Titiunik & Vazquez-Bare)` — `tests/reference_parity/test_rdlocrand_parity.py` |
| **RD: multi-cutoff / multi-score** | `rdmulti::rdmc`, `rdmulti::rdms` | `rdmc`, `rdms` | `sp.rdmc`, `sp.rdms` | equivalent | **bit-exact** — vs `rdmulti::rdmc 2.0.0 (Cattaneo, Titiunik, Vazquez-Bare & Keele)` — `tests/reference_parity/test_rdmulti_parity.py` |
| **RD: local randomization** | `rdlocrand::*` | `rdrandinf`, `rdwinselect` | `sp.rdrandinf`, `sp.rdwinselect`, `sp.rdsensitivity` | equivalent | **bit-exact** — vs `rdlocrand::rdrandinf 2.0 (Cattaneo, Titiunik & Vazquez-Bare)` — `tests/reference_parity/test_rdlocrand_parity.py` |
| **RD: heterogeneous effects** | `rdhte::rdhte` | `rdhte` | `sp.rdhte`, `sp.rdbwhte` | equivalent | **bit-exact** — vs `R rdhte::rdhte 0.2.0 (sandwich 3.1.1)` — `tests/reference_parity/test_rd_iv_rd_R_parity.py` |
| **RD: honest / bias-aware CIs** | `RDHonest::RDHonest` | --- | `sp.rd_honest` | equivalent | **bit-exact** — vs `RDHonest::RDHonest 1.0.1.9000 (Armstrong & Kolesar)` — `tests/reference_parity/test_rdhonest_parity.py` |
| **RD: kink design** | --- | --- | `sp.rkd`, `sp.kink_unified` | new | **bit-exact** — vs `R rdrobust::rdrobust(deriv = 1, vce = 'hc1') 4.0.0; Stata rdrobust, deriv(1) 11.1.0` — `tests/reference_parity/test_rd_iv_rd_R_parity.py` |
| **Synth: classical SCM** | `Synth::synth` | `synth` | `sp.synth(method="classic")` | equivalent | **bit-exact** — vs `Synth::synth` — `tests/r_parity/52_scm_unique.py` T4 disclosure: Basque donor weights are not uniquely identified |
| **Synth: SDID** | `synthdid::synthdid_estimate` | `sdid` | `sp.sdid`, `sp.synth(method="sdid")` | equivalent | **bit-exact** — vs `synthdid::synthdid_estimate` — `tests/r_parity/12_sdid.py` |
| **Synth: augmented SCM** | `augsynth::augsynth` | `allsynth` (different convention) | `sp.augsynth` | equivalent | **aligned** — vs `augsynth::augsynth` — `tests/r_parity/18_augsynth.py` |
| **Synth: generalised SCM** | `gsynth::gsynth` | `fect_stata` (different convention) | `sp.gsynth` | equivalent | **bit-exact** — vs `gsynth::gsynth` — `tests/r_parity/19_gsynth.py` |
| **Synth: SCPI inference** | `scpi::scpi` | `scpi` | `sp.scpi`, `sp.scest`, `sp.scdata` | equivalent | **bit-exact** — vs `R scpi::scdata (features = outcome, no cov.adj, constant = FALSE)` — `tests/reference_parity/test_did_synth_scpi_parity.py` |
| **Synth: BSTS / CausalImpact** | `CausalImpact::CausalImpact` | --- | `sp.causal_impact` | equivalent | **analytical** — `tests/reference_parity/test_did_synth_misc_parity.py` |
| **Synth: matrix completion** | `MCPanel::*` | --- | `sp.matrix_completion`, `sp.mc_panel` | partial | **bit-exact** — vs `MCPanel::mcnnm_fit (Athey, Bayati, Doudchenko, Imbens & Khosravi; github.com/susanathey/MCPanel) and fect::fect(method = "mc")` — `tests/reference_parity/test_did_synth_mc_parity.py` |
| **Synth: workflow** | `Synth::synth_runner` | `synth_runner` | `sp.synth_compare`, `sp.synth_recommend`, `sp.synth_sensitivity`, `sp.synth_report` | superset | test-covered, not tier-graded — `tests/test_cov95_synth_r2_exports.py` |
| **DML: PLR** | `DoubleML::DoubleMLPLR` | `ddml` | `sp.dml(model="plr")` | equivalent | **bit-exact** — vs `DoubleML::DoubleMLPLR` — `tests/r_parity/08_dml.py` |
| **DML: PLIV** | `DoubleML::DoubleMLPLIV` | `ddml init iv` | `sp.dml(model="pliv")` | equivalent | **bit-exact** — vs `DoubleML::DoubleMLPLR` — `tests/r_parity/08_dml.py` |
| **DML: IRM** | `DoubleML::DoubleMLIRM` | `ddml init interactive` | `sp.dml(model="irm")` | equivalent | **bit-exact** — vs `DoubleML::DoubleMLPLR` — `tests/r_parity/08_dml.py` |
| **DML: IIVM** | `DoubleML::DoubleMLIIVM` | `ddml init interactiveiv` | `sp.dml(model="iivm")` | equivalent | **bit-exact** — vs `DoubleML::DoubleMLPLR` — `tests/r_parity/08_dml.py` |
| **DML: sensitivity** | `DoubleML` sensitivity | --- | `sp.dml_sensitivity`, `sp.dml_diagnostics` | equivalent | **bit-exact** — vs `doubleml (Python) DoubleML.sensitivity_analysis` — `tests/external_parity/test_dml_sensitivity_parity.py` |
| **Causal forest** | `grf::causal_forest` | `cate` (Stata 19) | `sp.causal_forest` | equivalent | **aligned** — vs `grf::causal_forest` — `tests/r_parity/13_causal_forest.py` T3 combined-Monte-Carlo-error pass rather than a deterministic T2 claim |
| **Policy learning** | `policytree::policy_tree` | --- | `sp.policy_tree`, `sp.policy_value` | equivalent | **bit-exact** — vs `policytree::policy_tree` — `tests/r_parity/70_policy_tree.py` |
| **Meta-learners** | `causalToolbox::*`, `EconML` | --- | `sp.metalearner`, `sp.xlearner`, `sp.compare_metalearners` | equivalent | **bit-exact** — vs `econml.metalearners SLearner / TLearner / XLearner` — `tests/external_parity/test_metalearner_econml_parity.py` |
| **TMLE** | `tmle::tmle` | `eltmle` (wraps the same R package) | `sp.tmle`, `sp.ltmle`, `sp.hal_tmle` | equivalent | **bit-exact** — vs `tmle::tmle` — `tests/r_parity/72_tmle.py` |
| **BCF** | `bcf::bcf` | --- | `sp.bcf`, `sp.did_bcf` | equivalent | **analytical** — `tests/reference_parity/test_bcf_parity.py` |
| **Conformal causal inference** | `cfcausal::*` | --- | `sp.conformal_ite`, `sp.conformal_cate`, `sp.conformal_synth` | partial | **bit-exact** — vs `scinference (Chernozhukov-Wuthrich-Zhu authors' package, GitHub kwuthrich/scinference 567c688): estimation_method='sc', permutation_method='mb'` — `tests/reference_parity/test_synth_rest_R_parity.py` |
| **Rank-weighted ATE / RATE** | `grf::rank_average_treatment_effect` | --- | `sp.rate` | equivalent | **aligned** — vs `grf::rank_average_treatment_effect and rank_average_treatment_effect.fit 2.6.1 (AUTOC, QINI, TOC), forest outputs held fixed` — `tests/reference_parity/test_ml_causal_R_parity.py` |
| **Neural causal** | user `keras` code | --- | `sp.tarnet`, `sp.cfrnet`, `sp.dragonnet`, `sp.deepiv` | new | test-covered, not tier-graded — `tests/test_neural_causal.py` |
| **Causal discovery** | `pcalg::pc`, `bnlearn`, `pcalg::ges` | --- | `sp.pc_algorithm`, `sp.lingam`, `sp.notears`, `sp.ges`, `sp.fci` | partial | **analytical** — `tests/reference_parity/test_causal_discovery_parity.py` |
| **Matching: PSM 1:1** | `MatchIt::matchit(method="nearest")` | `psmatch2`, `teffects psmatch` | `sp.psm`, `sp.psmatch2` | equivalent | **bit-exact** — vs `MatchIt::matchit` — `tests/r_parity/11_psm.py` |
| **Matching: optimal / cardinality** | `MatchIt::matchit(method="optimal")` | `cem` (different method) | `sp.optimal_match`, `sp.cardinality_match` | partial | **aligned** — vs `optmatch::pairmatch 0.10.8 on a logit propensity score` — `tests/reference_parity/test_matching_r_parity.py` |
| **Matching: genetic** | `Matching::GenMatch` | --- | `sp.genmatch` | equivalent | **aligned** — vs `Matching::Match 4.10-15 (Weight = 3, Weight.matrix)` — `tests/reference_parity/test_matching_r_parity.py` |
| **Matching: CBPS** | `CBPS::CBPS` | `cbps` (user-contrib) | `sp.cbps` | equivalent | **aligned** — vs `CBPS::CBPS 0.24 (Imai & Ratkovic 2014)` — `tests/reference_parity/test_matching_r_parity.py` |
| **Weighting: entropy balancing** | `ebal::ebalance` | `ebalance` (user-contrib) | `sp.ebalance` | equivalent | **bit-exact** — vs `ebal::ebalance 0.2.1 (Hainmueller 2012)` — `tests/reference_parity/test_matching_r_parity.py` |
| **Weighting: stable balancing** | `sbw::sbw` | --- | `sp.sbw` | equivalent | **bit-exact** — vs `sbw::sbw 1.2 (Zubizarreta 2015), quadprog solver` — `tests/reference_parity/test_matching_r_parity.py` |
| **Weighting: overlap** | `PSweight::*` | --- | `sp.overlap_weights`, `sp.trimming` | equivalent | **bit-exact** — vs `WeightIt::weightit 1.7.0 (method='glm'), R 4.5.2` — `tests/reference_parity/test_overlap_weights_r_parity.py` |
| **IPW** | `WeightIt::weightit` | `teffects ipw` | `sp.ipw` | equivalent | **bit-exact** — vs `base R stats::glm(binomial) + hand-rolled Hajek weighted means` — `tests/reference_parity/test_ipw_parity.py` |
| **AIPW / doubly robust** | `AIPW::AIPW` | `teffects aipw`, `teffects ipwra` | `sp.aipw`, `sp.doubly_robust` | equivalent | **bit-exact** — vs `Stata teffects aipw (ATE, POmeans); R AIPW::AIPW 0.6.9.3 stratified_fit(k_split = 1)` — `tests/reference_parity/test_teffects_R_parity.py` |
| **Balance diagnostics** | `cobalt::bal.tab` | `pstest` | `sp.balance_diagnostics`, `sp.love_plot`, `sp.ps_balance` | equivalent | test-covered, not tier-graded — `tests/test_notebook_11_1_fixes.py` |
| **Decomposition: Oaxaca** | `oaxaca::oaxaca`, `ddecompose::oaxaca_blinder_decomposition` | `oaxaca` | `sp.decompose(method="oaxaca")`, `sp.oaxaca` | superset | **bit-exact** — vs `oaxaca::oaxaca` — `tests/r_parity/30_oaxaca.py` five reference conventions |
| **Decomposition: RIF** | `dineq::rif`, `rifreg` | `rifhdreg` | `sp.rifreg`, `sp.rif_decomposition` | equivalent | **bit-exact** — vs `R rifreg::rifreg (variance, quantiles) and dineq::rif + lm (Gini)` — `tests/reference_parity/test_decomp_R_parity.py` |
| **Decomposition: DFL** | `ddecompose` | `dfl` (user-contrib) | `sp.dfl_decompose` | equivalent | **bit-exact** — vs `ddecompose::dfl_decompose` — `tests/r_parity/31_dfl.py` |
| **Decomposition: Gelbach** | --- | `b1x2` | `sp.gelbach` | equivalent | **bit-exact** — vs `Stata b1x2 (Gelbach's own command), robust and homoskedastic` — `tests/reference_parity/test_decomp_R_parity.py` |
| **Decomposition: inequality indices** | `ineq::Theil`, `IC2` | `ineqdec0` | `sp.inequality_index`, `sp.shapley_inequality` | equivalent | **bit-exact** — vs `base-R closed form (Gini/Theil-T/Theil-L/Atkinson; = ineq)` — `tests/reference_parity/test_inequality_parity.py` |
| **Decomposition: Machado--Mata** | `Counterfactual::*` | `cdeco` | `sp.machado_mata`, `sp.melly_decompose` | equivalent | **bit-exact** — vs `Stata cdeco, method(qr) 1.0.2 (Chernozhukov, Fernandez-Val & Melly; bmelly/Stata counterfactual)` — `tests/reference_parity/test_decomp_qte_parity.py` |
| **Decomposition: Fairlie** | `oaxaca` nonlinear | `fairlie` | `sp.fairlie`, `sp.yun_nonlinear` | equivalent | **bit-exact** — vs `Stata fairlie 1.0.7 (Jann, SSC)` — `tests/reference_parity/test_decomp_qte_parity.py` |
| **Decomposition: gap closing** | `gapclosing::gapclosing` | --- | `sp.gap_closing` | equivalent | **bit-exact** — vs `R ddecompose::dfl_decompose (method='ipw') and ob_decompose (method='regression')` — `tests/reference_parity/test_decomp_R_parity.py` |
| **Decomposition: Das Gupta** | --- | --- | `sp.das_gupta` | new | **bit-exact** — vs `R DasGuptR::dgnpop (product rate function, summed over strata)` — `tests/reference_parity/test_decomp_R_parity.py` |
| **Frontier: cross-section** | `frontier::sfa`, `sfaR::sfacross` | `frontier` | `sp.frontier` | equivalent | **bit-exact** — vs `sfaR::sfacross` — `tests/r_parity/28_frontier.py` |
| **Frontier: panel** | `frontier::sfa` (panel) | `xtfrontier` | `sp.xtfrontier` | equivalent | **aligned** — vs `frontier::sfa` — `tests/r_parity/29_panel_sfa.py` |
| **Frontier: latent class** | `sfaR::sfalcmcross` | --- | `sp.lcsf` | equivalent | **aligned** — vs `sfaR::sfalcmcross 1.0.1 (2 classes, half-normal)` — `tests/reference_parity/test_frontier_struct_R_parity.py` |
| **Frontier: zero-inflated** | --- | --- | `sp.zisf` | new | **aligned** — vs `Stata chks 1.1 (estimation(zsf) eoption(ml)); R sfa::zsfm 1.2.0 (ZISF / ZISF_Z, likelihood at its optimum)` — `tests/reference_parity/test_r2_frontier_parity.py` |
| **Frontier: Malmquist TFP** | `Benchmarking::malmquist` | --- | `sp.malmquist` | equivalent | **aligned** — vs `sfaR::sfacross 1.0.1 per period + sfaR::efficiencies (teBC / teJLMS); TC from sfaR betas` — `tests/reference_parity/test_r2_frontier_parity.py` |
| **Mixed: LMM** | `lme4::lmer`, `nlme::lme` | `mixed` | `sp.mixed` | equivalent | **bit-exact** — vs `lme4::lmer` — `tests/r_parity/25_lmm.py` |
| **Mixed: GLMM** | `lme4::glmer` | `melogit`, `mepoisson`, `meglm` | `sp.melogit`, `sp.mepoisson`, `sp.meglm`, `sp.megamma`, `sp.menbreg`, `sp.meologit` | equivalent | **bit-exact** — vs `Stata 18 mepoisson, intmethod(laplace) / intmethod(mcaghermite) intpoints(7); lme4::glmer(nAGQ = 1 / 7)` — `tests/reference_parity/test_panel_glmm_parity.py` AGHQ quadrature |
| **Mixed: ICC** | `performance::icc` | `estat icc` | `sp.icc` | equivalent | **bit-exact** — vs `Stata 18 estat icc after mixed (ML, REML) and melogit; performance::icc; psych::ICC (balanced ANOVA identity)` — `tests/reference_parity/test_panel_icc_lrtest_parity.py` |
| **Mixed: LR test** | `lme4::anova` | `lrtest` | `sp.lrtest` | superset | **bit-exact** — vs `Stata 18 lrtest; R anova() on lme4 ML fits` — `tests/reference_parity/test_panel_icc_lrtest_parity.py` adds the Self--Liang boundary correction |
| **Spatial: diagnostics** | `spdep::moran.test`, `spdep::lm.LMtests` | `spatgsa`, `estat moran` | `sp.moran`, `sp.moran_local`, `sp.geary`, `sp.lm_tests` | equivalent | **bit-exact** — vs `R spdep::moran.test (randomisation null)` — `tests/reference_parity/test_spdep_parity.py` |
| **Spatial: ML (SAR/SEM/SAC)** | `spatialreg::lagsarlm`, `errorsarlm`, `sacsarlm` | `spregress` (different ML convention) | `sp.sar`, `sp.sem`, `sp.sac` | equivalent | **bit-exact** — vs `spatialreg::lagsarlm / spatialreg::errorsarlm / spatialreg::lagsarlm(Durbin=TRUE)` — `tests/r_parity/65_spatial.py` |
| **Spatial: GMM** | `spatialreg::stsls`, `GMerrorsar` | `spregress, gs2sls` (different moment convention) | `sp.sar_gmm`, `sp.sem_gmm`, `sp.sarar_gmm` | equivalent | **bit-exact** — vs `spatialreg::stsls(W2X=FALSE) / spatialreg::GMerrorsar` — `tests/r_parity/66_spatial_gmm.py` |
| **Spatial: panel / DiD** | `splm::spml` | `xsmle` (user-contrib) | `sp.spatial_panel`, `sp.spatial_did`, `sp.spatial_iv` | partial | **bit-exact** — vs `sphet::spreg(model = 'lag', het = TRUE) 2.1.1` — `tests/reference_parity/test_spatial_survey_R_parity.py` |
| **Spatial: GWR** | `GWmodel::gwr.*`, `spgwr::gwr` | --- | `sp.gwr`, `sp.mgwr` | equivalent | **bit-exact** — vs `GWmodel::gwr.basic 2.4.1` — `tests/reference_parity/test_spatial_survey_R_parity.py` |
| **Spatial: Conley SE** | `conleyreg::conleyreg` | `acreg`, `ols_spatial_HAC` | `sp.conley` | equivalent | **bit-exact** — vs `Stata acreg (Colella, Lalive, Sakalli & Thoenig)` — `tests/reference_parity/test_conley_acreg_spacetime_parity.py` |
| **Time series: ARIMA** | `stats::arima` | `arima` | `sp.arima` | equivalent | **bit-exact** — vs `stats::arima` — `tests/r_parity/39_arima.py` |
| **Time series: VAR** | `vars::VAR` | `var` | `sp.var`, `sp.irf` | equivalent | **bit-exact** — vs `vars::VAR` — `tests/r_parity/33_var.py` |
| **Time series: BVAR** | `BVAR::bvar` | `bayes: var` | `sp.bvar` | partial | **analytical** — `tests/reference_parity/test_timeseries_R_parity.py` |
| **Time series: GARCH** | `rugarch::ugarchfit` | `arch` | `sp.garch` | equivalent | **aligned** — vs `Stata 18 arch; rugarch::ugarchfit 1.5.6` — `tests/reference_parity/test_timeseries_R_parity.py` |
| **Time series: cointegration** | `urca::ca.jo`, `urca::ca.po` | `vecrank`, `egranger` | `sp.johansen`, `sp.engle_granger` | equivalent | **bit-exact** — vs `urca::ca.jo 1.3.4; Stata 18 vecrank` — `tests/reference_parity/test_timeseries_R_parity.py` |
| **Time series: local projections** | `lpirfs::lp_lin` | `lpirf` | `sp.local_projections` | equivalent | **bit-exact** — vs `lpirfs::lp_lin` — `tests/r_parity/34_lp.py` |
| **Time series: structural break** | `strucchange::breakpoints` | `estat sbsingle` | `sp.structural_break`, `sp.cusum_test` | equivalent | **bit-exact** — vs `strucchange::Fstats + sctest(type = 'supF') / breakpoints; mbreaks::dosequa (Bai-Perron sequential); Stata estat sbsingle` — `tests/reference_parity/test_r2_ts_parity.py` |
| **Time series: causal impact / ITS** | `CausalImpact` | `itsa` (user-contrib) | `sp.its` | equivalent | **bit-exact** — vs `lm + sandwich::NeweyWest 3.1.1; Stata 18 newey; itsa 1.0.0 (SSC)` — `tests/reference_parity/test_timeseries_R_parity.py` |
| **Survival: Cox** | `survival::coxph` | `stcox` | `sp.cox`, `sp.cox_frailty` | equivalent | **bit-exact** — vs `survival::coxph` — `tests/r_parity/24_coxph.py` |
| **Survival: AFT** | `survival::survreg` | `streg` | `sp.aft`, `sp.survreg` | equivalent | **aligned** — vs `survival::survreg (Weibull AFT)` — `tests/reference_parity/test_aft_parity.py` |
| **Survival: Kaplan--Meier** | `survival::survfit` | `sts graph` | `sp.kaplan_meier`, `sp.logrank_test` | equivalent | **bit-exact** — vs `survival::survfit` — `tests/reference_parity/test_survival_km_parity.py` |
| **Survival: competing risks** | `cmprsk::cuminc`, `crr` | `stcrreg` | `sp.cuminc`, `sp.finegray` | equivalent | **bit-exact** — vs `R cmprsk::cuminc (estimate, var, Tests); Stata stcompet (ci, se, hi, lo)` — `tests/reference_parity/test_survival_epi_R_parity.py` |
| **Epi: Mendelian randomisation** | `MendelianRandomization::*` | `mrrobust` | `sp.mr`, `sp.mendelian` | equivalent | **bit-exact** — vs `R MendelianRandomization::mr_ivw through the sp.mr dispatcher` — `tests/reference_parity/test_mr_R_parity.py` |
| **Epi: Bradford Hill / E-value** | `EValue::evalue` | --- | `sp.evalue`, `sp.evalue_rr`, `sp.bradford_hill` | equivalent | **bit-exact** — vs `EValue::evalues.RR` — `tests/r_parity/23_evalue.py` |
| **Survey design** | `survey::svydesign`, `svyglm` | `svyset`, `svy: regress` | `sp.svydesign`, `sp.svyglm`, `sp.svymean`, `sp.svytotal` | equivalent | **bit-exact** — vs `survey::svydesign + svymean/svytotal/svyglm/degf (strata, nested PSUs, fpc, survey.lonely.psu); Stata svyset + svy: mean/total/regress/logit/poisson + estat effects` — `tests/reference_parity/test_survey_design_R_parity.py` |
| **Multiple hypothesis testing** | `stats::p.adjust`, `multcomp` | `wyoung`, `rwolf` | `sp.adjust_pvalues`, `sp.romano_wolf`, `sp.benjamini_hochberg`, `sp.holm` | equivalent | **bit-exact** — vs `base R stats::p.adjust (bonferroni/holm/BH)` — `tests/reference_parity/test_mht_parity.py` |
| **Power analysis** | `pwr::*` | `power` | `sp.rdpower`, `sp.synth_power`, `sp.pretrends_power` | equivalent | **bit-exact** — vs `rdpower::rdpower 3.0 (Cattaneo, Titiunik & Vazquez-Bare)` — `tests/reference_parity/test_rdlocrand_parity.py` |
| **Randomization inference** | `ri2::conduct_ri` | `ritest` | `sp.ri_test` | equivalent | **bit-exact** — vs `R ri2::conduct_ri (randomizr full enumeration); Stata ritest over the full assignment set` — `tests/reference_parity/test_inference_sens_R_parity.py` |
| **Partial identification / bounds** | `boundsapply`-style | `leebounds` | `sp.lee_bounds`, `sp.manski_bounds`, `sp.horowitz_manski` | equivalent | **bit-exact** — vs `Stata leebounds 1.5 (Tauchmann), vce(analytic)` — `tests/reference_parity/test_teffects_R_parity.py` |
| **Mediation** | `mediation::mediate` | `medeff`, `sem` | `sp.mediate`, `sp.mediation`, `sp.mediation_decompose` | equivalent | **bit-exact** — vs `mediation::mediate` — `tests/r_parity/36_mediation.py` |
| **Interference / spillovers** | `interference`-style | --- | `sp.interference`, `sp.spillover`, `sp.spillover_did` | partial | **bit-exact** — vs `R did::att_gt(control_group='nevertreated') + did::aggte(type='simple') per group (direct / ring r, ring cohort = exposure onset); single cohort also fixest::feols(dbar ~ treat + ring1 + ring2, vcov='hetero', ssc(adj=FALSE))` — `tests/reference_parity/test_did_synth_misc_parity.py` |
| **Bartik / shift-share** | `bartik.weight::*` | `bartik_weight` | `sp.bartik` | equivalent | **bit-exact** — vs `2SLS: R AER::ivreg + sandwich (HC1 / classical), Stata ivregress 2sls, vce(robust) small / small; Rotemberg weights: R bartik.weight::bw and Stata bartik_weight (Goldsmith-Pinkham, Sorkin & Swift)` — `tests/reference_parity/test_did_synth_shiftshare_parity.py` |
| **Bunching** | `bunching::*` | `bunchit` (user-contrib) | `sp.bunching`, `sp.general_bunching`, `sp.notch` | equivalent | **analytical** — `tests/reference_parity/test_bunching_parity.py` |
| **Meta-analysis** | `metafor::rma` | `meta` | `sp.meta_analysis` | equivalent | **bit-exact** — vs `R metafor::rma (method='FE' and 'DL')` — `tests/reference_parity/test_weakiv_meta_parity.py` |
| **Sensitivity: Oster** | `robomit::*` | `psacalc` | `sp.oster_bounds`, `sp.oster_delta` | equivalent | **bit-exact** — vs `Stata psacalc (Oster); R robomit::o_delta / o_beta` — `tests/reference_parity/test_inference_sens_R_parity.py` |
| **Sensitivity: sensemakr** | `sensemakr::sensemakr` | `sensemakr` | `sp.sensemakr` | equivalent | **bit-exact** — vs `sensemakr::sensemakr` — `tests/r_parity/22_sensemakr.py` |
| **Sensitivity: Rosenbaum bounds** | `rbounds::*` | `rbounds` | `sp.rosenbaum_bounds`, `sp.rosenbaum_gamma` | equivalent | **bit-exact** — vs `R DOS2::senWilcox (Rosenbaum); Stata rbounds; R stats::binom.test (sign test); R rbounds::psens (zero_method='wilcox', 4-dp)` — `tests/reference_parity/test_inference_sens_R_parity.py` |
| **Sensitivity: specification curve** | `specr::specr` | --- | `sp.spec_curve` | equivalent | test-covered, not tier-graded — `tests/test_mixtape_ch09_guide.py` |
| **Sensitivity: breakdown frontier** | `breakdown`-style | --- | `sp.breakdown_frontier`, `sp.breakdown_m` | equivalent | **aligned** — vs `HonestDiD::findOptimalFLCI 0.2.8 (Rambachan & Roth), breakdown by uniroot on the bound facing zero` — `tests/reference_parity/test_did_synth_R_parity.py` |
| **Output: regression tables** | `modelsummary::msummary`, `stargazer`, `texreg` | `esttab`, `outreg2` | `sp.modelsummary`, `sp.etable`, `sp.regtable` | superset | test-covered, not tier-graded — `tests/test_regtable_fmt_auto.py` |
| **Output: marginal effects** | `marginaleffects::*` | `margins` | `sp.margins`, `sp.margins_at`, `sp.marginsplot` | equivalent | **bit-exact** — vs `Stata 18 margins, at(...); R marginaleffects::avg_predictions` — `tests/reference_parity/test_r2_postest_parity.py` |
| **Agent surface** | --- | --- | `sp.list_functions`, `sp.describe_function`, `sp.function_schema`, `sp.recommend` | new | test-covered, not tier-graded — `tests/test_agent_schema.py` |
| **Workflow / paper assistant** | --- | --- | `sp.paper`, `sp.causal_question`, `sp.methods_appendix` | new | test-covered, not tier-graded — `tests/test_docs_call_signatures.py` |

## Scope boundaries

Three deliberate exclusions, so the table's silence is not read as an
oversight:

1. **The Bayesian causal sub-package is not listed.** Frequentist parity
   against a point estimate is not the right yardstick for a posterior; the
   Bayesian estimators are validated through convergence diagnostics
   (`rhat`, `ess_bulk`, `ess_tail`, divergences) and recovery on simulated
   posteriors instead. Adding a "replacement" row for them would imply a
   comparison the evidence does not support.

2. **Plotting and reporting helpers are listed only where a canonical
   reference command exists.** `sp.love_plot` maps to `cobalt::bal.tab`;
   most figure helpers map to nothing in particular and are omitted rather
   than padded in.

3. **The table names entry points, not every alias.** Dispatchers such as
   `sp.synth(method=...)`, `sp.decompose(method=...)` and `sp.dml(model=...)`
   appear once per method rather than once per alias, matching how the
   registry documents them.

## Source

This file is generated by
[`../replication/scripts/build_replacement_table.py`](../replication/scripts/build_replacement_table.py).
Editorial changes — a new row, a corrected relationship, a different
reference package — belong in that script's `ROWS` table. Evidence changes
follow automatically from the parity artifacts and never need a hand edit.

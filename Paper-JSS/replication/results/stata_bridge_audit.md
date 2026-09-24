# Stata Bridge Audit

Status: PASS
Stata modules: 85
R-joined Stata modules: 85
Py-Stata-only migration modules: none
Pending scripted bridges: none
Reproducibility-report modules: 85

This audit does not require Stata. It verifies the frozen Stata bridge:
each `_Stata.json` must have a matching `.do` file, non-empty rows,
inline engine provenance, and a committed reproducibility-report row.
Re-running the Stata commands remains optional because it requires a
separate Stata license.

| Module | Rows | Join | Stata | Command / note |
|---|---:|---|---|---|
| `01_ols` | 7 | R+Stata | 18 MP | regress, vce(robust) |
| `02_iv` | 7 | R+Stata | 18 MP | ivregress 2sls, vce(robust) small |
| `03_hdfe` | 2 | R+Stata | 18 MP | reghdfe, absorb(firm year) vce(unadjusted) |
| `04_csdid` | 19 | R+Stata | 18 MP | csdid ... method(reg) long2 \| estat simple/event/group/calendar |
| `05_sunab` | 8 | R+Stata | 18 MP | eventstudyinteract Y rel_dummies, cohort(first_treat) control_cohort(nevertreat) absorb(i.countyreal i.year) vce(cluster countyreal) |
| `06_rd` | 6 | R+Stata | 18 MP | rdrobust Y X, c(0) |
| `07_scm` | 18 | R+Stata | 18 MP | synth gdppc gdppc(1955..1969), trunit(.) trperiod(1970) nested |
| `08_dml` | 1 | R+Stata | 18 MP | DML2 PLR: foldwise OLS residualization and pooled orthogonal score |
| `09_rddensity` | 6 | R+Stata | 18 MP | rddensity x, c(0) |
| `10_honest_did` | 10 | R+Stata | 18 MP | honestdid, b(b) vcov(V) numpre(3) mvec(...) delta(sd) |
| `11_psm` | 4 | R+Stata | 18 MP | teffects psmatch (re78) (treat ..., logit), atet nneighbor(1) |
| `12_sdid` | 2 | R+Stata | 18 MP | sdid cigsale state year treated, vce(placebo) |
| `14_ols_cluster` | 3 | R+Stata | 18 MP | regress lemp treat year, vce(cluster countyreal) |
| `15_hdfe_cluster` | 2 | R+Stata | 18 MP | reghdfe y x1 x2, absorb(firm year) vce(cluster firm) |
| `16_bjs` | 2 | R+Stata | 18 MP | replace first_treat = . if first_treat == 0; did_imputation lemp countyreal year first_treat, autosample |
| `17_etwfe` | 8 | R+Stata | 18 MP | jwdid lemp, ivar(countyreal) tvar(year) gvar(first_treat) [never] \| estat simple \| estat group |
| `18_augsynth` | 2 | R+Stata | 18 MP | Mata _sp_augsynth_bridge(region, year, gdppc, Basque Country, 1970) |
| `19_gsynth` | 3 | R+Stata | 18 MP | Mata _sp_gsynth_bridge(region, year, gdppc, Basque Country, 1970, r=1); diagnostic: fect gdppc, treat(treated_indicator) unit(unit_num) time(year) method(ife) r(1) force(two-way) tol(1e-12) maxiterations(20000) |
| `20_bacon` | 9 | R+Stata | 18 MP | bacondecomp lemp treat, ddetail |
| `21_honest_relmags` | 10 | R+Stata | 18 MP | honestdid, b(b) vcov(V) numpre(3) mvec(...) delta(rm) method(Conditional) gridPoints(1000) grid_lb(-2) grid_ub(2) |
| `22_sensemakr` | 7 | R+Stata | 18 MP | regress ... ; sensemakr, treat(treat) benchmark(re74) q(1) alpha(0.05) |
| `23_evalue` | 6 | R+Stata | 18 MP | evalue rr <est>, lcl(<lo>) ucl(<hi>) |
| `24_coxph` | 3 | R+Stata | 18 MP | stcox x1 x2, nohr (Efron default) |
| `25_lmm` | 4 | R+Stata | 18 MP | mixed y x1 \|\| gid:, reml |
| `26_glmm_logit` | 3 | R+Stata | 18 MP | melogit y x1 \|\| gid:, intmethod(laplace) |
| `27_glmm_aghq` | 3 | R+Stata | 18 MP | melogit y x1 \|\| gid:, intpoints(8) |
| `28_frontier` | 7 | R+Stata | 18 MP | frontier lny lnk lnl, distribution(hnormal) |
| `29_panel_sfa` | 5 | R+Stata | 18 MP | constraint 1 [mu]_cons = 0; xtfrontier lny lnk lnl, ti constraints(1) |
| `30_oaxaca` | 7 | R+Stata | 18 MP | oaxaca log_wage educ exper, by(female) |
| `31_dfl` | 6 | R+Stata | 18 MP | Newton-Raphson logit P(group==0\|educ,exper); reference=1 reweights group 0 to group 1 covariates |
| `32_rif` | 6 | R+Stata | 18 MP | Hmisc type-7 quantile + R stats::density binned Gaussian density + groupwise RIF-OLS decomposition |
| `33_var` | 11 | R+Stata | 18 MP | var y1 y2, lags(1/2) |
| `34_lp` | 6 | R+Stata | 18 MP | for h=0/5: regress y_h# x y_lag; lpirf y x, step(5) lags(1) |
| `35_panel` | 6 | R+Stata | 18 MP | xtreg ..., fe/re + hausman |
| `36_mediation` | 4 | R+Stata | 18 MP | paramed y, avar(treat) mvar(m) a0(0) a1(1) m(0) yreg(linear) mreg(linear) nointer |
| `37_ppmlhdfe` | 2 | R+Stata | 18 MP | ppmlhdfe y x1 x2, absorb(origin) vce(robust) |
| `38_drdid` | 3 | R+Stata | 18 MP | drdid y x, ivar(id) time(post) treatment(treated) drimp |
| `39_arima` | 4 | R+Stata | 18 MP | arima y, ar(1/2), tight MLE tolerances |
| `40_qreg` | 3 | R+Stata | 18 MP | qreg y x1 x2 |
| `41_tobit` | 3 | R+Stata | 18 MP | tobit y x, ll(0) |
| `42_nbreg` | 3 | R+Stata | 18 MP | nbreg y x1 x2 |
| `43_heckman` | 3 | R+Stata | 18 MP | heckman y x, select(sel = z) twostep |
| `44_mlogit` | 6 | R+Stata | 18 MP | mlogit y x1 x2, baseoutcome(0) |
| `45_ologit` | 3 | R+Stata | 18 MP | ologit y x |
| `46_clogit` | 1 | R+Stata | 18 MP | clogit choice x, group(group) |
| `47_ppmlhdfe_3fe` | 2 | R+Stata | 18 MP | ppmlhdfe trade log_dist contig, absorb(origin dest year) vce(robust) |
| `48_probit` | 3 | R+Stata | 18 MP | probit y x1 x2 |
| `49_oprobit` | 3 | R+Stata | 18 MP | oprobit y x |
| `50_xtabond` | 2 | R+Stata | 18 MP | xtabond y x, lags(1) vce(robust) |
| `51_newey` | 2 | R+Stata | 18 MP | newey y x, lag(4) |
| `52_scm_unique` | 7 | R+Stata | 18 MP | synth y y(0..19), trunit(6) trperiod(20) |
| `53_cr2` | 6 | R+Stata | 18 MP | CR2 uses (I-H_gg)^-1/2 adjusted scores; CR3 uses (I-H_gg)^-1 adjusted scores |
| `54_twoway_cluster` | 4 | R+Stata | 18 MP | reghdfe y x, noabsorb vce(cluster g1 g2) for diagnostic SEs; headline SEs from Mata CGM bridge |
| `55_hc2_hc3` | 6 | R+Stata | 18 MP | regress lemp treat year, vce(hc2) \| vce(hc3) |
| `56_multiway_cluster` | 4 | R+Stata | 18 MP | reghdfe y x, noabsorb vce(cluster g1 g2 g3) for diagnostic SEs; headline SEs from Mata CGM bridge |
| `57_logit` | 3 | R+Stata | 18 MP | logit y x1 x2 |
| `58_poisson` | 3 | R+Stata | 18 MP | poisson y x1 x2 |
| `59_liml` | 4 | R+Stata | 18 MP | ivregress liml y w (x = z1 z2), small |
| `60_sureg` | 6 | R+Stata | 18 MP | sureg (y1 x1 w) (y2 x2 w) |
| `61_betareg` | 4 | R+Stata | 18 MP | betareg y x1 x2, nrtolerance(1e-13) |
| `62_truncreg` | 4 | R+Stata | 18 MP | truncreg y x1 x2, ll(0) |
| `63_zip` | 5 | R+Stata | 18 MP | zip y x1 x2, inflate(z) |
| `64_zinb` | 6 | R+Stata | 18 MP | zinb y x1 x2, inflate(z) nrtolerance(1e-13) |
| `65_spatial` | 14 | R+Stata | 18 MP | materialized 2026-08-06 with licensed Stata 18 |
| `66_spatial_gmm` | 4 | R+Stata | 18 MP | ivregress 2sls y x1 x2 (Wy = Wx1 Wx2), small  -- Wy/Wx built from the same row-standardised rook W |
| `67_panel_glm` | 4 | R+Stata | 18 MP | materialized 2026-08-06 with licensed Stata 18 |
| `68_demean_within` | 10 | R+Stata | 18 MP | bysort id (_row): egen double _m = mean(v); gen double dm = v - _m |
| `69_balance_panel` | 8 | R+Stata | 18 MP | bysort id year: gen _first_yr = (_n==1); bysort id: egen _n_years = total(_first_yr); keep if _n_years == n_periods |
| `70_policy_tree` | 4 | R+Stata | 18 MP | audited Mata algorithm bridge, materialized 2026-08-06 with licensed Stata 18 |
| `71_dml_family` | 3 | R+Stata | 18 MP | ddml init interactive\|iv\|interactiveiv, foldvar(fold1); learners regress / logit; ddml crossfit; ddml estimate, robust |
| `72_tmle` | 1 | R+Stata | 18 MP | audited Stata/Mata algorithm bridge, materialized 2026-08-06 with licensed Stata 18 |
| `73_did2s` | 1 | R+Stata | 18 MP | did2s lemp, first_stage(i.countyreal i.year) second_stage(treated) treatment(treated) cluster(countyreal) |
| `74_cic` | 10 | R+Stata | 18 MP | cic all y treat post, at(10(10)90) vce(none) |
| `75_stacked` | 14 | R+Stata | 18 MP | reghdfe y <event-time dummies x treated_unit, k=-1 omitted>, absorb(uc tc) vce(cluster id) on a hand-built stack |
| `76_pretrends` | 8 | R+Stata | 18 MP | pretrends, numpre(3) b(beta) vcov(sigma) slope(#) / pretrends power #, numpre(3) b(beta) vcov(sigma) |
| `78_multiplegt_dyn` | 10 | R+Stata | 18 MP | did_multiplegt_dyn y id t d, effects(4) placebo(2) cluster(id) |
| `81_didm` | 2 | R+Stata | 18 MP | did_multiplegt_old y id t d, placebo(1) breps(0) |
| `82_staggered` | 33 | R+Stata | 18 MP |  |
| `83_lpdid` | 5 | R+Stata | 18 MP |  |
| `84_bjs_pretrends` | 7 | R+Stata | 18 MP | did_imputation y unit time g, pretrends(3) horizons(0/3) cluster(unit) |
| `85_twfe_event_study` | 8 | R+Stata | 18 MP | reghdfe y d_m4 d_m3 d_m2 d_p0 d_p1 d_p2 d_p3 d_p4, absorb(unit time) vce(cluster unit) |
| `86_fect` | 99 | R+Stata | 18 MP | fect Y, treat(D) unit(id) time(time) cov(X1 X2) method(fe\|ife\|mc) force(two-way) tol(1e-12) maxiterations(20000) [r(2) \| lambda(0.002)] |
| `87_interflex` | 17 | R+Stata | 18 MP | interflex Y D X Z1, type(linear\|binning\|kernel) vce(robust) neval(5) cutoffs(0.3 1.7) bw(1) |
| `88_rdbwselect` | 64 | R+Stata | 18 MP | rdbwselect y x, c(0) bwselect(mserd) |
| `89_rdms` | 15 | R+Stata | 18 MP | rdms y x1 x2 z, cvar(Cvar C2var) |

## Warnings

- 82_staggered has neither stata_command, identification_note, nor stata_bridge_status
- 83_lpdid has neither stata_command, identification_note, nor stata_bridge_status

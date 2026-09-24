* ---------------------------------------------------------------------------
* Stata reference for tests/reference_parity/test_postestimation_stata_parity.py
*
* Requires: Stata 18 (official commands only).
* Run:      stata -b do _generate_postestimation_stata.do   (from this directory)
* Data:     vce_grammar_data.csv, written by _generate_vce_grammar_stata.do.
*
* What this fixture pins
* ----------------------
* 1. `test` / `lincom` use the full e(V). sp.test / sp.lincom used only the
*    standard errors (a diagonal covariance), so any restriction involving
*    two correlated coefficients was wrong: F = 154.4 against Stata's 167.0
*    for `test x1 = x2` after `regress, vce(robust)`.
* 2. The reference distribution follows e(df_r): F / t after `regress`
*    (df_r = N-K, or G-1 under vce(cluster)), chi2 / z after ML commands.
*    StatsPAI reported t(N-K) for logit and for clustered OLS.
* 3. Coefficient p-values and confidence intervals (r(table)) under the same
*    rule.
* 4. `margins, dydx(*)` after logit: the delta-method SE needs the full e(V).
* ---------------------------------------------------------------------------
version 18
clear all
set type double
import delimited "vce_grammar_data.csv", clear asdouble

capture file close fh
file open fh using "postestimation_stata.json", write replace text
file write fh "{" _n

* _num <key> <scalar expression without spaces>
capture program drop _num
program define _num
    args key value
    file write fh `"    "`key'": "' %21.16e (`value') `","' _n
end

capture program drop _tests
program define _tests
    * _tests <block name>: test/lincom battery on the current estimates.
    args name
    file write fh `"  "`name'": {"' _n
    local dfr = cond(missing(e(df_r)), 0, e(df_r))
    _num df_r `dfr'
    matrix T = r(table)
    local c = colnumb(T, "x1")
    _num p_x1 T[4,`c']
    _num ll_x1 T[5,`c']
    _num ul_x1 T[6,`c']
    quietly test x1 = x2
    local stat = cond(missing(r(F)), r(chi2), r(F))
    _num test_eq_stat `stat'
    _num test_eq_p r(p)
    quietly test x1 x2
    local stat = cond(missing(r(F)), r(chi2), r(F))
    _num test_joint_stat `stat'
    _num test_joint_p r(p)
    quietly test x1 = x2 = 0
    _num test_chain_p r(p)
    quietly lincom x1 + x2
    _num lincom_sum_est r(estimate)
    _num lincom_sum_se r(se)
    _num lincom_sum_p r(p)
    _num lincom_sum_lb r(lb)
    quietly lincom x1 - 2*x2 + _cons
    _num lincom_mix_est r(estimate)
    _num lincom_mix_se r(se)
    file write fh `"    "N": "' %21.16e (e(N)) _n
    file write fh `"  },"' _n
end

quietly regress yl x1 x2
_tests regress_ols
quietly regress yl x1 x2, vce(robust)
_tests regress_robust
quietly regress yl x1 x2, vce(cluster g)
_tests regress_cluster
quietly ivregress 2sls yiv x1 x2 (endo = z1 z2), small vce(cluster g)
_tests ivregress_small_cluster
quietly logit yb x1 x2
_tests logit_oim
quietly logit yb x1 x2, vce(cluster g)
_tests logit_cluster
quietly poisson yc x1 x2, vce(robust)
_tests poisson_robust

* margins, dydx(*): average marginal effects on the default prediction scale
* (Pr(y) after logit/probit, E(y) after poisson/glm), delta-method SEs.
* margins used to return the index coefficients for every model, and a
* std(dydx)/sqrt(n) "SE" when the formula had interactions.
capture program drop _margins
program define _margins
    args name
    quietly margins, dydx(*)
    matrix M = r(table)
    local c1 = colnumb(M, "x1")
    local c2 = colnumb(M, "x2")
    file write fh `"  "`name'": {"' _n
    _num dydx_x1 M[1,`c1']
    _num se_x1 M[2,`c1']
    _num p_x1 M[4,`c1']
    _num dydx_x2 M[1,`c2']
    _num se_x2 M[2,`c2']
    file write fh `"    "N": "' %21.16e (e(N)) _n
    file write fh `"  },"' _n
end

quietly logit yb x1 x2
_margins logit_margins
quietly probit yp x1 x2
_margins probit_margins
quietly poisson yc x1 x2, vce(robust)
_margins poisson_margins
quietly glm yb x1 x2, family(binomial) link(cloglog)
_margins glm_cloglog_margins
quietly regress yl c.x1##c.x2
_margins regress_interaction_margins
quietly logit yb c.x1##c.x2
_margins logit_interaction_margins

file write fh `"  "_meta": {"' _n
file write fh `"    "stata_version": "' `"""' "`c(stata_version)'" `"""' `","' _n
file write fh `"    "generated": "' `"""' "`c(current_date)'" `"""' _n
file write fh `"  }"' _n
file write fh "}" _n
file close fh
display "wrote postestimation_stata.json"

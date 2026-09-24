* ---------------------------------------------------------------------------
* Stata reference for tests/reference_parity/test_decomp_qte_parity.py
* (round-2 decomposition / distributional-QTE family).
*
* Run _generate_decomp_qte_data.py first (writes dq_*.csv), then, from this
* directory,
*   stata-mp -b do _generate_decomp_qte_stata.do
* Writes decomp_qte_Stata.json (%23.16e: 17 significant digits; %g would
* drop the leading zero, which JSON forbids).
*
* Packages are installed into a PRIVATE ado tree next to this file
* (_ado_decomp_qte/, git-ignored by the _ado_*/ rule) -- never PLUS:
*   * counterfactual (cdeco), qrprocess, drprocess, ivqte:
*       net install <pkg>, from("https://raw.githubusercontent.com/bmelly/Stata/main/")
*     (Chernozhukov, Fernandez-Val & Melly's own implementation; ivqte is
*     Froelich & Melly's). cdeco/counterfactual are not on SSC.
*   * fairlie (Jann), shapley2 (Chavez Juarez), ineqdeco (Jenkins),
*     moremata (Jann), paramed (Liu & Emsley): ssc install <pkg>
*
* Conventions pinned here (each decides a number below)
* -----------------------------------------------------
* * cdeco, method(qr): nreg(100) quantile regressions at (j-0.5)/100,
*   fitted by est_opts(method(qreg)) -- Stata's exact simplex, so every
*   coefficient is the LP vertex. Unconditional quantiles are
*   mm_quantile() of the pooled n x 100 predictions, default definition 2
*   (averaged inverse CDF). The reported quantiles are offset from the
*   deciles (0.10003, ...): at tau*N integer (N = 500 x 100) definition 2
*   averages two order statistics, and whether Stata's floating running sum
*   of weights registers that tie is a rounding accident, not a property
*   of the estimator. Group 0 (female==0) is cdeco's reference group: the
*   counterfactual is group 0's coefficients on group 1's covariates. The
*   "_rev" runs swap the groups (group variable male = 1 - female).
* * cdeco, method(logit): drprocess with est_opts(thresholds(1.5(0.05)3.4))
*   -- 39 thresholds shared by both groups. The counterfactual CDF at each
*   threshold is mean(invlogit(X b(t))) over the other group's X, computed
*   below in Mata from e(coef0)/e(coef1) exactly as cdeco's distpred()
*   does before it sorts (rearranges) and inverts. drprocess fits each
*   logit with Stata's -logit- at its default tolerances. Same offset
*   quantiles as method(qr): a logit with an intercept reproduces its own
*   group's empirical proportion exactly, so the fitted CDF sits on k/500
*   and at tau = 0.9 the comparison F <= tau is decided by the last bit.
* * fairlie: groups of equal size (500/500), so no subsample is drawn and
*   the rank-to-rank matching is deterministic; reps(1). Coefficients from
*   group 0 (reference(0), the default) or group 1 (reference(1)).
*   e(V) is the delta-method variance averaged over replications.
* * shapley2 over the regression-based value function
*   v(S) = I(fitted values of regress wage on S); I from ineqdeco (ge0 =
*   mean log deviation, ge1 = Theil, ge2 = half squared CV, gini). shapley2
*   sets v(empty) = 0. ineqdeco's Gini is the plug-in (population) Gini.
* * ivqte (Froelich & Melly), unconditional endogenous QTE, default
*   kernel options (bandwidth infinity, lambda 1 => global logit for the
*   instrument propensity), trim(0.001). Weights (z - p)/(p(1 - p)),
*   demeaned; CDFs by est_qte(); quantile = ys[max(1, #{F <= tau})].
* * paramed: yreg(linear) mreg(linear) with the exposure-mediator
*   interaction, delta-method SEs from -regress- e(V) (s^2 with n - p),
*   effects at the covariate means.
* ---------------------------------------------------------------------------
version 18
set more off
set type double
local A "`c(pwd)'/_ado_decomp_qte"
sysdir set PLUS "`A'"
adopath ++ "`A'"

* paramed runs first: it clears Mata on its first call, which would drop
* the JSON writer defined below. Results are parked in Stata matrices.
import delimited using "dq_med.csv", clear asdouble
quietly summarize m if a == 0
scalar mstar = r(mean)
local mstar : display %21.0g mstar
quietly paramed y, avar(a) mvar(m) cvars(c1 c2) a0(0) a1(1) m(`mstar') ///
    yreg(linear) mreg(linear)
matrix PMb = e(b)
matrix PMV = e(V)
local pm_names : colnames PMb
quietly paramed y, avar(a) mvar(m) a0(0) a1(1) m(`mstar') yreg(linear) mreg(linear)
matrix PMb0 = e(b)
matrix PMV0 = e(V)

mata:
void wjson_row(real matrix M)
{
    // 1 x k or k x 1 -> flat JSON list; else nested list of rows
    real scalar i, j
    string scalar s
    if (rows(M) == 1 | cols(M) == 1) {
        M = vec(M)'
        s = "["
        for (j = 1; j <= cols(M); j++) {
            s = s + (j > 1 ? ", " : "") + strtrim(sprintf("%23.16e", M[1, j]))
        }
        st_local("js", s + "]")
        return
    }
    s = "["
    for (i = 1; i <= rows(M); i++) {
        s = s + (i > 1 ? ", " : "") + "["
        for (j = 1; j <= cols(M); j++) {
            s = s + (j > 1 ? ", " : "") + strtrim(sprintf("%23.16e", M[i, j]))
        }
        s = s + "]"
    }
    st_local("js", s + "]")
}
end

tempname fh
file open `fh' using "decomp_qte_Stata.json", write replace text
file write `fh' "{" _n

* ===========================================================================
* 1. Melly / CFM quantile-regression counterfactual: cdeco, method(qr)
* ===========================================================================
import delimited using "dq_wage.csv", clear asdouble
gen byte male = 1 - female
local qs "0.10003 0.25003 0.50003 0.75003 0.90003"
foreach dir in fwd rev {
    local gv = cond("`dir'" == "fwd", "female", "male")
    quietly cdeco log_wage educ exper tenure, group(`gv') method(qr) nreg(100) ///
        noboot est_opts(method(qreg)) quantiles(`qs')
    file write `fh' `"  "cdeco_qr_`dir'": {"'
    foreach m in fitted_0 fitted_1 counterfactual {
        matrix T = e(`m')
        mata: wjson_row(st_matrix("T")[., 1])
        file write `fh' `""`m'": `js', "'
    }
    foreach m in coef0 coef1 {
        matrix T = e(`m')
        mata: wjson_row(st_matrix("T"))
        file write `fh' `""`m'": `js', "'
    }
    matrix T = e(quantiles)
    mata: wjson_row(st_matrix("T"))
    file write `fh' `""quantiles": `js'}, "' _n
}

* ===========================================================================
* 2. CFM distribution regression: cdeco, method(logit)
* ===========================================================================
foreach dir in fwd rev {
    local gv = cond("`dir'" == "fwd", "female", "male")
    quietly cdeco log_wage educ exper tenure, group(`gv') method(logit) ///
        noboot quantiles(`qs') est_opts(thresholds(1.5(0.05)3.4))
    matrix C0 = e(coef0)
    matrix C1 = e(coef1)
    file write `fh' `"  "cdeco_logit_`dir'": {"'
    foreach m in fitted_0 fitted_1 counterfactual {
        matrix T = e(`m')
        mata: wjson_row(st_matrix("T")[., 1])
        file write `fh' `""`m'": `js', "'
    }
    * CDFs at the thresholds: rows of C are (thresholds \ coefficients),
    * coefficient order (educ exper tenure _cons).
    capture drop _g0 _g1
    gen byte _g0 = `gv' == 0
    gen byte _g1 = `gv' == 1
    mata {
        C0 = st_matrix("C0"); C1 = st_matrix("C1")
        X0 = st_data(., ("educ", "exper", "tenure"), "_g0"), J(500, 1, 1)
        X1 = st_data(., ("educ", "exper", "tenure"), "_g1"), J(500, 1, 1)
        F0 = mean(invlogit(X0 * C0[2..rows(C0), .]))
        F1 = mean(invlogit(X1 * C1[2..rows(C1), .]))
        FC = mean(invlogit(X1 * C0[2..rows(C0), .]))
        wjson_row(C0[1, .]); st_local("thr", st_local("js"))
        wjson_row(F0); st_local("f0", st_local("js"))
        wjson_row(F1); st_local("f1", st_local("js"))
        wjson_row(FC); st_local("fc", st_local("js"))
        wjson_row(C0[2..rows(C0), .]); st_local("b0", st_local("js"))
    }
    file write `fh' `""thresholds": `thr', "cdf_fitted_0": `f0', "'
    file write `fh' `""cdf_fitted_1": `f1', "cdf_counterfactual": `fc', "'
    file write `fh' `""coef0": `b0'}, "' _n
}

* ===========================================================================
* 3. Fairlie nonlinear decomposition (equal group sizes -> deterministic)
* ===========================================================================
foreach spec in logit_ref0 probit_ref0 logit_ref1 logit_ref0_tight probit_ref0_tight {
    local mdl = cond(strpos("`spec'", "probit"), "probit", "")
    local ref = cond(strpos("`spec'", "ref1"), "1", "0")
    * fairlie passes unrecognised options to logit/probit: the _tight runs
    * converge the reference-group model to 1e-14 instead of Stata's default.
    local tol = cond(strpos("`spec'", "tight"), "nrtolerance(1e-14) tolerance(1e-14) ltolerance(0) iterate(200)", "")
    set seed 12345
    quietly fairlie union educ exper tenure, by(female) reps(1) reference(`ref') `mdl' nodots `tol' 
    matrix b = e(b)
    matrix V = e(V)
    mata: wjson_row(st_matrix("b")); st_local("jb", st_local("js"))
    mata: wjson_row(diagonal(st_matrix("V"))'); st_local("jv", st_local("js"))
    file write `fh' `"  "fairlie_`spec'": {"b": `jb', "V_diag": `jv', "'
    file write `fh' `""pr_0": "' %23.16e (e(pr_0)) `", "pr_1": "' %23.16e (e(pr_1))
    file write `fh' `", "diff": "' %23.16e (e(diff)) `", "expl": "' %23.16e (e(expl))
    file write `fh' `", "N_match": "' %9.0f (e(N_match)) "}," _n
}

* ===========================================================================
* 4. Shapley inequality decomposition: shapley2 over regress + ineqdeco
* ===========================================================================
capture program drop _shineq
program define _shineq, eclass
    syntax varlist(min=1) [if]
    marksample touse
    gettoken dep rhs : varlist
    tempvar yhat
    quietly regress `dep' `rhs' if `touse'
    quietly predict double `yhat' if `touse'
    quietly ineqdeco `yhat' if `touse'
    * scalars, not locals: a local keeps only ~15 significant digits
    tempname s0 s1 s2 sg
    scalar `s0' = r(ge0)
    scalar `s1' = r(ge1)
    scalar `s2' = r(ge2)
    scalar `sg' = r(gini)
    ereturn post, esample(`touse')
    ereturn scalar ge0 = `s0'
    ereturn scalar ge1 = `s1'
    ereturn scalar ge2 = `s2'
    ereturn scalar gini = `sg'
    ereturn local cmd "_shineq"
    ereturn local depvar "`dep'"
end
quietly ineqdeco wage
file write `fh' `"  "shapley": {"total_ge0": "' %23.16e (r(ge0)) `", "total_ge1": "' %23.16e (r(ge1))
file write `fh' `", "total_ge2": "' %23.16e (r(ge2)) `", "total_gini": "' %23.16e (r(gini))
foreach s in ge0 ge1 ge2 gini {
    * shapley2 takes v(full) from the active e() results and e(sample) as
    * the estimation sample, so seed both with the full-model call.
    quietly _shineq wage educ exper tenure
    tempname full
    scalar `full' = e(`s')
    capture estimates drop myreg
    quietly shapley2, stat(`s') command(_shineq) indepvars(educ exper tenure) depvar(wage)
    matrix S = e(shapley)
    mata: wjson_row(st_matrix("S")); st_local("jb", st_local("js"))
    file write `fh' `", "`s'": `jb'"'
    file write `fh' `", "full_`s'": "' %23.16e (scalar(`full'))
}
* The value function itself, at full precision, for every non-empty subset
* (shapley2 routes v(S) through float-typed variables before combining, so
* its Shapley values carry ~1e-9 absolute rounding; its efficiency sum
* misses v(full) by that much). Order: e, x, t, ex, et, xt, ext.
foreach s in ge0 ge1 ge2 gini {
    file write `fh' `", "v_`s'": ["'
    local first 1
    foreach S in "educ" "exper" "tenure" "educ exper" "educ tenure" "exper tenure" "educ exper tenure" {
        quietly _shineq wage `S'
        if !`first' file write `fh' ", "
        file write `fh' %23.16e (e(`s'))
        local first 0
    }
    file write `fh' "]"
}
file write `fh' "}," _n

* ===========================================================================
* 5. Froelich-Melly unconditional IV-QTE: ivqte
* ===========================================================================
import delimited using "dq_iv.csv", clear asdouble
local iq "0.1 0.25 0.5 0.75 0.9"
quietly ivqte y (d = z), quantiles(`iq') variance
matrix b = e(b)
matrix V = e(V)
mata: wjson_row(st_matrix("b")); st_local("jb", st_local("js"))
mata: wjson_row(diagonal(st_matrix("V"))'); st_local("jv", st_local("js"))
file write `fh' `"  "ivqte_nocov": {"qte": `jb', "V_diag": `jv'}, "' _n
capture drop phat
quietly ivqte y (d = z), quantiles(`iq') continuous(x1) dummy(x2) generate_p(phat)
matrix b = e(b)
mata: wjson_row(st_matrix("b")); st_local("jb", st_local("js"))
mata: wjson_row(st_data(., "phat")); st_local("jp", st_local("js"))
file write `fh' `"  "ivqte_cov": {"qte": `jb', "phat": `jp'}, "' _n

* ===========================================================================
* 6. Linear mediation with exposure-mediator interaction: paramed
* ===========================================================================
mata: wjson_row(st_matrix("PMb")); st_local("jb", st_local("js"))
mata: wjson_row(sqrt(diagonal(st_matrix("PMV")))'); st_local("jv", st_local("js"))
file write `fh' `"  "paramed": {"names": "`pm_names'", "b": `jb', "se": `jv', "mstar": "' %23.16e (scalar(mstar)) "}," _n
mata: wjson_row(st_matrix("PMb0")); st_local("jb", st_local("js"))
mata: wjson_row(sqrt(diagonal(st_matrix("PMV0")))'); st_local("jv", st_local("js"))
file write `fh' `"  "paramed_nocov": {"b": `jb', "se": `jv'}, "' _n

* ---- provenance ------------------------------------------------------------
file write `fh' `"  "provenance": {"Stata": "`c(stata_version)'", "edition": "MP", "'
file write `fh' `""cdeco": "1.0.2 01mar2023 (bmelly/Stata counterfactual, Distribution-Date 20220803)", "'
file write `fh' `""ivqte": "2.1.15 17feb2010 (bmelly/Stata)", "fairlie": "1.0.7 16jun2008 (SSC)", "'
file write `fh' `""shapley2": "1.5 10jun15 (SSC)"}"' _n
file write `fh' "}" _n
file close `fh'
display "wrote decomp_qte_Stata.json"

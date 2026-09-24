* ---------------------------------------------------------------------------
* Stata reference for tests/reference_parity/test_r2_postest_parity.py
*
* Requires: Stata 18 (official commands only; no ado dir needed).
* Run:      stata-mp -b do _generate_r2_postest_stata.do   (from this directory)
* Data:     r2_postest_data.csv, written by _generate_r2_postest_data.py.
*
* What this fixture pins (sp.margins_at / sp.contrast / sp.pwcompare /
* sp.margins(at=, method="mem") / sp.test as the joint contrast test):
*
*  - margins, at(...)            predictive margins, single and multiple at-
*                                variables, at() on a factor variable
*  - margins r. / rb#. / ar. / gw.   contrasts of predictive margins
*  - margins g, pwcompare(effects) mcompare(noadjust|bonferroni|sidak)
*  - contrast r.g / pwcompare g  (asbalanced; differs from the margins
*                                versions only when g interacts with a factor)
*  - margins, dydx() at() / atmeans  after logit, probit, poisson
*  - vce(robust), vce(cluster)   (t with e(df_r) = G - 1 under clustering)
*  - an estimation sample smaller than the data (missing outcome)
*
* Every r(table) is written whole (rows b se t|z pvalue ll ul df crit eform),
* together with e(b) of each fit, at %21.16e (17 significant digits).
* ---------------------------------------------------------------------------
version 18
clear all
set type double
import delimited "r2_postest_data.csv", clear asdouble

capture file close fh
file open fh using "r2_postest_stata.json", write replace text
file write fh "{" _n

capture program drop _num
program define _num
    args key value
    file write fh `"  "`key'": "' %21.16e (`value') `","' _n
end

* _mat <key> <matrix>: {"cols": [...], "rows": [...], "v": [[...], ...]}
capture program drop _mat
program define _mat
    args key mname
    tempname M
    matrix `M' = `mname'
    local nr = rowsof(`M')
    local nc = colsof(`M')
    local cn : colfullnames `M'
    local rn : rownames `M'
    file write fh `"  "`key'": {"cols": ["'
    local i 0
    foreach c of local cn {
        local ++i
        file write fh `"""' `"`c'"' `"""'
        if `i' < `nc' file write fh ", "
    }
    file write fh `"], "rows": ["'
    local i 0
    foreach r of local rn {
        local ++i
        file write fh `"""' `"`r'"' `"""'
        if `i' < `nr' file write fh ", "
    }
    file write fh `"], "v": ["'
    forvalues r = 1/`nr' {
        file write fh "["
        forvalues c = 1/`nc' {
            if missing(`M'[`r', `c']) file write fh "null"
            else file write fh %21.16e (`M'[`r', `c'])
            if `c' < `nc' file write fh ", "
        }
        file write fh "]"
        if `r' < `nr' file write fh ", "
    }
    file write fh "]}," _n
end

* _vs <key>: pairwise-comparison table of the last margins/pwcompare call.
capture program drop _vs
program define _vs
    args key
    capture confirm matrix r(table_vs)
    if _rc {
        display as error "r(table_vs) missing for `key'"
        exit 498
    }
    _mat `key' r(table_vs)
end

* ===========================================================================
* 1. OLS, additive factor:  regress yl i.g x z
* ===========================================================================
foreach blk in ols robust cluster {
    if "`blk'" == "ols"     local vce ""
    if "`blk'" == "robust"  local vce "vce(robust)"
    if "`blk'" == "cluster" local vce "vce(cluster cl)"
    quietly regress yl i.g x z, `vce'
    _mat `blk'__b e(b)
    _num `blk'__df_r e(df_r)
    quietly margins, at(x=(-1 0 1.5))
    _mat `blk'__at_x r(table)
    _mat `blk'__at_x_at r(at)
    quietly margins r.g
    _mat `blk'__r_g r(table)
    quietly margins ar.g
    _mat `blk'__ar_g r(table)
    quietly margins g, pwcompare(effects) mcompare(sidak)
    _vs `blk'__pw_sidak
    quietly margins g, pwcompare(effects) mcompare(bonferroni)
    _vs `blk'__pw_bonferroni
    * joint Wald test of the g contrasts (= test 2.g 3.g 4.g)
    quietly contrast r.g
    _mat `blk'__contrast_F r(F)
    _mat `blk'__contrast_p r(p)
    _mat `blk'__contrast_df r(df)
}

quietly regress yl i.g x z
quietly margins, at(x=(-1 1) z=(0 2))
_mat ols__at_xz r(table)
_mat ols__at_xz_at r(at)
quietly margins, at(g=(1 3))
_mat ols__at_g r(table)
quietly margins rb3.g
_mat ols__rb3_g r(table)
quietly margins gw.g
_mat ols__gw_g r(table)
quietly margins g, pwcompare(effects)
_vs ols__pw_none
quietly pwcompare g, effects mcompare(sidak)
_vs ols__pwcompare_sidak
quietly contrast r.g, effects
_mat ols__contrast_rg r(table)
quietly margins, dydx(x) at(z=(0 1))
_mat ols__dydx_x_at_z r(table)
* at() on a variable that does not enter the model is an error in Stata
capture margins, at(cl=(0 1))
local rc = _rc
_num ols__at_notinmodel_rc `rc'

* ===========================================================================
* 2. OLS, factor x continuous interaction: regress yl i.g##c.x z
* ===========================================================================
quietly regress yl i.g##c.x z
_mat inter__b e(b)
_num inter__df_r e(df_r)
quietly margins, at(x=(-1 0 1.5))
_mat inter__at_x r(table)
quietly margins, at(g=(1 3) x=(0 1))
_mat inter__at_gx r(table)
_mat inter__at_gx_at r(at)
quietly margins r.g
_mat inter__r_g r(table)
quietly margins ar.g
_mat inter__ar_g r(table)
quietly margins gw.g
_mat inter__gw_g r(table)
quietly margins g, pwcompare(effects) mcompare(bonferroni)
_vs inter__pw_bonferroni
quietly contrast r.g, effects
_mat inter__contrast_rg r(table)
quietly margins, dydx(x)
_mat inter__dydx_x r(table)
quietly margins, dydx(x) at(g=(1 2 3 4))
_mat inter__dydx_x_at_g r(table)

* ===========================================================================
* 3. OLS, factor x factor interaction: regress yl i.g##i.h x
*    margins averages over the observed h (asobserved); contrast / pwcompare
*    balance over h (asbalanced) -- different estimands here.
* ===========================================================================
quietly regress yl i.g##i.h x
_mat ff__b e(b)
_num ff__df_r e(df_r)
quietly margins r.g
_mat ff__r_g r(table)
quietly contrast r.g, effects
_mat ff__contrast_rg r(table)
quietly margins g, pwcompare(effects) mcompare(sidak)
_vs ff__pw_sidak
quietly pwcompare g, effects mcompare(sidak)
_vs ff__pwcompare_sidak
quietly margins, at(h=(0 1))
_mat ff__at_h r(table)

* ===========================================================================
* 4. Estimation sample smaller than the data: yl_m has 25 missing values.
* ===========================================================================
quietly regress yl_m i.g x z
_mat miss__b e(b)
_num miss__N e(N)
quietly margins, at(x=(0 1))
_mat miss__at_x r(table)
quietly margins gw.g
_mat miss__gw_g r(table)

* ===========================================================================
* 5. Index models: dydx() at() / atmeans on the default prediction scale,
*    predictive margins at() on predict(pr) and predict(xb), and the
*    xb-scale contrast / pwcompare.
* ===========================================================================
foreach blk in logit probit {
    if "`blk'" == "logit"  local y yb
    if "`blk'" == "probit" local y yp
    quietly `blk' `y' i.g x z
    _mat `blk'__b e(b)
    quietly margins, dydx(x z) atmeans
    _mat `blk'__dydx_atmeans r(table)
    _mat `blk'__dydx_atmeans_at r(at)
    quietly margins, dydx(x) at(z=(0 1))
    _mat `blk'__dydx_x_at_z r(table)
    quietly margins, dydx(x) at(g=(1 3))
    _mat `blk'__dydx_x_at_g r(table)
    quietly margins, dydx(x) at(z=1) atmeans
    _mat `blk'__dydx_x_at_z1_atmeans r(table)
    quietly margins, at(x=(0 1))
    _mat `blk'__at_x_pr r(table)
    quietly margins, at(x=(0 1)) predict(xb)
    _mat `blk'__at_x_xb r(table)
    quietly margins r.g
    _mat `blk'__r_g_pr r(table)
    quietly contrast r.g, effects
    _mat `blk'__contrast_rg r(table)
    _mat `blk'__contrast_chi2 r(chi2)
    _mat `blk'__contrast_p r(p)
    quietly pwcompare g, effects mcompare(bonferroni)
    _vs `blk'__pwcompare_bonferroni

    * same model without the factor (atmeans with continuous covariates only)
    quietly `blk' `y' x z
    _mat `blk'_nf__b e(b)
    quietly margins, dydx(x z) atmeans
    _mat `blk'_nf__dydx_atmeans r(table)
}

quietly poisson yc x z, vce(robust)
_mat poisson__b e(b)
quietly margins, dydx(x z) atmeans
_mat poisson__dydx_atmeans r(table)
quietly margins, dydx(x) at(z=(0 1))
_mat poisson__dydx_x_at_z r(table)

* optimiser check: the logit fit at tight convergence tolerances
quietly logit yb i.g x z, nrtolerance(1e-14) tolerance(1e-14) ltolerance(1e-14)
_mat logit_tight__b e(b)
quietly margins, dydx(x) at(z=(0 1))
_mat logit_tight__dydx_x_at_z r(table)

file write fh `"  "_meta": {"' _n
file write fh `"    "stata_version": "' `"""' "`c(stata_version)'" `"""' `","' _n
file write fh `"    "born_date": "' `"""' "`c(born_date)'" `"""' `","' _n
file write fh `"    "generated": "' `"""' "`c(current_date)'" `"""' `","' _n
file write fh `"    "data": "r2_postest_data.csv""' _n
file write fh `"  }"' _n
file write fh "}" _n
file close fh
display "wrote r2_postest_stata.json"

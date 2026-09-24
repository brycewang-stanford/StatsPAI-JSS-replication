* tests/stata_parity/19_gsynth.do
*
* Module 19: Generalized SCM (Xu 2017) on the Basque replica.
*   StatsPAI:  sp.gsynth(..., backend="native")
*   R:         gsynth::gsynth(gdppc ~ treated_indicator, index = c("region","year"),
*                             force = "two-way", CV = TRUE, r = c(0, 5), se = FALSE)
*   Stata:     audited Stata/Mata implementation of gsynth's control-only
*              two-way IFE convention (below), plus a packaged fect_stata
*              method("ife") run recorded as an un-joined diagnostic row.
*
* Why a Mata bridge and not fect_stata: gsynth estimates the factor space on
* the never-treated control panel only (two-way demeaning + rank-r SVD, which
* is the closed-form fixed point of gsynth's inter_fe iteration on a balanced
* panel) and then projects the treated unit's PRE-treatment outcomes on
* [1, F] to obtain its unit effect and loadings. fect's "ife" instead runs the
* IFEct EM on ALL untreated observations, including the treated unit's
* pre-period cells, which is a different estimator. R's fect::fect exposes the
* gsynth convention as method = "gsynth" (att.avg -0.32417115086183, identical
* to the gsynth golden), but fect_stata only ships fe/ife/mc/bspline/polynomial
* (fect.ado line 165), so the gsynth convention has no packaged Stata route.
* On this fixture fect_stata ife r(1) tol(1e-12) gives -0.33206083 and a
* converged R fect ife (max.iteration = 50000, niter 5183) gives
* -0.33206095629 -- the two fect ports agree, and both differ from gsynth.
*
* Number of factors: gsynth's CV = TRUE draws random holdout cells, so r is
* fixed at the value R's CV selected (r.cv = 1, the n_factors row of
* 19_gsynth_R.json). Only att_gsynth and pre_rmse are emitted for the join;
* n_factors is an input here and is recorded in extra, not as a row.

version 18
clear all

do _common.do
stata_parity_init, module(19_gsynth)
stata_parity_open, module(19_gsynth)

import delimited "${STATA_PARITY_DATA}/19_gsynth.csv", clear case(preserve) ///
    stringcols(1) asdouble
local n = _N
local r_factors 1
local t_treat 1970

mata:
void _sp_gsynth_bridge(string scalar unitvar, string scalar timevar,
                       string scalar yvar, string scalar treated_name,
                       real scalar t_treat, real scalar r)
{
    string colvector units, ulist
    real colvector times, tlist, y, y1, target, coef, cf, eff, rowm, xi
    real rowvector colm
    real matrix Y, Y0, Y0dm, F, design
    transmorphic U, Vt, s
    real scalar N, T, T0, N0, mu, i, ri, ci, tr, att, pre_rmse, alpha_tr

    units = st_sdata(., unitvar)
    times = st_data(., timevar)
    y     = st_data(., yvar)
    ulist = uniqrows(units)
    tlist = uniqrows(times)
    N = rows(ulist)
    T = rows(tlist)
    Y = J(N, T, .)
    for (i = 1; i <= rows(y); i++) {
        ri = selectindex(ulist :== units[i])
        ci = selectindex(tlist :== times[i])
        Y[ri, ci] = y[i]
    }
    if (hasmissing(Y)) _error("panel is not balanced")
    tr = selectindex(ulist :== treated_name)
    T0 = sum(tlist :< t_treat)
    Y0 = select(Y, (1::N) :!= tr)
    N0 = rows(Y0)

    // gsynth force = "two-way": grand mean, unit and time effects of the
    // control panel; the rank-r term is the truncated SVD of the
    // double-demeaned control panel.
    mu   = sum(Y0) / (N0 * T)
    rowm = rowsum(Y0) :/ T
    colm = colsum(Y0) :/ N0
    Y0dm = Y0 :- rowm :- colm :+ mu
    xi   = colm' :- mu

    y1 = Y[tr, .]'
    target = y1[|1 \ T0|] :- mu :- xi[|1 \ T0|]
    if (r > 0) {
        // Mata's svd() wants a tall matrix; decompose the transpose
        // (T x N0) and read the factors off its left singular vectors.
        svd(Y0dm', U, s, Vt)
        F = U[|1, 1 \ T, r|]
        design = J(T0, 1, 1), F[|1, 1 \ T0, r|]
        coef = qrsolve(design, target)
        alpha_tr = coef[1]
        cf = mu :+ alpha_tr :+ xi :+ F * coef[|2 \ r + 1|]
    }
    else {
        alpha_tr = mean(target)
        cf = mu :+ alpha_tr :+ xi
    }
    eff = y1 - cf
    att = mean(eff[|T0 + 1 \ T|])
    pre_rmse = sqrt(mean(eff[|1 \ T0|] :^ 2))

    st_numscalar("SP_att", att)
    st_numscalar("SP_pre_rmse", pre_rmse)
    st_numscalar("SP_alpha_tr", alpha_tr)
    st_numscalar("SP_mu", mu)
    st_numscalar("SP_T0", T0)
    st_numscalar("SP_N0", N0)
}
_sp_gsynth_bridge("region", "year", "gdppc", "Basque Country", `t_treat', `r_factors')
end

local att = SP_att
local pre_rmse = SP_pre_rmse
display %24.17g `att'
display %24.17g `pre_rmse'

stata_parity_row, statname("att_gsynth") estimate(`att') nobs(`n')
stata_parity_row, statname("pre_rmse") estimate(`pre_rmse') nobs(`n')

* ---- packaged fect_stata method("ife") as an un-joined diagnostic ----------
local ado_fect "`c(pwd)'/_ado_fect"
capture mkdir "`ado_fect'"
adopath + "`ado_fect'"
capture which fect
if _rc != 0 {
    local plus_saved : sysdir PLUS
    sysdir set PLUS "`ado_fect'"
    net install fect, from("https://raw.githubusercontent.com/xuyiqing/fect_stata/master/") replace
    sysdir set PLUS "`plus_saved'"
}
capture which _gwtmean
if _rc != 0 {
    local plus_saved : sysdir PLUS
    sysdir set PLUS "`ado_fect'"
    ssc install _gwtmean, replace
    sysdir set PLUS "`plus_saved'"
}
encode region, generate(unit_num)
xtset unit_num year
fect gdppc, treat(treated_indicator) unit(unit_num) time(year) method("ife") ///
    r(`r_factors') force("two-way") tol(1e-12) maxiterations(20000)
matrix FATT = e(ATT)
local fect_ife_att = FATT[1, 1]
stata_parity_row, statname("ife_att_avg_fect_stata") estimate(`fect_ife_att') nobs(`n')

stata_parity_extra, key(method) val("gsynth (Xu 2017) two-way IFE, control-only factors, r fixed at R's r.cv")
stata_parity_extra_num, key(n_factors) val(`r_factors')
stata_parity_extra, key(n_factors_source) val("fixed at gsynth::gsynth CV = TRUE selection recorded in 19_gsynth_R.json (n_factors row); gsynth's CV holdout cells are random and cannot be re-seeded from Stata")
stata_parity_extra, key(stata_bridge_status) val("audited Stata/Mata algorithm bridge")
stata_parity_extra, key(stata_algorithm) val("two-way demean of the never-treated control panel; rank-r truncated SVD gives the factors; treated unit effect and loadings from OLS of its pre-treatment outcomes (net of mu and time effects) on [1, F]; counterfactual = mu + alpha_tr + xi_t + F_t lambda_tr; att = mean post gap; pre_rmse = RMSE of pre gap")
stata_parity_extra, key(stata_reference_note) val("fect_stata (GitHub xuyiqing/fect_stata) has no method(gsynth); its method(ife) is the IFEct EM on all untreated cells (treated pre-periods included), a different estimator. It is recorded as ife_att_avg_fect_stata and not joined. R fect::fect(method='gsynth', r=1) reproduces the gsynth golden exactly; R fect ife converged (max.iteration=50000) gives -0.33206095629, matching fect_stata ife to 4e-7.")
stata_parity_extra, key(stata_command) val("Mata _sp_gsynth_bridge(region, year, gdppc, Basque Country, 1970, r=1); diagnostic: fect gdppc, treat(treated_indicator) unit(unit_num) time(year) method(ife) r(1) force(two-way) tol(1e-12) maxiterations(20000)")

stata_parity_close, module(19_gsynth)

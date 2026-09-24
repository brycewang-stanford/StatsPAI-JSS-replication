* tests/stata_parity/18_augsynth.do
*
* Module 18: Augmented SCM (Ben-Michael, Feller and Rothstein 2021) on the
* Basque replica, outcome-only Ridge + SCM specification.
*   StatsPAI:  sp.augsynth(..., backend="native")
*   R:         augsynth::augsynth(gdppc ~ treated_indicator, unit = region,
*                                 time = year, progfunc = "Ridge", scm = TRUE)
*   Stata:     audited Stata/Mata implementation of the same estimator
*
* This is not a packaged Stata reference. allsynth (SSC, v1.32) is the only
* candidate and its bcorrect(merge ridge) de-biaser rejects this fixture:
* "Not enough control units to complete de-bias procedure given the given the
* specified number of predictors, K. Please supply at least K + 2 control
* units" (r(198); 16 controls, K = 15 pre-period outcomes). Even where it
* runs, allsynth's correction is a different estimand: -synth- V-weighted
* donor weights plus a per-post-period ridgeregress outcome model with its own
* CV lambda, whereas augsynth solves the unweighted simplex QP on
* control-mean-centred pre-outcomes and adds a ridge correction to the weights
* with one lambda picked by leave-one-period-out CV and the 1-SE rule.
*
* Algorithm ported (augsynth 0.2.0, fit_ridgeaug_formatted / cv_lambda /
* get_lambda_errors / choose_lambda / synth_qp / predict.augsynth):
*   1. X0 (J x T0) donor pre-outcomes, x1 treated pre-outcomes; centre every
*      period by the donor mean: Xc, xc1.
*   2. SCM weights w = argmin ||xc1 - Xc' w||^2 s.t. w >= 0, 1'w = 1
*      (augsynth: OSQP with eps_abs = eps_rel = 1e-8; here: exact primal
*      active-set QP, KKT solved by svsolve).
*   3. lambda grid: lambda_max = sigma_max(Xc)^2, 21 log-spaced values down to
*      lambda_max * 1e-8. For each holdout period i = 1..T0-1 (augsynth never
*      holds out the last period), refit w on the other T0-1 periods, form
*      w_aug(lambda) = w + Xc_(-i) (Xc_(-i)' Xc_(-i) + lambda I)^-1 (xc1 - Xc' w)
*      and score the squared error on period i. lambda = largest value whose
*      mean error is within one SE of the minimum.
*   4. w_aug = w + Xc (Xc'Xc + lambda I)^-1 (xc1 - Xc' w); counterfactual =
*      raw donor trajectory times w_aug; att_augmented = mean post gap,
*      pre_rmspe = RMSE of the pre gap.

version 18
clear all

do _common.do
stata_parity_init, module(18_augsynth)
stata_parity_open, module(18_augsynth)

import delimited "${STATA_PARITY_DATA}/18_augsynth.csv", clear case(preserve) ///
    stringcols(1) asdouble
local n = _N
local t_treat 1970

mata:
// Exact primal active-set solver for
//   min_w ||x1 - Xc' w||^2  s.t.  w >= 0, 1'w = 1
// Xc is J x T (donors x periods).
real colvector _sp_simplex_qp(real matrix Xc, real colvector x1)
{
    real matrix G, K
    real colvector c, w, g, p, sol, rhs, lam, ratios
    real colvector Fidx, negidx
    real scalar J, nF, mu, it, alpha, blk, k, tol, jmin
    real colvector W

    J = rows(Xc)
    G = Xc * Xc'
    c = Xc * x1
    w = J(J, 1, 1 / J)
    W = J(J, 1, 0)
    tol = 1e-13
    for (it = 1; it <= 1000; it++) {
        Fidx = selectindex(W :== 0)
        nF = rows(Fidx)
        g = G * w - c
        K = J(nF + 1, nF + 1, 0)
        K[|1, 1 \ nF, nF|] = G[Fidx, Fidx]
        K[|1, nF + 1 \ nF, nF + 1|] = J(nF, 1, 1)
        K[|nF + 1, 1 \ nF + 1, nF|] = J(1, nF, 1)
        rhs = -g[Fidx] \ 0
        sol = svsolve(K, rhs)
        p = J(J, 1, 0)
        p[Fidx] = sol[|1 \ nF|]
        mu = sol[nF + 1]
        if (max(abs(p)) < tol) {
            lam = g :+ mu
            lam = (W :== 1) :* lam :+ (W :== 0) :* 1e300
            jmin = selectindex(lam :== min(lam))[1]
            if (lam[jmin] >= -tol) return(w)
            W[jmin] = 0
            continue
        }
        negidx = selectindex((p :< 0) :& (W :== 0))
        alpha = 1
        blk = 0
        if (rows(negidx) > 0) {
            ratios = -w[negidx] :/ p[negidx]
            k = selectindex(ratios :== min(ratios))[1]
            if (ratios[k] < 1) {
                alpha = ratios[k]
                blk = negidx[k]
            }
        }
        w = w + alpha :* p
        if (blk > 0) {
            w[blk] = 0
            W[blk] = 1
        }
    }
    _error("simplex QP did not converge")
}

void _sp_augsynth_bridge(string scalar unitvar, string scalar timevar,
                         string scalar yvar, string scalar treated_name,
                         real scalar t_treat)
{
    string colvector units, ulist
    real colvector times, tlist, y, y1, x1, xc1, w, wf, wa, imb, rw, lambdas
    real colvector lerr, lse, keep, x1f, x0v
    transmorphic U, Vt, s
    real rowvector m
    real matrix Y, Y0, X0, Xc, Xf, Ypost0, errs, B
    real scalar N, T, T0, J, i, j, ri, ci, tr, lmax, scaler, nl, nf, minidx
    real scalar thresh, lambda, att, pre_rmspe, e

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
    J = rows(Y0)
    X0 = Y0[|1, 1 \ J, T0|]
    Ypost0 = Y0[|1, T0 + 1 \ J, T|]
    y1 = Y[tr, .]'
    x1 = y1[|1 \ T0|]

    // 1. centre by donor mean, period by period
    m = colsum(X0) :/ J
    Xc = X0 :- m
    xc1 = x1 - m'

    // 2. SCM weights on the centred pre-outcomes
    w = _sp_simplex_qp(Xc, xc1)

    // 3. augsynth lambda path and leave-one-period-out CV (1-SE rule)
    svd(Xc, U, s, Vt)
    lmax = s[1]^2
    nl = 21
    scaler = (1e-8)^(1 / 20)
    lambdas = lmax :* (scaler :^ (0::(nl - 1)))
    nf = T0 - 1
    errs = J(nf, nl, 0)
    for (i = 1; i <= nf; i++) {
        keep = selectindex((1::T0) :!= i)
        Xf = Xc[., keep]
        x1f = xc1[keep]
        x0v = Xc[., i]
        wf = _sp_simplex_qp(Xf, x1f)
        imb = x1f - Xf' * wf
        for (j = 1; j <= nl; j++) {
            B = lusolve(Xf' * Xf + lambdas[j] :* I(T0 - 1), Xf')
            rw = (imb' * B)'
            e = xc1[i] - x0v' * (wf + rw)
            errs[i, j] = e * e
        }
    }
    lerr = (colsum(errs) :/ nf)'
    lse = J(nl, 1, 0)
    for (j = 1; j <= nl; j++) lse[j] = sqrt(variance(errs[., j])) / sqrt(nf)
    minidx = selectindex(lerr :== min(lerr))[1]
    thresh = lerr[minidx] + lse[minidx]
    lambda = max(select(lambdas, lerr :<= thresh))

    // 4. ridge-augmented weights and the counterfactual on raw outcomes
    B = lusolve(Xc' * Xc + lambda :* I(T0), Xc')
    rw = ((xc1 - Xc' * w)' * B)'
    wa = w + rw
    att = mean(y1[|T0 + 1 \ T|] - Ypost0' * wa)
    pre_rmspe = sqrt(mean((x1 - X0' * wa) :^ 2))

    st_numscalar("SP_att", att)
    st_numscalar("SP_pre_rmspe", pre_rmspe)
    st_numscalar("SP_lambda", lambda)
    st_numscalar("SP_lambda_max", lmax)
    st_numscalar("SP_lambda_idx", minidx)
    st_numscalar("SP_l2_imbalance", sqrt(sum((xc1 - Xc' * wa) :^ 2)))
    st_matrix("SP_w_scm", w)
    st_matrix("SP_w_aug", wa)
    st_matrix("SP_lambda_errors", lerr)
}
_sp_augsynth_bridge("region", "year", "gdppc", "Basque Country", `t_treat')
end

local att = SP_att
local pre_rmspe = SP_pre_rmspe
local lambda = SP_lambda
display %24.17g `att'
display %24.17g `pre_rmspe'
display %24.17g `lambda'
matrix list SP_w_scm, format(%20.15g)
matrix list SP_w_aug, format(%20.15g)
matrix list SP_lambda_errors, format(%20.15g)

stata_parity_row, statname("att_augmented") estimate(`att') nobs(`n')
stata_parity_row, statname("pre_rmspe") estimate(`pre_rmspe') nobs(`n')

stata_parity_extra, key(method) val("augsynth Ridge + SCM (progfunc = Ridge, scm = TRUE), outcome-only")
stata_parity_extra_num, key(ridge_lambda) val(`lambda')
stata_parity_extra, key(ridge_lambda_rule) val("augsynth cv_lambda: lambda_max = sigma_max(Xc)^2, 21-point log grid to lambda_max*1e-8, leave-one-period-out holdout over periods 1..T0-1, largest lambda within one SE of the minimum mean squared holdout error (min_1se = TRUE); recomputed in Mata, equals the lambda element of the augsynth fit object, 0.019248584986999707")
stata_parity_extra, key(stata_bridge_status) val("audited Stata/Mata algorithm bridge")
stata_parity_extra, key(stata_algorithm) val("donor-mean-centred pre-outcomes; exact active-set simplex QP for the SCM weights; ridge correction (x1 - X0'w)'(X0'X0 + lambda I)^-1 X0' added to the weights; counterfactual = raw donor trajectory x augmented weights")
stata_parity_extra, key(stata_reference_note) val("Portable algorithm bridge; not a packaged Stata reference. allsynth v1.32 bcorrect(merge ridge) rejects the fixture (needs >= K + 2 = 17 controls, 16 available; r(198)) and, where feasible, estimates a different bias-corrected quantity (synth V-weighted weights + per-period ridgeregress outcome model). augsynth's remaining 7.9e-6 offset is its OSQP eps_abs = eps_rel = 1e-8 stopping rule on the simplex QP; the exact optimum agrees with the Python native path to 2e-8.")
stata_parity_extra, key(stata_command) val("Mata _sp_augsynth_bridge(region, year, gdppc, Basque Country, 1970)")

stata_parity_close, module(18_augsynth)

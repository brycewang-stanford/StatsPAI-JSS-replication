* ---------------------------------------------------------------------------
* Stata reference for tests/reference_parity/test_r2_frontier_parity.py
* (zero-inefficiency SF block).  Requires Stata 18 and Luis Chanci's
* user-written command chks (net install from luischanci.github.io/chks),
* installed into the PRIVATE ado dir _ado_r2_frontier/ (never PLUS); the
* lines below do that.
*
* Run from this directory:
*   stata-mp -b do _generate_r2_frontier_stata.do
* Reads frontier_struct_zisf.csv and writes r2_frontier_stata.json
* (numbers as %23.16e).
*
* Conventions pinned here
* -----------------------
* * chks y x1 x2, estimation(zsf) eoption(ml): linear zero-inefficiency SF,
*   log f = ln( P * phi(e; sv) + (1-P) * 2/s phi(e/s) Phi(-e lam / s) ),
*   e = y - x'b, P = invlogit(logist_probability) = P(fully efficient),
*   parameters lnsigma_u, lnsigma_v (log standard deviations).  This is the
*   same parameterisation as sp.zisf (p__cons, ln_sigma_u, ln_sigma_v).
* * Mata optimize(), evaluator type gf0 (numerical derivatives), default
*   convergence criteria; e(V) = optimize_result_V (inverse of the negative
*   numerical Hessian, i.e. OIM).
* * chks has no covariates in P and no cost option: only the production,
*   constant-probability model is referenced here.
* * SAMPLE TRAP: chks silently drops every row with missing ln(depvar), i.e.
*   y <= 0, even in the linear model (a check meant for its non-linear index
*   model).  Run as-is on this CSV it keeps only the y > 0 rows and returns a
*   different fit.  We therefore pass ys = y + 10 (all positive).  The
*   linear ZISF likelihood is exactly invariant to the shift apart from
*   _cons -> _cons + 10, so the test compares _cons - 10 (the shift is
*   written below as "y_shift").
* ---------------------------------------------------------------------------
version 18
set more off
set type double
local ado "`c(pwd)'/_ado_r2_frontier/"
capture mkdir "`ado'"
sysdir set PLUS "`ado'"
adopath ++ "`ado'"
capture which chks
if _rc net install chks, from("https://luischanci.github.io/chks/") replace

import delimited using "frontier_struct_zisf.csv", clear asdouble
local y_shift = 10
generate double ys = y + `y_shift'
quietly count if y <= 0
local n_nonpos = r(N)
chks ys x1 x2, estimation(zsf) eoption(ml) maxitera(1000)
* chks restores the data, so e(sample) is not usable; record instead that
* no row of the shifted outcome is <= 0 (so no row is dropped) and N.
quietly count if ys <= 0
local n_ys_nonpos = r(N)
local n_obs = _N
matrix b = e(b)
matrix V = e(V)
local names : colnames b

tempname fh
file open `fh' using "r2_frontier_stata.json", write replace text
file write `fh' "{" _n
file write `fh' `"  "zisf_chks": {"names": ["'
local k = colsof(b)
forvalues j = 1/`k' {
    local nm : word `j' of `names'
    file write `fh' `"""' "`nm'" `"""'
    if `j' < `k' file write `fh' ", "
}
file write `fh' "]," _n `"    "b": ["'
forvalues j = 1/`k' {
    file write `fh' %23.16e (b[1, `j'])
    if `j' < `k' file write `fh' ", "
}
file write `fh' "]," _n `"    "se": ["'
forvalues j = 1/`k' {
    file write `fh' %23.16e (sqrt(V[`j', `j']))
    if `j' < `k' file write `fh' ", "
}
file write `fh' "]," _n `"    "y_shift": "' %4.0f (`y_shift') `", "n_obs": "' %6.0f (`n_obs') `", "n_y_nonpositive": "' %6.0f (`n_nonpos') `", "n_shifted_y_nonpositive": "' %6.0f (`n_ys_nonpos') "}," _n
file write `fh' `"  "versions": {"stata": "`c(stata_version)'", "chks": "1.1 (chks.pkg dated 20190320)"}"' _n
file write `fh' "}" _n
file close `fh'

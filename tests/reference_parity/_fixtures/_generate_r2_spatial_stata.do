* Round-2 xsmle evidence for sp.spatial_panel two-way effects (r2_spatial).
*
* Same bytes as round 1 (spatial_survey_produc.csv / spatial_survey_usaww.csv).
* For SAR and SDM this records xsmle 1.4.5 under type(both) with three
* maximisers (default, technique(nr) difficult, technique(bfgs)), under
* type(both, leeyu) and type(ind, leeyu), and under type(ind): point
* estimates, e(ll), e(converged), e(ic), e(N). technique(bfgs) fails for
* SDM (the model is skipped when xsmle errors). Entity-effect fits use
* ml tolerances of 1e-14.
*
* xsmle goes into a PRIVATE ado tree (_ado_r2_spatial/plus, not committed).
* Run from this directory:
*   stata-mp -b do _generate_r2_spatial_stata.do
* Writes r2_spatial_stata.json
version 18
clear all
set type double
sysdir set PLUS "`c(pwd)'/_ado_r2_spatial/plus"
capture which xsmle
if _rc {
    ssc install xsmle, replace
}
mata: mata mlib index

import delimited using "spatial_survey_usaww.csv", clear varnames(1)
drop v1
mkmat _all, matrix(W)
import delimited using "spatial_survey_produc.csv", clear varnames(1)
encode state, gen(id)
xtset id year
local tol "nrtolerance(1e-14) tolerance(1e-14) ltolerance(1e-14)"

tempname fh
file open `fh' using "r2_spatial_stata.json", write replace
file write `fh' "{"
local first 1
foreach m in sar sdm {
    foreach cfg in default nr bfgs leeyu_both leeyu_ind ind {
        local ty "both"
        local opt ""
        if "`cfg'" == "nr"         local opt "technique(nr) difficult iterate(300)"
        if "`cfg'" == "bfgs"       local opt "technique(bfgs) iterate(300)"
        if "`cfg'" == "leeyu_both" local ty "both, leeyu"
        if "`cfg'" == "leeyu_ind"  local ty "ind, leeyu"
        if "`cfg'" == "ind"        local ty "ind"
        * the entity-effect fits converge; tighten -ml- so they are not
        * limited by its default stopping rule
        if inlist("`cfg'", "leeyu_both", "leeyu_ind", "ind") local opt "`tol'"
        capture noisily xsmle lgsp lpcap lpc lemp unemp, wmat(W) model(`m') fe type(`ty') nolog `opt'
        if _rc continue
        matrix b = e(b)
        local names : colfullnames b
        local k = colsof(b)
        if !`first' file write `fh' ","
        local first 0
        file write `fh' `""`m'_`cfg'": {"converged": "' (e(converged)) `", "ic": "' (e(ic)) `", "ll": "' %25.17e (e(ll)) `", "N": "' (e(N)) `", "coef": {"'
        forvalues j = 1/`k' {
            local nm : word `j' of `names'
            if `j' > 1 file write `fh' ","
            file write `fh' `"""' "`nm'" `"": "' %25.17e (b[1, `j'])
        }
        file write `fh' "}}"
    }
}
file write `fh' `", "versions": {"Stata": ""' "`c(stata_version)'" `"", "xsmle": ""'
tempname ah
file open `ah' using "`c(sysdir_plus)'x/xsmle.ado", read text
file read `ah' line
file close `ah'
local line : subinstr local line `"""' "", all
local line : subinstr local line "*! " "", all
local line : subinstr local line "* " "", all
file write `fh' `"`line'"' `""}}"'
file close `fh'

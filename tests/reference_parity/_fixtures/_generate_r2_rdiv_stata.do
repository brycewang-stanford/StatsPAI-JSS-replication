* ---------------------------------------------------------------------------
* Stata reference for tests/reference_parity/test_r2_rdiv_parity.py
* (round-2 open items of the rd_iv family).
*
* Requires Stata 18 (ivqregress is official since Stata 18) and, in a
* PRIVATE ado directory (never PLUS), installed on first run:
*   ssc install ivreg2 ranktest avar weakivtest weakiv
*
* Run _generate_r2_rdiv_R.R first (writes r2_rdiv_ivqr_oid.csv and
* r2_rdiv_ivqr_roots.csv; rd_iv_ivqr.csv / rd_iv_ivw.csv / rd_iv_rueda.csv
* come from _generate_rd_iv_R.R), then, from this directory:
*   stata-mp -b do _generate_r2_rdiv_stata.do
* Writes r2_rdiv_Stata.json (numbers as %23.16e).
*
* Blocks
* ------
* 1. ivqregress iqr (Chernozhukov-Hansen inverse QR; instrument = linear
*    projection of d on x and z, Wald criterion over a grid; SEs are the
*    CH sandwich with an Epanechnikov kernel and Silverman bandwidth).
*    "centred": noadaptive grid of 61 points on [root - 0.3, root + 0.3], so
*      the middle grid point is the R inverse-QR root (to rounding of the
*      grid arithmetic); e(b), e(V), e(bwidth_q1) are Stata's at the root.
*    "fine": noadaptive grid on [0.7, 1.4] with step 0.001 (701 points), the
*      same grid IVQR used in the R fixture; the estimate is a grid point.
*    "default": Stata's default adaptive 30-point grid, recorded to document
*      how far a default run sits from the root.
* 2. weakiv ivreg2 ..., md small on rd_iv_ivw.csv (k = 3, H0: beta = 0), run
*    twice: "byte" = the round-1 call (import delimited stores the integer-
*    valued z3 as BYTE; weakiv partials the controls out with
*    `replace var = resid`, and replacing a byte with non-integers promotes
*    it to FLOAT, not double, whatever `set type` says), and "double" =
*    the same call after `recast double z3`.
* 3. weakivtest after ivreg2 on the six effective-F designs of the round-1
*    fixture: r(F_eff) and the Montiel Olea-Pflueger critical values
*    r(c_TSLS_#), r(c_LIML_#), r(c_simp_#) for tau = 5, 10, 20, 30 %, and
*    r(K_eff_simp_#) (Patnaik effective degrees of freedom).
* ---------------------------------------------------------------------------
version 18
set more off
set type double

local here "`c(pwd)'"
local ado "`here'/_ado_r2_rdiv"
capture mkdir "`ado'"
sysdir set PLUS "`ado'"
net set ado "`ado'"
adopath ++ "`ado'"
foreach p in ivreg2 ranktest avar weakivtest weakiv {
    capture which `p'
    if _rc ssc install `p', replace
}

tempname fh
file open `fh' using "r2_rdiv_Stata.json", write replace text
file write `fh' "{" _n
file write `fh' `"  "meta": {"stata_version": "`c(stata_version)'", "stata_born_date": "`c(born_date)'", "'
foreach p in ivqregress weakivtest weakiv ivreg2 {
    quietly findfile `p'.ado
    file open _v using "`r(fn)'", read text
    local ver ""
    local i 0
    file read _v line
    while r(eof) == 0 & `"`ver'"' == "" & `i' < 40 {
        if strpos(`"`line'"', "*!") == 1 | strpos(`"`line'"', "this version:") {
            local ver = trim(subinstr(subinstr(`"`line'"', char(9), " ", .), `"""', "", .))
        }
        local ++i
        file read _v line
    }
    file close _v
    file write `fh' `""`p'": "`ver'", "'
}
file write `fh' `""note": "ivqregress iqr; weakiv md small; weakivtest"},"' _n

* ---- 1. ivqregress iqr -----------------------------------------------------
import delimited using "r2_rdiv_ivqr_roots.csv", clear asdouble
forvalues i = 1/`=_N' {
    local d = design[`i']
    local t = string(tau[`i'], "%4.2f")
    local root_`d'_`=100*tau[`i']' = root[`i']
}
file write `fh' `"  "ivqregress": {"' _n
local firstd 1
foreach d in jid oid {
    if "`d'" == "jid" {
        local csv "rd_iv_ivqr.csv"
        local eq "y x1 (d = z)"
    }
    else {
        local csv "r2_rdiv_ivqr_oid.csv"
        local eq "y x1 x2 (d = z1 z2 z3)"
    }
    import delimited using "`csv'", clear asdouble
    if !`firstd' file write `fh' "," _n
    local firstd 0
    file write `fh' `"    "`d'": {"' _n
    local firstt 1
    foreach q in 25 50 75 {
        local r = `root_`d'_`q''
        if !`firstt' file write `fh' "," _n
        local firstt 0
        file write `fh' `"      "0.`q'": {"root_used": "' %23.16e (`r') ", " _n
        * centred grid
        quietly ivqregress iqr `eq', quantile(0.`q') bound(`=`r'-0.3' `=`r'+0.3') ngrid(61) noadaptive nolog
        matrix b = e(b)
        matrix V = e(V)
        local k = colsof(b)
        file write `fh' `"        "centred": {"b": ["'
        forvalues j = 1/`k' {
            file write `fh' %23.16e (b[1,`j'])
            if `j' < `k' file write `fh' ", "
        }
        file write `fh' `"], "se": ["'
        forvalues j = 1/`k' {
            file write `fh' %23.16e (sqrt(V[`j',`j']))
            if `j' < `k' file write `fh' ", "
        }
        local names : colnames b
        file write `fh' `"], "names": ""' "`names'" `"", "bwidth": "' %23.16e (e(bwidth_q1)) ", "
        file write `fh' `""kernel": ""' "`e(kernel)'" `"", "bwrule": ""' "`e(bwrule)'" `""}, "' _n
        * fine fixed grid (step 0.001)
        quietly ivqregress iqr `eq', quantile(0.`q') bound(0.7 1.4) ngrid(701) noadaptive nolog
        file write `fh' `"        "fine": {"b1": "' %23.16e (_b[d]) `", "grid_lo": 0.7, "grid_hi": 1.4, "ngrid": 701}, "' _n
        * default adaptive grid
        quietly ivqregress iqr `eq', quantile(0.`q') nolog
        file write `fh' `"        "default": {"b1": "' %23.16e (_b[d]) "}}"
    }
    file write `fh' _n "    }"
}
file write `fh' _n "  }," _n

* ---- 2. weakiv md small: byte vs double z3 -----------------------------------
file write `fh' `"  "weakiv_md_small_ivw3": {"' _n
foreach st in byte double {
    import delimited using "rd_iv_ivw.csv", clear asdouble
    local z3type : type z3
    if "`st'" == "double" recast double z3
    quietly weakiv ivreg2 y x1 x2 (d = z1 z2 z3), md small
    file write `fh' `"    "`st'": {"z3_storage_type": ""' "`: type z3'" `"", "clr_stat": "' %23.16e (e(clr_stat)) ", "
    file write `fh' `""clr_p": "' %23.16e (e(clr_p)) `", "k_chi2": "' %23.16e (e(k_chi2)) ", "
    file write `fh' `""k_p": "' %23.16e (e(k_p)) `", "ar_chi2": "' %23.16e (e(ar_chi2)) ", "
    file write `fh' `""ar_p": "' %23.16e (e(ar_p)) `", "rk": "' %23.16e (e(rk)) ", "
    file write `fh' `""j_chi2": "' %23.16e (e(j_chi2)) `", "clrsims": "' %9.0f (e(clrsims)) ", "
    file write `fh' `""clr_cset": ""' "`e(clr_cset)'" `""}"'
    if "`st'" == "byte" file write `fh' ","
    file write `fh' _n
}
file write `fh' "  }," _n

* ---- 3. weakivtest critical values -----------------------------------------
file write `fh' `"  "weakivtest": {"' _n
local specs `" "ivw1_hc|rd_iv_ivw.csv|y x1 x2 (d = z1), robust" "ivw1_cl|rd_iv_ivw.csv|y x1 x2 (d = z1), cluster(cl)" "ivw3_hc|rd_iv_ivw.csv|y x1 x2 (d = z1 z2 z3), robust" "ivw3_cl|rd_iv_ivw.csv|y x1 x2 (d = z1 z2 z3), cluster(cl)" "rueda_hc|rd_iv_rueda.csv|e_vote_buying lpopulation lpotencial (lm_pob_mesa = lz_pob_mesa_f), robust" "rueda_cl|rd_iv_rueda.csv|e_vote_buying lpopulation lpotencial (lm_pob_mesa = lz_pob_mesa_f), cluster(muni_code)" "'
local first 1
foreach s of local specs {
    gettoken key rest : s, parse("|")
    gettoken bar rest : rest, parse("|")
    gettoken csv rest : rest, parse("|")
    gettoken bar cmd : rest, parse("|")
    import delimited using "`csv'", clear asdouble
    quietly ivreg2 `cmd'
    quietly weakivtest
    if !`first' file write `fh' "," _n
    local first 0
    file write `fh' `"    "`key'": {"F_eff": "' %23.16e (r(F_eff)) `", "K": "' %3.0f (r(K)) ", "
    foreach m in TSLS LIML simp {
        foreach tau in 5 10 20 30 {
            file write `fh' `""c_`m'_`tau'": "' %23.16e (r(c_`m'_`tau')) ", "
        }
    }
    foreach tau in 5 10 20 30 {
        file write `fh' `""K_eff_simp_`tau'": "' %23.16e (r(K_eff_simp_`tau')) ", "
    }
    file write `fh' `""eps": "' %23.16e (r(eps)) `", "level": "' %23.16e (r(level)) "}"
}
file write `fh' _n "  }" _n
file write `fh' "}" _n
file close `fh'

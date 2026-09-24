* ---------------------------------------------------------------------------
* Stata reference for tests/reference_parity/test_vce_grammar_stata_parity.py
*
* Requires: Stata 18 (every command below is official; nothing to install).
* Run:      stata -b do _generate_vce_grammar_stata.do   (from this directory)
*
* What this fixture pins
* ----------------------
* The Stata meaning of vce(oim) / vce(robust) / vce(cluster c) on every
* StatsPAI estimator that exposes robust= / cluster= / vce=.  Before the
* shared SE parser landed, StatsPAI's ML estimators computed the robust
* sandwich without Stata's N/(N-1) factor, several cluster sandwiches
* carried the regress-family (N-1)/(N-K) factor that Stata's ML commands
* do not use, `nbreg` built its sandwich from the Poisson score, and
* `truncreg` / `biprobit` / `betareg` ignored robust= and cluster=
* altogether.  Each of those is a number recorded here.
*
* Data is generated and exported HERE so both sides read the same bytes.
* ---------------------------------------------------------------------------
version 18
clear all
set type double
set seed 20260915
set obs 1200

gen long   id  = _n
gen double x1  = rnormal()
gen double x2  = rnormal()
gen int    g   = mod(_n, 40) + 1
gen int    grp = ceil(_n / 4)
gen int    gc  = ceil(grp / 10)

* Linear, heteroskedastic.
gen double yl = 1 + 0.5*x1 - 0.3*x2 + (1 + 0.5*abs(x1))*rnormal()
* Binary (logit and probit DGPs).
gen byte   yb = (0.2 + 0.6*x1 - 0.4*x2 + rlogistic()) > 0
gen byte   yp = (-0.1 + 0.5*x1 + 0.3*x2 + rnormal()) > 0
* Counts: Poisson, NB2 (alpha = 0.5), zero-inflated Poisson.
gen int    yc  = rpoisson(exp(0.3 + 0.4*x1 - 0.2*x2))
gen double nbm = exp(0.5 + 0.4*x1 - 0.2*x2)
gen int    ynb = rnbinomial(2, 2/(2 + nbm))
gen int    yz  = cond(runiform() < invlogit(-0.5 + 0.5*x2), 0, rpoisson(exp(0.4 + 0.4*x1)))
* Ordered (4 categories) and multinomial (3 categories).
gen double lat = 0.7*x1 - 0.4*x2 + rlogistic()
gen byte   yo  = (lat > -1) + (lat > 0) + (lat > 1)
gen double u0  = -ln(-ln(runiform()))
gen double u1  = 0.2 + 0.5*x1 - ln(-ln(runiform()))
gen double u2  = -0.3 + 0.8*x2 - ln(-ln(runiform()))
gen byte   ym  = cond(u1 > u0 & u1 > u2, 1, cond(u2 > u0 & u2 > u1, 2, 0))
* Conditional logit: one choice per group of four.
gen double util = 0.8*x1 - 0.5*x2 - ln(-ln(runiform()))
bysort grp (util): gen byte yk = (_n == _N)
sort id
* Fractional outcome strictly inside (0, 1).
gen double yf = invlogit(-0.2 + 0.6*x1 - 0.3*x2 + 0.5*rnormal())
* Truncated-from-below outcome (estimated on ytr > 0).
gen double ytr = 0.5 + 0.8*x1 - 0.4*x2 + rnormal()
* Bivariate probit, rho = 0.5.
gen double e1 = rnormal()
gen double e2 = 0.5*e1 + sqrt(0.75)*rnormal()
gen byte   y1 = (0.3 + 0.5*x1 + e1) > 0
gen byte   y2 = (-0.2 + 0.3*x1 + 0.4*x2 + e2) > 0
* Linear IV with one endogenous regressor, two instruments.
gen double z1   = rnormal()
gen double z2   = rnormal()
gen double v    = rnormal()
gen double endo = 0.5*z1 + 0.4*z2 + 0.3*x1 + v
gen double yiv  = 1 + 0.7*endo + 0.4*x1 + v + rnormal()
* Zero-inflated NB2 counts. Generated last so every draw above is unchanged.
gen int    yzn = cond(runiform() < invlogit(-0.5 + 0.5*x2), 0, rnbinomial(2, 2/(2 + exp(0.4 + 0.4*x1))))
* Binary panel outcomes with a genuine random effect per panel g (sigma_u = 1
* for logit, 0.8 for probit), so xtlogit/xtprobit, re sit away from the
* sigma_u = 0 boundary. Appended after yzn: earlier draws are unchanged.
gen int    gg   = ceil(g / 4)
bysort g (id): gen double re_u = rnormal() if _n == 1
bysort g (id): replace re_u = re_u[1]
sort id
gen byte   ybp  = (0.2 + 0.6*x1 - 0.4*x2 + re_u + rlogistic()) > 0
gen byte   ypp  = (-0.1 + 0.5*x1 + 0.3*x2 + 0.8*re_u + rnormal()) > 0
drop nbm lat u0 u1 u2 util e1 e2 v re_u

format x1 x2 yl yf ytr z1 z2 endo yiv %21.16e
export delimited id x1 x2 g grp gc yl yb yp yc ynb yz yo ym yk yf ytr y1 y2 z1 z2 endo yiv yzn ///
    gg ybp ypp using "vce_grammar_data.csv", replace datafmt

* ---- JSON helpers --------------------------------------------------------
* _fit <key> "<command with trailing comma>" "<vce option>" name|coef ...
* writes b_<name> = _b[coef] and se_<name> = _se[coef] for each term.
capture program drop _fit
program define _fit
    gettoken key 0 : 0
    gettoken cmd 0 : 0
    gettoken vopt 0 : 0
    local terms `0'
    quietly `cmd' `vopt'
    file write fh `"  "`key'": {"' _n
    foreach t of local terms {
        gettoken tk tc : t, parse("|")
        local tc = substr(`"`tc'"', 2, .)
        file write fh `"    "b_`tk'": "' %21.16e (_b[`tc']) `","' _n
        file write fh `"    "se_`tk'": "' %21.16e (_se[`tc']) `","' _n
    }
    local nclust = cond(missing(e(N_clust)), 0, e(N_clust))
    file write fh `"    "N_clust": "' %21.16e (`nclust') `","' _n
    * Log (quasi-)likelihood at Stata's optimum, so a test can show that a
    * point-estimate gap comes from where Stata's optimiser stopped rather
    * than from a different likelihood. regress/ivregress report it too.
    local llval = cond(missing(e(ll)), 0, e(ll))
    file write fh `"    "ll": "' %21.16e (`llval') `","' _n
    file write fh `"    "N": "' %21.16e (e(N)) _n
    file write fh `"  },"' _n
end

capture file close fh
file open fh using "vce_grammar_stata.json", write replace text
file write fh "{" _n

* ---- least squares -------------------------------------------------------
_fit "regress_ols"     "regress yl x1 x2," ""               x1|x1 cons|_cons
_fit "regress_robust"  "regress yl x1 x2," "vce(robust)"    x1|x1 cons|_cons
_fit "regress_hc3"     "regress yl x1 x2," "vce(hc3)"       x1|x1 cons|_cons
_fit "regress_cluster" "regress yl x1 x2," "vce(cluster g)" x1|x1 cons|_cons

* ---- GLM -------------------------------------------------------------------
foreach fam in gaussian poisson binomial {
    local dv = cond("`fam'" == "gaussian", "yl", cond("`fam'" == "poisson", "yc", "yb"))
    _fit "glm_`fam'_oim"     "glm `dv' x1 x2, family(`fam')" ""               x1|x1 cons|_cons
    _fit "glm_`fam'_robust"  "glm `dv' x1 x2, family(`fam')" "vce(robust)"    x1|x1 cons|_cons
    _fit "glm_`fam'_cluster" "glm `dv' x1 x2, family(`fam')" "vce(cluster g)" x1|x1 cons|_cons
}

* ---- GLM with non-canonical links ------------------------------------------
* Stata's glm default vce(oim) uses the observed information; for a
* non-canonical link it differs from the expected information that IRLS
* (and R's glm) reports. vce(robust) and vce(cluster) use the OIM bread too.
foreach spec in "probit yp binomial" "cloglog yb binomial" "log yl gaussian" {
    local lnk : word 1 of `spec'
    local dv  : word 2 of `spec'
    local fam : word 3 of `spec'
    _fit "glm_`lnk'_oim"     "glm `dv' x1 x2, family(`fam') link(`lnk')" ""               x1|x1 x2|x2 cons|_cons
    _fit "glm_`lnk'_robust"  "glm `dv' x1 x2, family(`fam') link(`lnk')" "vce(robust)"    x1|x1 x2|x2 cons|_cons
    _fit "glm_`lnk'_cluster" "glm `dv' x1 x2, family(`fam') link(`lnk')" "vce(cluster g)" x1|x1 x2|x2 cons|_cons
}

* ---- single-index ML -------------------------------------------------------
foreach spec in "logit yb" "probit yp" "cloglog yb" "poisson yc" {
    local cmdname : word 1 of `spec'
    _fit "`cmdname'_oim"     "`spec' x1 x2," ""               x1|x1 cons|_cons
    _fit "`cmdname'_robust"  "`spec' x1 x2," "vce(robust)"    x1|x1 cons|_cons
    _fit "`cmdname'_cluster" "`spec' x1 x2," "vce(cluster g)" x1|x1 cons|_cons
}

_fit "nbreg_oim"     "nbreg ynb x1 x2," ""               x1|x1 cons|_cons lnalpha|/lnalpha
_fit "nbreg_robust"  "nbreg ynb x1 x2," "vce(robust)"    x1|x1 cons|_cons lnalpha|/lnalpha
_fit "nbreg_cluster" "nbreg ynb x1 x2," "vce(cluster g)" x1|x1 cons|_cons lnalpha|/lnalpha
_fit "nb1_oim"     "nbreg ynb x1 x2, dispersion(constant)" ""               x1|x1 cons|_cons lndelta|/lndelta
_fit "nb1_robust"  "nbreg ynb x1 x2, dispersion(constant)" "vce(robust)"    x1|x1 cons|_cons lndelta|/lndelta
_fit "nb1_cluster" "nbreg ynb x1 x2, dispersion(constant)" "vce(cluster g)" x1|x1 cons|_cons lndelta|/lndelta

* ---- ordered / multinomial / conditional ----------------------------------
foreach cmdname in ologit oprobit {
    _fit "`cmdname'_oim"     "`cmdname' yo x1 x2," ""               x1|x1 x2|x2
    _fit "`cmdname'_robust"  "`cmdname' yo x1 x2," "vce(robust)"    x1|x1 x2|x2
    _fit "`cmdname'_cluster" "`cmdname' yo x1 x2," "vce(cluster g)" x1|x1 x2|x2
}
_fit "mlogit_oim"     "mlogit ym x1 x2, baseoutcome(0)" ""               x1_1|1:x1 x2_2|2:x2 cons_1|1:_cons
_fit "mlogit_robust"  "mlogit ym x1 x2, baseoutcome(0)" "vce(robust)"    x1_1|1:x1 x2_2|2:x2 cons_1|1:_cons
_fit "mlogit_cluster" "mlogit ym x1 x2, baseoutcome(0)" "vce(cluster g)" x1_1|1:x1 x2_2|2:x2 cons_1|1:_cons
_fit "clogit_oim"     "clogit yk x1 x2, group(grp)" ""                x1|x1 x2|x2
_fit "clogit_robust"  "clogit yk x1 x2, group(grp)" "vce(robust)"     x1|x1 x2|x2
_fit "clogit_cluster" "clogit yk x1 x2, group(grp)" "vce(cluster gc)" x1|x1 x2|x2

* ---- zero-inflated ---------------------------------------------------------
_fit "zip_oim"     "zip yz x1 x2, inflate(x1 x2)" ""               x1|yz:x1 cons|yz:_cons inf_x2|inflate:x2
_fit "zip_robust"  "zip yz x1 x2, inflate(x1 x2)" "vce(robust)"    x1|yz:x1 cons|yz:_cons inf_x2|inflate:x2
_fit "zip_cluster" "zip yz x1 x2, inflate(x1 x2)" "vce(cluster g)" x1|yz:x1 cons|yz:_cons inf_x2|inflate:x2

_fit "zinb_oim"     "zinb yzn x1 x2, inflate(x1 x2)" ""               x1|yzn:x1 cons|yzn:_cons inf_x2|inflate:x2 lnalpha|/lnalpha
_fit "zinb_robust"  "zinb yzn x1 x2, inflate(x1 x2)" "vce(robust)"    x1|yzn:x1 cons|yzn:_cons inf_x2|inflate:x2 lnalpha|/lnalpha
_fit "zinb_cluster" "zinb yzn x1 x2, inflate(x1 x2)" "vce(cluster g)" x1|yzn:x1 cons|yzn:_cons inf_x2|inflate:x2 lnalpha|/lnalpha

* ---- truncated / bivariate probit / beta / fractional ----------------------
_fit "truncreg_oim"     "truncreg ytr x1 x2 if ytr > 0, ll(0)" ""               x1|x1 cons|_cons
_fit "truncreg_robust"  "truncreg ytr x1 x2 if ytr > 0, ll(0)" "vce(robust)"    x1|x1 cons|_cons
_fit "truncreg_cluster" "truncreg ytr x1 x2 if ytr > 0, ll(0)" "vce(cluster g)" x1|x1 cons|_cons
_fit "biprobit_oim"     "biprobit (y1 = x1 x2) (y2 = x1 x2)," ""               x1_1|y1:x1 x2_2|y2:x2 athrho|/athrho
_fit "biprobit_robust"  "biprobit (y1 = x1 x2) (y2 = x1 x2)," "vce(robust)"    x1_1|y1:x1 x2_2|y2:x2 athrho|/athrho
_fit "biprobit_cluster" "biprobit (y1 = x1 x2) (y2 = x1 x2)," "vce(cluster g)" x1_1|y1:x1 x2_2|y2:x2 athrho|/athrho
_fit "betareg_oim"     "betareg yf x1 x2," ""               x1|yf:x1 cons|yf:_cons scale|scale:_cons
_fit "betareg_robust"  "betareg yf x1 x2," "vce(robust)"    x1|yf:x1 cons|yf:_cons scale|scale:_cons
_fit "betareg_cluster" "betareg yf x1 x2," "vce(cluster g)" x1|yf:x1 cons|yf:_cons scale|scale:_cons
* fracreg has no vce(oim): Stata's default and only non-cluster vcetype is robust.
_fit "fracreg_robust"  "fracreg logit yf x1 x2," ""               x1|x1 cons|_cons
_fit "fracreg_cluster" "fracreg logit yf x1 x2," "vce(cluster g)" x1|x1 cons|_cons

* ---- panel binary (xtlogit / xtprobit) -----------------------------------
* Non-adaptive Gauss-Hermite with 12 points is StatsPAI's integration rule;
* Stata's default is mean-variance adaptive quadrature, a different
* approximation to the same integral. vce(robust) clusters on the panel.
quietly xtset g
_fit "xtlogit_re_oim"      "xtlogit ybp x1 x2, re intmethod(ghermite) intpoints(12)"  ""                x1|x1 cons|_cons lnsig2u|/lnsig2u
_fit "xtlogit_re_robust"   "xtlogit ybp x1 x2, re intmethod(ghermite) intpoints(12)"  "vce(robust)"     x1|x1 cons|_cons lnsig2u|/lnsig2u
_fit "xtlogit_re_cluster"  "xtlogit ybp x1 x2, re intmethod(ghermite) intpoints(12)"  "vce(cluster gg)" x1|x1 cons|_cons lnsig2u|/lnsig2u
_fit "xtprobit_re_oim"     "xtprobit ypp x1 x2, re intmethod(ghermite) intpoints(12)" ""                x1|x1 cons|_cons lnsig2u|/lnsig2u
_fit "xtprobit_re_robust"  "xtprobit ypp x1 x2, re intmethod(ghermite) intpoints(12)" "vce(robust)"     x1|x1 cons|_cons lnsig2u|/lnsig2u
_fit "xtprobit_re_cluster" "xtprobit ypp x1 x2, re intmethod(ghermite) intpoints(12)" "vce(cluster gg)" x1|x1 cons|_cons lnsig2u|/lnsig2u
_fit "xtlogit_fe_oim"      "xtlogit ybp x1 x2, fe"                                    ""                x1|x1 x2|x2

* ---- LIML ----------------------------------------------------------------
* `small` is the convention of every StatsPAI linear IV estimator (and of
* tests/stata_parity/59_liml.do): RSS/(n-k), N/(N-K) on the robust meat and
* G/(G-1)*(N-1)/(N-K) on the cluster meat.
_fit "liml_unadjusted" "ivregress liml yiv x1 (endo = z1 z2), small" ""               endo|endo x1|x1
_fit "liml_robust"     "ivregress liml yiv x1 (endo = z1 z2), small" "vce(robust)"    endo|endo x1|x1
_fit "liml_cluster"    "ivregress liml yiv x1 (endo = z1 z2), small" "vce(cluster g)" endo|endo x1|x1

file write fh `"  "_meta": {"' _n
file write fh `"    "stata_version": "' `"""' "`c(stata_version)'" `"""' `","' _n
file write fh `"    "flavor": "' `"""' "`c(flavor)' `c(edition_real)'" `"""' `","' _n
file write fh `"    "seed": 20260915,"' _n
file write fh `"    "generated": "' `"""' "`c(current_date)'" `"""' _n
file write fh `"  }"' _n
file write fh "}" _n
file close fh
display "wrote vce_grammar_stata.json and vce_grammar_data.csv"

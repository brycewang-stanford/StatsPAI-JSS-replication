* tests/stata_parity/73_did2s.do
*
* Module 73: Gardner (2022) two-stage difference-in-differences.
*   StatsPAI:  sp.gardner_did
*   R:         did2s::did2s (1.2.1)
*   Stata:     did2s                                  <-- this file
*
* Butts' `did2s` on SSC is the Stata port of the same two-stage estimator,
* so this is a like-for-like third side rather than a re-implementation.
*
* Data: the mpdta replica dumped by 73_did2s.py. `first_treat == 0` marks
* never-treated counties, so the post indicator is
* (first_treat > 0 & year >= first_treat) -- which is exactly the committed
* `treat` column; this script rebuilds it explicitly and asserts the two
* agree so an upstream fixture change cannot silently redefine treatment.
*
* SE convention. Like the R package, `did2s` reports Gardner's (2022)
* corrected clustered variance: first-stage estimation error is propagated
* into the second-stage sandwich and no small-sample cluster factor is
* applied. sp.gardner_did's default vce="analytic" builds the same two-stage
* influence function, so estimate and SE are both strict parity rows. Stata
* solves the first stage exactly (as StatsPAI does), so the Stata SE lands
* on the Python SE at rel 1e-14 while R's fixest demeaning tolerance leaves
* both at ~1e-10 / 1e-8 from R. The Python side also emits a
* `static_ATT_stage2_se` diagnostic (the pre-correction stage-2-only SE,
* ~26% low) that has no Stata counterpart.
*
* Tolerance: rel < 1e-6 on the point estimate and on the SE.

version 18
clear all

do _common.do
stata_parity_init, module(73_did2s)
stata_parity_open, module(73_did2s)

import delimited "${STATA_PARITY_DATA}/73_did2s.csv", clear case(preserve)
count
local n = r(N)

gen byte treated = (first_treat > 0 & year >= first_treat)
qui count if treated != treat
if r(N) != 0 {
    display as error "fixture drift: rebuilt post indicator disagrees with committed treat column in `r(N)' rows"
    exit 459
}

did2s lemp, first_stage(i.countyreal i.year) second_stage(treated) ///
    treatment(treated) cluster(countyreal)

local bv = _b[treated]
local sv = _se[treated]
local lo = `bv' - ${STATA_PARITY_Z95} * `sv'
local hi = `bv' + ${STATA_PARITY_Z95} * `sv'

stata_parity_row, stat(static_ATT) est(`bv') std(`sv') cilo(`lo') cihi(`hi') nob(`n')

stata_parity_extra, key(stata_command) val("did2s lemp, first_stage(i.countyreal i.year) second_stage(treated) treatment(treated) cluster(countyreal)")
stata_parity_extra, key(se_convention) val("did2s corrected two-stage clustered variance (stage-1 estimation error propagated, no small-sample factor), matching did2s::did2s in R and sp.gardner_did vce='analytic'")
stata_parity_extra, key(stata_bridge_status) val("materialized 2026-08-06 with licensed Stata 18")

stata_parity_close, module(73_did2s)

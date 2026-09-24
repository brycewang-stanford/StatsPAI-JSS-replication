#!/usr/bin/env python3
"""Generate the audit-grade R/Stata replacement table.

``Paper-JSS/parity/replacement-table.md`` is the per-row detail behind the
high-level coverage table in the manuscript's architecture section. It used
to be a hand-maintained draft in which 54 of 100 rows carried a literal
``(verify)`` placeholder and several rows named ``sp.`` entry points that do
not exist in the registry (``sp.coxph``, ``sp.quantile``, ``sp.svar``,
``sp.spatial_lag``, ...). A reviewer typing those names gets an
``AttributeError``, which is a worse failure than an honest blank.

This script splits the table into the part a human must decide and the part
a machine must not be allowed to get wrong:

*Curated* (the ``ROWS`` table below): which reference package or Stata
command a StatsPAI entry point is meant to replace, and whether the
relationship is equivalent / subset / superset / partial / new. That is
editorial judgement and is version-controlled here.

*Derived* (everything in the Evidence column): whether the named function
actually exists in the live registry, and what committed numerical evidence
backs it. Both come from artifacts, never from prose:

  - ``statspai.list_functions()``            -> the name resolves
  - ``src/statspai/_parity_index.json``      -> evidence tier + test path
  - ``tests/r_parity/results/*_py.json``     -> Track A module membership
  - ``tests/stata_parity/results/*_Stata.json`` -> three-way coverage

A row whose function is absent from the registry is rendered as a hard
``NAME NOT IN REGISTRY`` failure and the script exits non-zero, so the table
cannot drift back into naming functions that do not exist.

Usage::

    python replication/scripts/build_replacement_table.py           # write
    python replication/scripts/build_replacement_table.py --check   # CI

The ``--check`` mode regenerates in memory and diffs against the committed
file, so a registry rename or a new parity module shows up as a failing
check rather than as silently stale documentation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAPER_DIR = HERE.parents[1]
ROOT = PAPER_DIR.parent
OUT = PAPER_DIR / "parity" / "replacement-table.md"
PARITY_INDEX = ROOT / "src" / "statspai" / "_parity_index.json"
R_RESULTS = ROOT / "tests" / "r_parity" / "results"
STATA_RESULTS = ROOT / "tests" / "stata_parity" / "results"

# --------------------------------------------------------------------------
# Curated content. Each row is
#   (domain, r_reference, stata_reference, entry_points, relationship, note)
# ``entry_points`` is the list of registry names the row claims; the rendered
# ``sp.`` call may carry arguments, which are kept in ``call``.
# --------------------------------------------------------------------------
Row = dict
FUNCTION_NAMES: set[str] = set()


def R(domain, r_ref, stata_ref, call, functions, relationship, note=""):
    return {
        "domain": domain,
        "r": r_ref,
        "stata": stata_ref,
        "call": call,
        "functions": functions,
        "relationship": relationship,
        "note": note,
    }


ROWS: list[Row] = [
    # ---- core regression ------------------------------------------------
    R(
        "OLS",
        "`stats::lm`, `sandwich::vcovHC`",
        "`regress, robust`",
        "`sp.regress`",
        ["regress"],
        "equivalent",
    ),
    R(
        "OLS clusters",
        "`sandwich::vcovCL`",
        "`regress, vce(cluster id)`",
        '`sp.regress(vce="cluster", cluster_id=...)`',
        ["regress"],
        "equivalent",
    ),
    R(
        "Robust SE family (HC2/HC3)",
        "`sandwich::vcovHC`",
        "`regress, vce(hc2)`/`vce(hc3)`",
        '`sp.regress(robust="hc2"|"hc3")`',
        ["regress"],
        "equivalent",
    ),
    R(
        "Multiway cluster SE",
        "`sandwich::vcovCL`",
        "`vcemway`, `reghdfe`",
        "`sp.multiway_cluster_vcov`, `sp.twoway_cluster`",
        ["multiway_cluster_vcov", "twoway_cluster"],
        "equivalent",
        "Stata side is an audited CGM/Mata bridge; `reghdfe` SEs kept as a diagnostic row",
    ),
    R(
        "CR2/CR3 cluster SE",
        "`clubSandwich::vcovCR`",
        "--- (Stata built-in is CR1)",
        "`sp.cr2_se`, `sp.cr3_jackknife_vcov`",
        ["cr2_se", "cr3_jackknife_vcov"],
        "superset",
        "Stata has no built-in CR2/CR3; the bridge implements clubSandwich's algebra",
    ),
    R(
        "Wild cluster bootstrap",
        "`fwildclusterboot::boottest`",
        "`boottest`",
        "`sp.wild_cluster_bootstrap`, `sp.wild_cluster_ci_inv`",
        ["wild_cluster_bootstrap", "wild_cluster_ci_inv"],
        "equivalent",
    ),
    R(
        "2SLS",
        "`AER::ivreg`, `ivreg::ivreg`",
        "`ivregress 2sls`",
        "`sp.iv`",
        ["iv"],
        "equivalent",
    ),
    R(
        "LIML",
        "`ivmodel::LIML`",
        "`ivregress liml, small`",
        "`sp.liml`",
        ["liml"],
        "equivalent",
    ),
    R(
        "Anderson--Rubin weak-IV inference",
        "`ivmodel::AR.test`",
        "`weakiv`",
        "`sp.anderson_rubin_test`, `sp.anderson_rubin_ci`",
        ["anderson_rubin_test", "anderson_rubin_ci"],
        "equivalent",
    ),
    R(
        "JIVE / UJIVE",
        "`SteinIV::jive.est`",
        "`jive`",
        "`sp.jive`",
        ["jive"],
        "equivalent",
    ),
    R(
        "GMM",
        "`gmm::gmm`",
        "`gmm`",
        "`sp.gmm`",
        ["gmm"],
        "subset",
        "linear and nonlinear moment conditions; Stata's `gmm` option surface is wider",
    ),
    R(
        "Three-stage least squares",
        "`systemfit::systemfit`",
        "`reg3`",
        "`sp.three_sls`",
        ["three_sls"],
        "equivalent",
    ),
    R(
        "SUR",
        "`systemfit::systemfit`",
        "`sureg`",
        "`sp.sureg`",
        ["sureg"],
        "equivalent",
        "Sigma divisor n (`sureg` default / `noDfCor`)",
    ),
    R(
        "HDFE FE",
        "`fixest::feols`",
        "`reghdfe`",
        "`sp.feols`, `sp.hdfe_ols`, `sp.absorb_ols`",
        ["feols", "hdfe_ols", "absorb_ols"],
        "equivalent",
    ),
    R(
        "HDFE Poisson",
        "`fixest::fepois`",
        "`ppmlhdfe`",
        "`sp.ppmlhdfe`, `sp.fepois`",
        ["ppmlhdfe", "fepois"],
        "equivalent",
    ),
    R(
        "Panel: FE/RE",
        "`plm::plm`",
        "`xtreg, fe`/`xtreg, re`",
        '`sp.panel(model="fe"|"re")`',
        ["panel"],
        "equivalent",
    ),
    R(
        "Panel: dynamic GMM",
        "`plm::pgmm`",
        "`xtabond`, `xtdpdsys`",
        "`sp.xtabond`, `sp.xtdpdsys`, `sp.xtlsdvc`",
        ["xtabond", "xtdpdsys", "xtlsdvc"],
        "equivalent",
    ),
    R(
        "Panel: FGLS",
        "`plm::pggls`",
        "`xtgls`",
        "`sp.panel_fgls`",
        ["panel_fgls"],
        "equivalent",
    ),
    R(
        "Panel: unit roots",
        "`plm::purtest`",
        "`xtunitroot`",
        "`sp.panel_unitroot`, `sp.ips`",
        ["panel_unitroot", "ips"],
        "equivalent",
    ),
    R(
        "Newey--West HAC",
        "`sandwich::NeweyWest`",
        "`newey`",
        "`sp.regress`",
        ["regress"],
        "equivalent",
    ),
    # ---- limited dependent variables ------------------------------------
    R(
        "Probit/Logit",
        "`stats::glm(family=binomial)`",
        "`probit`, `logit`",
        "`sp.probit`, `sp.logit`, `sp.glm`",
        ["probit", "logit", "glm"],
        "equivalent",
    ),
    R(
        "Poisson/NegBin",
        "`stats::glm`, `MASS::glm.nb`",
        "`poisson`, `nbreg`",
        "`sp.poisson`, `sp.nbreg`",
        ["poisson", "nbreg"],
        "equivalent",
    ),
    R(
        "Zero-inflated count",
        "`pscl::zeroinfl`",
        "`zip`, `zinb`",
        "`sp.zip_model`, `sp.zinb`",
        ["zip_model", "zinb"],
        "equivalent",
    ),
    R(
        "Ordered / multinomial",
        "`MASS::polr`, `nnet::multinom`",
        "`ologit`, `oprobit`, `mlogit`",
        "`sp.ologit`, `sp.oprobit`, `sp.mlogit`",
        ["ologit", "oprobit", "mlogit"],
        "equivalent",
    ),
    R(
        "Conditional logit",
        "`survival::clogit`",
        "`clogit`",
        "`sp.clogit`",
        ["clogit"],
        "equivalent",
    ),
    R(
        "Heckman",
        "`sampleSelection::heckit`",
        "`heckman`",
        "`sp.heckman`",
        ["heckman"],
        "equivalent",
    ),
    R("Tobit", "`censReg::censReg`", "`tobit`", "`sp.tobit`", ["tobit"], "equivalent"),
    R(
        "Truncated regression",
        "`truncreg::truncreg`",
        "`truncreg, ll(0)`",
        "`sp.truncreg`",
        ["truncreg"],
        "equivalent",
    ),
    R(
        "Beta regression",
        "`betareg::betareg`",
        "`betareg`",
        "`sp.betareg`",
        ["betareg"],
        "equivalent",
        "betareg SEs are expected-information (documented)",
    ),
    R(
        "Fractional response",
        "`stats::glm(quasibinomial)`",
        "`fracreg`",
        "`sp.fracreg`",
        ["fracreg"],
        "equivalent",
    ),
    R(
        "Quantile regression",
        "`quantreg::rq`",
        "`qreg`, `sqreg`, `ivqreg`",
        "`sp.qreg`, `sp.sqreg`, `sp.ivqreg`",
        ["qreg", "sqreg", "ivqreg"],
        "equivalent",
    ),
    R(
        "Bivariate probit",
        "`GJRM::gjrm`",
        "`biprobit`",
        "`sp.biprobit`",
        ["biprobit"],
        "equivalent",
    ),
    R(
        "Endogenous treatment",
        "`sampleSelection`",
        "`etregress`",
        "`sp.etregress`",
        ["etregress"],
        "equivalent",
    ),
    # ---- DiD ------------------------------------------------------------
    R(
        "**DiD: classical 2x2**",
        "`did2s::did2s`",
        "`didregress`",
        "`sp.did_2x2`",
        ["did_2x2"],
        "equivalent",
    ),
    R(
        "**DiD: Callaway--Sant'Anna**",
        "`did::att_gt` + `aggte`",
        "`csdid`",
        "`sp.callaway_santanna` + `sp.aggte`",
        ["callaway_santanna", "aggte"],
        "equivalent",
        "modulo the simple-ATT variance convention",
    ),
    R(
        "**DiD: doubly robust 2x2**",
        "`DRDID::drdid`",
        "`drdid`",
        "`sp.drdid`",
        ["drdid"],
        "equivalent",
    ),
    R(
        "**DiD: Sun--Abraham**",
        "`fixest::sunab`",
        "`eventstudyinteract`",
        "`sp.sun_abraham`",
        ["sun_abraham"],
        "equivalent",
    ),
    R(
        "**DiD: Borusyak imputation**",
        "`didimputation::did_imputation`",
        "`did_imputation`",
        "`sp.did_imputation`, `sp.bjs_pretrend_joint`",
        ["did_imputation", "bjs_pretrend_joint"],
        "equivalent",
    ),
    R(
        "**DiD: Gardner two-stage**",
        "`did2s::did2s`",
        "`did2s`",
        "`sp.gardner_did`",
        ["gardner_did"],
        "equivalent",
        "point estimate machine-level; SE is a documented convention gap",
    ),
    R(
        "**DiD: dCDH DID_M**",
        "`DIDmultiplegt` (0.1.4)",
        "`did_multiplegt_old`",
        "`sp.did_multiplegt`",
        ["did_multiplegt"],
        "equivalent",
    ),
    R(
        "**DiD: dCDH intertemporal**",
        "`DIDmultiplegtDYN`",
        "`did_multiplegt_dyn`",
        "`sp.did_multiplegt_dyn`",
        ["did_multiplegt_dyn"],
        "equivalent",
    ),
    R(
        "**DiD: ETWFE**",
        "`etwfe::etwfe`",
        "`jwdid`",
        "`sp.etwfe`, `sp.wooldridge_did`",
        ["etwfe", "wooldridge_did"],
        "equivalent",
    ),
    R(
        "**DiD: stacked**",
        "hand-written `fixest` stack",
        "hand-built stack + `reghdfe`",
        "`sp.stacked_did`",
        ["stacked_did"],
        "equivalent",
        "no packaged owner in either language; all three sides are independent constructions",
    ),
    R(
        "**DiD: triple differences**",
        "`triplediff::ddd`",
        "--- (no Stata package)",
        "`sp.ddd`, `sp.ddd_heterogeneous`",
        ["ddd", "ddd_heterogeneous"],
        "equivalent",
    ),
    R(
        "**DiD: continuous treatment**",
        "`contdid::cont_did`",
        "--- (no Stata package)",
        "`sp.continuous_did`, `sp.cgs_continuous_did`",
        ["continuous_did", "cgs_continuous_did"],
        "equivalent",
    ),
    R(
        "**DiD: changes-in-changes**",
        "`qte::CiC`",
        "`cic`",
        "`sp.cic`",
        ["cic"],
        "equivalent",
        "documented inverse-CDF tie-break gap on the median and the ATT",
    ),
    R(
        "**DiD: Honest**",
        "`HonestDiD::createSensitivityResults_*`",
        "`honestdid`",
        "`sp.honest_did`",
        ["honest_did"],
        "equivalent",
    ),
    R(
        "**DiD: pretrends power**",
        "`pretrends::pretrends`",
        "`pretrends`",
        "`sp.pretrends_power`, `sp.pretrends_slope_for_power`, `sp.pretrends_test`",
        ["pretrends_power", "pretrends_slope_for_power", "pretrends_test"],
        "equivalent",
    ),
    R(
        "**DiD: functional-form test**",
        "`didFF::didFF`",
        "--- (no Stata package)",
        "`sp.functional_form_test`",
        ["functional_form_test"],
        "equivalent",
    ),
    R(
        "**DiD: Bacon decomposition**",
        "`bacondecomp::bacon`",
        "`bacondecomp`",
        "`sp.bacon_decomposition`",
        ["bacon_decomposition"],
        "equivalent",
    ),
    R(
        "**DiD: local projections**",
        "`lpirfs`-style LP-DiD",
        "`lpdid`",
        "`sp.lp_did`",
        ["lp_did"],
        "equivalent",
    ),
    # ---- RD -------------------------------------------------------------
    R(
        "**RD: bias-corrected robust**",
        "`rdrobust::rdrobust`",
        "`rdrobust`",
        "`sp.rdrobust`",
        ["rdrobust"],
        "equivalent",
    ),
    R(
        "**RD: density manipulation**",
        "`rddensity::rddensity`",
        "`rddensity`",
        "`sp.rddensity`, `sp.rdplotdensity`",
        ["rddensity", "rdplotdensity"],
        "equivalent",
    ),
    R(
        "**RD: bandwidth selection**",
        "`rdrobust::rdbwselect`",
        "`rdbwselect`",
        "`sp.rdbwselect`",
        ["rdbwselect"],
        "equivalent",
    ),
    R(
        "**RD: power / sample size**",
        "`rdpower::rdpower`",
        "`rdpower`, `rdsampsi`",
        "`sp.rdpower`, `sp.rdsampsi`",
        ["rdpower", "rdsampsi"],
        "equivalent",
    ),
    R(
        "**RD: multi-cutoff / multi-score**",
        "`rdmulti::rdmc`, `rdmulti::rdms`",
        "`rdmc`, `rdms`",
        "`sp.rdmc`, `sp.rdms`",
        ["rdmc", "rdms"],
        "equivalent",
    ),
    R(
        "**RD: local randomization**",
        "`rdlocrand::*`",
        "`rdrandinf`, `rdwinselect`",
        "`sp.rdrandinf`, `sp.rdwinselect`, `sp.rdsensitivity`",
        ["rdrandinf", "rdwinselect", "rdsensitivity"],
        "equivalent",
    ),
    R(
        "**RD: heterogeneous effects**",
        "`rdhte::rdhte`",
        "`rdhte`",
        "`sp.rdhte`, `sp.rdbwhte`",
        ["rdhte", "rdbwhte"],
        "equivalent",
    ),
    R(
        "**RD: honest / bias-aware CIs**",
        "`RDHonest::RDHonest`",
        "---",
        "`sp.rd_honest`",
        ["rd_honest"],
        "equivalent",
    ),
    R(
        "**RD: kink design**",
        "---",
        "---",
        "`sp.rkd`, `sp.kink_unified`",
        ["rkd", "kink_unified"],
        "new",
    ),
    # ---- synthetic control ----------------------------------------------
    R(
        "**Synth: classical SCM**",
        "`Synth::synth`",
        "`synth`",
        '`sp.synth(method="classic")`',
        ["synth"],
        "equivalent",
        "T4 disclosure: Basque donor weights are not uniquely identified",
    ),
    R(
        "**Synth: SDID**",
        "`synthdid::synthdid_estimate`",
        "`sdid`",
        '`sp.sdid`, `sp.synth(method="sdid")`',
        ["sdid", "synth"],
        "equivalent",
    ),
    R(
        "**Synth: augmented SCM**",
        "`augsynth::augsynth`",
        "`allsynth` (different convention)",
        "`sp.augsynth`",
        ["augsynth"],
        "equivalent",
    ),
    R(
        "**Synth: generalised SCM**",
        "`gsynth::gsynth`",
        "`fect_stata` (different convention)",
        "`sp.gsynth`",
        ["gsynth"],
        "equivalent",
    ),
    R(
        "**Synth: SCPI inference**",
        "`scpi::scpi`",
        "`scpi`",
        "`sp.scpi`, `sp.scest`, `sp.scdata`",
        ["scpi", "scest", "scdata"],
        "equivalent",
    ),
    R(
        "**Synth: BSTS / CausalImpact**",
        "`CausalImpact::CausalImpact`",
        "---",
        "`sp.causal_impact`",
        ["causal_impact"],
        "equivalent",
    ),
    R(
        "**Synth: matrix completion**",
        "`MCPanel::*`",
        "---",
        "`sp.matrix_completion`, `sp.mc_panel`",
        ["matrix_completion", "mc_panel"],
        "partial",
    ),
    R(
        "**Synth: workflow**",
        "`Synth::synth_runner`",
        "`synth_runner`",
        "`sp.synth_compare`, `sp.synth_recommend`, `sp.synth_sensitivity`, `sp.synth_report`",
        ["synth_compare", "synth_recommend", "synth_sensitivity", "synth_report"],
        "superset",
    ),
    # ---- ML / DML -------------------------------------------------------
    R(
        "**DML: PLR**",
        "`DoubleML::DoubleMLPLR`",
        "`ddml`",
        '`sp.dml(model="plr")`',
        ["dml"],
        "equivalent",
    ),
    R(
        "**DML: PLIV**",
        "`DoubleML::DoubleMLPLIV`",
        "`ddml init iv`",
        '`sp.dml(model="pliv")`',
        ["dml"],
        "equivalent",
    ),
    R(
        "**DML: IRM**",
        "`DoubleML::DoubleMLIRM`",
        "`ddml init interactive`",
        '`sp.dml(model="irm")`',
        ["dml"],
        "equivalent",
    ),
    R(
        "**DML: IIVM**",
        "`DoubleML::DoubleMLIIVM`",
        "`ddml init interactiveiv`",
        '`sp.dml(model="iivm")`',
        ["dml"],
        "equivalent",
    ),
    R(
        "**DML: sensitivity**",
        "`DoubleML` sensitivity",
        "---",
        "`sp.dml_sensitivity`, `sp.dml_diagnostics`",
        ["dml_sensitivity", "dml_diagnostics"],
        "equivalent",
    ),
    R(
        "**Causal forest**",
        "`grf::causal_forest`",
        "`cate` (Stata 19)",
        "`sp.causal_forest`",
        ["causal_forest"],
        "equivalent",
        "T3 combined-Monte-Carlo-error pass rather than a deterministic T2 claim",
    ),
    R(
        "**Policy learning**",
        "`policytree::policy_tree`",
        "---",
        "`sp.policy_tree`, `sp.policy_value`",
        ["policy_tree", "policy_value"],
        "equivalent",
    ),
    R(
        "**Meta-learners**",
        "`causalToolbox::*`, `EconML`",
        "---",
        "`sp.metalearner`, `sp.xlearner`, `sp.compare_metalearners`",
        ["metalearner", "xlearner", "compare_metalearners"],
        "equivalent",
    ),
    R(
        "**TMLE**",
        "`tmle::tmle`",
        "`eltmle` (wraps the same R package)",
        "`sp.tmle`, `sp.ltmle`, `sp.hal_tmle`",
        ["tmle", "ltmle", "hal_tmle"],
        "equivalent",
    ),
    R(
        "**BCF**",
        "`bcf::bcf`",
        "---",
        "`sp.bcf`, `sp.did_bcf`",
        ["bcf", "did_bcf"],
        "equivalent",
    ),
    R(
        "**Conformal causal inference**",
        "`cfcausal::*`",
        "---",
        "`sp.conformal_ite`, `sp.conformal_cate`, `sp.conformal_synth`",
        ["conformal_ite", "conformal_cate", "conformal_synth"],
        "partial",
    ),
    R(
        "**Rank-weighted ATE / RATE**",
        "`grf::rank_average_treatment_effect`",
        "---",
        "`sp.rate`",
        ["rate"],
        "equivalent",
    ),
    R(
        "**Neural causal**",
        "user `keras` code",
        "---",
        "`sp.tarnet`, `sp.cfrnet`, `sp.dragonnet`, `sp.deepiv`",
        ["tarnet", "cfrnet", "dragonnet", "deepiv"],
        "new",
    ),
    R(
        "**Causal discovery**",
        "`pcalg::pc`, `bnlearn`, `pcalg::ges`",
        "---",
        "`sp.pc_algorithm`, `sp.lingam`, `sp.notears`, `sp.ges`, `sp.fci`",
        ["pc_algorithm", "lingam", "notears", "ges", "fci"],
        "partial",
    ),
    # ---- matching / weighting -------------------------------------------
    R(
        "**Matching: PSM 1:1**",
        '`MatchIt::matchit(method="nearest")`',
        "`psmatch2`, `teffects psmatch`",
        "`sp.psm`, `sp.psmatch2`",
        ["psm", "psmatch2"],
        "equivalent",
    ),
    R(
        "**Matching: optimal / cardinality**",
        '`MatchIt::matchit(method="optimal")`',
        "`cem` (different method)",
        "`sp.optimal_match`, `sp.cardinality_match`",
        ["optimal_match", "cardinality_match"],
        "partial",
    ),
    R(
        "**Matching: genetic**",
        "`Matching::GenMatch`",
        "---",
        "`sp.genmatch`",
        ["genmatch"],
        "equivalent",
    ),
    R(
        "**Matching: CBPS**",
        "`CBPS::CBPS`",
        "`cbps` (user-contrib)",
        "`sp.cbps`",
        ["cbps"],
        "equivalent",
    ),
    R(
        "**Weighting: entropy balancing**",
        "`ebal::ebalance`",
        "`ebalance` (user-contrib)",
        "`sp.ebalance`",
        ["ebalance"],
        "equivalent",
    ),
    R(
        "**Weighting: stable balancing**",
        "`sbw::sbw`",
        "---",
        "`sp.sbw`",
        ["sbw"],
        "equivalent",
    ),
    R(
        "**Weighting: overlap**",
        "`PSweight::*`",
        "---",
        "`sp.overlap_weights`, `sp.trimming`",
        ["overlap_weights", "trimming"],
        "equivalent",
    ),
    R(
        "**IPW**",
        "`WeightIt::weightit`",
        "`teffects ipw`",
        "`sp.ipw`",
        ["ipw"],
        "equivalent",
    ),
    R(
        "**AIPW / doubly robust**",
        "`AIPW::AIPW`",
        "`teffects aipw`, `teffects ipwra`",
        "`sp.aipw`, `sp.doubly_robust`",
        ["aipw", "doubly_robust"],
        "equivalent",
    ),
    R(
        "**Balance diagnostics**",
        "`cobalt::bal.tab`",
        "`pstest`",
        "`sp.balance_diagnostics`, `sp.love_plot`, `sp.ps_balance`",
        ["balance_diagnostics", "love_plot", "ps_balance"],
        "equivalent",
    ),
    # ---- decomposition --------------------------------------------------
    R(
        "**Decomposition: Oaxaca**",
        "`oaxaca::oaxaca`, `ddecompose::oaxaca_blinder_decomposition`",
        "`oaxaca`",
        '`sp.decompose(method="oaxaca")`, `sp.oaxaca`',
        ["decompose", "oaxaca"],
        "superset",
        "five reference conventions",
    ),
    R(
        "**Decomposition: RIF**",
        "`dineq::rif`, `rifreg`",
        "`rifhdreg`",
        "`sp.rifreg`, `sp.rif_decomposition`",
        ["rifreg", "rif_decomposition"],
        "equivalent",
    ),
    R(
        "**Decomposition: DFL**",
        "`ddecompose`",
        "`dfl` (user-contrib)",
        "`sp.dfl_decompose`",
        ["dfl_decompose"],
        "equivalent",
    ),
    R(
        "**Decomposition: Gelbach**",
        "---",
        "`b1x2`",
        "`sp.gelbach`",
        ["gelbach"],
        "equivalent",
    ),
    R(
        "**Decomposition: inequality indices**",
        "`ineq::Theil`, `IC2`",
        "`ineqdec0`",
        "`sp.inequality_index`, `sp.shapley_inequality`",
        ["inequality_index", "shapley_inequality"],
        "equivalent",
    ),
    R(
        "**Decomposition: Machado--Mata**",
        "`Counterfactual::*`",
        "`cdeco`",
        "`sp.machado_mata`, `sp.melly_decompose`",
        ["machado_mata", "melly_decompose"],
        "equivalent",
    ),
    R(
        "**Decomposition: Fairlie**",
        "`oaxaca` nonlinear",
        "`fairlie`",
        "`sp.fairlie`, `sp.yun_nonlinear`",
        ["fairlie", "yun_nonlinear"],
        "equivalent",
    ),
    R(
        "**Decomposition: gap closing**",
        "`gapclosing::gapclosing`",
        "---",
        "`sp.gap_closing`",
        ["gap_closing"],
        "equivalent",
    ),
    R(
        "**Decomposition: Das Gupta**",
        "---",
        "---",
        "`sp.das_gupta`",
        ["das_gupta"],
        "new",
    ),
    # ---- frontier / multilevel ------------------------------------------
    R(
        "**Frontier: cross-section**",
        "`frontier::sfa`, `sfaR::sfacross`",
        "`frontier`",
        "`sp.frontier`",
        ["frontier"],
        "equivalent",
    ),
    R(
        "**Frontier: panel**",
        "`frontier::sfa` (panel)",
        "`xtfrontier`",
        "`sp.xtfrontier`",
        ["xtfrontier"],
        "equivalent",
    ),
    R(
        "**Frontier: latent class**",
        "`sfaR::sfalcmcross`",
        "---",
        "`sp.lcsf`",
        ["lcsf"],
        "equivalent",
    ),
    R("**Frontier: zero-inflated**", "---", "---", "`sp.zisf`", ["zisf"], "new"),
    R(
        "**Frontier: Malmquist TFP**",
        "`Benchmarking::malmquist`",
        "---",
        "`sp.malmquist`",
        ["malmquist"],
        "equivalent",
    ),
    R(
        "**Mixed: LMM**",
        "`lme4::lmer`, `nlme::lme`",
        "`mixed`",
        "`sp.mixed`",
        ["mixed"],
        "equivalent",
    ),
    R(
        "**Mixed: GLMM**",
        "`lme4::glmer`",
        "`melogit`, `mepoisson`, `meglm`",
        "`sp.melogit`, `sp.mepoisson`, `sp.meglm`, `sp.megamma`, `sp.menbreg`, `sp.meologit`",
        ["melogit", "mepoisson", "meglm", "megamma", "menbreg", "meologit"],
        "equivalent",
        "AGHQ quadrature",
    ),
    R(
        "**Mixed: ICC**",
        "`performance::icc`",
        "`estat icc`",
        "`sp.icc`",
        ["icc"],
        "equivalent",
    ),
    R(
        "**Mixed: LR test**",
        "`lme4::anova`",
        "`lrtest`",
        "`sp.lrtest`",
        ["lrtest"],
        "superset",
        "adds the Self--Liang boundary correction",
    ),
    # ---- spatial / time series ------------------------------------------
    R(
        "**Spatial: diagnostics**",
        "`spdep::moran.test`, `spdep::lm.LMtests`",
        "`spatgsa`, `estat moran`",
        "`sp.moran`, `sp.moran_local`, `sp.geary`, `sp.lm_tests`",
        ["moran", "moran_local", "geary", "lm_tests"],
        "equivalent",
    ),
    R(
        "**Spatial: ML (SAR/SEM/SAC)**",
        "`spatialreg::lagsarlm`, `errorsarlm`, `sacsarlm`",
        "`spregress` (different ML convention)",
        "`sp.sar`, `sp.sem`, `sp.sac`",
        ["sar", "sem", "sac"],
        "equivalent",
    ),
    R(
        "**Spatial: GMM**",
        "`spatialreg::stsls`, `GMerrorsar`",
        "`spregress, gs2sls` (different moment convention)",
        "`sp.sar_gmm`, `sp.sem_gmm`, `sp.sarar_gmm`",
        ["sar_gmm", "sem_gmm", "sarar_gmm"],
        "equivalent",
    ),
    R(
        "**Spatial: panel / DiD**",
        "`splm::spml`",
        "`xsmle` (user-contrib)",
        "`sp.spatial_panel`, `sp.spatial_did`, `sp.spatial_iv`",
        ["spatial_panel", "spatial_did", "spatial_iv"],
        "partial",
    ),
    R(
        "**Spatial: GWR**",
        "`GWmodel::gwr.*`, `spgwr::gwr`",
        "---",
        "`sp.gwr`, `sp.mgwr`",
        ["gwr", "mgwr"],
        "equivalent",
    ),
    R(
        "**Spatial: Conley SE**",
        "`conleyreg::conleyreg`",
        "`acreg`, `ols_spatial_HAC`",
        "`sp.conley`",
        ["conley"],
        "equivalent",
    ),
    R(
        "**Time series: ARIMA**",
        "`stats::arima`",
        "`arima`",
        "`sp.arima`",
        ["arima"],
        "equivalent",
    ),
    R(
        "**Time series: VAR**",
        "`vars::VAR`",
        "`var`",
        "`sp.var`, `sp.irf`",
        ["var", "irf"],
        "equivalent",
    ),
    R(
        "**Time series: BVAR**",
        "`BVAR::bvar`",
        "`bayes: var`",
        "`sp.bvar`",
        ["bvar"],
        "partial",
    ),
    R(
        "**Time series: GARCH**",
        "`rugarch::ugarchfit`",
        "`arch`",
        "`sp.garch`",
        ["garch"],
        "equivalent",
    ),
    R(
        "**Time series: cointegration**",
        "`urca::ca.jo`, `urca::ca.po`",
        "`vecrank`, `egranger`",
        "`sp.johansen`, `sp.engle_granger`",
        ["johansen", "engle_granger"],
        "equivalent",
    ),
    R(
        "**Time series: local projections**",
        "`lpirfs::lp_lin`",
        "`lpirf`",
        "`sp.local_projections`",
        ["local_projections"],
        "equivalent",
    ),
    R(
        "**Time series: structural break**",
        "`strucchange::breakpoints`",
        "`estat sbsingle`",
        "`sp.structural_break`, `sp.cusum_test`",
        ["structural_break", "cusum_test"],
        "equivalent",
    ),
    R(
        "**Time series: causal impact / ITS**",
        "`CausalImpact`",
        "`itsa` (user-contrib)",
        "`sp.its`",
        ["its"],
        "equivalent",
    ),
    # ---- survival / epi -------------------------------------------------
    R(
        "**Survival: Cox**",
        "`survival::coxph`",
        "`stcox`",
        "`sp.cox`, `sp.cox_frailty`",
        ["cox", "cox_frailty"],
        "equivalent",
    ),
    R(
        "**Survival: AFT**",
        "`survival::survreg`",
        "`streg`",
        "`sp.aft`, `sp.survreg`",
        ["aft", "survreg"],
        "equivalent",
    ),
    R(
        "**Survival: Kaplan--Meier**",
        "`survival::survfit`",
        "`sts graph`",
        "`sp.kaplan_meier`, `sp.logrank_test`",
        ["kaplan_meier", "logrank_test"],
        "equivalent",
    ),
    R(
        "**Survival: competing risks**",
        "`cmprsk::cuminc`, `crr`",
        "`stcrreg`",
        "`sp.cuminc`, `sp.finegray`",
        ["cuminc", "finegray"],
        "equivalent",
    ),
    R(
        "**Epi: Mendelian randomisation**",
        "`MendelianRandomization::*`",
        "`mrrobust`",
        "`sp.mr`, `sp.mendelian`",
        ["mr"],
        "equivalent",
    ),
    R(
        "**Epi: Bradford Hill / E-value**",
        "`EValue::evalue`",
        "---",
        "`sp.evalue`, `sp.evalue_rr`, `sp.bradford_hill`",
        ["evalue", "evalue_rr", "bradford_hill"],
        "equivalent",
    ),
    # ---- design / inference ---------------------------------------------
    R(
        "**Survey design**",
        "`survey::svydesign`, `svyglm`",
        "`svyset`, `svy: regress`",
        "`sp.svydesign`, `sp.svyglm`, `sp.svymean`, `sp.svytotal`",
        ["svydesign", "svyglm", "svymean", "svytotal"],
        "equivalent",
    ),
    R(
        "**Multiple hypothesis testing**",
        "`stats::p.adjust`, `multcomp`",
        "`wyoung`, `rwolf`",
        "`sp.adjust_pvalues`, `sp.romano_wolf`, `sp.benjamini_hochberg`, `sp.holm`",
        ["adjust_pvalues", "romano_wolf", "benjamini_hochberg", "holm"],
        "equivalent",
    ),
    R(
        "**Power analysis**",
        "`pwr::*`",
        "`power`",
        "`sp.rdpower`, `sp.synth_power`, `sp.pretrends_power`",
        ["rdpower", "synth_power", "pretrends_power"],
        "equivalent",
    ),
    R(
        "**Randomization inference**",
        "`ri2::conduct_ri`",
        "`ritest`",
        "`sp.ri_test`",
        ["ri_test"],
        "equivalent",
    ),
    R(
        "**Partial identification / bounds**",
        "`boundsapply`-style",
        "`leebounds`",
        "`sp.lee_bounds`, `sp.manski_bounds`, `sp.horowitz_manski`",
        ["lee_bounds", "manski_bounds", "horowitz_manski"],
        "equivalent",
    ),
    R(
        "**Mediation**",
        "`mediation::mediate`",
        "`medeff`, `sem`",
        "`sp.mediate`, `sp.mediation`, `sp.mediation_decompose`",
        ["mediate", "mediation", "mediation_decompose"],
        "equivalent",
    ),
    R(
        "**Interference / spillovers**",
        "`interference`-style",
        "---",
        "`sp.interference`, `sp.spillover`, `sp.spillover_did`",
        ["interference", "spillover", "spillover_did"],
        "partial",
    ),
    R(
        "**Bartik / shift-share**",
        "`bartik.weight::*`",
        "`bartik_weight`",
        "`sp.bartik`",
        ["bartik"],
        "equivalent",
    ),
    R(
        "**Bunching**",
        "`bunching::*`",
        "`bunchit` (user-contrib)",
        "`sp.bunching`, `sp.general_bunching`, `sp.notch`",
        ["bunching", "general_bunching", "notch"],
        "equivalent",
    ),
    R(
        "**Meta-analysis**",
        "`metafor::rma`",
        "`meta`",
        "`sp.meta_analysis`",
        ["meta_analysis"],
        "equivalent",
    ),
    # ---- sensitivity ----------------------------------------------------
    R(
        "**Sensitivity: Oster**",
        "`robomit::*`",
        "`psacalc`",
        "`sp.oster_bounds`, `sp.oster_delta`",
        ["oster_bounds", "oster_delta"],
        "equivalent",
    ),
    R(
        "**Sensitivity: sensemakr**",
        "`sensemakr::sensemakr`",
        "`sensemakr`",
        "`sp.sensemakr`",
        ["sensemakr"],
        "equivalent",
    ),
    R(
        "**Sensitivity: Rosenbaum bounds**",
        "`rbounds::*`",
        "`rbounds`",
        "`sp.rosenbaum_bounds`, `sp.rosenbaum_gamma`",
        ["rosenbaum_bounds", "rosenbaum_gamma"],
        "equivalent",
    ),
    R(
        "**Sensitivity: specification curve**",
        "`specr::specr`",
        "---",
        "`sp.spec_curve`",
        ["spec_curve"],
        "equivalent",
    ),
    R(
        "**Sensitivity: breakdown frontier**",
        "`breakdown`-style",
        "---",
        "`sp.breakdown_frontier`, `sp.breakdown_m`",
        ["breakdown_frontier", "breakdown_m"],
        "equivalent",
    ),
    # ---- output / agent surface -----------------------------------------
    R(
        "**Output: regression tables**",
        "`modelsummary::msummary`, `stargazer`, `texreg`",
        "`esttab`, `outreg2`",
        "`sp.modelsummary`, `sp.etable`, `sp.regtable`",
        ["modelsummary", "etable", "regtable"],
        "superset",
    ),
    R(
        "**Output: marginal effects**",
        "`marginaleffects::*`",
        "`margins`",
        "`sp.margins`, `sp.margins_at`, `sp.marginsplot`",
        ["margins", "margins_at", "marginsplot"],
        "equivalent",
    ),
    R(
        "**Agent surface**",
        "---",
        "---",
        "`sp.list_functions`, `sp.describe_function`, `sp.function_schema`, `sp.recommend`",
        ["list_functions", "describe_function", "function_schema", "recommend"],
        "new",
    ),
    R(
        "**Workflow / paper assistant**",
        "---",
        "---",
        "`sp.paper`, `sp.causal_question`, `sp.methods_appendix`",
        ["paper", "causal_question", "methods_appendix"],
        "new",
    ),
]


# --------------------------------------------------------------------------
# Derived evidence
# --------------------------------------------------------------------------
def load_registry() -> set[str]:
    sys.path.insert(0, str(ROOT / "src"))
    import statspai  # noqa: PLC0415

    return set(statspai.list_functions())


def load_index() -> dict[str, dict]:
    payload = json.loads(PARITY_INDEX.read_text(encoding="utf-8"))
    return {r["function"]: r for r in payload["records"]}


TIER_LABEL = {
    "bit-exact": "bit-exact",
    "aligned": "aligned",
    "analytical-only": "analytical",
    "external-replication": "published",
}
TIER_RANK = {
    "bit-exact": 0,
    "aligned": 1,
    "external-replication": 2,
    "analytical-only": 3,
}


def build_test_fallback() -> dict[str, str]:
    """Map function name -> a test file that exercises it.

    The parity index is generated from graded artifacts only, and its
    analytical/external tiers are populated selectively, so a function can be
    genuinely tested and still be absent from it. Reporting such a row as "no
    numerical evidence" would understate the suite; reporting it as a graded
    tier would overstate it. This fallback is therefore rendered as an
    explicitly ungraded state: it records that a test names the function,
    which is weaker than a tolerance-checked artifact and is labelled as such.
    """
    hits: dict[str, str] = {}
    for base in ("tests/reference_parity", "tests/external_parity", "tests"):
        d = ROOT / base
        if not d.exists():
            continue
        for f in sorted(d.glob("test_*.py")):
            try:
                text = f.read_text(encoding="utf-8")
            except OSError:
                continue
            for name in FUNCTION_NAMES:
                if name in hits:
                    continue
                if f"sp.{name}(" in text or f"statspai.{name}(" in text:
                    hits[name] = str(f.relative_to(ROOT))
    return hits


def evidence_for(functions, registry, index, fallback):
    """Return (evidence_cell, missing_names).

    The strongest tier across the row's entry points wins, because the row
    claims that the group replaces the reference; the test path shown is the
    one attached to that strongest record.
    """
    missing = [f for f in functions if f not in registry]
    records = [index[f] for f in functions if f in index]
    if not records:
        for f in functions:
            if f in fallback:
                return (f"test-covered, not tier-graded — `{fallback[f]}`", missing)
        return ("no numerical evidence registered", missing)
    best = min(records, key=lambda r: TIER_RANK.get(r["status"], 9))
    label = TIER_LABEL.get(best["status"], best["status"])
    ref = best.get("reference") or ""
    test = (best.get("test") or [""])[0]
    parts = [f"**{label}**"]
    if ref:
        parts.append(f"vs `{ref}`")
    if test:
        parts.append(f"`{test}`")
    return (" — ".join(parts), missing)


def render() -> tuple[str, list[str]]:
    registry = load_registry()
    index = load_index()
    global FUNCTION_NAMES
    FUNCTION_NAMES = {f for row in ROWS for f in row["functions"]}
    fallback = build_test_fallback()
    py_modules = {p.name[: -len("_py.json")] for p in R_RESULTS.glob("*_py.json")}
    stata_modules = {
        p.name[: -len("_Stata.json")] for p in STATA_RESULTS.glob("*_Stata.json")
    }

    problems: list[str] = []
    body: list[str] = []
    counts = {"equivalent": 0, "subset": 0, "superset": 0, "partial": 0, "new": 0}
    tier_counts: dict[str, int] = {}

    for row in ROWS:
        cell, missing = evidence_for(row["functions"], registry, index, fallback)
        if missing:
            problems.append(
                f"{row['domain']}: not in registry: {', '.join('sp.' + m for m in missing)}"
            )
            cell = f"**NAME NOT IN REGISTRY**: {', '.join('sp.' + m for m in missing)}"
        counts[row["relationship"]] = counts.get(row["relationship"], 0) + 1
        head = cell.split(" — ")[0].strip("*")
        tier_counts[head] = tier_counts.get(head, 0) + 1
        note = f" {row['note']}" if row["note"] else ""
        body.append(
            f"| {row['domain']} | {row['r']} | {row['stata']} | {row['call']} | "
            f"{row['relationship']} | {cell}{note} |"
        )

    tier_line = "; ".join(
        f"{v} {k}" for k, v in sorted(tier_counts.items(), key=lambda kv: -kv[1])
    )
    rel_line = "; ".join(f"{v} {k}" for k, v in counts.items() if v)

    header = f"""# StatsPAI to R / Stata replacement table

**Generated file — do not edit by hand.** Regenerate with:

```bash
cd Paper-JSS
python replication/scripts/build_replacement_table.py
python replication/scripts/build_replacement_table.py --check   # drift check
```

This is the audit-grade detail behind the coverage table in the
manuscript's architecture section. Each row states which R package or Stata
command a StatsPAI entry point is meant to replace, what kind of
relationship that is, and — this is the part no human hand-maintains — what
committed numerical evidence backs it.

The Evidence column is derived, never asserted. Every `sp.` name in the
table is checked against the live registry (`statspai.list_functions()`),
and the tier and test path come from `src/statspai/_parity_index.json`,
which is itself generated from the committed parity artifacts by
`scripts/build_parity_index.py`. A row naming a function that does not
exist renders as a hard failure and makes the generator exit non-zero, so
the table cannot drift back into advertising `sp.` entry points a reader
cannot call.

## Reading the columns

**Relationship** is editorial judgement about scope:

- **equivalent** — same estimand and same default options as the reference.
- **subset** — a documented subset of the reference's option surface.
- **superset** — all of the reference's options plus additional methodology.
- **partial** — implemented, but the cross-language comparison is not
  like-for-like (different estimand, convention, or no packaged reference).
- **new** — no canonical reference implementation exists to compare against.

**Evidence** is the strongest committed numerical artifact across the row's
entry points:

- **bit-exact** — matches a named R or Stata reference to the machine
  tolerance tier (rel ≤ 1e-6) on identical CSV bytes.
- **aligned** — matches a named reference inside a documented looser
  tolerance (iterative, cross-fit, or methodological tier).
- **published** — reproduces published paper numbers.
- **analytical** — recovers a known population parameter or closed-form
  identity on a deterministic DGP; no cross-package reference exists.
- **test-covered, not tier-graded** — a committed test exercises the
  function, but the parity index carries no graded artifact for it. This is
  weaker than a tolerance-checked comparison and is labelled separately so
  it cannot be read as one.
- **no numerical evidence registered** — the function is registered and
  callable but carries no qualifying numerical artifact and no test names
  it directly. This is stated rather than hidden; it is the honest reading
  of the API-stable tier.

A row whose evidence is *analytical* is not a weaker version of a
cross-language check. For estimators with no reference implementation
anywhere — `sp.das_gupta`, `sp.zisf`, the neural-causal family — recovery of
a known truth on a controlled DGP is the only evidence that can exist.

## Summary

- Rows: {len(ROWS)}
- Relationship: {rel_line}
- Evidence tier: {tier_line}

## Table

| Domain | R package / function | Stata command | StatsPAI | Relationship | Evidence |
| --- | --- | --- | --- | --- | --- |
"""
    footer = """

## Scope boundaries

Three deliberate exclusions, so the table's silence is not read as an
oversight:

1. **The Bayesian causal sub-package is not listed.** Frequentist parity
   against a point estimate is not the right yardstick for a posterior; the
   Bayesian estimators are validated through convergence diagnostics
   (`rhat`, `ess_bulk`, `ess_tail`, divergences) and recovery on simulated
   posteriors instead. Adding a "replacement" row for them would imply a
   comparison the evidence does not support.

2. **Plotting and reporting helpers are listed only where a canonical
   reference command exists.** `sp.love_plot` maps to `cobalt::bal.tab`;
   most figure helpers map to nothing in particular and are omitted rather
   than padded in.

3. **The table names entry points, not every alias.** Dispatchers such as
   `sp.synth(method=...)`, `sp.decompose(method=...)` and `sp.dml(model=...)`
   appear once per method rather than once per alias, matching how the
   registry documents them.

## Source

This file is generated by
[`../replication/scripts/build_replacement_table.py`](../replication/scripts/build_replacement_table.py).
Editorial changes — a new row, a corrected relationship, a different
reference package — belong in that script's `ROWS` table. Evidence changes
follow automatically from the parity artifacts and never need a hand edit.
"""
    return header + "\n".join(body) + footer, problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--check", action="store_true", help="fail if the committed file is stale"
    )
    args = ap.parse_args()

    text, problems = render()
    for p in problems:
        print(f"FAIL -- {p}", file=sys.stderr)

    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print(f"FAIL -- {OUT} is stale; re-run without --check", file=sys.stderr)
            return 1
        if problems:
            return 1
        print(f"OK -- {OUT.relative_to(ROOT)} is in sync ({len(ROWS)} rows)")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"OK -- wrote {OUT.relative_to(ROOT)} ({len(ROWS)} rows)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

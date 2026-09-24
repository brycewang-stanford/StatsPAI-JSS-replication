#!/usr/bin/env Rscript
# ---------------------------------------------------------------------------
# Round-2 R reference for tests/reference_parity/test_r2_teffects_parity.py
#
# Reads the round-1 CSVs written by _fixtures/_generate_teffects_data.py
# (teffects_cs.csv, teffects_wide.csv, teffects_long.csv) and writes
# _fixtures/r2_teffects_R.json (17 significant digits) with package versions.
#
#   Rscript tests/reference_parity/_generate_r2_teffects_R.R
#
# Requires R 4.5 and CRAN: ltmle, SuperLearner, tmle, grf, policytree, jsonlite.
#
# Conventions pinned here (each decides a number below)
# -----------------------------------------------------
# * ICE g-formula point estimate: ltmle::ltmle(gcomp = TRUE) with
#   SL.library = list(Q = "SL.lm", g = "SL.glm"), default Qform (all
#   parents), stratify = FALSE (pooled over treatment). ltmle maps a
#   continuous Y to [0, 1] by (Y - min) / range; a linear fit is equivariant
#   to that map. With a single learner the SuperLearner NNLS weight is 1, so
#   the prediction is lm()'s. SL.lm clips predictions to [0, 1] under the
#   binomial family ltmle passes; every block records the range of the
#   intervened hand-lm predictions on ltmle's scale (q_range_scaled), so the
#   test pins only blocks where the clip is inert and shows that the others
#   (a linear-probability ICE on the binary Yb) move because of it. ltmle
#   sets every earlier A node to the regime when predicting (SetA); sp
#   keeps them observed. With OLS on nested histories the two
#   are algebraically identical (the difference is linear in the next
#   stage's regressors), which the multi-period regimes below exercise.
# * tmle ATT (tmle 2.1.1): tmle(Q.SL.library = "SL.glm", g.SL.library =
#   "SL.glm", gbound = 0.025, cvQinit = FALSE), exactly as round 1. The ATT
#   is tmle:::oneStepATT on the rows with g1W >= min(g1W | A = 1), with g
#   re-calibrated on those rows (intercept-only offset glm when they keep
#   >= 90% of the controls), g bounded below at 0.025 (gbound.ATT =
#   c(0.025, 0.975), of which oneStepATT uses only min()), initial Q (not
#   the ATE-targeted Q) on the [0, 1] scale, depsilon = 0.001, loss-based
#   stopping. The block re-runs that pipeline explicitly and exports every
#   input so the test can port oneStepATT and see the mechanism.
# * policy value: grf 2.6.1 causal_forest(seed = 7, num.trees = 500),
#   get_scores() (AIPW scores, the gain Gamma_1 - Gamma_0) and
#   average_treatment_effect(subset = pi == 1) (AIPW, target.sample = "all":
#   a plain mean of the subset's scores). policytree::double_robust_scores
#   gives the n x 2 reward matrix [Gamma_0, Gamma_1].
# ---------------------------------------------------------------------------
suppressPackageStartupMessages({
  library(ltmle); library(SuperLearner); library(tmle); library(grf)
  library(policytree); library(jsonlite)
})
.a <- commandArgs(trailingOnly = FALSE)
.f <- sub("^--file=", "", .a[grep("^--file=", .a)])
HERE <- if (length(.f)) dirname(normalizePath(.f[1])) else "."
FIX <- file.path(HERE, "_fixtures")

cs <- read.csv(file.path(FIX, "teffects_cs.csv"))
wide <- read.csv(file.path(FIX, "teffects_wide.csv"))
long <- read.csv(file.path(FIX, "teffects_long.csv"))
out <- list()

# ---- 1. ICE g-formula: ltmle(gcomp = TRUE) with a linear Q learner ---------------
# Hand ICE with lm(): returns psi and the range of the intervened stage
# predictions on ltmle's [0, 1] scale (where SL.lm's clip would act).
hand_ice <- function(d, Anodes, Lsets, Y, abar) {
  lo <- min(d[[Y]]); rg <- diff(range(d[[Y]]))
  if (all(d[[Y]] %in% c(0, 1))) { lo <- 0; rg <- 1 }
  q <- d[[Y]]; rngs <- c()
  for (t in rev(seq_along(Anodes))) {
    hist <- unlist(lapply(seq_len(t), function(s) c(Lsets[[s]], Anodes[s])))
    X <- cbind(1, as.matrix(d[, hist]))
    b <- qr.coef(qr(X), q)
    Xs <- X; Xs[, 1 + match(Anodes[t], hist)] <- abar[t]
    q <- drop(Xs %*% b)
    rngs <- c(rngs, range(q))
  }
  list(psi = mean(q), q_range_scaled = (range(rngs) - lo) / rg)
}
lt_ice <- function(d, Anodes, Lnodes, Y, abar) {
  r <- suppressWarnings(suppressMessages(
    ltmle(d, Anodes = Anodes, Lnodes = Lnodes, Ynodes = Y, abar = abar,
          gcomp = TRUE, SL.library = list(Q = "SL.lm", g = "SL.glm"),
          estimate.time = FALSE)))
  unname(r$estimates["gcomp"])
}
wd <- wide[, c("v", "L0", "A0", "L1", "A1", "Y")]
wdb <- wide[, c("v", "L0", "A0", "L1", "A1", "Yb")]
ice_blocks <- list()
for (ab in list(c(1, 1), c(0, 0), c(1, 0))) {
  for (yy in c("Y", "Yb")) {
    dd <- if (yy == "Y") wd else wdb
    h <- hand_ice(dd, c("A0", "A1"), list(c("v", "L0"), "L1"), yy, ab)
    ice_blocks[[length(ice_blocks) + 1]] <- list(
      data = "wide", outcome = yy, abar = ab,
      psi_ltmle = lt_ice(dd, c("A0", "A1"), c("L0", "L1"), yy, ab),
      psi_hand_lm = h$psi, q_range_scaled = h$q_range_scaled)
  }
}
# Four periods from teffects_long (l_t measured before a_t; y constant within id).
lw <- reshape(long[, c("id", "t", "v", "l", "a", "y")], idvar = c("id", "v", "y"),
              timevar = "t", direction = "wide", sep = "")
lw <- lw[order(lw$id), c("v", "l0", "a0", "l1", "a1", "l2", "a2", "l3", "a3", "y")]
An <- c("a0", "a1", "a2", "a3")
Ls <- list(c("v", "l0"), "l1", "l2", "l3")
for (ab in list(c(1, 1, 1, 1), c(0, 0, 0, 0), c(1, 0, 1, 0))) {
  h <- hand_ice(lw, An, Ls, "y", ab)
  ice_blocks[[length(ice_blocks) + 1]] <- list(
    data = "long_to_wide", outcome = "y", abar = ab,
    psi_ltmle = lt_ice(lw, An, c("l0", "l1", "l2", "l3"), "y", ab),
    psi_hand_lm = h$psi, q_range_scaled = h$q_range_scaled)
}
out$ice <- ice_blocks

# ---- 2. tmle::tmle ATT, and the same pipeline re-run step by step -----------------
W <- cs[, c("x1", "x2", "x3")]
att_block <- function(Y, family) {
  set.seed(1)
  f <- tmle(Y = Y, A = cs$d, W = W, family = family, Q.SL.library = "SL.glm",
            g.SL.library = "SL.glm", gbound = 0.025, cvQinit = FALSE)
  A <- cs$d; n <- length(A)
  # stage 1 exactly as tmle:::.initStage1 (maptoYstar = TRUE for both families)
  if (family == "binomial") {
    ab <- c(0, 1); Ystar <- Y; Qb <- c(0.9995, 5e-4)
  } else {
    qb <- range(Y); qb <- qb + 0.01 * c(-abs(qb[1]), abs(qb[2]))
    Ystar <- pmin(pmax(Y, qb[1]), qb[2]); ab <- range(Ystar)
    Ystar <- (Ystar - ab[1]) / diff(ab); Qb <- c(0.9995, 5e-4)
  }
  # f$Qinit$Q is the bounded initial Q mapped back to the Y scale
  # (plogis(Q$Q) * diff(ab) + ab[1]); oneStepATT receives plogis(Q$Q).
  Q01 <- (f$Qinit$Q - ab[1]) / diff(ab)
  QAW <- ifelse(A == 1, Q01[, "Q1W"], Q01[, "Q0W"])
  Q.ATT <- cbind(QAW = QAW, Q0W = Q01[, "Q0W"], Q1W = Q01[, "Q1W"])
  g1W <- f$g$g1W
  rows <- which(g1W >= min(g1W[A == 1]))
  recal <- sum(1 - A[rows]) >= 0.9 * sum(1 - A)
  if (recal) {
    m <- glm(A[rows] ~ 1 + offset(qlogis(g1W[rows])), family = "binomial")
    g.ATT <- plogis(coef(m) + qlogis(g1W))
  } else stop("pipeline branch not covered: ATT rows drop > 10% of controls")
  pD <- cbind(Z0A0 = rep(1, length(rows)), Z0A1 = rep(1, length(rows)))
  res <- tmle:::oneStepATT(Y = Ystar[rows], A = A[rows], Delta = rep(1, length(rows)),
                           Q = Q.ATT[rows, ], g1W = g.ATT[rows], pDelta1 = pD,
                           depsilon = 0.001, max_iter = 2000,
                           gbounds = f$g$bound.ATT, Qbounds = Qb,
                           obsWeights = rep(1, length(rows)))
  list(att = f$estimates$ATT$psi, att_se = sqrt(f$estimates$ATT$var.psi),
       att_rerun = res$psi * diff(ab), att_rerun_var = var(res$IC) * diff(ab)^2 / length(rows),
       ab = ab, ystar = Ystar, q0w_init = Q.ATT[, "Q0W"], q1w_init = Q.ATT[, "Q1W"],
       g1w = g1W, g_att = g.ATT, att_rows = rows, recalibrated = recal,
       gbound_att = f$g$bound.ATT, qbounds = Qb, depsilon = 0.001, max_iter = 2000)
}
out$tmle_att_gaussian <- att_block(cs$y, "gaussian")
out$tmle_att_binary <- att_block(cs$yb, "binomial")

# ---- 3. policy value: grf AIPW scores and the subset ATE --------------------------
X <- as.matrix(cs[, c("x1", "x2", "x3")])
cf <- causal_forest(X, cs$y, cs$d, seed = 7, num.trees = 500)
gam <- get_scores(cf)
G <- double_robust_scores(cf)
pi_rule <- as.integer(cs$x1 > 0)
ate_sub <- average_treatment_effect(cf, subset = pi_rule == 1)
out$policy_value <- list(
  gamma = unname(gam), Gamma0 = unname(G[, 1]), Gamma1 = unname(G[, 2]),
  policy = pi_rule, ate_subset = unname(ate_sub["estimate"]),
  ate_subset_se = unname(ate_sub["std.err"]), share_treated = mean(pi_rule))

out$versions <- list(
  R = R.version.string,
  ltmle = as.character(packageVersion("ltmle")),
  SuperLearner = as.character(packageVersion("SuperLearner")),
  tmle = as.character(packageVersion("tmle")),
  grf = as.character(packageVersion("grf")),
  policytree = as.character(packageVersion("policytree")))

writeLines(toJSON(out, auto_unbox = TRUE, digits = I(17), pretty = FALSE),
           file.path(FIX, "r2_teffects_R.json"))
cat("wrote", file.path(FIX, "r2_teffects_R.json"), "\n")

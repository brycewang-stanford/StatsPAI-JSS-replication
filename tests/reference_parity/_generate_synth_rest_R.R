#!/usr/bin/env Rscript
# Frozen R references for tests/reference_parity/test_synth_rest_R_parity.py
# (phase-3 cross-language campaign, round 2, family "synth_rest").
#
#   SCM sensitivity tools (sp.synth_loo / synth_time_placebo /
#   synth_donor_sensitivity / synth_rmspe_filter / synth_sensitivity)
#       vs Synth::synth (1.1.10) per fit + SCtools::mspe.test (0.3.3.1).
#
#       StatsPAI's SCM core, with no covariates, matches every pre-period
#       outcome with equal predictor weights after rescaling each predictor
#       row by its range over the fit's units (treated + donors). Synth
#       rescales each row by its standard deviation over the same units and
#       then applies diag(V). Passing custom.v = var_k / range_k^2 (per fit,
#       normalised by Synth) makes Synth's inner problem identical to
#       StatsPAI's, so both solve the same strictly convex simplex QP. The
#       placebo aggregation is SCtools' own: mspe.test() runs on a "tdf"
#       object built exactly as SCtools::generate.placebos builds it (the
#       placebo fits themselves are done here, because generate.placebos
#       re-optimises V and passes no custom.v). SCtools drops the treated
#       unit from every placebo's donor pool; StatsPAI's
#       placebo_pool = "exclude_treated" reproduces that.
#
#   sp.conformal_synth vs scinference::scinference (GitHub kwuthrich/
#       scinference, the Chernozhukov-Wuthrich-Zhu authors' package;
#       SHA recorded in meta): estimation_method = "sc" (limSolve::lsei,
#       simplex LS without intercept), permutation_method = "mb" (moving
#       block, deterministic), q = 1. Joint p-value of a constant effect on
#       a fixed grid, pointwise p-values at 0 (T0 + one post-period), and
#       pointwise CIs (ci = TRUE) at alpha = 0.1 on the same grid.
#       Reference defect: on a few extreme grid values limSolve::lsei
#       (type 1) returns IsError = TRUE with infeasible weights (negative,
#       SSR 310 vs 86.6 at the true simplex optimum) and scinference uses
#       them anyway. Every lsei call's IsError flag is recorded, and the
#       same statistics are recomputed with the simplex QP solved by
#       quadprog::solve.QP (scinference's code otherwise unchanged); the
#       test holds StatsPAI to scinference where lsei succeeded and to the
#       quadprog replica everywhere.
#
#   sp.multi_outcome_synth vs augsynth::augsynth_multiout (augsynth 0.2.0;
#       Sun, Ben-Michael & Feller are augsynth's multi-outcome authors),
#       progfunc = "None", scm = TRUE, fixedeff = FALSE, combine_method =
#       "concat" / "avg". augsynth's synth_qp hard-codes OSQP eps 1e-8; the
#       generator re-runs the identical QP with eps 1e-12 by swapping
#       synth_qp for a copy with only the tolerance changed
#       (assignInNamespace), and keeps the stock-tolerance weights too.
#
#   sp.sequential_sdid: per-cohort ATT(g) vs synthdid::synthdid_estimate
#       (0.0.9) on the sub-panel sequential_sdid builds for that cohort
#       (cohort-g units + never-treated + later cohorts, periods up to the
#       one before the next cohort adopts).
#
#   sp.shift_share_political (long difference period 5 minus period 1,
#       national shock g = shocks[5] - shocks[1]): AER::ivreg + sandwich
#       HC1 (2SLS), ShiftShareSE::ivreg_ss (EHW / AKM / AKM0),
#       bartik.weight::bw (Rotemberg alpha_k, beta_k), and the share-balance
#       F from anova(lm(c1 ~ 1), lm(c1 ~ shares)).
#   sp.shift_share_political_panel (instrument Z_it = s_i' g_t, two-way FE):
#       fixest::feols(y ~ 1 | unit + time | x ~ Z) with ssc(adj = FALSE,
#       cluster.adj = FALSE) for cluster = unit / time / twoway,
#       fitstat "ivf1"; unit-only and time-only FE; the unbalanced panel;
#       ShiftShareSE::ivreg_ss with unit and time dummies as controls and
#       W = shares in industry x period blocks (AKM); bartik.weight::bw
#       with the dummies as controls (Rotemberg alpha_kt, summed over t);
#       per-period cross-section 2SLS with HC0 (AER + sandwich).
#
# Regenerate (after _generate_synth_rest_data.py), from the repo root:
#   Rscript tests/reference_parity/_generate_synth_rest_R.R

suppressPackageStartupMessages({
  library(jsonlite)
  library(Synth)
  library(SCtools)
  library(scinference)
  library(augsynth)
  library(synthdid)
  library(AER)
  library(sandwich)
  library(ShiftShareSE)
  library(bartik.weight)
  library(fixest)
})

script_dir <- tryCatch(
  dirname(normalizePath(sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE)[1]))),
  error = function(e) "tests/reference_parity"
)
fixtures <- file.path(script_dir, "_fixtures")
num <- function(x) as.numeric(x)

# ---------------------------------------------------------------------------
# 1. SCM sensitivity tools
# ---------------------------------------------------------------------------
scm <- read.csv(file.path(fixtures, "synth_rest_scm.csv"))
Yw <- reshape(scm, idvar = "time", timevar = "unit", direction = "wide")
Yw <- Yw[order(Yw$time), ]
times <- Yw$time
Y <- as.matrix(Yw[, -1])
colnames(Y) <- sub("^y\\.", "", colnames(Y))
units <- as.integer(colnames(Y))
tr <- 1L
T0time <- 15

# One SCM fit on the rows `rows` (pre-period = time < t_int within rows),
# treated column `trt`, donor columns `donors`. Returns weights, gap path,
# pre MSPE (Synth's loss.v) and the synthetic path.
#
# Solver precision. Synth solves its QP with kernlab::ipop, whose defaults
# (margin 5e-4, sigf 5) give ~5 significant digits; tighter settings make
# ipop's Newton system singular on some of these fits. So each fit is run
# through Synth::synth with the tightest ipop setting that succeeds (sigf 9
# down to 5, margin 10^-sigf; recorded), AND the identical QP -- Synth's own
# scaled H = X0s' V X0s, c = -X1s' V X0s, simplex constraints -- is solved
# exactly by quadprog::solve.QP (Goldfarb-Idnani dual active set). The
# quadprog weights are the reference; the ipop weights are kept to show that
# Synth itself lands on the same solution at its own precision.
synth_qp_exact <- function(X1, X0, cv) {
  big <- cbind(X0, X1)
  divisor <- sqrt(apply(big, 1, var))
  X0s <- X0 / divisor
  X1s <- X1 / divisor
  V <- diag(abs(cv) / sum(cv), nrow = length(cv))
  H <- t(X0s) %*% V %*% X0s
  cc <- -1 * c(t(X1s) %*% V %*% X0s)
  J <- ncol(X0)
  A <- cbind(rep(1, J), diag(J))
  sol <- quadprog::solve.QP(Dmat = H, dvec = -cc, Amat = A,
                            bvec = c(1, rep(0, J)), meq = 1)
  w <- pmax(sol$solution, 0)
  w / sum(w)
}

fit_scm <- function(trt, donors, t_int, rows = seq_along(times)) {
  tt <- times[rows]
  pre <- rows[tt < t_int]
  X1 <- matrix(Y[pre, as.character(trt)], ncol = 1)
  X0 <- Y[pre, as.character(donors), drop = FALSE]
  big <- cbind(X0, X1)
  rng <- apply(big, 1, function(r) max(r) - min(r))
  vr <- apply(big, 1, var)
  cv <- vr / rng^2
  ipop_w <- NULL
  ipop_sigf <- NA
  for (sg in 9:5) {
    out <- tryCatch(
      synth(X1 = X1, X0 = X0, Z1 = X1, Z0 = X0, custom.v = cv,
            Margin.ipop = 10^(-sg), Sigf.ipop = sg, Bound.ipop = 10,
            verbose = FALSE),
      error = function(e) NULL)
    if (!is.null(out)) {
      ipop_w <- num(out$solution.w)
      ipop_sigf <- sg
      break
    }
  }
  # Unique weights need X0 (pre-periods x donors) of full column rank;
  # early in-time placebos have fewer pre-periods than donors, so only the
  # pre-period fit (the projection) is unique there, not w or the post path.
  identified <- qr(X0)$rank == ncol(X0)
  w <- if (identified) synth_qp_exact(X1, X0, cv) else rep(NA_real_, ncol(X0))
  path <- Y[rows, as.character(donors), drop = FALSE] %*% w
  gap <- num(Y[rows, as.character(trt)] - path)
  gpre <- gap[tt < t_int]
  gpost <- gap[tt >= t_int]
  list(w = w, donors = donors, gap = gap, synth_path = num(path),
       ipop_w = ipop_w, ipop_sigf = ipop_sigf,
       identified = identified,
       ipop_max_abs_diff = if (identified) max(abs(ipop_w - w)) else NA,
       loss_v = mean(gpre^2), pre_rmse = sqrt(mean(gpre^2)),
       att = mean(gpost), post_mspe = mean(gpost^2),
       ratio = sqrt(mean(gpost^2)) / sqrt(mean(gpre^2)))
}

donors_all <- setdiff(units, tr)
base <- fit_scm(tr, donors_all, T0time)

# --- leave-one-out ----------------------------------------------------------
loo <- lapply(donors_all, function(d) {
  f <- fit_scm(tr, setdiff(donors_all, d), T0time)
  list(dropped_unit = d, att = f$att, pre_rmse = f$pre_rmse, weights = f$w,
       donors = f$donors, ipop_sigf = f$ipop_sigf,
       ipop_max_abs_diff = f$ipop_max_abs_diff)
})

# --- in-time placebos (post-treatment rows discarded) -----------------------
pre_rows <- which(times < T0time)
cand <- times[pre_rows][-(1:2)]
time_placebo <- lapply(cand, function(pt) {
  f <- fit_scm(tr, donors_all, pt, rows = pre_rows)
  list(placebo_time = pt, identified = f$identified, att = f$att,
       pre_rmse = f$pre_rmse, weights = f$w)
})

# --- donor subsets replayed from numpy (see the data generator) -------------
subs <- read.csv(file.path(fixtures, "synth_rest_donor_subsets.csv"),
                 colClasses = c("integer", "character"))
donor_subsets <- lapply(seq_len(nrow(subs)), function(i) {
  dd <- as.integer(strsplit(subs$donors[i], ",")[[1]])
  f <- fit_scm(tr, dd, T0time)
  list(iteration = subs$iteration[i], donors = subs$donors[i], att = f$att,
       pre_rmse = f$pre_rmse)
})

# --- in-space placebos + SCtools::mspe.test ---------------------------------
placebo_set <- function(include_treated) {
  lapply(donors_all, function(d) {
    pool <- setdiff(donors_all, d)
    if (include_treated) pool <- c(pool, tr)
    f <- fit_scm(d, pool, T0time)
    f$unit <- d
    f
  })
}

# tdf object in the exact layout SCtools::generate.placebos returns:
# columns synthetic.<name> (one per placebo), the placebos' observed paths
# (dataprep.out$Y0), Y1, synthetic.Y1, year; mspe.placs = each placebo's
# loss.v; loss.v = treated loss.v.
make_tdf <- function(pl) {
  n <- length(pl)
  b <- as.data.frame(sapply(pl, function(f) f$synth_path))
  names(b) <- paste0("synthetic.", sapply(pl, function(f) f$unit))
  Y0 <- as.data.frame(Y[, as.character(donors_all), drop = FALSE])
  df <- cbind(b, Y0, Y[, as.character(tr)], base$synth_path, times)
  colnames(df)[(ncol(df) - 2):ncol(df)] <- c("Y1", "synthetic.Y1", "year")
  names_numbers <- data.frame(unit.names = as.character(donors_all),
                              unit.numbers = donors_all)
  res <- list(df = df, mspe.placs = data.frame(sapply(pl, function(f) f$loss_v)),
              t0 = min(times), t1 = T0time, tr = tr,
              names.and.numbers = names_numbers, n = n,
              treated.name = as.character(tr), loss.v = base$loss_v)
  class(res) <- append(class(res), "tdf")
  res
}

mspe_block <- function(include_treated) {
  pl <- placebo_set(include_treated)
  tdf <- make_tdf(pl)
  full <- mspe.test(tdf)
  lim <- lapply(c(2, 5, 20), function(L) {
    r <- suppressWarnings(mspe.test(tdf, discard.extreme = TRUE, mspe.limit = L))
    list(mspe_limit = L, p_val = r$p.val, n_placebos = nrow(r$test) - 1)
  })
  list(
    placebo_units = sapply(pl, function(f) f$unit),
    placebo_pre_rmspe = sapply(pl, function(f) f$pre_rmse),
    placebo_ratio = sapply(pl, function(f) f$ratio),
    ipop_max_abs_diff = max(sapply(pl, function(f) f$ipop_max_abs_diff)),
    mspe_ratios = num(full$test$MSPE.ratios),
    p_val = full$p.val,
    limited = lim
  )
}

sensitivity <- list(
  treated = list(weights = base$w, donors = base$donors, att = base$att,
                 pre_rmse = base$pre_rmse, ratio = base$ratio,
                 loss_v = base$loss_v, ipop_weights = base$ipop_w,
                 ipop_sigf = base$ipop_sigf,
                 ipop_max_abs_diff = base$ipop_max_abs_diff),
  loo = loo,
  time_placebo = time_placebo,
  donor_subsets = donor_subsets,
  placebo_exclude_treated = mspe_block(FALSE),
  placebo_include_treated = mspe_block(TRUE)
)

# ---------------------------------------------------------------------------
# 2. Conformal inference (scinference)
# ---------------------------------------------------------------------------
Y1c <- num(Y[, as.character(tr)])
Y0c <- Y[, as.character(donors_all), drop = FALSE]
T0c <- sum(times < T0time)
T1c <- sum(times >= T0time)
cgrid <- seq(-2, 9, length.out = 45)
joint_p <- sapply(cgrid, function(g)
  scinference(Y1c, Y0c, T1 = T1c, T0 = T0c, theta0 = g,
              estimation_method = "sc", permutation_method = "mb")$p_val)
joint_p0 <- scinference(Y1c, Y0c, T1 = T1c, T0 = T0c, theta0 = 0,
                        estimation_method = "sc", permutation_method = "mb")$p_val
point_p0 <- sapply(seq_len(T1c), function(t) {
  idx <- c(1:T0c, T0c + t)
  scinference(Y1c[idx], Y0c[idx, ], T1 = 1, T0 = T0c, theta0 = 0,
              estimation_method = "sc", permutation_method = "mb")$p_val
})
ci10 <- scinference(Y1c, Y0c, T1 = T1c, T0 = T0c, alpha = 0.1, ci = TRUE,
                    ci_grid = cgrid, estimation_method = "sc",
                    permutation_method = "mb")
w_pre <- limSolve::lsei(A = Y0c[1:T0c, ], B = Y1c[1:T0c], E = matrix(1, 1, ncol(Y0c)),
                        F = 1, G = diag(ncol(Y0c)), H = matrix(0, ncol(Y0c), 1),
                        type = 1)$X
# scinference's movingblock / confidence_interval with the sc() fit
# swapped for quadprog, plus lsei's error flag for each fit.
sc_qp <- function(y, X) {
  J <- ncol(X)
  w <- quadprog::solve.QP(crossprod(X), num(crossprod(X, y)),
                          cbind(rep(1, J), diag(J)), c(1, rep(0, J)), meq = 1)$solution
  num(y - X %*% w)
}
lsei_err <- function(y, X) {
  J <- ncol(X)
  limSolve::lsei(A = X, B = y, E = matrix(1, 1, J), F = 1, G = diag(J),
                 H = matrix(0, J, 1), type = 1)$IsError
}
mb_qp <- function(g) {
  y <- Y1c; y[(T0c + 1):(T0c + T1c)] <- y[(T0c + 1):(T0c + T1c)] - g
  u <- abs(sc_qp(y, Y0c)); uc <- c(u, u)
  S <- sapply(1:(T0c + T1c), function(s) sum(uc[s:(s + T1c - 1)]))
  c(p = mean(S >= S[T0c + 1]), err = lsei_err(y, Y0c))
}
mbq <- sapply(cgrid, mb_qp)
pw_qp <- lapply(seq_len(T1c), function(t) {
  idx <- c(1:T0c, T0c + t)
  r <- sapply(cgrid, function(g) {
    y <- Y1c[idx]; y[T0c + 1] <- y[T0c + 1] - g
    u <- abs(sc_qp(y, Y0c[idx, ]))
    c(p = mean(u >= u[T0c + 1]), err = lsei_err(y, Y0c[idx, ]))
  })
  acc <- cgrid[r["p", ] > 0.1]
  list(p = num(r["p", ]), lsei_error = as.logical(r["err", ]),
       lb = min(acc), ub = max(acc))
})

conformal <- list(
  grid = cgrid,
  joint_p_quadprog = num(mbq["p", ]), joint_lsei_error = as.logical(mbq["err", ]),
  pointwise_quadprog = pw_qp, joint_p = joint_p, joint_p0 = joint_p0,
  pointwise_p0 = point_p0, pointwise_lb_alpha10 = ci10$lb,
  pointwise_ub_alpha10 = ci10$ub, pre_weights = num(w_pre),
  att = mean(Y1c[(T0c + 1):(T0c + T1c)] - Y0c[(T0c + 1):(T0c + T1c), ] %*% w_pre)
)

# ---------------------------------------------------------------------------
# 3. Multiple-outcome SCM (augsynth_multiout)
# ---------------------------------------------------------------------------
mo <- read.csv(file.path(fixtures, "synth_rest_multi.csv"))
stock_qp <- get("synth_qp", asNamespace("augsynth"))
tight_qp <- function(X1, X0, V) {
  Pmat <- X0 %*% V %*% t(X0)
  qvec <- -t(X1) %*% V %*% t(X0)
  n0 <- nrow(X0)
  A <- rbind(rep(1, n0), diag(n0))
  l <- c(1, numeric(n0))
  u <- c(1, rep(1, n0))
  settings <- osqp::osqpSettings(verbose = FALSE, eps_rel = 1e-12, eps_abs = 1e-12,
                                 max_iter = 200000L, polishing = TRUE)
  osqp::solve_osqp(P = Pmat, q = qvec, A = A, l = l, u = u, pars = settings)$x
}
run_mo <- function(cm) {
  fit <- augsynth_multiout(gdp | emp | inv ~ treated, unit, time, t_int = 12,
                           data = mo, progfunc = "None", scm = TRUE,
                           fixedeff = FALSE, combine_method = cm)
  att <- predict(fit, att = TRUE)
  post <- as.numeric(rownames(att)) >= 12
  list(weights = num(fit$weights), donors = as.integer(rownames(fit$weights)),
       att_path = lapply(colnames(att), function(k) num(att[, k])),
       att_post_mean = num(colMeans(att[post, , drop = FALSE])),
       outcomes = colnames(att))
}
assignInNamespace("synth_qp", tight_qp, ns = "augsynth")
mo_tight <- list(concat = run_mo("concat"), avg = run_mo("avg"))
assignInNamespace("synth_qp", stock_qp, ns = "augsynth")
mo_stock <- list(concat = run_mo("concat"), avg = run_mo("avg"))
multi_outcome <- list(tight = mo_tight, stock = mo_stock)

# ---------------------------------------------------------------------------
# 4. Sequential SDID: per-cohort blocks
# ---------------------------------------------------------------------------
st <- read.csv(file.path(fixtures, "synth_rest_stag.csv"))
cohorts <- sort(setdiff(unique(st$cohort), 0))
seq_sdid <- lapply(seq_along(cohorts), function(k) {
  g <- cohorts[k]
  tmax <- if (k < length(cohorts)) cohorts[k + 1] - 1 else max(st$time)
  sub <- st[(st$cohort == 0 | st$cohort >= g) & st$time <= tmax, ]
  sub$W <- as.integer(sub$cohort == g & sub$time >= g)
  pm <- panel.matrices(sub[, c("unit", "time", "y", "W")])
  est <- synthdid_estimate(pm$Y, pm$N0, pm$T0)
  list(cohort = g, t_max = tmax, att = num(est), n_treated = sum(sub$cohort == g) / length(unique(sub$time)))
})

# ---------------------------------------------------------------------------
# 5. Shift-share
# ---------------------------------------------------------------------------
pan <- read.csv(file.path(fixtures, "synth_rest_ss_panel.csv"))
unb <- read.csv(file.path(fixtures, "synth_rest_ss_panel_unbal.csv"))
shr <- read.csv(file.path(fixtures, "synth_rest_ss_shares.csv"))
shk <- read.csv(file.path(fixtures, "synth_rest_ss_shocks.csv"))
inds <- setdiff(names(shr), "unit")
S <- as.matrix(shr[order(shr$unit), inds])
g <- num(as.matrix(shk[shk$time == 5, inds]) - as.matrix(shk[shk$time == 1, inds]))

# --- cross-section, long difference -----------------------------------------
p1 <- pan[pan$time == 1, ]; p5 <- pan[pan$time == 5, ]
p1 <- p1[order(p1$unit), ]; p5 <- p5[order(p5$unit), ]
cs <- data.frame(dy = p5$y - p1$y, dx = p5$x - p1$x, B = num(S %*% g), c1 = p1$c1)
iv_cs <- ivreg(dy ~ dx | B, data = cs)
se_hc1 <- sqrt(diag(vcovHC(iv_cs, type = "HC1")))["dx"]
ss <- ivreg_ss(dy ~ 1 | dx, X = B, data = cs, W = S,
               method = c("homosk", "ehw", "akm", "akm0"))
gl <- data.frame(ind = inds, g = g)
loc <- cbind(data.frame(id = seq_len(nrow(S))), as.data.frame(S))
bw_cs <- bw(cs, "dy", "dx", controls = NULL, weight = NULL, local = loc,
            Z = inds, global = gl, G = "g")
sb <- anova(lm(c1 ~ 1, data = cs), lm(c1 ~ S, data = cs))
shift_share_cs <- list(
  beta = num(coef(iv_cs)["dx"]), se_hc1 = num(se_hc1),
  ivreg_ss_se = as.list(setNames(num(ss$se), names(ss$se))),
  ivreg_ss_ci_l = as.list(setNames(num(ss$ci.l), names(ss$se))),
  ivreg_ss_ci_r = as.list(setNames(num(ss$ci.r), names(ss$se))),
  ivreg_ss_p = as.list(setNames(num(ss$p), names(ss$se))),
  ivreg_ss_beta = num(ss$beta),
  rotemberg_industry = bw_cs$ind, rotemberg_alpha = num(bw_cs$alpha),
  rotemberg_beta = num(bw_cs$beta),
  balance_F = num(sb$F[2]), balance_df1 = num(sb$Df[2]),
  balance_df2 = num(sb$Res.Df[2]), balance_p = num(sb$`Pr(>F)`[2]),
  balance_R2 = summary(lm(c1 ~ S, data = cs))$r.squared
)

# --- panel ------------------------------------------------------------------
add_Z <- function(d) {
  Sg <- S[match(d$unit, shr$unit[order(shr$unit)]), ]
  G <- as.matrix(shk[match(d$time, shk$time), inds])
  d$Z <- rowSums(Sg * G)
  d
}
pan <- add_Z(pan); unb <- add_Z(unb)
nossc <- ssc(adj = FALSE, cluster.adj = FALSE)
fx <- function(d, fe, vc) {
  f <- switch(fe,
    "two-way" = y ~ 1 | unit + time | x ~ Z,
    "unit" = y ~ 1 | unit | x ~ Z,
    "time" = y ~ 1 | time | x ~ Z)
  m <- feols(f, data = d, vcov = vc, ssc = nossc)
  list(beta = num(coef(m)["fit_x"]), se = num(se(m)["fit_x"]),
       # textbook partial F of the excluded instrument from the FE first
       # stage: (RSS_r - RSS_u) / (RSS_u / (n - #FE params - 1)), both RSS
       # from feols (fixest's own fitstat "ivf1" is not this quantity; its
       # value is recorded but not compared)
       fs_F = {
         f1 <- as.formula(paste("x ~ Z |", strsplit(deparse(f), "\\|")[[1]][2]))
         f0 <- as.formula(paste("x ~ 1 |", strsplit(deparse(f), "\\|")[[1]][2]))
         mu <- feols(f1, data = d); mr <- feols(f0, data = d)
         ru <- sum(resid(mu)^2); rr <- sum(resid(mr)^2)
         K <- sum(sapply(fixef(mu), length)) - (length(fixef(mu)) - 1) + 1
         (rr - ru) / (ru / (nobs(mu) - K))
       },
       ivf1_fixest = num(fitstat(m, "ivf1")[[1]]$stat))
}
panel_fx <- list(
  twoway_fe_unit = fx(pan, "two-way", ~unit),
  twoway_fe_time = fx(pan, "two-way", ~time),
  twoway_fe_twoway = fx(pan, "two-way", ~unit + time),
  unit_fe_unit = fx(pan, "unit", ~unit),
  time_fe_unit = fx(pan, "time", ~unit),
  unbal_twoway_fe_unit = fx(unb, "two-way", ~unit)
)
# AKM with the FE as dummy controls; shocks vary over time -> W has one
# column per (industry, period).
pan <- pan[order(pan$unit, pan$time), ]
Wp <- matrix(0, nrow(pan), length(inds) * 5)
for (t in 1:5) {
  rows <- which(pan$time == t)
  Wp[rows, ((t - 1) * length(inds) + 1):(t * length(inds))] <-
    S[match(pan$unit[rows], sort(shr$unit)), ]
}
pan$uf <- factor(pan$unit); pan$tf <- factor(pan$time)
ss_p <- ivreg_ss(y ~ uf + tf | x, X = Z, data = pan, W = Wp,
                 method = c("ehw", "akm", "akm0"))
# Rotemberg alpha_kt with the FE as controls (one dummy of each dropped).
D <- model.matrix(~ uf + tf, pan)[, -1]
pan_bw <- cbind(pan[, c("y", "x")], as.data.frame(D))
locp <- as.data.frame(Wp); names(locp) <- paste0("w", seq_len(ncol(Wp)))
glp <- data.frame(kt = names(locp),
                  G = num(t(as.matrix(shk[order(shk$time), inds]))))
bw_p <- bw(pan_bw, "y", "x", controls = colnames(D), weight = NULL,
           local = locp, Z = names(locp), global = glp, G = "G")
alpha_k <- tapply(num(bw_p$alpha), rep(inds, 5), sum)
per_period <- lapply(1:5, function(t) {
  d <- pan[pan$time == t, ]
  m <- ivreg(y ~ x | Z, data = d)
  list(time = t, estimate = num(coef(m)["x"]),
       se_hc0 = num(sqrt(diag(vcovHC(m, type = "HC0")))["x"]))
})
shift_share_panel <- list(
  fixest = panel_fx,
  ivreg_ss_beta = num(ss_p$beta),
  ivreg_ss_se = as.list(setNames(num(ss_p$se), names(ss_p$se))),
  ivreg_ss_ci_l = as.list(setNames(num(ss_p$ci.l), names(ss_p$se))),
  ivreg_ss_ci_r = as.list(setNames(num(ss_p$ci.r), names(ss_p$se))),
  rotemberg_industry = names(alpha_k), rotemberg_alpha = num(alpha_k),
  per_period = per_period
)

out <- list(
  meta = list(
    R_version = R.version.string,
    Synth = as.character(packageVersion("Synth")),
    SCtools = as.character(packageVersion("SCtools")),
    kernlab = as.character(packageVersion("kernlab")),
    quadprog = as.character(packageVersion("quadprog")),
    scinference = paste(as.character(packageVersion("scinference")),
                        packageDescription("scinference")$RemoteSha),
    limSolve = as.character(packageVersion("limSolve")),
    augsynth = as.character(packageVersion("augsynth")),
    osqp = as.character(packageVersion("osqp")),
    synthdid = as.character(packageVersion("synthdid")),
    AER = as.character(packageVersion("AER")),
    sandwich = as.character(packageVersion("sandwich")),
    ShiftShareSE = as.character(packageVersion("ShiftShareSE")),
    bartik.weight = as.character(packageVersion("bartik.weight")),
    fixest = as.character(packageVersion("fixest")),
    generated = format(Sys.Date())
  ),
  sensitivity = sensitivity,
  conformal = conformal,
  multi_outcome = multi_outcome,
  sequential_sdid = seq_sdid,
  shift_share_cs = shift_share_cs,
  shift_share_panel = shift_share_panel
)
writeLines(toJSON(out, auto_unbox = TRUE, digits = I(17), null = "null", na = "string"),
           file.path(fixtures, "synth_rest_R.json"))
cat("wrote", file.path(fixtures, "synth_rest_R.json"), "\n")

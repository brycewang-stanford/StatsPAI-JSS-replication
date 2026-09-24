#!/usr/bin/env Rscript
# ---------------------------------------------------------------------------
# R reference for tests/reference_parity/test_misc_sens_R_parity.py
# (round-2 "misc_sens" family: MI pooling, mediation / OVB / survival
# sensitivity, meta-analytic evidence synthesis, transport, and the
# Mendelian-randomisation leftovers).
#
# Run _fixtures/_generate_misc_sens_data.py first, then (any directory)
#   Rscript tests/reference_parity/_generate_misc_sens_R.R
# Writes _fixtures/misc_sens_mi_imputed.csv (the m completed datasets every
# side pools) and _fixtures/misc_sens_R.json; numbers at digits = 17.
#
# Packages: mice, mediation, sensemakr, EValue, metafor,
# MendelianRandomization, mrclust, causaleffect (+ igraph) from CRAN;
# GRAPPLE 0.2.2 (GitHub jingshuw/GRAPPLE) cannot be installed because its
# haploR import is archived, so its estimator file R/mr_fun_general.R is
# sourced from a checkout whose path is given in GRAPPLE_SRC; MR-BMA is
# Zuber et al.'s own script summary_mvMR_BF.R (GitHub
# verena-zuber/demo_AMD), path in ZUBER_SRC. Both scripts are read as
# published; nothing in them is edited.
#
# Conventions pinned (each decides a number below)
# ------------------------------------------------
# * mice::pool: qbar = mean, ubar = mean(se^2), b = var (m - 1 divisor),
#   t = ubar + (1 + 1/m) b, df = Barnard-Rubin (1999) with dfcom = the lm
#   residual df, riv = (1 + 1/m) b / ubar, fmi = (riv + 2/(df + 3))/(riv + 1).
#   The imputations are mice(m = 5, method = "pmm", seed = 20260918).
# * medsens(rho.by = 0.1): lm/lm "ct" branch -- iterated FGLS for the
#   two-equation SUR with the error correlation fixed at rho, residual
#   moments with the n - 1 divisor, iteration until the squared change in
#   the coefficients is below sqrt(.Machine$double.eps); var(ACME) is the
#   first-order delta method from solve(X' Omega^-1 X). err.cr.d is the grid
#   rho closest to ACME = 0.
# * sensemakr ovb_bounds: benchmark x1, kd = ky = k over the StatsPAI
#   multiplier grid; bias = se * sqrt(dof) * sqrt(r2yz.dx r2dz.x/(1-r2dz.x)),
#   adjusted estimate moved toward zero (reduce = TRUE).
# * metafor::rma(method = "DL") for tau^2, Q, I^2; rma(method = "FE") for
#   the inverse-variance pool.
# ---------------------------------------------------------------------------
suppressPackageStartupMessages({
  library(jsonlite); library(mice); library(mediation)
})
.a <- commandArgs(trailingOnly = FALSE)
.f <- sub("^--file=", "", .a[grep("^--file=", .a)])
HERE <- if (length(.f)) dirname(normalizePath(.f[1])) else "."
OUT <- file.path(HERE, "_fixtures")
rd <- function(name) read.csv(file.path(OUT, name))
ver <- function(p) as.character(packageVersion(p))
out <- list(versions = list(R = paste(R.version$major, R.version$minor, sep = "."),
                            mice = ver("mice"), mediation = ver("mediation")))

# ---- 1. Multiple-imputation pooling (mice::pool) --------------------------
mi <- rd("misc_sens_mi.csv")
imp <- mice(mi, m = 5, method = "pmm", seed = 20260918, printFlag = FALSE)
long <- complete(imp, "long")
g17 <- function(v) sprintf("%.17g", v)
imp_out <- data.frame(imp = long$.imp, id = long$.id, y = g17(long$y),
                      x1 = g17(long$x1), x2 = g17(long$x2), x3 = long$x3)
write.csv(imp_out, file.path(OUT, "misc_sens_mi_imputed.csv"),
          row.names = FALSE, quote = FALSE)
long <- read.csv(file.path(OUT, "misc_sens_mi_imputed.csv"))  # pool what we wrote
fits <- lapply(1:5, function(i) lm(y ~ x1 + x2 + x3, data = long[long$imp == i, ]))
pl <- pool(as.mira(fits))
ps <- summary(pl, conf.int = TRUE)
pp <- pl$pooled
out$mi <- list(term = as.character(pp$term), estimate = pp$estimate,
               ubar = pp$ubar, b = pp$b, t = pp$t, dfcom = pp$dfcom,
               df = pp$df, riv = pp$riv, lambda = pp$lambda, fmi = pp$fmi,
               se = ps$std.error, statistic = ps$statistic,
               p = ps$p.value, ci_lo = ps[["2.5 %"]], ci_hi = ps[["97.5 %"]])
# Large-sample pooling (dfcom = Inf): Rubin's (1987) df.
pl_inf <- pool(as.mira(fits), dfcom = Inf)
out$mi_inf <- list(df = pl_inf$pooled$df, fmi = pl_inf$pooled$fmi)

# ---- 2. Mediation sensitivity (mediation::medsens) ------------------------
md <- rd("misc_sens_med.csv")
fm <- lm(m ~ t + x1 + x2, data = md)
fy <- lm(y ~ t + m + x1 + x2, data = md)
set.seed(1)
me <- mediate(fm, fy, treat = "t", mediator = "m", sims = 50)
ms <- medsens(me, rho.by = 0.1, effect.type = "indirect")
# Closed form (Imai, Keele & Yamamoto 2010, Stat. Sci.): ACME(rho) = 0 at
# rho = corr(e_M, e_Y~T+X); computed here as an independent identity.
e1 <- resid(fm); e3 <- resid(lm(y ~ t + x1 + x2, data = md))
out$medsens <- list(rho = ms$rho, d0 = as.vector(ms$d0),
                    lower = as.vector(ms$lower.d0), upper = as.vector(ms$upper.d0),
                    err_cr = ms$err.cr.d, r2_m = ms$r.square.m, r2_y = ms$r.square.y,
                    R2star_thresh = ms$R2star.d.thresh,
                    R2tilde_thresh = ms$R2tilde.d.thresh,
                    rho_tilde = cor(e1, e3))
# The same analysis iterated to the fixed point (medsens' own eps argument).
ms_fp <- medsens(me, rho.by = 0.1, effect.type = "indirect", eps = 1e-26)
out$medsens_fixed_point <- list(d0 = as.vector(ms_fp$d0),
                                lower = as.vector(ms_fp$lower.d0),
                                upper = as.vector(ms_fp$upper.d0))

# ---- 3. OVB benchmark bounds (sensemakr) and the E-value (EValue) --------
suppressPackageStartupMessages({ library(sensemakr); library(EValue) })
out$versions$sensemakr <- ver("sensemakr"); out$versions$EValue <- ver("EValue")
ov <- rd("misc_sens_ovb.csv")
fit <- lm(y ~ d + x1 + x2 + x3, data = ov)
ks <- seq(0.5, 5, length.out = 19)
b <- ovb_bounds(fit, treatment = "d", benchmark_covariates = "x2", kd = ks, ky = ks)
r2d <- partial_r2(lm(d ~ x1 + x2 + x3, data = ov), covariates = "x2")
r2y <- partial_r2(fit, covariates = "x2")
cf <- summary(fit)$coefficients
sm <- sensemakr(fit, treatment = "d", benchmark_covariates = "x2", kd = 1)
out$ovb <- list(estimate = cf["d", 1], se = cf["d", 2], dof = fit$df.residual,
                r2dxj = unname(r2d), r2yxj = unname(r2y), k = ks,
                r2dz = b$r2dz.x, r2yz = b$r2yz.dx,
                adjusted_estimate = b$adjusted_estimate, adjusted_se = b$adjusted_se,
                adjusted_lo = b$adjusted_lower_CI, adjusted_hi = b$adjusted_upper_CI,
                rv_q = unname(sm$sensitivity_stats$rv_q),
                rv_qa = unname(sm$sensitivity_stats$rv_qa))
ev <- evalues.OLS(est = cf["d", 1], se = cf["d", 2], sd = sd(ov$y))
out$evalue_ols <- list(sd_y = sd(ov$y), rr = ev["RR", "point"],
                       rr_lo = ev["RR", "lower"], rr_hi = ev["RR", "upper"],
                       e_point = ev["E-values", "point"],
                       e_ci = unname(na.omit(ev["E-values", c("lower", "upper")])[1]))
# Hazard ratio: the bias factor that moves the CI limit to the null is the
# limit itself; its E-value is B + sqrt(B (B - 1)) (rare outcome).
evh <- evalues.HR(est = exp(0.4), lo = exp(0.4 - qnorm(0.975) * 0.15),
                  hi = exp(0.4 + qnorm(0.975) * 0.15), rare = TRUE)
out$evalue_hr <- list(log_hr = 0.4, se = 0.15, e_ci = unname(evh["E-values", "lower"]),
                      hr_lo = unname(evh["RR", "lower"]))

# ---- 4. Mendelian randomisation leftovers ----------------------------------
suppressPackageStartupMessages({ library(MendelianRandomization); library(mrclust) })
out$versions$MendelianRandomization <- ver("MendelianRandomization")
out$versions$mrclust <- ver("mrclust")
mr <- rd("mr_ldl.csv")      # round-1 file: MendelianRandomization's LDL-C data
o <- mr_input(bx = mr$bx, bxse = mr$bxse, by = mr$by, byse = mr$byse)
am <- mr_allmethods(o, method = "main")@Values
out$mr_allmethods <- list(method = am[, 1], est = am[, 2], se = am[, 3],
                          lo = am[, 4], hi = am[, 5], p = am[, 6])
# mr_mediation pieces: total = mr_ivw (default model), direct = mr_mvivw.
ivw <- mr_ivw(o)
mv <- mr_mvivw(mr_mvinput(bx = cbind(mr$bx, mr$hdl), bxse = cbind(mr$bxse, mr$hdlse),
                          by = mr$by, byse = mr$byse))
out$mr_mediation <- list(total = ivw@Estimate, total_se = ivw@StdError,
                         direct = mv@Estimate[1], direct_se = mv@StdError[1],
                         rse = mv@RSE)
# The same with byse tripled: residual standard error below 1, where the
# default model keeps the fixed-effect SE.
mv3 <- mr_mvivw(mr_mvinput(bx = cbind(mr$bx, mr$hdl, mr$tg),
                           bxse = cbind(mr$bxse, mr$hdlse, mr$tgse),
                           by = mr$by, byse = 3 * mr$byse))
out$mvivw_underdispersed <- list(est = mv3@Estimate, se = mv3@StdError, rse = mv3@RSE)

# MR-BMA: Zuber et al.'s summary_mvMR_BF (MIT; demo_AMD @ 4981b5a). The
# script reads its inputs from the globals bX / bY (object@ lines are
# commented out upstream), so they are set before the call.
zsrc <- "https://raw.githubusercontent.com/verena-zuber/demo_AMD/4981b5a56ce7ac33838d99c77af3b13d0096ff2a/summary_mvMR_BF.R"
zf <- tempfile(fileext = ".R"); download.file(zsrc, zf, quiet = TRUE)
suppressPackageStartupMessages(library(combinat))
source(zf)
bX <- cbind(mr$bx, mr$hdl, mr$tg) / mr$byse
bY <- matrix(mr$by / mr$byse, ncol = 1)
zin <- new("mvMRInput", betaX = bX, betaY = bY, exposure = c("ldl", "hdl", "tg"),
           outcome = "chd")
for (pp in c(0.5, 0.1)) {
  zb <- summary_mvMR_BF(zin, sigma = 0.5, prior_prob = pp)
  out[[paste0("mrbma_", pp)]] <- list(tupel = zb@tupel, pp = zb@pp,
                                      pp_marginal = zb@pp_marginal,
                                      bma = zb@BMAve_Estimate)
}

# GRAPPLE 0.2.2 (jingshuw/GRAPPLE @ 317e837): grappleRobustEst, sourced from
# its R file (the package cannot be installed: its haploR import is archived).
gsrc <- "https://raw.githubusercontent.com/jingshuw/GRAPPLE/317e837340a29129c52c9d9b22f5f8bae72e27d0/R/mr_fun_general.R"
gf <- tempfile(fileext = ".R"); download.file(gsrc, gf, quiet = TRUE)
source(gf)
gd <- data.frame(gamma_exp1 = mr$bx, se_exp1 = mr$bxse, gamma_out1 = mr$by,
                 se_out1 = mr$byse)
out$grapple <- list()
for (loss in c("tukey", "huber", "l2")) {
  g <- suppressWarnings(grappleRobustEst(gd, loss.function = loss, diagnosis = FALSE))
  out$grapple[[loss]] <- list(beta = unname(g$beta.hat), tau2 = g$tau2.hat,
                              se = sqrt(unname(g$beta.var)), tau2_se = g$tau2.se,
                              p = unname(g$beta.p.value))
}
out$versions$GRAPPLE <- "0.2.2 (317e837)"

# mrclust: EM over the Wald ratios with a null and a junk component.
set.seed(20260918)
wr <- mr$by / mr$bx
wr_se <- abs(mr$byse / mr$bx)
mc <- mr_clust_em(theta = wr, theta_se = wr_se, bx = mr$bx, by = mr$by,
                  bxse = mr$bxse, byse = mr$byse, obs_names = paste0("snp", seq_along(wr)))
out$mrclust <- list(results = mc$results$best, bic = mc$results$all$bic)

# ---- 5. Transport IOSW weights and meta-analytic heterogeneity -----------
suppressPackageStartupMessages({ library(sandwich); library(metafor) })
out$versions$sandwich <- ver("sandwich"); out$versions$metafor <- ver("metafor")
src <- rd("misc_sens_src.csv"); tgt <- rd("misc_sens_tgt.csv")
pool <- rbind(data.frame(src[, c("x1", "x2")], s = 1), data.frame(tgt[, c("x1", "x2")], s = 0))
lg <- glm(s ~ x1 + x2, family = binomial, data = pool,
          control = glm.control(epsilon = 1e-14, maxit = 100))
ps <- pmin(pmax(fitted(lg)[pool$s == 1], 1e-6), 1 - 1e-6)
pt <- mean(pool$s == 0)
w <- pt / (1 - pt) * (1 - ps) / ps
q <- quantile(w, c(0.01, 0.99), type = 7)
wt <- pmin(pmax(w, q[1]), q[2])
fw <- lm(y ~ a, data = src, weights = wt)
out$transport <- list(effect = unname(coef(fw)["a"]),
                      se_hc0 = sqrt(vcovHC(fw, type = "HC0")["a", "a"]),
                      ess = sum(wt)^2 / sum(wt^2), max_w = max(wt),
                      effect_untruncated = unname(coef(lm(y ~ a, data = src, weights = w))["a"]),
                      source_effect = unname(coef(lm(y ~ a, data = src))["a"]))
yi <- c(0.90, 0.42, 0.55, 0.05); si <- c(0.20, 0.10, 0.15, 0.12)
dl <- rma(yi = yi, sei = si, method = "DL")
fe <- rma(yi = c(0.50, 0.42) + c(-0.05, 0), sei = c(sqrt(0.2^2 + 0.02^2), 0.1), method = "FE")
out$meta <- list(yi = yi, si = si, tau2 = dl$tau2, Q = dl$QE, Qp = dl$QEp, I2 = dl$I2 / 100,
                 fe_est = as.numeric(fe$beta), fe_se = fe$se, fe_lo = fe$ci.lb, fe_hi = fe$ci.ub)

# ---- 6. Transportability identification (causaleffect::transport) -------
suppressPackageStartupMessages({ library(causaleffect); library(igraph) })
out$versions$causaleffect <- ver("causaleffect")
sel_graph <- function(edges) {
  g <- graph_from_edgelist(matrix(edges, ncol = 2, byrow = TRUE))
  E(g)$description <- NA
  V(g)$description <- ifelse(V(g)$name == "S", "S", NA)
  g
}
graphs <- list(
  a = c("X","Y", "W","Y", "W","X", "S","W"),
  b = c("X","Y", "S","Y"),
  c = c("X","Z", "Z","Y", "S","Z"),
  d = c("X","Y", "S","X"))
out$transport_id <- lapply(graphs, function(e)
  transport(y = "Y", x = "X", D = sel_graph(e), expr = TRUE))

writeLines(toJSON(out, digits = I(17), auto_unbox = TRUE, pretty = TRUE),
           file.path(OUT, "misc_sens_R.json"))

# ---------------------------------------------------------------------------
# R reference for tests/reference_parity/test_r2_frontier_parity.py
#
# Run _generate_frontier_struct_data.py and _generate_r2_frontier_data.py
# first, then from this directory:
#     Rscript _generate_r2_frontier_R.R
# Writes _fixtures/r2_frontier_R.json (numbers at 17 significant digits).
#
# Packages: sfaR (sfacross, efficiencies), metafrontier (malmquist_meta),
# sfa (zsfm), numDeriv (reference-point gradients only).
#
# Conventions pinned here
# -----------------------
# * malmquist (SFA, output orientation). One sfaR::sfacross half-normal
#   frontier per period (best of four optimisers by max |gradient|).
#     EC = TE_{t+1} / TE_t   with TE = sfaR efficiencies()$teBC
#                            (Battese-Coelli E[exp(-u)|e]) or $teJLMS
#                            (exp(-E[u|e])), each from its own period's fit;
#     TC = exp(0.5 (x_t + x_{t+1})' (b_{t+1} - b_t))  (geometric mean of the
#          frontier shift at both input bundles), M = EC * TC.
#   EC is a package quantity; TC is arithmetic on sfaR's betas.
# * malmquist, second reference: metafrontier::malmquist_meta(method = "sfa",
#   estimator = "bc88"/"jlms") with two groups g = id %% 2 (the function
#   requires >= 2 groups). Its group_malmquist EC_group = TE_t / TE_s from
#   its own optim() group-period SFA fits. Its TC_group is built from
#   Farrell-type distances exp(x'b - y) and is therefore the RECIPROCAL of the
#   standard (Shephard) TC: TC_group = 1 / TC; its MPI_group = EC * TC_group
#   mixes the two orientations and is not compared.
#   control = list(reltol = 1e-15, maxit = 20000, ndeps = rep(1e-6, 5))
#   tightens its BFGS stop and its finite-difference gradient step (optim's
#   default ndeps = 1e-3 leaves the group-period fits ~1e-3 off; see test).
# * zisf: sfa::zsfm (C. F. Parmeter & D. H. Bernstein).
#     "ZISF":   P(fully efficient) = exp(-|gamma|); sigv, sigu are standard
#               deviations (sign-free); -> logit p = log(p / (1 - p)),
#               ln_sigma = log |sig|.
#     "ZISF_Z": P = plogis(z'gamma) (logit = TRUE) -- same link as sp.zisf.
#     inefdec = FALSE is the cost frontier (eps = -(y - x'b)).
#   The reference optimum's own score is written (max |gradient| of sfa's
#   log-likelihood, transcribed from sfa's like.fn, by numDeriv), together
#   with its log-likelihood (= -opt$value), so the test can state how far
#   sfa's L-BFGS-B stop is from the exact optimum.
#   sfa stops L-BFGS-B at REL_REDUCTION_OF_F (score ~1e-4), so its point is
#   only good to ~1e-5 relative. "polished" = sfa's OWN log-likelihood
#   (transcribed below) taken from sfa's point by Newton steps with
#   numDeriv (Richardson) gradient / Hessian until max |score| < 1e-7 (the
#   numDeriv noise floor here is ~4e-8); its
#   SEs invert that Hessian. This is sfa's objective at its exact optimum,
#   not an independent implementation.
#   SEs: sfa inverts optim()'s numerical Hessian in ITS parameterisation;
#   beta SEs are invariant to the reparameterisation of the other
#   parameters at the optimum; the others are mapped by the delta method
#   in the test.
# ---------------------------------------------------------------------------
suppressMessages({
  library(sfaR)
  library(metafrontier)
  library(sfa)
  library(numDeriv)
  library(jsonlite)
})

fx <- "_fixtures"
out <- list(
  versions = list(
    R = R.version.string,
    sfaR = as.character(packageVersion("sfaR")),
    metafrontier = as.character(packageVersion("metafrontier")),
    sfa = as.character(packageVersion("sfa")),
    numDeriv = as.character(packageVersion("numDeriv"))
  )
)

# ----------------------------------------------------------- malmquist -----
pd_ <- read.csv(file.path(fx, "frontier_struct_malm.csv"))
periods <- sort(unique(pd_$t))
fits <- list()
for (tt in periods) {
  f <- NULL
  for (m in c("bfgs", "nr", "ucminf", "bhhh")) {
    ff <- try(sfaR::sfacross(y ~ x1 + x2, data = pd_[pd_$t == tt, ], S = 1,
                       udist = "hnormal", method = m, gradtol = 1e-10,
                       tol = 1e-14), silent = TRUE)
    if (inherits(ff, "try-error")) next
    if (is.null(f) || max(abs(ff$gradient)) < max(abs(f$gradient))) f <- ff
  }
  fits[[as.character(tt)]] <- f
}
per <- lapply(periods, function(tt) {
  f <- fits[[as.character(tt)]]
  e <- sfaR::efficiencies(f)
  sub <- pd_[pd_$t == tt, ]
  list(beta = unname(coef(f)[1:3]), loglik = f$mlLoglik,
       max_abs_gradient = max(abs(f$gradient)),
       id = sub$id, teBC = e$teBC, teJLMS = e$teJLMS)
})
names(per) <- as.character(periods)
idx_rows <- list()
for (k in seq_len(length(periods) - 1)) {
  s1 <- per[[k]]; s2 <- per[[k + 1]]
  a <- pd_[pd_$t == periods[k], ]; b <- pd_[pd_$t == periods[k + 1], ]
  j <- match(a$id, b$id)
  b <- b[j, ]
  X1 <- cbind(1, a$x1, a$x2); X2 <- cbind(1, b$x1, b$x2)
  lTC <- 0.5 * ((X1 + X2) %*% (s2$beta - s1$beta))
  ec_bc <- s2$teBC[j] / s1$teBC
  ec_jl <- s2$teJLMS[j] / s1$teJLMS
  idx_rows[[k]] <- data.frame(
    id = a$id, t_from = periods[k], t_to = periods[k + 1],
    tc = as.numeric(exp(lTC)),
    ec_bc = ec_bc, m_bc = ec_bc * as.numeric(exp(lTC)),
    ec_jlms = ec_jl, m_jlms = ec_jl * as.numeric(exp(lTC)))
}
it <- do.call(rbind, idx_rows)
it <- it[order(it$id, it$t_from), ]
out$malmquist_sfaR <- list(
  periods = lapply(per, function(p) p[c("beta", "loglik", "max_abs_gradient")]),
  index = as.list(it))

pd_$g <- pd_$id %% 2
for (est in c("bc88", "jlms")) {
  mm <- suppressMessages(malmquist_meta(
    y ~ x1 + x2, data = pd_, group = "g", time = "t", id = "id",
    method = "sfa", estimator = est,
    control = list(reltol = 1e-15, maxit = 20000, ndeps = rep(1e-6, 5))))
  gm <- mm$group_malmquist
  gm <- gm[order(gm$id, gm$period_from), ]
  out[[paste0("malmquist_meta_", est)]] <- list(
    id = gm$id, group = as.character(gm$group), t_from = gm$period_from,
    t_to = gm$period_to, EC_group = gm$EC_group, TC_group = gm$TC_group)
}

# ---------------------------------------------------------------- zisf -----
# sfa's ZISF / ZISF_Z log-likelihood, transcribed from sfa::zsfm's like.fn
# (used only to measure the score at sfa's reported optimum).
zisf_ll <- function(par, Y, X, Z = NULL, sgn = 1) {
  k <- ncol(X)
  if (is.null(Z)) {
    prob <- exp(-abs(par[1])); sv <- abs(par[2]); su <- abs(par[3])
    b <- par[4:(3 + k)]
  } else {
    sv <- abs(par[1]); su <- abs(par[2]); b <- par[3:(2 + k)]
    prob <- plogis(as.numeric(Z %*% par[(3 + k):length(par)]))
  }
  eps <- sgn * (Y - X %*% b)
  s <- sqrt(sv^2 + su^2); lam <- su / sv
  f1 <- -0.5 * log(2 * pi * sv^2) - 0.5 / sv^2 * eps^2
  f2 <- log(2 / s) + dnorm(-eps / s, log = TRUE) + pnorm(-eps * lam / s, log.p = TRUE)
  a1 <- log(prob) + f1; a2 <- log1p(-prob) + f2
  mx <- pmax(a1, a2)
  sum(mx + log(exp(a1 - mx) + exp(a2 - mx)))
}
zfit <- function(formula, model_name, data, Y, X, Z = NULL, cost = FALSE) {
  f <- sfa::zsfm(formula, model_name = model_name, data = data,
            inefdec = !cost, logit = TRUE)
  par <- unname(f$coefficients)
  sgn <- if (cost) -1 else 1
  fn <- function(p) zisf_ll(p, Y, X, Z, sgn)
  g <- numDeriv::grad(fn, par)
  pp <- par
  for (i in 1:50) {
    gp <- numDeriv::grad(fn, pp)
    if (max(abs(gp)) < 1e-7) break
    H <- numDeriv::hessian(fn, pp)
    pp <- pp - solve(H, gp)
  }
  gp <- numDeriv::grad(fn, pp)
  H <- numDeriv::hessian(fn, pp)
  polished <- list(par = pp, se = sqrt(diag(solve(-H))), loglik = fn(pp),
                   max_abs_gradient = max(abs(gp)), newton_steps = i - 1)
  list(names = names(f$coefficients), par = par, polished = polished,
       se = unname(f$std.errors), loglik = -f$opt$value,
       loglik_recomputed = zisf_ll(par, Y, X, Z, sgn),
       max_abs_gradient = max(abs(g)),
       convergence = f$opt$convergence, message = f$opt$message,
       post_prob = as.numeric(f$post.prob), jlms = as.numeric(f$jlms))
}
zd <- read.csv(file.path(fx, "frontier_struct_zisf.csv"))
Xz <- cbind(1, zd$x1, zd$x2)
out$zisf_prod <- zfit(y ~ x1 + x2, "ZISF", zd, zd$y, Xz)
zd$c <- -zd$y
out$zisf_cost <- zfit(c ~ x1 + x2, "ZISF", zd, zd$c, Xz, cost = TRUE)
zz <- read.csv(file.path(fx, "r2_frontier_zisf_z.csv"))
out$zisf_z <- zfit(y ~ x1 + x2 | z, "ZISF_Z", zz, zz$y,
                   cbind(1, zz$x1, zz$x2), Z = cbind(1, zz$z))

writeLines(toJSON(out, digits = I(17), auto_unbox = TRUE, pretty = TRUE),
           file.path(fx, "r2_frontier_R.json"))
cat("wrote", file.path(fx, "r2_frontier_R.json"), "\n")

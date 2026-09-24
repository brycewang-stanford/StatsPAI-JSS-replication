#!/usr/bin/env Rscript
# Ground truth for tests/reference_parity/test_r2_rdiv_parity.py
# (round-2 open items of the rd_iv family: sp.ivqreg against IVQR).
#
# Writes, under tests/reference_parity/_fixtures/:
#   r2_rdiv_ivqr_oid.csv  over-identified IV-QR design (n = 1500, one
#                         endogenous regressor, three instruments on very
#                         different scales, two controls); seed below
#   r2_rdiv_R.json        reference values at full double precision
#   r2_rdiv_ivqr_roots.csv  the inverse-QR roots (design, tau, root; %.17g),
#                         read by _fixtures/_generate_r2_rdiv_stata.do to
#                         centre Stata ivqregress's grid on them
# and reads the just-identified design rd_iv_ivqr.csv written by
# _generate_rd_iv_R.R.
#
# Re-run only when the contract changes:
#   Rscript tests/reference_parity/_generate_r2_rdiv_R.R
#
# Also stores R's Mersenne-Twister state after set.seed(666) (see the
# rdlocrand block below).
#
# Reference: R package IVQR 0.1.0 (Yu-Chang Chen; GitHub yuchang0321/IVQR,
# commit f36b124faa732bb5b51d817c12a5371329b75fe1, the only
# Chernozhukov-Hansen inverse-QR implementation found for R; not on CRAN).
# As released it stops on R >= 4.0 in ivqr.vc() with "the condition has
# length > 1", because
#     Check_Invertible <- function(m) class(try(solve(m),silent=T))=="matrix"
# compares class() of a matrix, which is c("matrix", "array") since R 4.0,
# against one string and feeds the length-2 result to `if`. This script
# downloads that commit, applies the ONE-LINE patch
#     Check_Invertible <- function(m) inherits(try(solve(m),silent=T), "matrix")
# (R/IVQR.R line 384; no numeric change: it only restores the intended
# TRUE/FALSE) and installs it into a PRIVATE library under tempdir() (or
# IVQR_LIB if set). Nothing is installed into the user library.
#
# What IVQR computes (read from its source, R/IVQR.R):
#   * ivqr(): the instrument is the least-squares projection
#     D_hat = [1, Z, X] (XZ'XZ)^{-1} XZ'D, i.e. the auxiliary quantile
#     regression is  rq(y - D alpha ~ D_hat + X)  (quantreg method "br");
#     with more instruments than endogenous regressors the model is thereby
#     collapsed to exact identification.
#   * objective: Wald statistic gamma' V_ker^{-1} gamma with quantreg's
#     summary.rq(se = "ker") covariance; the estimate is the grid point
#     minimising it (no refinement). Since dim(gamma) = dim(alpha) the
#     population minimum is gamma(alpha) = 0, so the fixture stores the
#     ROOT of gamma(alpha) (uniroot, tol 1e-13), and separately IVQR's own
#     grid argmin on a 0.001 grid to show it is the root rounded to the grid.
#   * ivqr.vc(): Powell kernel covariance,
#       e = y - D alpha - X beta   (beta from the rq at alpha, gamma dropped)
#       h = 1.364 (2 sqrt(pi))^(-1/5) sd(e) n^(-1/5)      ("Silver")
#       S = tau (1 - tau) Psi'Psi / n,  Psi = [D_hat, X]
#       J = (2 n h)^{-1} sum 1{|e| < h} Psi (D, X)'
#       V = J^{-1} S J^{-T} / n
#     SEs are stored for (alpha, intercept, controls) by calling ivqr() with
#     the one-point grid {root}, so they are IVQR's numbers at the root.

suppressMessages({
  library(quantreg)
  library(Formula)
  library(jsonlite)
})

FIX <- file.path("tests", "reference_parity", "_fixtures")
stopifnot(dir.exists(FIX))

# ---- patched IVQR in a private library ------------------------------------
IVQR_SHA <- "f36b124faa732bb5b51d817c12a5371329b75fe1"
lib <- Sys.getenv("IVQR_LIB", file.path(tempdir(), "ivqr_lib"))
if (!requireNamespace("IVQR", lib.loc = lib, quietly = TRUE)) {
  dir.create(lib, recursive = TRUE, showWarnings = FALSE)
  src <- file.path(tempdir(), "ivqr_src")
  dir.create(src, showWarnings = FALSE)
  tgz <- file.path(src, "ivqr.tar.gz")
  download.file(sprintf("https://github.com/yuchang0321/IVQR/archive/%s.tar.gz",
                        IVQR_SHA), tgz, quiet = TRUE)
  untar(tgz, exdir = src)
  pkg <- file.path(src, paste0("IVQR-", IVQR_SHA))
  f <- file.path(pkg, "R", "IVQR.R")
  code <- readLines(f)
  old <- 'Check_Invertible <- function(m) class(try(solve(m),silent=T))=="matrix"'
  new <- 'Check_Invertible <- function(m) inherits(try(solve(m),silent=T), "matrix")'
  hit <- grep(old, code, fixed = TRUE)
  stopifnot(length(hit) == 1L)
  code[hit] <- sub(old, new, code[hit], fixed = TRUE)
  writeLines(code, f)
  system2(file.path(R.home("bin"), "R"),
          c("CMD", "INSTALL", "--no-build-vignettes", "-l", shQuote(lib),
            shQuote(pkg)), stdout = FALSE, stderr = FALSE)
}
library(IVQR, lib.loc = lib)
stopifnot(inherits(try(solve(diag(2)), silent = TRUE), "matrix"))

# ---- over-identified design -----------------------------------------------
set.seed(20260918)
n <- 1500
z1 <- rnorm(n); z2 <- rnorm(n); z3 <- rnorm(n)
x1 <- rnorm(n); x2 <- rbinom(n, 1, 0.4); u <- rnorm(n)
# z3 enters on a scale 50x larger than z1 so that an identity-weighted
# criterion on the raw instruments is visibly scale-dependent.
d <- 0.6 * z1 + 0.4 * z2 + 0.25 * z3 + 0.3 * x1 + 0.7 * u + rnorm(n, 0, 0.5)
y <- 1 + 1.0 * d + 0.5 * x1 - 0.3 * x2 + (0.9 + 0.3 * d / 2) * u +
  rnorm(n, 0, 0.5)
write.csv(data.frame(y = y, d = d, z1 = z1, z2 = z2, z3 = 50 * z3,
                     x1 = x1, x2 = x2),
          file.path(FIX, "r2_rdiv_ivqr_oid.csv"), row.names = FALSE)
oid <- read.csv(file.path(FIX, "r2_rdiv_ivqr_oid.csv"))
jid <- read.csv(file.path(FIX, "rd_iv_ivqr.csv"))

designs <- list(
  jid = list(data = jid, formula = y ~ d | z | x1,
             Z = c("z"), X = c("x1")),
  oid = list(data = oid, formula = y ~ d | z1 + z2 + z3 | x1 + x2,
             Z = c("z1", "z2", "z3"), X = c("x1", "x2"))
)
TAUS <- c(0.25, 0.5, 0.75)

one_design <- function(ds) {
  dat <- ds$data
  XZ <- cbind(1, as.matrix(dat[, c(ds$Z, ds$X)]))
  dhat <- drop(XZ %*% solve(crossprod(XZ), crossprod(XZ, dat$d)))
  aux <- data.frame(dat, .dhat = dhat)
  rhs <- paste(c(".dhat", ds$X), collapse = " + ")
  g <- function(a, tau) {
    aux$.ytil <- aux$y - a * aux$d
    coef(rq(as.formula(paste(".ytil ~", rhs)), tau = tau, data = aux,
            method = "br"))[".dhat"]
  }
  out <- list()
  for (tau in TAUS) {
    grid <- seq(0.7, 1.4, by = 0.001)
    gv <- sapply(grid, g, tau = tau)
    ch <- which(diff(sign(gv)) != 0)
    root <- uniroot(function(a) g(a, tau), c(grid[ch[1]], grid[ch[1] + 1]),
                    tol = 1e-13)$root
    at_root <- ivqr(ds$formula, taus = tau, data = dat, grid = c(root))
    on_grid <- ivqr(ds$formula, taus = tau, data = dat, grid = grid)
    e <- drop(at_root$residuals)
    h <- 1.364 * ((2 * sqrt(pi))^(-1/5)) * sd(e) * (nrow(dat)^(-1/5))
    out[[as.character(tau)]] <- list(
      root = root,
      n_sign_changes = length(ch),
      gamma_at_root = as.numeric(at_root$coef$inst_var),
      exog_coef = as.numeric(at_root$coef$exog_var),
      exog_names = rownames(at_root$coef$exog_var),
      se = as.numeric(at_root$se),           # (alpha, intercept, controls)
      bandwidth = h,
      grid_argmin = as.numeric(on_grid$coef$endg_var),
      grid_step = 0.001
    )
  }
  out
}

# ---- R's random-number stream behind rdlocrand ------------------------------
# rdlocrand's rdrandinf() (hence rdsensitivity()) and rdrbounds() call
# set.seed(seed = 666) before EVERY p-value and then draw, per replication,
# sample(Dw) (fixed margins) or runif(n) <= prob (Bernoulli). Their p-values
# are therefore deterministic functions of R's Mersenne-Twister stream from
# seed 666. The fixture stores that stream's state (.Random.seed right after
# set.seed(666); RNGkind Mersenne-Twister / Inversion / Rejection) plus a
# short check sequence, so the test can regenerate R's draws bit-for-bit
# and feed them to StatsPAI's statistic / p-value code. The p-values being
# reproduced are those already frozen in rd_iv_rd_R.json (reps = 4000).
RNGkind("Mersenne-Twister", "Inversion", "Rejection")
set.seed(666)
seed666 <- as.integer(.Random.seed)
rng_check <- list(sample57 = sample(57), runif3 = runif(3))
rm(.Random.seed, envir = .GlobalEnv)

ref <- list(
  meta = list(
    R_version = R.version.string,
    IVQR_version = as.character(packageVersion("IVQR", lib.loc = lib)),
    IVQR_source = paste0("github.com/yuchang0321/IVQR@", IVQR_SHA,
                         " + one-line Check_Invertible patch"),
    quantreg_version = as.character(packageVersion("quantreg")),
    rdlocrand_version = as.character(packageVersion("rdlocrand")),
    RNGkind = RNGkind(),
    Formula_version = as.character(packageVersion("Formula")),
    seed = 20260918L,
    generated = "deterministic; re-run only on contract change"
  ),
  ivqr = lapply(designs, one_design),
  rng = list(seed = 666L, random_seed = seed666, check = rng_check)
)
writeLines(toJSON(ref, digits = I(17), auto_unbox = TRUE, pretty = TRUE,
                  null = "null"),
           file.path(FIX, "r2_rdiv_R.json"))
roots <- do.call(rbind, lapply(names(ref$ivqr), function(dn)
  data.frame(design = dn, tau = TAUS,
             root = sprintf("%.17g", sapply(as.character(TAUS),
                                            function(t) ref$ivqr[[dn]][[t]]$root)))))
write.csv(roots, file.path(FIX, "r2_rdiv_ivqr_roots.csv"), row.names = FALSE,
          quote = FALSE)
cat("wrote r2_rdiv_ivqr_oid.csv, r2_rdiv_R.json, r2_rdiv_ivqr_roots.csv\n")

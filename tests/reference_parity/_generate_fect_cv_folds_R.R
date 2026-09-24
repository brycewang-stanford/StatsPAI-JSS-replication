#!/usr/bin/env Rscript
# Given-fold reference for fect's CV scoring (tier T2 given the fold).
# Builds one set of 20 rolling folds with fect's own
# fect:::.build_cv_mask_rolling (set.seed(1), package defaults k = 20,
# cv.nobs = 3, cv.buffer = 1, cv.prop = 0.1, min.T0 = 5) on
# _fixtures/fect_cv_data.csv and scores every fold exactly as
# fect:::.fect_cv_score_one_ife_all / _mc_all do: a fresh initialFit on the
# remaining cells, inter_fe_ub (r = 0..5) / inter_fe_mc (fect's 10-point
# lambda grid) at cv_tol = 1e-3, MSPE of Y - fit on the scored cells.
# Writes _fixtures/fect_cv_folds_R.json with the folds (1-based column-major
# cell indices) and the fold x grid MSPE matrices, so StatsPAI can replay
# the identical folds. Also records the pooled MSPE fect would put in
# CV.out.ife / CV.out.mc.
#
#   Rscript tests/reference_parity/_generate_fect_cv_folds_R.R
suppressPackageStartupMessages({library(fect); library(jsonlite)})
here <- "tests/reference_parity/_fixtures"
df <- read.csv(file.path(here, "fect_cv_data.csv"))
ids <- sort(unique(df$id)); tt <- sort(unique(df$time))
N <- length(ids); TT <- length(tt)
Y <- matrix(NA, TT, N); D <- matrix(0, TT, N); X1 <- matrix(0, TT, N); X2 <- matrix(0, TT, N)
for (i in seq_len(nrow(df))) {
  r <- match(df$time[i], tt); c <- match(df$id[i], ids)
  Y[r, c] <- df$Y[i]; D[r, c] <- df$D[i]; X1[r, c] <- df$X1[i]; X2[r, c] <- df$X2[i]
}
I <- matrix(1L, TT, N); II <- I; II[D == 1] <- 0L
X <- array(c(X1, X2), dim = c(TT, N, 2))
YY <- Y; YY[II == 0] <- 0
oci <- which(c(II) == 1)
data.ini <- matrix(NA, TT * N, 5)
data.ini[, 1] <- c(Y); data.ini[, 2] <- rep(1:N, each = TT); data.ini[, 3] <- rep(1:TT, N)
data.ini[, 4] <- c(X1); data.ini[, 5] <- c(X2)
force <- 3; cv_tol <- 1e-3; max.iteration <- 1000; W.use <- as.matrix(0)
init <- fect:::initialFit(data = data.ini, force = force, oci = oci)
Y0 <- init$Y0
# fect's lambda grid (fect_cv): log-spaced below the largest singular value
Y.lambda <- YY - Y0; Y.lambda[II == 0] <- 0
eig <- svd(Y.lambda / (TT * N))$d
nlambda <- 10; lambda <- rep(NA, nlambda); lambda.by <- 3 / (nlambda - 2)
for (i in 1:(nlambda - 1)) lambda[i] <- 10^(log10(max(eig)) - (i - 1) * lambda.by)
lambda[nlambda] <- 0
r.grid <- 0:5
set.seed(1)
folds <- fect:::.build_cv_mask_rolling(II = II, D = D, k = 20, cv.nobs = 3, cv.buffer = 1,
                                       cv.prop = 0.1, min.T0 = 5, seed = NULL)
k <- length(folds)
mspe_ife <- matrix(NA, length(r.grid), k); mspe_mc <- matrix(NA, nlambda, k)
sse_ife <- matrix(0, length(r.grid), k); sse_mc <- matrix(0, nlambda, k); n_est <- integer(k)
fold_out <- list()
for (ii in seq_len(k)) {
  cv.id <- folds[[ii]]$cv.id; est.id <- folds[[ii]]$est.id
  ocicv <- setdiff(oci, cv.id)
  initcv <- fect:::initialFit(data = data.ini, force = force, oci = ocicv)
  II.cv <- II; II.cv[cv.id] <- 0L
  YY.cv <- YY; YY.cv[cv.id] <- 0
  b0 <- as.matrix(initcv$beta0)
  n_est[ii] <- length(est.id)
  for (ri in seq_along(r.grid)) {
    fit <- fect:::inter_fe_ub(YY.cv, initcv$Y0, X, II.cv, W.use, b0, r.grid[ri], force, cv_tol, max.iteration)$fit
    e <- YY[est.id] - fit[est.id]
    mspe_ife[ri, ii] <- mean(e^2); sse_ife[ri, ii] <- sum(e^2)
  }
  for (li in seq_len(nlambda)) {
    fit <- fect:::inter_fe_mc(YY.cv, initcv$Y0, X, II.cv, W.use, b0, 1L, lambda[li], force, cv_tol, max.iteration)$fit
    e <- YY[est.id] - fit[est.id]
    mspe_mc[li, ii] <- mean(e^2); sse_mc[li, ii] <- sum(e^2)
  }
  fold_out[[ii]] <- list(cv_id = cv.id, est_id = est.id)
  cat("fold", ii, "scored (", length(cv.id), "hidden,", length(est.id), "scored )\n")
}
out <- list(
  meta = list(fect_version = as.character(packageVersion("fect")), R_version = R.version.string,
              k = k, cv.nobs = 3, cv.buffer = 1, cv.prop = 0.1, min.T0 = 5, cv_tol = cv_tol,
              seed = 1, note = "1-based column-major cell indices (unit-major, TT rows per unit)"),
  r_grid = r.grid, lambda_grid = lambda, lambda_max = max(eig),
  folds = fold_out,
  mspe_ife_by_fold = mspe_ife, mspe_mc_by_fold = mspe_mc,
  pooled_mspe_ife = rowSums(sse_ife) / sum(n_est), pooled_mspe_mc = rowSums(sse_mc) / sum(n_est))
write_json(out, file.path(here, "fect_cv_folds_R.json"), digits = NA, auto_unbox = TRUE, matrix = "rowmajor")
cat("wrote fect_cv_folds_R.json\n")

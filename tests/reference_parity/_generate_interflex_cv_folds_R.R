#!/usr/bin/env Rscript
# Given-fold reference for interflex's kernel bandwidth CV (tier T2 given the
# fold): scores StatsPAI's fold assignments (from
# _fixtures/interflex_cv_folds.json) with interflex's own getError.CV and
# wls.nofe closures, extracted verbatim from deparse(interflex:::interflex.kernel)
# and evaluated in an environment carrying the same free variables the
# package sets up (discrete D with base 0, unit weights, X.eval over the
# full-sample range, the training-sample density). Writes
# _fixtures/interflex_cv_folds_R.json: per seed and grid index the per-fold
# (Num.Eff.Points, MSE, MAE) that interflex would average.
#
#   Rscript tests/reference_parity/_generate_interflex_cv_folds_R.R
suppressPackageStartupMessages({library(interflex); library(jsonlite); library(sandwich)})
here <- "tests/reference_parity/_fixtures"
src <- deparse(interflex:::interflex.kernel)
grab <- function(start_pat, end_pat) {
  s <- grep(start_pat, src)[1]; e <- grep(end_pat, src); e <- e[e > s][1] - 1
  eval(parse(text = src[s:e]), envir = globalenv())
}
grab("wls.nofe <- function", "wls <- function\\(x, data")
grab("getError.CV <- function", "fold <- createFolds")
data <- read.csv(file.path(here, "interflex_cv_data.csv"))
n <- nrow(data)
Y <- "Y"; D <- "D"; X <- "X"; Z <- "Z1"; FE <- NULL; IV <- NULL; use_fe <- 0
treat.type <- "discrete"; other.treat <- "1"; full.moderate <- FALSE
method <- "linear"; binary <- FALSE
data[, "D.1"] <- as.numeric(data[, D] == 1)
w <- rep(1, n); data[, "WEIGHTS"] <- w
neval <- 50
X.eval <- seq(min(data[, X]), max(data[, X]), length.out = neval)
rangeX <- max(data[, X]) - min(data[, X])
bw.grid <- exp(seq(log(rangeX / 100), log(rangeX), length.out = 30))
spec <- fromJSON(file.path(here, "interflex_cv_folds.json"))
kfold <- spec$kfold
out <- list(meta = list(interflex_version = as.character(packageVersion("interflex")),
                        R_version = R.version.string, grid = bw.grid,
                        grid_indices = spec$grid_indices), seeds = list())
for (s in names(spec$folds)) {
  fold <- as.integer(spec$folds[[s]])
  res <- list()
  for (gi in spec$grid_indices) {
    bw <- bw.grid[gi + 1]
    err <- matrix(NA, kfold, 5)
    for (j in 1:kfold) {
      testid <- which(fold == j)
      train <- data[-testid, ]; test <- data[testid, ]
      suppressWarnings(Xdensity.train <- density(data[-testid, X], weights = w[-testid]))
      err[j, ] <- getError.CV(train = train, test = test, bw = bw, neval = neval,
                              weights_name = "WEIGHTS", Xdensity = Xdensity.train)
    }
    res[[as.character(gi)]] <- list(bw = bw, n_eff = err[, 1], mse = err[, 4], mae = err[, 5])
  }
  out$seeds[[s]] <- res
  cat("seed", s, "scored\n")
}
write_json(out, file.path(here, "interflex_cv_folds_R.json"), digits = NA, na = "null", auto_unbox = TRUE)
cat("wrote interflex_cv_folds_R.json\n")

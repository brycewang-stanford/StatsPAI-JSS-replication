#!/usr/bin/env Rscript
# R reference for the fect / interflex cross-validation selectors (tier T3).
#
# Reads the two fixture CSVs written by
#   tests/reference_parity/_fixtures/_generate_fect_interflex_cv_data.py
# and, for each of 20 fold seeds, runs
#   fect::fect(method = "ife", CV = TRUE, r = c(0, 5))         -> r.cv, CV.out.ife
#   fect::fect(method = "mc",  CV = TRUE, nlambda = 10)        -> lambda.cv, CV.out.mc
#   interflex::interflex(estimator = "kernel", bw = NULL)      -> bw, CV.output
# with every other option at the package default (se = FALSE, parallel =
# FALSE so the fold stream is the seeded one), and writes
#   tests/reference_parity/_fixtures/fect_interflex_cv_R.json
# with the per-seed selections and CV curves. The Python port draws its
# folds from numpy, so the comparison is statistical: the StatsPAI curve
# must sit inside the across-seed spread recorded here.
#
#   Rscript tests/reference_parity/_generate_fect_interflex_cv_R.R
suppressPackageStartupMessages({library(fect); library(interflex); library(jsonlite)})
here <- "tests/reference_parity/_fixtures"
seeds <- 1:20

fect_df <- read.csv(file.path(here, "fect_cv_data.csv"))
iflx_df <- read.csv(file.path(here, "interflex_cv_data.csv"))

# Provenance: the options fect.default actually hands to its fect_cv worker
# (fect.formula's defaults differ from fect.default's signature).
captured <- NULL
trace(fect:::fect_cv, quote({
  assign(".fect_cv_args", list(k = k, cv.prop = cv.prop, cv.method = cv.method,
    cv.nobs = cv.nobs, cv.donut = cv.donut, cv.buffer = cv.buffer,
    min.T0 = min.T0, criterion = criterion, cv.rule = cv.rule,
    proportion = proportion, tol = tol, r = r, r.end = r.end,
    nlambda = nlambda), envir = .GlobalEnv)
}), print = FALSE, where = asNamespace("fect"))

ife_runs <- list(); mc_runs <- list(); bw_runs <- list()
t_all <- Sys.time()
for (s in seeds) {
  set.seed(s)
  o <- suppressMessages(fect(Y ~ D + X1 + X2, data = fect_df, index = c("id", "time"),
                             method = "ife", CV = TRUE, r = c(0, 5), se = FALSE,
                             parallel = FALSE, force = "two-way"))
  if (is.null(captured)) captured <- .fect_cv_args
  tab <- o$CV.out.ife
  ife_runs[[as.character(s)]] <- list(
    r_cv = as.integer(o$r.cv),
    r = as.integer(tab[, "r"]),
    mspe = as.numeric(tab[, "MSPE"]),
    gmspe = as.numeric(tab[, "GMSPE"]),
    moment = as.numeric(tab[, "Moment"]),
    sigma2 = as.numeric(tab[, "sigma2"]),
    ic = as.numeric(tab[, "IC"]),
    pc = as.numeric(tab[, "PC"]),
    att_avg = as.numeric(o$att.avg))
  set.seed(s)
  o2 <- suppressMessages(fect(Y ~ D + X1 + X2, data = fect_df, index = c("id", "time"),
                              method = "mc", CV = TRUE, nlambda = 10, se = FALSE,
                              parallel = FALSE, force = "two-way"))
  tab2 <- o2$CV.out.mc
  mspe2 <- as.numeric(tab2[, "MSPE"]); mspe2[mspe2 >= 1e19] <- NA
  mc_runs[[as.character(s)]] <- list(
    lambda_cv = as.numeric(o2$lambda.cv),
    lambda_norm_cv = as.numeric(o2$lambda.norm),
    lambda_seq = as.numeric(o2$lambda.seq),
    lambda_norm = as.numeric(tab2[, "lambda.norm"]),
    mspe = mspe2,
    n_evaluated = sum(!is.na(mspe2)),
    att_avg = as.numeric(o2$att.avg))
  set.seed(s)
  k <- suppressWarnings(suppressMessages(interflex(estimator = "kernel", Y = "Y", D = "D",
                                                    X = "X", Z = "Z1", data = iflx_df,
                                                    CI = FALSE, figure = FALSE,
                                                    parallel = FALSE, verbose = FALSE)))
  cvo <- k$CV.output
  bw_runs[[as.character(s)]] <- list(
    bw = as.numeric(k$bw),
    grid = as.numeric(cvo[, "bw"]),
    num_eff_points = as.numeric(cvo[, "Num.Eff.Points"]),
    mse = as.numeric(cvo[, "MSE"]),
    mae = as.numeric(cvo[, "MAE"]))
  cat(sprintf("seed %2d: r.cv=%d lambda.norm=%.4f bw=%.4f (%.0fs)\n", s, o$r.cv,
              o2$lambda.norm, k$bw, as.numeric(difftime(Sys.time(), t_all, units = "secs"))))
}
untrace(fect:::fect_cv, where = asNamespace("fect"))

out <- list(
  meta = list(
    R_version = R.version.string,
    fect_version = as.character(packageVersion("fect")),
    interflex_version = as.character(packageVersion("interflex")),
    seeds = seeds,
    fect_cv_options = captured,
    interflex_options = list(kfold = 10, grid = 30, metric = "MSE", neval = 50),
    note = paste("Fold draws use R's RNG (set.seed(seed) before each call);",
                 "the StatsPAI port cannot reproduce them, so the Python test",
                 "compares against the across-seed distribution recorded here.")),
  fect_ife = ife_runs, fect_mc = mc_runs, interflex_kernel = bw_runs)
write_json(out, file.path(here, "fect_interflex_cv_R.json"), digits = NA, auto_unbox = TRUE, pretty = TRUE, na = "null")
cat("wrote fect_interflex_cv_R.json\n")

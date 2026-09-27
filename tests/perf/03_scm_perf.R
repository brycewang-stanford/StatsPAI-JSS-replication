# Track C performance -- Classical SCM (R side).
# Same task and bytes as 03_scm_perf.py: the ADH specification (one outcome
# special predictor per pre-treatment year 1970-1984, nested V by optimx
# BFGS), weights and gap only -- no placebo loop on either side -- on
# data/03_scm_<donors>.csv.
.args <- commandArgs(trailingOnly = FALSE)
.f <- grep("^--file=", .args, value = TRUE)
source(file.path(if (length(.f)) dirname(normalizePath(sub("^--file=", "", .f[1]))) else getwd(), "_common.R"))
suppressPackageStartupMessages(library(Synth))

EST <- "03_scm"
N_REPS <- 3L
pre_years <- 1970:1984
post_years <- 1985:1999
rows <- list()
for (n_donors in c(20L, 50L, 100L)) {
  d <- read_perf_data(EST, n_donors)
  df <- d$df
  controls <- setdiff(sort(unique(df$unit_id)), 1L)
  special <- lapply(pre_years, function(yr) list("y", yr, "mean"))
  fn <- function() {
    dp <- Synth::dataprep(
      foo = df, predictors = NULL, predictors.op = "mean", dependent = "y",
      unit.variable = "unit_id", time.variable = "year",
      special.predictors = special, treatment.identifier = 1L,
      controls.identifier = controls, time.predictors.prior = pre_years,
      time.optimize.ssr = pre_years, time.plot = c(pre_years, post_years),
      unit.names.variable = "unit_name"
    )
    list(dp = dp, fit = Synth::synth(data.prep.obj = dp, optimxmethod = "BFGS", verbose = FALSE))
  }
  out <- suppressMessages(fn())
  post <- as.character(post_years)
  gap <- out$dp$Y1plot[post, 1] - (out$dp$Y0plot[post, ] %*% out$fit$solution.w)[, 1]
  res <- time_one(fn, n_reps = N_REPS)
  rows[[length(rows) + 1L]] <- perf_row(EST, n_donors, N_REPS, res, list(
    n_donors = n_donors, T = 30L,
    data_sha256 = d$sha256,
    task = "ADH special predictors (each pre-year), nested V, no placebos",
    estimate = mean(gap),
    loss_v = as.numeric(out$fit$loss.v),
    package = "Synth"
  ))
  cat(sprintf("  n_donors=%4d  median=%.3fs\n", n_donors, res$median))
}
write_perf(EST, rows, "Synth")

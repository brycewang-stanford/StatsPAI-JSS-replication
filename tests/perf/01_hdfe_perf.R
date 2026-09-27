# Track C performance benchmark -- HDFE 2-way FE (R side).
# Same task and bytes as 01_hdfe_perf.py: feols(y ~ x1 + x2 | firm + year,
# vcov = "iid") on data/01_hdfe_<N>.csv, one thread.
.args <- commandArgs(trailingOnly = FALSE)
.f <- grep("^--file=", .args, value = TRUE)
source(file.path(if (length(.f)) dirname(normalizePath(sub("^--file=", "", .f[1]))) else getwd(), "_common.R"))
suppressPackageStartupMessages(library(fixest))
fixest::setFixest_nthreads(1L)

EST <- "01_hdfe"
N_REPS <- 5L
rows <- list()
for (n in c(10000L, 100000L, 1000000L)) {
  d <- read_perf_data(EST, n)
  df <- d$df
  fn <- function() fixest::feols(y ~ x1 + x2 | firm + year, data = df, vcov = "iid")
  fit <- fn()
  res <- time_one(fn, n_reps = N_REPS)
  rows[[length(rows) + 1L]] <- perf_row(EST, n, N_REPS, res, list(
    data_sha256 = d$sha256,
    task = "OLS, two absorbed FE (firm, year), iid SE",
    estimate = unname(coef(fit)["x1"]),
    se = unname(se(fit)["x1"]),
    package = "fixest"
  ))
  cat(sprintf("  N=%9d  median=%.3fs  iqr=%.3fs\n", n, res$median, res$iqr))
}
write_perf(EST, rows, "fixest")

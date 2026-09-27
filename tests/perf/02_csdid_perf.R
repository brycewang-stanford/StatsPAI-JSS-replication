# Track C performance -- CS-DiD (R side).
# Same task and bytes as 02_csdid_perf.py: att_gt (reg, never-treated,
# analytic SEs; computes the pre-test) + aggte simple + aggte dynamic on
# data/02_csdid_<units>.csv (periods 1..5, cohorts 2, 3, 4).
.args <- commandArgs(trailingOnly = FALSE)
.f <- grep("^--file=", .args, value = TRUE)
source(file.path(if (length(.f)) dirname(normalizePath(sub("^--file=", "", .f[1]))) else getwd(), "_common.R"))
suppressPackageStartupMessages(library(did))

EST <- "02_csdid"
N_REPS <- 3L
T_PERIODS <- 5L
rows <- list()
for (n_units in c(1000L, 5000L, 25000L)) {
  d <- read_perf_data(EST, n_units)
  df <- d$df
  # did recodes never-treated first_treat = 0 to Inf inside a data.table; on
  # an integer column that assignment becomes NA and those units are dropped
  # silently ("No never-treated group is available"), so the fit uses the
  # last cohort as controls. read.csv parses the column as integer. The
  # previous version of this benchmark built it with integer() and timed
  # that degenerate problem; the output check in compare_perf.py caught it.
  df$first_treat <- as.numeric(df$first_treat)
  fn <- function() {
    fit <- did::att_gt(
      yname = "y", tname = "year", idname = "unit", gname = "first_treat",
      data = df, control_group = "nevertreated", est_method = "reg",
      bstrap = FALSE, cband = FALSE
    )
    list(
      simple = did::aggte(fit, type = "simple", bstrap = FALSE, cband = FALSE),
      dynamic = did::aggte(fit, type = "dynamic", bstrap = FALSE, cband = FALSE),
      pretest = fit$Wpval
    )
  }
  out <- fn()
  res <- time_one(fn, n_reps = N_REPS)
  rows[[length(rows) + 1L]] <- perf_row(EST, n_units * T_PERIODS, N_REPS, res, list(
    n_units = n_units, T = T_PERIODS,
    data_sha256 = d$sha256,
    task = "ATT(g,t) reg/never-treated, analytic SE, pre-test, simple + dynamic aggregation",
    estimate = out$simple$overall.att,
    se = out$simple$overall.se,
    package = "did"
  ))
  cat(sprintf("  N_units=%6d  median=%.3fs\n", n_units, res$median))
}
write_perf(EST, rows, "did")

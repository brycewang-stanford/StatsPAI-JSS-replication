#!/usr/bin/env Rscript
# Algorithmic Monte Carlo reference for sp.causal_forest vs R grf.
#
# The data are held FIXED (grf_data.csv, n = 1000). Only the forest's own
# randomness -- subsampling, split candidates, honesty splits -- varies, by
# refitting under K seeds. The spread across seeds is the forest's Monte
# Carlo error conditional on the data; it is a different object from the
# ATE standard error, which describes sampling variation across datasets.
# Comparing two engines' seed distributions is what "agreement within
# combined Monte Carlo error" has to mean for a stochastic estimator.
#
# Seeds are spaced 1e5 apart: grf forests grown from consecutive seeds share
# most of their random draws, which understates grf's Monte Carlo error by
# roughly an order of magnitude (found by the forest line, 2026-09-24).
#
# Output: grf_seed_mc_R.json, per tree count, per seed: AIPW ATE and its SE,
# AIPW ATT, and OOB CATE predictions at the first 20 training rows.
suppressMessages({ library(grf); library(jsonlite) })

# Usage: Rscript _generate_grf_seed_mc_R.R [grf | m13]
#   grf  grf_data.csv (the reference-parity fixture)       -> grf_seed_mc_R.json
#   m13  Track A module 13's clean-overlap CSV              -> grf_seed_mc_m13_R.json
arg <- commandArgs(trailingOnly = TRUE)
which <- if (length(arg)) arg[1] else "grf"
if (which == "grf") {
  df <- read.csv("grf_data.csv")
  X <- as.matrix(df[, paste0("X", 1:5)]); y <- df$y; W <- df$W
  outfile <- "grf_seed_mc_R.json"
} else {
  df <- read.csv("../../r_parity/data/13_causal_forest.csv")
  X <- as.matrix(df[, paste0("x", 1:5)]); y <- df$Y; W <- df$T
  outfile <- "grf_seed_mc_m13_R.json"
}
DESIGN <- list(list(trees = 500, K = 50), list(trees = 2000, K = 50),
               list(trees = 8000, K = 20))
out <- list()
for (d in DESIGN) {
  runs <- vector("list", d$K)
  for (k in seq_len(d$K)) {
    cf <- causal_forest(X, y, W, num.trees = d$trees, seed = 1000L + 100000L * k)
    ate <- average_treatment_effect(cf, target.sample = "all")
    att <- average_treatment_effect(cf, target.sample = "treated")
    runs[[k]] <- list(seed = 1000L + 100000L * k,
                      ate = unname(ate["estimate"]), ate_se = unname(ate["std.err"]),
                      att = unname(att["estimate"]),
                      cate20 = unname(predict(cf)$predictions[1:20]))
  }
  out[[paste0("trees_", d$trees)]] <- runs
}
out$meta <- list(R = R.version.string, grf = as.character(packageVersion("grf")),
                 n = nrow(df), seeds = "1000 + 100000 k")
write_json(out, outfile, auto_unbox = TRUE, digits = NA)

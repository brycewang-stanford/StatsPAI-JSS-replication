#!/usr/bin/env Rscript
# grf::causal_forest out-of-bag CATEs and variances on the engine-parity
# designs, three seeds each (T3 statistical reference).
#
#   Rscript tests/reference_parity/_fixtures/_generate_grf_engine.R
suppressMessages({library(grf); library(jsonlite)})
here <- "tests/reference_parity/_fixtures"
df <- read.csv(file.path(here, "grf_engine_data.csv"))
out <- list(meta = list(R_version = R.version.string,
                        grf_version = as.character(packageVersion("grf")),
                        num_trees = 2000, seeds = c(11, 22, 33)))
for (design in c("iid", "clustered")) {
  d <- df[df$design == design, ]
  X <- as.matrix(d[, paste0("x", 1:5)])
  runs <- list()
  for (seed in c(11, 22, 33)) {
    args <- list(X = X, Y = d$Y, W = d$W, num.trees = 2000, seed = seed, num.threads = 1)
    if (design == "clustered") args$clusters <- d$cluster
    cf <- do.call(causal_forest, args)
    p <- predict(cf, estimate.variance = TRUE)
    ate <- average_treatment_effect(cf, target.sample = "all")
    runs[[as.character(seed)]] <- list(
      tau = p$predictions, var = p$variance.estimates,
      ate = unname(ate["estimate"]), ate_se = unname(ate["std.err"]))
  }
  out[[design]] <- runs
}
write_json(out, file.path(here, "grf_engine_R.json"), digits = NA, auto_unbox = TRUE)
cat("wrote grf_engine_R.json\n")

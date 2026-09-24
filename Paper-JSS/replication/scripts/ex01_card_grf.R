# StatsPAI JSS replication -- Section 4.1 forest reference (Tier 2, needs R).
#
# Fits R grf's causal forest to the same bundled Card bytes that
# sp.datasets.card_1995() loads, with the same five covariates and a
# continuous treatment (years of schooling), and records the average
# partial effect and the spread of the out-of-bag CATE predictions.
# ex01_card.py reads the JSON this writes to report the StatsPAI--grf
# gap. Two independently seeded forests are compared, so the agreement is
# T3 (combined Monte Carlo error), never deterministic parity.
#
#   Rscript Paper-JSS/replication/scripts/ex01_card_grf.R
suppressMessages({
  library(grf)
  library(jsonlite)
})

args <- commandArgs(trailingOnly = FALSE)
script <- normalizePath(sub("^--file=", "", args[grep("^--file=", args)]))
here <- dirname(script)
repo <- normalizePath(file.path(here, "..", "..", ".."))
csv <- file.path(repo, "src", "statspai", "datasets", "data", "card_1995.csv")

d <- read.csv(csv)
X <- as.matrix(d[, c("exper", "expersq", "black", "south", "smsa")])
cf <- causal_forest(X, d$lwage, d$educ, num.trees = 2000, seed = 42)
ate <- average_treatment_effect(cf)
tau <- predict(cf)$predictions

out <- list(
  grf_version = as.character(packageVersion("grf")),
  r_version = paste(R.version$major, R.version$minor, sep = "."),
  data = "src/statspai/datasets/data/card_1995.csv",
  n = nrow(d),
  num_trees = 2000,
  seed = 42,
  ate = unname(ate[["estimate"]]),
  ate_se = unname(ate[["std.err"]]),
  cate_mean = mean(tau),
  cate_sd = sd(tau),
  cate_q25 = unname(quantile(tau, 0.25)),
  cate_q75 = unname(quantile(tau, 0.75))
)
path <- file.path(here, "..", "results", "ex01_card_grf.json")
writeLines(toJSON(out, auto_unbox = TRUE, digits = NA, pretty = TRUE), path)
cat("OK -- wrote", normalizePath(path), "\n")

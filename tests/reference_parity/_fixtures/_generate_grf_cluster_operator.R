#!/usr/bin/env Rscript
# grf inference *operators* with clusters, forest held fixed.
#
# Reads grf_cluster_operator_data.csv (written by the Python companion),
# fits any grf causal_forest on it to obtain a forest object, then replaces
# the object's stored out-of-bag predictions and nuisances with StatsPAI's
# vectors. grf's inference functions read only those fields (predict() with
# no newdata returns object$predictions; get_scores uses Y.hat / W.hat), so
# the outputs below are what grf's formulas give on StatsPAI's inputs.
#
#   Rscript tests/reference_parity/_fixtures/_generate_grf_cluster_operator.R

suppressMessages({
  library(grf)
  library(sandwich)
  library(jsonlite)
})

here <- "tests/reference_parity/_fixtures"
df <- read.csv(file.path(here, "grf_cluster_operator_data.csv"))
X <- as.matrix(df[, c("x1", "x2", "x3")])

inject <- function(equalize) {
  cf <- causal_forest(X, df$Y, df$W, clusters = df$cluster,
                      equalize.cluster.weights = equalize,
                      num.trees = 50, seed = 1)
  cf$Y.hat <- df$Y_hat
  cf$W.hat <- df$W_hat
  cf$predictions <- df$tau_oob
  cf
}

operator_outputs <- function(cf) {
  tc <- test_calibration(cf)
  ate <- lapply(c("all", "treated", "control", "overlap"), function(t) {
    r <- average_treatment_effect(cf, target.sample = t)
    list(target = t, estimate = unname(r["estimate"]), se = unname(r["std.err"]))
  })
  blp <- best_linear_projection(cf, A = X)
  list(
    calibration = list(coef = unname(tc[, 1]), se = unname(tc[, 2]),
                       t = unname(tc[, 3]), p_one_sided = unname(tc[, 4])),
    ate = ate,
    blp = list(coef = unname(blp[, 1]), se = unname(blp[, 2]))
  )
}

cf_plain <- inject(FALSE)
cf_eq <- inject(TRUE)

# sandwich::vcovCL on a weighted lm, all four types, with and without clusters.
fit <- lm(Y ~ W + x1 + x2, data = df, weights = df$vcov_weight)
vc <- list()
for (type in c("HC0", "HC1", "HC2", "HC3")) {
  vc[[paste0(type, "_cluster")]] <- as.vector(vcovCL(fit, cluster = df$cluster, type = type))
  vc[[paste0(type, "_rows")]] <- as.vector(vcovCL(fit, cluster = seq_len(nrow(df)), type = type))
}

out <- list(
  meta = list(R_version = R.version.string,
              grf_version = as.character(packageVersion("grf")),
              sandwich_version = as.character(packageVersion("sandwich"))),
  clusters = operator_outputs(cf_plain),
  clusters_equalized = operator_outputs(cf_eq),
  vcovCL = vc,
  vcovCL_coef = unname(coef(fit))
)
write_json(out, file.path(here, "grf_cluster_operator_R.json"),
           pretty = TRUE, auto_unbox = TRUE, digits = NA)
cat("wrote grf_cluster_operator_R.json\n")

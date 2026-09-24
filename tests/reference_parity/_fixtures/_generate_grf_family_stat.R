#!/usr/bin/env Rscript
# grf GRF-family forests on designs with known truth, three seeds (T3).
# Stores, per design, the seed-averaged predictions and per-seed summary
# metrics (RMSE against the truth, pointwise coverage, median variance,
# doubly-robust average and its standard error).
#
#   Rscript tests/reference_parity/_fixtures/_generate_grf_family_stat.R
suppressMessages({library(grf); library(jsonlite)})
here <- "tests/reference_parity/_fixtures"
df <- read.csv(file.path(here, "grf_family_stat_data.csv"))
seeds <- c(11, 22, 33)
H <- 1.5
out <- list(meta = list(R_version = R.version.string,
                        grf_version = as.character(packageVersion("grf")),
                        num_trees = 2000, seeds = seeds, horizon = H))
xs <- function(d) as.matrix(d[, paste0("x", 1:5)])
rmse <- function(a, b) sqrt(mean((a - b)^2))
cover <- function(p, v, truth) mean(abs(p - truth) <= qnorm(0.975) * sqrt(v))

summ <- function(preds, vars, truth, ate, ate_se) {
  list(rmse = rmse(preds, truth), cover = cover(preds, vars, truth),
       median_var = median(vars), ate = ate, ate_se = ate_se)
}

## IV
d <- df[df$design == "iv", ]; X <- xs(d)
runs <- list(); acc <- 0
for (s in seeds) {
  f <- instrumental_forest(X, d$Y, d$W, d$Z, num.trees = 2000, seed = s)
  p <- predict(f, estimate.variance = TRUE)
  a <- average_treatment_effect(f)
  runs[[as.character(s)]] <- summ(p$predictions, p$variance.estimates, d$tau,
                                  unname(a["estimate"]), unname(a["std.err"]))
  acc <- acc + p$predictions / length(seeds)
}
out$iv <- list(runs = runs, mean_predictions = acc)

## Multi-arm
d <- df[df$design == "multiarm", ]; X <- xs(d)
runs <- list(); acc <- 0
for (s in seeds) {
  f <- multi_arm_causal_forest(X, d$Y, factor(d$W), num.trees = 2000, seed = s)
  p <- predict(f, estimate.variance = TRUE)
  a <- average_treatment_effect(f)
  pr <- p$predictions[, , 1]; vr <- p$variance.estimates
  runs[[as.character(s)]] <- list(
    arm1 = summ(pr[, 1], vr[, 1], d$tau, a[1, "estimate"], a[1, "std.err"]),
    arm2 = summ(pr[, 2], vr[, 2], d$tau2, a[2, "estimate"], a[2, "std.err"]))
  acc <- acc + pr / length(seeds)
}
out$multiarm <- list(runs = runs, mean_predictions = unname(acc))

## lm forest
d <- df[df$design == "lm", ]; X <- xs(d)
runs <- list(); acc <- 0
for (s in seeds) {
  f <- lm_forest(X, d$Y, cbind(d$W, d$W2), num.trees = 2000, seed = s)
  pr <- predict(f)$predictions[, , 1]
  runs[[as.character(s)]] <- list(rmse1 = rmse(pr[, 1], d$tau),
                                  rmse2 = rmse(pr[, 2], d$tau2))
  acc <- acc + pr / length(seeds)
}
out$lm <- list(runs = runs, mean_predictions = unname(acc))

## Causal survival forest
d <- df[df$design == "csf", ]; X <- xs(d)
runs <- list(); acc <- 0
for (s in seeds) {
  f <- causal_survival_forest(X, d$Y, d$W, d$D, horizon = H, target = "RMST",
                              num.trees = 2000, seed = s)
  p <- predict(f, estimate.variance = TRUE)
  a <- average_treatment_effect(f)
  runs[[as.character(s)]] <- summ(p$predictions, p$variance.estimates, d$tau,
                                  unname(a["estimate"]), unname(a["std.err"]))
  acc <- acc + p$predictions / length(seeds)
}
out$csf <- list(runs = runs, mean_predictions = acc)

## Survival forest: S(t | x) at three times
d <- df[df$design == "survival", ]; X <- xs(d)
times <- c(0.25, 0.5, 1.0)
truth <- exp(-outer(d$tau, times))
runs <- list(); acc <- 0
for (s in seeds) {
  f <- survival_forest(X, d$Y, d$D, num.trees = 1000, seed = s)
  cur <- predict(f)$predictions
  ft <- f$failure.times
  at <- sapply(times, function(t) { k <- findInterval(t, ft); if (k == 0) rep(1, nrow(cur)) else cur[, k] })
  runs[[as.character(s)]] <- list(mae = colMeans(abs(at - truth)))
  acc <- acc + at / length(seeds)
}
out$survival <- list(runs = runs, times = times, mean_predictions = unname(acc))

## Quantile forest
d <- df[df$design == "quantile", ]; X <- xs(d)
qs <- c(0.1, 0.5, 0.9)
truth <- outer(d$x1, rep(1, 3)) + outer(d$tau, qnorm(qs))
runs <- list(); acc <- 0
for (s in seeds) {
  f <- quantile_forest(X, d$Y, quantiles = qs, num.trees = 2000, seed = s)
  pr <- predict(f, quantiles = qs)$predictions
  runs[[as.character(s)]] <- list(mae = colMeans(abs(pr - truth)))
  acc <- acc + pr / length(seeds)
}
out$quantile <- list(runs = runs, quantiles = qs, mean_predictions = unname(acc))

write_json(out, file.path(here, "grf_family_stat_R.json"), digits = 10, auto_unbox = TRUE)
cat("wrote grf_family_stat_R.json\n")

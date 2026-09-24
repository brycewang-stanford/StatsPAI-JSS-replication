#!/usr/bin/env Rscript
# grf operator fixture for the GRF-family forests (T2, forest held fixed).
#
# For each forest this exports the inputs its local solve / curve / quantile
# operator consumes (out-of-bag forest weights of rows 1..40, nuisance-
# centred data) and what grf reports (out-of-bag predictions, doubly-robust
# scores, averages, best linear projections, split frequencies and variable
# importance).  The Python tests feed grf's own forest to the StatsPAI
# operators.  Only exported outputs are compared; no grf code is used.
#
#   python tests/reference_parity/_fixtures/_generate_grf_family_data.py
#   Rscript tests/reference_parity/_fixtures/_generate_grf_family.R
suppressMessages({library(grf); library(jsonlite)})
here <- "tests/reference_parity/_fixtures"
df <- read.csv(file.path(here, "grf_family_data.csv"))
K <- 40  # rows whose weights are exported
NT <- 200
out <- list(meta = list(R_version = R.version.string,
                        grf_version = as.character(packageVersion("grf")),
                        num_trees = NT, weight_rows = K))

wts <- function(forest) unname(as.matrix(get_forest_weights(forest))[1:K, , drop = FALSE])
vi <- function(forest) list(split_frequencies = unname(split_frequencies(forest, 4)),
                            importance = as.numeric(variable_importance(forest)))
blp_tab <- function(b) list(coef = unname(b[, 1]), se = unname(b[, 2]))

## Instrumental forest -------------------------------------------------------
d <- df[df$design == "iv", ]
X <- as.matrix(d[, c("x1", "x2", "x3")])
ivf <- instrumental_forest(X, d$Y, d$W, d$Z, num.trees = NT, seed = 7, num.threads = 1)
cf <- causal_forest(X, d$W, d$Z, Y.hat = ivf$W.hat, W.hat = ivf$Z.hat,
                    num.trees = NT, seed = 8, num.threads = 1)
cs <- predict(cf)$predictions
ate <- average_treatment_effect(ivf, compliance.score = cs)
blp <- best_linear_projection(ivf, A = X[, 1:2], compliance.score = cs)
p <- predict(ivf, estimate.variance = TRUE)
out$iv <- c(list(
  Y = d$Y, W = d$W, Z = d$Z,
  Y_hat = ivf$Y.hat, W_hat = ivf$W.hat, Z_hat = ivf$Z.hat,
  predictions = p$predictions, variance = p$variance.estimates,
  weights = wts(ivf), compliance = cs,
  scores = get_scores(ivf, compliance.score = cs),
  ate = unname(ate["estimate"]), ate_se = unname(ate["std.err"]),
  blp = blp_tab(blp)), vi(ivf))

## Multi-arm causal forest and lm forest -------------------------------------
d <- df[df$design == "multiarm", ]
X <- as.matrix(d[, c("x1", "x2", "x3")])
maf <- multi_arm_causal_forest(X, d$Y, factor(d$W), num.trees = NT, seed = 9,
                               num.threads = 1)
pm <- predict(maf, estimate.variance = TRUE)
am <- average_treatment_effect(maf)
out$multiarm <- c(list(
  Y = d$Y, W = d$W, Y_hat = as.numeric(maf$Y.hat), W_hat = unname(maf$W.hat),
  predictions = unname(pm$predictions[, , 1]),
  variance = unname(pm$variance.estimates),
  weights = wts(maf),
  scores = unname(get_scores(maf)[, , 1]),
  ate = unname(am[, "estimate"]), ate_se = unname(am[, "std.err"])), vi(maf))

Wlm <- cbind(d$W2, d$x2)
lmf <- lm_forest(X, d$Y, Wlm, num.trees = NT, seed = 10, num.threads = 1)
out$lm <- c(list(
  Y = d$Y, W = unname(Wlm), Y_hat = as.numeric(lmf$Y.hat), W_hat = unname(lmf$W.hat),
  predictions = unname(predict(lmf)$predictions[, , 1]),
  weights = wts(lmf)), vi(lmf))

## Causal survival forest and survival forest --------------------------------
d <- df[df$design == "survival", ]
X <- as.matrix(d[, c("x1", "x2", "x3")])
h <- 1.5
for (tg in c("RMST", "survival.probability")) {
  csf <- causal_survival_forest(X, d$Y, d$W, d$D, horizon = h, target = tg,
                                num.trees = NT, seed = 11, num.threads = 1)
  ac <- average_treatment_effect(csf)
  bc <- best_linear_projection(csf, A = X[, 1:2])
  out[[paste0("csf_", tg)]] <- c(list(
    Y = d$Y, W = d$W, D = d$D, horizon = h, W_hat = csf$W.hat,
    numerator = csf[["_psi"]]$numerator, denominator = csf[["_psi"]]$denominator,
    predictions = predict(csf)$predictions,
    weights = wts(csf),
    scores = get_scores(csf),
    ate = unname(ac["estimate"]), ate_se = unname(ac["std.err"]),
    blp = blp_tab(bc)), vi(csf))
}
sf <- survival_forest(X, d$Y, d$D, num.trees = NT, seed = 12, num.threads = 1)
out$survival <- c(list(
  Y = d$Y, D = d$D, failure_times = sf$failure.times,
  km = unname(predict(sf, prediction.type = "Kaplan-Meier")$predictions[1:K, ]),
  na = unname(predict(sf, prediction.type = "Nelson-Aalen")$predictions[1:K, ]),
  weights = wts(sf)), vi(sf))

## Quantile, probability and regression forests ------------------------------
d <- df[df$design == "iv", ]
X <- as.matrix(d[, c("x1", "x2", "x3")])
qs <- c(0.1, 0.5, 0.9)
qf <- quantile_forest(X, d$Y, quantiles = qs, num.trees = NT, seed = 13, num.threads = 1)
out$quantile <- c(list(
  Y = d$Y, quantiles = qs,
  predictions = unname(predict(qf, quantiles = qs)$predictions[1:K, ]),
  weights = wts(qf)), vi(qf))
pf <- probability_forest(X, factor(d$W + d$Z), num.trees = NT, seed = 14, num.threads = 1)
out$probability <- c(list(
  classes = d$W + d$Z,
  predictions = unname(predict(pf)$predictions[1:K, ]),
  weights = wts(pf)), vi(pf))
rf <- regression_forest(X, d$Y, num.trees = NT, seed = 15, num.threads = 1)
out$regression <- c(list(
  Y = d$Y, predictions = predict(rf)$predictions[1:K],
  weights = wts(rf)), vi(rf))

write_json(out, file.path(here, "grf_family_R.json"), digits = NA, auto_unbox = TRUE)
cat("wrote grf_family_R.json\n")

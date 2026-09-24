#!/usr/bin/env Rscript
# Panel / DML references for the ml_causal family.
#
#   Rscript tests/reference_parity/_generate_ml_causal_panel_R.R
#
# Writes tests/reference_parity/_fixtures/ml_causal_panel_R.json:
#   * fixest::demean one-way (unit) and two-way (unit + time) residuals of
#     y, d, x1..x3 on the balanced and the unbalanced panel -- the fixed-
#     effect absorption sp.dml_panel performs before cross-fitting;
#   * ddml::ddml_plm on the two-way-demeaned unbalanced panel with an OLS
#     learner, the committed unit-level folds and unit clustering -- a
#     second (R) reference whose inference convention differs from
#     DoubleML's (OLS of y_r on d_r WITH an intercept; sandwich::vcovCL
#     CR1);
#   * ddml::ddml_plm short-stacking over three OLS candidates (all of x1-x3;
#     x1 only; x1-x3 plus squares) with ensemble_type "nnls1" (non-negative
#     weights summing to one) on the cross-sectional stacked data, for
#     sp.dml_model_averaging(weight_rule="short_stacking").

suppressMessages({
  library(fixest)
  library(ddml)
  library(jsonlite)
})

dm <- function(df, fe) {
  vars <- c("y", "d", "x1", "x2", "x3")
  f <- if (fe == "unit") ~ unit else ~ unit + time
  m <- fixest::demean(as.matrix(df[, vars]), f = df[, all.vars(f), drop = FALSE],
                      tol = 1e-14, iter = 100000)
  setNames(lapply(vars, function(v) as.numeric(m[, v])), vars)
}

bal <- read.csv("tests/reference_parity/_fixtures/ml_causal_panel.csv")
unb <- read.csv("tests/reference_parity/_fixtures/ml_causal_panel_unbal.csv")

demeaned <- list(
  balanced_unit = dm(bal, "unit"), balanced_twoway = dm(bal, "twoway"),
  unbal_unit = dm(unb, "unit"), unbal_twoway = dm(unb, "twoway")
)

# ---- ddml PLM on the two-way-demeaned unbalanced panel ------------------
tw <- demeaned$unbal_twoway
Xt <- cbind(tw$x1, tw$x2, tw$x3)
folds <- lapply(sort(unique(unb$fold)), function(k) which(unb$fold == k))
set.seed(1)
fit <- ddml_plm(y = tw$y, D = tw$d, X = Xt, learners = list(what = ols),
                sample_folds = length(folds), subsamples = folds,
                cluster_variable = unb$unit, silent = TRUE)
inf <- summary(fit)
ddml_panel <- list(
  coef = unname(inf["D_r", "Estimate", 1]),
  se = unname(inf["D_r", "Std. Error", 1]),
  n_clusters = length(unique(unb$unit))
)

# ---- ddml short-stacking (cross-section: stacked rows of the balanced panel)
cs <- bal
X3 <- as.matrix(cs[, c("x1", "x2", "x3")])
Xaug <- cbind(X3, X3^2)
learners <- list(
  list(fun = ols, assign_X = 1:3),
  list(fun = ols, assign_X = 1),
  list(fun = ols, assign_X = 1:6)
)
folds_cs <- lapply(0:4, function(k) which(cs$fold == k))
set.seed(1)
ss <- ddml_plm(y = cs$y, D = cs$d, X = Xaug, learners = learners,
               ensemble_type = "nnls1", shortstack = TRUE,
               sample_folds = 5, subsamples = folds_cs, silent = TRUE)
ssinf <- summary(ss, type = "HC1")
shortstack <- list(
  coef = unname(as.numeric(ss$coef)[1]),
  se_HC1 = unname(ssinf["D_r", "Std. Error", 1]),
  weights_y = as.numeric(ss$weights$y_X[, 1]),
  weights_d = as.numeric(ss$weights$D1_X[, 1])
)

out <- list(
  meta = list(R_version = R.version.string,
              fixest_version = as.character(packageVersion("fixest")),
              ddml_version = as.character(packageVersion("ddml")),
              sandwich_version = as.character(packageVersion("sandwich"))),
  demeaned = demeaned,
  ddml_panel = ddml_panel,
  shortstack = shortstack
)
write(toJSON(out, digits = I(17), auto_unbox = TRUE, pretty = TRUE),
      "tests/reference_parity/_fixtures/ml_causal_panel_R.json")
cat("wrote tests/reference_parity/_fixtures/ml_causal_panel_R.json\n")

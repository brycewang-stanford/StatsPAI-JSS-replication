#!/usr/bin/env Rscript
# Reference numbers for the ml_causal parity family (grf post-fit
# operators and the CDDF BLP / GATES regressions).
#
#   python tests/reference_parity/_fixtures/_generate_ml_causal_data.py
#   Rscript tests/reference_parity/_generate_ml_causal_R.R
#
# Writes tests/reference_parity/_fixtures/ml_causal_R.json.
#
# Design: the forest is the only stochastic factor. It is grown once,
# here, and its outputs (OOB tau.hat, Y.hat, W.hat) are written to the
# fixture. Every quantity below is a deterministic function of those
# outputs and the data, so StatsPAI fed the same outputs must reproduce
# each one to the floating-point floor. The only exceptions are grf's
# RATE standard errors, which come from a half-sample bootstrap and are
# recorded for a Monte Carlo comparison, not a pin.

suppressMessages({
  library(grf)
  library(GenericML)
  library(jsonlite)
  library(sandwich)
  library(lmtest)
})

df <- read.csv("tests/reference_parity/_fixtures/ml_causal_cate.csv")
X <- as.matrix(df[, paste0("x", 1:5)])
Y <- df$y
W <- df$w
n <- nrow(df)

cf <- causal_forest(X, Y, W, num.trees = 2000, seed = 42)
tau_hat <- as.numeric(predict(cf)$predictions)
y_hat <- as.numeric(cf$Y.hat)
w_hat <- as.numeric(cf$W.hat)
dr_scores <- as.numeric(get_scores(cf))

ate <- function(target) {
  r <- average_treatment_effect(cf, target.sample = target)
  list(estimate = unname(r[["estimate"]]), se = unname(r[["std.err"]]))
}

calib <- function(vcov_type) {
  tc <- test_calibration(cf, vcov.type = vcov_type)
  list(
    coef = unname(tc[, 1]), se = unname(tc[, 2]),
    t = unname(tc[, 3]), p_one_sided = unname(tc[, 4]),
    rows = rownames(tc)
  )
}

rate_forest <- function(target, priorities, R, seed) {
  set.seed(seed)
  r <- rank_average_treatment_effect(cf, priorities, target = target, R = R)
  list(
    estimate = unname(r$estimate), se = unname(r$std.err),
    toc_q = r$TOC$q, toc_estimate = r$TOC$estimate, R = R, seed = seed
  )
}

rate_fit <- function(target, priorities) {
  # R = 0: the operator only; std.err is set to 0 by grf when R < 2.
  r <- rank_average_treatment_effect.fit(dr_scores, priorities,
                                         target = target, R = 0)
  list(estimate = unname(r$estimate), toc_q = r$TOC$q,
       toc_estimate = r$TOC$estimate)
}

prio_ties <- round(tau_hat, 1)

# ---- CDDF BLP / GATES (GenericML), identical proxies --------------------
# Proxies are grf's own forest outputs; the point is the regression
# operator, not proxy quality.
prop <- w_hat
bca <- y_hat - w_hat * tau_hat   # E[Y | X, W = 0] implied by the forest
cate_proxy <- tau_hat

blp_one <- function(funs_Z, vcov) {
  b <- GenericML::BLP(Y, W, prop, bca, cate_proxy,
                      X1_control = setup_X1(funs_Z = funs_Z),
                      vcov_control = vcov)
  gt <- b$generic_targets
  list(beta = unname(gt[, "Estimate"]), se = unname(gt[, "Std. Error"]),
       z = unname(gt[, "z value"]), p_left = unname(gt[, "Pr(<z)"]),
       p_right = unname(gt[, "Pr(>z)"]), ci_lo = unname(gt[, "CB lower"]),
       ci_up = unname(gt[, "CB upper"]))
}

memb <- quantile_group(cate_proxy, cutoffs = c(0.25, 0.5, 0.75))
gates_one <- function(funs_Z, vcov) {
  g <- GenericML::GATES(Y, W, prop, bca, cate_proxy, membership = memb,
                        X1_control = setup_X1(funs_Z = funs_Z),
                        vcov_control = vcov, monotonize = FALSE)
  gt <- g$generic_targets
  list(rows = rownames(gt), estimate = unname(gt[, "Estimate"]),
       se = unname(gt[, "Std. Error"]), z = unname(gt[, "z value"]),
       p_right = unname(gt[, "Pr(>z)"]))
}

vc_const <- setup_vcov()                                     # GenericML default
vc_hc1 <- setup_vcov(estimator = "vcovHC", arguments = list(type = "HC1"))

out <- list(
  meta = list(
    R_version = R.version.string,
    grf_version = as.character(packageVersion("grf")),
    GenericML_version = as.character(packageVersion("GenericML")),
    sandwich_version = as.character(packageVersion("sandwich")),
    num_trees = 2000L, seed = 42L, n = n
  ),
  tau_hat = tau_hat, y_hat = y_hat, w_hat = w_hat, dr_scores = dr_scores,
  ate = list(all = ate("all"), treated = ate("treated"),
             control = ate("control"), overlap = ate("overlap")),
  calibration = list(HC3 = calib("HC3"), HC1 = calib("HC1")),
  rate = list(
    autoc = rate_forest("AUTOC", tau_hat, 200L, 1L),
    qini = rate_forest("QINI", tau_hat, 200L, 1L),
    autoc_R2000 = rate_forest("AUTOC", tau_hat, 2000L, 2L),
    qini_R2000 = rate_forest("QINI", tau_hat, 2000L, 2L),
    fit_autoc_ties = rate_fit("AUTOC", prio_ties),
    fit_qini_ties = rate_fit("QINI", prio_ties),
    n_distinct_ties = length(unique(prio_ties))
  ),
  generic_ml = list(
    membership = apply(memb, 1, which),
    blp_B_const = blp_one("B", vc_const),
    blp_B_hc1 = blp_one("B", vc_hc1),
    blp_none_hc1 = blp_one(character(0), vc_hc1),
    gates_B_const = gates_one("B", vc_const),
    gates_B_hc1 = gates_one("B", vc_hc1)
  )
)

write(toJSON(out, digits = I(17), auto_unbox = TRUE, pretty = TRUE),
      "tests/reference_parity/_fixtures/ml_causal_R.json")
cat("wrote tests/reference_parity/_fixtures/ml_causal_R.json\n")

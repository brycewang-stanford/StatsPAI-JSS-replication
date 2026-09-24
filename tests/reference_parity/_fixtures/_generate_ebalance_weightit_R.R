# Reference values for sp.ebalance's ATT standard error vs R WeightIt.
#
# WeightIt::weightit(method = "ebal", estimand = "ATT") solves the same
# entropy-balancing problem as sp.ebalance (unique solution); its
# lm_weightit(y ~ d, vcov = "asympt") reports the M-estimation sandwich
# that stacks the balancing conditions with the outcome model, so the
# uncertainty from estimating the weights is propagated. That is the
# quantity sp.ebalance(vce = "mestimation") computes.
#
# Cases: two simulated selection-on-observables designs (the Track B
# coverage DGP and a heteroskedastic one) and the public MatchIt::lalonde
# extract (NSW treated + PSID controls), each at moments = 1, 2, 3.
suppressPackageStartupMessages({ library(WeightIt); library(MatchIt); library(jsonlite) })

set.seed(20260924)
n <- 500
X1 <- rnorm(n); X2 <- rnorm(n)
d <- as.integer(runif(n) < plogis(-0.3 + 0.5 * X1 - 0.3 * X2))
sim_cia <- data.frame(y = 1 + 1.5 * X1 - 0.8 * X2 + 2 * d + rnorm(n, sd = 0.8),
                      d = d, X1 = X1, X2 = X2)
X1 <- rnorm(n); X2 <- rexp(n)
d <- as.integer(runif(n) < plogis(-0.5 + 0.8 * X1 + 0.4 * X2))
sim_het <- data.frame(y = X1 + X2^1.5 + (1 + 0.5 * X1) * d + rnorm(n, sd = 0.5 + 0.5 * abs(X1)),
                      d = d, X1 = X1, X2 = X2)
data("lalonde", package = "MatchIt")
lal <- data.frame(y = lalonde$re78, d = lalonde$treat, age = lalonde$age,
                  educ = lalonde$educ, black = as.integer(lalonde$race == "black"),
                  hispan = as.integer(lalonde$race == "hispan"),
                  married = lalonde$married, nodegree = lalonde$nodegree,
                  re74 = lalonde$re74, re75 = lalonde$re75)
write.csv(sim_cia, "ebalance_sim_cia.csv", row.names = FALSE)
write.csv(sim_het, "ebalance_sim_het.csv", row.names = FALSE)
write.csv(lal, "ebalance_lalonde.csv", row.names = FALSE)

cases <- list(sim_cia = list(df = sim_cia, x = c("X1", "X2")),
              sim_het = list(df = sim_het, x = c("X1", "X2")),
              lalonde = list(df = lal, x = c("age", "educ", "black", "hispan",
                                              "married", "nodegree", "re74", "re75")))
out <- list()
for (nm in names(cases)) {
  cs <- cases[[nm]]
  for (mo in 1:3) {
    if (nm == "lalonde" && mo > 1) {
      # squares/cubes of binary indicators duplicate them; balance the
      # continuous covariates' higher moments only, as sp.ebalance would
      # reject the duplicated constraints.
      next
    }
    f <- as.formula(paste("d ~", paste(cs$x, collapse = " + ")))
    W <- weightit(f, data = cs$df, method = "ebal", estimand = "ATT", moments = mo)
    fit <- lm_weightit(y ~ d, data = cs$df, weightit = W, vcov = "asympt")
    out[[paste0(nm, "_m", mo)]] <- list(
      data = paste0("ebalance_", nm, ".csv"), covariates = cs$x, moments = mo,
      att = unname(coef(fit)["d"]), se = unname(sqrt(diag(vcov(fit)))["d"]))
  }
}
out$`_provenance` <- list(WeightIt = as.character(packageVersion("WeightIt")),
                          MatchIt = as.character(packageVersion("MatchIt")),
                          R = R.version.string, vcov = "asympt")
writeLines(toJSON(out, digits = NA, auto_unbox = TRUE, pretty = TRUE),
           "ebalance_weightit_R.json")

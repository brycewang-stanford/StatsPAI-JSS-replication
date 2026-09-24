# 2SLS on the original Card (1995) NLSYM extract vs R AER::ivreg + sandwich.
# Fills the configuration gap found by sp.validation_scope: Track A module 02
# pins 2SLS with HC1 errors, but sp.iv's default is the classical 2SLS
# covariance (the one printed in the JSS Card listing). Cases: classical,
# HC1 and CR1 (clustered on a deterministic id, row index mod 50, added to the
# CSV) for the just-identified (nearc4) and over-identified (nearc4 + nearc2)
# models, plus the Sargan statistic of the over-identified fit.
suppressPackageStartupMessages({ library(AER); library(sandwich); library(jsonlite) })
df <- read.csv("iv_card.csv")
X <- "exper + expersq + black + south + smsa"
out <- list()
for (inst in c("nearc4", "nearc4 + nearc2")) {
  f <- as.formula(paste("lwage ~ educ +", X, "|", X, "+", inst))
  fit <- ivreg(f, data = df)
  key <- if (inst == "nearc4") "just" else "over"
  se <- function(V) unname(sqrt(diag(V))["educ"])
  out[[key]] <- list(
    instruments = inst,
    beta = unname(coef(fit)["educ"]),
    se_classical = se(vcov(fit)),
    se_hc1 = se(vcovHC(fit, type = "HC1")),
    se_cr1 = se(vcovCL(fit, cluster = ~cl, type = "HC1")),
    sargan = if (key == "over") unname(summary(fit, diagnostics = TRUE)$diagnostics["Sargan", "statistic"]) else NULL
  )
}
out$`_provenance` <- list(AER = as.character(packageVersion("AER")),
                          sandwich = as.character(packageVersion("sandwich")),
                          R = R.version.string)
writeLines(toJSON(out, digits = NA, auto_unbox = TRUE, pretty = TRUE), "iv_card_R.json")

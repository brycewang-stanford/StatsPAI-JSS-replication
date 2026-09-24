#!/usr/bin/env Rscript
# grf's causal-survival score map evaluated on fixed nuisance curves (T2).
# grf's internal compute_psi / expected_survival are called as black boxes
# on csf_psi_inputs.json; only their outputs are stored.
#
#   Rscript tests/reference_parity/_fixtures/_generate_csf_psi.R
suppressMessages({library(grf); library(jsonlite)})
here <- "tests/reference_parity/_fixtures"
inp <- fromJSON(file.path(here, "csf_psi_inputs.json"))
h <- inp$horizon; Y <- inp$Y; D <- inp$D; W <- inp$W; e <- inp$e; G <- inp$grid
S1 <- inp$S1; S0 <- inp$S0; C <- inp$C
S <- S1 * W + S0 * (1 - W)
Dh <- D; Dh[Y >= h] <- 1
idx <- findInterval(pmin(Y, h), G)
CY <- cbind(1, C)[cbind(seq_along(Y), idx + 1)]
out <- list(meta = list(grf_version = as.character(packageVersion("grf"))))
mu1 <- grf:::expected_survival(S1, G)
mu0 <- grf:::expected_survival(S0, G)
out$RMST <- list(mu1 = mu1, mu0 = mu0)
out$survival_probability <- list(mu1 = S1[, ncol(S1)], mu0 = S0[, ncol(S0)])
for (tg in c("RMST", "survival_probability")) {
  m <- e * out[[tg]]$mu1 + (1 - e) * out[[tg]]$mu0
  fY <- if (tg == "RMST") pmin(Y, h) else as.numeric(Y > h)
  ps <- grf:::compute_psi(S, C, CY, m, W - e, Dh, fY, idx, G,
                          if (tg == "RMST") "RMST" else "survival.probability", h)
  out[[tg]]$numerator <- ps$numerator
  out[[tg]]$denominator <- ps$denominator
}
write_json(out, file.path(here, "csf_psi_R.json"), digits = NA, auto_unbox = TRUE)
cat("wrote csf_psi_R.json\n")

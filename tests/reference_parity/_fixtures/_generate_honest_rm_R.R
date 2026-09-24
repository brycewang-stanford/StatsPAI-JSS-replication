# Reference values for the native relative-magnitudes Honest-DiD confidence
# set (statspai.did._arp) vs R HonestDiD 0.2.8
# (Rambachan & Roth 2023; Andrews, Roth & Pakes 2023).
#
# HonestDiD reports the smallest and largest accepted point of a 1,000-point
# theta grid, so a correct port agrees *exactly* whenever every grid decision
# agrees. The cases are chosen so a mismatch localises:
#   diag33     3 pre / 3 post, diagonal Sigma (Track A module 21's input)
#   corr33     3 pre / 3 post, correlated Sigma (did_synth_honest_es.csv, the
#              FLCI fixture of test_did_synth_R_parity.py)
#   corr42     4 pre / 2 post, AR(1)-type Sigma, target = mean of post
#              periods (a non-basis l_vec exercises the Gamma change of basis)
#   nonuis21   2 pre / 1 post: the no-nuisance test path (.APR_computeCI_NoNuis)
# Both "Conditional" (no simulation: exact target) and "C-LF" (HonestDiD's
# default; its least-favourable critical value is simulated with R's RNG, so
# the native value can differ by Monte Carlo error) are recorded.
suppressPackageStartupMessages({ library(HonestDiD); library(jsonlite) })

es <- read.csv("did_synth_honest_es.csv")
S6 <- as.matrix(es[, paste0("s", 0:5)])

ar1 <- function(n, rho, sd) { m <- outer(1:n, 1:n, function(i, j) rho^abs(i - j)); m * outer(sd, sd) }

cases <- list(
  diag33 = list(b = c(0.01, -0.02, 0.0, 0.5, 0.4, 0.3),
                S = diag(c(.05, .05, .05, .1, .1, .1)^2), npre = 3, npost = 3,
                l = c(1, 0, 0)),
  corr33 = list(b = es$betahat, S = S6, npre = 3, npost = 3, l = c(0, 1, 0)),
  corr42 = list(b = c(0.03, -0.01, 0.02, -0.015, 0.2, 0.25),
                S = ar1(6, 0.5, c(.02, .02, .02, .02, .05, .06)), npre = 4, npost = 2,
                l = c(0.5, 0.5)),
  nonuis21 = list(b = c(-0.02, 0.01, 0.15), S = ar1(3, 0.3, c(.03, .03, .06)),
                  npre = 2, npost = 1, l = 1)
)
MBAR <- c(0, 0.5, 1, 2)

out <- list()
for (nm in names(cases)) {
  cs <- cases[[nm]]
  for (meth in c("Conditional", "C-LF")) {
    r <- suppressWarnings(createSensitivityResults_relativeMagnitudes(
      betahat = cs$b, sigma = cs$S, numPrePeriods = cs$npre, numPostPeriods = cs$npost,
      Mbarvec = MBAR, method = meth, l_vec = cs$l, alpha = 0.05))
    out[[paste(nm, meth, sep = "|")]] <- list(
      betahat = cs$b, sigma = unname(cs$S), npre = cs$npre, npost = cs$npost,
      l_vec = cs$l, method = meth, Mbar = MBAR, lb = r$lb, ub = r$ub)
  }
}
out$`_provenance` <- list(HonestDiD = as.character(packageVersion("HonestDiD")),
                          R = R.version.string)
writeLines(toJSON(out, digits = NA, auto_unbox = TRUE, pretty = TRUE), "honest_rm_R.json")

# StatsPAI Honest-DiD parity (R side) -- Module 10.
#
# Mirrors the hand-crafted event study used by 10_honest_did.py, whose
# Python side runs the *native* StatsPAI FLCI (no R call). Three
# references are written so every gap has a named mechanism:
#
#   ci_*_M_*           HonestDiD::createSensitivityResults(method = "FLCI")
#                      with HonestDiD's internal .qfoldednormal replaced by
#                      the exact quantile (root of the folded-normal CDF).
#                      Like-for-like with the native solver; the headline
#                      rows for M > 0.
#   shipped_ci_*_M_*   HonestDiD as shipped. Its folded-normal quantile is
#                      simulated (1e6 draws, seed 0): ~3e-4 from exact.
#   analytic_ci_*_M_0  Closed form at M = 0, computed here with base linear
#                      algebra and no HonestDiD call: under Delta^SD(0) the
#                      violation is linear, the worst-case bias is zero, and
#                      the FLCI is the GLS linear extrapolation
#                      beta_post[1] - s_hat plus/minus z_{0.975} sd. It
#                      adjudicates the M = 0 gap between the two solvers.

.args <- commandArgs(trailingOnly = FALSE)
.file_arg <- grep("^--file=", .args, value = TRUE)
.script_dir <- if (length(.file_arg) > 0) {
  dirname(normalizePath(sub("^--file=", "", .file_arg[1])))
} else {
  getwd()
}
source(file.path(.script_dir, "_common.R"))

suppressPackageStartupMessages({
  library(HonestDiD)
})

MODULE <- "10_honest_did"
M_GRID <- c(0.0, 0.05, 0.1, 0.2, 0.5)

#   pre  rel-time {-3,-2,-1} : att = (0.01, -0.02, 0.0), SE = 0.05
#   post rel-time { 0, 1, 2} : att = (0.5,   0.4,   0.3), SE = 0.10
betahat <- c(0.01, -0.02, 0.0,   0.5, 0.4, 0.3)
ses     <- c(0.05, 0.05,  0.05,  0.10, 0.10, 0.10)
sigma   <- diag(ses^2)

run_flci <- function() {
  # Suppress the cone-solver "may be inaccurate" warnings that come
  # from the small synthetic example.
  suppressWarnings(
    HonestDiD::createSensitivityResults(
      betahat = betahat,
      sigma   = sigma,
      numPrePeriods  = 3,
      numPostPeriods = 3,
      Mvec    = M_GRID,
      method  = "FLCI",
      alpha   = 0.05
    )
  )
}

rows <- list()
emit <- function(prefix, m, lb, ub) {
  rows[[length(rows) + 1L]] <<- parity_row(
    module = MODULE, statistic = sprintf("%sci_lower_M_%g", prefix, m),
    estimate = lb, n = 1000
  )
  rows[[length(rows) + 1L]] <<- parity_row(
    module = MODULE, statistic = sprintf("%sci_upper_M_%g", prefix, m),
    estimate = ub, n = 1000
  )
}

# (1) HonestDiD as shipped.
sens <- run_flci()
for (i in seq_along(M_GRID)) emit("shipped_", M_GRID[i], sens$lb[i], sens$ub[i])

# (2) HonestDiD with the exact folded-normal quantile.
exact_qfoldednormal <- function(p, mu = 0, sd = 1, numSims = 10^6, seed = 0) {
  vapply(mu, function(m) {
    m <- abs(m)
    stats::uniroot(
      function(q) stats::pnorm((q - m) / sd) - stats::pnorm((-q - m) / sd) - p,
      c(0, m + 20 * sd), tol = 1e-14
    )$root
  }, numeric(1))
}
shipped_qfoldednormal <- get(".qfoldednormal", envir = asNamespace("HonestDiD"))
assignInNamespace(".qfoldednormal", exact_qfoldednormal, ns = "HonestDiD")
sens_exact <- run_flci()
assignInNamespace(".qfoldednormal", shipped_qfoldednormal, ns = "HonestDiD")
for (i in seq_along(M_GRID)) emit("", M_GRID[i], sens_exact$lb[i], sens_exact$ub[i])

# (3) Closed form at M = 0: GLS slope through the omitted reference period.
t_pre   <- c(-3, -2, -1)
S_pre   <- sigma[1:3, 1:3]
Si      <- solve(S_pre)
s_hat   <- drop(solve(t(t_pre) %*% Si %*% t_pre) %*% t(t_pre) %*% Si %*% betahat[1:3])
var_s   <- drop(solve(t(t_pre) %*% Si %*% t_pre))
theta   <- betahat[4] - 1 * s_hat          # first post period sits at t = +1
sd_th   <- sqrt(sigma[4, 4] + 1^2 * var_s)  # pre/post independent here
z       <- stats::qnorm(0.975)
emit("analytic_", 0, theta - z * sd_th, theta + z * sd_th)

write_results(MODULE, rows,
              extra = list(method = "FLCI", alpha = 0.05,
                           references = c("shipped", "exact_quantile",
                                          "closed_form_M0")))

#!/usr/bin/env Rscript
# R reference for tests/reference_parity/test_r2_postest_parity.py (secondary
# to the Stata fixture r2_postest_stata.json).
#
# Pins two conventions that Stata does not cover:
#   * emmeans pairwise comparisons with adjust = "holm" (Stata's pwcompare /
#     margins, mcompare() has no Holm option): p-values follow p.adjust("holm")
#     on t(df.residual) p-values; the confidence intervals of a Holm family
#     fall back to Bonferroni (emmeans prints the note).
#   * marginaleffects::avg_predictions defaults to the normal distribution
#     even after lm(); with df = df.residual it reproduces Stata's t(df_r).
#
# Regenerate (from the repo root, after _generate_r2_postest_data.py):
#   Rscript tests/reference_parity/_generate_r2_postest_R.R
suppressPackageStartupMessages({
  library(jsonlite); library(emmeans); library(marginaleffects)
})
d <- read.csv("tests/reference_parity/_fixtures/r2_postest_data.csv")
d$g <- factor(d$g)
m <- lm(yl ~ g + x + z, data = d)

pw <- function(adjust) {
  ct <- pairs(emmeans(m, ~ g), reverse = TRUE, adjust = adjust)
  s <- summary(ct, infer = c(TRUE, TRUE), adjust = adjust)
  list(contrast = as.character(s$contrast), estimate = s$estimate,
       se = s$SE, df = s$df, p = s$p.value,
       lower = s$lower.CL, upper = s$upper.CL)
}

ap <- function(df) {
  a <- if (is.null(df)) {
    avg_predictions(m, variables = list(x = c(-1, 0, 1.5)),
                    numderiv = "richardson")
  } else {
    avg_predictions(m, variables = list(x = c(-1, 0, 1.5)), df = df,
                    numderiv = "richardson")
  }
  list(x = a$x, estimate = a$estimate, se = a$std.error, p = a$p.value,
       lower = a$conf.low, upper = a$conf.high)
}

out <- list(
  emmeans_pairs = list(none = pw("none"), holm = pw("holm"),
                       bonferroni = pw("bonferroni"), sidak = pw("sidak")),
  avg_predictions_default = ap(NULL),
  avg_predictions_df = ap(df.residual(m)),
  df_residual = df.residual(m),
  provenance = list(
    r_version = R.version.string,
    emmeans_version = as.character(packageVersion("emmeans")),
    marginaleffects_version = as.character(packageVersion("marginaleffects")),
    generated_by = "tests/reference_parity/_generate_r2_postest_R.R"
  )
)
writeLines(toJSON(out, auto_unbox = TRUE, digits = I(17), pretty = TRUE),
           "tests/reference_parity/_fixtures/r2_postest_R.json")
cat("wrote r2_postest_R.json\n")

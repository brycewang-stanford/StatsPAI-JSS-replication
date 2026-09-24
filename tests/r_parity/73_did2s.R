# StatsPAI Gardner two-stage DiD parity (R side) -- Module 73.
#
# Reads data/73_did2s.csv (the StatsPAI mpdta replica) and runs
# did2s::did2s with a two-way FE first stage and a static treatment
# indicator in the second stage.
#
# Tolerance: rel < 1e-6 on the point estimate and on the SE. did2s reports
# the corrected clustered variance of Gardner (2022), which propagates
# first-stage estimation error into the second-stage sandwich with no
# small-sample cluster factor; sp.gardner_did's default vce='analytic'
# builds the same two-stage influence function, so the SE row is a strict
# parity assertion (observed rel 2.7e-10; the residual is fixest's
# iterative-demeaning tolerance in the first stage, which also shows in
# the 4.8e-8 point-estimate gap -- Stata's exact first stage lands on the
# Python SE at 1e-14).

.args <- commandArgs(trailingOnly = FALSE)
.file_arg <- grep("^--file=", .args, value = TRUE)
.script_dir <- if (length(.file_arg) > 0) {
  dirname(normalizePath(sub("^--file=", "", .file_arg[1])))
} else {
  getwd()
}
source(file.path(.script_dir, "_common.R"))

suppressPackageStartupMessages({
  library(did2s)
})

MODULE <- "73_did2s"

df <- read_csv_strict(MODULE)
df$first_treat <- as.numeric(df$first_treat)
# Time-varying treatment status implied by the cohort column.
df$dpost <- as.integer(df$first_treat > 0 & df$year >= df$first_treat)

fit <- did2s::did2s(
  df,
  yname        = "lemp",
  first_stage  = ~ 0 | countyreal + year,
  second_stage = ~ i(dpost, ref = FALSE),
  treatment    = "dpost",
  cluster_var  = "countyreal"
)

co <- coef(fit)
se <- sqrt(diag(vcov(fit)))

rows <- list(
  parity_row(
    module    = MODULE,
    statistic = "static_ATT",
    estimate  = unname(co[1]),
    se        = unname(se[1]),
    n         = nrow(df)
  )
)

write_results(MODULE, rows, extra = list(
  package = "did2s",
  version = as.character(utils::packageVersion("did2s"))
))

# Reference for sp.sun_abraham's default overall aggregate.
#
# sp.sun_abraham(aggregation="event_time") reports the equal-weighted
# average of the post-treatment (e >= 0) interaction-weighted event-time
# effects. fixest has no built-in summary with these weights, so the
# reference is the same linear combination of fixest's own event-time
# coefficients: w = 1/|E+| on each post-period coefficient of
#   feols(lemp ~ sunab(first_treat, year) | countyreal + year,
#         cluster = ~countyreal)
# on Track A module 05's CSV bytes, with SE sqrt(w' V w) from fixest's
# vcov (cohort shares treated as fixed, fixest's convention).
#
# Run from the repository root:
#   Rscript tests/reference_parity/_fixtures/_generate_sunab_event_time_R.R
suppressPackageStartupMessages({
  library(fixest)
  library(jsonlite)
})

df <- read.csv("tests/r_parity/data/05_sunab.csv")
df$first_treat <- as.numeric(df$first_treat)
fit <- feols(lemp ~ sunab(first_treat, year) | countyreal + year,
             data = df, cluster = ~countyreal)
# fixest reports the per-relative-period coefficients but exposes only the
# full cohort-by-period covariance. Rebuild the aggregation map A (weights
# proportional to each cohort's observation count at that relative period,
# fixest's documented sunab aggregation), and require that it reproduces
# fixest's own aggregated coefficients and standard errors before using it.
b_full <- coef(fit, agg = FALSE)
V_full <- vcov(fit)[names(b_full), names(b_full)]
cell_rel <- as.integer(sub("^year::(-?\\d+):cohort::.*$", "\\1", names(b_full)))
cell_coh <- as.numeric(sub("^.*:cohort::(\\d+)$", "\\1", names(b_full)))
n_cell <- mapply(function(g, e) sum(df$first_treat == g & df$year - g == e),
                 cell_coh, cell_rel)
b_agg <- coef(fit)
rel <- as.integer(sub("^year::(-?\\d+)$", "\\1", names(b_agg)))
A <- t(sapply(rel, function(e) {
  on <- cell_rel == e
  out <- rep(0, length(b_full))
  out[on] <- n_cell[on] / sum(n_cell[on])
  out
}))
stopifnot(max(abs(A %*% b_full - b_agg)) < 1e-12)
stopifnot(max(abs(sqrt(diag(A %*% V_full %*% t(A))) - se(fit)) / se(fit)) < 1e-10)
V_agg <- A %*% V_full %*% t(A)
post <- which(rel >= 0)
w <- rep(0, length(b_agg))
w[post] <- 1 / length(post)
b <- b_agg
V <- V_agg
out <- list(
  att_event_time = sum(w * b),
  se_event_time = sqrt(as.numeric(t(w) %*% V %*% w)),
  post_event_times = rel[post],
  n = nrow(df),
  fixest = as.character(packageVersion("fixest")),
  r_version = R.version.string
)
write_json(out, "tests/reference_parity/_fixtures/sunab_event_time_R.json",
           digits = NA, auto_unbox = TRUE, pretty = TRUE)

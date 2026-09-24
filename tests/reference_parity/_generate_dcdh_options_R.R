# Reference values for tests/reference_parity/test_dcdh_options_parity.py.
#
#   sp.did_multiplegt_dyn(controls=, trends_nonparam=, normalized=)
#     vs DIDmultiplegtDYN::did_multiplegt_dyn 2.3.4 (de Chaisemartin &
#     D'Haultfoeuille), on the same CSV bytes.
#
# Regenerate (from the repository root):
#   python  tests/reference_parity/_generate_dcdh_options_data.py
#   Rscript tests/reference_parity/_generate_dcdh_options_R.R \
#           tests/reference_parity/_fixtures/dcdh_options_panel.csv out.json
#
# Environment note: DIDmultiplegtDYN needs rgl (headless: rgl.useNULL) and
# is much faster with polars loaded; trends_lin additionally caps the number
# of placebos, which is why it takes its own placebo count below.
#
# The printed values are pasted into the test as R_REFERENCE; the test then
# compares at rtol 1e-12, because these are the same estimators on the same
# bytes rather than two implementations of one estimand.

options(rgl.useNULL = TRUE)
suppressPackageStartupMessages({ library(polars); library(DIDmultiplegtDYN); library(jsonlite) })
df <- read.csv(commandArgs(trailingOnly = TRUE)[1])
out <- list()
grab <- function(r) {
  e <- r$results$Effects
  p <- if (!is.null(r$results$Placebos)) r$results$Placebos else NULL
  list(effects = as.numeric(e[, "Estimate"]),
       effect_se = as.numeric(e[, "SE"]),
       n_switchers = as.numeric(e[, "Switchers"]),
       placebos = if (is.null(p)) NULL else as.numeric(p[, "Estimate"]),
       ate = as.numeric(r$results$ATE[1, "Estimate"]))
}
run <- function(label, npl = 2, ...) {
  r <- try(did_multiplegt_dyn(df = df, outcome = "y", group = "id", time = "t",
                              treatment = "d", effects = 4, placebo = npl,
                              graph_off = TRUE, ...), silent = TRUE)
  if (inherits(r, "try-error")) { cat("FAILED", label, "\n"); return(invisible()) }
  out[[label]] <<- grab(r)
  cat("ok", label, "\n")
}
run("plain")
run("controls", controls = c("x1", "x2"))
run("trends_lin", npl = 1, trends_lin = TRUE)
run("trends_nonparam", trends_nonparam = c("reg"))
run("normalized", normalized = TRUE)

# The companion panel for continuous=: every group's period-one treatment is
# distinct, so the baseline match is impossible and the polynomial replaces it.
cont <- read.csv(file.path(dirname(commandArgs(trailingOnly = TRUE)[1]),
                           "dcdh_continuous_panel.csv"))
for (k in c(1, 2)) {
  r <- did_multiplegt_dyn(df = cont, outcome = "y", group = "id", time = "t",
                          treatment = "d", effects = 3, placebo = 1,
                          graph_off = TRUE, continuous = k)
  e <- r$results$Effects
  out[[paste0("continuous", k)]] <- list(effects = as.numeric(e[, "Estimate"]))
  cat("ok continuous", k, "\n")
}

write(toJSON(out, digits = 15, auto_unbox = TRUE, null = "null"),
      commandArgs(trailingOnly = TRUE)[2])
cat("written\n")

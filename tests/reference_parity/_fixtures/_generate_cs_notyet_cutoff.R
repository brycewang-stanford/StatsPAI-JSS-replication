#!/usr/bin/env Rscript
# R did::att_gt with control_group = "notyettreated" across base periods,
# anticipation and covariates, panel and repeated cross-section paths.
#
#   Rscript tests/reference_parity/_fixtures/_generate_cs_notyet_cutoff.R
suppressMessages({library(did); library(jsonlite)})
here <- "tests/reference_parity/_fixtures"
df <- read.csv(file.path(here, "cs_notyet_cutoff_data.csv"))
df$g <- as.numeric(df$g)
df$t <- as.numeric(df$t)
cases <- list()
for (panel in c(TRUE, FALSE)) for (base in c("universal", "varying"))
  for (ant in c(0, 1)) for (xf in c("~1", "~x1")) {
    r <- suppressWarnings(att_gt(
      yname = "y", tname = "t", idname = "id", gname = "g",
      xformla = as.formula(xf), data = df, panel = panel,
      control_group = "notyettreated", base_period = base,
      anticipation = ant, bstrap = FALSE, est_method = "dr"))
    keep <- !(is.na(r$se))
    cases[[length(cases) + 1]] <- list(
      panel = panel, base_period = base, anticipation = ant,
      covariates = xf != "~1",
      group = r$group[keep], time = r$t[keep],
      att = r$att[keep], se = r$se[keep])
  }
write_json(list(meta = list(R_version = R.version.string,
                            did_version = as.character(packageVersion("did"))),
                cases = cases),
           file.path(here, "cs_notyet_cutoff_R.json"), digits = NA, auto_unbox = TRUE)
cat("wrote cs_notyet_cutoff_R.json\n")

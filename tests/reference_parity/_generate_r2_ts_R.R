# ---------------------------------------------------------------------------
# Round-2 R reference for tests/reference_parity/test_r2_ts_parity.py.
#
# Reads _fixtures/ts_break.csv (round 1) and _fixtures/r2_ts_break.csv
# (written by _fixtures/_generate_r2_ts_data.py) and writes
# _fixtures/r2_ts_R.json (digits = 17). Run from the repository root:
#
#   Rscript tests/reference_parity/_generate_r2_ts_R.R
#
# * strucchange: Fstats + sctest(type = "supF") and the p-value function
#   pvalue.Fstats on a grid. Its coefficient table sc.beta.sup is Hansen's
#   (1997) table; it equals the table in Hansen's own pv_sup.R
#   (users.ssc.wisc.edu/~bhansen/progs/jbes_97.html) entry for entry.
# * mbreaks (Nguyen, Yamamoto & Perron; MIT): dosequa, the Bai-Perron
#   sequential procedure, with prewhit = 0, robust = 0, hetdat = 1,
#   hetvar = 0 (homoskedastic, serially uncorrelated errors, segment-specific
#   regressor moments). pftest is traced (not modified) to record every
#   sup F(l + 1 | l) statistic the procedure computes, in call order.
# ---------------------------------------------------------------------------
suppressMessages({
  library(jsonlite)
  library(strucchange)
  library(mbreaks)
})

fx <- "tests/reference_parity/_fixtures"
out <- list()
out$versions <- list(
  R = R.version.string,
  strucchange = as.character(packageVersion("strucchange")),
  mbreaks = as.character(packageVersion("mbreaks"))
)

br <- read.csv(file.path(fx, "ts_break.csv"))
r2 <- read.csv(file.path(fx, "r2_ts_break.csv"))
cases <- list(
  ts_ym = list(d = br, y = "ym", z = NULL),
  ts_yx = list(d = br, y = "y", z = "x"),
  r2_y3 = list(d = r2, y = "y3", z = NULL),
  r2_yx = list(d = r2, y = "yx", z = "x"),
  r2_yx2 = list(d = r2, y = "yx2", z = "x"),
  r2_wn = list(d = r2, y = "wn", z = NULL)
)

# ---- sup-F p-values: strucchange (Hansen 1997) -------------------------------
supf <- list()
for (nm in names(cases)) {
  cs <- cases[[nm]]
  f <- if (is.null(cs$z)) as.formula(paste(cs$y, "~ 1")) else
    as.formula(paste(cs$y, "~", cs$z))
  fs <- Fstats(f, data = cs$d, from = 0.15)
  st <- sctest(fs, type = "supF")
  supf[[nm]] <- list(
    stat = unname(st$statistic), p = unname(st$p.value),
    breakpoint = fs$breakpoint, from = fs$from, to = fs$to, nobs = fs$nobs
  )
}
out$supf <- supf

# p-value function on a grid (x is the Wald-scale statistic = k * F)
pv <- get("pvalue.Fstats", asNamespace("strucchange"))
grid <- list()
for (k in c(1, 2, 3, 5, 10, 40)) for (pi0 in c(0.005, 0.05, 0.10, 0.15, 0.20, 0.25, 0.33, 0.495, 0.5)) {
  xs <- k + c(0.5, 2, 5, 8, 12, 20, 35) * sqrt(k)
  grid[[length(grid) + 1]] <- list(
    k = k, pi0 = pi0, x = xs,
    p = sapply(xs, function(x) pv(x, type = "supF", k = k, lambda = pi0))
  )
}
out$supf_grid <- grid

# ---- Bai-Perron sequential procedure: mbreaks::dosequa ----------------------
calls <- NULL
trace(mbreaks:::pftest,
      exit = quote(calls[[length(calls) + 1]] <<- c(
        stat = as.numeric(returnValue()), bigT = bigT,
        date = as.numeric(datevec)[1])),
      print = FALSE, where = asNamespace("mbreaks"))
seqr <- list()
for (nm in names(cases)) {
  cs <- cases[[nm]]
  for (sig in 1:4) {
    calls <- list()
    o <- suppressWarnings(suppressMessages(dosequa(
      cs$y, z_name = cs$z, data = cs$d, m = 5, eps1 = 0.15, prewhit = 0,
      robust = 0, hetdat = 1, hetvar = 0, signif = sig)))
    cm <- do.call(rbind, calls)
    seqr[[paste0(nm, "_s", sig)]] <- list(
      nbreak = o$nbreak,
      dates = if (o$nbreak > 0) as.numeric(o$date) else numeric(0),
      calls_stat = unname(cm[, "stat"]),
      calls_T = unname(cm[, "bigT"]),
      calls_date = unname(cm[, "date"])
    )
  }
}
untrace(mbreaks:::pftest, where = asNamespace("mbreaks"))
out$sequential <- seqr

# the Bai-Perron (2003) sup F(l + 1 | l) critical values mbreaks uses
cvt <- list()
for (e in 1:5) {
  tab <- get(paste0("supF_next_cv", e), asNamespace("mbreaks"))
  cvt[[as.character(c(0.05, 0.10, 0.15, 0.20, 0.25)[e])]] <- unname(as.matrix(tab))
}
out$bp_cv <- cvt

writeLines(
  toJSON(out, digits = 17, auto_unbox = TRUE, pretty = TRUE, na = "null"),
  file.path(fx, "r2_ts_R.json")
)
cat("wrote", file.path(fx, "r2_ts_R.json"), "\n")

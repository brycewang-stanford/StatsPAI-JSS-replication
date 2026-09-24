#!/usr/bin/env Rscript
# Ground truth for tests/reference_parity/test_rd_open_R_parity.py
# (round-2 family `rd_open`: boundary discontinuity designs).
#
# Reads (written by _fixtures/_generate_rd_open_data.py):
#   _fixtures/rd_open_bd.csv       y, x1, x2, t (assignment above x2 = 0.3 x1),
#                                  g (120 clusters), takeup, yf (fuzzy outcome)
#   _fixtures/rd_open_bd_mass.csv  same design on a 0.05 lattice (mass points)
# Writes _fixtures/rd_open_R.json at 17 significant digits.
#
# Re-run only when the contract changes:
#   Rscript tests/reference_parity/_generate_rd_open_R.R
#
# Reference: rd2d 1.0.0 (Cattaneo, Titiunik, Yu) -- rd2d(), rdbw2d(),
# rd2d.distance(), rdbw2d.distance(). Deterministic (no simulation is
# involved in any number written here; the uniform bands, which are
# simulated, are not written).

suppressMessages({
  library(rd2d)
  library(RDHonest)
  library(jsonlite)
})

fx <- "tests/reference_parity/_fixtures"
df <- read.csv(file.path(fx, "rd_open_bd.csv"))
dm <- read.csv(file.path(fx, "rd_open_bd_mass.csv"))

bb <- c(-0.6, -0.3, 0, 0.3, 0.6)
b <- cbind(bb, 0.3 * bb)
X <- cbind(df$x1, df$x2)
Xm <- cbind(dm$x1, dm$x2)
dist_to <- function(d, b) {
  sapply(seq_len(nrow(b)), function(j)
    sqrt((d$x1 - b[j, 1])^2 + (d$x2 - b[j, 2])^2) * (2 * d$t - 1))
}
D <- dist_to(df, b)
Dm <- dist_to(dm, b)

tab <- function(x) {
  x <- as.data.frame(x)
  lapply(x, function(col) as.numeric(col))
}
out <- list()

loc <- function(r, cov = TRUE) {
  o <- list(main = tab(r$main))
  if (cov) o$cov_main <- unname(as.matrix(r$params.cov$main))
  if (!is.null(r$itt) && !identical(r$itt, NA)) {
    o$itt <- tab(r$itt)
    o$fs <- tab(r$fs)
  }
  o
}

# ---------------- location-based (rd2d) ----------------
out$L_default <- loc(rd2d(df$y, X, df$t, b, params.cov = "main"))
out$L_user_h_epa_hc3_sep_p2 <- loc(rd2d(df$y, X, df$t, b, h = 0.5, p = 2, kernel = "epa",
                                        vce = "hc3", fitmethod = "separate", params.cov = "main"))
out$L_cluster_hc0_msetwo <- loc(rd2d(df$y, X, df$t, b, cluster = df$g, vce = "hc0",
                                     bwselect = "msetwo", params.cov = "main"))
out$L_cluster_hc1_joint <- loc(rd2d(df$y, X, df$t, b, cluster = df$g, params.cov = "main"))
out$L_rad_uni_imserd_rot <- loc(rd2d(df$y, X, df$t, b, kernel = "uni", kernel_type = "rad",
                                     bwselect = "imserd", method = "rot", params.cov = "main"))
# Radial kernel with a user bandwidth: R fits at radius sqrt(h^2 + h^2) =
# sqrt(2) h (rd2d_h_normalize on the 2-column bandwidth grid) but rescales the
# variance with h * h, so its standard errors are sqrt(2) times the sandwich of
# the fit it runs. Independent evidence written alongside: weighted lm() at that
# radius with sandwich::vcovHC(type = "HC0") on each side.
out$L_rad_user_h_hc0_sep <- loc(rd2d(df$y, X, df$t, b, h = 0.4, kernel_type = "rad",
                                     vce = "hc0", fitmethod = "separate", params.cov = "main"))
rad_check <- lapply(seq_len(nrow(b)), function(j) {
  H <- 0.4 * sqrt(2)
  res <- sapply(0:1, function(s) {
    d <- df[df$t == s, ]
    u <- sqrt((d$x1 - b[j, 1])^2 + (d$x2 - b[j, 2])^2) / H
    w <- pmax(1 - u, 0)
    k <- w > 0
    dd <- data.frame(y = d$y[k], u1 = d$x1[k] - b[j, 1], u2 = d$x2[k] - b[j, 2])
    f <- lm(y ~ u1 + u2, data = dd, weights = w[k])
    c(coef(f)[1], sandwich::vcovHC(f, type = "HC0")[1, 1], sum(k))
  })
  list(est = unname(res[1, 2] - res[1, 1]), se = sqrt(res[2, 1] + res[2, 2]),
       n0 = res[3, 1], n1 = res[3, 2])
})
out$rad_lm_check <- list(est = sapply(rad_check, `[[`, "est"), se = sapply(rad_check, `[[`, "se"),
                         n0 = sapply(rad_check, `[[`, "n0"), n1 = sapply(rad_check, `[[`, "n1"),
                         sandwich = as.character(packageVersion("sandwich")))
out$L_deriv10_p2 <- loc(rd2d(df$y, X, df$t, b, p = 2, deriv = c(1, 0), params.cov = "main"))
tv <- cbind(rep(1, 5), rep(0.3, 5)) / sqrt(1.09)
out$L_tangvec <- loc(suppressWarnings(rd2d(df$y, X, df$t, b, tangvec = tv, params.cov = "main")))
out$L_gau_cerrd <- loc(rd2d(df$y, X, df$t, b, kernel = "gau", bwselect = "cerrd",
                            params.cov = "main"))
out$L_fuzzy_joint <- loc(rd2d(df$yf, X, df$t, b, fuzzy = df$takeup, params.cov = "main"))
out$L_fuzzy_cluster_separate <- loc(rd2d(df$yf, X, df$t, b, fuzzy = df$takeup, cluster = df$g,
                                         fitmethod = "separate", params.cov = "main"))
out$L_mass_adjust <- loc(suppressWarnings(rd2d(dm$y, Xm, dm$t, b, masspoints = "adjust",
                                               params.cov = "main")))
out$L_icertwo_hc2 <- loc(rd2d(df$y, X, df$t, b, bwselect = "icertwo", vce = "hc2",
                              params.cov = "main"))

# WBATE (summary.rd2d): weighted average of the pointwise effects with the
# covariance of the bias-corrected estimates. Equal and 1:5 weights.
wbate <- function(r, w) {
  invisible(capture.output(sm <- summary(r, WBATE = w)))
  row <- sm$tables$main["WBATE", ]
  lapply(as.list(row[, c("estimate.p", "estimate.q", "std.err.q", "t.value", "p.value",
                          "ci.lower", "ci.upper")]), as.numeric)
}
r_def <- rd2d(df$y, X, df$t, b, params.cov = "main")
out$WBATE_loc_equal <- wbate(r_def, rep(1, 5))
out$WBATE_loc_1to5 <- wbate(r_def, 1:5)

bw <- function(r) tab(r$bws)
out$BW_loc_default <- bw(rdbw2d(df$y, X, df$t, b))
out$BW_loc_certwo_rad <- bw(rdbw2d(df$y, X, df$t, b, bwselect = "certwo", kernel_type = "rad"))
out$BW_loc_fuzzy_itt <- bw(rdbw2d(df$yf, X, df$t, b, fuzzy = df$takeup, bwparam = "itt"))
out$BW_loc_nostd_sep <- bw(rdbw2d(df$y, X, df$t, b, stdvars = FALSE, fitmethod = "separate"))

# ---------------- distance-based (rd2d.distance) ----------------
dist <- function(r, cov = TRUE) {
  o <- list(main = tab(r$main))
  if (cov) o$cov_main <- unname(as.matrix(r$params.cov$main))
  o
}
out$D_default <- dist(rd2d.distance(df$y, D, b = b, cbands = FALSE, params.cov = "main"))
out$D_kink_unknown <- dist(rd2d.distance(df$y, D, b = b, kink.unknown = TRUE, cbands = FALSE,
                                         params.cov = "main"))
out$D_kink_unknown_TF <- dist(rd2d.distance(df$y, D, b = b, kink.unknown = c(TRUE, FALSE),
                                            cbands = FALSE, params.cov = "main"))
out$D_kink_position3 <- dist(rd2d.distance(df$y, D, b = b, kink.position = 3, cbands = FALSE,
                                           params.cov = "main"))
out$D_fuzzy_cluster <- dist(rd2d.distance(df$yf, D, b = b, fuzzy = df$takeup, cluster = df$g,
                                          cbands = FALSE, params.cov = "main"))
hm <- cbind(c(0.40, 0.45, 0.50, 0.55, 0.60), c(0.50, 0.50, 0.45, 0.45, 0.40))
out$D_user_h_hc2_p2_sep <- dist(rd2d.distance(df$y, D, b = b, h = hm, p = 2, vce = "hc2",
                                              fitmethod = "separate", cbands = FALSE,
                                              params.cov = "main"))
out$D_epa_imsetwo <- dist(rd2d.distance(df$y, D, b = b, kernel = "epa", bwselect = "imsetwo",
                                        cbands = FALSE, params.cov = "main"))
out$D_mass_adjust <- dist(suppressWarnings(rd2d.distance(dm$y, Dm, b = b, masspoints = "adjust",
                                                         cbands = FALSE, params.cov = "main")))
out$D_cluster_hc1_joint <- dist(rd2d.distance(df$y, D, b = b, cluster = df$g, cbands = FALSE,
                                              params.cov = "main"))

r_ddef <- rd2d.distance(df$y, D, b = b, cbands = FALSE, params.cov = "main")
out$WBATE_dist_equal <- wbate(r_ddef, rep(1, 5))
out$WBATE_dist_1to5 <- wbate(r_ddef, 1:5)

out$BW_dist_default <- bw(rdbw2d.distance(df$y, D, b = b))
out$BW_dist_certwo <- bw(rdbw2d.distance(df$y, D, b = b, bwselect = "certwo"))
out$BW_dist_cqt <- bw(rdbw2d.distance(df$y, D, b = b, cqt = 0.3, kernel = "uni"))

# ---------------- discrete running variable (sp.rd_discrete) ----------------
# Kolesar & Rothe (2018): BSD interval = RDHonest(), BME interval =
# RDHonestBME(), both by Kolesar. Integer ages 8..28, cutoff 18.
dd <- read.csv(file.path(fx, "rd_open_discrete.csv"))
hon <- function(r) {
  co <- r$coefficients
  keep <- intersect(c("estimate", "std.error", "maximum.bias", "conf.low", "conf.high",
                      "conf.low.onesided", "conf.high.onesided", "bandwidth", "eff.obs",
                      "leverage", "p.value", "M"), names(co))
  lapply(as.list(co[1, keep]), as.numeric)
}
out$DISC_bsd_fixed <- hon(RDHonest(y ~ age, data = dd, cutoff = 18, M = 0.05, h = 5))
out$DISC_bsd_selected <- hon(suppressMessages(RDHonest(y ~ age, data = dd, cutoff = 18)))
out$DISC_bsd_uniform <- hon(RDHonest(y ~ age, data = dd, cutoff = 18, M = 0.05, h = 4,
                                     kern = "uniform"))
out$DISC_bme_h4 <- hon(RDHonestBME(y ~ age, data = dd, cutoff = 18, h = 4))
out$DISC_bme_h6_o1 <- hon(RDHonestBME(y ~ age, data = dd, cutoff = 18, h = 6, order = 1))
out$DISC_bme_all_o2 <- hon(RDHonestBME(y ~ age, data = dd, cutoff = 18, order = 2))

out$meta <- list(
  R = paste(R.version$major, R.version$minor, sep = "."),
  rd2d = as.character(packageVersion("rd2d")),
  sandwich = as.character(packageVersion("sandwich")),
  RDHonest = as.character(packageVersion("RDHonest")),
  b = unname(b),
  tangvec = unname(tv),
  h_user_distance = unname(hm)
)

writeLines(toJSON(out, digits = I(17), auto_unbox = TRUE, pretty = FALSE, na = "null"),
           file.path(fx, "rd_open_R.json"))
cat("wrote", file.path(fx, "rd_open_R.json"), "\n")

# R side of sdid_drawwise_reference.py: synthdid on each draw's bytes.
# Writes the point estimate, the package's placebo standard error at 100
# replications, and the exhaustive placebo standard error (each of the N0
# controls taken in turn as the pseudo-treated unit), which has no
# simulation noise.
suppressPackageStartupMessages({library(synthdid); library(parallel)})
args <- commandArgs(trailingOnly = TRUE)
dir <- args[1]; n <- as.integer(args[2]); cores <- as.integer(args[3])
one <- function(s) {
  d <- read.csv(sprintf("%s/d%04d.csv", dir, s))
  Y <- as.matrix(d)
  N0 <- nrow(Y) - 1L; T0 <- 12L
  tau <- synthdid_estimate(Y, N0, T0)
  set.seed(s)
  se100 <- sqrt(vcov(tau, method = "placebo", replications = 100))
  Yc <- Y[seq_len(N0), , drop = FALSE]
  pl <- sapply(seq_len(N0), function(j) {
    ord <- c(setdiff(seq_len(N0), j), j)
    as.numeric(synthdid_estimate(Yc[ord, , drop = FALSE], N0 - 1L, T0))
  })
  c(as.numeric(tau), as.numeric(se100), sqrt((N0 - 1) / N0) * sd(pl))
}
res <- do.call(rbind, mclapply(seq_len(n) - 1L, one, mc.cores = cores))
colnames(res) <- c("estimate", "se_placebo100", "se_placebo_exhaustive")
write.csv(res, file.path(dir, "r.csv"), row.names = FALSE)

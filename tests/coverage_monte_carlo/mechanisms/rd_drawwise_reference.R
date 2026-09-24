# R side of rd_drawwise_reference.py: rdrobust defaults on each draw's bytes.
suppressPackageStartupMessages(library(rdrobust))
args <- commandArgs(trailingOnly = TRUE); dir <- args[1]; n <- as.integer(args[2])
res <- t(sapply(seq_len(n) - 1L, function(s) {
  d <- read.csv(sprintf("%s/d%03d.csv", dir, s))
  r <- rdrobust(d$y, d$x, c = 0)
  c(r$coef[3], r$ci[3, 1], r$ci[3, 2])  # robust row
}))
colnames(res) <- c("estimate", "ci_lo", "ci_hi")
write.csv(res, file.path(dir, "r.csv"), row.names = FALSE)

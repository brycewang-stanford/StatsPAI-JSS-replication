# Section 4.3: R HonestDiD on the coefficients and covariance of the original
# did::mpdta case study, for every post period, at M = 0. Reads the moments that
# ex03_honestdid_moments in ex03_csdid.py writes. HonestDiD simulates its
# folded-normal quantile, so agreement stops near 3e-4 (Section 5.3).
library(HonestDiD)
d <- "replication/results"
b <- scan(file.path(d, "ex03_mpdta_beta.csv"), quiet = TRUE)
S <- unname(as.matrix(read.csv(file.path(d, "ex03_mpdta_sigma.csv"), header = FALSE)))
set.seed(1)
out <- do.call(rbind, lapply(1:4, function(k) {
  l <- rep(0, 4); l[k] <- 1
  r <- createSensitivityResults(betahat = b, sigma = S, numPrePeriods = 3,
                                numPostPeriods = 4, method = "FLCI",
                                Mvec = 0, l_vec = l, alpha = 0.05)
  data.frame(event_time = k - 1, lb = r$lb, ub = r$ub)
}))
write.csv(out, file.path(d, "ex03_honestdid_reference.csv"), row.names = FALSE)
print(out)

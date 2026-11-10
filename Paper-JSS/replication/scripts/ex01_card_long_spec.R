# Section 4.1: the longer specification behind Card's published 0.075 and 0.132,
# on the full wooldridge::card extract (sp.datasets.card_1995() keeps only the
# columns of the shorter specification used in the article).
data("card", package = "wooldridge")
x <- "exper + expersq + black + south + smsa + smsa66 + reg662 + reg663 + reg664 + reg665 + reg666 + reg667 + reg668 + reg669"
ols <- lm(as.formula(paste("lwage ~ educ +", x)), card)
iv <- AER::ivreg(as.formula(paste("lwage ~ educ +", x, "| nearc4 +", x)), data = card)
out <- data.frame(model = c("OLS", "2SLS"), educ = c(coef(ols)["educ"], coef(iv)["educ"]))
write.csv(out, "replication/results/ex01_card_long_spec.csv", row.names = FALSE)
print(out)

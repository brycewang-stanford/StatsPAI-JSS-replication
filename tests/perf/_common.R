# Shared helpers for the R side of the Track C benchmarks.
#
# Every input is written once by tests/perf/_data.py and read by both
# sides; read_perf_data() checks the file against the manifest's SHA-256
# and returns the hash so the result file can prove which bytes it timed.
# Threads are pinned to one on both sides (fixest, data.table, BLAS via
# the runner's environment) so a ratio compares implementations, not the
# number of cores each package decides to use.

suppressPackageStartupMessages({
  library(jsonlite)
  library(digest)
})

.perf_dir <- (function() {
  args <- commandArgs(trailingOnly = FALSE)
  m <- grep("^--file=", args, value = TRUE)
  if (length(m) > 0) dirname(normalizePath(sub("^--file=", "", m[1]))) else getwd()
})()
RESULTS_DIR <- file.path(.perf_dir, "results")
DATA_DIR <- file.path(.perf_dir, "data")
dir.create(RESULTS_DIR, showWarnings = FALSE, recursive = TRUE)

if (requireNamespace("data.table", quietly = TRUE)) data.table::setDTthreads(1L)

read_perf_data <- function(estimator, n) {
  name <- sprintf("%s_%d.csv", estimator, as.integer(n))
  path <- file.path(DATA_DIR, name)
  manifest <- jsonlite::fromJSON(file.path(DATA_DIR, "manifest.json"))
  if (!file.exists(path) || is.null(manifest[[name]])) {
    stop("missing benchmark input ", name, "; run `python tests/perf/_data.py` first")
  }
  sha <- digest::digest(file = path, algo = "sha256")
  if (!identical(sha, manifest[[name]])) {
    stop("benchmark input ", name, " does not match its manifest hash")
  }
  list(df = read.csv(path), sha256 = sha)
}

time_one <- function(fn, n_reps, warmup = 1L) {
  for (i in seq_len(warmup)) suppressMessages(fn())
  t <- numeric(n_reps)
  for (i in seq_len(n_reps)) {
    gc()
    t0 <- proc.time()[["elapsed"]]
    suppressMessages(fn())
    t[i] <- proc.time()[["elapsed"]] - t0
  }
  list(median = median(t), iqr = IQR(t), min = min(t), max = max(t))
}

perf_row <- function(estimator, n, n_reps, res, extra) {
  list(
    estimator = jsonlite::unbox(estimator),
    side = jsonlite::unbox("R"),
    n = jsonlite::unbox(as.integer(n)),
    n_reps = jsonlite::unbox(as.integer(n_reps)),
    median_time_s = jsonlite::unbox(res$median),
    iqr_time_s = jsonlite::unbox(res$iqr),
    min_time_s = jsonlite::unbox(res$min),
    max_time_s = jsonlite::unbox(res$max),
    peak_mem_mb = jsonlite::unbox(NA_real_),
    extra = lapply(extra, jsonlite::unbox)
  )
}

write_perf <- function(estimator, rows, package) {
  payload <- list(
    estimator = jsonlite::unbox(estimator),
    side = jsonlite::unbox("R"),
    rows = rows,
    hardware = list(
      reference_package = jsonlite::unbox(
        paste(package, as.character(utils::packageVersion(package)))
      ),
      platform = jsonlite::unbox(R.version$platform),
      R_version = jsonlite::unbox(R.version$version.string),
      run_id = jsonlite::unbox(Sys.getenv("STATSPAI_PERF_RUN_ID", "unset")),
      load_avg_1m_at_start = jsonlite::unbox(tryCatch(
        as.numeric(strsplit(trimws(system("sysctl -n vm.loadavg", intern = TRUE)), " ")[[1]][2]),
        error = function(e) NA_real_
      )),
      threads = jsonlite::unbox(1L)
    ),
    extra = list()
  )
  writeLines(
    jsonlite::toJSON(payload, pretty = TRUE, na = "null", null = "null", digits = NA),
    file.path(RESULTS_DIR, sprintf("%s_R.json", estimator))
  )
  message("OK -- wrote ", estimator, "_R.json")
}

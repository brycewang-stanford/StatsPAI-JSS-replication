#!/usr/bin/env bash
# Run the eight Track C benchmarks once the machine is idle.
#
#   tests/perf/run_when_idle.sh [SRC]
#
# SRC is the statspai source tree to benchmark (default: this checkout's
# src/). Run it against the release-candidate commit before tagging, so the
# timings land inside the tag the JSS paper pins. It waits until the 1-minute
# load average has stayed below $LOAD_MAX (default 1.5) for five one-minute
# samples, then runs Python and R sides in sequence and logs the load before
# each. Wall-clock timings from a busy machine are not comparable: a run
# under load ~9 once inflated ratios by 20-30%.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="${1:-$HERE/../../src}"
LOAD_MAX="${LOAD_MAX:-1.5}"
export PYTHONPATH="$SRC"
PY="${PYTHON:-python3}"
load1() { if command -v sysctl >/dev/null && sysctl -n vm.loadavg >/dev/null 2>&1; then sysctl -n vm.loadavg | awk '{print $2}'; else awk '{print $1}' /proc/loadavg; fi; }
streak=0
while (( streak < 5 )); do
  l=$(load1)
  if awk -v l="$l" -v m="$LOAD_MAX" 'BEGIN{exit !(l < m)}'; then streak=$((streak+1)); else streak=0; fi
  (( streak >= 5 )) && break
  echo "$(date +%T) waiting, load=$l"; sleep 60
done
cd "$HERE"
"$PY" -c "import statspai; print('benchmarking statspai', statspai.__version__, 'from', statspai.__file__)"
for m in 01_hdfe 02_csdid 03_scm 04_dml; do
  echo "=== $m py $(date +%T) load=$(load1)"; "$PY" "${m}_perf.py"
  echo "=== $m R  $(date +%T) load=$(load1)"; Rscript "${m}_perf.R"
done
"$PY" compare_perf.py
echo "=== done $(date +%T) load=$(load1)"

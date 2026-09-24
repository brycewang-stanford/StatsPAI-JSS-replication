"""Every Track A row states which implementation its StatsPAI side ran.

A parity row supports a claim about a StatsPAI-native algorithm only if the
Python side executed one. ``tests/r_parity/compare.py::
IMPLEMENTATION_PROVENANCE`` records the exceptions (official ports,
third-party Python libraries, reference backends), and
``tests/r_parity/results/_implementation_trace.json`` -- written by
``scripts/trace_parity_provenance.py``, which *runs* each module under a
profiler -- records what actually happened. This test holds the two
together, so a module cannot quietly start delegating (or stop) without the
table, the appendix marker and the manuscript counts following.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PARITY = ROOT / "tests" / "r_parity"
TRACE = PARITY / "results" / "_implementation_trace.json"

#: Packages whose use makes a row third-party even if StatsPAI wraps it.
THIRD_PARTY_ESTIMATORS = {
    "linearmodels",
    "statsmodels",
    "pyfixest",
    "econml",
    "doubleml",
    "lifelines",
    "causalml",
}
#: Python ports maintained by the method's own authors.
OFFICIAL_PORTS = {"rdrobust", "rddensity", "rdd", "rdmulti", "rdlocrand"}
#: statsmodels namespaces that are utilities, not estimators.
STATSMODELS_UTILITY_PREFIXES = ("statsmodels.tools.", "statsmodels.compat")


def _load_compare():
    spec = importlib.util.spec_from_file_location(
        "_compare_prov", PARITY / "compare.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _trace() -> dict:
    return json.loads(TRACE.read_text(encoding="utf-8"))["modules"]


def _observed_kind(rec: dict, side_checks: frozenset = frozenset()) -> str:
    if rec["rscript_launches"] > 0:
        return "reference_backend"
    estimator_pkgs = set()
    for call in rec["boundary_calls"]:
        pkg = call["package"]
        if pkg in side_checks:
            continue
        if pkg == "statsmodels" and call["callee"].startswith(
            STATSMODELS_UTILITY_PREFIXES
        ):
            continue
        estimator_pkgs.add(pkg)
    if estimator_pkgs & THIRD_PARTY_ESTIMATORS:
        return "third_party_python"
    if estimator_pkgs & OFFICIAL_PORTS:
        return "official_python_port"
    return "native"


def test_every_module_is_traced_and_the_trace_is_current():
    compare = _load_compare()
    trace = _trace()
    assert set(trace) == set(compare.TOLERANCES)
    stale = [
        stem
        for stem, rec in trace.items()
        if rec.get("source_sha256")
        != hashlib.sha256((PARITY / f"{stem}.py").read_bytes()).hexdigest()
    ]
    assert not stale, (
        "Track A modules edited since they were traced; re-run "
        f"`python scripts/trace_parity_provenance.py {' '.join(s[:2] for s in stale)}`"
    )
    errors = {stem: rec["error"] for stem, rec in trace.items() if rec.get("error")}
    assert not errors


def test_registered_provenance_matches_the_trace():
    compare = _load_compare()

    def observed(stem, rec):
        allowed = frozenset(compare.IMPLEMENTATION_SIDE_CHECKS.get(stem, {}))
        return _observed_kind(rec, allowed)

    mismatches = {
        stem: (compare.implementation_kind(stem), observed(stem, rec))
        for stem, rec in _trace().items()
        if compare.implementation_kind(stem) != observed(stem, rec)
    }
    # A side-check allowance must be real: the package is used, and only by a
    # module that is otherwise native.
    for stem, pkgs in compare.IMPLEMENTATION_SIDE_CHECKS.items():
        assert set(pkgs) <= set(_trace()[stem]["packages"]), stem
    assert not mismatches, mismatches


def test_no_parity_row_compares_a_reference_with_itself():
    compare = _load_compare()
    assert (
        compare.implementation_census(list(compare.TOLERANCES))["reference_backend"]
        == 0
    )
    for stem, rec in _trace().items():
        assert rec["rscript_launches"] == 0, stem


def test_honest_did_modules_are_native():
    trace = _trace()
    for stem in ("10_honest_did", "21_honest_relmags"):
        assert _observed_kind(trace[stem]) == "native"


@pytest.mark.parametrize("stem", ["06_rd"])
def test_official_port_is_a_recorded_side_check_not_the_headline(stem):
    """The RD headline is native; the port appears only as unjoined rows."""
    compare = _load_compare()
    assert compare.implementation_kind(stem) == "native"
    rows = {d.statistic for d in compare.collect(stem)}
    assert not any(r.startswith("cct_port_") for r in rows)

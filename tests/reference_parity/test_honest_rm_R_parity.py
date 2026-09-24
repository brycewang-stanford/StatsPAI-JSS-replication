"""Native relative-magnitudes Honest DiD vs R ``HonestDiD`` 0.2.8.

``statspai.did._arp`` inverts the Andrews-Roth-Pakes conditional test (and
the conditional least-favourable hybrid, HonestDiD's default) over the union
of ``Delta^RM(Mbar)`` pieces on HonestDiD's own theta grid. Both packages
report the smallest and largest accepted grid point, so:

* ``method="Conditional"`` involves no simulation and a correct port agrees
  **exactly** (the same grid points), on every case below -- a diagonal and
  a correlated covariance, a non-basis target (the mean of the post
  periods, exercising the change of basis), and a single post period (the
  no-nuisance test path).
* ``method="C-LF"`` calibrates its first stage with a simulated
  least-favourable critical value (1,000 draws). Our draws come from NumPy,
  HonestDiD's from R, so the bounds can differ by that Monte Carlo error --
  observed at most one grid step (0.4% of the grid span / 40 target SDs).
  This is T3 evidence, stated as such.

Fixture: ``_fixtures/honest_rm_R.json`` from
``_fixtures/_generate_honest_rm_R.R``.
"""

from __future__ import annotations

import json
import pathlib
import warnings

import numpy as np
import pandas as pd
import pytest

import statspai as sp
from statspai.core.results import CausalResult
from statspai.did._arp import create_a_rm, rm_confidence_set

_FIX = pathlib.Path(__file__).parent / "_fixtures"
REF = json.loads((_FIX / "honest_rm_R.json").read_text(encoding="utf-8"))
CASES = sorted(k for k in REF if not k.startswith("_"))

pytestmark = pytest.mark.slow  # ~40 s: 16 finite-grid test inversions


def _inputs(key):
    c = REF[key]
    return (
        np.asarray(c["betahat"], float),
        np.asarray(c["sigma"], float),
        int(c["npre"]),
        int(c["npost"]),
        np.atleast_1d(np.asarray(c["l_vec"], float)),
        c,
    )


@pytest.mark.parametrize("key", [k for k in CASES if k.endswith("|Conditional")])
def test_conditional_set_is_identical_to_honestdid(key):
    b, s, npre, npost, l_vec, c = _inputs(key)
    for i, m_bar in enumerate(c["Mbar"]):
        lo, hi, _, _ = rm_confidence_set(
            b, s, npre, npost, m_bar, l_vec=l_vec, method="Conditional"
        )
        assert lo == pytest.approx(c["lb"][i], abs=1e-12), (key, m_bar)
        assert hi == pytest.approx(c["ub"][i], abs=1e-12), (key, m_bar)


@pytest.mark.parametrize("key", [k for k in CASES if k.endswith("|C-LF")])
def test_clf_hybrid_within_one_grid_step_of_honestdid(key):
    """aligned, not bit-exact: the first-stage critical value is simulated."""
    b, s, npre, npost, l_vec, c = _inputs(key)
    for i, m_bar in enumerate(c["Mbar"]):
        lo, hi, grid, _ = rm_confidence_set(
            b, s, npre, npost, m_bar, l_vec=l_vec, method="C-LF"
        )
        step = grid[1] - grid[0]
        assert abs(lo - c["lb"][i]) <= step * (1 + 1e-9), (key, m_bar)
        assert abs(hi - c["ub"][i]) <= step * (1 + 1e-9), (key, m_bar)


def test_moment_matrix_equals_honestdid():
    # HonestDiD:::.create_A_RM(numPrePeriods = 3, numPostPeriods = 3,
    # Mbar = 1, s = 0, max_positive = TRUE), printed by R 4.5.2: 12 rows
    # minus the one zero row (the reference difference bounding itself),
    # six columns once the normalised reference period is dropped.
    expected = np.array(
        [
            [-1, 1, 1, 0, 0, 0],
            [0, -1, 2, 0, 0, 0],
            [0, 0, 1, 1, 0, 0],
            [0, 0, 1, -1, 1, 0],
            [0, 0, 1, 0, -1, 1],
            [1, -1, 1, 0, 0, 0],
            [0, 1, 0, 0, 0, 0],
            [0, 0, 2, 0, 0, 0],
            [0, 0, 1, -1, 0, 0],
            [0, 0, 1, 1, -1, 0],
            [0, 0, 1, 0, 1, -1],
        ],
        dtype=float,
    )
    np.testing.assert_array_equal(create_a_rm(3, 3, 1.0, 0, True) + 0.0, expected)


def test_public_api_routes_to_the_native_set_and_matches_r():
    """sp.honest_did(method='relative_magnitude') is the native ARP set."""
    b, s, npre, npost, l_vec, c = _inputs("diag33|Conditional")
    times = [-3, -2, -1, 0, 1, 2]
    es = pd.DataFrame({"relative_time": times, "att": b, "se": np.sqrt(np.diag(s))})
    res = CausalResult(
        method="x",
        estimand="ATT(0)",
        estimate=float(b[3]),
        se=float(np.sqrt(s[3, 3])),
        pvalue=0.0,
        ci=(0.0, 1.0),
        alpha=0.05,
        n_obs=1000,
        model_info={
            "event_study": es,
            "event_study_vcov": pd.DataFrame(s, index=times, columns=times),
        },
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # the native path must not warn here
        out = sp.honest_did(
            res,
            e=0,
            m_grid=c["Mbar"],
            method="relative_magnitude",
            honestdid_method="Conditional",
        )
    assert out.attrs["interval"] == "arp_conditional"
    np.testing.assert_allclose(out["ci_lower"], c["lb"], atol=1e-12)
    np.testing.assert_allclose(out["ci_upper"], c["ub"], atol=1e-12)


def test_breakdown_relative_magnitude_uses_the_native_set():
    b, s, npre, npost, l_vec, _ = _inputs("corr33|C-LF")
    times = [-4, -3, -2, 0, 1, 2]
    es = pd.DataFrame({"relative_time": times, "att": b, "se": np.sqrt(np.diag(s))})
    res = CausalResult(
        method="x",
        estimand="ATT",
        estimate=float(b[4]),
        se=float(np.sqrt(s[4, 4])),
        pvalue=0.0,
        ci=(0.0, 1.0),
        alpha=0.05,
        n_obs=1000,
        model_info={
            "event_study": es,
            "event_study_vcov": pd.DataFrame(s, index=times, columns=times),
        },
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        m_star = sp.breakdown_m(res, e=1, method="relative_magnitude")
    # The set excludes zero just below M* and not just above it.
    lo_b, hi_b, _, _ = rm_confidence_set(
        b, s, 3, 3, max(m_star - 0.01, 0.0), l_vec=l_vec
    )
    lo_a, hi_a, _, _ = rm_confidence_set(b, s, 3, 3, m_star + 0.01, l_vec=l_vec)
    assert not (lo_b <= 0 <= hi_b)
    assert lo_a <= 0 <= hi_a


def test_without_covariance_falls_back_and_warns():
    es = pd.DataFrame(
        {
            "relative_time": [-2, -1, 0, 1],
            "att": [0.01, -0.01, 0.4, 0.3],
            "se": [0.05, 0.05, 0.1, 0.1],
        }
    )
    res = CausalResult(
        method="x",
        estimand="ATT",
        estimate=0.4,
        se=0.1,
        pvalue=0.0,
        ci=(0.2, 0.6),
        alpha=0.05,
        n_obs=100,
        model_info={"event_study": es},
    )
    with pytest.warns(UserWarning, match="covariance is unavailable"):
        out = sp.honest_did(res, e=0, method="relative_magnitude")
    assert out.attrs["interval"] == "worst_case_bias"


def test_unsupported_native_method_raises():
    b, s, *_ = _inputs("diag33|Conditional")
    times = [-3, -2, -1, 0, 1, 2]
    es = pd.DataFrame({"relative_time": times, "att": b, "se": np.sqrt(np.diag(s))})
    res = CausalResult(
        method="x",
        estimand="ATT",
        estimate=0.5,
        se=0.1,
        pvalue=0.0,
        ci=(0.3, 0.7),
        alpha=0.05,
        n_obs=100,
        model_info={
            "event_study": es,
            "event_study_vcov": pd.DataFrame(s, index=times, columns=times),
        },
    )
    with pytest.raises(sp.exceptions.MethodIncompatibility):
        sp.honest_did(res, e=0, method="relative_magnitude", honestdid_method="FLCI")

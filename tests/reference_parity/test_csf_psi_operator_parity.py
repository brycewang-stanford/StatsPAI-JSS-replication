"""Reference parity (T2): the causal-survival score map vs ``grf``.

The causal survival forest turns nuisance curves -- event survival under
each arm, censoring survival, propensity -- into the numerator ``A_i`` and
denominator ``B_i`` of its estimating equation (Cui, Kosorok, Sverdrup,
Wager and Zhu 2023, eq. 11).  The paper leaves the discretisation of the
censoring integral open; StatsPAI follows the reference implementation
maintained by the method's authors (grf): the sum over grid times at or
below ``min(U, h)`` of ``[log S^C(c_{k-1}) - log S^C(c_k)] / S^C(c_k)``
times ``Q(c_k) - m``, with ``B_i = (W_i - e_i)^2``.

Given the same curves (``csf_psi_inputs.json``, deliberately with tied
event/censoring times and rows past the horizon), ``csf_scores`` must
reproduce grf's numerator, denominator and arm means to the floating-point
floor for both targets.

Regenerate with::

    python tests/reference_parity/_fixtures/_generate_csf_psi_inputs.py
    Rscript tests/reference_parity/_fixtures/_generate_csf_psi.R

References
----------
[@cui2023estimating]
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest

from statspai.survival.causal_forest import csf_scores

_DIR = pathlib.Path(__file__).parent / "_fixtures"
_IN = _DIR / "csf_psi_inputs.json"
_OUT = _DIR / "csf_psi_R.json"

pytestmark = pytest.mark.skipif(
    not (_IN.exists() and _OUT.exists()),
    reason="csf_psi fixture is not materialized",
)


@pytest.fixture(scope="module")
def inputs():
    return json.loads(_IN.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ref():
    return json.loads(_OUT.read_text(encoding="utf-8"))


@pytest.mark.parametrize("target", ["RMST", "survival_probability"])
def test_score_map_matches_grf(inputs, ref, target):
    a = {k: np.asarray(v, dtype=float) for k, v in inputs.items()}
    grid = a["grid"]
    out = csf_scores(
        a["Y"],
        a["D"],
        a["W"],
        a["e"],
        a["S1"],
        a["S0"],
        grid,
        a["C"],
        grid,
        float(inputs["horizon"]),
        target,
    )
    r = {k: np.asarray(v, dtype=float) for k, v in ref[target].items()}
    np.testing.assert_allclose(out["mu1"], r["mu1"], rtol=0, atol=1e-12)
    np.testing.assert_allclose(out["mu0"], r["mu0"], rtol=0, atol=1e-12)
    np.testing.assert_allclose(out["A"], r["numerator"], rtol=0, atol=1e-12)
    np.testing.assert_allclose(out["B"], r["denominator"], rtol=0, atol=1e-12)


def test_fixture_exercises_ties_and_horizon(inputs):
    """The fixture must keep the cases where conventions could diverge."""
    Y = np.asarray(inputs["Y"])
    D = np.asarray(inputs["D"])
    h = float(inputs["horizon"])
    ev = set(Y[D > 0.5].tolist())
    ce = set(Y[D < 0.5].tolist())
    assert ev & ce, "no tied event/censoring times"
    assert np.any(Y >= h) and np.any((D < 0.5) & (Y < h))

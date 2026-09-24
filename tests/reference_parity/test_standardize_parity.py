"""Reference parity: sp.direct_standardize / sp.indirect_standardize.

Both are deterministic closed-form epidemiological rate standardizations
(identical to epiR / standard texts and Stata ``dstdize``/``istdize``):

  * ``direct_standardize`` : DSR = sum(w_i * r_i) / sum(w_i), where
    r_i = events_i / population_i and w_i are the standard-population weights.
  * ``indirect_standardize`` : expected = sum((events_ref_i/pop_ref_i) *
    pop_study_i); SMR = observed / expected.

Closed-form identities (no external fixture needed); match is machine-precision.
"""

from __future__ import annotations

import numpy as np
import pytest

import statspai as sp

_TOL = 1e-12


def _g(obj, key):
    return obj[key] if isinstance(obj, dict) else getattr(obj, key)


def test_direct_standardize_closed_form():
    events = [30.0, 50.0, 20.0]
    population = [1000.0, 800.0, 500.0]
    weights = [2000.0, 1500.0, 1000.0]
    r = sp.direct_standardize(events, population, weights)
    rates = np.array(events) / np.array(population)
    w = np.array(weights)
    dsr = float(np.sum(w * rates) / np.sum(w))
    assert _g(r, "rate") == pytest.approx(dsr, abs=_TOL)


def test_indirect_standardize_smr_closed_form():
    observed = 120.0
    ev_ref = [30.0, 50.0, 20.0]
    pop_ref = [1000.0, 800.0, 500.0]
    pop_study = [1500.0, 1200.0, 700.0]
    r = sp.indirect_standardize(observed, ev_ref, pop_ref, pop_study)
    ref_rates = np.array(ev_ref) / np.array(pop_ref)
    expected = float(np.sum(ref_rates * np.array(pop_study)))
    assert _g(r, "expected") == pytest.approx(expected, abs=_TOL)
    assert _g(r, "smr") == pytest.approx(observed / expected, abs=_TOL)

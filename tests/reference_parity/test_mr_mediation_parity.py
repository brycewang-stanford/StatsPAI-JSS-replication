"""Frozen-formula parity: sp.mr_mediation direct + indirect = total.

Two-step MR mediation (Burgess et al. 2015) decomposes the total causal
effect into a direct effect (exposure -> outcome, controlling for mediator)
and an indirect effect via the mediator. The two components must sum to
the total effect exactly, and the proportion-mediated ratio must equal
indirect / total. Bit-exact against these closed-form identities.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp


@pytest.fixture(scope="module")
def fitted():
    rng = np.random.default_rng(0)
    K = 50
    df = pd.DataFrame(
        {
            "beta_x": rng.uniform(0.10, 0.30, K),
            "se_x": rng.uniform(0.005, 0.020, K),
            "beta_m": rng.uniform(0.20, 0.50, K),
            "se_m": rng.uniform(0.005, 0.020, K),
            "beta_y": rng.uniform(0.30, 0.60, K),
            "se_y": rng.uniform(0.005, 0.020, K),
        }
    )
    return sp.mr_mediation(df)


def test_direct_plus_indirect_equals_total(fitted):
    assert float(fitted.direct_effect) + float(fitted.indirect_effect) == pytest.approx(
        float(fitted.total_effect), abs=1e-12
    )


def test_proportion_mediated_equals_indirect_over_total(fitted):
    assert float(fitted.proportion_mediated) == pytest.approx(
        float(fitted.indirect_effect) / float(fitted.total_effect), abs=1e-12
    )


def test_mediation_proportion_within_unit_interval(fitted):
    assert 0.0 <= float(fitted.proportion_mediated) <= 1.0

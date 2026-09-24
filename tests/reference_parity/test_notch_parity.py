"""Analytical parity: sp.notch planted-bunching recovery (Kleven & Waseem 2013).

On a uniform running-variable density over [5, 15] we plant a notch response:
every unit in (10, 10.5] relocates just below the notch point at 10. The
planted excess mass is therefore the known mover count (~ n/20), the missing
mass above the notch equals the excess mass (mass conservation), and the
marginal buncher sits at 10.5. The estimator recovers all three from the
observed histogram vs the excluded-region counterfactual polynomial.
Analytical evidence tier (known-truth recovery on a deterministic DGP).
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp

N = 40_000
NOTCH = 10.0
MOVER_UPPER = 10.5  # units in (NOTCH, MOVER_UPPER] bunch below the notch


@pytest.fixture(scope="module")
def fitted():
    rng = np.random.default_rng(0)
    x = rng.uniform(5, 15, N)
    movers = (x > NOTCH) & (x <= MOVER_UPPER)
    x2 = x.copy()
    x2[movers] = rng.uniform(9.75, 10.0, movers.sum())
    df = pd.DataFrame({"inc": x2})
    res = sp.notch(
        df,
        x="inc",
        notch_point=NOTCH,
        bin_width=0.25,
        exclude_range=(9.75, 10.75),
        n_boot=30,
        seed=0,
    )
    return int(movers.sum()), res


def test_excess_bunching_recovers_planted_mass(fitted):
    n_movers, r = fitted
    assert float(r.excess_bunching) == pytest.approx(n_movers, rel=0.10)


def test_missing_mass_conservation(fitted):
    _, r = fitted
    # The mass missing above the notch equals the excess mass below it.
    assert float(r.missing_mass) == pytest.approx(float(r.excess_bunching), rel=0.10)


def test_marginal_buncher_location(fitted):
    _, r = fitted
    # True movers came from up to 10.5; resolution is one bin (0.25).
    assert abs(float(r.marginal_buncher) - MOVER_UPPER) <= 0.25

"""Analytical parity: sp.structural_break planted-break recovery (Bai-Perron).

On a series with a single planted mean shift at t = 150 the Bai-Perron
procedure recovers the break date exactly, reports one break, and the
segmented RSS is far below the no-break RSS. Analytical evidence tier
(known-truth recovery on a deterministic DGP).
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp

BREAK_AT = 150
N = 300


@pytest.fixture(scope="module")
def result():
    rng = np.random.default_rng(0)
    y = np.concatenate(
        [1.0 + rng.normal(0, 0.5, BREAK_AT), 3.0 + rng.normal(0, 0.5, N - BREAK_AT)]
    )
    df = pd.DataFrame({"y": y, "t": np.arange(N)})
    return sp.structural_break(df, y="y")


def test_recovers_planted_break_date(result):
    assert int(result.n_breaks) == 1
    assert list(result.break_dates) == [BREAK_AT]


def test_break_improves_fit_and_is_significant(result):
    assert float(result.rss_segments) < 0.5 * float(result.rss_full)
    # sup F(1|0) against the Bai-Perron 5% critical value (round 2: the
    # sequential procedure reports critical values, not p-values)
    assert float(result.f_stats[0]) > float(result.critical_values[0])
    assert float(result.f_stats[0]) > 100

"""Seed-replicated algorithmic comparison: ``sp.causal_forest`` vs ``grf``.

A causal forest is a stochastic algorithm. Two kinds of uncertainty must
not be confused:

* **sampling** variation -- how the ATE would change across datasets, which
  is what ``average_treatment_effect()``'s standard error estimates; and
* **algorithmic Monte Carlo** variation -- how it changes across forest
  seeds with the data held fixed.

Saying two implementations "agree within Monte Carlo error" is a statement
about the second, and it can only be tested by refitting each engine under
many seeds on the same data. The fixtures do that
(``_fixtures/_generate_grf_seed_mc_{R.R,py.py}``): K seeds per engine at
500, 2,000 (the default) and 8,000 trees, on two datasets -- the
reference-parity fixture ``grf_data.csv`` and Track A module 13's
clean-overlap CSV -- with both engines at their defaults.

What the evidence supports, and what these tests pin:

1. **Equivalent for inference at every tree count.** A two one-sided test
   (TOST, 5%) establishes ``|mean_sp - mean_grf| < delta`` with
   ``delta = 0.1 x`` grf's mean reported sampling SE, at 500, 2,000 and
   8,000 trees on both datasets (upper TOST bound <= 0.056 sampling SE).
2. **The same algorithmic noise.** The two engines' seed-to-seed SDs are
   within a factor of two of each other at every tree count (observed
   ratios 0.78-1.48), about 6-8% of the sampling SE at the default 2,000
   trees, and fall with the number of trees.
3. **No claim of identity.** The engines are independent implementations;
   the seed means are not pinned to agree within their combined Monte
   Carlo error (at 8,000 trees, where that error is smallest, the gap is at
   most 0.025 sampling SE with |z| <= 2.6), so the
   grade is equivalence, not parity.

Seeds are spaced 1e5 apart on both sides. grf forests grown from
*consecutive* seeds share most of their random draws, so a consecutive-seed
fixture understates grf's Monte Carlo SD several-fold; an earlier version of
this file drew R seeds ``1000 + k`` and concluded, wrongly, that StatsPAI's
forest was several times noisier than grf's.

The margin ``delta`` was fixed after inspecting the grf_data fixture on an
earlier engine, not pre-registered; the module-13 dataset and the spaced-seed
rerun were both run after it was fixed.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd
import pytest

_FIX = pathlib.Path(__file__).parent / "_fixtures"
DATASETS = {
    "grf_data": ("grf_seed_mc_py.json", "grf_seed_mc_R.json"),
    "module13": ("grf_seed_mc_m13_py.json", "grf_seed_mc_m13_R.json"),
}
TREES = ("trees_500", "trees_2000", "trees_8000")
DELTA_SAMPLING_SE = 0.1
Z_TOST = 1.6448536269514722  # one-sided 5%


def _load(ds):
    py_file, r_file = DATASETS[ds]
    return (
        json.loads((_FIX / py_file).read_text(encoding="utf-8")),
        json.loads((_FIX / r_file).read_text(encoding="utf-8")),
    )


def _stats(py, r, trees, stat):
    p = np.array([row[stat] for row in py[trees]])
    q = np.array([row[stat] for row in r[trees]])
    diff = p.mean() - q.mean()
    se_diff = np.sqrt(p.var(ddof=1) / p.size + q.var(ddof=1) / q.size)
    sampling_se = float(np.mean([row["ate_se"] for row in r[trees]]))
    return diff, se_diff, p.std(ddof=1), q.std(ddof=1), sampling_se


@pytest.mark.parametrize("ds", sorted(DATASETS))
@pytest.mark.parametrize("stat", ["ate", "att"])
@pytest.mark.parametrize("trees", TREES)
def test_equivalent_within_a_tenth_of_the_sampling_se(ds, stat, trees):
    py, r = _load(ds)
    diff, se_diff, _, _, sampling_se = _stats(py, r, trees, stat)
    delta = DELTA_SAMPLING_SE * sampling_se
    # TOST: both one-sided nulls |diff| >= delta rejected at 5%.
    assert abs(diff) + Z_TOST * se_diff < delta, (ds, stat, trees, diff, delta)


@pytest.mark.parametrize("ds", sorted(DATASETS))
@pytest.mark.parametrize("trees", TREES)
def test_engines_have_the_same_algorithmic_noise(ds, trees):
    """Claim 2: seed-to-seed SDs within a factor of two of each other."""
    py, r = _load(ds)
    _, _, sd_py, sd_r, _ = _stats(py, r, trees, "ate")
    assert 0.5 < sd_py / sd_r < 2.0, (ds, trees, sd_py, sd_r)


@pytest.mark.parametrize("ds", sorted(DATASETS))
def test_noise_falls_with_trees(ds):
    py, r = _load(ds)
    sds = {t: _stats(py, r, t, "ate")[2:4] for t in TREES}
    for side in (0, 1):
        assert sds["trees_8000"][side] < sds["trees_500"][side] / 2


def test_noise_is_a_small_fraction_of_sampling_error_at_2000_trees():
    """At the default 2,000 trees both engines' seed-to-seed SD stays below
    a tenth of the sampling SE on both datasets."""
    for ds in DATASETS:
        py, r = _load(ds)
        _, _, sd_py, sd_r, sampling_se = _stats(py, r, "trees_2000", "ate")
        assert sd_py < 0.1 * sampling_se
        assert sd_r < 0.1 * sampling_se


@pytest.mark.parametrize("ds", sorted(DATASETS))
def test_fixtures_use_spaced_seeds(ds):
    """Consecutive grf seeds share most of their draws; the fixtures must not."""
    py, r = _load(ds)
    for side in (py, r):
        seeds = [row["seed"] for row in side["trees_2000"]]
        assert min(np.diff(seeds)) >= 100000


@pytest.mark.slow
def test_frozen_python_draws_are_current():
    """The frozen StatsPAI draws must be what the current engine returns.

    Refits the first two 2,000-tree seeds; an engine change that moves
    them means the fixture must be regenerated (and the conclusions
    re-checked), not that the tolerance should widen.
    """
    import statspai as sp

    py, _ = _load("grf_data")
    df = pd.read_csv(_FIX / "grf_data.csv")
    for row in py["trees_2000"][:2]:
        cf = sp.causal_forest(
            "y ~ W | X1 + X2 + X3 + X4 + X5",
            data=df,
            n_estimators=2000,
            random_state=row["seed"],
            discrete_treatment=True,
        )
        ate = cf.average_treatment_effect(target_sample="all")
        assert float(ate["estimate"]) == pytest.approx(row["ate"], abs=1e-12)

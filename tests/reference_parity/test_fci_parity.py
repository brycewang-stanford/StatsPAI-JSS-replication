"""Analytical parity: sp.fci recovers known PAG structures.

FCI (Fast Causal Inference; Spirtes, Glymour & Scheines 2000) learns a PAG
over the Markov equivalence class allowing latent confounders. On known
linear-Gaussian DGPs the output is checkable exactly:

* chain X -> Y -> Z: skeleton X--Y--Z with no X--Z edge, all endpoint marks
  circles (``o-o``), and separating set {Y} for (X, Z);
* collider X -> Z <- Y: both edges oriented INTO Z (``o->``), no X--Y edge,
  and the empty separating set for (X, Y).

Deterministic given the seeded data (FCI itself is deterministic), so the
assertions are exact. Analytical evidence tier (known-truth structure recovery
on a deterministic DGP; no cross-package reference).
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp

N = 5000


def test_chain_skeleton_sepset_and_circle_marks():
    rng = np.random.default_rng(0)
    X = rng.normal(0, 1, N)
    Y = 0.8 * X + rng.normal(0, 1, N)
    Z = 0.8 * Y + rng.normal(0, 1, N)
    r = sp.fci(pd.DataFrame({"X": X, "Y": Y, "Z": Z}))
    assert sorted(r.edges) == [("X", "o-o", "Y"), ("Y", "o-o", "Z")]
    sepsets = dict(r.separating_sets)
    assert sepsets[("X", "Z")] == {"Y"}


def test_collider_oriented_into_z():
    rng = np.random.default_rng(0)
    X = rng.normal(0, 1, N)
    Y = rng.normal(0, 1, N)
    Z = 0.8 * X + 0.8 * Y + rng.normal(0, 1, N)
    r = sp.fci(pd.DataFrame({"X": X, "Y": Y, "Z": Z}))
    # v-structure identified: arrowheads into Z, circles at X / Y ends.
    assert sorted(r.edges) == [("X", "o->", "Z"), ("Y", "o->", "Z")]
    # X and Y are marginally independent: empty separating set.
    sepsets = dict(r.separating_sets)
    assert sepsets[("X", "Y")] == set()


def test_collider_never_orients_out_of_z():
    # Across seeds, finite-sample CI noise may keep an extra edge (alpha-level
    # false positive), but no seed may orient an arrowhead OUT of the collider.
    for seed in range(4):
        rng = np.random.default_rng(seed)
        X = rng.normal(0, 1, N)
        Y = rng.normal(0, 1, N)
        Z = 0.8 * X + 0.8 * Y + rng.normal(0, 1, N)
        r = sp.fci(pd.DataFrame({"X": X, "Y": Y, "Z": Z}))
        for a, mark, b in r.edges:
            if mark == "o->":
                assert b == "Z"  # arrowheads only ever point into the collider

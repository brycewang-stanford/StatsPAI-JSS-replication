"""Inputs for the causal-survival score-operator fixture (T2).

The censoring-adjusted numerator of the causal survival forest (Cui,
Kosorok, Sverdrup, Wager and Zhu 2023, eq. 11) is a deterministic map from
nuisance curves to per-row scores.  This script draws a censored sample
(times rounded to 3 decimals, so event and censoring times tie, and many
rows run past the horizon) and builds valid step-function nuisance curves
on the grid of distinct ``min(Y, h)``: event curves that only drop at event
times, a censoring curve that only drops at censoring times, a propensity.
The R companion evaluates grf's score map on exactly these inputs.

    python tests/reference_parity/_fixtures/_generate_csf_psi_inputs.py
    Rscript tests/reference_parity/_fixtures/_generate_csf_psi.R
"""

from __future__ import annotations

import json
import pathlib

import numpy as np

OUT = pathlib.Path(__file__).parent / "csf_psi_inputs.json"


def _step(rate: np.ndarray, grid: np.ndarray, jumps: np.ndarray) -> np.ndarray:
    """exp(-cumulative hazard), piecewise constant between jump times."""
    dt = np.diff(np.concatenate([[0.0], grid]))
    H = np.cumsum(np.outer(rate, dt), axis=1)
    out = np.ones_like(H)
    last = np.zeros(rate.size)
    for k in range(grid.size):
        if jumps[k]:
            last = H[:, k]
        out[:, k] = np.exp(-last)
    return out


def _round(curves: np.ndarray) -> list:
    """12 significant digits: both sides read the same values, so the
    comparison stays exact while the fixture stays small."""
    return [[float(f"{v:.12g}") for v in row] for row in curves]


def main() -> None:
    rng = np.random.default_rng(4)
    n, h = 120, 1.2
    X = rng.normal(size=(n, 2))
    W = rng.binomial(1, 0.5, n).astype(float)
    T = rng.exponential(1 / np.exp(0.5 * X[:, 0] - 0.4 * W))
    C = rng.exponential(2.0, n)
    Y = np.round(np.minimum(T, C), 3)
    D = (T <= C).astype(float)
    Dh = (D > 0.5) | (Y >= h)
    grid = np.unique(np.minimum(Y, h))
    ev = np.isin(grid, np.minimum(Y, h)[Dh])
    ce = np.isin(grid, Y[(D < 0.5) & (Y < h)])
    lam = np.exp(0.5 * X[:, 0])
    payload = {
        "horizon": h,
        "Y": Y.tolist(),
        "D": D.tolist(),
        "W": W.tolist(),
        "e": [float(f"{v:.12g}") for v in 1 / (1 + np.exp(-0.3 * X[:, 1]))],
        "grid": grid.tolist(),
        "S1": _round(_step(lam * np.exp(-0.4), grid, ev)),
        "S0": _round(_step(lam, grid, ev)),
        "C": _round(_step(0.5 * np.exp(0.2 * X[:, 1]), grid, ce)),
    }
    OUT.write_text(json.dumps(payload), encoding="utf-8")
    print(f"wrote {OUT.name}")


if __name__ == "__main__":
    main()

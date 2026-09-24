"""Write the shared input CSVs for the ``ml_causal`` parity family.

Run once from the repository root::

    python tests/reference_parity/_fixtures/_generate_ml_causal_data.py

Three datasets, each written with full float precision so that every
reference script (R ``grf`` / ``GenericML`` / ``ddml``, Python ``obp`` /
``DoubleML``) and the StatsPAI tests read identical bytes.

``ml_causal_cate.csv`` (n = 1000)
    Observational binary-treatment design for the ``grf`` post-fit
    operators and the Chernozhukov-Demirer-Duflo-Fernandez-Val BLP /
    GATES regressions. Propensity ``plogis(0.5 x1 - 0.4 x2)`` stays inside
    (0.1, 0.9) on this draw; CATE ``1 + x1 + 0.5 * 1{x3 > 0}``.

``ml_causal_ope.csv`` (n = 2000, K = 3 actions)
    Logged contextual-bandit data: the behaviour policy (softmax of a
    linear index), the logged action and reward, an evaluation policy and
    a deterministic reward-model matrix ``q0..q2`` (a fixed linear
    function of ``x``, deliberately misspecified so that DM, IPS and DR
    give different numbers).

``ml_causal_panel.csv`` (60 units x 6 periods, balanced) and
``ml_causal_panel_unbal.csv`` (the same panel with 37 rows removed)
    Static panel with unit effects correlated with the treatment. The
    ``fold`` column is a unit-level 5-fold assignment (12 units per fold),
    used verbatim by every side so the cross-fitting partition is shared.
"""

from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).parent


def _cate() -> pd.DataFrame:
    rng = np.random.default_rng(20260918)
    n = 1000
    X = rng.standard_normal((n, 5))
    e = 1.0 / (1.0 + np.exp(-(0.5 * X[:, 0] - 0.4 * X[:, 1])))
    w = rng.binomial(1, e)
    tau = 1.0 + X[:, 0] + 0.5 * (X[:, 2] > 0)
    y = X[:, 1] + 0.5 * X[:, 3] + tau * w + rng.standard_normal(n)
    out = pd.DataFrame({"y": y, "w": w})
    for j in range(5):
        out[f"x{j + 1}"] = X[:, j]
    return out


def _ope() -> pd.DataFrame:
    rng = np.random.default_rng(918)
    n, K = 2000, 3
    X = rng.standard_normal((n, 2))
    idx_b = np.column_stack([0.2 * X[:, 0], -0.3 * X[:, 1], 0.1 * X[:, 0] * X[:, 1]])
    pb = np.exp(idx_b)
    pb /= pb.sum(axis=1, keepdims=True)
    A = np.array([rng.choice(K, p=pb[i]) for i in range(n)])
    mu = np.column_stack(
        [1.0 + 0.5 * X[:, 0], 0.5 + X[:, 1] ** 2, 0.8 - 0.3 * X[:, 0] + 0.2 * X[:, 1]]
    )
    R = mu[np.arange(n), A] + rng.normal(scale=0.5, size=n)
    idx_e = np.column_stack([1.2 * X[:, 0], 0.8 * X[:, 1], np.zeros(n)])
    pe = np.exp(idx_e)
    pe /= pe.sum(axis=1, keepdims=True)
    # Reward model: fixed, misspecified linear predictions.
    q = np.column_stack(
        [0.9 + 0.45 * X[:, 0], 1.4 + 0.1 * X[:, 1], 0.75 - 0.25 * X[:, 0]]
    )
    out = pd.DataFrame({"x1": X[:, 0], "x2": X[:, 1], "a": A, "r": R})
    for k in range(K):
        out[f"pb{k}"] = pb[:, k]
    for k in range(K):
        out[f"pe{k}"] = pe[:, k]
    for k in range(K):
        out[f"q{k}"] = q[:, k]
    return out


def _panel() -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(6060)
    G, T = 60, 6
    rows = []
    for i in range(G):
        a_i = rng.normal()
        for t in range(T):
            x = rng.standard_normal(3)
            d = 0.5 * x[0] - 0.3 * x[1] + 0.8 * a_i + 0.1 * t + rng.normal()
            y = 0.7 * d + x[0] + 0.5 * x[1] ** 2 - 0.4 * x[2] + a_i + 0.2 * t
            y += rng.normal()
            rows.append(
                {"unit": i, "time": t, "y": y, "d": d,
                 "x1": x[0], "x2": x[1], "x3": x[2]}
            )
    bal = pd.DataFrame(rows)
    perm = rng.permutation(G)
    fold_of_unit = np.empty(G, dtype=int)
    for k, units in enumerate(np.array_split(perm, 5)):
        fold_of_unit[units] = k
    bal["fold"] = fold_of_unit[bal["unit"].to_numpy()]
    drop = rng.choice(len(bal), size=37, replace=False)
    unbal = bal.drop(index=drop).reset_index(drop=True)
    return bal, unbal


def main() -> None:
    _cate().to_csv(HERE / "ml_causal_cate.csv", index=False, float_format="%.17g")
    _ope().to_csv(HERE / "ml_causal_ope.csv", index=False, float_format="%.17g")
    bal, unbal = _panel()
    bal.to_csv(HERE / "ml_causal_panel.csv", index=False, float_format="%.17g")
    unbal.to_csv(HERE / "ml_causal_panel_unbal.csv", index=False, float_format="%.17g")


if __name__ == "__main__":
    main()

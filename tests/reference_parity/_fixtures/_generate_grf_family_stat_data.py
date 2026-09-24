"""Designs with known truth for the GRF-family statistical fixture (T3).

Written to ``grf_family_stat_data.csv`` (``design`` column), each with the
true conditional quantity alongside the data:

* ``iv`` (n = 2000): binary instrument, endogenous binary treatment,
  ``tau(x) = 1 + max(x1, 0) - 0.5 x2`` (the conditional LATE).
* ``multiarm`` (n = 2000): three arms with covariate-dependent assignment,
  ``tau_1(x) = 1 + max(x1, 0)``, ``tau_2(x) = -0.5 + 0.5 x2``.
* ``lm`` (n = 2000): ``Y = x3 + h1(x) W1 + h2(x) W2 + e`` with
  ``h1 = 1 + x1``, ``h2 = -1 + 0.5 max(x2, 0)``.
* ``csf`` (n = 2000): exponential event times, confounded treatment,
  independent censoring; truth is the RMST difference at ``h = 1.5``.
* ``survival`` (n = 1000): ``S(t | x) = exp(-exp(0.8 x1) t)``.
* ``quantile`` (n = 1000): ``Y = x1 + (1 + 1{x2 > 0}) e``.

    python tests/reference_parity/_fixtures/_generate_grf_family_stat_data.py
    Rscript tests/reference_parity/_fixtures/_generate_grf_family_stat.R
"""

from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd

OUT = pathlib.Path(__file__).parent / "grf_family_stat_data.csv"
H = 1.5


def _rmst(rate: np.ndarray, h: float) -> np.ndarray:
    return (1 - np.exp(-rate * h)) / rate


def _frame(design: str, X: np.ndarray, **cols: np.ndarray) -> pd.DataFrame:
    df = pd.DataFrame(X, columns=[f"x{j + 1}" for j in range(X.shape[1])])
    df.insert(0, "design", design)
    for k, v in cols.items():
        df[k] = v
    return df


def main() -> None:
    rng = np.random.default_rng(907)
    frames = []

    n = 2000
    X = rng.normal(size=(n, 5))
    Z = rng.binomial(1, 0.5, n)
    U = rng.normal(size=n)
    W = 0.8 * Z + 0.5 * X[:, 1] + U + rng.normal(scale=0.5, size=n) > 0.4
    tau = 1 + np.maximum(X[:, 0], 0) - 0.5 * X[:, 1]
    Y = tau * W + X[:, 2] + U + rng.normal(size=n)
    frames.append(_frame("iv", X, Y=Y, W=W.astype(int), Z=Z, tau=tau))

    X = rng.normal(size=(n, 5))
    logits = np.column_stack([np.zeros(n), 0.5 * X[:, 1], -0.5 * X[:, 1]])
    p = np.exp(logits) / np.exp(logits).sum(axis=1, keepdims=True)
    A = (rng.random(n)[:, None] > np.cumsum(p, axis=1)).sum(axis=1)
    t1 = 1 + np.maximum(X[:, 0], 0)
    t2 = -0.5 + 0.5 * X[:, 1]
    Y = X[:, 2] + t1 * (A == 1) + t2 * (A == 2) + rng.normal(size=n)
    frames.append(_frame("multiarm", X, Y=Y, W=A, tau=t1, tau2=t2))

    X = rng.normal(size=(n, 5))
    W1 = rng.normal(size=n)
    W2 = rng.normal(size=n)
    h1 = 1 + X[:, 0]
    h2 = -1 + 0.5 * np.maximum(X[:, 1], 0)
    Y = X[:, 2] + h1 * W1 + h2 * W2 + rng.normal(size=n)
    frames.append(_frame("lm", X, Y=Y, W=W1, W2=W2, tau=h1, tau2=h2))

    X = rng.normal(size=(n, 5))
    e = 1 / (1 + np.exp(-0.5 * X[:, 1]))
    W = rng.binomial(1, e)
    r0 = np.exp(0.3 * X[:, 1])
    r1 = r0 * np.exp(-0.7 * (X[:, 0] > 0))
    T = rng.exponential(1 / np.where(W == 1, r1, r0))
    C = rng.exponential(3.0, n)
    frames.append(
        _frame(
            "csf",
            X,
            Y=np.minimum(T, C),
            W=W,
            D=(T <= C).astype(int),
            tau=_rmst(r1, H) - _rmst(r0, H),
        )
    )

    n = 1000
    X = rng.normal(size=(n, 5))
    rate = np.exp(0.8 * X[:, 0])
    T = rng.exponential(1 / rate)
    C = rng.exponential(2.0, n)
    frames.append(
        _frame("survival", X, Y=np.minimum(T, C), D=(T <= C).astype(int), tau=rate)
    )

    X = rng.normal(size=(n, 5))
    sd = 1 + (X[:, 1] > 0)
    frames.append(_frame("quantile", X, Y=X[:, 0] + sd * rng.normal(size=n), tau=sd))

    out = pd.concat(frames, ignore_index=True)
    out.to_csv(OUT, index=False, float_format="%.10g")
    print(f"wrote {OUT.name} ({len(out)} rows)")


if __name__ == "__main__":
    main()

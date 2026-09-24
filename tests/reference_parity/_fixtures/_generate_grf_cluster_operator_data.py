"""Data for the clustered GRF *operator* parity fixture.

Writes ``grf_cluster_operator_data.csv``: a clustered design (150 clusters of
unequal size) with a binary treatment, plus the out-of-bag CATE predictions
and nuisances of an ``sp.causal_forest(clusters=...)`` fit.  The R companion
``_generate_grf_cluster_operator.R`` injects exactly these vectors into a
``grf`` forest object and records what grf's inference functions return, so
the Python operators can be pinned to machine precision independently of any
forest randomness.

    PYTHONPATH=src python tests/reference_parity/_fixtures/_generate_grf_cluster_operator_data.py
"""

from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd

import statspai as sp

OUT = pathlib.Path(__file__).parent / "grf_cluster_operator_data.csv"


def main() -> None:
    rng = np.random.default_rng(20260916)
    sizes = rng.integers(3, 13, size=150)
    cluster = np.repeat(np.arange(150), sizes)
    n = cluster.size
    X = rng.normal(size=(n, 3))
    u = rng.normal(size=150)[cluster]
    e = 1.0 / (1.0 + np.exp(-(0.6 * X[:, 0] - 0.4 * X[:, 1])))
    W = (rng.uniform(size=n) < e).astype(float)
    tau = 1.0 + X[:, 0] - 0.5 * X[:, 2]
    Y = X[:, 1] + u + tau * W + rng.normal(size=n)
    cf = sp.causal_forest(
        Y=Y, T=W, X=X, clusters=cluster, n_estimators=1000, random_state=7
    )
    df = pd.DataFrame(X, columns=["x1", "x2", "x3"])
    df["W"] = W
    df["Y"] = Y
    df["cluster"] = cluster
    df["Y_hat"] = cf._m_insample
    df["W_hat"] = cf._e_insample
    df["tau_oob"] = cf._oob_tau
    df["vcov_weight"] = rng.uniform(0.5, 2.0, size=n)
    df.to_csv(OUT, index=False, float_format="%.17g")
    print(f"wrote {OUT} ({n} rows)")


if __name__ == "__main__":
    main()

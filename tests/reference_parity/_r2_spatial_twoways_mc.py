"""Known-truth Monte Carlo for two-way spatial-panel lag transforms (r2_spatial).

DGP: y_t = (I - rho W)^{-1} (x_t beta + mu + alpha_t 1 + e_t), rho = 0.4,
beta = 1, large and trending time effects alpha_t, x correlated with both
effects, row-standardised W that is NOT column-stochastic (usaww, N = 48;
clustered 5-NN, N = 200 / 800). Estimators (concentrated ML):
  WQ  W(Qy) lag, T log|I - rho W|, NT       -- splm / sp.spatial_panel default
  QW  Q(Wy) lag, T log|I - rho W|, NT       -- twoways_lag="within" (Lee-Yu eq. 21)
  LY  Q(Wy) lag, (T-1)[log|I - rho W| - log(1 - rho)], (N-1)(T-1)
      -- Lee & Yu (2010) transformation approach, eq. (24)
Usage: python tests/reference_parity/_r2_spatial_twoways_mc.py [R=1000]
Not a test (minutes of runtime); results are recorded in the campaign notes.
"""

import pathlib
import sys

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

FX = str(pathlib.Path(__file__).resolve().parent / "_fixtures") + "/"


def usaww():
    W = pd.read_csv(FX + "spatial_survey_usaww.csv", index_col=0).to_numpy(float)
    return W / W.sum(1, keepdims=True)


def knn(N, k=5, seed=0):
    rng = np.random.default_rng(seed)
    p = rng.uniform(size=(N, 2))
    p[: N // 5] *= 0.3  # clustered -> uneven column sums
    D = np.linalg.norm(p[:, None] - p[None], axis=2)
    np.fill_diagonal(D, np.inf)
    W = np.zeros((N, N))
    idx = np.argsort(D, 1)[:, :k]
    for i in range(N):
        W[i, idx[i]] = 1
    return W / W.sum(1, keepdims=True)


Q = lambda A: A - A.mean(1, keepdims=True) - A.mean(0, keepdims=True) + A.mean()


def est(Y, X, W, ev, variant):
    N, T = Y.shape
    y = Q(Y).ravel("F")
    x = Q(X).ravel("F")[:, None]
    wy = (W @ Q(Y)).ravel("F") if variant == "WQ" else Q(W @ Y).ravel("F")
    M = lambda v: v - x @ np.linalg.lstsq(x, v, rcond=None)[0]
    e0, e1 = M(y), M(wy)
    a, b, c = e0 @ e0, e0 @ e1, e1 @ e1
    nobs, tj = ((N - 1) * (T - 1), T - 1) if variant == "LY" else (N * T, T)

    def nll(r):
        j = np.sum(np.log(1 - r * ev)) - (np.log(1 - r) if variant == "LY" else 0)
        return nobs / 2 * np.log(a - 2 * r * b + r * r * c) - tj * j

    r = minimize_scalar(
        nll, bounds=(-0.95, 0.95), method="bounded", options={"xatol": 1e-10}
    ).x
    beta = np.linalg.lstsq(x, y - r * wy, rcond=None)[0][0]
    return r, beta


def run(W, T, R, rho=0.4, beta=1.0, seed=1):
    N = W.shape[0]
    ev = np.real(np.linalg.eigvals(W))
    rng = np.random.default_rng(seed)
    Ainv = np.linalg.inv(np.eye(N) - rho * W)
    out = {v: [] for v in ("WQ", "QW", "LY")}
    for _ in range(R):
        mu = rng.normal(0, 2, N)
        al = 5 * rng.normal(size=T) + np.arange(T)
        X = rng.normal(size=(N, T)) + mu[:, None] * 0.5 + al[None, :] * 0.3
        E = rng.normal(size=(N, T))
        Y = Ainv @ (X * beta + mu[:, None] + al[None, :] + E)
        for v in out:
            out[v].append(est(Y, X, W, ev, v))
    return {v: np.array(o) for v, o in out.items()}


R = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
cases = [
    ("usaww N=48", usaww(), 5),
    ("usaww N=48", usaww(), 17),
    ("usaww N=48", usaww(), 50),
    ("kNN5 N=200", knn(200), 5),
    ("kNN5 N=800", knn(800), 5),
]
print("rho0=0.4 beta0=1; R=%d" % R)
for lab, W, T in cases:
    cs = W.sum(0)
    o = run(W, T, R if W.shape[0] < 800 else R // 4)
    for v, a in o.items():
        print(
            f"{lab:12s} T={T:3d} colsum[{cs.min():.2f},{cs.max():.2f}] {v}: rho mean-bias {a[:,0].mean()-0.4:+.5f} sd {a[:,0].std():.5f} mcse {a[:,0].std()/np.sqrt(len(a)):.5f} | beta bias {a[:,1].mean()-1:+.5f} sd {a[:,1].std():.5f}",
            flush=True,
        )

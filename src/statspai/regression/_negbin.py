"""Joint (beta, ln-dispersion) likelihood derivatives for negative binomial.

Stata's ``nbreg`` estimates ``(beta, lnalpha)`` -- or ``(beta, lndelta)``
under ``dispersion(constant)`` -- jointly, and every standard error it
reports comes from that joint parameter vector:

* ``vce(oim)``: the inverse observed information of the joint vector, whose
  beta block is *not* the ``(X' W X)^{-1}`` of the IRLS weights because the
  observed cross-derivative between beta and the dispersion is non-zero;
* ``vce(robust)`` / ``vce(cluster)``: the sandwich built from the joint
  per-observation scores, with Stata's N/(N-1) and G/(G-1) factors.

``sp.nbreg`` previously used the IRLS weight matrix as the bread and the
Poisson residual ``y - mu`` as the score.  The NB2 score for beta is
``x (y - mu) / (1 + alpha mu)``; omitting the denominator inflated the robust
and cluster standard errors by ~5% on moderately overdispersed data.

NB2 derivatives are analytic.  NB1 scores use the complex-step derivative
(exact to rounding) and its Hessian a central difference of those scores.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Tuple

import numpy as np
from scipy import special

__all__ = ["NegBinJoint", "negbin_joint", "nb1_obs_loglik", "nb2_obs_loglik"]


def nb2_obs_loglik(
    theta: np.ndarray, y: np.ndarray, X: np.ndarray, offset: np.ndarray
) -> np.ndarray:
    """Per-observation NB2 log-likelihood at ``theta = (beta, ln alpha)``.

    ``Var(y) = mu + alpha mu^2``. Complex-step safe.
    """
    mu = np.exp(X @ theta[:-1] + offset)
    m = np.exp(-theta[-1])
    return (
        special.loggamma(y + m)
        - special.loggamma(m)
        - special.gammaln(y + 1)
        + m * np.log(m / (m + mu))
        + y * np.log(mu / (m + mu))
    )


def nb1_obs_loglik(
    theta: np.ndarray, y: np.ndarray, X: np.ndarray, offset: np.ndarray
) -> np.ndarray:
    """Per-observation NB1 log-likelihood at ``theta = (beta, ln delta)``.

    ``Var(y) = mu (1 + delta)``, i.e. size ``mu / delta`` and success
    probability ``1 / (1 + delta)``. Complex-step safe.
    """
    mu = np.exp(X @ theta[:-1] + offset)
    delta = np.exp(theta[-1])
    r = mu / delta
    log1pd = np.log(1.0 + delta)
    return (
        special.loggamma(y + r)
        - special.loggamma(r)
        - special.gammaln(y + 1)
        - r * log1pd
        + y * (theta[-1] - log1pd)
    )


def _nb2_scores_hessian(
    theta: np.ndarray, y: np.ndarray, X: np.ndarray, offset: np.ndarray, w: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """Analytic NB2 per-observation scores ``(n, k+1)`` and total Hessian."""
    mu = np.exp(X @ theta[:-1] + offset)
    a = np.exp(theta[-1])
    m = 1.0 / a
    d = 1.0 + a * mu
    # dl/dm and d2l/dm2, with m = 1/alpha.
    dl_dm = (
        special.digamma(y + m)
        - special.digamma(m)
        + np.log(m / (m + mu))
        + (mu - y) / (m + mu)
    )
    d2l_dm2 = (
        special.polygamma(1, y + m)
        - special.polygamma(1, m)
        + 1.0 / m
        - 1.0 / (m + mu)
        - (mu - y) / (m + mu) ** 2
    )
    scores = np.column_stack([X * ((y - mu) / d)[:, None], -m * dl_dm]) * w[:, None]
    k = X.shape[1]
    H = np.empty((k + 1, k + 1))
    H[:k, :k] = -(X * (w * mu * (1.0 + a * y) / d**2)[:, None]).T @ X
    cross = -(X * (w * a * mu * (y - mu) / d**2)[:, None]).sum(axis=0)
    H[:k, k] = cross
    H[k, :k] = cross
    H[k, k] = float(np.sum(w * (m * dl_dm + m**2 * d2l_dm2)))
    return scores, H


def _complex_step_scores(
    loglik: Callable[..., np.ndarray],
    theta: np.ndarray,
    y: np.ndarray,
    X: np.ndarray,
    offset: np.ndarray,
    h: float = 1e-30,
) -> np.ndarray:
    k = theta.size
    out = np.empty((y.size, k))
    for j in range(k):
        tc = theta.astype(complex)
        tc[j] += 1j * h
        out[:, j] = loglik(tc, y, X, offset).imag / h
    return out


def _nb1_scores_hessian(
    theta: np.ndarray, y: np.ndarray, X: np.ndarray, offset: np.ndarray, w: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    def total_score(t: np.ndarray) -> np.ndarray:
        return (_complex_step_scores(nb1_obs_loglik, t, y, X, offset) * w[:, None]).sum(
            axis=0
        )

    scores = _complex_step_scores(nb1_obs_loglik, theta, y, X, offset) * w[:, None]
    k = theta.size
    H = np.empty((k, k))
    for j in range(k):
        step = 1e-5 * max(1.0, abs(float(theta[j])))
        tp, tm = theta.copy(), theta.copy()
        tp[j] += step
        tm[j] -= step
        H[:, j] = (total_score(tp) - total_score(tm)) / (2.0 * step)
    return scores, 0.5 * (H + H.T)


@dataclass(frozen=True)
class NegBinJoint:
    """Joint NegBin optimum and the pieces of its variance.

    ``bread`` is the inverse observed information of ``theta`` and ``scores``
    the per-observation score contributions, both over ``(beta, ln
    dispersion)``; pass them to ``core._vcov.ml_vcov``.
    """

    beta: np.ndarray
    dispersion: float
    mu: np.ndarray
    theta: np.ndarray
    scores: np.ndarray
    bread: np.ndarray
    gradient_norm: float
    newton_steps: int


def negbin_joint(
    y: np.ndarray,
    X: np.ndarray,
    offset: Optional[np.ndarray],
    beta: np.ndarray,
    dispersion: float,
    *,
    weights: Optional[np.ndarray] = None,
    nb2: bool = True,
    maxiter: int = 50,
) -> NegBinJoint:
    """Polish a NegBin fit to the joint MLE and return its variance pieces.

    Starting from the profile-likelihood estimates ``(beta, dispersion)``,
    runs step-halving Newton iterations on the joint log-likelihood until
    the step is below ``1e-10`` relative. The profile fit stops on a
    relative-change rule for the dispersion alone, which leaves the joint
    gradient at a level visible in the fifth significant digit of the
    standard errors; Newton removes it. When the dispersion sits at its
    lower boundary (``<= 1e-8``, i.e. the data are not overdispersed) the
    log-dispersion is unbounded below and no polishing is attempted.
    """
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    n = y.shape[0]
    offset = np.zeros(n) if offset is None else np.asarray(offset, dtype=float)
    w = np.ones(n) if weights is None else np.asarray(weights, dtype=float)
    loglik = nb2_obs_loglik if nb2 else nb1_obs_loglik
    parts = _nb2_scores_hessian if nb2 else _nb1_scores_hessian

    def total_ll(t: np.ndarray) -> float:
        with np.errstate(all="ignore"):
            return float(np.sum(w * np.real(loglik(t, y, X, offset))))

    theta = np.append(
        np.asarray(beta, dtype=float), np.log(max(float(dispersion), 1e-300))
    )
    scores, H = parts(theta, y, X, offset, w)
    steps = 0
    if dispersion > 1e-8:
        ll = total_ll(theta)
        for _ in range(maxiter):
            try:
                step = np.linalg.solve(H, scores.sum(axis=0))
            except np.linalg.LinAlgError:
                break
            candidate = theta - step
            ll_new = total_ll(candidate)
            halvings = 0
            while not (np.isfinite(ll_new) and ll_new >= ll - 1e-12 * abs(ll)):
                if halvings == 40:
                    break
                step = step / 2.0
                candidate = theta - step
                ll_new = total_ll(candidate)
                halvings += 1
            if halvings == 40:
                break
            theta, ll = candidate, ll_new
            scores, H = parts(theta, y, X, offset, w)
            steps += 1
            if np.max(np.abs(step)) < 1e-10 * (1.0 + np.max(np.abs(theta))):
                break

    try:
        bread = np.linalg.inv(-H)
    except np.linalg.LinAlgError:
        bread = np.linalg.pinv(-H)
    beta_hat = theta[:-1]
    return NegBinJoint(
        beta=beta_hat,
        dispersion=float(np.exp(theta[-1])),
        mu=np.exp(X @ beta_hat + offset),
        theta=theta,
        scores=scores,
        bread=bread,
        gradient_norm=float(np.linalg.norm(scores.sum(axis=0))),
        newton_steps=steps,
    )

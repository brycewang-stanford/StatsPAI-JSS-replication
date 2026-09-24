"""Multiscale GWR (MGWR): one bandwidth per regression coefficient.

The default fit reproduces the authors' reference implementation, PySAL
``mgwr`` (``Sel_BW(multi=True).search()`` followed by ``MGWR.fit()``),
step for step:

- **Initialisation.** A GWR with all covariates at the bandwidth chosen by
  ``mgwr``'s golden-section search (``init`` overrides it).
- **Back-fitting.** Gauss-Seidel sweeps over the covariates. In each sweep
  covariate ``j``'s partial residual is smoothed by a one-covariate GWR
  (no intercept) whose bandwidth is re-selected by the same search, with
  bounds ``[40 + 2, n]`` (adaptive) unless given. Once the bandwidth vector
  has been unchanged for ``bws_same_times`` consecutive sweeps it is
  frozen. Iteration stops when the score of change (SOC)
  ``sqrt(sum((f_new - f_old)^2) / n / sum(yhat_new^2))`` falls below
  ``tol`` (``rss_score=True``: the relative change of the RSS).
- **Golden section** (``mgwr.search.golden_section``): ``delta = 0.38197``,
  probes rounded to integers for adaptive bandwidths, a memo of evaluated
  bandwidths, stop when the criterion difference of the two probes is
  ``<= search_tol`` (1e-6) or after ``search_max_iter`` probes; the
  returned bandwidth is rounded to 2 decimals. Default bounds: ``[40 + 2 p,
  n]`` (adaptive, ``p`` covariates in the model being searched) or
  ``[min distance / 2, 2 max distance]`` (fixed).
- **Kernel.** ``mgwr.kernels.Kernel``: the adaptive scale is the distance
  to the ``int(bw)``-th nearest point (the point itself counted)
  multiplied by ``eps = 1.0000001``; only the bisquare is truncated.
- **Inference** (``MGWR.fit``): the back-fitting is replayed on the identity
  matrix with the recorded bandwidth history, giving the operators
  ``R_j`` with ``f_j = R_j y``. ``ENP_j = tr(R_j)``, ``tr(S) = sum ENP_j``,
  ``sigma^2 = RSS / (n - tr(S))``, ``Var(beta_j(i)) = sigma^2 * sum_m
  (R_j[i, m] / x_ij)^2``, and ``AICc = -2 llf + 2 n (tr(S) + 1) /
  (n - tr(S) - 2)``. The replay has exactly as many sweeps as the
  bandwidth search, so it is the finite-iteration operator ``mgwr``
  reports, not the limit of the back-fitting.

With ``bws=`` the bandwidths are fixed and nothing is searched: the
back-fitting then solves the additive model at those bandwidths, which is
also ``GWmodel::gwr.multiscale(bws0 = bws, bw.seled = TRUE)``'s fixed
point when ``kernel_eps=1.0`` (GWmodel's kernel has no ``eps``).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Tuple, Union

import numpy as np

from ..._result_serialize import ResultProtocolMixin
from ...exceptions import MethodIncompatibility, NumericalInstability
from .gwr import KernelName, _kernel

MGWRCriterion = Literal["AICc", "AIC", "BIC", "CV"]

_MGWR_EPS = 1.0000001  # mgwr.kernels.Kernel(eps=1.0000001)
_GOLDEN_DELTA = 0.38197  # mgwr.sel_bw.Sel_BW._bw: 1 - (sqrt(5) - 1) / 2


@dataclass
class MGWRResult(ResultProtocolMixin):
    params: np.ndarray  # (n, k)
    predicted: np.ndarray  # (n,)
    residuals: np.ndarray  # (n,)
    bws: List[float]  # one per coefficient
    kernel: KernelName
    fixed: bool
    R2: float
    resid_ss: float
    n: int
    k: int
    n_iter: int
    bse: Optional[np.ndarray] = None  # (n, k) local standard errors
    tvalues: Optional[np.ndarray] = None  # (n, k)
    ENP_j: Optional[np.ndarray] = None  # (k,) effective number of parameters
    tr_S: Optional[float] = None
    sigma2: Optional[float] = None
    aicc: Optional[float] = None
    aic: Optional[float] = None
    bic: Optional[float] = None
    llf: Optional[float] = None
    bw_init: Optional[float] = None
    bws_history: Optional[np.ndarray] = None  # (n_iter, k)
    scores: Optional[np.ndarray] = None  # (n_iter,) SOC / RSS change
    converged: bool = True
    search: str = "mgwr"

    def summary(self) -> str:
        lines = [
            "Multiscale Geographically Weighted Regression (MGWR)",
            "-" * 52,
            f"n            : {self.n}",
            f"k            : {self.k}",
            f"Iterations   : {self.n_iter}",
            f"R²           : {self.R2:.4f}",
            f"Residual SS  : {self.resid_ss:.3f}",
        ]
        if self.aicc is not None:
            lines.append(f"AICc         : {self.aicc:.4f}")
            lines.append(f"tr(S)        : {self.tr_S:.4f}")
        lines += ["", "Coefficient-specific bandwidths:"]
        for j, bw in enumerate(self.bws):
            enp = "" if self.ENP_j is None else f"  ENP = {self.ENP_j[j]:.3f}"
            lines.append(f"  β{j}  bw = {bw:.3f}{enp}")
        lines += ["", "Local coefficient summary:"]
        for j in range(self.k):
            col = self.params[:, j]
            lines.append(f"  β{j}  mean={col.mean(): .4f}  std={col.std(): .4f}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return self.summary()


# --------------------------------------------------------------------- #
#  Weights (mgwr.kernels.Kernel)
# --------------------------------------------------------------------- #


class _Weights:
    """Kernel weight matrices W[i, m] = K(d_im / h_i), cached per bandwidth."""

    def __init__(self, coords: np.ndarray, kernel: KernelName, fixed: bool, eps: float):
        diff = coords[:, None, :] - coords[None, :, :]
        self.D = np.sqrt((diff**2).sum(axis=2))
        self.Dsorted = np.sort(self.D, axis=1) if not fixed else None
        self.n = coords.shape[0]
        self.kernel = kernel
        self.fixed = fixed
        self.eps = eps
        self._cache: Dict[float, np.ndarray] = {}

    def __call__(self, bw: float) -> np.ndarray:
        bw = float(bw)
        W = self._cache.get(bw)
        if W is not None:
            return W
        if np.isinf(bw):
            W = np.ones_like(self.D)
        else:
            if self.fixed:
                h = np.full(self.n, bw)
            else:
                kk = int(bw)
                if kk < 1:
                    raise MethodIncompatibility(
                        f"adaptive bandwidth must be >= 1 neighbour; got {bw!r}"
                    )
                if kk > self.n:
                    # outside mgwr's domain; GWmodel's extrapolation
                    h = bw / self.n * self.D.max(axis=1)
                else:
                    h = self.Dsorted[:, kk - 1] * self.eps
            if not np.all(h > 0):
                raise NumericalInstability(
                    "bandwidth maps to a zero distance (coincident points); "
                    "increase the bandwidth",
                    recovery_hint=(
                        "Increase the bandwidth or de-duplicate coincident "
                        "coordinates."
                    ),
                )
            W = _kernel(self.D / h[:, None], self.kernel)
        if len(self._cache) > 256:
            self._cache.clear()
        self._cache[bw] = W
        return W


# --------------------------------------------------------------------- #
#  GWR fits used inside MGWR (mgwr.gwr.GWR.fit(lite=True))
# --------------------------------------------------------------------- #


def _gwr_uni(W: np.ndarray, y: np.ndarray, x: np.ndarray):
    """One-covariate GWR without intercept: beta_i = sum w x y / sum w x^2."""
    wx = W * x[None, :]
    den = wx @ x
    beta = (wx @ y) / den
    predy = x * beta
    influ = x * x * np.diag(W) / den
    return beta, predy, influ


def _gwr_multi(W: np.ndarray, y: np.ndarray, X: np.ndarray):
    n, k = X.shape
    params = np.empty((n, k))
    influ = np.empty(n)
    for i in range(n):
        xT = (X * W[i][:, None]).T
        P = np.linalg.solve(xT @ X, xT)  # (k, n)
        params[i] = P @ y
        influ[i] = X[i] @ P[:, i]
    predy = (X * params).sum(axis=1)
    return params, predy, influ


def _llf(resid: np.ndarray) -> float:
    # spglm Gaussian loglike with scale = 1 (the profile log-likelihood)
    n = resid.shape[0]
    ssr = float(resid @ resid)
    nobs2 = n / 2.0
    return -np.log(ssr) * nobs2 - (1 + np.log(np.pi / nobs2)) * nobs2


def _criterion(resid: np.ndarray, influ: np.ndarray, criterion: str) -> float:
    """mgwr.diagnostics.get_AICc / get_AIC / get_BIC / get_CV (Gaussian)."""
    n = resid.shape[0]
    trS = float(np.sum(influ))
    if criterion == "CV":
        aa = resid / (1.0 - influ)
        return float(np.sum(aa**2) / n)
    llf = _llf(resid)
    if criterion == "AICc":
        return -2.0 * llf + 2.0 * n * (trS + 1.0) / (n - trS - 2.0)
    if criterion == "AIC":
        return -2.0 * llf + 2.0 * (trS + 1)
    if criterion == "BIC":
        return -2.0 * llf + (trS + 1) * np.log(n)
    raise MethodIncompatibility(
        f"unknown criterion {criterion!r}",
        recovery_hint="Use criterion='AICc', 'AIC', 'BIC' or 'CV'.",
    )


# --------------------------------------------------------------------- #
#  mgwr.search.golden_section
# --------------------------------------------------------------------- #


def _golden_section(
    a: float,
    c: float,
    function: Callable[[float], float],
    tol: float,
    max_iter: int,
    bw_max: Optional[float],
    int_score: bool,
) -> Tuple[float, float]:
    delta = _GOLDEN_DELTA
    b = a + delta * np.abs(c - a)
    d = c - delta * np.abs(c - a)
    opt_score = np.inf
    opt_val = np.nan
    diff = 1.0e9
    iters = 0
    memo: Dict[float, float] = {}
    while np.abs(diff) > tol and iters < max_iter and a != np.inf:
        iters += 1
        if int_score:
            b = np.round(b)
            d = np.round(d)
        if b in memo:
            score_b = memo[b]
        else:
            score_b = function(b)
            memo[b] = score_b
        if d in memo:
            score_d = memo[d]
        else:
            score_d = function(d)
            memo[d] = score_d
        if score_b <= score_d:
            opt_val = b
            opt_score = score_b
            c = d
            d = b
            b = a + delta * np.abs(c - a)
        else:
            opt_val = d
            opt_score = score_d
            a = b
            b = d
            d = c - delta * np.abs(c - a)
        opt_val = np.round(opt_val, 2)
        diff = score_b - score_d
    if a == np.inf or (bw_max is not None and bw_max == np.inf):
        score_ols = function(np.inf)
        if score_ols <= opt_score:
            opt_score = score_ols
            opt_val = np.inf
    return float(opt_val), float(opt_score)


def _init_section(wts: _Weights, n_vars: int, bw_min, bw_max) -> Tuple[float, float]:
    """mgwr.sel_bw.Sel_BW._init_section."""
    if not wts.fixed:
        a = 40 + 2 * n_vars
        c = wts.n
    else:
        D = wts.D
        off = D + np.diag(np.full(wts.n, np.inf))
        a = float(off.min()) / 2.0
        c = float(D.max()) * 2.0
    if bw_min is not None:
        a = bw_min
    if bw_max is not None and bw_max is not np.inf and bw_max != np.inf:
        c = bw_max
    return float(a), float(c)


# --------------------------------------------------------------------- #
#  Public entry point
# --------------------------------------------------------------------- #


def _per_cov(v, k, name) -> List[Optional[float]]:
    if v is None:
        return [None] * k
    if np.isscalar(v):
        return [float(v)] * k
    v = list(v)
    if len(v) == 1:
        return [None if v[0] is None else float(v[0])] * k
    if len(v) != k:
        raise MethodIncompatibility(
            f"{name} must be a scalar or have length {k}; got {len(v)}"
        )
    return [None if b is None else float(b) for b in v]


def mgwr(
    coords: Any,
    y: Any,
    X: Any,
    kernel: KernelName = "bisquare",
    fixed: bool = False,
    add_constant: bool = True,
    max_iter: int = 200,
    tol: float = 1e-5,
    bw_init: Optional[float] = None,
    bws: Optional[Sequence[float]] = None,
    criterion: MGWRCriterion = "AICc",
    bw_min: Union[None, float, Sequence[Optional[float]]] = None,
    bw_max: Union[None, float, Sequence[Optional[float]]] = None,
    bws_same_times: int = 5,
    rss_score: bool = False,
    search_tol: float = 1e-6,
    search_max_iter: int = 200,
    kernel_eps: float = _MGWR_EPS,
) -> MGWRResult:
    """Multiscale GWR by back-fitting, as PySAL ``mgwr`` computes it.

    Parameters
    ----------
    coords : (n, 2) array-like
        Projected point coordinates.
    y : (n,) array-like
    X : (n, p) array-like
        Regressors, without a constant unless ``add_constant=False``.
        ``mgwr``'s documentation standardises ``y`` and ``X`` (mean 0,
        variance 1) before fitting, so that the bandwidths are comparable;
        this function does not standardise.
    kernel : {"bisquare", "gaussian", "exponential"}, default "bisquare"
    fixed : bool, default False
        False: bandwidths are nearest-neighbour counts (integer search).
    add_constant : bool, default True
    max_iter : int, default 200
        Maximum back-fitting sweeps (``mgwr``'s ``max_iter_multi``).
    tol : float, default 1e-5
        Back-fitting stop on the score of change (``mgwr``'s ``tol_multi``);
        see the module docstring. Until StatsPAI 1.28 this was a threshold
        on ``max |f_new - f_old|``.
    bw_init : float, optional
        Bandwidth of the initialising all-covariate GWR (``mgwr``'s
        ``init_multi``); searched when omitted.
    bws : sequence of float, optional
        Fixed covariate-specific bandwidths (length ``k``, intercept first
        when ``add_constant=True``). No bandwidth is searched; the result is
        the additive-model fit at these bandwidths.
    criterion : {"AICc", "AIC", "BIC", "CV"}, default "AICc"
        Bandwidth criterion, with ``mgwr``'s definitions (its CV is the
        leave-one-out sum of squares divided by ``n``).
    bw_min, bw_max : float or sequence, optional
        Per-covariate search bounds (``mgwr``'s ``multi_bw_min`` /
        ``multi_bw_max``); a scalar applies to every covariate.
    bws_same_times : int, default 5
        Freeze the bandwidths once they have been unchanged for this many
        consecutive sweeps.
    rss_score : bool, default False
        Stop on the relative change of the RSS instead of the SOC.
    search_tol, search_max_iter : float, int
        Golden-section stop (``mgwr``'s ``tol`` / ``max_iter``).
    kernel_eps : float, default 1.0000001
        Multiplier of the adaptive nearest-neighbour distance, as in
        ``mgwr.kernels.Kernel``. ``1.0`` gives ``GWmodel``'s (and
        :func:`sp.gwr`'s) kernel, under which the ``int(bw)``-th neighbour
        gets zero bisquare weight.

    Returns
    -------
    MGWRResult
        ``params``, ``bse``, ``tvalues``, ``ENP_j``, ``tr_S``, ``sigma2``,
        ``aicc`` / ``aic`` / ``bic`` as ``mgwr.gwr.MGWRResults``;
        ``converged`` is False (with a ``RuntimeWarning``) when ``max_iter``
        sweeps did not reach ``tol``.

    Examples
    --------
    >>> import numpy as np
    >>> import statspai as sp
    >>> rng = np.random.default_rng(0)
    >>> n = 60
    >>> coords = rng.uniform(0, 10, size=(n, 2))
    >>> x = rng.normal(size=n)
    >>> y = 1.0 + 0.5 * x + 0.1 * coords[:, 0] + rng.normal(0, 0.3, size=n)
    >>> res = sp.mgwr(coords, y, x.reshape(-1, 1), bw_min=20)
    >>> res.params.shape  # (n, intercept + 1 covariate)
    (60, 2)
    >>> bool(np.isfinite(res.aicc))
    True
    """
    coords = np.asarray(coords, dtype=float)
    y = np.asarray(y, dtype=float).ravel()
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    if add_constant:
        X = np.column_stack([np.ones(X.shape[0]), X])
    n, k = X.shape
    if criterion not in ("AICc", "AIC", "BIC", "CV"):
        raise MethodIncompatibility(
            f"unknown criterion {criterion!r}",
            recovery_hint="Use criterion='AICc', 'AIC', 'BIC' or 'CV'.",
        )
    wts = _Weights(coords, kernel, fixed, float(kernel_eps))
    int_score = not fixed

    def select(
        yy: np.ndarray, fit_score: Callable[[np.ndarray], Tuple], n_vars: int, lo, hi
    ) -> float:
        a, c = _init_section(wts, n_vars, lo, hi)

        def fn(bw):
            resid, influ = fit_score(wts(bw))
            return _criterion(resid, influ, criterion)

        bw, _ = _golden_section(a, c, fn, search_tol, search_max_iter, hi, int_score)
        return bw

    # -- initial GWR ----------------------------------------------------- #
    if bw_init is None:

        def full_fit(W):
            _, predy, influ = _gwr_multi(W, y, X)
            return y - predy, influ

        bw_init = select(y, full_fit, k, None, None)
    bw_init = float(bw_init)
    params, predy, _ = _gwr_multi(wts(bw_init), y, X)
    err = y - predy

    if bws is not None:
        fixed_bws = [float(b) for b in bws]
        if len(fixed_bws) != k:
            raise MethodIncompatibility(
                f"bws must have length {k}; got {len(fixed_bws)}"
            )
    else:
        fixed_bws = None
    lo_j = _per_cov(bw_min, k, "bw_min")
    hi_j = _per_cov(bw_max, k, "bw_max")

    # -- back-fitting (mgwr.search.multi_bw) ---------------------------- #
    XB = params * X
    rss = float(err @ err)
    cur_bws = np.full(k, np.nan) if fixed_bws is None else np.array(fixed_bws)
    history: List[np.ndarray] = []
    scores: List[float] = []
    stable = 0
    converged = False
    for it in range(1, max_iter + 1):
        new_XB = np.zeros_like(X)
        new_params = np.zeros_like(X)
        for j in range(k):
            temp_y = XB[:, j] + err
            xj = X[:, j]
            if fixed_bws is None and stable < bws_same_times:

                def uni_fit(W, _y=temp_y, _x=xj):
                    _, py, infl = _gwr_uni(W, _y, _x)
                    return _y - py, infl

                bw = select(temp_y, uni_fit, 1, lo_j[j], hi_j[j])
            else:
                bw = cur_bws[j]
            beta_j, predy_j, _ = _gwr_uni(wts(bw), temp_y, xj)
            err = temp_y - predy_j
            new_XB[:, j] = predy_j
            new_params[:, j] = beta_j
            cur_bws[j] = bw
        if it > 1 and np.all(history[-1] == cur_bws):
            stable += 1
        else:
            stable = 0
        num = np.sum((new_XB - XB) ** 2) / n
        den = np.sum(np.sum(new_XB, axis=1) ** 2)
        score = float((num / den) ** 0.5)
        XB = new_XB
        params = new_params
        if rss_score:
            pred = np.sum(params * X, axis=1)
            new_rss = float(np.sum((y - pred) ** 2))
            score = abs((new_rss - rss) / new_rss)
            rss = new_rss
        scores.append(score)
        history.append(cur_bws.copy())
        if score < tol:
            converged = True
            break
    if not converged:
        warnings.warn(
            f"MGWR back-fitting did not converge in {max_iter} iterations "
            f"(last score of change = {scores[-1]:.3g} >= tol = {tol:g}).",
            RuntimeWarning,
            stacklevel=2,
        )
    bws_hist = np.array(history)

    # -- inference (mgwr.gwr.MGWR.fit): replay on the identity ---------- #
    # B[j] maps y to beta_j; R_j = diag(x_j) B[j] maps y to f_j.
    W0 = wts(bw_init)
    B = np.empty((k, n, n))
    for i in range(n):
        xT = (X * W0[i][:, None]).T
        B[:, i, :] = np.linalg.solve(xT @ X, xT)
    R = X.T[:, :, None] * B  # (k, n, n)
    E = np.eye(n) - R.sum(axis=0)
    for row in bws_hist:
        for j in range(k):
            Rj_old = R[j] + E
            W = wts(row[j])
            xj = X[:, j]
            wx = W * xj[None, :]
            B[j] = (wx / (wx @ xj)[:, None]) @ Rj_old
            R[j] = xj[:, None] * B[j]
            E = Rj_old - R[j]
    ENP_j = np.array([np.trace(R[j]) for j in range(k)])
    CCT = np.stack([np.sum(B[j] ** 2, axis=1) for j in range(k)], axis=1)

    predicted = np.sum(X * params, axis=1)
    residuals = y - predicted
    resid_ss = float(residuals @ residuals)
    tss = float(((y - y.mean()) ** 2).sum())
    R2 = 1.0 - resid_ss / tss if tss > 0 else np.nan
    tr_S = float(ENP_j.sum())
    sigma2 = resid_ss / (n - tr_S)
    bse = np.sqrt(CCT * sigma2)
    with np.errstate(divide="ignore", invalid="ignore"):
        tvalues = params / bse
    llf = _llf(residuals)
    aicc = -2.0 * llf + 2.0 * n * (tr_S + 1.0) / (n - tr_S - 2.0)
    aic = -2.0 * llf + 2.0 * (tr_S + 1)
    bic = -2.0 * llf + (tr_S + 1) * np.log(n)

    return MGWRResult(
        params=params,
        predicted=predicted,
        residuals=residuals,
        bws=[float(b) for b in cur_bws],
        kernel=kernel,
        fixed=fixed,
        R2=float(R2),
        resid_ss=resid_ss,
        n=n,
        k=k,
        n_iter=len(history),
        bse=bse,
        tvalues=tvalues,
        ENP_j=ENP_j,
        tr_S=tr_S,
        sigma2=float(sigma2),
        aicc=float(aicc),
        aic=float(aic),
        bic=float(bic),
        llf=float(llf),
        bw_init=bw_init,
        bws_history=bws_hist,
        scores=np.array(scores),
        converged=converged,
        search="fixed" if fixed_bws is not None else "mgwr",
    )

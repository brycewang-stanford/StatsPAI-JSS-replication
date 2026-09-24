"""
Chernozhukov-Fernández-Val-Melly (2013) counterfactual distributions.

Uses *distribution regression* (logit-at-threshold) to estimate the
conditional CDF F(y|X), then integrates over the covariate distribution
of the counterfactual sample to obtain F_{Y<A|B>}(y).  Inverting the CDF
gives the counterfactual quantile function.  Decomposition of any
distributional functional (quantiles, variance, Lorenz, Gini) follows.

References
----------
Chernozhukov, V., Fernández-Val, I., & Melly, B. (2013). "Inference on
Counterfactual Distributions." *Econometrica*, 81(6), 2205-2268.

Chernozhukov, V., Fernández-Val, I., Melly, B., & Wüthrich, K. (2020).
"Generic Inference on Quantile and Quantile Effect Functions for
Discrete Outcomes." *JASA*, 115(529), 123-137. [@chernozhukov2020generic]
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any, ClassVar, Dict, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from ..exceptions import ConvergenceFailure, MethodIncompatibility
from ._common import add_constant, logit_fit, logit_predict, prepare_frame
from ._results import DecompResultMixin

# ════════════════════════════════════════════════════════════════════════
# Distribution regression
# ════════════════════════════════════════════════════════════════════════


def _threshold_grid(y: np.ndarray, n_thresh: int = 40) -> np.ndarray:
    """Evenly-spaced quantiles of y as threshold grid."""
    qs = np.linspace(0.02, 0.98, n_thresh)
    return np.asarray(np.quantile(y, qs))


def _fit_dr(
    y: np.ndarray,
    X: np.ndarray,
    thresholds: np.ndarray,
) -> np.ndarray:
    """
    Distribution regression: for each threshold t, fit logit(1{y ≤ t} ~ X).

    Returns
    -------
    betas : (n_thresh, k) matrix
    """
    n_t = len(thresholds)
    k = X.shape[1]
    betas = np.empty((n_t, k))
    for i, t in enumerate(thresholds):
        ind = (y <= t).astype(float)
        # Handle degenerate (all 0 or all 1)
        if ind.sum() <= 2 or ind.sum() >= len(ind) - 2:
            betas[i] = 0.0
            # Set intercept so predictions are nearly constant
            p = ind.mean()
            p = np.clip(p, 1e-3, 1 - 1e-3)
            betas[i, 0] = np.log(p / (1 - p))
        else:
            try:
                # Distribution regression tolerates near-separation at
                # extreme thresholds (the NR loop clips the index); a
                # singular information matrix falls back to the empirical
                # proportion, loudly.
                b, _ = logit_fit(ind, X, warn_on_nonconvergence=False)
                betas[i] = b
            except (np.linalg.LinAlgError, ConvergenceFailure, RuntimeError) as exc:
                warnings.warn(
                    f"cfm_decompose: the distribution-regression logit at "
                    f"threshold {t:.6g} failed ({type(exc).__name__}: {exc}); "
                    "using the unconditional proportion there.",
                    RuntimeWarning,
                    stacklevel=3,
                )
                betas[i] = 0.0
                p = ind.mean()
                p = np.clip(p, 1e-3, 1 - 1e-3)
                betas[i, 0] = np.log(p / (1 - p))
    return betas


def _counterfactual_cdf(
    betas: np.ndarray,
    X_source: np.ndarray,
    thresholds: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Evaluate F̂_{Y<β|X_source>}(t) = avg_X Λ(X'β(t)).

    Returns
    -------
    thr : (n_thresh,) thresholds (sorted, monotonised)
    cdf : (n_thresh,) CDF values (monotonised to [0, 1])
    """
    # predicted probabilities at each threshold
    preds = np.array([logit_predict(b, X_source) for b in betas])  # (n_t, n_src)
    cdf = preds.mean(axis=1)
    # Enforce monotonicity by rearrangement: sort the CDF values across the
    # (sorted) thresholds (Chernozhukov, Fernandez-Val & Galichon 2010), as
    # Chernozhukov, Fernandez-Val & Melly's own ``cdeco`` does. Up to 1.28.0
    # this took the running maximum, which is a different monotone
    # projection whenever the raw distribution-regression CDF crosses.
    order = np.argsort(thresholds)
    thr = thresholds[order]
    cdf_mono = np.clip(np.sort(cdf[order]), 0.0, 1.0)
    return thr, cdf_mono


def _invert_cdf_step(thr: np.ndarray, cdf: np.ndarray, taus: np.ndarray) -> np.ndarray:
    """Step-function inverse used by ``cdeco``'s ``getquantile``.

    ``Q(tau) = thr[j]`` for the first threshold whose CDF value exceeds
    ``tau`` strictly, i.e. ``thr[min(#{F <= tau}, T - 1)]`` (0-based).
    """
    idx = np.array([int(np.sum(cdf <= t)) for t in np.atleast_1d(taus)])
    return np.asarray(thr[np.minimum(idx, len(thr) - 1)])


def _invert_cdf(thr: np.ndarray, cdf: np.ndarray, taus: np.ndarray) -> np.ndarray:
    """Invert a monotonic CDF at the given quantile levels."""
    # np.interp requires strictly increasing xp; apply small ε jitter
    eps = 1e-9 * np.arange(len(cdf))
    cdf_j = cdf + eps
    return np.asarray(np.interp(taus, cdf_j, thr))


# ════════════════════════════════════════════════════════════════════════
# Result
# ════════════════════════════════════════════════════════════════════════


@dataclass
class CFMResult(DecompResultMixin):
    """Chernozhukov-Fernández-Val-Melly counterfactual distribution result."""

    method_name: ClassVar[str] = "Chernozhukov-Fernandez-Val-Melly (2013) Decomposition"
    bib_keys: ClassVar[Tuple[str, ...]] = ("chernozhukov2013inference",)

    quantile_grid: pd.DataFrame
    cdf_grid: pd.DataFrame
    overall: Dict[str, float]
    reference: int
    n_thresh: int
    n_a: int
    n_b: int
    ks_stat: Optional[float] = None
    ks_pvalue: Optional[float] = None

    def summary(self) -> str:
        g = self.quantile_grid
        lines = [
            "━" * 72,
            "  Chernozhukov-Fernández-Val-Melly (2013) Decomposition",
            "━" * 72,
            f"  N_A = {self.n_a}   N_B = {self.n_b}   "
            f"thresholds = {self.n_thresh}   reference = {self.reference}",
        ]
        if self.ks_stat is not None:
            lines.append(
                f"  KS test (F_A = F_cf):  stat = {self.ks_stat:.4f}   "
                f"p = {self.ks_pvalue:.4f}"
            )
        lines.append("")
        lines.append(
            f"  {'tau':>6s} {'q_A':>9s} {'q_B':>9s} {'q_CF':>9s} "
            f"{'gap':>9s} {'comp':>9s} {'struct':>9s}"
        )
        for _, row in g.iterrows():
            lines.append(
                f"  {row['tau']:>6.2f} {row['q_a']:>9.4f} {row['q_b']:>9.4f} "
                f"{row['q_cf']:>9.4f} {row['gap']:>9.4f} "
                f"{row['composition']:>9.4f} {row['structure']:>9.4f}"
            )
        lines.append("━" * 72)
        text = "\n".join(lines)
        print(text)
        return text

    def plot(self, **kwargs: Any) -> Any:
        from .plots import counterfactual_cdf_plot

        return counterfactual_cdf_plot(self, **kwargs)

    def to_latex(self) -> str:
        latex: str = self.quantile_grid.round(4).to_latex(index=False)
        return latex

    def _repr_html_(self) -> str:
        html: str = self.quantile_grid.round(4).to_html(index=False)
        return (
            "<div style='font-family:monospace;'>"
            "<h3>CFM Counterfactual Decomposition</h3>" + html + "</div>"
        )

    def __repr__(self) -> str:
        return f"CFMResult(n_tau={len(self.quantile_grid)}, reference={self.reference})"


# ════════════════════════════════════════════════════════════════════════
# Main function
# ════════════════════════════════════════════════════════════════════════


def cfm_decompose(
    data: pd.DataFrame,
    y: str,
    group: str,
    x: Sequence[str],
    tau_grid: Optional[Sequence[float]] = None,
    reference: int = 0,
    n_thresh: int = 40,
    ks_test: bool = True,
    thresholds: Optional[Sequence[float]] = None,
    inversion: str = "interpolate",
) -> CFMResult:
    """
    Chernozhukov-Fernández-Val-Melly (2013) counterfactual decomposition.

    Parameters
    ----------
    data : pd.DataFrame
    y, group, x : column names
    tau_grid : Sequence[float] or None
    reference : {0, 1}
        Same convention as ``machado_mata`` / ``melly_decompose``:
        ``reference=0`` builds the counterfactual from A's distribution
        regression coefficients applied to B's X (F_{Y<0|1>}), opposite
        to the reweighting convention in ``dfl_decompose``.
    n_thresh : int — number of thresholds for distribution regression
        (ignored when ``thresholds`` is given).
    ks_test : bool — whether to compute Kolmogorov-Smirnov gap test
    thresholds : sequence of float, optional
        Explicit distribution-regression thresholds, shared by both groups.
        Default: ``n_thresh`` quantiles of the pooled outcome at
        ``linspace(0.02, 0.98, n_thresh)``.
    inversion : {'interpolate', 'step'}, default 'interpolate'
        How the estimated CDF, known only at the thresholds, is inverted.
        ``'interpolate'`` interpolates linearly between thresholds (a
        smoothed quantile). ``'step'`` returns the first threshold at which
        the CDF exceeds ``tau`` -- the step-function inverse of
        Chernozhukov, Fernández-Val & Melly's Stata ``cdeco``; with the same
        thresholds it reproduces ``cdeco, method(logit)``.

    Returns
    -------
    CFMResult

    Examples
    --------
    >>> import statspai as sp
    >>> df = sp.decomposition.datasets.cps_wage()
    >>> r = sp.cfm_decompose(df, y="log_wage", group="female",
    ...                      x=["education", "experience"],
    ...                      tau_grid=[0.25, 0.5, 0.75], n_thresh=15)
    >>> type(r).__name__
    'CFMResult'
    >>> sorted(r.overall)
    ['mean_composition', 'mean_gap', 'mean_structure']
    """
    cols = [y, group] + list(x)
    df, _ = prepare_frame(data, cols)
    g = df[group].astype(int).to_numpy()
    y_vec = df[y].to_numpy(dtype=float)
    X_raw = df[list(x)].to_numpy(dtype=float)

    X_a = add_constant(X_raw[g == 0])
    X_b = add_constant(X_raw[g == 1])
    y_a = y_vec[g == 0]
    y_b = y_vec[g == 1]

    if len(y_a) < 20 or len(y_b) < 20:
        raise ValueError("Need ≥20 obs per group for CFM.")

    if tau_grid is None:
        tau_seq: Sequence[float] | np.ndarray = np.round(np.arange(0.1, 0.95, 0.1), 2)
    else:
        tau_seq = tau_grid
    tau_eval = np.asarray(tau_seq, dtype=float)

    if reference not in (0, 1):
        raise MethodIncompatibility(f"reference must be 0 or 1, got {reference!r}")

    if inversion not in ("interpolate", "step"):
        raise MethodIncompatibility(
            f"inversion must be 'interpolate' or 'step', got {inversion!r}"
        )
    invert = _invert_cdf if inversion == "interpolate" else _invert_cdf_step

    # Common threshold grid based on pooled y
    if thresholds is None:
        thr = _threshold_grid(y_vec, n_thresh=n_thresh)
    else:
        thr = np.sort(np.asarray(thresholds, dtype=float))
        if thr.ndim != 1 or len(thr) < 2:
            raise MethodIncompatibility(
                "thresholds must be a 1-D sequence of length >= 2."
            )
        n_thresh = len(thr)

    betas_a = _fit_dr(y_a, X_a, thr)
    betas_b = _fit_dr(y_b, X_b, thr)

    thr_a, cdf_a = _counterfactual_cdf(betas_a, X_a, thr)
    thr_b, cdf_b = _counterfactual_cdf(betas_b, X_b, thr)
    if reference == 0:
        thr_cf, cdf_cf = _counterfactual_cdf(betas_a, X_b, thr)
    else:
        thr_cf, cdf_cf = _counterfactual_cdf(betas_b, X_a, thr)

    q_a = invert(thr_a, cdf_a, tau_eval)
    q_b = invert(thr_b, cdf_b, tau_eval)
    q_cf = invert(thr_cf, cdf_cf, tau_eval)

    gap = q_a - q_b
    if reference == 0:
        composition = q_a - q_cf
        structure = q_cf - q_b
    else:
        composition = q_cf - q_b
        structure = q_a - q_cf

    grid_df = pd.DataFrame(
        {
            "tau": tau_eval,
            "q_a": q_a,
            "q_b": q_b,
            "q_cf": q_cf,
            "gap": gap,
            "composition": composition,
            "structure": structure,
        }
    )
    cdf_df = pd.DataFrame(
        {
            "y": thr_a,
            "cdf_a": cdf_a,
            "cdf_b": np.interp(thr_a, thr_b, cdf_b),
            "cdf_cf": np.interp(thr_a, thr_cf, cdf_cf),
        }
    )

    overall = {
        "mean_gap": float(np.mean(gap)),
        "mean_composition": float(np.mean(composition)),
        "mean_structure": float(np.mean(structure)),
    }

    ks_stat: Optional[float] = None
    ks_p: Optional[float] = None
    if ks_test:
        # KS of composition effect: max |F_A - F_cf|
        diff = cdf_a - np.interp(thr_a, thr_cf, cdf_cf)
        ks_stat = float(np.max(np.abs(diff)))
        n = min(len(y_a), len(y_b))
        # approximate asymptotic p-value
        ks_p = float(stats.kstwo.sf(ks_stat, n))

    return CFMResult(
        quantile_grid=grid_df,
        cdf_grid=cdf_df,
        overall=overall,
        reference=reference,
        n_thresh=n_thresh,
        n_a=int(len(y_a)),
        n_b=int(len(y_b)),
        ks_stat=ks_stat,
        ks_pvalue=ks_p,
    )

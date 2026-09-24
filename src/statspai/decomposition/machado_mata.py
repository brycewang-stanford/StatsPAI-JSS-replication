"""
Machado-Mata (2005) quantile regression decomposition.

Simulate counterfactual outcome distributions by combining one group's
quantile regression coefficients with another group's covariate
distribution. Decompose quantile gaps into composition (X distribution)
and coefficient (price / structural) effects at each τ.

References
----------
Machado, J.A.F. & Mata, J. (2005). "Counterfactual Decomposition of Changes
in Wage Distributions Using Quantile Regression." *Journal of Applied
Econometrics*, 20(4), 445-465. [@machado2005counterfactual]

Albrecht, Björklund, Vroman (2003). "Is There a Glass Ceiling in Sweden?"
*Journal of Labor Economics*, 21(1), 145-177. [@albrecht2003there]
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Dict, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from ..exceptions import MethodIncompatibility
from ._common import add_constant
from ._common import averaged_inverse_cdf as _q2
from ._common import prepare_frame
from ._results import DecompResultMixin

# ════════════════════════════════════════════════════════════════════════
# Quantile regression process (exact linear-programming solution)
# ════════════════════════════════════════════════════════════════════════


def _qreg_grid(
    y: np.ndarray,
    X: np.ndarray,
    tau_grid: np.ndarray,
) -> np.ndarray:
    """Quantile regression at each τ; returns the (n_tau, k) coefficient matrix.

    Each fit is the exact minimiser of the check-function objective, solved
    as a linear program by :func:`statspai.regression.quantile._qreg_fit`
    (the solver behind ``sp.qreg``). Up to 1.28.0 this used an iteratively
    reweighted least-squares approximation that stopped far from the
    optimum -- coefficients off by 1-5% at the median and by several
    hundred percent on small slopes in the tails -- and every Melly and
    Machado-Mata counterfactual inherited the error.
    """
    from ..regression.quantile import _qreg_fit

    out = np.empty((len(tau_grid), X.shape[1]))
    for i, t in enumerate(tau_grid):
        out[i] = _qreg_fit(y, X, float(t))
    return out


def _tau_process_grid(n_tau_qr: int) -> np.ndarray:
    """Midpoint grid ``(j - 0.5) / J``, ``j = 1..J``, for the QR process.

    Each point carries mass ``1/J`` of the uniform on (0, 1), so pooling the
    ``J`` fitted conditional quantiles with equal weight integrates
    ``∫_0^1 1{x'β(u) <= y} du`` by the midpoint rule over the whole unit
    interval. This is the grid of Chernozhukov, Fernández-Val & Melly's own
    implementations (Stata ``cdeco`` / ``counterfactual``; R
    ``Counterfactual``). The pre-1.29 grid ``linspace(0.01, 0.99, 99)``
    covered only (0.005, 0.995), silently trimming 1% of the conditional
    distribution.
    """
    J = int(n_tau_qr)
    if J < 2:
        raise MethodIncompatibility("n_tau_qr must be at least 2.")
    return (np.arange(1, J + 1) - 0.5) / J


# ════════════════════════════════════════════════════════════════════════
# Result
# ════════════════════════════════════════════════════════════════════════


@dataclass
class MachadoMataResult(DecompResultMixin):
    """Container for Machado-Mata decomposition."""

    method_name: ClassVar[str] = "Machado-Mata Quantile Decomposition"
    bib_keys: ClassVar[Tuple[str, ...]] = ("machado2005counterfactual",)

    quantile_grid: pd.DataFrame  # τ, q_a, q_b, q_cf, gap, composition, structure
    overall: Dict[str, float]  # aggregated across grid
    reference: int
    n_sim: int
    n_a: int
    n_b: int
    se: Optional[pd.DataFrame] = None

    def summary(self) -> str:
        g = self.quantile_grid
        lines = [
            "━" * 72,
            "  Machado-Mata Quantile Decomposition",
            "━" * 72,
            f"  N_A = {self.n_a}   N_B = {self.n_b}   "
            f"simulations = {self.n_sim}   reference = {self.reference}",
            "",
            f"  {'tau':>6s} {'q_A':>9s} {'q_B':>9s} {'q_CF':>9s} "
            f"{'gap':>9s} {'comp':>9s} {'struct':>9s}",
        ]
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
        from .plots import quantile_process_plot

        return quantile_process_plot(self, **kwargs)

    def to_latex(self) -> str:
        g = self.quantile_grid
        lines = [
            r"\begin{table}[htbp]",
            r"\centering",
            r"\caption{Machado-Mata Decomposition}",
            r"\begin{tabular}{ccccccc}",
            r"\toprule",
            r"$\tau$ & $q_A$ & $q_B$ & $q_{cf}$ & Gap & Comp. & Struct. \\",
            r"\midrule",
        ]
        for _, row in g.iterrows():
            lines.append(
                f"{row['tau']:.2f} & {row['q_a']:.4f} & {row['q_b']:.4f} & "
                f"{row['q_cf']:.4f} & {row['gap']:.4f} & {row['composition']:.4f} "
                f"& {row['structure']:.4f} \\\\"
            )
        lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
        return "\n".join(lines)

    def _repr_html_(self) -> str:
        html: str = self.quantile_grid.round(4).to_html(index=False)
        return (
            "<div style='font-family:monospace;'>"
            "<h3>Machado-Mata Decomposition</h3>" + html + "</div>"
        )

    def __repr__(self) -> str:
        return (
            f"MachadoMataResult(n_tau={len(self.quantile_grid)}, "
            f"reference={self.reference}, n_sim={self.n_sim})"
        )


# ════════════════════════════════════════════════════════════════════════
# Core function
# ════════════════════════════════════════════════════════════════════════


def machado_mata(
    data: pd.DataFrame,
    y: str,
    group: str,
    x: Sequence[str],
    tau_grid: Optional[Sequence[float]] = None,
    reference: int = 0,
    n_sim: int = 500,
    n_tau_qr: int = 100,
    inference: str = "none",
    n_boot: int = 199,
    alpha: float = 0.05,
    seed: Optional[int] = 12345,
) -> MachadoMataResult:
    """
    Machado-Mata (2005) quantile decomposition.

    Parameters
    ----------
    data : pd.DataFrame
    y, group, x : column names
    tau_grid : Sequence[float] or None
        τ grid for reporting (default: deciles 0.1..0.9)
    reference : {0, 1}
        0: use Group A's coefficients with Group B's X. The
           counterfactual is F_{Y<0|1>} — A's β on B's X.
        1: use Group B's coefficients with Group A's X.

        .. warning::
           Opposite convention to ``dfl_decompose``. In DFL,
           ``reference=0`` means *A's X, B's β* (reweighting). Here,
           ``reference=0`` means *A's β, B's X* (coefficient swap).
           See ``dfl_decompose`` docstring for the full convention map.
    n_sim : int — number of (τ, obs) draws per counterfactual
    n_tau_qr : int, default 100
        Number ``J`` of quantile regressions, fitted at the midpoints
        ``(j - 0.5)/J``; each simulated draw picks one of them uniformly,
        so the draws sample the uniform on (0, 1) at resolution ``1/J``
        (Machado & Mata draw ``u ~ U(0, 1)`` directly; with this grid, as
        ``n_sim -> inf`` the decomposition converges to
        :func:`melly_decompose` on the same ``J``). Changed in 1.29.0 from
        99 regressions on ``linspace(0.01, 0.99, 99)``.
    inference : {'none', 'bootstrap'}
    n_boot : int
    alpha : float
    seed : int or None

    Returns
    -------
    MachadoMataResult

    Examples
    --------
    >>> import statspai as sp
    >>> df = sp.cps_wage()
    >>> r = sp.machado_mata(df, y='log_wage', group='female',
    ...                     x=['education', 'experience', 'tenure'],
    ...                     tau_grid=[0.25, 0.5, 0.75], n_sim=100, seed=0)
    >>> import contextlib, io
    >>> with contextlib.redirect_stdout(io.StringIO()):
    ...     text = r.summary()
    >>> "Machado-Mata Quantile Decomposition" in text
    True
    >>> list(r.quantile_grid['tau'])
    [0.25, 0.5, 0.75]
    >>> set(['gap', 'composition', 'structure']) <= set(r.quantile_grid.columns)
    True

    References
    ----------
    [@machado2005counterfactual]
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
        raise ValueError("Need ≥20 obs per group for Machado-Mata.")

    if tau_grid is None:
        tau_src: Sequence[float] | np.ndarray = np.round(np.arange(0.1, 0.95, 0.1), 2)
    else:
        tau_src = tau_grid
    tau_arr = np.asarray(tau_src, dtype=float)

    if reference not in (0, 1):
        raise MethodIncompatibility(f"reference must be 0 or 1, got {reference!r}")
    if inference not in ("none", "bootstrap"):
        raise MethodIncompatibility(
            f"inference must be 'none' or 'bootstrap', got {inference!r}"
        )

    tau_qr = _tau_process_grid(n_tau_qr)
    beta_a_grid = _qreg_grid(y_a, X_a, tau_qr)
    beta_b_grid = _qreg_grid(y_b, X_b, tau_qr)

    rng = np.random.default_rng(seed)

    def simulate(beta_grid: np.ndarray, X_source: np.ndarray, n: int) -> np.ndarray:
        """Draw n times: random τ, random row from X_source, predict y."""
        n_src = X_source.shape[0]
        t_idx = rng.integers(0, len(tau_qr), size=n)
        r_idx = rng.integers(0, n_src, size=n)
        b = beta_grid[t_idx]  # (n, k)
        xrow = X_source[r_idx]  # (n, k)
        return np.asarray(np.sum(b * xrow, axis=1))

    # Simulated (marginal) distributions
    y_a_sim = simulate(beta_a_grid, X_a, n_sim)
    y_b_sim = simulate(beta_b_grid, X_b, n_sim)
    if reference == 0:
        # counterfactual: A's coefficients, B's X
        y_cf_sim = simulate(beta_a_grid, X_b, n_sim)
    else:
        # counterfactual: B's coefficients, A's X
        y_cf_sim = simulate(beta_b_grid, X_a, n_sim)

    rows = []
    for t in tau_arr:
        q_a = float(_q2(y_a_sim, t))
        q_b = float(_q2(y_b_sim, t))
        q_cf = float(_q2(y_cf_sim, t))
        gap = q_a - q_b
        if reference == 0:
            composition = q_a - q_cf  # effect of X being A-like vs B-like (A's coefs)
            structure = q_cf - q_b  # remaining
        else:
            composition = q_cf - q_b
            structure = q_a - q_cf
        rows.append(
            {
                "tau": t,
                "q_a": q_a,
                "q_b": q_b,
                "q_cf": q_cf,
                "gap": gap,
                "composition": composition,
                "structure": structure,
            }
        )
    grid_df = pd.DataFrame(rows)

    overall = {
        "mean_gap": float(grid_df["gap"].mean()),
        "mean_composition": float(grid_df["composition"].mean()),
        "mean_structure": float(grid_df["structure"].mean()),
        "median_gap": float(grid_df["gap"].median()),
    }

    se_df = None
    if inference == "bootstrap":
        rng_b = np.random.default_rng(seed)
        boot_list = []
        n_failed = 0
        last_error: Optional[BaseException] = None
        strata = g
        for _ in range(n_boot):
            # Stratified bootstrap
            idx_parts = []
            for s in (0, 1):
                s_idx = np.where(strata == s)[0]
                idx_parts.append(rng_b.choice(s_idx, size=len(s_idx), replace=True))
            idx = np.concatenate(idx_parts)
            g_i = g[idx]
            y_i = y_vec[idx]
            X_i = X_raw[idx]
            X_a_i = add_constant(X_i[g_i == 0])
            X_b_i = add_constant(X_i[g_i == 1])
            y_a_i = y_i[g_i == 0]
            y_b_i = y_i[g_i == 1]
            try:
                beta_a_i = _qreg_grid(y_a_i, X_a_i, tau_qr)
                beta_b_i = _qreg_grid(y_b_i, X_b_i, tau_qr)
            except (np.linalg.LinAlgError, ValueError) as exc:
                n_failed += 1
                last_error = exc
                continue
            ya_sim = simulate(beta_a_i, X_a_i, n_sim)
            yb_sim = simulate(beta_b_i, X_b_i, n_sim)
            if reference == 0:
                ycf_sim = simulate(beta_a_i, X_b_i, n_sim)
            else:
                ycf_sim = simulate(beta_b_i, X_a_i, n_sim)
            gaps_b = []
            comps_b = []
            for t in tau_arr:
                q_a_b = _q2(ya_sim, t)
                q_b_b = _q2(yb_sim, t)
                q_cf_b = _q2(ycf_sim, t)
                gaps_b.append(q_a_b - q_b_b)
                if reference == 0:
                    comps_b.append(q_a_b - q_cf_b)
                else:
                    comps_b.append(q_cf_b - q_b_b)
            boot_list.append((gaps_b, comps_b))
        if n_failed:
            import warnings

            warnings.warn(
                f"machado_mata: {n_failed}/{n_boot} bootstrap replications "
                f"failed ({type(last_error).__name__}: {last_error}); the "
                "standard errors use the remaining replications.",
                RuntimeWarning,
                stacklevel=2,
            )
        if len(boot_list) <= 10:
            import warnings

            warnings.warn(
                f"machado_mata: only {len(boot_list)} of {n_boot} bootstrap "
                "replications available (need > 10); standard errors not "
                "computed (se is None).",
                RuntimeWarning,
                stacklevel=2,
            )
        else:
            gaps_arr = np.array([b[0] for b in boot_list])
            comps_arr = np.array([b[1] for b in boot_list])
            se_df = pd.DataFrame(
                {
                    "tau": tau_arr,
                    "gap_se": gaps_arr.std(axis=0, ddof=1),
                    "composition_se": comps_arr.std(axis=0, ddof=1),
                }
            )

    return MachadoMataResult(
        quantile_grid=grid_df,
        overall=overall,
        reference=reference,
        n_sim=n_sim,
        n_a=int(len(y_a)),
        n_b=int(len(y_b)),
        se=se_df,
    )

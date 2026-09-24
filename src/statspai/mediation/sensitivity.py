"""Mediation sensitivity analysis (Imai, Keele & Yamamoto, 2010).

Under sequential ignorability (SI), the average causal mediation
effect (ACME) is identified. But SI is untestable. The sensitivity
parameter ``ρ`` is the correlation between the error of the mediator
model and the error of the outcome model; an unobserved confounder of
the mediator-outcome relationship makes it non-zero. When ρ = 0, SI
holds; as |ρ| grows the ACME shrinks to zero and flips sign.

- :func:`mediate_sensitivity` -- for each ρ on a grid, re-fit the
  mediator and outcome regressions as a two-equation seemingly-unrelated
  regression whose error correlation is *fixed* at ρ (iterated feasible
  GLS), and report ACME(ρ) = α_T · β_M with its delta-method standard
  error. This is the linear/linear branch of R ``mediation::medsens``.
- The ρ at which ACME(ρ) = 0 has a closed form: the sample correlation
  between the residuals of ``M ~ T + X`` and of ``Y ~ T + X``
  (Imai, Keele & Yamamoto 2010).

References
----------
Imai, K., Keele, L. & Yamamoto, T. (2010). "Identification, Inference
  and Sensitivity Analysis for Causal Mediation Effects." *Stat Sci*,
  25(1), 51–71. [@imai2010identification]
Imai, K., Keele, L. & Tingley, D. (2010). "A General Approach to
  Causal Mediation Analysis." *Psych Methods*, 15(4), 309–334.
  [@imai2010general]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy import stats

from .._result_serialize import ResultProtocolMixin
from ..exceptions import MethodIncompatibility


@dataclass
class MediateSensitivityResult(ResultProtocolMixin):
    rho_grid: np.ndarray  # (n_grid,)
    acme_at_rho: np.ndarray  # (n_grid,)
    rho_at_zero: Optional[float]  # ρ where ACME(ρ) = 0 (closed form)
    acme_at_zero: float  # ACME at ρ=0 (the baseline)
    se_at_rho: np.ndarray = field(default_factory=lambda: np.empty(0))
    ci_lower: np.ndarray = field(default_factory=lambda: np.empty(0))
    ci_upper: np.ndarray = field(default_factory=lambda: np.empty(0))
    rho_grid_zero: Optional[float] = None  # grid ρ closest to ACME = 0
    r2_mediator: float = float("nan")
    r2_outcome: float = float("nan")
    r2star_threshold: float = float("nan")  # rho_at_zero ** 2
    r2tilde_threshold: float = float("nan")
    conf_level: float = 0.95

    def plot(
        self,
        ax: Any = None,
        *,
        fill: bool = True,
        annotate: bool = True,
        figsize: Any = (7.0, 4.5),
        **kwargs: Any,
    ) -> Any:
        """Publication-style sensitivity plot.

        Shows ACME(ρ) vs the mediator-outcome confounder strength ρ,
        with a coloured fill for the *region of nullability* (any ρ in
        ``[ρ_at_zero, 1]`` flips the ACME sign), the ρ at which the
        ACME crosses zero (annotated), and reference lines at ρ=0
        (i.e. sequential-ignorability) and ACME=0.

        Parameters
        ----------
        ax : matplotlib Axes, optional
        fill : bool, default True
            Fill the {ACME(ρ) > 0} region in light blue and the
            {ACME(ρ) < 0} region in light red, à la sensemakr.
        annotate : bool, default True
            Annotate ρ_at_zero, baseline ACME, and an interpretive note.
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError as e:  # pragma: no cover
            raise ImportError("matplotlib required for plot()") from e
        if ax is None:
            fig, ax = plt.subplots(figsize=figsize)
        else:
            fig = ax.figure

        rho = self.rho_grid
        acme = self.acme_at_rho

        if fill:
            ax.fill_between(
                rho,
                0,
                acme,
                where=(acme >= 0),
                color="#1f77b4",
                alpha=0.18,
                label="ACME ≥ 0",
            )
            ax.fill_between(
                rho,
                0,
                acme,
                where=(acme < 0),
                color="#d62728",
                alpha=0.18,
                label="ACME < 0",
            )
        ax.plot(rho, acme, color="#1f77b4", lw=1.8)
        ax.axhline(0, color="#333", lw=0.7)
        ax.axvline(
            0, color="#333", lw=0.7, ls=":", label=r"$\rho=0$ (sequential ignorability)"
        )

        # Mark the baseline ACME and ρ_at_zero
        ax.scatter([0.0], [self.acme_at_zero], color="#1f77b4", s=60, zorder=5)
        if annotate:
            ax.annotate(
                f"baseline ACME = {self.acme_at_zero:+.3f}",
                xy=(0.0, self.acme_at_zero),
                xytext=(8, 8),
                textcoords="offset points",
                fontsize=9,
            )

        if self.rho_at_zero is not None:
            ax.axvline(
                self.rho_at_zero,
                color="#d62728",
                lw=1.2,
                ls="--",
                label=rf"ACME=0 at $\rho={self.rho_at_zero:.3f}$",
            )
            if annotate:
                ax.annotate(
                    "robustness threshold",
                    xy=(self.rho_at_zero, 0),
                    xytext=(6, -20),
                    textcoords="offset points",
                    fontsize=8,
                    color="#d62728",
                )

        ax.set_xlabel(r"$\rho$ — confounder strength on (mediator, outcome) errors")
        ax.set_ylabel(r"$\widehat{\mathrm{ACME}}(\rho)$")
        ax.set_title("Mediation sensitivity analysis (Imai-Keele-Yamamoto 2010)")
        ax.legend(loc="best", fontsize=8)
        return fig, ax

    def summary(self) -> str:
        lines = [
            "Mediation Sensitivity (Imai et al. 2010)",
            "-" * 45,
            f"Baseline ACME (ρ=0) : {self.acme_at_zero: .4f}",
        ]
        if self.rho_at_zero is not None:
            lines.append(f"ρ at which ACME = 0  : {self.rho_at_zero: .4f}")
            lines.append(
                f"Interpretation: unobserved confounding with |ρ| > "
                f"{abs(self.rho_at_zero):.2f} would explain away the "
                f"estimated mediation effect."
            )
            lines.append(
                f"R²* (product) at ACME = 0 : {self.r2star_threshold: .4f}   "
                f"R̃² (product) : {self.r2tilde_threshold: .4f}"
            )
        else:
            lines.append("ACME(ρ) never reaches zero for |ρ| < 1.")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return self.summary()


def _sur_fixed_rho(
    X1: np.ndarray,
    y1: np.ndarray,
    X2: np.ndarray,
    y2: np.ndarray,
    rho: float,
    eps: Optional[float],
    max_iter: int,
) -> tuple:
    """Two-equation SUR with the error correlation fixed at ``rho``.

    Transcribes the lm/lm branch of R ``mediation::medsens`` step by step:
    start from equation-by-equation OLS; at each step form
    ``Ω = [[e1'e1/(n-1), ρ s1 s2], [ρ s1 s2, e2'e2/(n-1)]]`` from the
    current residuals (``s`` the n-1 standard deviations), take the GLS
    step ``b = (X' (Ω⁻¹ ⊗ I) X)⁻¹ X' (Ω⁻¹ ⊗ I) y`` and stop once the
    *squared* change ``Σ (b_new - b_old)²`` is at most ``eps``. The
    covariance is ``(X' (Ω⁻¹ ⊗ I) X)⁻¹`` from the last step.
    """
    n = len(y1)
    k1 = X1.shape[1]
    b = np.concatenate(
        [np.linalg.lstsq(X1, y1, rcond=None)[0], np.linalg.lstsq(X2, y2, rcond=None)[0]]
    )
    X1tX1, X1tX2, X2tX2 = X1.T @ X1, X1.T @ X2, X2.T @ X2
    X1ty1, X1ty2, X2ty1, X2ty2 = X1.T @ y1, X1.T @ y2, X2.T @ y1, X2.T @ y2
    for _ in range(max_iter):
        e1 = y1 - X1 @ b[:k1]
        e2 = y2 - X2 @ b[k1:]
        s1 = float(np.std(e1, ddof=1))
        s2 = float(np.std(e2, ddof=1))
        omega = np.array(
            [[e1 @ e1 / (n - 1), rho * s1 * s2], [rho * s1 * s2, e2 @ e2 / (n - 1)]]
        )
        w = np.linalg.inv(omega)
        A = np.block(
            [[w[0, 0] * X1tX1, w[0, 1] * X1tX2], [w[1, 0] * X1tX2.T, w[1, 1] * X2tX2]]
        )
        c = np.concatenate(
            [w[0, 0] * X1ty1 + w[0, 1] * X1ty2, w[1, 0] * X2ty1 + w[1, 1] * X2ty2]
        )
        b_new = np.linalg.solve(A, c)
        V = np.linalg.inv(A)
        dif = float(np.sum((b_new - b) ** 2))
        b = b_new
        # eps=None: the fixed point, i.e. a relative step of 1e-13.
        stop = (
            eps if eps is not None else (1e-13 * max(1.0, float(np.abs(b).max()))) ** 2
        )
        if dif <= stop:
            return b, V, True
    return b, V, False


def mediate_sensitivity(
    data: pd.DataFrame,
    y: str,
    treat: str,
    mediator: str,
    covariates: Optional[list] = None,
    rho_range: tuple = (-0.9, 0.9),
    n_grid: int = 41,
    *,
    conf_level: float = 0.95,
    eps: Optional[float] = None,
    max_iter: int = 10_000,
) -> MediateSensitivityResult:
    """Sensitivity analysis for causal mediation (linear models).

    Implements the sensitivity analysis of Imai, Keele & Yamamoto (2010)
    for a linear mediator model ``M = α₀ + α_T T + α_X'X + ε₁`` and a
    linear outcome model ``Y = β₀ + β_T T + β_M M + β_X'X + ε₂``. For each
    ρ = corr(ε₁, ε₂) on the grid the two equations are re-estimated
    jointly as a seemingly-unrelated regression with the error
    correlation fixed at ρ, and the ACME is ``α_T(ρ) · β_M(ρ)`` with the
    first-order delta-method variance
    ``α_T² Var(β_M) + β_M² Var(α_T)``. This is the lm/lm branch of R
    ``mediation::medsens`` (which requires ``mediate()`` output built
    from the same two ``lm`` fits).

    The ACME is exactly zero at ρ̃, the sample correlation between the
    residuals of ``M ~ T + X`` and of ``Y ~ T + X``; ``rho_at_zero``
    reports that closed form rather than an interpolation on the grid.

    Parameters
    ----------
    data : pd.DataFrame
    y, treat, mediator : str
        Outcome, treatment (binary or continuous) and mediator columns.
    covariates : list of str, optional
        Pre-treatment covariates entering both models.
    rho_range : (lo, hi), default (-0.9, 0.9)
        Grid end points; must lie strictly inside (-1, 1).
    n_grid : int, default 41
        Number of grid points (``medsens``' default ``rho.by = 0.1`` is
        ``rho_range=(-0.9, 0.9), n_grid=19``).
    conf_level : float, default 0.95
        Level of the normal-approximation band ``ACME ± z · SE``.
    eps : float, optional
        Stopping rule of the feasible-GLS iteration: stop when the
        squared change of the coefficient vector is at most ``eps``.
        The default iterates to the fixed point (machine precision).
        ``eps=np.sqrt(np.finfo(float).eps)`` is ``medsens``' default and
        reproduces its output exactly; that rule stops a few iterations
        early at large |ρ| (ACME off by up to ~1e-4 relative).
    max_iter : int, default 10000
        Iteration cap; a warning is raised when it binds.

    Returns
    -------
    MediateSensitivityResult
        ``acme_at_rho``, ``se_at_rho``, ``ci_lower`` / ``ci_upper`` on
        ``rho_grid``; ``rho_at_zero`` (closed form), ``rho_grid_zero``
        (``medsens``' ``err.cr.d``: the grid ρ closest to ACME = 0) and
        the R²* / R̃² thresholds (``R2star.d.thresh`` /
        ``R2tilde.d.thresh``, computed from ``rho_at_zero``).

    Notes
    -----
    Before 1.30 this function subtracted a heuristic omitted-variable
    bias ``α_T · ρ · σ_Y / σ_M`` from the naive ACME. That is not the
    Imai-Keele-Yamamoto sensitivity function: on the reference data it put
    the crossing point at 0.558 instead of 0.487 and ACME(-0.9) at 0.852
    instead of 1.533 (the curve is not linear in ρ).

    Examples
    --------
    >>> import statspai as sp
    >>> df = sp.cps_wage()
    >>> s = sp.mediate_sensitivity(df, y='log_wage', treat='union',
    ...                            mediator='tenure',
    ...                            covariates=['education', 'experience'],
    ...                            n_grid=11)
    >>> s.rho_grid.size
    11
    >>> bool(s.rho_grid.min() == -0.9 and s.rho_grid.max() == 0.9)
    True
    >>> import numpy as np
    >>> bool(np.isfinite(s.acme_at_zero))  # baseline ACME at rho=0
    True

    References
    ----------
    [@imai2010identification]
    """
    import warnings

    if covariates is None:
        covariates = []
    lo, hi = float(rho_range[0]), float(rho_range[1])
    if not (-1.0 < lo <= hi < 1.0):
        raise MethodIncompatibility(
            f"rho_range must lie strictly inside (-1, 1); got {rho_range}"
        )
    if not 0.0 < conf_level < 1.0:
        raise MethodIncompatibility(f"conf_level must be in (0, 1); got {conf_level}")
    df = data[[y, treat, mediator] + list(covariates)].dropna()
    Y = df[y].to_numpy(float)
    T = df[treat].to_numpy(float)
    M = df[mediator].to_numpy(float)
    n = len(df)
    X_cov = df[list(covariates)].to_numpy(float) if covariates else np.empty((n, 0))
    ones = np.ones((n, 1))

    Xm = np.column_stack([ones, T, X_cov])  # M ~ T + X
    Xy = np.column_stack([ones, T, M, X_cov])  # Y ~ T + M + X
    k1 = Xm.shape[1]

    beta_m = np.linalg.lstsq(Xm, M, rcond=None)[0]
    beta_y = np.linalg.lstsq(Xy, Y, rcond=None)[0]
    resid_m = M - Xm @ beta_m
    resid_y = Y - Xy @ beta_y
    acme_naive = float(beta_m[1] * beta_y[2])
    r2_m = float(1.0 - resid_m @ resid_m / np.sum((M - M.mean()) ** 2))
    r2_y = float(1.0 - resid_y @ resid_y / np.sum((Y - Y.mean()) ** 2))

    # Closed-form crossing point: corr(resid(M ~ T + X), resid(Y ~ T + X)).
    resid_y3 = Y - Xm @ np.linalg.lstsq(Xm, Y, rcond=None)[0]
    rho_tilde = float(np.corrcoef(resid_m, resid_y3)[0, 1])

    rho_grid = np.linspace(lo, hi, n_grid)
    acme = np.empty(n_grid)
    se = np.empty(n_grid)
    for k, rho in enumerate(rho_grid):
        b, V, ok = _sur_fixed_rho(Xm, M, Xy, Y, float(rho), eps, max_iter)
        if not ok:
            warnings.warn(
                f"mediate_sensitivity: FGLS did not converge (eps={eps}) at "
                f"rho={rho:.4f} within {max_iter} iterations",
                RuntimeWarning,
                stacklevel=2,
            )
        a_t, b_m = float(b[1]), float(b[k1 + 2])
        acme[k] = a_t * b_m
        se[k] = np.sqrt(a_t**2 * V[k1 + 2, k1 + 2] + b_m**2 * V[1, 1])

    z = float(stats.norm.ppf(0.5 + conf_level / 2.0))
    grid_zero = float(rho_grid[int(np.argmin(np.abs(acme)))])
    crosses = bool(np.isfinite(rho_tilde)) and abs(rho_tilde) < 1.0
    rho_at_zero = rho_tilde if crosses else None
    r2star = rho_tilde**2 if crosses else float("nan")

    _result = MediateSensitivityResult(
        rho_grid=rho_grid,
        acme_at_rho=acme,
        rho_at_zero=rho_at_zero,
        acme_at_zero=acme_naive,
        se_at_rho=se,
        ci_lower=acme - z * se,
        ci_upper=acme + z * se,
        rho_grid_zero=grid_zero,
        r2_mediator=r2_m,
        r2_outcome=r2_y,
        r2star_threshold=r2star,
        r2tilde_threshold=r2star * (1.0 - r2_m) * (1.0 - r2_y),
        conf_level=conf_level,
    )
    try:
        from ..output._lineage import attach_provenance as _attach_prov

        _attach_prov(
            _result,
            function="sp.mediation.mediate_sensitivity",
            params={
                "y": y,
                "treat": treat,
                "mediator": mediator,
                "covariates": list(covariates) if covariates else None,
                "rho_range": list(rho_range),
                "n_grid": n_grid,
                "conf_level": conf_level,
                "eps": eps,
            },
            data=data,
            overwrite=False,
        )
    except Exception:  # pragma: no cover
        pass
    return _result

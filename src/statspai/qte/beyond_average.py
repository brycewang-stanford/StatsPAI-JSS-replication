"""Distributional treatment effects on compliers under imperfect compliance.

Estimates ``F_{Y(1)|complier}`` and ``F_{Y(0)|complier}`` by Abadie kappa
weighting and returns their quantile difference, i.e. the complier QTE.

Motivated by Byambadalai, Hirata, Oka & Yasui (2025), *Beyond the Average:
Distributional Causal Inference under Imperfect Compliance*; the estimator
implemented here is the Abadie (2002, 2003) kappa-weighted one, which the
paper takes as its baseline.

The kappa machinery lives in :mod:`statspai.qte._core` and is shared with
:func:`statspai.qte.dist_iv.dist_iv`.

References
----------
abadie2002bootstrap, abadie2003semiparametric, byambadalai2025beyond
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy import stats

from .._result_serialize import ResultProtocolMixin


@dataclass
class BeyondAverageResult(ResultProtocolMixin):
    """Distributional LATE on compliers.

    Returned by :func:`beyond_average_late`; holds the per-quantile complier
    LATE, its bootstrap SE / CI, and the estimated complier share.

    Examples
    --------
    >>> import numpy as np
    >>> import pandas as pd
    >>> import statspai as sp
    >>> rng = np.random.default_rng(42)
    >>> n = 600
    >>> z = rng.integers(0, 2, n)
    >>> d = ((0.2 + 0.6 * z + rng.normal(0, 0.3, n)) > 0.5).astype(int)
    >>> y = 1.0 + 1.0 * d + rng.normal(0, 1, n)
    >>> df = pd.DataFrame({"y": y, "d": d, "z": z})
    >>> res = sp.beyond_average_late(
    ...     df, y="y", treat="d", instrument="z",
    ...     quantiles=np.array([0.25, 0.5, 0.75]), n_boot=50)
    >>> isinstance(res, sp.BeyondAverageResult)
    True
    >>> res.late_q.round(2).tolist()
    [0.98, 1.01, 1.14]
    >>> round(res.complier_share, 2)
    0.69
    """

    quantiles: np.ndarray
    late_q: np.ndarray
    se_q: np.ndarray
    ci_low: np.ndarray
    ci_high: np.ndarray
    complier_share: float
    n_obs: int

    def plot(self, ax: Any = None) -> Any:
        """Plot the complier LATE curve with its CI band. Returns (fig, ax)."""
        import matplotlib.pyplot as plt

        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 5))
        else:
            fig = ax.get_figure()
        ax.plot(
            self.quantiles,
            self.late_q,
            "o-",
            color="#2c7bb6",
            lw=2,
            label="Complier LATE",
        )
        ax.fill_between(
            self.quantiles, self.ci_low, self.ci_high, alpha=0.2, color="#2c7bb6"
        )
        ax.axhline(0, color="grey", ls="--", lw=0.8)
        ax.set_xlabel("Quantile (tau)")
        ax.set_ylabel("Complier LATE")
        ax.set_title(f"Distributional LATE (complier share {self.complier_share:.3f})")
        ax.legend()
        fig.tight_layout()
        return fig, ax

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "quantile": self.quantiles,
                "late": self.late_q,
                "se": self.se_q,
                "ci_low": self.ci_low,
                "ci_high": self.ci_high,
            }
        )

    def summary(self) -> str:
        rows = [
            "Beyond-the-Average: Distributional LATE",
            "=" * 42,
            f"  N           : {self.n_obs}",
            f"  Complier sh.: {self.complier_share:.3f}",
            "  Quantile  LATE      SE       95% CI",
        ]
        for q, l, s, lo, hi in zip(
            self.quantiles, self.late_q, self.se_q, self.ci_low, self.ci_high
        ):
            rows.append(f"  {q:.2f}     {l:+.4f}  {s:.4f}  [{lo:+.4f}, {hi:+.4f}]")
        return "\n".join(rows)


def beyond_average_late(
    data: pd.DataFrame,
    y: str,
    treat: str,
    instrument: str,
    quantiles: Optional[np.ndarray] = None,
    alpha: float = 0.05,
    n_boot: int = 200,
    seed: int = 0,
) -> BeyondAverageResult:
    """
    Distributional LATE on compliers under imperfect compliance.

    Parameters
    ----------
    data : pd.DataFrame
    y, treat, instrument : str
    quantiles : array-like, optional
    alpha : float
    n_boot : int
    seed : int

    Returns
    -------
    BeyondAverageResult

    Examples
    --------
    >>> import numpy as np
    >>> import pandas as pd
    >>> import statspai as sp
    >>> rng = np.random.default_rng(42)
    >>> n = 600
    >>> z = rng.integers(0, 2, n)
    >>> d = ((0.2 + 0.6 * z + rng.normal(0, 0.3, n)) > 0.5)
    >>> d = d.astype(int)
    >>> y = 1.0 + 1.0 * d + rng.normal(0, 1, n)
    >>> df = pd.DataFrame({"y": y, "d": d, "z": z})
    >>> res = sp.beyond_average_late(
    ...     df, y="y", treat="d", instrument="z",
    ...     quantiles=np.array([0.25, 0.5, 0.75]), n_boot=50)
    >>> res.late_q.round(2).tolist()  # complier LATE per quantile
    [0.98, 1.01, 1.14]
    >>> round(res.complier_share, 2)
    0.69
    """
    if quantiles is None:
        quantiles = np.array([0.1, 0.25, 0.5, 0.75, 0.9])
    df = data[[y, treat, instrument]].dropna().reset_index(drop=True)
    Y = df[y].to_numpy(float)
    D = df[treat].to_numpy(int)
    Z = df[instrument].to_numpy(int)
    n = len(df)
    rng = np.random.default_rng(seed)

    if Z.max() != 1 or Z.min() != 0:
        raise ValueError("Instrument must be binary (0/1).")

    complier_share = float(D[Z == 1].mean() - D[Z == 0].mean())
    if complier_share <= 0:
        raise ValueError(
            "Estimated complier share ≤ 0 — instrument fails monotonicity."
        )

    # Abadie (2002) kappa-weighted complier CDFs + left-continuous
    # inversion. Without covariates kappa reduces to the Imbens-Angrist
    # Wald identity per CDF. The primitives are the ones sp.dist_iv uses
    # (statspai.qte._core); up to 1.28.0 this function carried its own copy.
    from ._core import complier_cdfs, invert_cdf

    def _late_q(
        Yi: np.ndarray,
        Di: np.ndarray,
        Zi: np.ndarray,
        q: float,
    ) -> float:
        cdfs = complier_cdfs(Yi, Di, Zi)
        if cdfs is None:
            return np.nan
        grid, F1, F0, _ = cdfs
        return float(invert_cdf(grid, F1, q)[0] - invert_cdf(grid, F0, q)[0])

    late_q = np.array([_late_q(Y, D, Z, q) for q in quantiles])

    # Bootstrap SE
    boot = np.full((n_boot, len(quantiles)), np.nan)
    for b in range(n_boot):
        idx = rng.integers(0, n, size=n)
        for j, q in enumerate(quantiles):
            # A degenerate resample (no first stage) yields NaN, which is
            # counted and reported below -- not swallowed.
            boot[b, j] = _late_q(Y[idx], D[idx], Z[idx], q)
    n_finite = np.isfinite(boot).sum(axis=0)
    se_q = np.nanstd(boot, axis=0, ddof=1)
    # Quantiles whose bootstrap collapsed get NaN, not a fabricated 1e-6
    # (which would yield a spuriously narrow CI), and we surface it.
    se_q = np.where(np.isfinite(se_q) & (n_finite >= 2), se_q, np.nan)
    if (n_finite < n_boot).any():
        import warnings

        n_nan = int((n_finite < 2).sum())
        warnings.warn(
            f"qte beyond-average: LATE-quantile bootstrap failed for some "
            f"quantiles; {n_nan}/{len(quantiles)} quantile SE(s) are NaN "
            f"and remaining SEs use fewer replicates.",
            RuntimeWarning,
            stacklevel=2,
        )

    z_crit = float(stats.norm.ppf(1 - alpha / 2))
    ci_low = late_q - z_crit * se_q
    ci_high = late_q + z_crit * se_q

    _result = BeyondAverageResult(
        quantiles=quantiles,
        late_q=late_q,
        se_q=se_q,
        ci_low=ci_low,
        ci_high=ci_high,
        complier_share=complier_share,
        n_obs=n,
    )
    try:
        from ..output._lineage import attach_provenance as _attach_prov

        _attach_prov(
            _result,
            function="sp.qte.beyond_average_late",
            params={
                "y": y,
                "treat": treat,
                "instrument": instrument,
                "quantiles": (
                    list(quantiles)
                    if quantiles is not None and hasattr(quantiles, "__iter__")
                    else None
                ),
                "alpha": alpha,
                "n_boot": n_boot,
                "seed": seed,
            },
            data=data,
            overwrite=False,
        )
    except Exception:  # pragma: no cover
        pass
    return _result

"""
Multiple Imputation by Chained Equations (MICE).

Implements the MICE algorithm (van Buuren & Groothuis-Oudshoorn 2011)
for handling missing data, plus Rubin's rules for combining estimates.

Equivalent to Stata's ``mi impute chained`` and R's ``mice::mice()``.

References
----------
van Buuren, S. & Groothuis-Oudshoorn, K. (2011).
"mice: Multivariate Imputation by Chained Equations in R."
*Journal of Statistical Software*, 45(3), 1-67. [@buuren2011mice]

Rubin, D.B. (1987).
"Multiple Imputation for Nonresponse in Surveys."
*Wiley*. [@rubin1987multiple]
"""

from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd
from scipy import stats

from .._result_serialize import ResultProtocolMixin
from ..exceptions import DataInsufficient, MethodIncompatibility


class MICEResult(ResultProtocolMixin):
    """Results from MICE imputation.

    Examples
    --------
    >>> import statspai as sp
    >>> import numpy as np, pandas as pd
    >>> rng = np.random.default_rng(7)
    >>> x1 = rng.normal(size=120)
    >>> x2 = 0.5 * x1 + rng.normal(size=120)
    >>> y = 1.0 + x1 + x2 + rng.normal(size=120)
    >>> df = pd.DataFrame({"y": y, "x1": x1, "x2": x2})
    >>> df.loc[rng.choice(120, size=15, replace=False), "x2"] = np.nan
    >>> res = sp.mice(df, m=3, method="pmm", seed=0)
    >>> type(res).__name__
    'MICEResult'
    >>> res.n_imputations
    3
    >>> bool(res.complete(0)["x2"].notna().all())
    True
    """

    def __init__(
        self,
        imputed_datasets: Any,
        n_imputations: Any,
        n_obs: Any,
        n_missing: Any,
        variables_imputed: Any,
        methods: Any,
        convergence: Any,
    ) -> None:
        self.imputed_datasets = imputed_datasets
        self.n_imputations = n_imputations
        self.n_obs = n_obs
        self.n_missing = n_missing  # dict: var -> count
        self.variables_imputed = variables_imputed
        self.methods = methods  # dict: var -> method used
        self.convergence = convergence

    def summary(self) -> str:
        lines = [
            "Multiple Imputation by Chained Equations (MICE)",
            "=" * 55,
            f"Imputations: {self.n_imputations}",
            f"Observations: {self.n_obs}",
            "",
            f"{'Variable':<20s} {'Missing':>8s} {'%':>6s} {'Method':<15s}",
            "-" * 55,
        ]
        for var in self.variables_imputed:
            n_miss = self.n_missing[var]
            pct = n_miss / self.n_obs * 100
            method = self.methods.get(var, "pmm")
            lines.append(f"{var:<20s} {n_miss:>8d} {pct:>5.1f}% {method:<15s}")
        lines.append("=" * 55)
        return "\n".join(lines)

    def complete(self, m: int = 0) -> pd.DataFrame:
        """Return the m-th completed dataset (0-indexed)."""
        if m >= self.n_imputations:
            raise ValueError(f"Only {self.n_imputations} imputations available")
        return self.imputed_datasets[m].copy()

    def combine(self, estimates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Apply Rubin's rules to combine estimates across imputations."""
        return _rubins_rules(estimates)


def _barnard_rubin_df(m: int, b: np.ndarray, t: np.ndarray, dfcom: float) -> np.ndarray:
    """Barnard & Rubin (1999) small-sample degrees of freedom.

    ``lambda = (1 + 1/m) b / t``; ``nu_old = (m - 1) / lambda^2`` (Rubin
    1987) and, for finite ``dfcom``,
    ``nu = (m - 1) tmp / ((dfcom + 3)(m - 1) + lambda^2 tmp)`` with
    ``tmp = (1 - lambda)(1 + dfcom) dfcom`` -- algebraically
    ``1 / (1/nu_old + 1/nu_obs)``, written as R ``mice:::barnard.rubin``
    writes it so that ``b = 0`` (no between-imputation variance) gives
    ``nu_obs`` instead of ``inf / inf``.
    """
    lam = (1.0 + 1.0 / m) * b / t
    with np.errstate(divide="ignore", invalid="ignore"):
        if not np.isfinite(dfcom):
            return (m - 1) / lam**2
        tmp = (1.0 - lam) * (1.0 + dfcom) * dfcom
        return (m - 1) * tmp / ((dfcom + 3.0) * (m - 1) + lam**2 * tmp)


def _rubins_rules(
    estimates: List[Dict[str, Any]],
    dfcom: Optional[float] = None,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """
    Apply Rubin's (1987) combination rules.

    Parameters
    ----------
    estimates : list of dict
        Each dict has 'params' (array) and 'var_cov' (matrix), and
        optionally 'df_resid' (complete-data residual degrees of freedom).
    dfcom : float, optional
        Complete-data degrees of freedom. Defaults to the ``df_resid`` the
        estimates carry (all must agree), else infinity (large sample).
    alpha : float, default 0.05
        Level of the returned confidence intervals.

    Returns
    -------
    dict
        ``params`` (Q-bar), ``se``, ``tvalues``, ``pvalues``, ``ci_lower``,
        ``ci_upper``, ``df``, ``dfcom``, ``ubar``, ``b``, ``t``, ``riv``,
        ``lambda``, ``fmi``, ``fmi_barnard_rubin`` (all per coefficient),
        ``var_cov`` (the total
        covariance ``U-bar + (1 + 1/m) B``) and ``n_imputations``.

    Notes
    -----
    These are the quantities R ``mice::pool`` reports. The degrees of
    freedom are Barnard & Rubin's (1999) small-sample df when ``dfcom`` is
    finite and Rubin's (1987) ``(m - 1) / lambda^2`` otherwise; the
    fraction of missing information is ``(riv + 2/(df + 3)) / (riv + 1)``
    with that same df (R ``mice``); ``fmi_barnard_rubin`` is Barnard &
    Rubin's (1999) small-sample version ``1 - [l(df)/l(dfcom)] U/T`` with
    ``l(u) = (u + 1)/(u + 3)``, which is what Stata ``mi estimate`` reports
    (it equals ``fmi`` when ``dfcom`` is infinite). Before 1.30 StatsPAI
    always used Rubin's large-sample df (while labelling it Barnard-Rubin),
    which overstates the df -- and understates p-values -- when the
    complete-data df is small.
    """
    m = len(estimates)
    if m < 2:
        raise DataInsufficient(
            "Rubin's rules need at least two imputations.",
            recovery_hint="Pool the estimates from m >= 2 imputed datasets.",
        )
    params_list = np.asarray([np.asarray(e["params"], dtype=float) for e in estimates])
    vcov_list = np.asarray([np.asarray(e["var_cov"], dtype=float) for e in estimates])

    if dfcom is None:
        dfs = [e.get("df_resid") for e in estimates]
        if all(d is not None for d in dfs):
            if len(set(float(d) for d in dfs)) != 1:
                raise MethodIncompatibility(
                    f"complete-data df differ across imputations ({sorted(set(dfs))}); "
                    "pass dfcom= explicitly",
                    recovery_hint="Pass dfcom= explicitly.",
                )
            dfcom = float(dfs[0])
        else:
            dfcom = float("inf")
    dfcom = float(dfcom)

    # Combined point estimate: mean across imputations
    Q_bar = params_list.mean(axis=0)
    # Within-imputation variance
    U_bar = vcov_list.mean(axis=0)
    # Between-imputation variance (m - 1 divisor)
    dev = params_list - Q_bar
    B = dev.T @ dev / (m - 1)
    # Total variance
    T = U_bar + (1 + 1 / m) * B

    ubar = np.diag(U_bar)
    b = np.diag(B)
    t = np.diag(T)
    se = np.sqrt(t)
    tvalues = Q_bar / se
    riv = (1 + 1 / m) * b / ubar
    lam = (1 + 1 / m) * b / t
    df = _barnard_rubin_df(m, b, t, dfcom)
    pvalues = 2 * stats.t.sf(np.abs(tvalues), df)
    tcrit = stats.t.ppf(1 - alpha / 2, df)
    fmi = (riv + 2 / (df + 3)) / (riv + 1)
    # Barnard & Rubin (1999, p. 953) small-sample FMI, as Stata's
    # `mi estimate` reports it: 1 - [l(df) / l(dfcom)] U/T, l(u) = (u+1)/(u+3).
    if np.isfinite(dfcom):
        fmi_br = 1 - ((df + 1) / (df + 3)) / ((dfcom + 1) / (dfcom + 3)) * ubar / t
    else:
        fmi_br = fmi

    return {
        "params": Q_bar,
        "se": se,
        "tvalues": tvalues,
        "pvalues": pvalues,
        "ci_lower": Q_bar - tcrit * se,
        "ci_upper": Q_bar + tcrit * se,
        "df": df,
        "dfcom": dfcom,
        "ubar": ubar,
        "b": b,
        "t": t,
        "riv": riv,
        "lambda": lam,
        "fmi": fmi,
        "fmi_barnard_rubin": fmi_br,
        "var_cov": T,
        "n_imputations": m,
    }


def _impute_pmm(y_obs: Any, x_obs: Any, x_miss: Any, rng: Any, k: int = 5) -> Any:
    """Predictive mean matching imputation."""
    n_obs = len(y_obs)
    if n_obs < 2:
        return rng.choice(y_obs, size=len(x_miss))

    # Fit OLS on observed
    X_obs = np.column_stack([np.ones(n_obs), x_obs])
    try:
        beta = np.linalg.lstsq(X_obs, y_obs, rcond=None)[0]
    except np.linalg.LinAlgError:
        return rng.choice(y_obs, size=len(x_miss))

    # Draw beta from posterior (Bayesian bootstrap)
    resid = y_obs - X_obs @ beta
    sigma2 = np.sum(resid**2) / max(n_obs - X_obs.shape[1], 1)
    try:
        XtX_inv = np.linalg.inv(X_obs.T @ X_obs)
    except np.linalg.LinAlgError:
        return rng.choice(y_obs, size=len(x_miss))

    beta_star = rng.multivariate_normal(beta, sigma2 * XtX_inv)

    # Predicted values
    y_hat_obs = X_obs @ beta_star
    X_miss = np.column_stack([np.ones(len(x_miss)), x_miss])
    y_hat_miss = X_miss @ beta_star

    # Match: for each missing, find k nearest observed predictions
    imputed = np.empty(len(x_miss))
    for i, yh in enumerate(y_hat_miss):
        distances = np.abs(y_hat_obs - yh)
        nearest_idx = np.argsort(distances)[:k]
        imputed[i] = rng.choice(y_obs[nearest_idx])

    return imputed


def _impute_norm(y_obs: Any, x_obs: Any, x_miss: Any, rng: Any) -> Any:
    """Normal (Bayesian linear regression) imputation."""
    n_obs = len(y_obs)
    X_obs = np.column_stack([np.ones(n_obs), x_obs])
    try:
        beta = np.linalg.lstsq(X_obs, y_obs, rcond=None)[0]
        resid = y_obs - X_obs @ beta
        sigma2 = np.sum(resid**2) / max(n_obs - X_obs.shape[1], 1)
        XtX_inv = np.linalg.inv(X_obs.T @ X_obs)
    except np.linalg.LinAlgError:
        return rng.normal(y_obs.mean(), y_obs.std(), size=len(x_miss))

    # Draw from posterior
    sigma2_star = (
        sigma2 * (n_obs - X_obs.shape[1]) / rng.chisquare(n_obs - X_obs.shape[1])
    )
    beta_star = rng.multivariate_normal(beta, sigma2_star * XtX_inv)

    X_miss = np.column_stack([np.ones(len(x_miss)), x_miss])
    y_hat = X_miss @ beta_star + rng.normal(0, np.sqrt(sigma2_star), size=len(x_miss))
    return y_hat


def _impute_logreg(y_obs: Any, x_obs: Any, x_miss: Any, rng: Any) -> Any:
    """Logistic regression imputation for binary variables."""
    from scipy.optimize import minimize

    n_obs = len(y_obs)
    X_obs = np.column_stack([np.ones(n_obs), x_obs])

    def neg_ll(beta: Any) -> Any:
        xb = X_obs @ beta
        xb = np.clip(xb, -500, 500)
        p = 1 / (1 + np.exp(-xb))
        p = np.clip(p, 1e-10, 1 - 1e-10)
        return -np.sum(y_obs * np.log(p) + (1 - y_obs) * np.log(1 - p))

    beta0 = np.zeros(X_obs.shape[1])
    try:
        result = minimize(neg_ll, beta0, method="BFGS")
        beta = result.x
    except Exception:
        p_obs = y_obs.mean()
        return (rng.random(len(x_miss)) < p_obs).astype(float)

    X_miss = np.column_stack([np.ones(len(x_miss)), x_miss])
    xb = X_miss @ beta
    xb = np.clip(xb, -500, 500)
    probs = 1 / (1 + np.exp(-xb))
    return (rng.random(len(x_miss)) < probs).astype(float)


def mice(
    data: pd.DataFrame,
    m: int = 5,
    max_iter: int = 10,
    method: Union[str, Dict[str, str]] = "pmm",
    predictors: Optional[Dict[str, List[str]]] = None,
    seed: Optional[int] = None,
    print_progress: bool = False,
) -> MICEResult:
    """
    Multiple Imputation by Chained Equations (MICE).

    Equivalent to Stata's ``mi impute chained`` and R's ``mice::mice()``.

    Parameters
    ----------
    data : pd.DataFrame
        Data with missing values (NaN).
    m : int, default 5
        Number of imputations.
    max_iter : int, default 10
        Number of MICE iterations per imputation.
    method : str or dict, default 'pmm'
        Imputation method per variable:
        'pmm' (predictive mean matching), 'norm' (Bayesian linear),
        'logreg' (logistic for binary), 'sample' (random sample).
        Dict maps variable names to methods.
    predictors : dict, optional
        Dict mapping variable -> list of predictor variables.
        If None, uses all other variables.
    seed : int, optional
        Random seed.
    print_progress : bool, default False

    Returns
    -------
    MICEResult
        Result with .complete(m), .summary(), and .combine() methods.

    Examples
    --------
    >>> import statspai as sp
    >>> import numpy as np, pandas as pd
    >>> rng = np.random.default_rng(7)
    >>> x1 = rng.normal(size=120)
    >>> x2 = 0.5 * x1 + rng.normal(size=120)
    >>> y = 1.0 + x1 + x2 + rng.normal(size=120)
    >>> df = pd.DataFrame({"y": y, "x1": x1, "x2": x2})
    >>> df.loc[rng.choice(120, size=15, replace=False), "x2"] = np.nan
    >>> result = sp.mice(df, m=3, method='pmm', seed=0)
    >>> df_complete = result.complete(0)  # first imputed dataset
    >>> type(df_complete).__name__
    'DataFrame'
    >>> result.n_imputations
    3
    >>> # Combine estimates across imputations with Rubin's rules
    >>> estimates = []
    >>> for i in range(3):
    ...     df_i = result.complete(i)
    ...     r = sp.regress("y ~ x1 + x2", data=df_i)
    ...     estimates.append({'params': r.params.values,
    ...                       'var_cov': np.diag(r.std_errors.values ** 2)})
    >>> combined = result.combine(estimates)
    >>> {'fmi', 'df', 'n_imputations'} <= set(combined)
    True
    """
    rng = np.random.default_rng(seed)
    df = data.copy()

    # Identify variables with missing data
    missing_vars = [col for col in df.columns if df[col].isna().any()]
    n_missing = {col: df[col].isna().sum() for col in missing_vars}
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    # Determine methods
    if isinstance(method, str):
        methods = {}
        for var in missing_vars:
            if var not in numeric_cols:
                methods[var] = "sample"
            elif df[var].dropna().nunique() == 2:
                methods[var] = "logreg"
            else:
                methods[var] = method
    else:
        methods = method

    # Sort by amount of missing (least to most)
    missing_vars_sorted = sorted(missing_vars, key=lambda v: n_missing[v])

    imputed_datasets = []

    for imp in range(m):
        if print_progress:
            print(f"Imputation {imp + 1}/{m}")

        df_imp = df.copy()

        # Initial imputation: random sample from observed
        for var in missing_vars_sorted:
            mask = df_imp[var].isna()
            observed = df_imp.loc[~mask, var].values
            if len(observed) > 0:
                df_imp.loc[mask, var] = rng.choice(observed, size=mask.sum())

        # Chained equations iterations
        for iteration in range(max_iter):
            for var in missing_vars_sorted:
                mask = df[var].isna()  # Original missing pattern
                if mask.sum() == 0:
                    continue

                # Predictor variables
                if predictors is not None and var in predictors:
                    pred_vars = predictors[var]
                else:
                    pred_vars = [
                        c for c in numeric_cols if c != var and c in df_imp.columns
                    ]

                if len(pred_vars) == 0:
                    # No predictors: sample from observed
                    observed = df.loc[~mask, var].values
                    df_imp.loc[mask, var] = rng.choice(observed, size=mask.sum())
                    continue

                # Get predictor matrix (using current imputed values)
                X_all = df_imp[pred_vars].values.astype(float)

                # Handle any remaining NaN in predictors
                for j in range(X_all.shape[1]):
                    col_nan = np.isnan(X_all[:, j])
                    if col_nan.any():
                        X_all[col_nan, j] = np.nanmean(X_all[:, j])

                y_obs = df_imp.loc[~mask, var].values.astype(float)
                x_obs = X_all[~mask.values]
                x_miss = X_all[mask.values]

                m_method = methods.get(var, "pmm")

                if m_method == "pmm":
                    imputed = _impute_pmm(y_obs, x_obs, x_miss, rng)
                elif m_method == "norm":
                    imputed = _impute_norm(y_obs, x_obs, x_miss, rng)
                elif m_method == "logreg":
                    imputed = _impute_logreg(y_obs, x_obs, x_miss, rng)
                elif m_method == "sample":
                    observed = df.loc[~mask, var].values
                    imputed = rng.choice(observed, size=mask.sum())
                else:
                    observed = df.loc[~mask, var].values
                    imputed = rng.choice(observed, size=mask.sum())

                df_imp.loc[mask, var] = imputed

        imputed_datasets.append(df_imp)

    _result = MICEResult(
        imputed_datasets=imputed_datasets,
        n_imputations=m,
        n_obs=len(df),
        n_missing=n_missing,
        variables_imputed=missing_vars_sorted,
        methods=methods,
        convergence=True,
    )
    try:
        from ..output._lineage import attach_provenance as _attach_prov

        _attach_prov(
            _result,
            function="sp.imputation.mice",
            params={
                "m": m,
                "max_iter": max_iter,
                "method": method if isinstance(method, str) else dict(method),
                "predictors": (
                    {k: list(v) for k, v in predictors.items()} if predictors else None
                ),
                "seed": seed,
                "print_progress": print_progress,
            },
            data=data,
            overwrite=False,
        )
    except Exception:  # pragma: no cover
        pass
    return _result


def mi_estimate(
    mice_result: MICEResult,
    estimator: Any,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Run an estimator on each imputed dataset and combine using Rubin's rules.

    Parameters
    ----------
    mice_result : MICEResult
        Result from mice().
    estimator : callable
        Estimation function that returns an EconometricResults object.
    **kwargs
        Arguments passed to the estimator.

    Returns
    -------
    dict
        Combined estimates (Rubin's rules), keyed as in
        :meth:`MICEResult.combine`, plus ``var_names``. The within-imputation
        covariance is the estimator's full ``var_cov`` when it exposes one
        (``data_info['var_cov']``), else the diagonal of squared standard
        errors; the complete-data df for Barnard-Rubin is its ``df_resid``
        when exposed, else infinity. This reproduces R ``mice::pool`` and
        Stata ``mi estimate`` (small-sample df) for ``sp.regress``.

    Examples
    --------
    >>> import statspai as sp
    >>> import numpy as np, pandas as pd
    >>> rng = np.random.default_rng(7)
    >>> x1 = rng.normal(size=120)
    >>> x2 = 0.5 * x1 + rng.normal(size=120)
    >>> y = 1.0 + x1 + x2 + rng.normal(size=120)
    >>> df = pd.DataFrame({"y": y, "x1": x1, "x2": x2})
    >>> df.loc[rng.choice(120, size=15, replace=False), "x2"] = np.nan
    >>> mice_res = sp.mice(df, m=3, seed=0)
    >>> combined = sp.mi_estimate(mice_res, sp.regress, formula="y ~ x1 + x2")
    >>> combined['n_imputations']
    3
    >>> combined['var_names']
    ['Intercept', 'x1', 'x2']
    """
    estimates = []
    var_names: Optional[List[str]] = None
    for i in range(mice_result.n_imputations):
        df_i = mice_result.complete(i)
        result = estimator(data=df_i, **kwargs)
        params = result.params
        info = getattr(result, "data_info", None) or {}
        V = info.get("var_cov")
        k = len(params)
        if V is None or np.shape(V) != (k, k):
            # No full covariance exposed: pool the variances only.
            V = np.diag(np.asarray(result.std_errors, dtype=float) ** 2)
        est = {"params": np.asarray(params, dtype=float), "var_cov": np.asarray(V)}
        if info.get("df_resid") is not None:
            est["df_resid"] = float(info["df_resid"])
        estimates.append(est)
        if var_names is None:
            var_names = list(getattr(params, "index", range(k)))

    combined = _rubins_rules(estimates)
    combined["var_names"] = var_names
    return combined

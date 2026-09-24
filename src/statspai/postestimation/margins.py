"""
Marginal effects estimation.

Computes Average Marginal Effects (AME) for linear and nonlinear models
via numerical differentiation, with delta-method standard errors.

Equivalent to Stata's ``margins, dydx(*)`` and ``marginsplot``.

Supports:
- Continuous variables: dy/dx
- Binary/categorical: discrete change (0→1)
- Conditional margins: at specific covariate values
- Interaction effects
"""

import re
from itertools import product as itertools_product
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from ..exceptions import MethodIncompatibility
from ._covariance import coefficient_covariance, inference_df, require_covariance


def margins(
    result: Any,
    data: Optional[pd.DataFrame] = None,
    variables: Optional[List[str]] = None,
    at: Optional[Dict[str, Any]] = None,
    method: str = "ame",
    eps: float = 1e-5,
    alpha: float = 0.05,
) -> pd.DataFrame:
    """
    Compute marginal effects from a fitted model.

    Parameters
    ----------
    result : EconometricResults
        Fitted model result (must have ``.params`` and associated data).
    data : pd.DataFrame, optional
        Data to compute margins on. Defaults to the estimation sample.
    variables : list of str, optional
        Variables to compute dy/dx for. Default: all regressors.
    at : dict, optional
        Fix covariates at specific values for conditional margins.
        E.g., ``{'age': 30, 'female': 1}``.
    method : str, default 'ame'
        - 'ame': Average Marginal Effect (average dy/dx across all obs)
        - 'mem': Marginal Effect at the Mean (dy/dx at mean of X)
    eps : float, default 1e-5
        Step size for numerical differentiation.
    alpha : float, default 0.05
        Significance level.

    Returns
    -------
    pd.DataFrame
        Table with columns: variable, dy/dx, se, z, pvalue, ci_lower, ci_upper.

    Examples
    --------
    >>> import numpy as np
    >>> import pandas as pd
    >>> import statspai as sp
    >>> rng = np.random.default_rng(0)
    >>> df = pd.DataFrame({
    ...     "x1": rng.normal(size=200),
    ...     "x2": rng.normal(size=200),
    ...     "female": rng.integers(0, 2, size=200).astype(float),
    ... })
    >>> df["y"] = (1.0 + 0.5 * df["x1"] - 0.3 * df["x2"]
    ...            + 0.2 * df["x1"] * df["x2"] + rng.normal(size=200))
    >>> result = sp.regress("y ~ x1 + x2 + x1:x2", data=df)
    >>> me = sp.margins(result, data=df)
    >>> me.columns.tolist()
    ['variable', 'dy/dx', 'se', 'z', 'pvalue', 'ci_lower', 'ci_upper']

    Conditional margins: marginal effect of x1 with female fixed at 1.

    >>> me_at = sp.margins(result, data=df, variables=['x1'], at={'female': 1})
    >>> me_at['variable'].tolist()
    ['x1']
    """
    if method not in ("ame", "mem"):
        raise MethodIncompatibility(
            f"margins: method must be 'ame' or 'mem', got {method!r}."
        )
    link = _response_link(result)
    params = result.params
    frame = _margins_frame(result, data)
    if at:
        frame = frame.copy()
        for name, value in at.items():
            frame[name] = value
    base_vars = _term_variables(params.index)
    present = [v for v in base_vars if v in frame.columns]
    incomplete = frame[present].isna().any(axis=1) if present else None
    if incomplete is not None and bool(incomplete.any()):
        raise MethodIncompatibility(
            f"margins: {int(incomplete.sum())} row(s) of data have missing "
            f"values in model variables {present}; marginal effects averaged "
            "over them are undefined.",
            recovery_hint=(
                "Omit data= to average over the fitted model's own estimation "
                "sample (Stata's e(sample)), or pass data restricted to "
                "complete rows."
            ),
            diagnostics={"n_incomplete": int(incomplete.sum())},
        )
    if method == "mem":
        # Stata ``atmeans``: every component at its sample mean.
        frame = frame.mean(numeric_only=True).to_frame().T

    if variables is None:
        variables = [v for v in base_vars if not _is_factor_variable(v, params.index)]
    else:
        unknown = [v for v in variables if v not in base_vars]
        if unknown:
            raise MethodIncompatibility(
                f"margins: {unknown} do not enter the model.",
                recovery_hint=f"Variables in the model: {base_vars}.",
            )

    beta = params.to_numpy(dtype=float)
    X = _design(params.index, frame)
    eta = X @ beta + _offset(result, frame)
    f, f_prime = _link_derivatives(link, eta)

    df_ref = inference_df(result)
    finite = np.isfinite(df_ref)
    crit = (
        stats.t.ppf(1 - alpha / 2, df_ref) if finite else stats.norm.ppf(1 - alpha / 2)
    )

    rows = []
    for var in variables:
        if _is_factor_variable(var, params.index):
            raise MethodIncompatibility(
                f"margins: {var!r} enters as a factor; dy/dx of a factor is a "
                "discrete change, which this function does not compute.",
                recovery_hint="Use sp.contrast for level comparisons.",
            )
        D = _design_derivative(params.index, frame, var)  # d X / d var
        d_eta = D @ beta
        dydx = float(np.mean(f * d_eta))
        # Delta method: d AME / d beta = mean(f'(eta) X d_eta + f(eta) D).
        grad = np.mean(f_prime[:, None] * X * d_eta[:, None] + f[:, None] * D, axis=0)
        V = require_covariance(result, grad.reshape(1, -1), f"margins({var!r})")
        se = float(np.sqrt(max(float(grad @ V @ grad), 0.0)))
        stat = dydx / se if se > 0 else float("nan")
        pv = float(
            2 * (stats.t.sf(abs(stat), df_ref) if finite else stats.norm.sf(abs(stat)))
        )
        rows.append(
            {
                "variable": var,
                "dy/dx": dydx,
                "se": se,
                "z": stat,
                "pvalue": pv,
                "ci_lower": dydx - crit * se,
                "ci_upper": dydx + crit * se,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Index-model margins: prediction scale, design and its derivative
# ---------------------------------------------------------------------------
#
# ``margins`` used to return the index coefficients for every model without an
# interaction term -- so after ``sp.logit`` it reported beta (0.568) where
# Stata's ``margins, dydx(*)`` reports the average marginal effect on Pr(y)
# (0.126) -- and, with interactions, a "standard error" std(dydx)/sqrt(n) that
# is not a delta-method SE at all. Both are replaced by the delta method on
# the model's own prediction scale, using the full coefficient covariance.

_LINKS_SUPPORTED = ("identity", "logit", "probit", "cloglog", "log")


def _response_link(result: Any) -> str:
    """The inverse link of the default prediction, as a name."""
    model_info = getattr(result, "model_info", None) or {}
    data_info = getattr(result, "data_info", None) or {}
    link = model_info.get("link")
    link_obj = data_info.get("link_obj")
    if link_obj is not None:
        link = getattr(link_obj, "name", link)
    if isinstance(link, str) and link.lower() in _LINKS_SUPPORTED:
        return link.lower()
    likelihood_fit = (
        data_info.get("inference") == "z" and model_info.get("vcov_type") is None
    )
    if link is not None or likelihood_fit:
        raise MethodIncompatibility(
            f"margins: the prediction scale of this model (link={link!r}) is "
            "not supported; reporting index coefficients would not be "
            "marginal effects.",
            recovery_hint=(
                "margins supports linear models and logit / probit / cloglog / "
                "log-link (poisson, nbreg, glm) index models."
            ),
        )
    return "identity"


def _link_derivatives(link: str, eta: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """``(d mu / d eta, d2 mu / d eta2)`` for the inverse link."""
    if link == "identity":
        return np.ones_like(eta), np.zeros_like(eta)
    if link == "logit":
        p = 1.0 / (1.0 + np.exp(-eta))
        f = p * (1.0 - p)
        return f, f * (1.0 - 2.0 * p)
    if link == "probit":
        f = stats.norm.pdf(eta)
        return f, -eta * f
    if link == "cloglog":
        e = np.exp(eta)
        f = e * np.exp(-e)
        return f, f * (1.0 - e)
    mu = np.exp(eta)  # log
    return mu, mu


def _margins_frame(result: Any, data: Optional[pd.DataFrame]) -> pd.DataFrame:
    """Covariate values to average over: ``data`` or the stored design."""
    if data is not None:
        return data
    data_info = getattr(result, "data_info", None) or {}
    X = data_info.get("X")
    names = data_info.get("var_names")
    if X is not None and names is not None and np.shape(X)[1] == len(names):
        return pd.DataFrame(np.asarray(X, dtype=float), columns=list(names))
    raise MethodIncompatibility(
        "margins needs the covariate values: pass data=<estimation sample>.",
    )


def _term_variables(terms: Any) -> List[str]:
    """Distinct base variables that enter the model terms, in order."""
    out: List[str] = []
    for term in terms:
        for part in str(term).split(":"):
            if part in _INTERCEPT_TOKENS:
                continue
            m = _CAT_TERM_RE.match(part)
            name = m.group(1) if m is not None else part
            if name not in out:
                out.append(name)
    return out


def _is_factor_variable(var: str, terms: Any) -> bool:
    for term in terms:
        for part in str(term).split(":"):
            m = _CAT_TERM_RE.match(part)
            if m is not None and m.group(1) == var:
                return True
    return False


_INTERCEPT_TOKENS = ("Intercept", "const", "_cons")


def _part_values(part: str, frame: pd.DataFrame) -> np.ndarray:
    n = len(frame)
    if part in _INTERCEPT_TOKENS:
        return np.ones(n)
    m = _CAT_TERM_RE.match(part)
    if m is not None:
        base, level = m.group(1), m.group(2)
        if base not in frame.columns:
            raise MethodIncompatibility(f"margins: {base!r} is not in the data.")
        return np.array(
            [_factor_value(base, level, v) for v in frame[base]], dtype=float
        )
    if part not in frame.columns:
        raise MethodIncompatibility(
            f"margins: model term {part!r} is not a data column; transformed "
            "terms such as I(x**2) or np.log(x) are not supported.",
            recovery_hint="Create the transformed variable as a column and refit.",
        )
    return frame[part].to_numpy(dtype=float)


def _design(terms: Any, frame: pd.DataFrame) -> np.ndarray:
    columns = []
    for term in terms:
        value = np.ones(len(frame))
        for part in str(term).split(":"):
            value = value * _part_values(part, frame)
        columns.append(value)
    return np.column_stack(columns)


def _design_derivative(terms: Any, frame: pd.DataFrame, var: str) -> np.ndarray:
    """``d X / d var`` for each design column (product rule over ``a:b``)."""
    columns = []
    for term in terms:
        parts = str(term).split(":")
        deriv = np.zeros(len(frame))
        for i, part in enumerate(parts):
            if part != var:
                continue
            others = np.ones(len(frame))
            for j, other in enumerate(parts):
                if j != i:
                    others = others * _part_values(other, frame)
            deriv = deriv + others
        columns.append(deriv)
    return np.column_stack(columns)


def _offset(result: Any, frame: pd.DataFrame) -> np.ndarray:
    """Offset / log-exposure in the linear predictor, when the fit had one."""
    model_info = getattr(result, "model_info", None) or {}
    total = np.zeros(len(frame))
    for key, transform in (("offset", lambda v: v), ("exposure", np.log)):
        spec = model_info.get(key)
        if spec is None:
            continue
        if isinstance(spec, str) and spec in frame.columns:
            total = total + transform(frame[spec].to_numpy(dtype=float))
        else:
            raise MethodIncompatibility(
                f"margins: the fit used {key}={spec!r}, which is not a column of "
                "the data passed to margins.",
                recovery_hint="Pass data= containing the offset/exposure column.",
            )
    return total


def _get_vcov(result: Any) -> np.ndarray:
    """Full coefficient covariance for the gradient-based margins functions.

    ``margins_at`` / ``contrast`` / ``pwcompare`` combine several coefficients
    through a gradient, so the diagonal-of-standard-errors fallback used before
    silently dropped every covariance term. Without a stored matrix that
    matches the reported standard errors they now refuse.
    """
    V, _ = coefficient_covariance(result)
    if V is None:
        raise MethodIncompatibility(
            "this margins function combines several coefficients and needs "
            "their full covariance matrix, which the result does not carry.",
            recovery_hint="Refit with an estimator that stores data_info['var_cov'].",
        )
    return V


def _require_linear_prediction(result: Any, function: str) -> None:
    """``margins_at`` / ``contrast`` / ``pwcompare`` predict on the index scale.

    That is the prediction scale only for linear models; after logit or
    poisson it would report log-odds / log-count contrasts labelled as
    margins, so those fits are refused.
    """
    if _response_link(result) != "identity":
        raise MethodIncompatibility(
            f"{function} predicts on the linear-index scale, which is not the "
            "outcome scale of this model.",
            recovery_hint="Use sp.margins for response-scale marginal effects.",
        )


# Categorical design-term pattern, e.g. ``C(group)[T.2]`` or ``group[T.b]``
# (formulaic / patsy treatment-coding).  Captures the base variable name and
# the encoded reference level.
_CAT_TERM_RE = re.compile(r"^(?:C\(\s*)?([A-Za-z_]\w*)\s*(?:,[^)]*)?\)?\[T\.(.+)\]$")


def _factor_value(base: str, level: str, obs_val: Any) -> float:
    """Indicator for a treatment-coded dummy: 1.0 if ``obs_val`` is ``level``."""
    try:
        return 1.0 if float(obs_val) == float(level) else 0.0
    except (TypeError, ValueError):
        return 1.0 if str(obs_val) == str(level) else 0.0


def _component_value(
    token: str,
    row: pd.Series,
    var_to_change: Optional[str],
    new_val: Any,
) -> Optional[float]:
    """Design value of a single (non-interaction) token for one observation.

    Handles the intercept, plain numeric columns, and treatment-coded
    categorical dummies ``C(var)[T.level]``.  Returns ``None`` when the token
    references a variable that is absent from the row (so callers can treat the
    whole interaction term as zero, matching the original behaviour).
    """
    if token in ("Intercept", "const"):
        return 1.0

    m = _CAT_TERM_RE.match(token)
    if m is not None:
        base, level = m.group(1), m.group(2)
        obs_val = new_val if base == var_to_change else row.get(base)
        if base != var_to_change and base not in row.index:
            return None
        return _factor_value(base, level, obs_val)

    if token == var_to_change:
        return float(new_val)
    if token in row.index:
        return float(row[token])
    return None


def _predict_row(
    params: pd.Series,
    row: pd.Series,
    var_to_change: Optional[str],
    new_val: Any,
) -> float:
    """Predict y for a single observation, changing one variable."""
    y = 0.0
    for term, coef in params.items():
        val = coef
        for part in term.split(":"):
            comp = _component_value(part, row, var_to_change, new_val)
            if comp is None:
                val = 0.0
                break
            val *= comp
        y += val
    return float(y)


def marginsplot(
    margins_df: pd.DataFrame,
    ax: Any = None,
    figsize: Tuple[float, float] = (8, 5),
    color: str = "#2C3E50",
    title: Optional[str] = None,
) -> Tuple[Any, Any]:
    """
    Plot marginal effects with confidence intervals.

    Parameters
    ----------
    margins_df : pd.DataFrame
        Output from ``margins()``.
    ax : matplotlib Axes, optional
    figsize : tuple
    color : str
    title : str, optional

    Returns
    -------
    (fig, ax)

    Examples
    --------
    >>> import statspai as sp
    >>> df = sp.cps_wage()
    >>> result = sp.regress("log_wage ~ education + experience + female",
    ...                     data=df)
    >>> me = sp.margins(result, data=df)
    >>> fig, ax = sp.marginsplot(me, title='AME of wage determinants')
    >>> fig.savefig('margins.png')  # doctest: +SKIP
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        raise ImportError("matplotlib required. Install: pip install matplotlib")

    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.get_figure()

    vars = margins_df["variable"].values
    dydx = margins_df["dy/dx"].values
    lo = margins_df["ci_lower"].values
    hi = margins_df["ci_upper"].values

    y_pos = np.arange(len(vars))

    ax.scatter(dydx, y_pos, color=color, s=50, zorder=5)
    ax.errorbar(
        dydx,
        y_pos,
        xerr=[dydx - lo, hi - dydx],
        fmt="none",
        color=color,
        capsize=4,
        linewidth=1.5,
        zorder=3,
    )
    ax.axvline(x=0, color="gray", linestyle="--", linewidth=0.8)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(vars)
    ax.invert_yaxis()
    ax.set_xlabel("Marginal Effect (dy/dx)")
    ax.set_title(title or "Average Marginal Effects")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()

    return fig, ax


# ---------------------------------------------------------------------------
# margins_at: Predictive margins at specific covariate values
# ---------------------------------------------------------------------------


def margins_at(
    result: Any,
    data: pd.DataFrame,
    at: Dict[str, Any],
    alpha: float = 0.05,
) -> pd.DataFrame:
    """
    Compute predictive margins at specific covariate values.

    Equivalent to Stata's ``margins, at(experience=(1 5 10 15 20))``.

    For each combination of *at* values, every observation has the *at*
    variables set to those values while all other covariates stay at their
    observed levels.  The predicted value is averaged across observations
    to give the *predictive margin* at that point, with delta-method SEs.

    Parameters
    ----------
    result : EconometricResults
        Fitted model result (must have ``.params`` and associated data).
    data : pd.DataFrame
        Data to compute margins on.
    at : dict
        Mapping of variable names to lists/arrays of values.
        If multiple variables are given, the Cartesian product of all
        value lists is used.  Example::

            at={"experience": [1, 5, 10], "female": [0, 1]}

        produces 6 grid points.
    alpha : float, default 0.05
        Significance level for confidence intervals.

    Returns
    -------
    pd.DataFrame
        One row per grid point with columns for each *at* variable,
        plus ``margin``, ``se``, ``ci_lower``, ``ci_upper``.

    Examples
    --------
    >>> import numpy as np
    >>> import pandas as pd
    >>> import statspai as sp
    >>> rng = np.random.default_rng(42)
    >>> df = pd.DataFrame({
    ...     "experience": rng.integers(0, 20, size=200).astype(float),
    ...     "female": rng.integers(0, 2, size=200).astype(float),
    ... })
    >>> df["wage"] = (10.0 + 0.5 * df["experience"]
    ...               - 1.0 * df["female"] + rng.normal(size=200))
    >>> result = sp.regress(
    ...     "wage ~ experience + female + experience:female", data=df
    ... )
    >>> m = sp.margins_at(result, data=df, at={"experience": [1, 5, 10, 15, 20]})
    >>> m.shape[0]
    5
    >>> m.columns.tolist()
    ['experience', 'margin', 'se', 'ci_lower', 'ci_upper']
    """
    params = result.params
    _require_linear_prediction(result, "this margins function")
    vcov = _get_vcov(result)
    z_crit = stats.norm.ppf(1 - alpha / 2)

    # Build grid (Cartesian product of all at-values)
    at_vars = list(at.keys())
    at_values = [np.atleast_1d(at[v]).tolist() for v in at_vars]
    grid = list(itertools_product(*at_values))

    rows = []
    for point in grid:
        point_dict = dict(zip(at_vars, point))

        # Set at-variables to grid values for every observation
        df_mod = data.copy()
        for var, val in point_dict.items():
            df_mod[var] = val

        # Compute predicted y for each observation, then average
        preds = np.array(
            [
                _predict_row(params, df_mod.iloc[i], var_to_change=None, new_val=None)
                for i in range(len(df_mod))
            ]
        )
        margin = float(np.mean(preds))

        # Delta-method SE: gradient of the average prediction w.r.t. beta
        gradient = _margin_gradient(params, df_mod)
        se = float(np.sqrt(gradient @ vcov @ gradient))

        row = dict(point_dict)
        row.update(
            {
                "margin": margin,
                "se": se,
                "ci_lower": margin - z_crit * se,
                "ci_upper": margin + z_crit * se,
            }
        )
        rows.append(row)

    return pd.DataFrame(rows)


def _margin_gradient(params: pd.Series, df_mod: pd.DataFrame) -> np.ndarray:
    """Gradient of average prediction w.r.t. parameter vector (for delta method)."""
    n = len(df_mod)
    p = len(params)
    grad = np.zeros(p)

    for i in range(n):
        row = df_mod.iloc[i]
        for j, (term, _coef) in enumerate(params.items()):
            val = 1.0
            for part in term.split(":"):
                comp = _component_value(part, row, None, None)
                if comp is None:
                    val = 0.0
                    break
                val *= comp
            grad[j] += val

    grad /= n
    return grad


# ---------------------------------------------------------------------------
# margins_at_plot: Visualise predictive margins
# ---------------------------------------------------------------------------


def margins_at_plot(
    margins_at_df: pd.DataFrame,
    x: Optional[str] = None,
    by: Optional[str] = None,
    ax: Any = None,
    figsize: Tuple[float, float] = (8, 5),
    title: Optional[str] = None,
    xlabel: Optional[str] = None,
    ylabel: str = "Predicted Value",
    palette: Optional[List[str]] = None,
) -> Tuple[Any, Any]:
    """
    Plot predictive margins from ``margins_at()`` with confidence bands.

    Parameters
    ----------
    margins_at_df : pd.DataFrame
        Output from ``margins_at()``.
    x : str, optional
        Variable to place on the x-axis.  If *None*, inferred as the
        at-variable with the most unique values.
    by : str, optional
        Variable to produce separate lines for (legend grouping).
    ax : matplotlib Axes, optional
    figsize : tuple
    title : str, optional
    xlabel : str, optional
    ylabel : str
    palette : list of str, optional
        Colours for each ``by`` group.

    Returns
    -------
    (fig, ax)

    Examples
    --------
    >>> import numpy as np
    >>> import pandas as pd
    >>> import statspai as sp
    >>> rng = np.random.default_rng(42)
    >>> df = pd.DataFrame({
    ...     "experience": rng.integers(0, 20, size=200).astype(float),
    ...     "female": rng.integers(0, 2, size=200).astype(float),
    ... })
    >>> df["wage"] = (10.0 + 0.5 * df["experience"]
    ...               - 1.0 * df["female"] + rng.normal(size=200))
    >>> res = sp.regress(
    ...     "wage ~ experience + female + experience:female", data=df
    ... )
    >>> m = sp.margins_at(
    ...     res, data=df, at={"experience": [1, 5, 10, 15, 20]}
    ... )
    >>> fig, ax = sp.margins_at_plot(m, x="experience")
    >>> fig.savefig("margins_at.png")  # doctest: +SKIP
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        raise ImportError("matplotlib required.  Install: pip install matplotlib")

    # Detect at-variable columns (everything except margin/se/ci_*)
    meta_cols = {"margin", "se", "ci_lower", "ci_upper"}
    at_cols = [c for c in margins_at_df.columns if c not in meta_cols]

    if x is None:
        # Pick the at-variable with the most unique values
        x = max(at_cols, key=lambda c: margins_at_df[c].nunique())

    if by is None:
        remaining = [c for c in at_cols if c != x]
        if remaining:
            by = remaining[0]

    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.get_figure()

    default_palette = [
        "#2C3E50",
        "#E74C3C",
        "#3498DB",
        "#2ECC71",
        "#9B59B6",
        "#F39C12",
        "#1ABC9C",
        "#E67E22",
    ]
    colors = palette or default_palette

    if by is not None:
        groups = margins_at_df[by].unique()
        for idx, grp in enumerate(groups):
            sub = margins_at_df[margins_at_df[by] == grp].sort_values(x)
            color = colors[idx % len(colors)]
            ax.plot(sub[x], sub["margin"], marker="o", color=color, label=f"{by}={grp}")
            ax.fill_between(
                sub[x], sub["ci_lower"], sub["ci_upper"], alpha=0.15, color=color
            )
        ax.legend()
    else:
        sub = margins_at_df.sort_values(x)
        ax.plot(sub[x], sub["margin"], marker="o", color=colors[0])
        ax.fill_between(
            sub[x], sub["ci_lower"], sub["ci_upper"], alpha=0.20, color=colors[0]
        )

    ax.set_xlabel(xlabel or x)
    ax.set_ylabel(ylabel)
    ax.set_title(title or "Predictive Margins")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()

    return fig, ax


# ---------------------------------------------------------------------------
# contrast: Contrasts of predictive margins
# ---------------------------------------------------------------------------


def contrast(
    result: Any,
    data: pd.DataFrame,
    variable: str,
    method: str = "r",
    reference: Any = None,
    alpha: float = 0.05,
) -> pd.DataFrame:
    """
    Compute contrasts of predictive margins across levels of a variable.

    Equivalent to Stata's ``margins <var>, contrast(ar)`` / ``contrast(r)``.

    Parameters
    ----------
    result : EconometricResults
        Fitted model result.
    data : pd.DataFrame
        Estimation data.
    variable : str
        Categorical variable whose levels are contrasted.
    method : str, default 'r'
        Contrast type:

        - ``'r'`` (reference): each level vs *reference* level.
        - ``'ar'`` (adjacent): each level vs the previous level.
        - ``'gw'`` (grand-mean weighted): each level vs the weighted
          grand mean of all levels.
    reference : scalar, optional
        Reference level when ``method='r'``.  Defaults to the smallest
        observed level.
    alpha : float, default 0.05
        Significance level.

    Returns
    -------
    pd.DataFrame
        Columns: ``contrast_label``, ``contrast``, ``se``, ``z``,
        ``pvalue``, ``ci_lower``, ``ci_upper``.

    Examples
    --------
    >>> import numpy as np
    >>> import pandas as pd
    >>> import statspai as sp
    >>> rng = np.random.default_rng(1)
    >>> n = 300
    >>> group = rng.integers(0, 3, size=n).astype(float)
    >>> df = pd.DataFrame({
    ...     "group": group,
    ...     "experience": rng.normal(10, 3, size=n),
    ... })
    >>> df["wage"] = (10 + 2.0 * df["group"]
    ...               + 0.3 * df["experience"] + rng.normal(size=n))
    >>> result = sp.regress("wage ~ group + experience", data=df)
    >>> c = sp.contrast(result, data=df, variable="group",
    ...                 method="r", reference=0)
    >>> c["contrast_label"].tolist()
    ['1.0 vs 0', '2.0 vs 0']
    """
    params = result.params
    _require_linear_prediction(result, "this margins function")
    vcov = _get_vcov(result)
    z_crit = stats.norm.ppf(1 - alpha / 2)

    levels = sorted(data[variable].unique())

    # Compute predictive margin and gradient at each level
    level_margins = {}
    level_grads = {}
    level_counts = {}
    for lev in levels:
        df_mod = data.copy()
        df_mod[variable] = lev
        preds = np.array(
            [
                _predict_row(params, df_mod.iloc[i], var_to_change=None, new_val=None)
                for i in range(len(df_mod))
            ]
        )
        level_margins[lev] = float(np.mean(preds))
        level_grads[lev] = _margin_gradient(params, df_mod)
        level_counts[lev] = int((data[variable] == lev).sum())

    # Build contrasts
    rows = []
    if method == "r":
        if reference is None:
            reference = levels[0]
        for lev in levels:
            if lev == reference:
                continue
            diff = level_margins[lev] - level_margins[reference]
            grad_diff = level_grads[lev] - level_grads[reference]
            se = float(np.sqrt(grad_diff @ vcov @ grad_diff))
            z = diff / se if se > 0 else 0.0
            pv = float(2 * stats.norm.sf(abs(z)))
            rows.append(
                {
                    "contrast_label": f"{lev} vs {reference}",
                    "contrast": diff,
                    "se": se,
                    "z": z,
                    "pvalue": pv,
                    "ci_lower": diff - z_crit * se,
                    "ci_upper": diff + z_crit * se,
                }
            )

    elif method == "ar":
        for i in range(1, len(levels)):
            lev, prev = levels[i], levels[i - 1]
            diff = level_margins[lev] - level_margins[prev]
            grad_diff = level_grads[lev] - level_grads[prev]
            se = float(np.sqrt(grad_diff @ vcov @ grad_diff))
            z = diff / se if se > 0 else 0.0
            pv = float(2 * stats.norm.sf(abs(z)))
            rows.append(
                {
                    "contrast_label": f"{lev} vs {prev}",
                    "contrast": diff,
                    "se": se,
                    "z": z,
                    "pvalue": pv,
                    "ci_lower": diff - z_crit * se,
                    "ci_upper": diff + z_crit * se,
                }
            )

    elif method == "gw":
        total_n = sum(level_counts.values())
        weights = {lev: level_counts[lev] / total_n for lev in levels}
        grand_margin = sum(weights[lev] * level_margins[lev] for lev in levels)
        grand_grad = sum(weights[lev] * level_grads[lev] for lev in levels)

        for lev in levels:
            diff = level_margins[lev] - grand_margin
            grad_diff = level_grads[lev] - grand_grad
            se = float(np.sqrt(grad_diff @ vcov @ grad_diff))
            z = diff / se if se > 0 else 0.0
            pv = float(2 * stats.norm.sf(abs(z)))
            rows.append(
                {
                    "contrast_label": f"{lev} vs grand mean",
                    "contrast": diff,
                    "se": se,
                    "z": z,
                    "pvalue": pv,
                    "ci_lower": diff - z_crit * se,
                    "ci_upper": diff + z_crit * se,
                }
            )
    else:
        raise ValueError(f"Unknown contrast method '{method}'. Use 'r', 'ar', or 'gw'.")

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# pwcompare: Pairwise comparisons of predictive margins
# ---------------------------------------------------------------------------


def pwcompare(
    result: Any,
    data: pd.DataFrame,
    variable: str,
    adjust: str = "none",
    alpha: float = 0.05,
) -> pd.DataFrame:
    """
    Pairwise comparisons of predictive margins across all levels.

    Equivalent to Stata's ``pwcompare <var>``.

    Parameters
    ----------
    result : EconometricResults
        Fitted model result.
    data : pd.DataFrame
        Estimation data.
    variable : str
        Categorical variable whose levels are compared pairwise.
    adjust : str, default 'none'
        P-value adjustment method:

        - ``'none'``: unadjusted.
        - ``'bonferroni'``: Bonferroni correction.
        - ``'sidak'``: Sidak correction.
        - ``'holm'``: Holm step-down procedure.
    alpha : float, default 0.05
        Significance level for (adjusted) confidence intervals.

    Returns
    -------
    pd.DataFrame
        Columns: ``comparison``, ``diff``, ``se``, ``z``, ``pvalue``,
        ``pvalue_adj``, ``ci_lower``, ``ci_upper``.

    Examples
    --------
    >>> import numpy as np
    >>> import pandas as pd
    >>> import statspai as sp
    >>> rng = np.random.default_rng(1)
    >>> n = 300
    >>> group = rng.integers(0, 3, size=n).astype(float)
    >>> df = pd.DataFrame({
    ...     "group": group,
    ...     "experience": rng.normal(10, 3, size=n),
    ... })
    >>> df["wage"] = (10 + 2.0 * df["group"]
    ...               + 0.3 * df["experience"] + rng.normal(size=n))
    >>> result = sp.regress("wage ~ group + experience", data=df)
    >>> pw = sp.pwcompare(result, data=df, variable="group",
    ...                   adjust="bonferroni")
    >>> bool((pw["pvalue_adj"] >= pw["pvalue"]).all())
    True
    """
    params = result.params
    _require_linear_prediction(result, "this margins function")
    vcov = _get_vcov(result)

    levels = sorted(data[variable].unique())

    # Compute margin & gradient at each level
    level_margins = {}
    level_grads = {}
    for lev in levels:
        df_mod = data.copy()
        df_mod[variable] = lev
        preds = np.array(
            [
                _predict_row(params, df_mod.iloc[i], var_to_change=None, new_val=None)
                for i in range(len(df_mod))
            ]
        )
        level_margins[lev] = float(np.mean(preds))
        level_grads[lev] = _margin_gradient(params, df_mod)

    # All pairwise comparisons
    pairs = []
    for i in range(len(levels)):
        for j in range(i + 1, len(levels)):
            pairs.append((levels[i], levels[j]))

    n_comp = len(pairs)
    rows = []
    for lev_a, lev_b in pairs:
        diff = level_margins[lev_b] - level_margins[lev_a]
        grad_diff = level_grads[lev_b] - level_grads[lev_a]
        se = float(np.sqrt(grad_diff @ vcov @ grad_diff))
        z = diff / se if se > 0 else 0.0
        pv = float(2 * stats.norm.sf(abs(z)))
        rows.append(
            {
                "comparison": f"{lev_b} vs {lev_a}",
                "diff": diff,
                "se": se,
                "z": z,
                "pvalue": pv,
            }
        )

    # Adjust p-values
    raw_pvals = [r["pvalue"] for r in rows]
    adj_pvals = _adjust_pvalues(raw_pvals, method=adjust, n_comparisons=n_comp)

    # Determine adjusted alpha for CIs
    alpha_adj = _adjusted_alpha(alpha, adjust, n_comp)
    z_crit = stats.norm.ppf(1 - alpha_adj / 2)

    for r, padj in zip(rows, adj_pvals):
        r["pvalue_adj"] = padj
        r["ci_lower"] = r["diff"] - z_crit * r["se"]
        r["ci_upper"] = r["diff"] + z_crit * r["se"]

    return pd.DataFrame(rows)


def _adjust_pvalues(
    pvals: Any,
    method: str,
    n_comparisons: int,
) -> List[float]:
    """Apply multiple-comparison correction to p-values."""
    pvals = np.asarray(pvals, dtype=float)
    if method == "none":
        return [float(p) for p in pvals.tolist()]
    elif method == "bonferroni":
        return [float(p) for p in np.minimum(pvals * n_comparisons, 1.0).tolist()]
    elif method == "sidak":
        return [float(p) for p in (1.0 - (1.0 - pvals) ** n_comparisons).tolist()]
    elif method == "holm":
        n = len(pvals)
        order = np.argsort(pvals)
        adj = np.empty(n)
        for rank, idx in enumerate(order):
            adj[idx] = min(pvals[idx] * (n_comparisons - rank), 1.0)
        # Enforce monotonicity
        cum_max = 0.0
        for idx in order:
            cum_max = max(cum_max, adj[idx])
            adj[idx] = cum_max
        return [float(p) for p in adj.tolist()]
    else:
        raise ValueError(
            f"Unknown adjustment method '{method}'. "
            "Use 'none', 'bonferroni', 'sidak', or 'holm'."
        )


def _adjusted_alpha(alpha: float, method: str, n_comparisons: int) -> float:
    """Return adjusted significance level for CI construction."""
    if method == "none":
        return alpha
    elif method == "bonferroni":
        return alpha / n_comparisons
    elif method == "sidak":
        return float(1.0 - (1.0 - alpha) ** (1.0 / n_comparisons))
    elif method == "holm":
        # Conservative: use Bonferroni alpha for CIs
        return alpha / n_comparisons
    else:
        return alpha


# ---------------------------------------------------------------------------
# margins_table — adapter that wraps a margins DataFrame so it pipes
# straight into sp.regtable for publication-quality marginal-effects
# tables. Mirrors the R workflow ``modelsummary(avg_slopes(model))`` and
# closes the "estimator → marginal-effects table" gap that previously
# required users to hand-build add_rows.
# ---------------------------------------------------------------------------


class _MarginsResult:
    """Duck-typed result wrapping a ``margins`` DataFrame.

    Exposes the attributes ``_extract_model_data`` (in ``output/estimates``)
    looks for: ``params`` / ``std_errors`` / ``tvalues`` / ``pvalues`` /
    ``conf_int_lower`` / ``conf_int_upper`` / ``diagnostics`` /
    ``data_info`` / ``model_info``. Behaves like an ``EconometricResults``
    for the purposes of ``regtable``.
    """

    def __init__(
        self,
        margins_df: pd.DataFrame,
        *,
        n_obs: Optional[int] = None,
        method: str = "ame",
    ) -> None:
        if "variable" not in margins_df.columns:
            raise ValueError(
                "margins_table requires a DataFrame with a 'variable' column "
                "(produced by sp.margins). Got columns: "
                f"{list(margins_df.columns)}"
            )
        idx = margins_df["variable"].astype(str).tolist()
        # ``dy/dx`` may be NaN for binary/categorical rows that report a
        # discrete change instead — the helper below is defensive.
        col_dydx = "dy/dx" if "dy/dx" in margins_df.columns else "diff"
        col_p = "pvalue_adj" if "pvalue_adj" in margins_df.columns else "pvalue"
        self.params = pd.Series(margins_df[col_dydx].astype(float).values, index=idx)
        self.std_errors = pd.Series(margins_df["se"].astype(float).values, index=idx)
        # margins reports z-stat (z under normal); we name it tvalues so
        # the rest of regtable's machinery treats it as a t-style ratio
        # without special-casing.
        z_col = "z" if "z" in margins_df.columns else "t"
        if z_col in margins_df.columns:
            self.tvalues = pd.Series(margins_df[z_col].astype(float).values, index=idx)
        else:
            self.tvalues = pd.Series(np.nan, index=idx)
        self.pvalues = pd.Series(margins_df[col_p].astype(float).values, index=idx)
        if "ci_lower" in margins_df.columns:
            self.conf_int_lower = pd.Series(
                margins_df["ci_lower"].astype(float).values, index=idx
            )
            self.conf_int_upper = pd.Series(
                margins_df["ci_upper"].astype(float).values, index=idx
            )
        else:
            self.conf_int_lower = pd.Series(np.nan, index=idx)
            self.conf_int_upper = pd.Series(np.nan, index=idx)
        # Minimal diagnostics so ``stats=["N"]`` still works.
        self.diagnostics = {"N": n_obs} if n_obs is not None else {}
        self.data_info = {"nobs": n_obs} if n_obs is not None else {}
        # Tag so users can introspect (and we leave a breadcrumb in the
        # rendered table footer via ``method`` later if desired).
        self.model_info = {"model_type": f"Marginal effects ({method})"}
        # df_resid omitted — margins inference is z-based, regtable falls
        # back to standard normal which is correct here.

    def __repr__(self) -> str:
        n = len(self.params)
        return f"<MarginsResult: {n} marginal effect{'s' if n != 1 else ''}>"


def event_study_table(
    result: Any,
    *,
    regex: Optional[str] = None,
    label_fmt: str = "t={t}",
    include_reference: bool = False,
) -> _MarginsResult:
    """Adapter that turns an event-study fit into a regtable input.

    Two extraction paths:

    1. **CausalResult fast path** — when ``result.model_info`` carries an
       ``"event_study"`` DataFrame (the canonical shape produced by
       :func:`sp.event_study`), read its ``relative_time`` /
       ``estimate`` / ``se`` / ``ci_lower`` / ``ci_upper`` / ``pvalue``
       columns directly. Reference period (``estimate==0`` and
       ``se==0``) is dropped by default (set ``include_reference=True``
       to keep it visible).

    2. **Regex path** — when ``regex`` is provided, scan
       ``result.params.index`` for coefficients matching the pattern
       and use the first capture group as the relative time.

    Rows are sorted by relative time (so the rendered table reads
    ``t=-3, t=-2, …, t=+3`` regardless of the underlying coefficient
    name encoding).

    Parameters
    ----------
    result : CausalResult or EconometricResults
        Fitted model. The CausalResult fast path is used automatically
        when ``model_info['event_study']`` is present.
    regex : str, optional
        Pattern with one capture group that matches the relative time
        in coefficient names. Required when the CausalResult fast path
        is not applicable. Examples: ``r"^tau_(-?\\d+)$"``,
        ``r"^lag(\\d+)$"``, ``r"::(-?\\d+)$"``.
    label_fmt : str, default ``"t={t}"``
        Format string for the row label of each event-time bin. The
        ``{t}`` placeholder receives the integer relative time.
    include_reference : bool, default False
        Whether to render the reference period row (typically
        ``t=-1``) where the estimate is identically zero.

    Returns
    -------
    _MarginsResult
        Duck-typed result accepted directly by :func:`sp.regtable`.

    Examples
    --------
    >>> import numpy as np
    >>> import pandas as pd
    >>> import statspai as sp
    >>> rng = np.random.default_rng(7)
    >>> rows = []
    >>> for u in range(60):
    ...     tt = rng.choice([3, 4, 5, 100])  # 100 marks never-treated
    ...     for t in range(8):
    ...         post = 1.0 if (tt < 100 and t >= tt) else 0.0
    ...         y = 0.3 * u / 60 + 0.1 * t + 1.5 * post + rng.normal(scale=0.5)
    ...         rows.append({"unit": u, "time": t, "treat_time": tt, "y": y})
    >>> panel = pd.DataFrame(rows)
    >>> r = sp.event_study(panel, y="y", treat_time="treat_time",
    ...                    time="time", unit="unit", window=(-3, 3))
    >>> tbl = sp.event_study_table(r)
    >>> _ = sp.regtable(tbl, title="Event study", output="text")
    """
    mi = getattr(result, "model_info", {}) or {}
    es_df = mi.get("event_study") if isinstance(mi, dict) else None
    rows: List[Tuple[int, float, float, float, float, float]] = []

    if isinstance(es_df, pd.DataFrame) and "relative_time" in es_df.columns:
        for _, row in es_df.iterrows():
            t = int(row["relative_time"])
            est = float(row.get("estimate", row.get("dy/dx", np.nan)))
            se = float(row.get("se", np.nan))
            lo = float(row.get("ci_lower", np.nan))
            hi = float(row.get("ci_upper", np.nan))
            pv = float(row.get("pvalue", np.nan))
            if not include_reference and abs(est) < 1e-15 and abs(se) < 1e-15:
                continue
            rows.append((t, est, se, lo, hi, pv))
    elif regex is not None:
        params = getattr(result, "params", None)
        if params is None:
            raise ValueError(
                "event_study_table: result has no .params; cannot use "
                "regex extraction path."
            )
        std_errors = getattr(result, "std_errors", pd.Series())
        pvalues = getattr(result, "pvalues", pd.Series())
        ci_lo = getattr(result, "conf_int_lower", pd.Series())
        ci_hi = getattr(result, "conf_int_upper", pd.Series())
        rx = re.compile(regex)
        for name in params.index:
            m = rx.search(str(name))
            if not m:
                continue
            try:
                t = int(m.group(1))
            except (IndexError, ValueError):
                continue
            est = float(params.get(name, np.nan))
            se = (
                float(std_errors.get(name, np.nan))
                if name in std_errors.index
                else np.nan
            )
            pv = float(pvalues.get(name, np.nan)) if name in pvalues.index else np.nan
            lo = float(ci_lo.get(name, np.nan)) if name in ci_lo.index else np.nan
            hi = float(ci_hi.get(name, np.nan)) if name in ci_hi.index else np.nan
            rows.append((t, est, se, lo, hi, pv))
    else:
        raise ValueError(
            "event_study_table: result has no model_info['event_study'] "
            "DataFrame and no `regex` was provided. Pass regex=... to "
            "extract event-time coefficients from result.params.index."
        )

    if not rows:
        raise ValueError(
            "event_study_table: no event-time rows extracted. Check "
            "the regex pattern or include_reference=True."
        )

    rows.sort(key=lambda r: r[0])
    labels = [label_fmt.format(t=t) for t, *_ in rows]
    df = pd.DataFrame(
        {
            "variable": labels,
            "dy/dx": [r[1] for r in rows],
            "se": [r[2] for r in rows],
            "ci_lower": [r[3] for r in rows],
            "ci_upper": [r[4] for r in rows],
            "pvalue": [r[5] for r in rows],
        }
    )
    # Synthesise a z-stat for the ``tvalues`` slot (regtable uses it
    # only when se_type='t', and event studies almost always show
    # estimates with SE — but populate consistently).
    with np.errstate(divide="ignore", invalid="ignore"):
        df["z"] = df["dy/dx"] / df["se"]
    n_obs = None
    diag = getattr(result, "diagnostics", {}) or {}
    dinfo = getattr(result, "data_info", {}) or {}
    if isinstance(diag, dict) and diag.get("N") is not None:
        n_obs = diag.get("N")
    elif isinstance(dinfo, dict) and dinfo.get("nobs") is not None:
        n_obs = dinfo.get("nobs")
    return _MarginsResult(df, n_obs=n_obs, method="event-study")


def margins_table(
    result: Any,
    data: Optional[pd.DataFrame] = None,
    variables: Optional[List[str]] = None,
    at: Optional[Dict[str, Any]] = None,
    method: str = "ame",
    eps: float = 1e-5,
    alpha: float = 0.05,
) -> _MarginsResult:
    """Marginal-effects result that pipes straight into ``sp.regtable``.

    Thin adapter over :func:`margins`: computes the marginal effects
    (same kwargs), then wraps the resulting DataFrame in a
    :class:`_MarginsResult` exposing ``params`` / ``std_errors`` /
    ``tvalues`` / ``pvalues`` / ``conf_int_*`` so that
    ``sp.regtable(margins_table(model))`` produces a publication-quality
    marginal-effects table — closing the "estimator → margins table"
    gap that previously required users to hand-build ``add_rows``.

    Mirrors the R workflow ``modelsummary(avg_slopes(model))``.

    Parameters
    ----------
    result : EconometricResults
        Fitted model — same input ``sp.margins`` accepts.
    data, variables, at, method, eps, alpha
        Forwarded verbatim to :func:`margins`.

    Returns
    -------
    _MarginsResult
        A duck-typed result object usable directly as a positional
        argument to :func:`sp.regtable`.

    Examples
    --------
    >>> import numpy as np
    >>> import pandas as pd
    >>> import statspai as sp
    >>> rng = np.random.default_rng(0)
    >>> n = 300
    >>> x = rng.normal(size=n)
    >>> z = rng.normal(size=n)
    >>> p = 1 / (1 + np.exp(-(0.5 * x - 0.4 * z)))
    >>> df = pd.DataFrame({
    ...     "y": (rng.uniform(size=n) < p).astype(int),
    ...     "x": x,
    ...     "z": z,
    ... })
    >>> m = sp.logit("y ~ x + z", data=df)
    >>> mt = sp.margins_table(m)
    >>> _ = sp.regtable(mt, output="text")
    >>> sp.regtable(mt, output="latex", filename="margins.tex")  # doctest: +SKIP
    """
    df = margins(
        result,
        data=data,
        variables=variables,
        at=at,
        method=method,
        eps=eps,
        alpha=alpha,
    )
    n_obs = None
    diag = getattr(result, "diagnostics", {}) or {}
    dinfo = getattr(result, "data_info", {}) or {}
    if isinstance(diag, dict) and diag.get("N") is not None:
        n_obs = diag.get("N")
    elif isinstance(dinfo, dict) and dinfo.get("nobs") is not None:
        n_obs = dinfo.get("nobs")
    return _MarginsResult(df, n_obs=n_obs, method=method)

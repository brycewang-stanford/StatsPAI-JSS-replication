"""Simulated dyadic trade panel with a currency union (teaching DGP).

The layout follows the empirical design of [aytug2026euro] -- country
pairs observed yearly, a treatment that switches on when *both* countries
of a pair have adopted a common currency, effect modifiers that include
pre-adoption trade intensity and economic size -- but every number is
simulated.  Country codes are generic (``C01`` ...); nothing here is
Eurostat data or should be read as an estimate of the euro's effect.

Why it is useful: the true pair-level effect ``tau_true`` is known, pair
fixed effects are correlated with adoption (core pairs trade more *and*
adopt), and the optional second wave adopts during a common downturn --
the two features that bias a pooled causal forest in opposite directions
and that a forest with fixed effects removes.
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

__all__ = ["currency_union_panel"]


def currency_union_panel(seed: int = 0, late_adopters: bool = False) -> pd.DataFrame:
    """Simulated country-pair panel with staggered currency-union adoption.

    Parameters
    ----------
    seed : int, default 0
    late_adopters : bool, default False
        ``False``: 15 countries (12 adopt, 11 in 1999 and one in 2001;
        three never adopt), 105 pairs, 1995-2015.  ``True``: adds six
        countries adopting in 2007, 2008, 2009, 2011, 2014 and 2015 and
        seven that never adopt (378 pairs, 1995-2019), with a common
        downturn in 2009-2012 that coincides with the late adoptions.

    Returns
    -------
    pandas.DataFrame
        One row per pair-year: ``pair``, ``country_i``, ``country_j``,
        ``year``, ``log_trade`` (outcome), ``euro`` (1 when both members
        have adopted), ``ever_euro``, ``adopt_year`` (NaN if never),
        ``pre_trade`` (mean ``log_trade`` of the pair before 1999),
        ``log_gdp_prod`` and ``log_gdppc`` (time-varying), and
        ``tau_true`` (the effect of adoption on ``log_trade`` for that
        pair-year, defined for every row).  ``attrs`` records the design
        and the true average effect on treated rows.

    Notes
    -----
    ``log_trade = 20 + a_ij + g_t + 0.6 (log_gdp_prod - mean) +
    tau_ij,t euro + e`` with AR(1) errors (rho = 0.5) within pairs.  The
    pair effect ``a_ij`` rises with the members' latent "core" index,
    which also raises the chance of adopting, and ``tau`` rises with the
    pair's latent trade intensity and current size:
    ``tau = 0.05 + 0.12 z_trade + 0.06 z_size``, clipped to
    ``[-0.2, 0.6]``.

    Examples
    --------
    >>> import statspai as sp
    >>> df = sp.datasets.currency_union_panel(seed=0)
    >>> df.shape
    (2205, 13)
    >>> round(float(df.loc[df["euro"] == 1, "tau_true"].mean()), 2) > 0
    True

    References
    ----------
    [aytug2026euro], [kattenberg2023causal]
    """
    rng = np.random.default_rng(seed)
    if late_adopters:
        adopt = (
            [1999] * 11
            + [2001]
            + [np.nan] * 3
            + [2007, 2008, 2009, 2011, 2014, 2015]
            + [np.nan] * 7
        )
        years = np.arange(1995, 2020)
    else:
        adopt = [1999] * 11 + [2001] + [np.nan] * 3
        years = np.arange(1995, 2016)
    n_c = len(adopt)
    adopt_arr = np.asarray(adopt, dtype=float)
    adopter = np.isfinite(adopt_arr)
    names = [f"C{c + 1:02d}" for c in range(n_c)]

    # Country traits: adopters are more "core" on average, with overlap.
    core = rng.normal(0.4 * adopter - 0.2, 1.0)
    base_gdp = rng.normal(12.5, 1.0, size=n_c)
    base_pc = rng.normal(10.2, 0.3, size=n_c)
    growth = rng.normal(0.02, 0.01, size=n_c)
    T = years.size
    t_idx = np.arange(T)
    gdp = (
        base_gdp[:, None]
        + growth[:, None] * t_idx[None, :]
        + np.cumsum(rng.normal(0, 0.01, size=(n_c, T)), axis=1)
    )
    pc = base_pc[:, None] + 0.8 * growth[:, None] * t_idx[None, :]

    # Common year effects, with a downturn in 2009-2012.
    g = 0.03 * t_idx + rng.normal(0, 0.03, size=T)
    g[(years >= 2009) & (years <= 2012)] -= np.where(
        years[(years >= 2009) & (years <= 2012)] == 2009, 0.25, 0.15
    )

    pairs = list(itertools.combinations(range(n_c), 2))
    P = len(pairs)
    ci = np.array([p[0] for p in pairs])
    cj = np.array([p[1] for p in pairs])
    latent_trade = (
        core[ci]
        + core[cj]
        + 0.5 * (base_gdp[ci] + base_gdp[cj] - 2 * base_gdp.mean())
        + rng.normal(0, 0.5, size=P)
    )
    a = 0.8 * latent_trade
    z_trade = (latent_trade - latent_trade.mean()) / latent_trade.std()
    both = adopter[ci] & adopter[cj]
    pair_adopt = np.where(both, np.fmax(adopt_arr[ci], adopt_arr[cj]), np.nan)

    gdp_prod = gdp[ci] + gdp[cj]  # (P, T)
    gdppc = 0.5 * (pc[ci] + pc[cj])
    size_mean, size_sd = float(gdp_prod.mean()), float(gdp_prod.std())
    z_size = (gdp_prod - size_mean) / size_sd
    tau = np.clip(0.05 + 0.12 * z_trade[:, None] + 0.06 * z_size, -0.2, 0.6)
    euro = (np.isfinite(pair_adopt)[:, None]) & (years[None, :] >= pair_adopt[:, None])

    e = np.zeros((P, T))
    shock = rng.normal(0, 0.12, size=(P, T))
    e[:, 0] = shock[:, 0] / np.sqrt(1 - 0.25)
    for t in range(1, T):
        e[:, t] = 0.5 * e[:, t - 1] + shock[:, t]
    log_trade = (
        20.0 + a[:, None] + g[None, :] + 0.6 * (gdp_prod - size_mean) + tau * euro + e
    )
    pre = years < 1999
    pre_trade = log_trade[:, pre].mean(axis=1)

    df = pd.DataFrame(
        {
            "pair": np.repeat([f"{names[i]}-{names[j]}" for i, j in pairs], T),
            "country_i": np.repeat([names[i] for i in ci], T),
            "country_j": np.repeat([names[j] for j in cj], T),
            "year": np.tile(years, P),
            "log_trade": log_trade.ravel(),
            "euro": euro.ravel().astype(int),
            "ever_euro": np.repeat(both.astype(int), T),
            "adopt_year": np.repeat(pair_adopt, T),
            "pre_trade": np.repeat(pre_trade, T),
            "log_gdp_prod": gdp_prod.ravel(),
            "log_gdppc": gdppc.ravel(),
            "tau_true": tau.ravel(),
        }
    )
    df.insert(1, "pair_id", np.repeat(np.arange(P), T))
    treated = df["euro"] == 1
    df.attrs.update(
        {
            "design": (
                "simulated dyadic panel, currency union adopted when both "
                "members adopt; layout after Aytug (2026, arXiv:2601.19664)"
            ),
            "paper": "aytug2026euro",
            "simulated": True,
            "late_adopters": bool(late_adopters),
            "true_att": float(df.loc[treated, "tau_true"].mean()),
            "notes": (
                "All values are simulated; country codes are generic. "
                "tau_true is known for every row, including never-adopting "
                "pairs (their counterfactual effect)."
            ),
        }
    )
    return df

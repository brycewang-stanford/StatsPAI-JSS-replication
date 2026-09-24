"""Reference parity: ``fepois`` / ``feglm`` ``vce="wild"`` — **bit-exact** vs boottest.

The restricted (null-imposed) **score wild cluster bootstrap** (Kline-Santos
2012) — the method Stata ``boottest`` runs after ``poisson`` / ``logit`` — is
wired as ``sp.fepois(vce="wild", cluster=...)`` / ``sp.feglm(..., vce="wild")``
with ``boottest``'s exact studentization, reverse-engineered from its enumerated
bootstrap distribution (numerators + t statistics extracted via ``svmat``) and
corroborated against the ``boottest.mata`` source:

* numerator: per-cluster restricted one-step contributions
  ``q_g = (A s_g)[j]`` (``A`` = inverse Hessian at the restricted fit, full
  design) — ``N(w) = Σ w_g q_g``;
* denominator: **cluster-share-centered** CRVE
  ``D²(w) = Σ_g (w_g q_g − c_g N(w))²`` with ``c_g = n_g/N`` (``boottest``'s
  ``ClustShare`` centering — boottest.mata:
  ``pustar = pustar :- ClustShare * colsum(pustar)``);
* observed statistic ``t*(1)`` = boottest's ``r(z)``; p-value counts **strict**
  exceedances ``|t*| > |t_obs|`` over the enumerated 2^G Rademacher grid
  (which includes the identity draw; the identity and its negation tie exactly
  and are excluded by strictness).

In the enumerated regime (``2^G <= wild_reps``) the p-value is deterministic
and **bit-exact** vs Stata; tie margins on these frozen designs are >= 4.6e-4,
far above IRLS convergence noise (~1e-7), so the exact-equality assertions are
stable.

Stata references (Stata 18 MP, boottest 4.5.3, ``reps(2000)`` => enumerated)::

    poisson y x1 x2 x3 i.firm, vce(cluster clu)      // n=240, G=10, 2^10=1024
    boottest x3, reps(2000) weighttype(rademacher)   // p=.31640625  z=-1.0999434
    boottest x2, reps(2000) weighttype(rademacher)   // p=0          z=-5.65642179

    logit y x1 x2 x3 i.firm, vce(cluster clu)        // n=300, G=9,  2^9=512
    boottest x3, reps(2000) weighttype(rademacher)   // p=.95703125  z=0.06450520
    boottest x1, reps(2000) weighttype(rademacher)   // p=.00390625  z=4.56025174
"""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("pyfixest")

from statspai.fixest import feglm, fepois  # noqa: E402

# Frozen Stata boottest enumerated references (see module docstring).
POIS_X3_P = 0.31640625  # = 324/1024
POIS_X2_P = 0.0
LOGIT_X3_P = 0.95703125  # = 490/512
LOGIT_X1_P = 0.00390625  # = 2/512


def _pois_panel() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    n, g = 240, 10
    firm = rng.integers(0, 5, n)
    clu = rng.integers(0, g, n)
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    x3 = rng.normal(size=n)
    mu = np.exp(0.3 + 0.35 * x1 - 0.2 * x2 + 0.0 * x3 + 0.1 * firm)
    y = rng.poisson(mu)
    return pd.DataFrame(
        {"y": y, "x1": x1, "x2": x2, "x3": x3, "firm": firm, "clu": clu}
    )


def _logit_panel() -> pd.DataFrame:
    rng = np.random.default_rng(77)
    n, g = 300, 9
    firm = rng.integers(0, 4, n)
    clu = rng.integers(0, g, n)
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    x3 = rng.normal(size=n)
    p = 1.0 / (1.0 + np.exp(-(0.2 + 0.6 * x1 - 0.3 * x2 + 0.0 * x3 + 0.25 * firm)))
    y = (rng.random(n) < p).astype(int)
    return pd.DataFrame(
        {"y": y, "x1": x1, "x2": x2, "x3": x3, "firm": firm, "clu": clu}
    )


def test_fepois_wild_bit_exact_vs_boottest() -> None:
    df = _pois_panel()
    r = fepois("y ~ x1 + x2 + x3 | firm", data=df, vce="wild", cluster="clu")
    # Enumerated (2^10 <= 9999 default reps) => deterministic, bit-exact.
    assert float(r.pvalues["x3"]) == POIS_X3_P
    assert float(r.pvalues["x2"]) == POIS_X2_P
    assert "wild cluster bootstrap" in r.model_info["vcov_type"]


def test_feglm_logit_wild_bit_exact_vs_boottest() -> None:
    df = _logit_panel()
    r = feglm(
        "y ~ x1 + x2 + x3 | firm",
        data=df,
        family="logit",
        vce="wild",
        cluster="clu",
    )
    assert float(r.pvalues["x3"]) == LOGIT_X3_P
    assert float(r.pvalues["x1"]) == LOGIT_X1_P


def test_glm_score_wild_boot_observed_stat_matches_boottest_z() -> None:
    """The observed studentized statistic equals boottest's r(z)."""
    import statsmodels.api as sm

    from statspai.inference.jackknife import glm_score_wild_boot

    df = _pois_panel()
    codes = pd.factorize(df.clu.values)[0]
    dummies = pd.get_dummies(df.firm, prefix="f", drop_first=True).astype(float).values
    X = np.column_stack(
        [df.x1.values, df.x2.values, df.x3.values, np.ones(len(df)), dummies]
    )
    out = glm_score_wild_boot(
        X, df.y.values.astype(float), sm.families.Poisson(), codes, test_idx=2
    )
    assert np.isclose(out["t_obs"], -1.0999434, atol=1e-5)
    assert out["enumerated"] == 1.0


def test_fepois_wild_requires_cluster_and_rejects_weights() -> None:
    df = _pois_panel()
    with pytest.raises(Exception):
        fepois("y ~ x1 + x2 + x3 | firm", data=df, vce="wild")
    df["w"] = 1.0
    with pytest.raises(Exception):
        fepois(
            "y ~ x1 + x2 + x3 | firm",
            data=df,
            vce="wild",
            cluster="clu",
            weights="w",
        )

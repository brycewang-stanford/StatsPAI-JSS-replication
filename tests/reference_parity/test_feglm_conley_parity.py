"""Reference parity: ``fepois`` / ``feglm`` ``vce="conley"`` vs R ``conleyreg``.

GLM Conley spatial HAC has no Stata reference (``acreg`` supports OLS/2SLS
only), but R **conleyreg** (Duben, CRAN 0.1.9) natively supports
``model="poisson"/"logit"/"probit"``. The implementation follows conleyreg's
convention exactly: score sandwich ``A (S' K S) A`` with the uniform kernel on
great-circle distances (atan2-form haversine, earth radius **6371.01 km** —
read from ``conleyreg/src/distance_functions.cpp``), on the FE-as-dummies
design (conleyreg's own construction is dummy-based; its GLM path does not
even accept ``factor()`` terms, so the FE reference was produced with manual
dummy columns).

Agreement is ~1e-7 absolute (~1e-6 relative); the residual is conleyreg's
internal accumulation order, not the estimator convention — verified by
feeding conleyreg's own coefficients into the formula (residual unchanged)
and by testing rounded/strict kernel variants (all worse).

Frozen references (R 4.5, conleyreg 0.1.9, ``kernel="uniform"``,
``dist_comp="spherical"``, ``dist_cutoff=200``)::

    conleyreg(y  ~ x1 + x2,               model="poisson")  # x1=0.033367118927
    conleyreg(y2 ~ x1 + x2 + f1..f4,      model="poisson")  # x1=0.038715735992
    conleyreg(yb ~ x1 + x2,               model="logit")    # x1=0.082098140165

Note the documented convention split: the OLS menu (`regress`/`feols`/`panel`/
`hdfe_ols`) follows Stata ``acreg``'s planar 111-km/degree distance; the GLM
menu follows ``conleyreg``'s spherical distance, because that is the reference
that exists for GLMs.
"""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("pyfixest")

from statspai.fixest import feglm, fepois  # noqa: E402

CONLEYREG_POIS_NOFE_X1 = 0.033367118927
CONLEYREG_POIS_FE_X1 = 0.038715735992
CONLEYREG_LOGIT_X1 = 0.082098140165
CONLEYREG_LOGIT_X2 = 0.108813744438
_ATOL = 5e-7  # observed residual <= 7.2e-8 (conleyreg accumulation order)


def _conley_glm_panel() -> pd.DataFrame:
    rng = np.random.default_rng(31)
    n = 400
    lat = rng.uniform(30, 45, n)
    lon = rng.uniform(-120, -100, n)
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    mu = np.exp(0.3 + 0.4 * x1 - 0.25 * x2)
    yv = rng.poisson(mu)
    rng2 = np.random.default_rng(32)
    firm = rng2.integers(0, 5, n)
    mu2 = np.exp(0.3 + 0.4 * x1 - 0.25 * x2 + 0.1 * firm)
    y2 = rng2.poisson(mu2)
    p = 1.0 / (1.0 + np.exp(-(0.2 + 0.6 * x1 - 0.3 * x2)))
    yb = (rng2.random(n) < p).astype(int)
    return pd.DataFrame(
        {
            "y": yv,
            "y2": y2,
            "yb": yb,
            "x1": x1,
            "x2": x2,
            "firm": firm,
            "lat": lat,
            "lon": lon,
        }
    )


def test_fepois_conley_matches_conleyreg() -> None:
    df = _conley_glm_panel()
    r0 = fepois(
        "y ~ x1 + x2",
        data=df,
        vce="conley",
        conley_lat="lat",
        conley_lon="lon",
        conley_cutoff=200,
    )
    assert np.isclose(float(r0.std_errors["x1"]), CONLEYREG_POIS_NOFE_X1, atol=_ATOL)
    rf = fepois(
        "y2 ~ x1 + x2 | firm",
        data=df,
        vce="conley",
        conley_lat="lat",
        conley_lon="lon",
        conley_cutoff=200,
    )
    assert np.isclose(float(rf.std_errors["x1"]), CONLEYREG_POIS_FE_X1, atol=_ATOL)
    assert "conleyreg spherical" in rf.model_info["vcov_type"]


def test_feglm_logit_conley_matches_conleyreg() -> None:
    df = _conley_glm_panel()
    r = feglm(
        "yb ~ x1 + x2",
        data=df,
        family="logit",
        vce="conley",
        conley_lat="lat",
        conley_lon="lon",
        conley_cutoff=200,
    )
    assert np.isclose(float(r.std_errors["x1"]), CONLEYREG_LOGIT_X1, atol=_ATOL)
    assert np.isclose(float(r.std_errors["x2"]), CONLEYREG_LOGIT_X2, atol=_ATOL)


def test_fepois_conley_requires_coordinates() -> None:
    df = _conley_glm_panel()
    with pytest.raises(Exception):
        fepois("y ~ x1 + x2", data=df, vce="conley")

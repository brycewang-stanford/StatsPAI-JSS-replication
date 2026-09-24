"""First-stage F after ``sp.ivreg`` matches Stata ``estat firststage``.

``sp.ivreg(..., robust="hc1")`` / ``cluster=`` used to report the classical
(homoskedastic) first-stage F even though every other number on the result
used the requested variance estimator. Stata's ``estat firststage`` after
``ivregress 2sls ..., vce(robust)`` / ``vce(cluster)`` reports the Wald test
of the excluded instruments under that vce, divided by the number of
instruments, on ``F(m, N - k)`` / ``F(m, G - 1)``.

Reference values: Stata 18 MP, run 2026-09-16 on the bundled Card (1995)
extract (``sp.datasets.card_1995()`` written to CSV, ``import delimited``),
with ``gen long cid = mod(_n - 1, 37)``::

    ivregress 2sls lwage (educ = <Z>) exper expersq black south smsa, vce(<V>)
    estat firststage
    matrix S = r(singleresults)      // S[1,4] = F, S[1,5..6] = df

The first stage only involves ``educ`` and integer regressors, so Stata's
float storage of ``lwage`` does not enter these statistics.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

import statspai as sp

CONTROLS = "exper + expersq + black + south + smsa"

# (instruments, vce) -> (F, df_num, df_denom) from Stata 18 MP.
STATA_ESTAT_FIRSTSTAGE = {
    ("nearc4", "nonrobust"): (16.717591436451, 1, 3003),
    ("nearc4", "hc1"): (17.513316096885, 1, 3003),
    ("nearc4", "cluster"): (13.962090377532, 1, 36),
    ("nearc4 + nearc2", "nonrobust"): (9.452688527077, 2, 3002),
    ("nearc4 + nearc2", "hc1"): (9.716770752056, 2, 3002),
    ("nearc4 + nearc2", "cluster"): (7.265342531979, 2, 36),
}


@pytest.fixture(scope="module")
def card():
    df = sp.datasets.card_1995()
    df["cid"] = np.arange(len(df)) % 37
    return df


def _fit(card, instruments, vce):
    kwargs = {"hc1": {"robust": "hc1"}, "cluster": {"cluster": "cid"}}.get(vce, {})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return sp.ivreg(
            f"lwage ~ (educ ~ {instruments}) + {CONTROLS}", data=card, **kwargs
        )


@pytest.mark.parametrize(
    "instruments,vce", list(STATA_ESTAT_FIRSTSTAGE), ids=lambda v: str(v)
)
def test_first_stage_f_matches_stata(card, instruments, vce):
    f_ref, df1, df2 = STATA_ESTAT_FIRSTSTAGE[(instruments, vce)]
    res = _fit(card, instruments, vce)
    fs = res.model_info["first_stage"][0]
    # Stata prints 12 decimals; observed agreement is ~1e-13 relative.
    assert fs["f_statistic"] == pytest.approx(f_ref, rel=1e-10)
    assert fs["f_df"] == (df1, df2)
    assert res.diagnostics["First-stage F (educ)"] == fs["f_statistic"]
    assert res.model_info["first_stage_f"] == pytest.approx(f_ref, rel=1e-10)


@pytest.mark.parametrize("instruments", ["nearc4", "nearc4 + nearc2"])
def test_classical_f_is_kept_alongside_robust_f(card, instruments):
    classic, _, _ = STATA_ESTAT_FIRSTSTAGE[(instruments, "nonrobust")]
    for vce in ("hc1", "cluster"):
        res = _fit(card, instruments, vce)
        fs = res.model_info["first_stage"][0]
        assert fs["f_vce"] == vce
        assert fs["f_statistic_nonrobust"] == pytest.approx(classic, rel=1e-10)
        assert res.diagnostics["First-stage F, non-robust (educ)"] == pytest.approx(
            classic, rel=1e-10
        )
    nonrobust = _fit(card, instruments, "nonrobust")
    assert "First-stage F, non-robust (educ)" not in nonrobust.diagnostics
    fs = nonrobust.model_info["first_stage"][0]
    assert fs["f_statistic"] == fs["f_statistic_nonrobust"]


def test_hc3_first_stage_f_uses_hc3_sandwich(card):
    import statsmodels.api as sm

    res = sp.ivreg(f"lwage ~ (educ ~ nearc4) + {CONTROLS}", data=card, robust="hc3")
    exog = ["exper", "expersq", "black", "south", "smsa"]
    W = sm.add_constant(card[exog + ["nearc4"]])
    ref = sm.OLS(card["educ"], W).fit(cov_type="HC3")
    f_ref = float(ref.wald_test("nearc4 = 0", scalar=True, use_f=True).statistic)
    assert res.model_info["first_stage"][0]["f_statistic"] == pytest.approx(
        f_ref, rel=1e-10
    )


def test_weak_iv_warning_names_the_vce(card):
    # Clustering on 37 groups pulls the two-instrument F below 10.
    with pytest.warns(sp.exceptions.AssumptionWarning) as rec:
        sp.ivreg(
            f"lwage ~ (educ ~ nearc4 + nearc2) + {CONTROLS}",
            data=card,
            cluster="cid",
        )
    msgs = [str(w.message) for w in rec if "Weak instrument" in str(w.message)]
    assert msgs and "cluster F" in msgs[0]

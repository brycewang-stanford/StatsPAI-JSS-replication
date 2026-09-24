"""Cross-language parity: Stata's ``vce()`` grammar on every SE-bearing estimator.

Fixture: ``_fixtures/_generate_vce_grammar_stata.do`` (Stata 18, official
commands only). It generates the data in Stata, exports it at ``%21.16e`` and
records ``_b`` / ``_se`` / ``e(ll)`` for ``vce(oim)`` (or the command's
default), ``vce(robust)`` and ``vce(cluster g)``.

What is pinned, in four layers:

1. **Numbers.** Every estimator x vce cell against Stata at the CLAUDE.md
   default budget ``rtol = 1e-6`` on coefficients *and* standard errors.
   Two estimators carry a larger coefficient budget, each for a stated
   mechanism rather than a gap nobody could explain: Stata's optimiser stops
   short of the optimum StatsPAI's Newton polish reaches, which the test
   proves by asserting StatsPAI's log-likelihood is at least Stata's.
2. **Spellings.** ``True``, ``"robust"``, ``"vce(robust)"`` and ``"r"`` give the
   same standard errors; so do ``vce="cluster g"``, ``cluster="g"``,
   ``vce="cluster", cluster="g"`` and ``"vce(cluster g)"``.
3. **Refusals.** A spelling an estimator does not implement raises
   :class:`~statspai.exceptions.MethodIncompatibility`.
4. **Regression guards for defects that were silent.** Before the shared SE
   parser, ``truncreg`` / ``biprobit`` / ``betareg`` ignored ``robust=`` and
   ``cluster=``; ``logit`` answered ``vce="cluster g"`` with heteroskedasticity-
   robust SEs; ``nbreg``'s robust SEs were ~150% off; ML robust sandwiches
   lacked Stata's N/(N-1); several ML cluster sandwiches carried the
   regress-family (N-1)/(N-K) factor.
"""

from __future__ import annotations

import json
import pathlib
import warnings
from functools import lru_cache
from typing import Any, Callable, Dict, Tuple

import numpy as np
import pandas as pd
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import statspai as sp

from statspai.exceptions import MethodIncompatibility

_FIX = pathlib.Path(__file__).parent / "_fixtures"
DEFAULT_RTOL = 1e-6


@lru_cache(maxsize=None)
def _ref() -> Dict[str, Any]:
    path = _FIX / "vce_grammar_stata.json"
    if not path.exists():  # pragma: no cover
        pytest.skip("run _generate_vce_grammar_stata.do first")
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _data() -> pd.DataFrame:
    path = _FIX / "vce_grammar_data.csv"
    if not path.exists():  # pragma: no cover
        pytest.skip("run _generate_vce_grammar_stata.do first")
    return pd.read_csv(path)


def _trunc() -> pd.DataFrame:
    df = _data()
    return df[df.ytr > 0].reset_index(drop=True)


_VCE: Dict[str, Dict[str, Any]] = {
    "ols": {},
    "oim": {},
    "unadjusted": {},
    "robust": {"vce": "robust"},
    "hc3": {"vce": "hc3"},
    "cluster": {"vce": "cluster g"},
}

Fit = Callable[[Dict[str, Any]], Any]
I = "Intercept"  # noqa: E741 -- reads as the regress/glm intercept name


def _estimators() -> Dict[str, Tuple[Fit, Dict[str, str]]]:
    """``family -> (fit(**vce_kwargs), {stata term: statspai term})``."""
    d = _data
    out: Dict[str, Tuple[Fit, Dict[str, str]]] = {
        "regress": (
            lambda kw: sp.regress("yl ~ x1 + x2", d(), **kw),
            {"x1": "x1", "cons": I},
        ),
        "logit": (
            lambda kw: sp.logit("yb ~ x1 + x2", d(), **kw),
            {"x1": "x1", "cons": I},
        ),
        "probit": (
            lambda kw: sp.probit("yp ~ x1 + x2", d(), **kw),
            {"x1": "x1", "cons": I},
        ),
        "cloglog": (
            lambda kw: sp.cloglog("yb ~ x1 + x2", d(), **kw),
            {"x1": "x1", "cons": I},
        ),
        "poisson": (
            lambda kw: sp.poisson("yc ~ x1 + x2", d(), **kw),
            {"x1": "x1", "cons": "_cons"},
        ),
        "nbreg": (
            lambda kw: sp.nbreg("ynb ~ x1 + x2", d(), **kw),
            {"x1": "x1", "cons": "_cons"},
        ),
        "nb1": (
            lambda kw: sp.nbreg("ynb ~ x1 + x2", d(), dispersion="constant", **kw),
            {"x1": "x1", "cons": "_cons"},
        ),
        "ologit": (
            lambda kw: sp.ologit("yo ~ x1 + x2", d(), **kw),
            {"x1": "x1", "x2": "x2"},
        ),
        "oprobit": (
            lambda kw: sp.oprobit("yo ~ x1 + x2", d(), **kw),
            {"x1": "x1", "x2": "x2"},
        ),
        "mlogit": (
            lambda kw: sp.mlogit("ym ~ x1 + x2", d(), **kw),
            {"x1_1": "[1]x1", "x2_2": "[2]x2", "cons_1": "[1]_cons"},
        ),
        "clogit": (
            lambda kw: sp.clogit(
                "yk ~ x1 + x2",
                d(),
                group="grp",
                **({"vce": "cluster gc"} if kw.get("vce") == "cluster g" else kw),
            ),
            {"x1": "x1", "x2": "x2"},
        ),
        "zip": (
            lambda kw: sp.zip_model("yz ~ x1 + x2", d(), **kw),
            {"x1": "x1", "cons": "const", "inf_x2": "inflate_x2"},
        ),
        "zinb": (
            lambda kw: sp.zinb("yzn ~ x1 + x2", d(), **kw),
            {
                "x1": "x1",
                "cons": "const",
                "inf_x2": "inflate_x2",
                "lnalpha": "ln_alpha",
            },
        ),
        "truncreg": (
            lambda kw: sp.truncreg(_trunc(), "ytr", ["x1", "x2"], ll=0, **kw),
            {"x1": "x1", "cons": "_cons"},
        ),
        "biprobit": (
            lambda kw: sp.biprobit(d(), "y1", "y2", ["x1", "x2"], ["x1", "x2"], **kw),
            {"x1_1": "eq1.x1", "x2_2": "eq2.x2"},
        ),
        "betareg": (
            lambda kw: sp.betareg(d(), "yf", ["x1", "x2"], **kw),
            {"x1": "x1", "cons": "_cons", "scale": "_cons_phi"},
        ),
        "fracreg": (
            lambda kw: sp.fracreg(d(), "yf", ["x1", "x2"], **kw),
            {"x1": "x1", "cons": "_cons"},
        ),
        "liml": (
            lambda kw: sp.liml(
                data=d(), y="yiv", x_endog=["endo"], x_exog=["x1"], z=["z1", "z2"], **kw
            ),
            {"endo": "endo", "x1": "x1"},
        ),
    }
    for fam, dv in (("gaussian", "yl"), ("poisson", "yc"), ("binomial", "yb")):
        out[f"glm_{fam}"] = (
            lambda kw, fam=fam, dv=dv: sp.glm(f"{dv} ~ x1 + x2", d(), family=fam, **kw),
            {"x1": "x1", "cons": I},
        )
    # Non-canonical links: the observed-information bread (Stata's default).
    for lnk, dv, fam in (
        ("probit", "yp", "binomial"),
        ("cloglog", "yb", "binomial"),
        ("log", "yl", "gaussian"),
    ):
        out[f"glm_{lnk}"] = (
            lambda kw, lnk=lnk, dv=dv, fam=fam: sp.glm(
                f"{dv} ~ x1 + x2", d(), family=fam, link=lnk, **kw
            ),
            {"x1": "x1", "cons": I},
        )
    # Panel binary: 12-point non-adaptive Gauss-Hermite on both sides; the
    # cluster variable gg (10 groups) nests the 40 panels.
    panel = dict(id="g", time="id", n_quadrature=12)
    out["xtlogit_re"] = (
        lambda kw: sp.panel_logit(
            d(),
            "ybp",
            ["x1", "x2"],
            method="re",
            **panel,
            **({"vce": "cluster gg"} if kw.get("vce") == "cluster g" else kw),
        ),
        {"x1": "x1", "cons": "_cons"},
    )
    out["xtprobit_re"] = (
        lambda kw: sp.panel_probit(
            d(),
            "ypp",
            ["x1", "x2"],
            method="re",
            **panel,
            **({"vce": "cluster gg"} if kw.get("vce") == "cluster g" else kw),
        ),
        {"x1": "x1", "cons": "_cons"},
    )
    out["xtlogit_fe"] = (
        lambda kw: sp.panel_logit(d(), "ybp", ["x1", "x2"], method="fe", **panel, **kw),
        {"x1": "x1", "x2": "x2"},
    )
    return out


#: Stata keys and the vce label each maps to.
CELLS = (
    [f"regress_{v}" for v in ("ols", "robust", "hc3", "cluster")]
    + [
        f"glm_{f}_{v}"
        for f in ("gaussian", "poisson", "binomial")
        for v in ("oim", "robust", "cluster")
    ]
    + [
        f"{m}_{v}"
        for m in (
            "logit",
            "probit",
            "cloglog",
            "poisson",
            "nbreg",
            "nb1",
            "ologit",
            "oprobit",
            "mlogit",
            "clogit",
            "zip",
            "zinb",
            "truncreg",
            "biprobit",
            "betareg",
        )
        for v in ("oim", "robust", "cluster")
    ]
    + ["fracreg_robust", "fracreg_cluster"]
    + [f"liml_{v}" for v in ("unadjusted", "robust", "cluster")]
    + [
        f"glm_{lnk}_{v}"
        for lnk in ("probit", "cloglog", "log")
        for v in ("oim", "robust", "cluster")
    ]
    + [
        f"{m}_{v}"
        for m in ("xtlogit_re", "xtprobit_re")
        for v in ("oim", "robust", "cluster")
    ]
    + ["xtlogit_fe_oim"]
)

#: Per-family coefficient / SE budgets above the default, with the mechanism.
#: Both are optimiser stopping points on Stata's side: StatsPAI's
#: log-likelihood is higher (asserted in ``test_loglik_at_least_statas``).
BUDGET = {
    # betareg: Stata's ml stops with e(ll) 2.7e-6 below ours; the flat
    # precision direction moves coefficients ~5e-5.
    "betareg": 2e-4,
    # truncreg: Stata stops 5e-11 below ours in e(ll); the intercept sits
    # ~1.7e-6 away.
    "truncreg": 5e-6,
    # zinb: Stata stops 9e-10 below ours in e(ll); /lnalpha is the flat
    # direction and moves ~1.1e-5, dragging the SEs ~1.4e-5.
    "zinb": 5e-5,
}

#: Absolute coefficient budgets, for estimates near zero where a relative
#: budget is meaningless. glm gaussian/log: Stata's ml stops with coefficients
#: ~1e-7 from ours and a *larger* SSR (asserted below); the intercept is
#: -0.0098, so that gap reads as 1e-5 relative.
COEF_ABS = {"glm_log": 5e-7}


@pytest.mark.parametrize(
    "lnk,dv,fam", [("log", "yl", "gaussian"), ("cloglog", "yb", "binomial")]
)
def test_glm_noncanonical_objective_at_least_as_good_as_statas(lnk, dv, fam):
    """At our coefficients the GLM objective is no worse than at Stata's."""
    from scipy import stats as _st

    d = _data()
    ref = _ref()[f"glm_{lnk}_oim"]
    r = _fit(f"glm_{lnk}_oim")
    X = np.column_stack([np.ones(len(d)), d.x1, d.x2])
    y = d[dv].to_numpy()
    ours = r.params[[I, "x1", "x2"]].to_numpy()
    theirs = np.array([ref["b_cons"], ref["b_x1"], ref["b_x2"]])

    def objective(b):
        eta = X @ b
        if fam == "gaussian":
            return float(np.sum((y - np.exp(eta)) ** 2))
        p = 1 - np.exp(-np.exp(eta)) if lnk == "cloglog" else _st.norm.cdf(eta)
        return float(-np.sum(y * np.log(p) + (1 - y) * np.log(1 - p)))

    assert objective(ours) <= objective(theirs) + 1e-9 * abs(objective(theirs))


def _family(cell: str) -> str:
    return cell.rsplit("_", 1)[0]


@lru_cache(maxsize=None)
def _fit(cell: str) -> Any:
    family, vce = cell.rsplit("_", 1)
    fit, _ = _estimators()[family]
    kwargs = dict(_VCE[vce])
    if family == "fracreg" and vce == "robust":
        kwargs = {}  # robust is fracreg's default, as in Stata
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return fit(kwargs)


def _ll(result: Any) -> float | None:
    for store in (
        getattr(result, "diagnostics", None) or {},
        getattr(result, "model_info", None) or {},
    ):
        for key in ("log_likelihood", "ll", "loglik", "quasi_log_likelihood"):
            if key in store and store[key] is not None:
                return float(store[key])
    return None


# --------------------------------------------------------------------------- #
# 1. Numbers
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("cell", CELLS)
def test_coefficients_and_standard_errors_match_stata(cell):
    ref = _ref()[cell]
    family = _family(cell)
    _, names = _estimators()[family]
    r = _fit(cell)
    rtol = BUDGET.get(family, DEFAULT_RTOL)
    for stata_term, sp_term in names.items():
        assert float(r.params[sp_term]) == pytest.approx(
            ref[f"b_{stata_term}"], rel=rtol, abs=COEF_ABS.get(family, 1e-12)
        ), (
            cell,
            stata_term,
        )
        assert float(r.std_errors[sp_term]) == pytest.approx(
            ref[f"se_{stata_term}"], rel=rtol
        ), (
            cell,
            stata_term,
        )


@pytest.mark.parametrize("family", sorted(BUDGET))
def test_loglik_at_least_statas(family):
    """Every widened budget is Stata stopping early, not a different likelihood."""
    cell = f"{family}_oim"
    ours = _ll(_fit(cell))
    stata = _ref()[cell]["ll"]
    assert ours is not None
    assert ours >= stata - 1e-9 * abs(stata)


def test_every_cell_has_a_stata_reference():
    missing = [c for c in CELLS if c not in _ref()]
    assert not missing


@pytest.mark.parametrize(
    "cell", [c for c in CELLS if c.endswith("_cluster") and not c.startswith("regress")]
)
def test_cluster_count_matches_stata(cell):
    # gc nests the clogit groups (30); gg nests the 40 panels (10).
    expected = {"clogit": 30, "xtlogit_re": 10, "xtprobit_re": 10}.get(
        _family(cell), 40
    )
    assert _ref()[cell]["N_clust"] == expected


@pytest.mark.parametrize("family", ["xtlogit_re", "xtprobit_re"])
def test_panel_robust_clusters_on_the_panel(family):
    """xtlogit/xtprobit, re vce(robust) is vce(cluster panelvar)."""
    assert _ref()[f"{family}_robust"]["N_clust"] == 40
    fit = sp.panel_logit if family == "xtlogit_re" else sp.panel_probit
    y = "ybp" if family == "xtlogit_re" else "ypp"
    kw = dict(id="g", time="id", method="re", n_quadrature=12)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        a = fit(_data(), y, ["x1", "x2"], vce="robust", **kw)
        b = fit(_data(), y, ["x1", "x2"], cluster="g", **kw)
    np.testing.assert_array_equal(a.std_errors.values, b.std_errors.values)


def test_fe_logit_refuses_robust_like_stata():
    for kw in ({"vce": "robust"}, {"cluster": "gg"}):
        with pytest.raises(MethodIncompatibility, match="sp.clogit"):
            sp.panel_logit(
                _data(), "ybp", ["x1", "x2"], id="g", time="id", method="fe", **kw
            )


def test_panel_cluster_must_nest_panels():
    with pytest.raises(MethodIncompatibility, match="nested within clusters"):
        sp.panel_logit(
            _data(), "ybp", ["x1", "x2"], id="g", time="id", method="re", cluster="grp"
        )


# --------------------------------------------------------------------------- #
# 2. Spellings
# --------------------------------------------------------------------------- #

SPELLING_FAMILIES = [
    "regress",
    "logit",
    "poisson",
    "nbreg",
    "glm_poisson",
    "ologit",
    "mlogit",
    "zip",
    "truncreg",
    "biprobit",
    "betareg",
    "liml",
]


def _se(family: str, **kw: Any) -> np.ndarray:
    fit, names = _estimators()[family]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = fit(kw)
    return np.array([float(r.std_errors[t]) for t in names.values()])


@pytest.mark.parametrize("family", SPELLING_FAMILIES)
def test_robust_spellings_are_identical(family):
    base = _se(family, vce="robust")
    for kw in (
        {"vce": True},
        {"vce": "vce(robust)"},
        {"vce": "r"},
        {"robust": "robust"},
    ):
        np.testing.assert_array_equal(_se(family, **kw), base, err_msg=str(kw))


@pytest.mark.parametrize("family", SPELLING_FAMILIES)
def test_cluster_spellings_are_identical(family):
    base = _se(family, cluster="g")
    for kw in (
        {"vce": "cluster g"},
        {"vce": "cluster", "cluster": "g"},
        {"vce": "vce(cluster g)"},
        {"vce": "cl g"},
    ):
        np.testing.assert_array_equal(_se(family, **kw), base, err_msg=str(kw))


def test_regress_hc1_spelling_is_statas_robust():
    np.testing.assert_array_equal(
        _se("regress", vce="hc1"), _se("regress", vce="robust")
    )


def test_ivreg_accepts_cluster_keyword_with_cluster_argument():
    df = _data()
    a = sp.ivreg("yiv ~ x1 + (endo ~ z1 + z2)", df, vce="cluster", cluster="g")
    b = sp.ivreg("yiv ~ x1 + (endo ~ z1 + z2)", df, cluster="g")
    np.testing.assert_array_equal(a.std_errors.values, b.std_errors.values)


# --------------------------------------------------------------------------- #
# 3. Refusals
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "family,kw",
    [
        ("logit", {"vce": "hc3"}),
        ("poisson", {"vce": "hc3"}),
        ("nbreg", {"vce": "hc2"}),
        ("ologit", {"vce": "bogus"}),
        ("zip", {"vce": "hac"}),
        ("truncreg", {"vce": "bogus"}),
        ("biprobit", {"vce": "hc3"}),
        ("betareg", {"vce": "wild", "cluster": "g"}),
        ("fracreg", {"vce": "oim"}),
        ("regress", {"vce": "robust g"}),
        ("regress", {"vce": "hc3", "cluster": "g"}),
        ("logit", {"vce": "cluster g", "cluster": "grp"}),
        ("logit", {"vce": "cluster"}),
    ],
)
def test_unsupported_or_contradictory_requests_raise(family, kw):
    fit, _ = _estimators()[family]
    with pytest.raises(MethodIncompatibility):
        fit(kw)


# --------------------------------------------------------------------------- #
# 4. Guards for defects that were silent
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("family", ["truncreg", "biprobit", "betareg"])
def test_robust_and_cluster_are_no_longer_ignored(family):
    oim, robust, cluster = (
        _se(family),
        _se(family, vce="robust"),
        _se(family, cluster="g"),
    )
    assert not np.allclose(oim, robust, rtol=1e-4)
    assert not np.allclose(robust, cluster, rtol=1e-4)


@pytest.mark.parametrize(
    "family", ["logit", "probit", "poisson", "glm_poisson", "ologit", "zip"]
)
def test_ml_robust_carries_n_over_n_minus_1(family):
    n = len(_data())
    ratio = _se(family, vce="robust") / _se(family, vce="hc0")
    np.testing.assert_allclose(ratio, np.sqrt(n / (n - 1.0)), rtol=1e-12)


def test_betareg_refuses_boundary_outcomes():
    df = _data().copy()
    df.loc[0, "yf"] = 1.0
    with pytest.raises(ValueError, match="strictly inside"):
        sp.betareg(df, "yf", ["x1", "x2"])


def test_betareg_cloglog_is_not_logit():
    df = _data()
    a = sp.betareg(df, "yf", ["x1", "x2"], link="logit")
    b = sp.betareg(df, "yf", ["x1", "x2"], link="cloglog")
    assert abs(float(a.params["x1"]) - float(b.params["x1"])) > 1e-3
    with pytest.raises(ValueError, match="unknown link"):
        sp.betareg(df, "yf", ["x1", "x2"], link="bogus")


def test_truncreg_drops_observations_outside_the_limits_like_stata():
    full = _data()
    with pytest.warns(UserWarning, match="outside the truncation limits"):
        r = sp.truncreg(full, "ytr", ["x1", "x2"], ll=0)
    expected = _fit("truncreg_oim")
    np.testing.assert_allclose(r.params.values, expected.params.values, rtol=1e-12)
    assert r.model_info["n_truncated"] == int((full.ytr <= 0).sum())


def test_clogit_rejects_groups_spanning_clusters():
    with pytest.raises(MethodIncompatibility, match="nested within clusters"):
        sp.clogit("yk ~ x1 + x2", _data(), group="grp", cluster="g")

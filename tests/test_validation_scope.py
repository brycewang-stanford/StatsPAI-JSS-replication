"""``sp.validation_scope``: configuration-level evidence for the validated core.

The registry tier is per function; the evidence is per configuration. These
tests keep the map honest: every artifact it cites exists, extraction reads
the fitted configuration, a configuration no artifact exercised is reported
as not covered, and stochastic-only evidence is not promoted to "covered".
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import pandas as pd
import pytest

import statspai as sp
from statspai.exceptions import MethodIncompatibility
from statspai.validation_scope import SCOPES

ROOT = Path(__file__).resolve().parents[1]


def test_every_artifact_exists():
    missing = sorted(
        {row.artifact for scope in SCOPES.values() for row in scope.rows}
        - {
            p
            for p in {row.artifact for s in SCOPES.values() for row in s.rows}
            if (ROOT / p).exists()
        }
    )
    assert not missing


def test_row_kinds_and_dimensions_are_well_formed():
    for name, scope in SCOPES.items():
        for row in scope.rows:
            assert row.kind in {"T1", "T2", "T3", "T4", "B"}, (name, row)
            assert set(row.config) == set(scope.dimensions), (name, row.artifact)


def test_coverage_rows_exist_in_the_coverage_artifact():
    rows = json.loads(
        (
            ROOT / "tests/coverage_monte_carlo/results_b1000/coverage_b1000.json"
        ).read_text(encoding="utf-8")
    )
    names = " ".join(r["name"] for r in rows).lower()
    for token in (
        "regress",
        "ivreg",
        "callaway",
        "sun_abraham",
        "rdrobust",
        "sdid",
        "plr",
        "irm",
        "causal_forest",
    ):
        assert token in names, token


@pytest.fixture(scope="module")
def card():
    return sp.datasets.card_1995()


def test_regress_hc1_is_covered(card):
    scope = sp.validation_scope(sp.regress("lwage ~ educ", data=card, robust="hc1"))
    assert scope["function"] == "regress"
    assert scope["configuration"] == {"vce": "hc1"}
    assert scope["status"] == "covered"
    assert {m["kind"] for m in scope["matched"]} >= {"T2", "B"}


def test_flexible_dml_is_stochastic_only_and_names_the_linear_row(card):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = sp.dml(
            card, y="lwage", d="educ", X=["exper", "black"], model="plr", n_folds=2
        )
    scope = sp.validation_scope(fit)
    assert scope["configuration"] == {"model": "plr", "learners": "flexible"}
    assert scope["status"] == "stochastic_only"
    assert any(
        n["artifact"].endswith("08_dml.py") and n["differs_in"] == "learners"
        for n in scope["near_misses"]
    )


def test_callaway_santanna_default_dr_is_covered_by_the_grid_not_module_04():
    m = sp.datasets.mpdta()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = sp.callaway_santanna(
            m, y="lemp", g="first_treat", t="year", i="countyreal"
        )
    scope = sp.validation_scope(fit)
    assert scope["configuration"]["estimator"] == "dr"
    assert scope["status"] == "covered"
    assert [r["artifact"] for r in scope["matched"]] == [
        "tests/reference_parity/test_cs_weighted_parity.py"
    ]


def test_explicit_configuration_without_a_result():
    assert (
        sp.validation_scope(
            function="rdrobust",
            design="fuzzy",
            bwselect="mserd",
            kernel="triangular",
            p="1",
            code_path="native",
        )["status"]
        == "not_covered"
    )
    assert (
        sp.validation_scope(
            function="causal_forest", treatment="binary", trees=">=2000"
        )["status"]
        == "stochastic_only"
    )
    assert (
        sp.validation_scope(function="causal_forest", treatment="binary", trees="<500")[
            "status"
        ]
        == "not_covered"
    )


def test_unknown_function_and_dimension_raise():
    with pytest.raises(MethodIncompatibility):
        sp.validation_scope(function="ols_but_fancier")
    with pytest.raises(MethodIncompatibility):
        sp.validation_scope(function="dml", learner="lasso")


def test_renders_readably(card):
    text = str(sp.validation_scope(sp.regress("lwage ~ educ", data=card, robust="hac")))
    assert text.startswith("Validation scope: sp.regress  [covered]")
    assert "51_newey.py" in text

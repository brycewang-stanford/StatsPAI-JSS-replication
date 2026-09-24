"""``sp.audit`` must not ask for a test that does not exist for the fit.

An over-identification (Sargan / Hansen J) test has ``L - K`` degrees of
freedom: excluded instruments minus endogenous regressors. On a
just-identified IV fit (``L == K``) there is no restriction to test, so the
audit must report the check as ``not_applicable`` with a reason -- not as
``missing`` (which tells the user to go and run it) and not as ``passed``.
The same audit must *read* the J statistic an over-identified fit already
carries, rather than reporting it missing.

The Card (1995) design of the JSS manuscript is the motivating case: one
endogenous regressor (``educ``) and one excluded instrument (``nearc4``).
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

import statspai as sp
from statspai.smart.audit import _overid_degree, _rule_overidentified

X = ["exper", "expersq", "black", "south", "smsa"]


@pytest.fixture(scope="module")
def card():
    return sp.datasets.card_1995()


def _iv(card, instruments, **kw):
    formula = "lwage ~ " + " + ".join(X) + f" + (educ ~ {instruments})"
    return sp.iv(formula, data=card, **kw)


def _check(report, name):
    matches = [c for c in report["checks"] if c["name"] == name]
    assert len(matches) == 1, report
    return matches[0]


class TestJustIdentified:
    def test_overid_is_not_applicable_with_reason(self, card):
        report = sp.audit(_iv(card, "nearc4"))
        chk = _check(report, "overid_test")
        assert chk["status"] == "not_applicable"
        assert chk["suggest_function"] is None
        assert "just-identified" in chk["reason"]
        assert chk["severity"] == "info"

    def test_not_applicable_is_excluded_from_denominator(self, card):
        report = sp.audit(_iv(card, "nearc4"))
        s = report["summary"]
        assert s["not_applicable"] == 1
        assert s["passed"] + s["failed"] + s["missing"] == s["n_total"]
        assert s["n_total"] + s["not_applicable"] == len(report["checks"])
        assert report["coverage"] == pytest.approx(s["passed"] / s["n_total"], abs=1e-3)

    def test_not_applicable_is_not_listed_as_missing(self, card):
        report = sp.audit(_iv(card, "nearc4"))
        assert "overid_test" not in {c["name"] for c in report.missing}
        assert [c["name"] for c in report.not_applicable] == ["overid_test"]

    def test_rendering_says_na_not_missing(self, card):
        text = str(sp.audit(_iv(card, "nearc4")))
        assert "missing overid_test" not in text
        assert "n/a     overid_test" in text
        assert "; 1 n/a)" in text

    def test_json_and_mcp_payload_keep_the_status(self, card):
        from statspai.agent._result_cache import RESULT_CACHE
        from statspai.agent.workflow_tools import execute_workflow_tool

        fit = _iv(card, "nearc4")
        payload = json.loads(json.dumps(sp.audit(fit)))
        assert _check(payload, "overid_test")["status"] == "not_applicable"

        rid = RESULT_CACHE.put(fit, tool="iv")
        out = execute_workflow_tool("audit_result", {"result_id": rid})
        chk = _check(out, "overid_test")
        assert chk["status"] == "not_applicable"
        assert "just-identified" in chk["reason"]
        assert out["summary"]["not_applicable"] == 1


class TestOverIdentified:
    def test_sargan_already_on_the_fit_is_read(self, card):
        fit = _iv(card, "nearc4 + nearc2")
        chk = _check(sp.audit(fit), "overid_test")
        assert chk["status"] == "passed"
        assert chk["value"] == pytest.approx(fit.diagnostics["Sargan p-value"])

    def test_robust_fit_reads_hansen_j(self, card):
        fit = _iv(card, "nearc4 + nearc2", robust="hc1")
        chk = _check(sp.audit(fit), "overid_test")
        assert chk["status"] == "passed"
        assert chk["value"] == pytest.approx(fit.diagnostics["Hansen J p-value"])

    def test_rejection_is_failed(self):
        # Two instruments, one of which enters the outcome directly: the
        # exclusion restriction is false and the J test must reject.
        rng = np.random.default_rng(3)
        n = 4000
        z1, z2, u = rng.normal(size=(3, n))
        d = z1 + z2 + u + rng.normal(size=n)
        y = 1.0 * d + 1.5 * z2 + u + rng.normal(size=n)
        df = pd.DataFrame({"y": y, "d": d, "z1": z1, "z2": z2})
        chk = _check(sp.audit(sp.iv("y ~ (d ~ z1 + z2)", data=df)), "overid_test")
        assert chk["status"] == "failed"
        assert chk["value"] < 0.05


class TestDegreeResolution:
    @pytest.mark.parametrize(
        "info, degree",
        [
            ({"Sargan df": 2}, 2),
            ({"hansen_df": 0}, 0),
            ({"hansen_j": {"df": 1, "pvalue": 0.4}}, 1),
            ({"n_moments": 3, "n_params": 3}, 0),
            ({"n_moments": 5, "n_params": 3}, 2),
            ({"N instruments": 1, "N endogenous": 1}, 0),
            ({"N instruments": 1, "N endogenous": 2}, -1),
            ({"n_instruments": 12, "n_regressors": 3}, 9),
            ({"overidentified": False}, 0),
            ({"overidentified": True}, None),
            ({}, None),
            ({"N instruments": float("nan"), "N endogenous": 1}, None),
        ],
    )
    def test_overid_degree(self, info, degree):
        assert _overid_degree(info) == degree

    def test_under_identified_reason(self):
        reason = _rule_overidentified({"N instruments": 1, "N endogenous": 2})
        assert reason.startswith("under-identified")

    def test_unknown_metadata_falls_back_to_evaluation(self):
        # When the stored metadata cannot decide, the rule abstains and the
        # check is evaluated normally (here: missing), never silently dropped.
        assert _rule_overidentified({}) is None

    def test_exactly_identified_gmm(self):
        rng = np.random.default_rng(0)
        x = rng.normal(size=500)
        y = 2.0 * x + rng.normal(size=500)
        fit = sp.gmm(
            lambda theta, data: (data["y"] - theta[0] * data["x"]).to_numpy()[:, None]
            * data[["x"]].to_numpy(),
            data=pd.DataFrame({"y": y, "x": x}),
            theta0=np.array([0.0]),
        )
        assert fit.model_info["overidentified"] is False
        # The generic GMM family routes to IV; J has zero degrees of freedom.
        assert _overid_degree({**fit.model_info, **(fit.diagnostics or {})}) == 0


class TestNextStepsAgreeWithAudit:
    """``result.next_steps()`` must not recommend the test audit calls n/a."""

    @staticmethod
    def _actions(fit):
        return [s["action"] for s in fit.next_steps()]

    def test_just_identified_has_no_overid_step(self, card):
        actions = self._actions(_iv(card, "nearc4"))
        assert "sp.estat(result, 'overid')" not in actions
        assert "sp.estat(result, 'firststage')" in actions

    def test_over_identified_keeps_overid_step(self, card):
        actions = self._actions(_iv(card, "nearc4 + nearc2"))
        assert "sp.estat(result, 'overid')" in actions

    def test_robust_refit_suggestion_keeps_the_instruments(self, card):
        actions = self._actions(_iv(card, "nearc4"))
        assert any(a.startswith("sp.iv(") and "robust='hc1'" in a for a in actions)
        assert not any(a.startswith("sp.regress(") for a in actions)

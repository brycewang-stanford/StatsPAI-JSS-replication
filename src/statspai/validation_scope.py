"""Configuration-level validation scope for the validated core.

A registry tier (``certified`` / ``validated``) is attached to a *function*.
The evidence behind it is attached to *configurations*: a Track A module
runs one estimator variant, with one inference option, on one kind of data,
through one code path, and compares one output. ``sp.dml`` being certified
does not mean that the configuration a user just ran -- say, the partially
linear model with gradient-boosting learners -- is the one the parity row
exercised; the parity row used linear learners on fixed folds, and the
coverage row used a different model.

This module records, for the twelve estimators of the paper's validation
suite, which configurations each artifact exercises, along the dimensions
that change the computation or the inference:

    method variant x inference x data condition x code path x output

``sp.validation_scope(result)`` reads the configuration from a fitted
result, and reports the evidence rows that match it *exactly*, the rows
that differ in one dimension (so the user can see what is and is not
covered), and an overall status:

* ``"covered"`` -- at least one deterministic reference or known-truth row
  (T1/T2) matches the configuration;
* ``"stochastic_only"`` -- only seed-replicated (T3), disclosure (T4) or
  coverage-simulation (B) rows match;
* ``"not_covered"`` -- no row matches; the function's tier is a statement
  about other configurations.

The map is deliberately narrower than the registry: an unlisted option is
reported as not covered, never inferred to be covered by proximity.
Every artifact path is checked to exist by
``tests/test_validation_scope.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

__all__ = ["validation_scope", "ValidationScope", "SCOPE_FUNCTIONS"]

ANY = "*"
_DETERMINISTIC = {"T1", "T2"}


@dataclass(frozen=True)
class _Row:
    """One artifact and the configuration it exercises."""

    kind: str  # "T1" | "T2" | "T3" | "T4" | "B"
    artifact: str  # repo-relative path
    config: Mapping[str, str]  # dimension -> value, or ANY
    compares: str  # the output that is compared

    def matches(self, cfg: Mapping[str, Optional[str]]) -> Tuple[bool, List[str]]:
        misses = [
            dim
            for dim, want in self.config.items()
            if want != ANY and cfg.get(dim) is not None and cfg.get(dim) != want
        ]
        unknown = [dim for dim in self.config if cfg.get(dim) is None]
        return (not misses and not unknown), misses


@dataclass(frozen=True)
class _Scope:
    function: str
    dimensions: Tuple[str, ...]
    extract: Callable[[Any], Dict[str, Optional[str]]]
    rows: Tuple[_Row, ...]
    note: str = ""


def _mi(result: Any) -> Dict[str, Any]:
    return dict(getattr(result, "model_info", None) or {})


def _lower(v: Any) -> Optional[str]:
    return None if v is None else str(v).lower()


# --------------------------------------------------------------------------- #
#  Configuration extractors (read only what the fit recorded)
# --------------------------------------------------------------------------- #


def _x_regress(r: Any) -> Dict[str, Optional[str]]:
    mi = _mi(r)
    robust = _lower(mi.get("robust"))
    if mi.get("cluster") is not None:
        vce = "cluster"
    elif robust in {"nonrobust", None}:
        vce = "classical"
    else:
        vce = robust
    return {"vce": vce}


def _x_iv(r: Any) -> Dict[str, Optional[str]]:
    mi = _mi(r)
    kappa = mi.get("kappa")
    estimator = (
        "2sls" if kappa is not None and abs(float(kappa) - 1.0) < 1e-12 else "kclass"
    )
    from .smart.audit import _overid_degree  # shared identification rule

    view = dict(mi)
    view.update(getattr(r, "diagnostics", None) or {})
    degree = _overid_degree(view)
    ident = None if degree is None else ("just" if degree == 0 else "over")
    vce = _x_regress(r)["vce"]
    return {"estimator": estimator, "vce": vce, "identification": ident}


def _x_feols(r: Any) -> Dict[str, Optional[str]]:
    return {"vcov": _lower(getattr(r, "vcov_type", None))}


def _x_cs(r: Any) -> Dict[str, Optional[str]]:
    mi = _mi(r)
    return {
        "estimator": _lower(mi.get("estimator")),
        "control_group": _lower(mi.get("control_group")),
        "weights": "weighted" if mi.get("weighted") else "none",
        "inference": "bootstrap" if mi.get("bstrap") else "analytic",
        "base_period": _lower(mi.get("base_period")),
    }


def _x_sa(r: Any) -> Dict[str, Optional[str]]:
    mi = _mi(r)
    return {"control_group": _lower(mi.get("control_group"))}


def _x_rd(r: Any) -> Dict[str, Optional[str]]:
    mi = _mi(r)
    return {
        "design": _lower(mi.get("rd_type")),
        "bwselect": _lower(mi.get("bwselect")),
        "kernel": _lower(mi.get("kernel")),
        "p": None if mi.get("polynomial_p") is None else str(mi.get("polynomial_p")),
        "code_path": "port" if mi.get("cct_delegation") else "native",
    }


def _x_rddensity(r: Any) -> Dict[str, Optional[str]]:
    return {"code_path": _lower(_mi(r).get("backend"))}


def _x_synth(r: Any) -> Dict[str, Optional[str]]:
    mi = _mi(r)
    v = _lower(mi.get("v_method"))
    nonunique = mi.get("weight_solution_nonunique")
    return {
        "predictors": "special_nested" if v == "nested" else "outcome_path",
        # The solver records whether near-optimal starts landed on different
        # donor-weight classes; certification holds only for identified fits.
        "weights": (
            None if nonunique is None else ("nonunique" if nonunique else "unique")
        ),
        "code_path": _lower(mi.get("backend")),
    }


def _x_sdid(r: Any) -> Dict[str, Optional[str]]:
    mi = _mi(r)
    return {
        "se_method": _lower(mi.get("se_method")),
        "code_path": _lower(mi.get("backend")),
    }


def _x_dml(r: Any) -> Dict[str, Optional[str]]:
    mi = _mi(r)
    learners = {str(mi.get("ml_g")), str(mi.get("ml_m"))}
    linear = learners <= {"LinearRegression", "LogisticRegression"}
    return {
        "model": _lower(mi.get("dml_model")),
        "learners": "linear" if linear else "flexible",
    }


def _x_forest(r: Any) -> Dict[str, Optional[str]]:
    discrete = getattr(r, "discrete_treatment", None)
    n_trees = getattr(r, "n_estimators", None)
    if n_trees is None:
        trees = None
    elif int(n_trees) >= 2000:
        trees = ">=2000"
    elif int(n_trees) >= 500:
        trees = "500-1999"
    else:
        trees = "<500"
    if discrete is None:
        return {"treatment": None, "trees": trees}
    values = getattr(r, "_treatment_values", None)
    binary = bool(discrete) and (values is None or len(values) == 2)
    return {"treatment": "binary" if binary else "continuous", "trees": trees}


def _x_psm(r: Any) -> Dict[str, Optional[str]]:
    mi = _mi(r)
    return {
        "method": _lower(mi.get("method")),
        "n_matches": None if mi.get("n_matches") is None else str(mi.get("n_matches")),
        "replace": _lower(mi.get("replace")),
        "caliper": "none" if mi.get("caliper") is None else "set",
    }


# --------------------------------------------------------------------------- #
#  The evidence map
# --------------------------------------------------------------------------- #

_R = "tests/r_parity/"
_RP = "tests/reference_parity/"
_B = "tests/coverage_monte_carlo/results_b1000/coverage_b1000.json"
_VCE = _RP + "test_vce_grammar_stata_parity.py"

SCOPES: Dict[str, _Scope] = {
    "regress": _Scope(
        "regress",
        ("vce",),
        _x_regress,
        (
            _Row(
                "T2",
                _R + "01_ols.py",
                {"vce": "hc1"},
                "coefficients and HC1 SEs vs lm+sandwich",
            ),
            _Row(
                "T2",
                _VCE,
                {"vce": "hc1"},
                "coefficients and robust SEs vs Stata regress",
            ),
            _Row(
                "T2",
                _VCE,
                {"vce": "classical"},
                "coefficients and SEs vs Stata regress",
            ),
            _Row("T2", _R + "55_hc2_hc3.py", {"vce": "hc2"}, "HC2 SEs vs sandwich"),
            _Row("T2", _R + "55_hc2_hc3.py", {"vce": "hc3"}, "HC3 SEs vs sandwich"),
            _Row(
                "T2",
                _R + "14_ols_cluster.py",
                {"vce": "cluster"},
                "CR1 SEs vs sandwich::vcovCL",
            ),
            _Row("T2", _VCE, {"vce": "cluster"}, "cluster SEs vs Stata regress"),
            _Row(
                "T2", _R + "51_newey.py", {"vce": "hac"}, "Newey-West SEs vs sandwich"
            ),
            _Row("B", _B, {"vce": "hc1"}, "95% CI coverage on a known-truth RCT DGP"),
        ),
    ),
    "iv": _Scope(
        "iv",
        ("estimator", "vce", "identification"),
        _x_iv,
        (
            _Row(
                "T2",
                _R + "02_iv.py",
                {"estimator": "2sls", "vce": "hc1", "identification": "just"},
                "coefficients and HC1 SEs vs AER::ivreg",
            ),
            _Row(
                "T2",
                _RP + "test_iv_card_aer_parity.py",
                {"estimator": "2sls", "vce": ANY, "identification": ANY},
                "coefficient and classical / HC1 / CR1 SEs vs AER::ivreg + sandwich on the "
                "original Card extract, just- and over-identified; Sargan statistic",
            ),
            _Row(
                "T2",
                _R + "59_liml.py",
                {"estimator": "kclass", "vce": ANY, "identification": "over"},
                "LIML coefficients vs ivmodel",
            ),
            _Row(
                "B",
                _B,
                {"estimator": "2sls", "vce": "hc1", "identification": "just"},
                "95% CI coverage, strong single instrument",
            ),
        ),
        note="sp.iv and sp.ivreg share this map.",
    ),
    "fast.feols": _Scope(
        "fast.feols",
        ("vcov",),
        _x_feols,
        (
            _Row(
                "T2",
                _R + "03_hdfe.py",
                {"vcov": "iid"},
                "coefficients and iid SEs vs fixest::feols",
            ),
            _Row(
                "T2",
                _R + "15_hdfe_cluster.py",
                {"vcov": "cr1"},
                "CR1 SEs vs fixest::feols(cluster=)",
            ),
        ),
        note="The Track B fixed-effects coverage row runs sp.panel, not this entry point.",
    ),
    "callaway_santanna": _Scope(
        "callaway_santanna",
        ("estimator", "control_group", "weights", "inference", "base_period"),
        _x_cs,
        (
            _Row(
                "T2",
                _R + "04_csdid.py",
                {
                    "estimator": "reg",
                    "control_group": "nevertreated",
                    "weights": "none",
                    "inference": "analytic",
                    "base_period": "universal",
                },
                "simple / dynamic / group ATT and SEs vs did and csdid",
            ),
            _Row(
                "T2",
                _RP + "test_cs_weighted_parity.py",
                {
                    "estimator": ANY,
                    "control_group": ANY,
                    "weights": ANY,
                    "inference": "analytic",
                    "base_period": "universal",
                },
                "aggregated ATT and SE vs did::att_gt over dr/reg/ipw x never/not-yet x weights",
            ),
            _Row(
                "T3",
                _RP + "test_cs_inference_parity.py",
                {
                    "estimator": ANY,
                    "control_group": "nevertreated",
                    "weights": "none",
                    "inference": "bootstrap",
                    "base_period": ANY,
                },
                "multiplier-bootstrap SEs and uniform bands vs did (independent draws)",
            ),
            _Row(
                "B",
                _B,
                {
                    "estimator": "reg",
                    "control_group": "nevertreated",
                    "weights": "none",
                    "inference": "analytic",
                    "base_period": "universal",
                },
                "95% CI coverage of the simple ATT on a staggered DGP",
            ),
        ),
    ),
    "sun_abraham": _Scope(
        "sun_abraham",
        ("control_group",),
        _x_sa,
        (
            _Row(
                "T2",
                _R + "05_sunab.py",
                {"control_group": "nevertreated"},
                "IW aggregate and event-time effects vs fixest::sunab and eventstudyinteract",
            ),
            _Row(
                "B",
                _B,
                {"control_group": "nevertreated"},
                "95% CI coverage of the overall ATT",
            ),
        ),
    ),
    "rdrobust": _Scope(
        "rdrobust",
        ("design", "bwselect", "kernel", "p", "code_path"),
        _x_rd,
        (
            _Row(
                "T2",
                _R + "06_rd.py",
                {
                    "design": "sharp",
                    "bwselect": "mserd",
                    "kernel": "triangular",
                    "p": "1",
                    "code_path": "native",
                },
                "conventional / robust estimates, SEs and h, b vs rdrobust (R and Stata)",
            ),
            _Row(
                "B",
                _B,
                {
                    "design": "sharp",
                    "bwselect": "mserd",
                    "kernel": "triangular",
                    "p": "1",
                    "code_path": "native",
                },
                "robust bias-corrected CI coverage on a known-jump DGP",
            ),
        ),
        note="Other bandwidth selectors are pinned for sp.rdbwselect (Track A module 88), "
        "not for this entry point.",
    ),
    "rddensity": _Scope(
        "rddensity",
        ("code_path",),
        _x_rddensity,
        (
            _Row(
                "T2",
                _R + "09_rddensity.py",
                {"code_path": "native"},
                "density-difference test statistic and p-value vs rddensity",
            ),
        ),
    ),
    "synth": _Scope(
        "synth",
        ("predictors", "weights", "code_path"),
        _x_synth,
        (
            _Row(
                "T2",
                _R + "52_scm_unique.py",
                {
                    "predictors": "outcome_path",
                    "weights": "unique",
                    "code_path": "native",
                },
                "weights and gap vs Synth and synth on a uniquely identified DGP",
            ),
            _Row(
                "T4",
                _R + "07_scm.py",
                {"predictors": "special_nested", "weights": ANY, "code_path": "native"},
                "Basque gap: reference implementations disagree (non-unique V, W)",
            ),
        ),
        note="Classical SCM only; other sp.synth methods have their own modules.",
    ),
    "sdid": _Scope(
        "sdid",
        ("se_method", "code_path"),
        _x_sdid,
        (
            _Row(
                "T2",
                _R + "12_sdid.py",
                {"se_method": ANY, "code_path": "native"},
                "point ATT vs synthdid (the SE is not part of this row)",
            ),
            _Row(
                "B",
                _B,
                {"se_method": "placebo", "code_path": "native"},
                "placebo-SE CI coverage, one treated unit",
            ),
        ),
    ),
    "dml": _Scope(
        "dml",
        ("model", "learners"),
        _x_dml,
        (
            _Row(
                "T2",
                _R + "08_dml.py",
                {"model": "plr", "learners": "linear"},
                "theta and SE vs DoubleML on shared folds",
            ),
            _Row(
                "T2",
                _R + "71_dml_family.py",
                {"model": "irm", "learners": "linear"},
                "theta and SE vs DoubleML on shared folds",
            ),
            _Row(
                "T2",
                _R + "71_dml_family.py",
                {"model": "pliv", "learners": "linear"},
                "theta and SE vs DoubleML on shared folds",
            ),
            _Row(
                "T2",
                _R + "71_dml_family.py",
                {"model": "iivm", "learners": "linear"},
                "theta and SE vs DoubleML on shared folds",
            ),
            _Row(
                "B",
                _B,
                {"model": "plr", "learners": "flexible"},
                "95% CI coverage with the default learners: 0.883, bias 0.5 MC SD "
                "(nuisance regularisation; see mechanisms/dml_plr_learners.py)",
            ),
            _Row(
                "B",
                _B,
                {"model": "irm", "learners": "flexible"},
                "95% CI coverage with the default learners",
            ),
        ),
        note="With flexible learners the estimate depends on the learner, so deterministic "
        "parity is only possible for fixed learners and folds.",
    ),
    "causal_forest": _Scope(
        "causal_forest",
        ("treatment", "trees"),
        _x_forest,
        (
            _Row(
                "T3",
                _RP + "test_grf_seed_mc_equivalence.py",
                {"treatment": "binary", "trees": ">=2000"},
                "seed-replicated AIPW ATE/ATT vs grf (2,000 and 8,000 trees): equivalence "
                "within 0.1 sampling SE on both datasets; equal seed-to-seed noise",
            ),
            _Row(
                "T3",
                _RP + "test_grf_seed_mc_equivalence.py",
                {"treatment": "binary", "trees": "500-1999"},
                "seed-replicated AIPW ATE/ATT vs grf (500 trees): equivalence within "
                "0.1 sampling SE on both datasets",
            ),
            _Row(
                "T3",
                _R + "13_causal_forest.py",
                {"treatment": "binary", "trees": ">=2000"},
                "single-draw AIPW ATE/ATT vs grf",
            ),
            _Row(
                "B",
                _B,
                {"treatment": "binary", "trees": ">=2000"},
                "coverage of the forest's own AIPW interval (2,000 trees)",
            ),
        ),
        note="A continuous treatment is compared with grf only in the Card worked example.",
    ),
    "psm": _Scope(
        "psm",
        ("method", "n_matches", "replace", "caliper"),
        _x_psm,
        (
            _Row(
                "T2",
                _R + "11_psm.py",
                {
                    "method": "nearest",
                    "n_matches": "1",
                    "replace": "true",
                    "caliper": "none",
                },
                "ATT vs MatchIt; Abadie-Imbens SE vs Stata teffects psmatch",
            ),
        ),
    ),
}
SCOPES["ivreg"] = SCOPES["iv"]

#: Functions with a configuration map.
SCOPE_FUNCTIONS = tuple(sorted(SCOPES))


class ValidationScope(dict):
    """Evidence for one fitted configuration (a ``dict``; prints as a table).

    Returned by :func:`validation_scope`. Keys: ``function``,
    ``configuration``, ``status`` (``"covered"``, ``"stochastic_only"`` or
    ``"not_covered"``), ``matched``, ``near_misses`` and ``note``.

    Examples
    --------
    >>> import statspai as sp
    >>> scope = sp.validation_scope(function="causal_forest",
    ...                             treatment="binary", trees=">=2000")
    >>> scope["status"]
    'stochastic_only'
    """

    __slots__ = ()

    def _render(self) -> str:
        lines = [
            f"Validation scope: sp.{self['function']}  [{self['status']}]",
            "configuration: "
            + ", ".join(f"{k}={v}" for k, v in self["configuration"].items()),
        ]
        if self["matched"]:
            lines.append("evidence for this configuration:")
            for row in self["matched"]:
                lines.append(f"  {row['kind']:<3} {row['artifact']}: {row['compares']}")
        else:
            lines.append("no artifact exercises this configuration")
        if self["near_misses"]:
            lines.append("evidence differing in one dimension:")
            for row in self["near_misses"]:
                lines.append(
                    f"  {row['kind']:<3} {row['artifact']} (differs in {row['differs_in']})"
                )
        if self.get("note"):
            lines.append(f"note: {self['note']}")
        return "\n".join(lines)

    __str__ = _render
    __repr__ = _render


def validation_scope(
    result: Any = None, *, function: Optional[str] = None, **configuration: Any
) -> ValidationScope:
    """Which validation artifacts cover the configuration that was run?

    Parameters
    ----------
    result : fitted result, optional
        A result from one of the validation-suite estimators. Its
        configuration (estimator variant, inference option, treatment type,
        code path, ...) is read from the fitted object.
    function : str, optional
        Name of the estimator (``"dml"``, ``"callaway_santanna"``, ...),
        required when ``result`` is omitted and otherwise inferred.
    **configuration
        Dimension values to use instead of (or in addition to) those read
        from ``result``, e.g. ``validation_scope(function="dml",
        model="plr", learners="flexible")``.

    Returns
    -------
    ValidationScope
        A ``dict`` with ``function``, ``configuration``, ``status``
        (``"covered"``, ``"stochastic_only"``, ``"not_covered"``),
        ``matched`` (artifacts exercising exactly this configuration),
        ``near_misses`` (artifacts differing in one dimension), and
        ``note``.

    Examples
    --------
    >>> import statspai as sp
    >>> scope = sp.validation_scope(function="dml", model="plr", learners="linear")
    >>> scope["status"]
    'covered'
    >>> sp.validation_scope(function="dml", model="plr", learners="flexible")["status"]
    'stochastic_only'

    Notes
    -----
    The registry tier of a function summarises its evidence; this function
    answers the narrower question a user or agent actually has after a
    fit. An option absent from the map is reported as not covered rather
    than inferred from a neighbouring configuration.
    """
    name = function or _function_of(result)
    if name is None or name not in SCOPES:
        from .exceptions import MethodIncompatibility

        raise MethodIncompatibility(
            f"No configuration-level evidence map for {name!r}.",
            recovery_hint=(
                "validation_scope covers the twelve validation-suite estimators: "
                + ", ".join(SCOPE_FUNCTIONS)
                + ". For other functions read sp.describe_function(name)['validation_notes']."
            ),
            diagnostics={"function": name},
        )
    scope = SCOPES[name]
    cfg: Dict[str, Optional[str]] = {d: None for d in scope.dimensions}
    if result is not None:
        cfg.update(scope.extract(result))
    for key, value in configuration.items():
        if key not in scope.dimensions:
            from .exceptions import MethodIncompatibility

            raise MethodIncompatibility(
                f"{key!r} is not a dimension of the {name} map.",
                recovery_hint=f"Dimensions: {', '.join(scope.dimensions)}.",
                diagnostics={"function": name, "dimension": key},
            )
        cfg[key] = _lower(value)

    matched, near = [], []
    for row in scope.rows:
        ok, misses = row.matches(cfg)
        rec = {
            "kind": row.kind,
            "artifact": row.artifact,
            "compares": row.compares,
            "configuration": dict(row.config),
        }
        if ok:
            matched.append(rec)
        elif len(misses) == 1 and not any(
            n["artifact"] == row.artifact and n["differs_in"] == misses[0] for n in near
        ):
            near.append({**rec, "differs_in": misses[0]})
    kinds = {m["kind"] for m in matched}
    if kinds & _DETERMINISTIC:
        status = "covered"
    elif kinds:
        status = "stochastic_only"
    else:
        status = "not_covered"
    return ValidationScope(
        {
            "function": name,
            "configuration": cfg,
            "status": status,
            "matched": matched,
            "near_misses": near,
            "note": scope.note,
        }
    )


_METHOD_TO_FUNCTION = (
    ("callaway and sant'anna", "callaway_santanna"),
    ("sun and abraham", "sun_abraham"),
    ("rd estimation", "rdrobust"),
    ("density test", "rddensity"),
    ("synthetic control", "synth"),
    ("synthetic difference", "sdid"),
    ("double ml", "dml"),
    ("matching", "psm"),
)


def _function_of(result: Any) -> Optional[str]:
    if result is None:
        return None
    if type(result).__name__ == "CausalForest":
        return "causal_forest"
    if type(result).__name__ == "FeolsResult":
        return "fast.feols"
    mi = _mi(result)
    model_type = _lower(mi.get("model_type")) or ""
    if model_type.startswith("iv") or "2sls" in model_type:
        return "iv"
    if model_type == "ols":
        return "regress"
    method = (
        (_lower(getattr(result, "method", None)) or "")
        + " "
        + (_lower(mi.get("estimator_label")) or "")
    )
    for token, fn in _METHOD_TO_FUNCTION:
        if token in method:
            return fn
    return None

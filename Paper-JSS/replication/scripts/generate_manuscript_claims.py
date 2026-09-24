#!/usr/bin/env python3
"""Generate auditable LaTeX macros for live StatsPAI inventory claims."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:  # _paths.py sits beside this script; importlib loaders do not add the script dir
    sys.path.insert(0, _SCRIPTS_DIR)

from _paths import PAPER_ROOT, statspai_root

REPO_ROOT = statspai_root()
OUTPUT = PAPER_ROOT / "manuscript" / "generated_claims.tex"


def _claims() -> dict[str, int | str]:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import stability_audit  # noqa: PLC0415

    sys.path.insert(0, str(PAPER_ROOT / "replication" / "scripts"))
    import agent_interface_audit  # noqa: PLC0415

    sys.path.insert(0, str(REPO_ROOT / "src"))
    import statspai as sp  # noqa: PLC0415

    audit = stability_audit.collect()
    report = sp.validation_report()
    status = report.registry["per_validation_status"]
    breakdown = audit["auto_unbacked_breakdown"]
    schema = agent_interface_audit._schema_quality()
    # The evidence-kind split. `certified` + `validated` sums two claims that
    # answer different questions -- "does StatsPAI agree with R/Stata" and
    # "does StatsPAI recover the right answer" -- and only the first is a
    # parity claim. The manuscript quotes them separately so the smaller
    # claim cannot borrow the larger one's authority.
    parity = sp.parity_summary()
    kinds = parity["by_evidence_kind"]
    strata = parity["denominators"]
    r_modules = report.evidence["r_parity"]["matched_modules"]
    stata_modules = report.evidence["stata_parity"]["modules"]
    return {
        # Printed release number: the manuscript never hard-codes it, so a
        # version bump cannot leave one section naming an older release.
        "StatsPAIVersion": sp.__version__,
        "RegistryTotal": report.registry["total_functions"],
        "RegistryCertified": status["certified"],
        "RegistryValidated": status["validated"],
        "RegistryCertifiedValidated": status["certified"] + status["validated"],
        "RegistryApiStable": status["api_stable"],
        "RegistryExperimental": status["experimental"],
        "RegistryStableHandwritten": audit["totals"]["stable_handwritten"],
        "RegistryAutoUnbacked": audit["parity_coverage"]["unbacked_auto"],
        "RegistryAutoUnbackedClasslike": breakdown["classlike_symbol_count"],
        "RegistryAutoUnbackedFunctionlike": breakdown["functionlike_symbol_count"],
        "RegistryOtherApiEvidence": (
            status["api_stable"] - audit["parity_coverage"]["unbacked_auto"]
        ),
        "AgentCardCount": report.registry["agent_cards"],
        "AgentDefaultCardCount": report.registry["total_functions"] - report.registry["agent_cards"],
        "AgentCardPct": (
            f"{100 * report.registry['agent_cards'] / report.registry['total_functions']:.1f}\\%"
        ),
        "SchemaWithTypedParameter": schema["with_typed_parameter"],
        "SchemaParameterTotal": schema["parameter_total"],
        "SchemaParameterDescribed": schema["parameter_with_description"],
        "SchemaParameterDefault": schema["parameter_with_default"],
        "SchemaParameterEnum": schema["parameter_with_enum"],
        "SchemaParameterDescribedPct": (
            f"{100 * schema['parameter_with_description'] / schema['parameter_total']:.1f}\\%"
        ),
        "SchemaParameterDefaultPct": (
            f"{100 * schema['parameter_with_default'] / schema['parameter_total']:.1f}\\%"
        ),
        "SchemaParameterEnumPct": (
            f"{100 * schema['parameter_with_enum'] / schema['parameter_total']:.1f}\\%"
        ),
        "ParityCrossLanguage": kinds["cross_language"],
        "ParityInternalEvidence": kinds["internal_evidence"],
        "ParityEstimatorTotal": strata["estimator"]["total"],
        "ParityEstimatorCrossLanguage": strata["estimator"]["cross_language"],
        "ParityEstimatorCrossLanguagePct": (
            f"{100 * strata['estimator']['cross_language_fraction']:.1f}\\%"
        ),
        "ParityInfraTotal": strata["infrastructure"]["total"],
        "ParityClassTotal": strata["classes"]["total"],
        "RParityModuleCount": r_modules,
        "StataParityModuleCount": stata_modules,
        "NoStataModuleCount": r_modules - stata_modules,
        **_orig_parity_claims(),
        **_track_a_verdict_claims(),
    }


def _track_a_verdict_claims() -> dict[str, int]:
    """Headline verdicts of the Track A table (``tests/r_parity/compare.py``).

    The manuscript used to type the pass count by hand, which went stale
    each time a module was added.
    """
    import importlib.util  # noqa: PLC0415

    path = REPO_ROOT / "tests" / "r_parity" / "compare.py"
    spec = importlib.util.spec_from_file_location("statspai_compare_for_claims", path)
    module = importlib.util.module_from_spec(spec)
    # compare.py declares dataclasses, which look their module up here.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    verdicts = [meta["verdict"] for meta in module.HEADLINE.values()]
    passes = sum("PASS" in verdict for verdict in verdicts)
    # What the StatsPAI side of each module executes (native algorithm,
    # official port, third-party Python library, or the reference itself).
    # Verified against a call trace by test_parity_implementation_provenance.
    census = module.implementation_census(sorted(module.TOLERANCES))
    return {
        "RParityPassCount": passes,
        "RParityNonPassCount": len(verdicts) - passes,
        "ParityNativeModuleCount": census["native"],
        "ParityPortModuleCount": census["official_python_port"],
        "ParityThirdPartyModuleCount": census["third_party_python"],
        "ParityBackendModuleCount": census["reference_backend"],
    }


def _orig_parity_claims() -> dict[str, int]:
    """Module and statistic-row counts of the original-data ledger."""
    import json  # noqa: PLC0415

    results = REPO_ROOT / "tests" / "orig_parity" / "results"
    modules = sorted(results.glob("*_py.json"))
    rows = 0
    for path in modules:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows += len(payload.get("rows", []))
    return {
        "OrigParityModuleCount": len(modules),
        "OrigParityRowCount": rows,
    }


def _render() -> str:
    lines = [
        "% AUTO-GENERATED by replication/scripts/generate_manuscript_claims.py",
        "% Do not edit by hand; run the generator or `make manuscript-claims`.",
    ]
    for name, value in _claims().items():
        formatted = f"{value:,}".replace(",", "{,}") if isinstance(value, int) else value
        lines.append(f"\\newcommand{{\\{name}}}{{{formatted}}}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the committed macro file differs from the live package",
    )
    args = parser.parse_args()
    expected = _render()
    if args.check:
        actual = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if actual != expected:
            print(f"FAIL -- generated manuscript claims are stale: {OUTPUT}")
            return 1
        print("OK -- generated manuscript claims match the live package")
        return 0
    OUTPUT.write_text(expected, encoding="utf-8")
    print(f"OK -- wrote {OUTPUT.relative_to(PAPER_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

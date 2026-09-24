"""Audit the reviewer-facing JSS reproduction environment.

This script checks the packaging pieces that make the submitted archive
actually runnable from a clean Python/TeX environment: Dockerfile,
requirements file, Makefile targets, and the tiered reproduction driver.
It does not build Docker; it verifies the static contract that the archive
advertises to reviewers.
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys
import time
from pathlib import Path

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:  # _paths.py sits beside this script; importlib loaders do not add the script dir
    sys.path.insert(0, _SCRIPTS_DIR)

from _paths import PAPER_ROOT as _PAPER_ROOT
from _paths import expected_stata_module_count as _expected_stata
from _paths import expected_r_module_count as _expected_r
from _paths import statspai_root as _statspai_root


HERE = Path(__file__).resolve().parent
PAPER_DIR = _PAPER_ROOT
ROOT = _statspai_root()  # see _paths.py: worktree-safe
RESULTS_DIR = PAPER_DIR / "replication" / "results"
OUT_JSON = RESULTS_DIR / "reproduction_environment_audit.json"
OUT_MD = RESULTS_DIR / "reproduction_environment_audit.md"
SOURCE_DATE_EPOCH = os.environ.get("SOURCE_DATE_EPOCH")


def _generated_at_unix() -> int:
    if SOURCE_DATE_EPOCH is not None:
        return int(SOURCE_DATE_EPOCH)
    return int(time.time())

DOCKERFILE = PAPER_DIR / "replication" / "Dockerfile"
REQUIREMENTS = PAPER_DIR / "requirements-jss.txt"
MAKEFILE = PAPER_DIR / "Makefile"
PAPER_README = PAPER_DIR / "README.md"
MANUSCRIPT_README = PAPER_DIR / "manuscript" / "README.md"
REPRODUCE = PAPER_DIR / "replication" / "reproduce.py"
TIER1_TRANSCRIPT = RESULTS_DIR / "reproduce_tier1_output.txt"
RENV_LOCK = ROOT / "tests" / "r_parity" / "renv.lock"
R_ENVIRONMENT = ROOT / "tests" / "r_parity" / "R_ENVIRONMENT.md"
R_REPRO_REPORT = ROOT / "tests" / "r_parity" / "results" / "REPRODUCIBILITY_REPORT.md"
STATA_ENV = ROOT / "tests" / "stata_parity" / "STATA_ENVIRONMENT.md"
STATA_VERIFY = ROOT / "tests" / "stata_parity" / "verify_reproduce_stata.py"
STATA_REPRO_REPORT = (
    ROOT / "tests" / "stata_parity" / "results" / "REPRODUCIBILITY_REPORT_STATA.md"
)
EXPECTED_R_REPRO_MODULES = _expected_r()
EXPECTED_STATA_REPRO_MODULES = _expected_stata()
RNG_AUDIT_ROOTS = (
    PAPER_DIR / "replication" / "scripts",
    ROOT / "tests" / "perf",
    ROOT / "tests" / "coverage_monte_carlo",
)
PAPER_RNG_AUDIT_SCRIPT_NAMES = {
    "generate_figures.py",
    "generate_inventory.py",
    "gen_appendix_A.py",
    "gen_appendix_C.py",
}
RNG_AUDIT_SUFFIXES = {".py", ".R"}
RNG_USAGE_RE = re.compile(
    r"np\.random|numpy\.random|default_rng|RandomState|random_state|"
    r"set\.seed\(|\bimport random\b|\bfrom random import\b"
)
RNG_SEED_RE = (
    re.compile(r"default_rng\s*\(\s*(?:seed|[0-9])"),
    re.compile(r"RandomState\s*\(\s*(?:seed|[0-9])"),
    re.compile(r"np\.random\.seed\s*\("),
    re.compile(r"random_state\s*=\s*(?:seed|[0-9])"),
    re.compile(r"random_seed\s*=\s*(?:seed|[0-9])"),
    re.compile(r"seed\s*[:=][^\n]*[0-9]"),
    re.compile(r"set\.seed\s*\("),
)
TIER1_LIVE_EXTERNAL_PATTERNS = (
    "Rscript",
    "verify_reproduce.py",
    "verify_reproduce_stata.py",
    "stata-mp",
    "shutil.which(\"stata\")",
    "shutil.which(\"Rscript\")",
)

REQUIRED_PIP_PACKAGES = {
    "setuptools",
    "wheel",
    "numpy",
    "pandas",
    "scipy",
    "statsmodels",
    "linearmodels",
    "numba",
    "scikit-learn",
    "matplotlib",
    "rdrobust",
    "pillow",
    "pyarrow",
    "pytest",
    "pytest-cov",
    "jsonschema",
}

REQUIRED_APT_PACKAGES = {
    "make",
    "pandoc",
    "poppler-utils",
    "latexmk",
    "texlive-latex-base",
    "texlive-latex-recommended",
    "texlive-latex-extra",
    "texlive-fonts-recommended",
    "texlive-bibtex-extra",
}

REQUIRED_MAKE_TARGETS = {
    "reproduce-jss",
    "reproduce-jss-full",
    "reproduce-tier1",
    "reproduce-tier1-transcript",
    "reproduce-tier2",
    "reproduce-tier3",
    "audit",
    "performance-artifacts",
    "submission-package",
    "verify-submission-package",
    "submission-ready",
    "release-boundary-audit",
    "stata-rerun-protocol",
    "agent-interface-audit",
    "agent-benchmark-protocol",
    "manuscript-artifact-audit",
    "data-provenance-audit",
    "bibliography-metadata-audit",
    "pdf-render-audit",
    "pdf-visual-check-protocol",
    "jss-formal-compliance-audit",
    "submission-risk-ledger",
    "reviewer-evidence-map",
    "editor-screening-checklist",
}

PAPER_README_REVIEWER_COMMANDS = (
    "make reproduce-jss PYTHON=../.venv/bin/python",
    "make audit PYTHON=../.venv/bin/python",
    "../.venv/bin/python replication/reproduce.py --tier 1",
    "../.venv/bin/python replication/reproduce.py --tier 1 \\\n  --transcript replication/results/reproduce_tier1_output.txt",
    "../.venv/bin/python replication/reproduce.py --tier 2",
    "../.venv/bin/python replication/reproduce.py --tier 3",
    "STATA_EXE=/path/to/stata-mp ../.venv/bin/python replication/reproduce.py --tier 3",
    "make submission-ready PYTHON=../.venv/bin/python",
    "make submission-risk-ledger PYTHON=../.venv/bin/python",
    "make reviewer-evidence-map PYTHON=../.venv/bin/python",
    "make editor-screening-checklist PYTHON=../.venv/bin/python",
    "make manuscript-artifact-audit PYTHON=../.venv/bin/python",
    "make pdf-render-audit PYTHON=../.venv/bin/python",
    "make pdf-visual-check-protocol PYTHON=../.venv/bin/python",
    "make jss-formal-compliance-audit PYTHON=../.venv/bin/python",
    "make gap-ledger PYTHON=../.venv/bin/python",
    "make stata-bridge-audit PYTHON=../.venv/bin/python",
    "make stata-rerun-protocol PYTHON=../.venv/bin/python",
    "make agent-interface-audit PYTHON=../.venv/bin/python",
    "make agent-benchmark-protocol PYTHON=../.venv/bin/python",
    "make data-provenance-audit PYTHON=../.venv/bin/python",
    "make bibliography-metadata-audit PYTHON=../.venv/bin/python",
    "make release-audit PYTHON=../.venv/bin/python",
    "make release-boundary-audit PYTHON=../.venv/bin/python",
    "make reproduction-environment-audit PYTHON=../.venv/bin/python",
    "make jss-style PYTHON=../.venv/bin/python",
)

PAPER_README_STATA_CONTRACT_SNIPPETS = (
    "that skip is not evidence of a live Stata rerun",
    "committed Stata JSON/do/provenance bundle",
)

MANUSCRIPT_README_STATA_CONTRACT_SNIPPETS = (
    "STATA_EXE=/path/to/stata-mp",
    "not as live rerun evidence",
)

MANUSCRIPT_README_REVIEWER_COMMANDS = (
    "make reproduce-jss",
    "make reproduce-jss-full PYTHON=../.venv/bin/python",
    "make release-audit PYTHON=../.venv/bin/python",
    "make submission-ready PYTHON=../.venv/bin/python",
    "docker build -f Paper-JSS/replication/Dockerfile -t statspai-jss .",
    "docker run --rm statspai-jss",
    "cd Paper-JSS && make submission-ready PYTHON=../.venv/bin/python",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _require_file(path: Path, failures: list[str]) -> str:
    if not path.exists():
        failures.append(f"missing reproduction file: {path.relative_to(ROOT)}")
        return ""
    return _read(path)


def _normalise_package(line: str) -> str:
    return re.split(r"[<>=!~\[]", line.strip(), maxsplit=1)[0].strip().lower()


def _make_targets(text: str) -> set[str]:
    targets: set[str] = set()
    for line in text.splitlines():
        if not line or line.startswith(("\t", " ", "#", ".")):
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)\s*:", line)
        if match:
            targets.add(match.group(1))
    return targets


def _function_source(text: str, name: str) -> str:
    """Return the source segment for a top-level function, or an empty string."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return ""
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(text, node) or ""
    return ""


def _check_dockerfile(text: str, failures: list[str]) -> dict[str, object]:
    apt_missing = sorted(pkg for pkg in REQUIRED_APT_PACKAGES if pkg not in text)
    for pkg in apt_missing:
        failures.append(f"Dockerfile missing apt package: {pkg}")
    required_snippets = [
        "FROM python:3.12-slim",
        "COPY pyproject.toml README.md README_CN.md CHANGELOG.md LICENSE ./",
        "COPY src ./src",
        "COPY scripts ./scripts",
        "COPY tests ./tests",
        "COPY docs ./docs",
        "COPY Paper-JSS ./Paper-JSS",
        "python -m pip install --upgrade pip setuptools wheel",
        "python -m pip install .",
        "python -m pip install -r Paper-JSS/requirements-jss.txt",
        'CMD ["make", "reproduce-jss-full"]',
    ]
    for snippet in required_snippets:
        if snippet not in text:
            failures.append(f"Dockerfile missing snippet: {snippet!r}")
    return {
        "base_image": "python:3.12-slim" if "FROM python:3.12-slim" in text else "unknown",
        "required_apt_missing": apt_missing,
    }


def _check_requirements(text: str, failures: list[str]) -> dict[str, object]:
    packages = {
        _normalise_package(line)
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    version_comment_ok = "local StatsPAI 1.20.0 tree" in text
    if not version_comment_ok or "local StatsPAI 1.16.1 tree" in text:
        failures.append("requirements-jss.txt has stale StatsPAI version comment")
    missing = sorted(REQUIRED_PIP_PACKAGES - packages)
    for pkg in missing:
        failures.append(f"requirements-jss.txt missing package: {pkg}")
    if "rdrobust" not in packages:
        failures.append("requirements-jss.txt does not install rdrobust for CCT RD path")
    if "pytest" not in packages or "pytest-cov" not in packages:
        failures.append("requirements-jss.txt does not install pytest/pytest-cov for audit tests")
    return {
        "package_count": len(packages),
        "required_pip_missing": missing,
        "packages": sorted(packages),
        "version_comment_ok": version_comment_ok,
    }


def _check_makefile(text: str, failures: list[str]) -> dict[str, object]:
    targets = _make_targets(text)
    missing = sorted(REQUIRED_MAKE_TARGETS - targets)
    for target in missing:
        failures.append(f"Makefile missing target: {target}")
    if "submission-ready: reproduce-jss-full" not in text:
        failures.append(
            "Makefile submission-ready target must run reproduce-jss-full "
            "so the Tier-1 transcript is refreshed before packaging"
        )
    fixed_point_snippets = (
        "replication/scripts/jss_submission_package.py\n\t$(PYTHON) replication/scripts/jss_full_audit.py",
        "replication/scripts/jss_full_audit.py\n\t$(PYTHON) replication/scripts/submission_risk_ledger.py",
        "replication/scripts/submission_risk_ledger.py\n\t$(PYTHON) replication/scripts/reviewer_evidence_map.py",
        "replication/scripts/reviewer_evidence_map.py\n\t$(PYTHON) replication/scripts/editor_screening_checklist.py",
        "replication/scripts/editor_screening_checklist.py\n\t$(PYTHON) replication/scripts/jss_submission_package.py",
        "replication/scripts/verify_submission_package.py",
    )
    for snippet in fixed_point_snippets:
        if snippet not in text:
            failures.append(
                "Makefile submission-ready target must package, audit, "
                "write the submission-risk ledger, reviewer evidence map, "
                "and editor screening checklist, re-package, then verify"
            )
            break
    pandoc_optional = (
        "SKIP -- $(PANDOC) not found" in text
        and "main.md is an excluded convenience export" in text
    )
    if not pandoc_optional:
        failures.append(
            "Makefile markdown target must skip missing pandoc because "
            "main.md is excluded from the JSS submission archive"
        )
    return {
        "target_count": len(targets),
        "required_targets_missing": missing,
        "pandoc_markdown_optional": pandoc_optional,
    }


def _check_reviewer_readmes(failures: list[str]) -> dict[str, object]:
    paper_readme = _require_file(PAPER_README, failures)
    manuscript_readme = _require_file(MANUSCRIPT_README, failures)
    paper_missing = [
        command for command in PAPER_README_REVIEWER_COMMANDS
        if paper_readme and command not in paper_readme
    ]
    manuscript_missing = [
        command for command in MANUSCRIPT_README_REVIEWER_COMMANDS
        if manuscript_readme and command not in manuscript_readme
    ]
    for command in paper_missing:
        failures.append(f"Paper-JSS README missing reviewer command: {command}")
    for command in manuscript_missing:
        failures.append(
            "manuscript README missing reviewer command: " + command
        )
    paper_stata_missing = [
        snippet for snippet in PAPER_README_STATA_CONTRACT_SNIPPETS
        if paper_readme and snippet not in paper_readme
    ]
    manuscript_stata_missing = [
        snippet for snippet in MANUSCRIPT_README_STATA_CONTRACT_SNIPPETS
        if manuscript_readme and snippet not in manuscript_readme
    ]
    for snippet in paper_stata_missing:
        failures.append(f"Paper-JSS README missing Stata rerun contract: {snippet}")
    for snippet in manuscript_stata_missing:
        failures.append(f"manuscript README missing Stata rerun contract: {snippet}")
    return {
        "paper_readme_command_count": len(PAPER_README_REVIEWER_COMMANDS),
        "paper_readme_missing_commands": paper_missing,
        "manuscript_readme_command_count": len(MANUSCRIPT_README_REVIEWER_COMMANDS),
        "manuscript_readme_missing_commands": manuscript_missing,
        "paper_readme_stata_contract_missing": paper_stata_missing,
        "manuscript_readme_stata_contract_missing": manuscript_stata_missing,
        "stata_live_rerun_command_documented": (
            not paper_stata_missing and "STATA_EXE=/path/to/stata-mp" in paper_readme
        ),
        "stata_missing_runtime_skip_documented": (
            not paper_stata_missing and not manuscript_stata_missing
        ),
    }


def _check_reproduce(text: str, failures: list[str]) -> dict[str, object]:
    required = [
        "Tier 1  (no R, no Stata)",
        "Tier 2  (needs R)",
        "Tier 3  (needs a Stata license)",
        "STATA_EXE=/path/to/stata-mp",
        "methodological gap ledger",
        "frozen Stata bridge audit",
        "agent interface audit",
        "release boundary audit",
        "manuscript-artifact audit",
        "optional external-runtime checks skipped",
        "--transcript",
    ]
    for snippet in required:
        if snippet not in text:
            failures.append(f"reproduce.py missing tier contract text: {snippet!r}")
    if "shutil.which(\"Rscript\")" not in text:
        failures.append("reproduce.py does not gate Tier 2 on Rscript")
    if "shutil.which(candidate)" not in text or "stata-mp" not in text or "stata" not in text:
        failures.append("reproduce.py does not gate Tier 3 on Stata availability")
    if "_stata_executable_for_tier3" not in text or 'env["STATA_EXE"] = stata_exe' not in text:
        failures.append("reproduce.py does not pass the resolved Stata executable through STATA_EXE")
    tier1_source = _function_source(text, "tier1")
    if not tier1_source:
        failures.append("reproduce.py tier1() source could not be inspected")
    tier1_live_external_hits = [
        pattern for pattern in TIER1_LIVE_EXTERNAL_PATTERNS
        if pattern in tier1_source
    ]
    for pattern in tier1_live_external_hits:
        failures.append(
            "Tier-1 reproduction path contains live R/Stata dependency marker: "
            + pattern
        )
    return {
        "has_tier1": "Tier 1  (no R, no Stata)" in text,
        "has_tier2": "Tier 2  (needs R)" in text,
        "has_tier3": "Tier 3  (needs a Stata license)" in text,
        "has_transcript_option": "--transcript" in text,
        "tier3_accepts_stata_exe": "STATA_EXE=/path/to/stata-mp" in text,
        "tier3_passes_stata_exe_to_verifier": 'env["STATA_EXE"] = stata_exe' in text,
        "tier1_live_external_dependency_markers": tier1_live_external_hits,
        "tier1_live_external_call_count": len(tier1_live_external_hits),
    }


def _check_tier1_transcript(failures: list[str]) -> dict[str, bool]:
    present = TIER1_TRANSCRIPT.exists()
    complete = False
    if not present:
        failures.append(
            "missing reviewer transcript: "
            f"{TIER1_TRANSCRIPT.relative_to(ROOT)}"
        )
        return {"tier1_transcript_present": False, "tier1_transcript_complete": False}

    text = _read(TIER1_TRANSCRIPT)
    if "StatsPAI JSS replication -- Tier 1" not in text:
        failures.append("Tier-1 transcript lacks the replication header")
    complete = "RESULT: OK -- all required steps reproduced." in text
    no_r_stata = "Every Section 4-7 headline number was rebuilt without R or Stata" in text
    if "SUMMARY" in text and not no_r_stata:
        failures.append(
            "Tier-1 transcript does not state the no-R/no-Stata headline path"
        )
    # During `reproduce.py --transcript`, this audit runs before the script's
    # final summary is printed. The submission package verifier checks the
    # final transcript strictly after generation.
    if "SUMMARY" in text and not complete:
        failures.append("Tier-1 transcript has a summary but no RESULT: OK marker")
    return {
        "tier1_transcript_present": True,
        "tier1_transcript_complete": complete,
        "tier1_transcript_no_r_stata": no_r_stata,
    }


def _repro_report_counts(report: str) -> dict[str, int]:
    rows = [
        line for line in report.splitlines()
        if line.startswith("| `") and line.count("|") >= 7
    ]
    reproduced = [line for line in rows if "reproduces" in line]
    return {
        "rows": len(rows),
        "reproduced": len(reproduced),
        "non_reproduced": len(rows) - len(reproduced),
    }


def _check_external_environment_files(failures: list[str]) -> dict[str, object]:
    paths = {
        "renv_lock_present": RENV_LOCK,
        "r_environment_present": R_ENVIRONMENT,
        "r_repro_report_present": R_REPRO_REPORT,
        "stata_environment_present": STATA_ENV,
        "stata_repro_report_present": STATA_REPRO_REPORT,
    }
    present: dict[str, object] = {}
    for key, path in paths.items():
        exists = path.exists()
        present[key] = exists
        if not exists:
            failures.append(f"missing external reproducibility file: {path.relative_to(ROOT)}")

    if R_ENVIRONMENT.exists():
        text = _read(R_ENVIRONMENT)
        for snippet in ("R 4.5.2", "renv.lock", "verify_reproduce.py"):
            if snippet not in text:
                failures.append(f"R_ENVIRONMENT.md missing {snippet!r}")
    if R_REPRO_REPORT.exists():
        text = _read(R_REPRO_REPORT)
        if "Generated by `tests/r_parity/verify_reproduce.py`" not in text:
            failures.append("R reproducibility report lacks generator provenance")
        counts = _repro_report_counts(text)
        present["r_reproduced_modules"] = counts["reproduced"]
        present["r_repro_report_rows"] = counts["rows"]
        present["r_repro_report_non_reproduced_rows"] = counts["non_reproduced"]
        present["r_expected_reproduced_modules"] = EXPECTED_R_REPRO_MODULES
        if counts["reproduced"] != EXPECTED_R_REPRO_MODULES:
            failures.append(
                "R reproducibility report reproduced "
                f"{counts['reproduced']} modules, expected {EXPECTED_R_REPRO_MODULES}"
            )
        if counts["non_reproduced"] != 0:
            failures.append(
                "R reproducibility report contains non-reproduced rows: "
                f"{counts['non_reproduced']}"
            )
    if STATA_ENV.exists():
        text = _read(STATA_ENV)
        for snippet in ("Stata 18", "Edition | MP", "verify_reproduce_stata.py"):
            if snippet not in text:
                failures.append(f"STATA_ENVIRONMENT.md missing {snippet!r}")
    if STATA_REPRO_REPORT.exists():
        text = _read(STATA_REPRO_REPORT)
        if "Generated by `tests/stata_parity/verify_reproduce_stata.py`" not in text:
            failures.append("Stata reproducibility report lacks generator provenance")
        counts = _repro_report_counts(text)
        present["stata_reproduced_modules"] = counts["reproduced"]
        present["stata_repro_report_rows"] = counts["rows"]
        present["stata_repro_report_non_reproduced_rows"] = counts["non_reproduced"]
        present["stata_expected_reproduced_modules"] = EXPECTED_STATA_REPRO_MODULES
        if counts["reproduced"] != EXPECTED_STATA_REPRO_MODULES:
            failures.append(
                "Stata reproducibility report reproduced "
                f"{counts['reproduced']} modules, expected {EXPECTED_STATA_REPRO_MODULES}"
            )
        if counts["non_reproduced"] != 0:
            failures.append(
                "Stata reproducibility report contains non-reproduced rows: "
                f"{counts['non_reproduced']}"
            )
    return present


def _check_stata_live_rerun_contract(failures: list[str]) -> dict[str, object]:
    if not STATA_VERIFY.exists():
        failures.append(
            "missing Stata live-rerun verifier: "
            f"{STATA_VERIFY.relative_to(ROOT)}"
        )
        return {
            "stata_verify_script_present": False,
            "stata_verify_uses_stata_exe": False,
            "stata_verify_missing_runtime_returns_skip": False,
        }
    text = _read(STATA_VERIFY)
    uses_stata_exe = 'os.environ.get("STATA_EXE"' in text
    missing_runtime_returns_skip = (
        "Stata executable not found (set STATA_EXE=...). Skipping." in text
        and "return 0  # absence of Stata is a skip, not a failure" in text
    )
    if not uses_stata_exe:
        failures.append("Stata verifier does not read STATA_EXE")
    if not missing_runtime_returns_skip:
        failures.append(
            "Stata verifier missing-runtime skip contract is not explicit"
        )
    return {
        "stata_verify_script_present": True,
        "stata_verify_uses_stata_exe": uses_stata_exe,
        "stata_verify_missing_runtime_returns_skip": missing_runtime_returns_skip,
    }


def _iter_rng_audit_files() -> list[Path]:
    files: list[Path] = []
    for root in RNG_AUDIT_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in RNG_AUDIT_SUFFIXES:
                continue
            if root == PAPER_DIR / "replication" / "scripts":
                if not (
                    path.name.startswith("ex")
                    or path.name in PAPER_RNG_AUDIT_SCRIPT_NAMES
                ):
                    continue
            files.append(path)
    return sorted(files)


def _check_random_seeding(failures: list[str]) -> dict[str, object]:
    """Ensure stochastic paper-reproduction code declares deterministic seeds."""
    stochastic: list[str] = []
    unseeded: list[str] = []
    for path in _iter_rng_audit_files():
        text = path.read_text(encoding="utf-8")
        if not RNG_USAGE_RE.search(text):
            continue
        rel = str(path.relative_to(ROOT))
        stochastic.append(rel)
        if not any(pattern.search(text) for pattern in RNG_SEED_RE):
            unseeded.append(rel)
    for rel in unseeded:
        failures.append(f"stochastic reproduction file lacks explicit seed: {rel}")
    return {
        "checked_file_count": len(_iter_rng_audit_files()),
        "seeded_stochastic_file_count": len(stochastic) - len(unseeded),
        "stochastic_file_count": len(stochastic),
        "unseeded_stochastic_file_count": len(unseeded),
        "unseeded_stochastic_files": unseeded,
        "stochastic_files": stochastic,
    }


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []

    docker_text = _require_file(DOCKERFILE, failures)
    req_text = _require_file(REQUIREMENTS, failures)
    make_text = _require_file(MAKEFILE, failures)
    reproduce_text = _require_file(REPRODUCE, failures)

    external_files = _check_external_environment_files(failures)
    stata_contract = _check_stata_live_rerun_contract(failures)
    transcript = _check_tier1_transcript(failures)
    rng = _check_random_seeding(failures)

    docker = _check_dockerfile(docker_text, failures) if docker_text else {}
    requirements = _check_requirements(req_text, failures) if req_text else {}
    makefile = _check_makefile(make_text, failures) if make_text else {}
    reproduce = _check_reproduce(reproduce_text, failures) if reproduce_text else {}
    reviewer_readmes = _check_reviewer_readmes(failures)

    status = "PASS" if not failures else "FAIL"
    result = {
        "generated_at_unix": _generated_at_unix(),
        "status": status,
        "dockerfile": docker,
        "requirements": requirements,
        "makefile": makefile,
        "reviewer_readmes": reviewer_readmes,
        "reproduce": reproduce,
        "stata_live_rerun_contract": stata_contract,
        "random_seeding": rng,
        **transcript,
        **external_files,
        "failures": failures,
    }
    OUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Reproduction Environment Audit",
        "",
        f"Status: {status}",
        "",
        "Scope: static checks for the Dockerfile, Python requirements, Makefile",
        "targets, tiered reproduction driver, reviewer transcript, R lockfile,",
        "Stata environment note, and deterministic random seeds in stochastic",
        "paper-reproduction scripts.",
        "",
        f"Docker base image: {docker.get('base_image', 'n/a')}",
        f"Python requirement packages: {requirements.get('package_count', 'n/a')}",
        (
            "Requirements source version comment: "
            f"{requirements.get('version_comment_ok')}"
        ),
        f"Makefile targets: {makefile.get('target_count', 'n/a')}",
        (
            "Reviewer README commands checked: "
            f"{reviewer_readmes.get('paper_readme_command_count', 'n/a')}"
        ),
        (
            "Manuscript README commands checked: "
            f"{reviewer_readmes.get('manuscript_readme_command_count', 'n/a')}"
        ),
        (
            "Optional Pandoc Markdown export: "
            f"{makefile.get('pandoc_markdown_optional')}"
        ),
        f"Tier-1 reviewer transcript present: {transcript.get('tier1_transcript_present')}",
        f"Tier-1 reviewer transcript complete: {transcript.get('tier1_transcript_complete')}",
        f"Tier-1 transcript states no R/Stata headline path: {transcript.get('tier1_transcript_no_r_stata')}",
        (
            "Tier-1 live R/Stata dependency markers: "
            f"{reproduce.get('tier1_live_external_call_count', 'n/a')}"
        ),
        (
            "Stata live-rerun command documented: "
            f"{reviewer_readmes.get('stata_live_rerun_command_documented')}"
        ),
        (
            "Stata missing-runtime skip documented: "
            f"{reviewer_readmes.get('stata_missing_runtime_skip_documented')}"
        ),
        (
            "Stata verifier missing-runtime returns skip: "
            f"{stata_contract.get('stata_verify_missing_runtime_returns_skip')}"
        ),
        f"R lockfile present: {external_files.get('renv_lock_present')}",
        f"R environment note present: {external_files.get('r_environment_present')}",
        f"R reproducibility report present: {external_files.get('r_repro_report_present')}",
        (
            "R reproduced modules: "
            f"{external_files.get('r_reproduced_modules', 'n/a')}/"
            f"{external_files.get('r_expected_reproduced_modules', 'n/a')}"
        ),
        (
            "R non-reproduced rows: "
            f"{external_files.get('r_repro_report_non_reproduced_rows', 'n/a')}"
        ),
        f"Stata environment note present: {external_files.get('stata_environment_present')}",
        (
            "Stata reproducibility report present: "
            f"{external_files.get('stata_repro_report_present')}"
        ),
        (
            "Stata reproduced modules: "
            f"{external_files.get('stata_reproduced_modules', 'n/a')}/"
            f"{external_files.get('stata_expected_reproduced_modules', 'n/a')}"
        ),
        (
            "Stata non-reproduced rows: "
            f"{external_files.get('stata_repro_report_non_reproduced_rows', 'n/a')}"
        ),
        f"Stochastic reproduction files checked: {rng['stochastic_file_count']}",
        f"Seeded stochastic reproduction files: {rng['seeded_stochastic_file_count']}",
        f"Unseeded stochastic reproduction files: {rng['unseeded_stochastic_file_count']}",
        "",
    ]
    if failures:
        lines.append("Failures:")
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.append("Failures: none")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"OK -- wrote {OUT_JSON}")
    print(f"OK -- wrote {OUT_MD}")
    if failures:
        print("FAIL -- reproduction environment audit failed", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

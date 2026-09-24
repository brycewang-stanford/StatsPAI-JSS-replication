#!/usr/bin/env python3
"""Standalone three-tier replication driver for the StatsPAI JSS paper.

JSS asks that all results be reproducible and that a reviewer be able to
*verify* reproducibility -- ideally within ~1 hour on a standard PC.
This single script makes the dependency boundary explicit so a reviewer
knows exactly what each headline number costs to reproduce:

  Tier 1  (no R, no Stata)  -- DEFAULT.  Rebuilds every headline table
            and figure of Sections 4-7 from pure Python. What it
            *recomputes*: the worked examples, every manuscript listing and
            transcript, the known-truth recovery tests, the seed-replicated
            forest analysis, and the configuration map. What it only
            *re-derives from frozen artifacts*: the Track-A parity table
            (from the committed *_py / *_R / *_Stata JSON), the Track-B
            coverage tables (from results_b1000/*.json) and the Track-C
            timing table (from tests/perf/results). Those experiments are
            recomputed by --recompute below, not by Tier 1. Tier 1 runs the
            six worked examples, the
            deterministic agent trace, the figures, the Track-A parity
            rollup, the Track-C performance table/figure, the supplemental
            tables, the registry inventory, the methodological-gap ledger,
            the frozen Stata bridge audit, the agent-interface audit, the
            release-boundary audit, the reproduction-environment audit, the
            manuscript-artifact audit, and the causal-forest AIPW /
            synthetic-control recovery validations. The submitted
            transcript records 22/22 steps, and the formal compliance
            gate requires this short reviewer path to remain below the
            JSS one-hour threshold rather than pinning a machine-specific
            minute count in prose.

  Tier 2  (needs R)         -- Additionally re-runs the cross-language
            R-parity harness (fixest/did/Synth/grf/DoubleML/MatchIt/...)
            on the committed CSV bytes and diffs every statistic against
            the committed golden *_R.json.  ~30-60 min.

  Tier 3  (needs a Stata license) -- Additionally re-runs the Stata
            bridge .do files.  Supplementary migration evidence only; no
            Tier-1 headline number depends on it.

Usage
-----
    python reproduce.py                # Tier 1 (default)
    python reproduce.py --transcript replication/results/reproduce_tier1_output.txt
    python reproduce.py --tier 2       # Tier 1 + R parity
    python reproduce.py --tier 3       # Tier 1 + R + Stata
    STATA_EXE=/path/to/stata-mp python reproduce.py --tier 3
    python reproduce.py --list         # show what each tier runs

Full recomputation of the frozen experiments (hours; see --list):

    python reproduce.py --recompute parity-py    # Python side of every Track A
                                                 # module + fixture bytes (~15 min)
    python reproduce.py --recompute montecarlo   # Track B at B=1,000 (~75 min)
    python reproduce.py --recompute forest-seed  # seed-replicated forest, Python
                                                 # side (~30 min; R side needs R)
    python reproduce.py --recompute performance  # Track C timings (hardware-
                                                 # dependent; R legs need R)

Each group writes to the same artifact paths the paper reads, so a
recompute followed by Tier 1 regenerates the tables from fresh numbers;
`git diff` then shows what moved.

Exit code is non-zero if any step in the requested tier fails, so the
script doubles as a CI smoke test.
"""
from __future__ import annotations

import argparse
import contextlib
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent          # Paper-JSS/replication
PAPER = HERE.parent                              # Paper-JSS
REPO = PAPER.parent                              # repo root
SCRIPTS = HERE / "scripts"


class _Tee:
    """Write stdout to both the console and a reviewer transcript."""

    def __init__(self, *streams):
        self._streams = streams

    def write(self, data: str) -> int:
        for stream in self._streams:
            stream.write(data)
            stream.flush()
        return len(data)

    def flush(self) -> None:
        for stream in self._streams:
            stream.flush()


def _run(
    label: str,
    argv: list[str],
    *,
    cwd: Path = REPO,
    env: dict[str, str] | None = None,
) -> tuple[str, float, bool]:
    """Run a subprocess, stream nothing, capture pass/fail + wall time."""
    print(f"  -> {label} ...", flush=True)
    t0 = time.time()
    proc = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True, env=env)
    dt = time.time() - t0
    ok = proc.returncode == 0
    if not ok:
        print(f"     FAILED ({dt:.1f}s). Last stderr lines:", flush=True)
        for line in proc.stderr.strip().splitlines()[-12:]:
            print(f"       {line}", flush=True)
    else:
        print(f"     ok ({dt:.1f}s)", flush=True)
    return label, dt, ok


def tier1() -> list[tuple[str, float, bool]]:
    """No R, no Stata. Rebuilds every headline number."""
    py = sys.executable
    results: list[tuple[str, float, bool]] = []

    print("\n[Tier 1] worked examples (Sections 4, 7) -- replicas + fixtures")
    for ex in sorted(SCRIPTS.glob("ex0*.py")):
        results.append(_run(ex.name, [py, str(ex)], cwd=SCRIPTS))

    print("\n[Tier 1] figures, supplemental tables, registry inventory")
    for script in ["generate_figures.py", "gen_appendix_A.py",
                   "gen_appendix_C.py", "generate_inventory.py"]:
        p = SCRIPTS / script
        if p.exists():
            results.append(_run(script, [py, str(p)], cwd=SCRIPTS))
    results.append(_run(
        "Track-A parity rollup",
        [py, "tests/r_parity/compare.py"],
        cwd=REPO,
    ))
    results.append(_run(
        "Track-C performance artifacts",
        [py, "tests/perf/compare_perf.py"],
        cwd=REPO,
    ))

    print("\n[Tier 1] validation against TRUTH (no external language needed)")
    # The causal-forest AIPW recovery and the synthetic-control recovery
    # certificates are the Tier-1 evidence behind the module-13 and
    # module-52 parity rows; they need no R.
    results.append(_run(
        "causal-forest AIPW recovery",
        [py, "-m", "pytest",
         "tests/reference_parity/test_causal_forest_aipw_recovery.py",
         "tests/reference_parity/test_scm_recovery.py",
         "tests/reference_parity/test_grf_parity.py",
         "-q", "--no-cov", "-p", "no:cacheprovider"],
        cwd=REPO,
    ))
    # Evidence added in response to the 2026-09 review: seed-replicated
    # forest equivalence (reads frozen seed draws), implementation
    # provenance (reads the committed call trace), entropy-balancing and
    # 2SLS SEs against WeightIt / AER fixtures, the audit's applicability
    # rules, and the configuration-level evidence map.
    results.append(_run(
        "evidence-design checks (review response)",
        [py, "-m", "pytest",
         "tests/reference_parity/test_grf_seed_mc_equivalence.py",
         "tests/test_parity_implementation_provenance.py",
         "tests/reference_parity/test_ebalance_weightit_parity.py",
         "tests/reference_parity/test_iv_card_aer_parity.py",
         "tests/test_audit_applicability.py",
         "tests/test_validation_scope.py",
         "-q", "--no-cov", "-p", "no:cacheprovider"],
        cwd=REPO,
    ))
    results.append(_run(
        "JSS headline-count guard",
        [py, "-m", "pytest", "tests/test_jss_validation_api.py",
         "-q", "--no-cov", "-p", "no:cacheprovider"],
        cwd=REPO,
    ))
    results.append(_run(
        "methodological gap ledger",
        [py, str(SCRIPTS / "methodological_gap_ledger.py")],
        cwd=REPO,
    ))
    results.append(_run(
        "frozen Stata bridge audit",
        [py, str(SCRIPTS / "stata_bridge_audit.py")],
        cwd=REPO,
    ))
    results.append(_run(
        "agent interface audit",
        [py, str(SCRIPTS / "agent_interface_audit.py")],
        cwd=REPO,
    ))
    results.append(_run(
        "release boundary audit",
        [py, str(SCRIPTS / "release_boundary_audit.py")],
        cwd=REPO,
    ))
    results.append(_run(
        "reproduction environment audit",
        [py, str(SCRIPTS / "reproduction_environment_audit.py")],
        cwd=REPO,
    ))
    results.append(_run(
        "manuscript artifact audit",
        [py, str(SCRIPTS / "manuscript_artifact_audit.py")],
        cwd=REPO,
    ))
    results.append(_run(
        "manuscript listings execute",
        [py, str(SCRIPTS / "listings_execute_audit.py")],
        cwd=REPO,
    ))

    print("\n[Tier 1] citation verifier")
    results.append(_run(
        "verify_citations.py",
        [py, str(SCRIPTS / "verify_citations.py")], cwd=HERE,
    ))
    return results


def tier2() -> list[tuple[str, float, bool]]:
    """Needs R. Re-verify the cross-language R-parity golden values."""
    results: list[tuple[str, float, bool]] = []
    if shutil.which("Rscript") is None:
        print("\n[Tier 2] SKIPPED -- Rscript not found on PATH. Install R and the")
        print("         reference packages (see tests/r_parity/R_ENVIRONMENT.md).")
        results.append(("R-parity (Rscript missing)", 0.0, False))
        return results
    print("\n[Tier 2] re-verify committed R golden values on identical bytes")
    verify = REPO / "tests" / "r_parity" / "verify_reproduce.py"
    if verify.exists():
        results.append(_run("verify_reproduce.py (R)",
                            [sys.executable, str(verify)], cwd=REPO))
    else:
        print("         verify_reproduce.py not found; run tests/r_parity/*.R manually.")
    # Section 4.1 forest reference: R grf on the bundled Card bytes; rerun
    # ex01_card.py afterwards so its JSON picks up the refreshed gap.
    results.append(_run("ex01_card_grf.R (grf reference)",
                        ["Rscript", str(SCRIPTS / "ex01_card_grf.R")], cwd=REPO))
    results.append(_run("ex01_card.py (with grf gap)",
                        [sys.executable, str(SCRIPTS / "ex01_card.py")],
                        cwd=SCRIPTS))
    return results


def recompute(group: str) -> list[tuple[str, float, bool]]:
    """Re-run a frozen experiment instead of re-reading its artifact."""
    py = sys.executable
    fixtures = REPO / "tests" / "reference_parity" / "_fixtures"
    mc = REPO / "tests" / "coverage_monte_carlo"
    groups: dict[str, list[tuple[str, list[str], Path]]] = {
        "parity-py": [
            ("Track A Python side + fixture bytes",
             [py, "tests/r_parity/verify_reproduce_py.py"], REPO),
        ],
        "montecarlo": [
            ("Track B coverage, B=1000", [py, str(mc / "run_b1000.py")], REPO),
            ("Track B robustness, B=1000", [py, str(mc / "run_robustness_b1000.py")], REPO),
            ("Track B size/power", [py, str(mc / "run_size_power_b1000.py")], REPO),
        ],
        "forest-seed": [
            ("forest seed MC (reference fixture)",
             [py, "_generate_grf_seed_mc_py.py", "grf"], fixtures),
            ("forest seed MC (module-13 design)",
             [py, "_generate_grf_seed_mc_py.py", "m13"], fixtures),
        ],
        "performance": [
            (f"Track C {p.stem}", [py, str(p)], REPO)
            for p in sorted((REPO / "tests" / "perf").glob("0[1-4]_*_perf.py"))
        ] + [("Track C rollup", [py, "tests/perf/compare_perf.py"], REPO)],
    }
    if group not in groups:
        raise SystemExit(f"unknown --recompute group {group!r}; one of {sorted(groups)}")
    print(f"\n[recompute:{group}]")
    results = [_run(label, argv, cwd=cwd) for label, argv, cwd in groups[group]]
    if group == "forest-seed" and shutil.which("Rscript"):
        for arg in ("grf", "m13"):
            results.append(_run(f"forest seed MC, R side ({arg})",
                                ["Rscript", "_generate_grf_seed_mc_R.R", arg], cwd=fixtures))
    return results


def _stata_executable_for_tier3() -> str | None:
    """Return the Stata executable that the downstream verifier should use."""
    configured = os.environ.get("STATA_EXE")
    if configured:
        return configured if Path(configured).exists() else None
    for candidate in ("stata-mp", "stata"):
        found = shutil.which(candidate)
        if found:
            return found
    mac_default = Path("/Applications/Stata/StataMP.app/Contents/MacOS/stata-mp")
    return str(mac_default) if mac_default.exists() else None


def tier3() -> list[tuple[str, float, bool]]:
    """Needs a Stata license. Supplementary migration evidence only."""
    results: list[tuple[str, float, bool]] = []
    stata_exe = _stata_executable_for_tier3()
    if stata_exe is None:
        print("\n[Tier 3] SKIPPED -- no Stata executable found. The Stata bridge is")
        print("         supplementary migration evidence; no Tier-1 headline number")
        print("         depends on it. Set STATA_EXE=/path/to/stata-mp for a live rerun;")
        print("         frozen *_Stata.json + provenance remain auditable.")
        results.append(("Stata bridge (Stata missing)", 0.0, False))
        return results
    verify = REPO / "tests" / "stata_parity" / "verify_reproduce_stata.py"
    if verify.exists():
        env = dict(os.environ)
        env["STATA_EXE"] = stata_exe
        results.append(_run("verify_reproduce_stata.py",
                            [sys.executable, str(verify)], cwd=REPO, env=env))
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tier", type=int, default=1, choices=[1, 2, 3],
                    help="1=no R/Stata (default); 2=+R parity; 3=+Stata bridge")
    ap.add_argument("--list", action="store_true",
                    help="describe what each tier runs and exit")
    ap.add_argument("--transcript", type=Path,
                    help="write the complete reviewer-facing run output to this file")
    ap.add_argument("--recompute", action="append", default=[],
                    choices=["parity-py", "montecarlo", "forest-seed", "performance"],
                    help="re-run a frozen experiment (repeatable); see --list")
    args = ap.parse_args()

    if args.list:
        print(__doc__)
        return 0

    if args.recompute:
        results = []
        for group in args.recompute:
            results += recompute(group)
        failed = [lbl for lbl, _, ok in results if not ok]
        for lbl, dt, ok in results:
            print(f"  [{'PASS' if ok else 'FAIL'}] {lbl:48s} {dt:7.1f}s")
        return 1 if failed else 0

    if args.transcript is not None:
        path = args.transcript if args.transcript.is_absolute() else PAPER / args.transcript
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            with contextlib.redirect_stdout(_Tee(sys.stdout, fh)):
                print(f"Transcript: {path}")
                return _run_tier(args.tier)
    return _run_tier(args.tier)


def _run_tier(tier: int) -> int:
    print("=" * 70)
    print(f"StatsPAI JSS replication -- Tier {tier}")
    print("=" * 70)

    results = tier1()
    if tier >= 2:
        results += tier2()
    if tier >= 3:
        results += tier3()

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    total = 0.0
    n_ok = 0
    for label, dt, ok in results:
        total += dt
        n_ok += int(ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] {label:48s} {dt:7.1f}s")
    print("-" * 70)
    print(f"  {n_ok}/{len(results)} steps passed in {total/60:.1f} min")
    # Tier-1 failures are real; Tier-2/3 skips (missing R/Stata) are tolerated.
    tier1_steps = tier1.__doc__  # noqa: F841 (doc marker)
    hard_fail = any(
        not ok and not lbl.endswith(("missing)", "licence)"))
        for lbl, _, ok in results
    )
    if hard_fail:
        print("  RESULT: FAILED -- see the failing step(s) above.")
        return 1
    optional_skip = any(
        not ok and lbl.endswith(("missing)", "licence)"))
        for lbl, _, ok in results
    )
    if optional_skip:
        print("  RESULT: OK -- required steps reproduced; optional external-runtime checks skipped.")
    else:
        print("  RESULT: OK -- all required steps reproduced.")
    if tier == 1:
        print("  (Every Section 4-7 headline table and figure was rebuilt without R or")
        print("   Stata; Track A/B/C experiments were re-read, not re-run -- see --recompute.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

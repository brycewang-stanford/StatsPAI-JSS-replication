#!/usr/bin/env python3
"""Standalone replication driver for the StatsPAI JSS paper.

JSS asks that results be reproducible and that a reviewer be able to verify
that within about an hour, with complete scripts for the longer experiments.
This script separates the two and says, for every artifact the compiled
manuscript reads, which of the two produced it.

  Tier 1  (no R, no Stata)  -- DEFAULT, a few minutes on a laptop, well
            inside the JSS one-hour threshold. Runs every
            generator the manuscript depends on and then accounts for each
            manuscript input file (the table at the end of the run, also
            written to ``replication/results/reproduce_manifest.json``):

            * RECOMPUTED on this run from the installed package: the worked
              examples and their figures and tables, every printed listing
              and transcript, the registry census behind every count in the
              text, the deterministic MCP trace, the known-truth recovery
              tests, and the configuration map.
            * RE-TABULATED from frozen experiment artifacts: Track A parity
              (``*_py`` / ``*_R`` / ``*_Stata`` JSON), the original-data
              parity rows, Track B coverage (``results_b1000``), the
              seed-replicated forest draws, and Track C timings. Those
              experiments are recomputed by ``--recompute`` (below) or by
              Tiers 2-3; Tier 1 only rebuilds their tables.

            ``--clean`` deletes every manuscript input first, so a run proves
            that each one has a build edge rather than surviving from an
            earlier checkout (use it in a scratch copy).

  Tier 2  (needs R)         -- Additionally re-runs every R reference of
            Track A on the committed CSV bytes and diffs against the golden
            *_R.json (~30-60 min).

  Tier 3  (needs a Stata license) -- Additionally re-runs the Stata bridge.

Full recomputation of the frozen experiments (each writes the artifact the
tables read, so a recompute followed by Tier 1 rebuilds them from fresh
numbers; ``git diff`` shows what moved):

    python reproduce.py --recompute parity-py    # Python side of every Track A
                                                 # module + fixture bytes (~15 min)
    python reproduce.py --recompute montecarlo   # Track B at B=1,000 + the
                                                 # mechanism experiments (~2 h)
    python reproduce.py --recompute forest-seed  # seed-replicated forest, both
                                                 # sides (~50 min; R side needs R)
    python reproduce.py --recompute performance  # Track C, both sides, one run id
                                                 # (hardware-dependent; needs R)
    python reproduce.py --recompute provenance   # call trace of every Track A
                                                 # module (~15 min)

A recompute group whose reference side needs R fails -- it does not fall
back to the frozen reference -- when Rscript is missing, so fresh Python
numbers are never silently paired with old reference numbers.
Full-recompute dependencies beyond the Tier 1 lock are in
``requirements-jss-recompute.txt``.

Usage
-----
    python reproduce.py                  # Tier 1 (default)
    python reproduce.py --clean          # Tier 1 from an empty set of inputs
    python reproduce.py --transcript replication/results/reproduce_tier1_output.txt
    python reproduce.py --tier 2         # Tier 1 + R parity
    python reproduce.py --tier 3         # Tier 1 + R + Stata
    STATA_EXE=/path/to/stata-mp python reproduce.py --tier 3
    python reproduce.py --list           # this text

Exit code is non-zero if any required step fails or any manuscript input was
not rebuilt, so the script doubles as a CI smoke test.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
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
MANUSCRIPT = PAPER / "manuscript"

RECOMPUTED = "recomputed"
TABULATED = "re-tabulated from frozen artifacts"

#: Every generated file the compiled manuscript reads, the step that writes
#: it, and whether that step recomputes it or re-tabulates frozen results.
MANUSCRIPT_INPUTS: list[tuple[str, str, str]] = [
    ("manuscript/generated_claims.tex", "manuscript claims (registry census)", RECOMPUTED),
    ("manuscript/figures/ex02_basque_gap.pdf", "generate_figures.py", RECOMPUTED),
    ("manuscript/figures/ex03_mpdta_event_study.pdf", "generate_figures.py", RECOMPUTED),
    ("replication/tables/ex07_agent_trace.tex", "ex07_agent_trace.py", RECOMPUTED),
    ("replication/tables/ex08_three_way.tex",
     "ex08_fect_interflex.py (StatsPAI side; R/Stata goldens frozen)", RECOMPUTED),
    ("manuscript/tables/track_a_cross_language_snapshot.tex", "Track-A parity rollup", TABULATED),
    ("manuscript/tables/appendix_b_parity.tex", "gen_appendix_parity.py", TABULATED),
    ("manuscript/tables/headline_parity.tex", "generate_headline_parity_table.py", TABULATED),
    ("manuscript/tables/track_b_monte_carlo.tex", "generate_track_b_tables.py", TABULATED),
    ("manuscript/tables/forest_seed_mc.tex", "generate_forest_seed_table.py", TABULATED),
    ("manuscript/tables/track_c_perf.tex", "Track-C performance artifacts", TABULATED),
    ("manuscript/figures/track_c_loglog.pdf", "Track-C performance artifacts", TABULATED),
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _clean_inputs() -> None:
    """Delete every manuscript input so the run must rebuild each one."""
    for rel, _, _ in MANUSCRIPT_INPUTS:
        path = PAPER / rel
        if path.exists():
            path.unlink()
    print(f"  --clean: removed {len(MANUSCRIPT_INPUTS)} manuscript inputs")


def _account(started: float) -> list[tuple[str, float, bool]]:
    """Say, per manuscript input, whether this run rebuilt it and how."""
    print("\n[Tier 1] manuscript inputs: what this run rebuilt, and how")
    rows, ok_all = [], True
    for rel, step, how in MANUSCRIPT_INPUTS:
        path = PAPER / rel
        rebuilt = path.exists() and path.stat().st_mtime >= started - 1
        ok_all &= rebuilt
        rows.append({
            "file": rel,
            "step": step,
            "provenance": how if rebuilt else "NOT REBUILT",
            "sha256": _sha256(path) if path.exists() else None,
        })
        print(f"  {'ok ' if rebuilt else 'NO '} {rel:58s} {how if rebuilt else 'NOT REBUILT'}")
    out = HERE / "results" / "reproduce_manifest.json"
    out.write_text(json.dumps({"inputs": rows}, indent=2) + "\n", encoding="utf-8")
    print(f"  wrote {out.relative_to(PAPER)}")
    return [("manuscript inputs all rebuilt", 0.0, ok_all)]


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
        "manuscript claims (registry census)",
        [py, str(SCRIPTS / "generate_manuscript_claims.py")],
        cwd=PAPER,
    ))
    results.append(_run(
        "Track-A parity rollup",
        [py, "tests/r_parity/compare.py"],
        cwd=REPO,
    ))
    for script in ["gen_appendix_parity.py", "generate_headline_parity_table.py",
                   "generate_track_b_tables.py", "generate_forest_seed_table.py"]:
        results.append(_run(script, [py, str(SCRIPTS / script)], cwd=PAPER))
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
         "tests/reference_parity/test_validation_entry_points.py",
         "tests/reference_parity/test_sunab_event_time_aggregate_parity.py",
         "-q", "--no-cov", "-p", "no:cacheprovider", "-o", "addopts="],
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
    if not os.environ.get("STATSPAI_DIDM_LIB"):
        print("         note: module 81 needs DIDmultiplegt 0.1.4 in a private library")
        print("         (STATSPAI_DIDM_LIB); see tests/r_parity/R_ENVIRONMENT.md.")
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
    mech = mc / "mechanisms"
    perf = REPO / "tests" / "perf"
    have_r = shutil.which("Rscript") is not None
    # (label, argv, cwd, needs_r)
    groups: dict[str, list[tuple[str, list[str], Path, bool]]] = {
        "parity-py": [
            ("Track A Python side + fixture bytes",
             [py, "tests/r_parity/verify_reproduce_py.py"], REPO, False),
        ],
        "montecarlo": [
            ("Track B coverage, B=1000", [py, str(mc / "run_b1000.py")], REPO, False),
            ("Track B robustness, B=1000", [py, str(mc / "run_robustness_b1000.py")], REPO, False),
            ("Track B size/power", [py, str(mc / "run_size_power_b1000.py")], REPO, False),
            ("mechanism: DML PLR learners", [py, "dml_plr_learners.py"], mech, False),
            ("mechanism: forest size", [py, "forest_trees.py"], mech, False),
            ("mechanism: feols small-sample factor", [py, "feols_ssc.py"], mech, False),
            ("mechanism: RD draw-wise vs rdrobust", [py, "rd_drawwise_reference.py"], mech, True),
        ],
        "forest-seed": [
            ("forest seed MC, Python (reference fixture)",
             [py, "_generate_grf_seed_mc_py.py", "grf"], fixtures, False),
            ("forest seed MC, Python (module-13 design)",
             [py, "_generate_grf_seed_mc_py.py", "m13"], fixtures, False),
            ("forest seed MC, R (reference fixture)",
             ["Rscript", "_generate_grf_seed_mc_R.R", "grf"], fixtures, True),
            ("forest seed MC, R (module-13 design)",
             ["Rscript", "_generate_grf_seed_mc_R.R", "m13"], fixtures, True),
        ],
        # One script runs both sides of every module under one run id, with
        # one thread each; compare_perf.py refuses mixed runs or inputs.
        "performance": [
            ("Track C, both sides + rollup", ["bash", str(perf / "run_when_idle.sh")],
             REPO, True),
        ],
        "provenance": [
            ("Track A call trace", [py, "scripts/trace_parity_provenance.py"], REPO, False),
        ],
    }
    if group not in groups:
        raise SystemExit(f"unknown --recompute group {group!r}; one of {sorted(groups)}")
    print(f"\n[recompute:{group}]")
    env = dict(os.environ)
    env.setdefault("PYTHON", py)
    results = []
    for label, argv, cwd, needs_r in groups[group]:
        if needs_r and not have_r:
            print(f"  -> {label} ... FAILED: Rscript not found; the frozen reference "
                  "was NOT reused", flush=True)
            results.append((f"{label} (Rscript missing)", 0.0, False))
            continue
        results.append(_run(label, argv, cwd=cwd, env=env))
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
    ap.add_argument("--clean", action="store_true",
                    help="delete every manuscript input before Tier 1 (use in a scratch copy)")
    ap.add_argument("--transcript", type=Path,
                    help="write the complete reviewer-facing run output to this file")
    ap.add_argument("--recompute", action="append", default=[],
                    choices=["parity-py", "montecarlo", "forest-seed", "performance",
                             "provenance"],
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
                return _run_tier(args.tier, clean=args.clean)
    return _run_tier(args.tier, clean=args.clean)


def _run_tier(tier: int, clean: bool = False) -> int:
    print("=" * 70)
    print(f"StatsPAI JSS replication -- Tier {tier}")
    print("=" * 70)
    import statspai

    print(f"  statspai {statspai.__version__} from {Path(statspai.__file__).parent}")
    started = time.time()
    if clean:
        _clean_inputs()
    results = tier1()
    results += _account(started)
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
        not ok and not lbl.endswith(("(Rscript missing)", "(Stata missing)"))
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
    print("  Tier 1 needs no R or Stata: it recomputes the examples, listings and census and re-tabulates the frozen parity, coverage and timing experiments.")
    print("  Track A/B/C experiments, the forest seed draws, and the provenance trace")
    print("  were re-tabulated from frozen artifacts, not re-run; see --recompute and")
    print("  replication/results/reproduce_manifest.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Guard active-manuscript headline numbers against their source JSON artifacts.

Motivation
----------
The central claim of the StatsPAI JSS paper is cross-language *numerical*
parity. A paper whose headline numbers drift away from the artifacts that
generate them loses reviewer trust on the first mismatch -- and exactly such a
drift was found and fixed during review (the ``did::mpdta`` CS simple ATT was
printed as ``-0.03995`` in the headline parity table while every reproduction
artifact, and the worked-example text, computed ``-0.0329765``).

This script is a deliberately small, *self-contained* drift guard: it reads only
the in-archive ``Paper-JSS/replication/results/*.json`` artifacts and the active
compiled manuscript sources, and asserts that each anchored headline number
still literally appears in the section the paper claims it appears in. It is
intentionally narrow -- it anchors only on numbers whose in-archive artifact is
the *same estimand on the same data* as the manuscript value (e.g. it does NOT
anchor the ADH special-predictor Basque gap on the default-`V` replica gap,
which is a different estimand). Extend it as new headline numbers are pinned.

``make verify`` runs it (target ``headline-numbers-check``); it can also be
run directly:

    python Paper-JSS/replication/scripts/check_headline_numbers.py

It also guards Section 6: every Track C speed ratio quoted in the prose must
equal the ratio computed from ``tests/perf/results`` at the largest size, and
those results must record the StatsPAI release the manuscript pins. The
timings once stayed at 1.13.0 while the paper moved to 1.30.1, and nothing
noticed, because the table regenerates from whatever JSON is on disk.

Exit status is 0 if every anchored number matches, 1 otherwise.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / "results"
SECTIONS = HERE.parent.parent / "manuscript" / "sections"


def _load(name: str) -> dict:
    with (RESULTS / name).open(encoding="utf-8") as fh:
        return json.load(fh)


def _flatten_tex(name: str) -> str:
    """Read a section file and collapse whitespace so multi-line table cells
    and \\citep blocks do not hide an otherwise-present number."""
    raw = (SECTIONS / name).read_text(encoding="utf-8")
    return re.sub(r"\s+", " ", raw)


def _dig(obj: dict, path: str):
    cur = obj
    for part in path.split("."):
        cur = cur[part]
    return cur


# Each check: human label, artifact file, dotted key path, value formatter,
# and the (section-file, expected-substring) pairs that must contain it.
CHECKS = [
    {
        "label": "did::mpdta CS simple ATT (full precision, worked example)",
        "artifact": "ex03_csdid.json",
        "key": "cs_simple_att.estimate",
        "fmt": lambda v: f"{v:.7f}",          # -0.0329765
        "must_contain": [("04-examples-compact.tex", None)],
    },
    {
        # Section 5 no longer prints the replica ATT in prose; the number
        # lives in the generated cross-language snapshot, which is built from
        # the Track A JSON rather than from ex03. Anchoring the worked
        # example's artifact there checks that the two paths agree.
        "label": "mpdta replica CS simple ATT (cross-language snapshot table)",
        "artifact": "ex03_csdid.json",
        "key": "cs_simple_att.estimate",
        "fmt": lambda v: f"{v:.9f}",          # -0.032976514
        "must_contain": [("../tables/track_a_cross_language_snapshot.tex", None)],
    },
    {
        "label": "advertising-lift estimated average effect (known-truth guard)",
        "artifact": "ex06_causal_impact.json",
        "key": "estimated_avg_effect",
        "fmt": lambda v: f"{v:.3f}",          # 4.306
        "must_contain": [("04-examples-compact.tex", None)],
    },
    {
        "label": "advertising-lift pre-period RMSE (known-truth guard)",
        "artifact": "ex06_causal_impact.json",
        "key": "pre_period_rmse",
        "fmt": lambda v: f"{v:.3f}",          # 0.562
        "must_contain": [("04-examples-compact.tex", None)],
    },
]


# Track C: (module, reference side). The ratio is reference / StatsPAI time
# at the largest size, rendered as compare_perf.py renders it.
PERF = [("01_hdfe", "R"), ("02_csdid", "R"), ("03_scm", "R"),
        ("04_dml", "doubleml_py")]


#: Modules a later release may change without touching the timed path,
#: each with the reason. Anything not listed (and not release metadata or a
#: Markdown/text file) keeps a version mismatch a failure.
NOT_TIMED_MODULES = {
    "src/statspai/_schema_enrich.py": "derives function-schema enums and field "
    "metadata from docstrings; only function_schema() / dump_schemas call it",
}
RELEASE_METADATA = {
    "src/statspai/CITATION.cff",
    "src/statspai/schemas/index.json",
    "src/statspai/__init__.py",  # only its __version__ line, checked below
}


def _estimators_identical(root: Path, measured: str, pinned: str) -> bool:
    """True when the code a timing ran is the timed code of the pinned release.

    A later release that changes only documentation or release metadata
    (1.34.1 and 1.34.2 after 1.34.0) leaves every timed estimator unchanged,
    so its timings are the earlier release's. Accepted only if both tags
    exist and every change under src/ or rust/ between them is release
    metadata (``__init__.py`` limited to its ``__version__`` line), a Markdown
    or text file, or a module in :data:`NOT_TIMED_MODULES`. Anything else
    keeps the version mismatch a failure.
    """
    import subprocess

    def _git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)

    tags = (f"v{measured}", f"v{pinned}")
    if any(_git("rev-parse", "--verify", "--quiet", f"{t}^{{commit}}").returncode != 0 for t in tags):
        return False
    names = _git("diff", "--name-only", tags[0], tags[1], "--", "src", "rust")
    if names.returncode != 0:
        return False
    for path in names.stdout.split():
        if path in RELEASE_METADATA or path in NOT_TIMED_MODULES:
            continue
        if path.endswith((".md", ".txt")):
            continue
        return False
    init = _git("diff", "-U0", tags[0], tags[1], "--", "src/statspai/__init__.py").stdout
    changed = [ln for ln in init.splitlines()
               if ln[:1] in "+-" and not ln.startswith(("+++", "---"))]
    return all(ln[1:].startswith("__version__ = ") for ln in changed)


def _timed_path_status(root: Path) -> dict[str, tuple[bool, str]] | None:
    """Per Track C module: do the committed timings still describe ``root``?

    StatsPAI records, next to the timings, the hash of every source file that
    ran inside the timed calls (``scripts/trace_perf_path.py``, record
    ``tests/perf/results/_timed_path.json``). While those files are unchanged
    the timings hold whatever the version number says. Returns ``None`` when
    the checkout predates that record (tags up to v1.34.2); the caller then
    falls back to the tag-diff rule of :func:`_estimators_identical`.
    """
    import subprocess

    script = root / "scripts" / "trace_perf_path.py"
    record = root / "tests" / "perf" / "results" / "_timed_path.json"
    if not (script.exists() and record.exists()):
        return None
    proc = subprocess.run([sys.executable, str(script), "--check"],
                          cwd=root, capture_output=True, text=True)
    status: dict[str, tuple[bool, str]] = {}
    for line in proc.stdout.splitlines():
        head, _, rest = line.partition(":")
        word, _, stem = head.partition(" ")
        if word in ("OK", "STALE") and stem.strip():
            status[stem.strip()] = (word == "OK", rest.strip())
    return status


def _head_is_tag(root: Path, tag: str) -> bool:
    """True if ``root`` is checked out at ``tag``, or ``tag`` does not exist."""
    import subprocess

    def _rev(ref: str) -> str | None:
        p = subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "--quiet", ref],
                           capture_output=True, text=True)
        return p.stdout.strip() if p.returncode == 0 else None

    tagged = _rev(f"{tag}^{{commit}}")
    return tagged is None or tagged == _rev("HEAD")


def _perf_checks() -> list[str]:
    sys.path.insert(0, str(HERE))
    from _paths import release_version, statspai_root

    results = statspai_root() / "tests" / "perf" / "results"
    flat = _flatten_tex("06-performance.tex")
    out: list[str] = []
    pinned = release_version()
    timed = _timed_path_status(statspai_root())
    # The hash check is binding on the pinned release itself (or on a tree
    # whose release has no tag yet: a release being cut).
    at_pin = _head_is_tag(statspai_root(), f"v{pinned}")
    for est, ref in PERF:
        py = json.loads((results / f"{est}_py.json").read_text(encoding="utf-8"))
        rf = json.loads((results / f"{est}_{ref}.json").read_text(encoding="utf-8"))
        measured = (py.get("hardware") or {}).get("statspai_version")
        ok, why = (timed or {}).get(est, (False, "never traced"))
        if timed is not None and ok:
            print(f"PASS  Track C {est}: {why}")
        elif timed is not None and at_pin:
            out.append(f"FAIL  Track C {est}: timings no longer describe "
                       f"the pinned release: {why}")
        elif measured != pinned:
            if timed is not None:
                # A development tree past the pin: the paper describes
                # v{pinned}, so the tag-diff rule below decides. Re-measure
                # when the paper is re-anchored, not before.
                print(f"NOTE  Track C {est}: this tree has moved past v{pinned} "
                      f"({why}); re-measure at the next re-anchor")
            if measured and _estimators_identical(statspai_root(), measured, pinned):
                print(f"PASS  Track C {est}: timings record StatsPAI {measured}; "
                      f"src/ and rust/ differ from v{pinned} only off the timed path")
            else:
                out.append(f"FAIL  Track C {est}: timings record StatsPAI "
                           f"{measured or 'no version'}, manuscript pins {pinned}")
        n = max(r["n"] for r in py["rows"])
        t_sp = next(r for r in py["rows"] if r["n"] == n)["median_time_s"]
        t_ref = next(r for r in rf["rows"] if r["n"] == n)["median_time_s"]
        ratio = t_ref / t_sp
        if ratio > 1.5:
            needle = f"{ratio:.1f}\\times"
        elif ratio < 0.67:
            needle = f"{1 / ratio:.1f}\\times"
        else:
            needle = f"{ratio:.2f}\\times"
        if needle in flat:
            print(f"PASS  Track C {est}: {needle} present in 06-performance.tex")
        else:
            out.append(f"FAIL  Track C {est}: ratio {needle} (from tests/perf/"
                       f"results) NOT found in 06-performance.tex")
    return out


def main() -> int:
    flat_cache: dict[str, str] = {}
    failures: list[str] = []
    checked = 0

    perf_failures = _perf_checks()
    for line in perf_failures:
        print(line)
    failures.extend(perf_failures)
    checked += len(PERF)

    for chk in CHECKS:
        artifact = _load(chk["artifact"])
        value = _dig(artifact, chk["key"])
        rendered = chk["fmt"](value)
        # The minus sign in the artifact may be a hyphen-minus; the .tex uses a
        # plain hyphen-minus inside math too, so a literal substring search is
        # the right test for "did this exact number make it into the prose."
        needle = rendered
        for section, _ in chk["must_contain"]:
            checked += 1
            flat = flat_cache.setdefault(section, _flatten_tex(section))
            if needle in flat:
                print(f"PASS  {chk['label']}: {needle} present in {section}")
            else:
                failures.append(
                    f"FAIL  {chk['label']}: {needle} "
                    f"(from {chk['artifact']}:{chk['key']}) NOT found in {section}"
                )
                print(failures[-1])

    print(f"\n{checked - len(failures)}/{checked} headline-number anchors matched.")
    if failures:
        print("RESULT: DRIFT DETECTED -- manuscript number disagrees with its "
              "source artifact. Update the manuscript or regenerate the artifact.")
        return 1
    print("RESULT: OK -- every anchored headline number matches its artifact.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

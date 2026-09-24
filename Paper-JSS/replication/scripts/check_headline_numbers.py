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


def _perf_checks() -> list[str]:
    sys.path.insert(0, str(HERE))
    from _paths import release_version, statspai_root

    results = statspai_root() / "tests" / "perf" / "results"
    flat = _flatten_tex("06-performance.tex")
    out: list[str] = []
    pinned = release_version()
    for est, ref in PERF:
        py = json.loads((results / f"{est}_py.json").read_text(encoding="utf-8"))
        rf = json.loads((results / f"{est}_{ref}.json").read_text(encoding="utf-8"))
        measured = (py.get("hardware") or {}).get("statspai_version")
        if measured != pinned:
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

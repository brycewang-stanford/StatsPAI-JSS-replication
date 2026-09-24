"""Execute every code listing printed in the active JSS manuscript.

The manuscript's hand-written listings are part of the paper's claim
surface: Listing 1 in particular is the only in-text evidence for the
"flat estimator surface / interoperable result objects" design claims.
The generated-table audit hashes machine-written fragments but cannot
catch a hand-written listing that silently drifts away from the real
call signatures, which is precisely the failure mode most damaging to
a validation paper.

This audit therefore extracts every ``lstlisting`` block from the
compiled sections of ``manuscript/main.tex`` and executes it verbatim
against the live package:

* plain listings are run as scripts, in a temporary working directory
  (so file-writing lines like ``.to_docx(...)`` exercise the export
  path without polluting the tree);
* REPL-style listings (``>>>`` transcripts) are replayed statement by
  statement through a real interpreter loop, so bare expressions echo
  exactly as they do at a prompt, and **the output printed in the
  manuscript is compared line for line against the output the code
  actually produces**. A stale number inside a printed transcript is the
  failure mode this audit exists to catch: it looks like evidence, it is
  quoted as evidence, and nothing else in the build reads it. Listings
  that must elide output register a reason in ``TRANSCRIPT_ELIDED``;
* per-listing assertions in ``EXPECTED`` additionally pin values the
  surrounding prose quotes;
* listings that continue an earlier context declare a ``PRELUDE`` that
  reproduces exactly the objects the surrounding prose says are in
  scope (e.g. the parity-module fixtures of Section 4.7).

A listing that is present in the manuscript but not covered here fails
the audit, so a newly added listing cannot bypass execution.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import tempfile
import time
import traceback
from contextlib import redirect_stdout
from pathlib import Path

SOURCE_DATE_EPOCH = os.environ.get("SOURCE_DATE_EPOCH")


def _elapsed(start: float) -> float:
    # Deterministic-output convention shared with the other audits: under
    # SOURCE_DATE_EPOCH the artifact must be byte-stable across runs.
    if SOURCE_DATE_EPOCH is not None:
        return 0.0
    return round(time.time() - start, 2)

HERE = Path(__file__).resolve().parent
PAPER_DIR = HERE.parents[1]
MANUSCRIPT = PAPER_DIR / "manuscript"
RESULTS_DIR = PAPER_DIR / "replication" / "results"
OUT_JSON = RESULTS_DIR / "listings_execute_audit.json"
OUT_MD = RESULTS_DIR / "listings_execute_audit.md"

sys.path.insert(0, str(HERE))
from _paths import STATSPAI_ROOT  # noqa: E402

R_DATA = STATSPAI_ROOT / "tests" / "r_parity" / "data"

# The sections actually compiled into main.tex.
ACTIVE_SECTIONS = [
    "01-introduction-compact.tex",
    "02-architecture-compact.tex",
    "03-agent-facing-compact.tex",
    "04-examples-compact.tex",
    "05-parity-compact.tex",
    "06-performance.tex",
    "07-agent-eval.tex",
    "08-computational-details-compact.tex",
    "09-discussion-compact.tex",
]

#: The Section 4.1 transcripts continue the Listing 1 session, so their
#: prelude *is* Listing 1 -- reproduced here rather than re-imported, so
#: that a drift between the manuscript listing and this copy shows up as
#: a transcript mismatch instead of passing silently.
_CARD_SESSION = (
    "import statspai as sp\n"
    "card = sp.datasets.card_1995()\n"
    'X = ["exper", "expersq", "black", "south", "smsa"]\n'
    'ols = sp.regress("lwage ~ educ + " + " + ".join(X), data=card)\n'
    'iv = sp.iv("lwage ~ " + " + ".join(X) + " + (educ ~ nearc4)",\n'
    "           data=card)\n"
    'dml = sp.dml(card, y="lwage", d="educ", X=X,\n'
    '             model="plr", n_folds=5, random_state=42)\n'
    'cf = sp.causal_forest("lwage ~ educ | " + " + ".join(X), data=card,\n'
    "                      n_estimators=2000, discrete_treatment=False,\n"
    "                      random_state=42)\n"
)

# Setup code for listings that the prose presents as continuing an
# existing session. Keys are the LaTeX labels.
PRELUDE: dict[str, str] = {
    "lst:motivating": "",
    "lst:validation-tier-output": "import statspai as sp\n",
    # The Section 4.1 transcripts continue the Listing 1 session, so their
    # prelude *is* Listing 1 -- reproduced here rather than re-imported so
    # a drift between the two shows up as a transcript mismatch.
    "lst:card-output": _CARD_SESSION,
    "lst:card-cate": _CARD_SESSION,
    "lst:csdid": "import statspai as sp\n",
    # The Section 4.3 transcript continues the Listing 3 session.
    "lst:csdid-output": (
        "import statspai as sp\n"
        "mpdta = sp.datasets.mpdta()\n"
        'cs = sp.callaway_santanna(mpdta, y="lemp", t="year",\n'
        '                          i="countyreal", g="first_treat",\n'
        '                          control_group="nevertreated",\n'
        '                          estimator="reg")\n'
        'agg = sp.aggte(cs, type="simple", random_state=0)\n'
        'hd = sp.honest_did(cs, e=0, method="smoothness")\n'
    ),
    "lst:fect": (
        "import pandas as pd\n"
        "import statspai as sp\n"
        f"panel = pd.read_csv(r'{R_DATA / '86_fect.csv'}')\n"
        f"sample = pd.read_csv(r'{R_DATA / '87_interflex.csv'}')\n"
    ),
}

# Post-execution assertions pinning the values the paper quotes.
EXPECTED: dict[str, str] = {
    "lst:validation-tier-output": (
        "assert spec['stability'] == 'stable', spec['stability']\n"
        "assert spec['validation_status'] == 'certified', spec['validation_status']\n"
        "assert len(spec['validation_notes']) >= 3\n"
        "assert spec['limitations'], 'expected a non-empty limitations list'\n"
    ),
    "lst:fect": (
        "assert info['staggered'] is True and info['has_reversals'] is False\n"
        "assert bins.model_info['tests']['p_wald'] is not None\n"
    ),
    "lst:motivating": (
        "import pathlib\n"
        "assert pathlib.Path('returns_to_schooling.docx').exists()\n"
        # The forest in this listing is fitted on a *continuous* treatment
        # (years of schooling). Before 1.25.0 the aggregation applied a
        # binary-treatment AIPW score there and returned -1266.6 against a
        # mean conditional effect of 0.086. Nothing in the listing prints
        # that number, so it could sit in the paper's own front-page
        # example unnoticed. Pin the magnitude, and pin that the
        # aggregation says which quantity it is reporting.
        "import warnings\n"
        "with warnings.catch_warnings(record=True) as _w:\n"
        "    warnings.simplefilter('always')\n"
        "    _agg = cf.average_treatment_effect()\n"
        # Since 1.29.0 the continuous-treatment average is grf's
        # Riesz-representer doubly-robust ATE (aipw_continuous), no longer
        # the 1.25.0 plug-in guard; pin the label, the estimand and the
        # magnitude (0.0787 with 2,000 trees at random_state=42), and that no
        # binary-treatment warning is raised on this path any more.
        "assert _agg['method'] == 'aipw_continuous', _agg['method']\n"
        "assert _agg['estimand'] == 'ATE', _agg['estimand']\n"
        "assert abs(_agg['estimate'] - 0.0787) < 2e-3, _agg['estimate']\n"
        "assert 0.003 < _agg['se'] < 0.007, _agg['se']\n"
        "assert not any('binary treatment' in str(_x.message) for _x in _w)\n"
    ),
    "lst:card-output": (
        "assert abs(float(ols.params['educ']) - 0.07401) < 5e-5\n"
        "assert abs(float(iv.params['educ']) - 0.1323) < 5e-5\n"
        # One endogenous regressor, one excluded instrument: the
        # over-identification test does not exist for this fit, and the
        # audit must say so rather than ask for it (JSS review, 2026-09).
        "_chk = {c['name']: c for c in sp.audit(iv)['checks']}\n"
        "assert _chk['overid_test']['status'] == 'not_applicable'\n"
        "assert _chk['overid_test']['suggest_function'] is None\n"
    ),
    "lst:card-cate": (
        "import numpy as np\n"
        "assert np.isfinite(sp.cate_summary(cf).loc['Mean (ATE)', 'CATE'])\n"
    ),
    "lst:csdid": (
        "assert abs(float(agg.estimate) - (-0.0330)) < 1e-3\n"
    ),
    "lst:csdid-output": (
        "assert bool(hd['rejects_zero'].iloc[0])\n"
        "assert not bool(hd['rejects_zero'].iloc[-1])\n"
    ),
}

#: Listings whose printed output is deliberately not reproduced in full.
#: Each entry needs a reason: an unverified transcript is exactly what
#: this audit exists to prevent, so opting out has to be a decision on
#: the record rather than a silent omission.
TRANSCRIPT_ELIDED: dict[str, str] = {}

LISTING_RE = re.compile(
    r"\\begin\{lstlisting\}\[(?P<opts>.*?)\]\s*\n(?P<body>.*?)\\end\{lstlisting\}",
    re.DOTALL,
)
LABEL_RE = re.compile(r"label=\{(?P<label>[^}]*)\}")


def extract_listings() -> list[dict[str, str]]:
    listings: list[dict[str, str]] = []
    for name in ACTIVE_SECTIONS:
        tex = (MANUSCRIPT / "sections" / name).read_text(encoding="utf-8")
        for match in LISTING_RE.finditer(tex):
            label_m = LABEL_RE.search(match.group("opts"))
            label = label_m.group("label") if label_m else f"<unlabelled in {name}>"
            listings.append(
                {"section": name, "label": label, "body": match.group("body")}
            )
    return listings


def _split_transcript(body: str) -> list[tuple[str, list[str]]]:
    """Split a ``>>>`` transcript into (statement, printed-output) pairs.

    A statement is a ``>>>`` line plus its ``...`` continuations; the
    printed output is every following line up to the next prompt.
    """
    blocks: list[tuple[str, list[str]]] = []
    stmt: list[str] | None = None
    out: list[str] = []
    for raw in body.splitlines():
        if raw.startswith(">>>"):
            if stmt is not None:
                blocks.append(("\n".join(stmt), out))
            stmt, out = [raw[4:] if raw.startswith(">>> ") else raw[3:]], []
        elif raw.startswith("..."):
            if stmt is None:  # a continuation with no prompt is malformed
                raise ValueError("transcript continuation before any '>>>'")
            stmt.append(raw[4:] if raw.startswith("... ") else raw[3:])
        elif stmt is not None:
            out.append(raw)
    if stmt is not None:
        blocks.append(("\n".join(stmt), out))
    return blocks


def _repl_to_script(body: str) -> str:
    """Convert a ``>>>`` transcript into executable statements."""
    return "\n".join(stmt for stmt, _ in _split_transcript(body)) + "\n"


def _replay_transcript(label: str, body: str, prelude: str) -> list[str]:
    """Replay a transcript through a real interpreter loop and diff it.

    Returns a list of human-readable mismatches, empty when the printed
    output in the manuscript is exactly what the code produces.
    ``compile(..., "single")`` is what makes a bare expression echo, so
    the captured text is a genuine prompt transcript rather than the
    output of a script that happens to contain the same statements.
    """
    namespace: dict[str, object] = {"__name__": "__main__"}
    if prelude:
        exec(compile(prelude, f"<{label}:prelude>", "exec"), namespace)

    problems: list[str] = []
    for stmt, printed in _split_transcript(body):
        buf = io.StringIO()
        with redirect_stdout(buf):
            exec(compile(stmt, f"<{label}>", "single"), namespace)
        actual = [line.rstrip() for line in buf.getvalue().splitlines()]
        expected = [line.rstrip() for line in printed]
        # Trailing blank lines in the .tex are layout, not output.
        while expected and not expected[-1]:
            expected.pop()
        while actual and not actual[-1]:
            actual.pop()
        if actual != expected:
            first = next(
                (
                    i
                    for i, (a, b) in enumerate(
                        zip(actual + [None] * len(expected), expected + [None] * len(actual))
                    )
                    if a != b
                ),
                0,
            )
            problems.append(
                f"after {stmt.splitlines()[0]!r}: printed transcript and real "
                f"output first differ at output line {first + 1}\n"
                f"      manuscript: {expected[first] if first < len(expected) else '<no line>'!r}\n"
                f"      actual:     {actual[first] if first < len(actual) else '<no line>'!r}"
            )
    return problems


def _prepare_source(label: str, body: str) -> str:
    is_repl = any(line.startswith(">>>") for line in body.splitlines())
    code = _repl_to_script(body) if is_repl else body
    # A bare expression line used for display (e.g. ``ife.detail``) is
    # valid Python already; nothing to strip. Comments survive verbatim.
    prelude = PRELUDE.get(label, "")
    expected = EXPECTED.get(label, "")
    return prelude + code + "\n" + expected


def run_listing(label: str, body: str) -> dict[str, object]:
    if label not in PRELUDE:
        return {
            "label": label,
            "status": "FAIL",
            "detail": (
                "listing has no registered prelude/assertion entry; add it "
                "to listings_execute_audit.py so it is executed"
            ),
        }
    source = _prepare_source(label, body)
    is_repl = any(line.startswith(">>>") for line in body.splitlines())
    t0 = time.time()
    buf = io.StringIO()
    old_cwd = Path.cwd()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            import os

            os.chdir(tmp)
            try:
                with redirect_stdout(buf):
                    exec(compile(source, f"<{label}>", "exec"), {"__name__": "__main__"})
                # Executing the statements proves they run; replaying the
                # transcript proves the manuscript prints what they print.
                if is_repl and label not in TRANSCRIPT_ELIDED:
                    mismatches = _replay_transcript(
                        label, body, PRELUDE.get(label, "")
                    )
                else:
                    mismatches = []
            finally:
                os.chdir(old_cwd)
        if mismatches:
            return {
                "label": label,
                "status": "FAIL",
                "seconds": _elapsed(t0),
                "detail": "printed transcript does not match real output:\n  - "
                + "\n  - ".join(mismatches),
            }
        return {
            "label": label,
            "status": "PASS",
            "seconds": _elapsed(t0),
            "stdout_bytes": len(buf.getvalue()),
            "transcript_verified": bool(is_repl and label not in TRANSCRIPT_ELIDED),
        }
    except Exception:
        return {
            "label": label,
            "status": "FAIL",
            "seconds": _elapsed(t0),
            "detail": traceback.format_exc(limit=6),
        }


def main() -> int:
    listings = extract_listings()
    rows = [run_listing(item["label"], item["body"]) for item in listings]
    for item, row in zip(listings, rows):
        row["section"] = item["section"]

    n_fail = sum(1 for r in rows if r["status"] != "PASS")
    payload = {
        "audit": "listings_execute_audit",
        "manuscript_sections": ACTIVE_SECTIONS,
        "n_listings": len(rows),
        "n_pass": len(rows) - n_fail,
        "n_fail": n_fail,
        "status": "PASS" if n_fail == 0 else "FAIL",
        "rows": rows,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Manuscript listings execution audit",
        "",
        "Every `lstlisting` block compiled into `main.tex` is executed",
        "verbatim against the live package (REPL transcripts are replayed",
        "line by line; quoted output values are pinned by assertions).",
        "",
        "| Section | Listing | Status | Time (s) |",
        "|---|---|---|---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r.get('section', '?')} | `{r['label']}` | {r['status']} | "
            f"{r.get('seconds', '—')} |"
        )
    if n_fail:
        lines.append("")
        for r in rows:
            if r["status"] != "PASS":
                lines.append(f"## FAIL: `{r['label']}`")
                lines.append("```")
                lines.append(str(r.get("detail", "")))
                lines.append("```")
    lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(f"listings_execute_audit: {payload['status']} "
          f"({payload['n_pass']}/{payload['n_listings']} listings pass)")
    if n_fail:
        for r in rows:
            if r["status"] != "PASS":
                print(f"  FAIL {r['label']}: {str(r.get('detail'))[:400]}",
                      file=sys.stderr)
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())

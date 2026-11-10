#!/usr/bin/env python3
"""Render the full Track A ledger as the manuscript's parity appendix.

Section 5's Table 8 prints a twelve-row *slice* of Track A and points at
the archive for the rest. For a paper whose central claim is same-byte
parity across every registered module, the rest is the evidence, and a
referee should not have to unzip an archive to see whether the other
seventy-five rows pass. This script prints all of them.

The data rows come from ``tests/r_parity/compare.py``'s generated
``parity_table_3way.tex``; only the surrounding table header, column
widths, and caption are authored here. The split matters: the caption
carries the release number and the module counts, and those are the
numbers that go stale. Emitting them from the same generated macros the
body text uses (``\\StatsPAIVersion``, ``\\RParityModuleCount``,
``\\StataParityModuleCount``) means a version bump or a new module
cannot leave an appendix caption describing an older tree -- which is
exactly what the previously copied caption did, still naming release
1.20.0 and 85 modules after the tree had moved on.

Usage::

    python replication/scripts/gen_appendix_parity.py            # write
    python replication/scripts/gen_appendix_parity.py --check    # gate
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:  # _paths.py sits beside this script
    sys.path.insert(0, _SCRIPTS_DIR)

from _paths import PAPER_ROOT, STATSPAI_ROOT
from _track_a_grades import is_stochastic_screen

SOURCE = STATSPAI_ROOT / "tests" / "r_parity" / "results" / "parity_table_3way.tex"
OUTPUT = PAPER_ROOT / "manuscript" / "tables" / "appendix_b_parity.tex"

_HEADER = r"""ID & Method & Worst diff vs \proglang{R} & Worst diff vs \proglang{Stata} & Verdict \\"""

_CAPTION = r"""\caption{Every parity module, at \statspai{}~\StatsPAIVersion{}.
The \code{ID} is the module's two-digit prefix in \code{tests/r\_parity/}.
The difference columns report the worst observed gap across that module's
headline rows, point estimates only. ``none'' means no \proglang{Stata}
reference exists, for a reason recorded in the archive. S marks a stochastic
screen, one draw per engine.}"""


#: ``compare.py`` writes tolerances as ``$\le 5.1e-08$``. Inside math mode
#: TeX sets that as "5.1e - 08" -- an italic *e*, a spaced binary minus,
#: and a break opportunity in the middle of a number, which is how the
#: appendix ended up with "rel $\le$ 5e - 15" split across two lines.
_SCI = re.compile(r"(?<![\w.])(\d(?:\.\d+)?)e-0*(\d+)(?![\w.])")


def _tidy_numbers(row: str) -> str:
    """Set every ``1.2e-08`` as a proper unbreakable power of ten.

    ``\ensuremath`` because the same spelling appears both inside the
    generated ``$\le \dots$`` groups and in plain-text footnote prose
    such as ``rel $<$ 1e-9``; a bare ``\times`` in the second position
    is a "Missing $ inserted" error rather than a typographic nicety.
    """
    return _SCI.sub(
        lambda m: rf"\ensuremath{{{m.group(1)}\times 10^{{-{m.group(2)}}}}}", row
    )


#: compare.py's measured-reason prose sometimes quotes a command in
#: Markdown backticks; TeX sets the opening one as a curly left quote.
_BACKTICK = re.compile(r"`([^`]+)`")


def _grade_row(row: str) -> str:
    """Print the paper's grade where it is finer than compare.py's verdict.

    A PASS on one draw per engine is a stochastic screen (S). Showing it
    as PASS beside same-byte rows let a single draw read as parity.
    """
    row = _BACKTICK.sub(lambda m: rf"\code{{{m.group(1)}}}", row)
    if is_stochastic_screen(row):
        row = row.replace(r"\textbf{PASS}", r"\textbf{S}")
    return row


def _compact_cell(cell: str) -> str:
    """Drop a cell's parenthetical note; the per-row ledger keeps it.

    89 rows with their notes ran to five and a half pages. The evidence a
    reader needs on the page is the worst gap, so the notes stay in
    ``parity_table_3way.md``. Nested parentheses are peeled from the inside.
    """
    previous = None
    while previous != cell:
        previous = cell
        cell = re.sub(r"\s*\([^()]*\)", "", cell)
    return cell.replace("{\\footnotesize}", "").strip()


def _compact_row(row: str) -> str:
    cells = row.rstrip().rstrip("\\\\").split(" & ")
    if len(cells) != 5:
        return row
    module, method, vs_r, vs_stata, verdict = (c.strip() for c in cells)
    if "n/a" in vs_stata:
        vs_stata = "see text"  # module 76: Stata side exists, default rows differ
    elif "\\emph{" in vs_stata or "\\textit{" in vs_stata:
        vs_stata = "none"
    return (
        f"{module} & {_compact_cell(method)} & {_compact_cell(vs_r)} & "
        f"{_compact_cell(vs_stata)} & {verdict} \\\\"
    )


def _body_rows(text: str) -> list[str]:
    """The data rows of the generated longtable, without its own frame."""
    start = text.index(r"\endlastfoot")
    end = text.index(r"\end{longtable}")
    rows = [
        _compact_row(_grade_row(_tidy_numbers(line)))
        for line in text[start:end].splitlines()
        if line.startswith(r"\code{")
    ]
    if not rows:
        raise RuntimeError(f"no data rows found in {SOURCE}")
    return rows


def render() -> str:
    rows = _body_rows(SOURCE.read_text(encoding="utf-8"))
    return "\n".join(
        [
            "% AUTO-GENERATED by replication/scripts/gen_appendix_parity.py",
            "% Data rows come from tests/r_parity/compare.py; the caption and",
            "% table frame are authored in this script. Do not edit by hand.",
            r"\begingroup",
            r"\scriptsize",
            r"\setlength{\tabcolsep}{2pt}",
            # longtable sets its caption in a 4in box by default, which
            # prints the caption indented into the middle of a full-width
            # table rather than under it.
            r"\setlength{\LTcapwidth}{\linewidth}",
            # L{} is main.tex's ragged-right p-column. Justified p-columns
            # stretch "rel $\le 5\times 10^{-15}$" across the full column
            # width, which reads as five separate tokens.
            r"\begin{longtable}{@{}L{0.04\linewidth}L{0.44\linewidth}"
            r"L{0.19\linewidth}L{0.19\linewidth}L{0.07\linewidth}@{}}",
            r"\toprule",
            _HEADER,
            r"\midrule",
            r"\endfirsthead",
            r"\multicolumn{5}{c}{\textit{(Table \ref{tab:track-a-parity} continued)}}\\",
            r"\toprule",
            _HEADER,
            r"\midrule",
            r"\endhead",
            # JSS sets captions below floats, and the style guard enforces
            # it. For a longtable that means the caption belongs in
            # \endlastfoot, so it prints once, under the final page of the
            # table, rather than once above the first page.
            r"\midrule",
            r"\multicolumn{5}{r}{\textit{(continued on the next page)}}\\",
            r"\endfoot",
            r"\bottomrule",
            _CAPTION,
            r"\label{tab:track-a-parity}\\",
            r"\endlastfoot",
            *rows,
            r"\end{longtable}",
            r"\endgroup",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="fail if the committed appendix is stale")
    args = parser.parse_args()

    if not SOURCE.exists():
        print(f"FAIL -- missing {SOURCE}", file=sys.stderr)
        return 1
    rendered = render()
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != rendered:
            print(
                f"FAIL -- {OUTPUT.relative_to(PAPER_ROOT)} is stale; run "
                "`make appendices`",
                file=sys.stderr,
            )
            return 1
        print(f"OK -- {OUTPUT.relative_to(PAPER_ROOT)} is current "
              f"({len(_body_rows(SOURCE.read_text(encoding='utf-8')))} modules)")
        return 0
    OUTPUT.write_text(rendered, encoding="utf-8")
    print(f"OK -- wrote {OUTPUT} "
          f"({len(_body_rows(SOURCE.read_text(encoding='utf-8')))} modules)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

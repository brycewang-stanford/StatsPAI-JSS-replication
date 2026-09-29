"""How the paper grades a Track A headline verdict.

``tests/r_parity/compare.py`` gives every module a PASS or GAP verdict.
The paper's grading is finer: a PASS earned by one draw from each of two
stochastic engines is a stochastic screen (S), not same-byte parity (T2);
the T3 grade for such an estimator rests on a separate seed-replicated
study. compare.py marks these rows in the module's note ("single draw per
engine"), and the appendix renderer and the claims generator both read
that marker through this one predicate so they cannot disagree.
"""

from __future__ import annotations

SCREEN_MARKER = "single draw per engine"


def is_stochastic_screen(note: str) -> bool:
    """True when a Track A row's note says it is one draw per engine."""
    return SCREEN_MARKER in note

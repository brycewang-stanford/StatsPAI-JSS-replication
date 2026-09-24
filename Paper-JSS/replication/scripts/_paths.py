"""Where this checkout is, and where the package it describes is.

Every script here needs two roots: the Paper-JSS checkout it belongs to,
and the StatsPAI checkout whose live registry and parity artefacts it
reports on. Both were previously derived by counting parent directories
from ``__file__``, which is correct only when the paper sits directly
inside the package tree.

Inside a git worktree it is not. ``HERE.parents[2]`` then lands on the
``.worktrees`` directory, every StatsPAI-side path resolves under it, and
the scripts report the files as missing. That failure is indistinguishable
from a genuinely absent file in the output, which is the reason to fix it
centrally rather than per script: a path bug that prints the same message
as a real finding will be read as a real finding.

``STATSPAI_ROOT`` overrides the package root, because a worktree of the
paper is routinely paired with a worktree of the package and the sibling
guess cannot know which one is meant.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

__all__ = [
    "PAPER_ROOT",
    "statspai_root",
    "STATSPAI_ROOT",
    "resolve_claim_path",
    "release_version",
    "EDITOR_FACING_DOCS",
    "PUBLIC_SNAPSHOT_MARKER",
    "withheld_editor_doc",
]

#: The Paper-JSS checkout this file belongs to. This file lives at
#: ``<paper>/replication/scripts/_paths.py``, so the checkout is two
#: directories up from its own directory -- correct in the primary
#: checkout and in a worktree alike.
PAPER_ROOT = Path(__file__).resolve().parents[2]


def _is_statspai_checkout(path: Path) -> bool:
    return (path / "src" / "statspai" / "__init__.py").is_file()


def statspai_root() -> Path:
    """The StatsPAI checkout whose state these scripts describe.

    Order: an explicit ``STATSPAI_ROOT``; then the sibling layout, which
    is right for the primary checkout; then the nearest ancestor that
    actually looks like a StatsPAI checkout, which is what makes a paper
    worktree resolve without the environment variable. Only the last step
    inspects the filesystem, so the common cases stay cheap and the
    fallback is a search rather than another guess.
    """
    override = os.environ.get("STATSPAI_ROOT")
    if override:
        return Path(override).resolve()

    sibling = PAPER_ROOT.parent
    if _is_statspai_checkout(sibling):
        return sibling

    for ancestor in PAPER_ROOT.parents:
        if _is_statspai_checkout(ancestor):
            return ancestor

    # Nothing found: return the sibling so the caller reports a missing
    # file against a plausible path rather than raising at import time
    # in a context that may not need the package root at all.
    return sibling


STATSPAI_ROOT = statspai_root()


def resolve_claim_path(rel: str) -> Path:
    """Resolve a repo-relative path against the tree that owns it.

    Claim and artefact lists mix StatsPAI-relative paths such as
    ``docs/stats.md`` with paper-relative ones written ``Paper-JSS/...``.
    A single root resolves both only in the primary layout.
    """
    if rel.startswith("Paper-JSS/"):
        return PAPER_ROOT / rel[len("Paper-JSS/") :]
    return STATSPAI_ROOT / rel


def release_version() -> str:
    """The release number the manuscript describes, from ``pyproject.toml``.

    Every audit that pins submission-facing prose to a release number reads
    it from here rather than repeating a literal. A literal repeated across
    eight scripts is a version bump that silently half-lands: the manuscript
    names the new release, one audit still greps for the old one, and the
    gap only shows up as an audit failure whose message points at the wrong
    file. Read from the source tree, not ``importlib.metadata``, so the
    number describes the tree the PDF was built from rather than whichever
    wheel is installed in the ambient environment.
    """
    text = (STATSPAI_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if match is None:  # pragma: no cover - a version-less pyproject is a packaging bug
        raise RuntimeError(f"no [project] version in {STATSPAI_ROOT / 'pyproject.toml'}")
    return match.group(1)


def _py_parity_modules() -> set:
    results = STATSPAI_ROOT / "tests" / "r_parity" / "results"
    return {p.name.removesuffix("_py.json") for p in results.glob("*_py.json")}


def expected_r_module_count() -> int:
    """How many Track A modules the R harness covers: one per Python side."""
    return len(_py_parity_modules())


def expected_stata_module_count() -> int:
    """How many Track A modules should carry a frozen Stata reference.

    Derived, not declared: every Python-side parity module either has a
    Stata artefact or a measured reason in ``compare.py::STATA_SKIP_REASON``
    for not having one, and the parity harness contract already enforces
    that partition. The audits used to repeat the resulting number as a
    literal (83), which went stale as soon as two more modules gained Stata
    bridges and turned five audits red for a count, not a finding. Reading
    the skip registry keeps the audits checking the artefacts on disk
    against the registry rather than against an old snapshot of it.
    """
    import ast

    py_modules = _py_parity_modules()
    tree = ast.parse(
        (STATSPAI_ROOT / "tests" / "r_parity" / "compare.py").read_text(encoding="utf-8")
    )
    for node in tree.body:
        target = getattr(node, "target", None)
        if isinstance(node, ast.AnnAssign) and getattr(target, "id", None) == "STATA_SKIP_REASON":
            skipped = {ast.literal_eval(k) for k in node.value.keys}
            return len(py_modules - skipped)
    raise RuntimeError("compare.py no longer defines STATA_SKIP_REASON")


#: Documents addressed to the JSS editors. They belong to the confidential
#: submission, not to the replication material, so the public snapshot
#: (``export_public_replication.py``) omits them and writes
#: ``PUBLIC_SNAPSHOT_MARKER``.
EDITOR_FACING_DOCS = frozenset({
    "Paper-JSS/cover-letter.md",
    "Paper-JSS/REVIEWER-HARDENING-AUDIT.md",
    "Paper-JSS/JOSS-JSS-OVERLAP.md",
})
PUBLIC_SNAPSHOT_MARKER = PAPER_ROOT / "PUBLIC_SNAPSHOT"


def withheld_editor_doc(rel: str) -> bool:
    """True when ``rel`` is an editor-facing document withheld from this tree.

    Audits that check the wording of the submission documents skip such a
    file, and only in the public snapshot: the marker must be present *and*
    the file absent. Anywhere else a missing editor-facing document is
    still a failure.
    """
    if rel not in EDITOR_FACING_DOCS or not PUBLIC_SNAPSHOT_MARKER.is_file():
        return False
    if (statspai_root() / rel).exists():
        return False
    print(f"SKIP -- {rel}: editor-facing document withheld from the public snapshot")
    return True

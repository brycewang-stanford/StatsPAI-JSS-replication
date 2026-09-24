#!/usr/bin/env python3
"""Export the public replication snapshot (StatsPAI-JSS-replication).

The public repository is the JSS submission archive
(``build/statspai-jss-submission.zip``, built by
``jss_submission_package.py``) minus the documents addressed to the JSS
editors, with machine-local paths scrubbed from generated audit output.
Deriving it from the archive keeps one packaging rule set: anything the
archive excludes (notes, e-mail drafts, third-party PDFs, review drafts)
is excluded here too.

Additional public-only rules:

* ``PUBLIC_EXCLUDE`` -- editor-facing submission documents (cover letter,
  reviewer-hardening checklist, JOSS/JSS overlap disclosure). They are
  part of the confidential submission, not of the replication material.
* Absolute paths of the build machine (``/Users/<name>/...``, including
  worktree names) in text files are rewritten to ``<STATSPAI_ROOT>`` or
  ``~``; they carry no evidence and only leak local layout.
* Every file that also exists in the StatsPAI or Paper-JSS checkout is
  taken byte-for-byte from there. The JSS archive transliterates ``.py``
  sources to ASCII for the journal's upload rule, which changes bytes the
  Track-A provenance test hashes; a git repository has no such rule.
* ``Paper-JSS/PUBLIC_SNAPSHOT`` marks the tree so the submission-document
  audits skip the withheld files (``_paths.withheld_editor_doc``).
* The archive's root ``README.md`` is replaced by a public one (the file
  must exist: ``pyproject.toml`` names it as the package readme).

The target directory is emptied except for ``.git`` and rewritten, so the
public repository can be refreshed with a normal commit. A final scan
fails if an excluded file or a machine path survives.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _paths import (  # noqa: E402
    EDITOR_FACING_DOCS,
    PAPER_ROOT,
    PUBLIC_SNAPSHOT_MARKER,
    release_version,
    statspai_root,
)

ARCHIVE = PAPER_ROOT / "build" / "statspai-jss-submission.zip"
DEFAULT_OUT = PAPER_ROOT.parents[1] / "StatsPAI-JSS-replication"
PUBLIC_REPO_URL = "https://github.com/brycewang-stanford/StatsPAI-JSS-replication"

PUBLIC_EXCLUDE = tuple(sorted(EDITOR_FACING_DOCS))
MARKER_REL = "Paper-JSS/" + PUBLIC_SNAPSHOT_MARKER.name
MARKER_TEXT = """\
This tree is the public replication snapshot of the StatsPAI JSS paper.
Documents addressed to the journal editors are withheld from it; the
submission-document audits skip those files here, and only where this
marker is present (see replication/scripts/_paths.py).
"""
#: Files the export writes itself rather than taking from a source tree.
GENERATED = {"README.md", ".gitignore", MARKER_REL}
MAX_FILE_MB = 50.0

#: Real account names only (no brackets), so the patterns do not match
#: their own source text when this script is itself exported.
ROOT_PATH_RE = re.compile(
    r"/Users/[A-Za-z0-9._-]+/Documents/GitHub/StatsPAI"
    r"(?:/\.claude/worktrees/[A-Za-z0-9._-]+|/\.worktrees/[A-Za-z0-9._-]+)?"
)
HOME_PATH_RE = re.compile(r"/Users/[A-Za-z0-9._-]+/")

GITIGNORE = """\
__pycache__/
*.py[cod]
.venv/
.pytest_cache/
.DS_Store
Paper-JSS/build/
Paper-JSS/manuscript/*.aux
Paper-JSS/manuscript/*.bbl
Paper-JSS/manuscript/*.blg
Paper-JSS/manuscript/*.fdb_latexmk
Paper-JSS/manuscript/*.fls
Paper-JSS/manuscript/*.log
Paper-JSS/manuscript/*.out
"""

README = """\
# StatsPAI-JSS-replication

Replication materials for

> Biaoyue Wang and Scott Rozelle. *StatsPAI: Validation-Tiered Python
> Workflows for Causal Inference.* Preprint, submitted to the *Journal of
> Statistical Software*.

This repository is a frozen snapshot of the replication package that
accompanies the manuscript. The package itself is developed at
<https://github.com/brycewang-stanford/StatsPAI>.

| | |
| --- | --- |
| StatsPAI version string | {version} |
| StatsPAI source commit | [`{commit_short}`](https://github.com/brycewang-stanford/StatsPAI/commit/{commit}) |
| Relation to release tag | {tag_note} |
| Manuscript sources commit | `{paper_commit_short}` (private manuscript repository) |

`src/statspai/` here is the source at that commit, and `pip install -e .`
installs exactly it; use it rather than the PyPI wheel to reproduce the
paper.

## Contents

| Path | What it is |
| --- | --- |
| `Paper-JSS/manuscript/` | LaTeX source and PDF of the manuscript |
| `Paper-JSS/replication/reproduce.py` | single-script, three-tier replication driver |
| `Paper-JSS/replication/scripts/` | worked examples, figure/table generators, audits |
| `Paper-JSS/replication/results/` | committed outputs, incl. the Tier-1 transcript |
| `Paper-JSS/README.md` | full reviewer guide: every tier, audit, and artifact |
| `src/statspai/` | the StatsPAI source snapshot the paper describes |
| `tests/r_parity/`, `tests/stata_parity/` | same-byte R / Stata parity modules, CSV fixtures, golden outputs |
| `tests/reference_parity/`, `tests/external_parity/`, `tests/coverage_monte_carlo/`, `tests/perf/` | known-truth recovery, published-number, Monte Carlo coverage, and performance evidence |

## Quick start (Python only, no R or Stata)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r Paper-JSS/requirements-jss.txt
pip install -e .
cd Paper-JSS
python replication/reproduce.py --tier 1
```

Tier 1 rebuilds every headline table and figure of Sections 4-7 from
Python alone; the committed transcript
(`Paper-JSS/replication/results/reproduce_tier1_output.txt`) shows the
expected output. Tier 2 (`--tier 2`) additionally re-runs the R references
(packages pinned in `tests/r_parity/renv.lock`); Tier 3 (`--tier 3`) re-runs
the Stata bridges and needs a Stata licence. See `Paper-JSS/README.md` for
details.

## Notes

* Machine-specific absolute paths in generated audit files have been
  replaced by `<STATSPAI_ROOT>` or `~`.
* Documents addressed to the journal editors (cover letter and related
  submission disclosures) are not part of this public snapshot; a few
  files in `Paper-JSS/` still mention them by name.
* Software is released under the MIT licence (`LICENSE`).
"""


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def _provenance(version: str) -> dict[str, str]:
    root = statspai_root()
    commit = _git(root, "rev-parse", "HEAD").stdout.strip()
    paper_commit = _git(PAPER_ROOT, "rev-parse", "HEAD").stdout.strip()
    if not commit or not paper_commit:
        sys.exit("FAIL -- could not resolve the StatsPAI / Paper-JSS commits")
    dirty = _git(root, "status", "--porcelain", "--", "src", "pyproject.toml").stdout.strip()
    if dirty:
        sys.exit("FAIL -- StatsPAI src/ has uncommitted changes; the snapshot "
                 "would not correspond to any commit")
    tag = f"v{version}"
    if _git(root, "rev-parse", "--verify", "--quiet", tag).returncode != 0:
        tag_note = f"no `{tag}` tag exists"
    elif _git(root, "diff", "--quiet", tag, commit, "--", "src").returncode == 0:
        tag_note = f"`src/` is identical to release tag `{tag}` (PyPI {version})"
    else:
        tag_note = (f"`src/` contains changes committed after release tag `{tag}`; "
                    f"the PyPI {version} wheel is **not** identical to this snapshot")
    return {
        "commit": commit, "commit_short": commit[:10],
        "paper_commit_short": paper_commit[:10], "tag_note": tag_note,
    }


def _clear(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for child in out.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _restore_original_bytes(out: Path) -> int:
    """Overwrite archive members with the checkout's bytes where one exists."""
    root = statspai_root()
    restored = 0
    for p in out.rglob("*"):
        if not p.is_file() or ".git" in p.relative_to(out).parts:
            continue
        rel = p.relative_to(out).as_posix()
        if rel in GENERATED:
            continue
        if rel.startswith("Paper-JSS/"):
            src = PAPER_ROOT / rel[len("Paper-JSS/"):]
        else:
            src = root / rel
        if src.is_file() and src.read_bytes() != p.read_bytes():
            shutil.copyfile(src, p)
            restored += 1
    return restored


def _scrub(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, ValueError):
        return 0
    new = ROOT_PATH_RE.sub("<STATSPAI_ROOT>", text)
    new = HOME_PATH_RE.sub("~/", new)
    if new == text:
        return 0
    path.write_text(new, encoding="utf-8")
    return 1


def export(out: Path, rebuild: bool) -> None:
    if rebuild or not ARCHIVE.is_file():
        subprocess.run([sys.executable,
                        str(PAPER_ROOT / "replication" / "scripts" / "jss_submission_package.py")],
                       check=True)
    _provenance(release_version())  # fail before touching the target
    _clear(out)
    with zipfile.ZipFile(ARCHIVE) as zf:
        zf.extractall(out)

    for rel in PUBLIC_EXCLUDE:
        target = out / rel
        if not target.is_file():
            sys.exit(f"FAIL -- expected {rel} in the archive; update PUBLIC_EXCLUDE")
        target.unlink()

    restored = _restore_original_bytes(out)
    scrubbed = sum(_scrub(p) for p in out.rglob("*") if p.is_file() and ".git" not in p.parts)
    version = release_version()
    prov = _provenance(version)
    (out / "README.md").write_text(README.format(version=version, **prov), encoding="utf-8")
    (out / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    (out / MARKER_REL).write_text(MARKER_TEXT, encoding="utf-8")

    problems = []
    files = [p for p in out.rglob("*") if p.is_file() and ".git" not in p.parts]
    for p in files:
        rel = p.relative_to(out).as_posix()
        if rel in PUBLIC_EXCLUDE:
            problems.append(f"excluded file present: {rel}")
        if p.stat().st_size > MAX_FILE_MB * 1e6:
            problems.append(f"file over {MAX_FILE_MB:.0f} MB: {rel}")
        try:
            if HOME_PATH_RE.search(p.read_text(encoding="utf-8")):
                problems.append(f"machine path survives: {rel}")
        except (UnicodeDecodeError, ValueError):
            pass
    if problems:
        sys.exit("FAIL --\n" + "\n".join(problems))
    size_mb = sum(p.stat().st_size for p in files) / 1e6
    print(f"OK -- exported {len(files)} files ({size_mb:.1f} MB) to {out}")
    print(f"      restored original bytes for {restored} ASCII-transliterated files")
    print(f"      StatsPAI {version}; scrubbed machine paths in {scrubbed} files; "
          f"dropped {len(PUBLIC_EXCLUDE)} editor-facing documents")
    print(f"      publish to {PUBLIC_REPO_URL}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help=f"target directory (default: {DEFAULT_OUT})")
    parser.add_argument("--rebuild", action="store_true",
                        help="rebuild the submission archive first")
    args = parser.parse_args()
    export(args.out.resolve(), args.rebuild)


if __name__ == "__main__":
    main()

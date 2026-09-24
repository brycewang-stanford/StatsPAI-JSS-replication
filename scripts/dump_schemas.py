"""Export the machine-readable StatsPAI schema bundle to ``schemas/``.

Companion to ``scripts/registry_stats.py`` and
``scripts/agent_card_coverage.py``. Writes an import-free, versioned bundle
an external agent / non-Python client can read to discover the whole
surface — tool input schemas, function schemas, agent cards, and a JSON
Schema for the agent-facing *result* payload.

Usage
-----
    python scripts/dump_schemas.py                 # (re)write schemas/
    python scripts/dump_schemas.py --out DIR       # write to DIR
    python scripts/dump_schemas.py --check         # CI: fail if schemas/ stale

``--check`` regenerates in-memory and compares against the committed
``schemas/`` so a PR that changes the tool surface without refreshing the
bundle is flagged (same "artifact stays in sync" discipline as the parity
tables).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
PACKAGE_SCHEMA_DIR = REPO_ROOT / "src" / "statspai" / "schemas"
RUNTIME_SCHEMA_FILES = {
    "index.json",
    "tools.json",
    "functions.json",
    "agent_cards.json",
    "result.schema.json",
}

from statspai._schema_export import (  # noqa: E402
    build_schemas,
    render_files,
)


def _runtime_snapshot(files: dict[str, str]) -> dict[str, str]:
    """Subset bundled inside the wheel for import-free agent discovery."""
    return {k: v for k, v in files.items() if k in RUNTIME_SCHEMA_FILES}


def _write_runtime_snapshot(files: dict[str, str]) -> None:
    PACKAGE_SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    for fname, text in _runtime_snapshot(files).items():
        (PACKAGE_SCHEMA_DIR / fname).write_text(text, encoding="utf-8")


def check(out_dir: Path) -> int:
    """Exit non-zero if the committed bundle differs from a fresh render."""
    expected = render_files(build_schemas())
    stale: list[str] = []
    missing: list[str] = []
    for fname, text in expected.items():
        path = out_dir / fname
        if not path.exists():
            missing.append(fname)
            continue
        if path.read_text(encoding="utf-8") != text:
            stale.append(fname)
    for fname, text in _runtime_snapshot(expected).items():
        path = PACKAGE_SCHEMA_DIR / fname
        label = f"src/statspai/schemas/{fname}"
        if not path.exists():
            missing.append(label)
            continue
        if path.read_text(encoding="utf-8") != text:
            stale.append(label)
    if missing or stale:
        if missing:
            print(f"[dump_schemas] missing files: {missing}", file=sys.stderr)
        if stale:
            print(f"[dump_schemas] stale files: {stale}", file=sys.stderr)
        print(
            "Run `python scripts/dump_schemas.py` and commit the refreshed "
            "schemas/ bundle.",
            file=sys.stderr,
        )
        return 1
    print(f"[dump_schemas] OK — schemas/ is in sync ({len(expected)} files).")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--out",
        default=str(REPO_ROOT / "schemas"),
        help="output directory (default: ./schemas)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if the committed bundle is stale",
    )
    args = parser.parse_args(argv)
    out_dir = Path(args.out)

    if args.check:
        return check(out_dir)

    files = render_files(build_schemas())
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for fname, text in files.items():
        path = out_dir / fname
        path.write_text(text, encoding="utf-8")
        written.append(path)
    if out_dir.resolve() == (REPO_ROOT / "schemas").resolve():
        _write_runtime_snapshot(files)
    print(f"[dump_schemas] wrote {len(written)} files to {out_dir}/:")
    for p in written:
        print(f"   {p.name}")
    if out_dir.resolve() == (REPO_ROOT / "schemas").resolve():
        print(
            f"[dump_schemas] mirrored {len(RUNTIME_SCHEMA_FILES)} runtime "
            f"files to {PACKAGE_SCHEMA_DIR}/"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

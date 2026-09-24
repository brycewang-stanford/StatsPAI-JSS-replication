"""Check that all cited bibliography keys exist in the local JSS bib file."""
from __future__ import annotations

import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
PAPER_DIR = HERE.parents[1]
MANUSCRIPT_DIR = PAPER_DIR / "manuscript"


def main() -> int:
    text = (MANUSCRIPT_DIR / "main.tex").read_text(encoding="utf-8")
    for path in sorted((MANUSCRIPT_DIR / "sections").glob("*.tex")):
        text += "\n" + path.read_text(encoding="utf-8")

    cited: set[str] = set()
    cite_pattern = r"\\cite[a-zA-Z*]*(?:\[[^\]]*\]){0,2}\{([^}]*)\}"
    for match in re.finditer(cite_pattern, text):
        cited.update(key.strip() for key in match.group(1).split(",") if key.strip())

    # The submission .bib (jss-bib.bib) is the cited+reserved subset; orphan
    # entries live in jss-bib-archival.bib. A citation in any manuscript source
    # (compiled OR archival long-form) must resolve against the union of both,
    # so check the union -- the compiled PDF's own resolution is proven
    # independently by latexmk (0 undefined citations).
    available: set[str] = set()
    for bib_name in ("jss-bib.bib", "jss-bib-archival.bib"):
        bib_path = MANUSCRIPT_DIR / bib_name
        if bib_path.exists():
            bib = bib_path.read_text(encoding="utf-8")
            available |= set(re.findall(r"@\w+\{([^,]+),", bib))
    missing = sorted(cited - available)
    print(f"cited={len(cited)} bib={len(available)} missing={len(missing)}")
    if missing:
        print("\n".join(missing))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

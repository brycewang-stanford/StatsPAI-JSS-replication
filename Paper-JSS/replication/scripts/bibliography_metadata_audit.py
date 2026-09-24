"""Audit active JSS bibliography metadata without network access.

This complements ``verify_citations.py``.  The citation verifier checks that
every cited key resolves against the local bibliography union; this audit
focuses on the submission-facing ``jss-bib.bib`` subset used by the active
``main.tex`` input graph.  It records active cited-key counts, reserved
submission-bibliography entries, DOI/locator coverage, and the documented
reason for each no-DOI entry so the archive does not rely on the excluded
``references/`` working notes for bibliography-quality evidence.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
PAPER_DIR = HERE.parents[1]
MANUSCRIPT_DIR = PAPER_DIR / "manuscript"
RESULTS_DIR = PAPER_DIR / "replication" / "results"
OUT_JSON = RESULTS_DIR / "bibliography_metadata_audit.json"
OUT_MD = RESULTS_DIR / "bibliography_metadata_audit.md"
SOURCE_DATE_EPOCH = os.environ.get("SOURCE_DATE_EPOCH")

EXPECTED_RESERVED_KEYS = ["brown2020language"]

NO_DOI_VERIFICATION = {
    "pedregosa2011scikit": (
        "JMLR article; JMLR registers no DOIs, so the entry carries the "
        "official JMLR article URL, verified 2026-09-05 against the JMLR "
        "page and the arXiv record 1201.0490 (title, authors, journal_ref)."
    ),
    "anthropic2024mcp": (
        "Software/web specification citation; URL and access date are rendered "
        "from howpublished/note fields."
    ),
    "bach2022doubleml": (
        "JMLR software paper; URL to the official JMLR article page is present, "
        "and no DOI is recorded in the submission bibliography."
    ),
    "brown2020language": (
        "NeurIPS 2020 proceedings paper; the proceedings carry no DOI, so the "
        "entry records the official proceedings URL plus the arXiv eprint "
        "(2005.14165) rather than attaching the preprint's DOI to the venue record."
    ),
    "chen2025efficient": (
        "arXiv preprint (2506.17729) with no journal publication as of "
        "verification; the eprint field is the identifier and the note says so."
    ),
    "ghanem2026selection": (
        "arXiv preprint (2203.09001, v15 dated 2026-07-24) with no journal "
        "publication as of verification; the eprint field is the identifier."
    ),
    "liang2023helm": (
        "Transactions on Machine Learning Research article; TMLR issues no DOI, "
        "so the entry carries the arXiv eprint (2211.09110) whose journal_ref "
        "names the TMLR publication."
    ),
    "patil2023gorilla": (
        "arXiv preprint (2305.15334) cited as such; the eprint field is the "
        "identifier and no DOI is fabricated."
    ),
    "berge2018efficient": (
        "CREA discussion paper for the fixest implementation lineage; URL to "
        "the institution-hosted PDF is present, and no DOI is recorded."
    ),
    "card1995using": (
        "Book-chapter citation; booktitle, editors, publisher, pages, and year "
        "are present, and no DOI is expected."
    ),
    "econml": (
        "Software repository citation; URL is rendered from the howpublished "
        "field rather than a DOI."
    ),
    "lalonde1986evaluating": (
        "American Economic Review 1986 article from the pre-routine-DOI era; "
        "journal, volume, issue, pages, and year are present, and no DOI is "
        "fabricated."
    ),
    "rios2022csdid": (
        "Reserved software documentation citation; URL and access date are "
        "rendered from howpublished/note fields."
    ),
}


def _generated_at_unix() -> int:
    if SOURCE_DATE_EPOCH is not None:
        return int(SOURCE_DATE_EPOCH)
    return int(time.time())


def _strip_comments(text: str) -> str:
    return re.sub(r"(?<!\\)%.*", "", text)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _resolve_tex_input(raw: str) -> Path:
    path = MANUSCRIPT_DIR / raw
    if path.suffix != ".tex":
        path = path.with_suffix(".tex")
    return path


def _active_tex_files() -> list[Path]:
    main = MANUSCRIPT_DIR / "main.tex"
    seen: set[Path] = set()
    ordered: list[Path] = []

    def visit(path: Path) -> None:
        path = path.resolve()
        if path in seen:
            return
        seen.add(path)
        ordered.append(path)
        text = _strip_comments(_read(path))
        for match in re.finditer(r"\\(?:input|include)\{([^}]+)\}", text):
            child = _resolve_tex_input(match.group(1).strip())
            if child.exists():
                visit(child)

    visit(main)
    return ordered


def _active_citations(paths: list[Path]) -> list[str]:
    cited: set[str] = set()
    cite_pattern = r"\\cite[a-zA-Z*]*(?:\[[^\]]*\]){0,2}\{([^}]*)\}"
    for path in paths:
        for match in re.finditer(cite_pattern, _strip_comments(_read(path))):
            cited.update(key.strip() for key in match.group(1).split(",") if key.strip())
    return sorted(cited)


def _extract_field(body: str, name: str) -> str | None:
    match = re.search(r"\b" + re.escape(name) + r"\s*=\s*", body, flags=re.I)
    if not match:
        return None
    i = match.end()
    while i < len(body) and body[i].isspace():
        i += 1
    if i >= len(body):
        return None
    if body[i] == "{":
        depth = 0
        start = i + 1
        j = i
        while j < len(body):
            if body[j] == "{":
                depth += 1
            elif body[j] == "}":
                depth -= 1
                if depth == 0:
                    return body[start:j].strip()
            j += 1
        return None
    if body[i] == '"':
        start = i + 1
        j = start
        while j < len(body):
            if body[j] == '"' and body[j - 1] != "\\":
                return body[start:j].strip()
            j += 1
        return None
    start = i
    j = i
    while j < len(body) and body[j] not in ",\n":
        j += 1
    return body[start:j].strip()


def _parse_bib(path: Path) -> list[dict[str, Any]]:
    text = _strip_comments(_read(path))
    entries: list[dict[str, Any]] = []
    for match in re.finditer(r"@(\w+)\s*\{\s*([^,]+),", text):
        entry_type = match.group(1).lower()
        key = match.group(2).strip()
        start = text.index("{", match.start())
        depth = 0
        i = start
        while i < len(text):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        body = text[start + 1 : i]
        field_names = sorted(
            {field.lower() for field in re.findall(r"\b([A-Za-z][A-Za-z0-9_-]*)\s*=", body)}
        )
        fields = {
            field: _extract_field(body, field)
            for field in field_names
        }
        entries.append(
            {
                "key": key,
                "type": entry_type,
                "fields": fields,
            }
        )
    return entries


def _required_fields(entry_type: str) -> set[str]:
    base = {"author", "title", "year"}
    if entry_type == "article":
        return base | {"journal"}
    if entry_type == "book":
        return base | {"publisher"}
    if entry_type == "incollection":
        return base | {"booktitle", "publisher", "pages"}
    if entry_type == "inproceedings":
        return base | {"booktitle"}
    return base


def _has_locator(fields: dict[str, str | None]) -> bool:
    for field in ("doi", "url", "isbn", "issn", "eprint"):
        if fields.get(field):
            return True
    for field in ("howpublished", "note"):
        value = fields.get(field) or ""
        if "http://" in value or "https://" in value or "\\url{" in value:
            return True
    return False


def _bbl_summary() -> dict[str, Any]:
    bbl = MANUSCRIPT_DIR / "main.bbl"
    if not bbl.exists():
        return {
            "present": False,
            "bibitem_count": None,
            "thebibliography_count": None,
        }
    text = _read(bbl)
    count_match = re.search(r"\\begin\{thebibliography\}\{(\d+)\}", text)
    return {
        "present": True,
        "bibitem_count": len(re.findall(r"\\bibitem", text)),
        "thebibliography_count": int(count_match.group(1)) if count_match else None,
    }


def _check(name: str, ok: bool, evidence: str, failures: list[str]) -> dict[str, Any]:
    if not ok:
        failures.append(name)
    return {"requirement": name, "ok": bool(ok), "evidence": evidence}


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []

    active_files = _active_tex_files()
    active_cited_keys = _active_citations(active_files)
    bib_entries = _parse_bib(MANUSCRIPT_DIR / "jss-bib.bib")
    archival_path = MANUSCRIPT_DIR / "jss-bib-archival.bib"
    archival_entries = _parse_bib(archival_path) if archival_path.exists() else []

    by_key = {entry["key"]: entry for entry in bib_entries}
    duplicate_keys = sorted(
        key
        for key in {entry["key"] for entry in bib_entries}
        if [entry["key"] for entry in bib_entries].count(key) > 1
    )
    bib_keys = sorted(by_key)
    active_missing = sorted(set(active_cited_keys) - set(bib_keys))
    reserved_keys = sorted(set(bib_keys) - set(active_cited_keys))
    unexpected_reserved = sorted(set(reserved_keys) - set(EXPECTED_RESERVED_KEYS))
    missing_reserved = sorted(set(EXPECTED_RESERVED_KEYS) - set(reserved_keys))
    archival_keys = sorted(entry["key"] for entry in archival_entries)
    active_archival_only = sorted(set(active_cited_keys) & (set(archival_keys) - set(bib_keys)))

    field_failures = []
    for entry in bib_entries:
        fields = entry["fields"]
        missing = sorted(field for field in _required_fields(entry["type"]) if not fields.get(field))
        if missing:
            field_failures.append({"key": entry["key"], "type": entry["type"], "missing": missing})

    no_doi_entries = []
    for entry in bib_entries:
        fields = entry["fields"]
        if fields.get("doi"):
            continue
        key = entry["key"]
        no_doi_entries.append(
            {
                "key": key,
                "type": entry["type"],
                "active_cited": key in active_cited_keys,
                "reserved": key in reserved_keys,
                "has_locator": _has_locator(fields),
                "manual_verification": NO_DOI_VERIFICATION.get(key),
            }
        )
    missing_no_doi_reasons = sorted(
        entry["key"] for entry in no_doi_entries if not entry["manual_verification"]
    )
    stale_no_doi_reasons = sorted(
        set(NO_DOI_VERIFICATION) - {entry["key"] for entry in no_doi_entries}
    )

    bbl = _bbl_summary()
    bbl_mismatch = (
        bbl["present"]
        and (
            bbl.get("bibitem_count") != len(active_cited_keys)
            or bbl.get("thebibliography_count") != len(active_cited_keys)
        )
    )

    doi_count = sum(1 for entry in bib_entries if entry["fields"].get("doi"))
    url_count = sum(1 for entry in bib_entries if entry["fields"].get("url"))
    locator_count = sum(1 for entry in bib_entries if _has_locator(entry["fields"]))

    checks = [
        _check(
            "active manuscript citations resolve inside jss-bib.bib",
            not active_missing,
            f"missing={active_missing}",
            failures,
        ),
        _check(
            "submission bibliography has no duplicate keys",
            not duplicate_keys,
            f"duplicates={duplicate_keys}",
            failures,
        ),
        _check(
            "reserved bibliography keys are explicit and stable",
            not unexpected_reserved and not missing_reserved,
            f"reserved={reserved_keys}; expected={EXPECTED_RESERVED_KEYS}",
            failures,
        ),
        _check(
            "active citations are not archival-only",
            not active_archival_only,
            f"active_archival_only={active_archival_only}",
            failures,
        ),
        _check(
            "submission bibliography entries keep required fields",
            not field_failures,
            f"field_failures={field_failures}",
            failures,
        ),
        _check(
            "no-DOI entries have manual verification reasons",
            not missing_no_doi_reasons and not stale_no_doi_reasons,
            (
                f"missing_reasons={missing_no_doi_reasons}; "
                f"stale_reasons={stale_no_doi_reasons}"
            ),
            failures,
        ),
        _check(
            "compiled bibliography count matches active citations when main.bbl exists",
            not bbl_mismatch,
            (
                f"bbl_present={bbl['present']}; bibitems={bbl.get('bibitem_count')}; "
                f"active_citations={len(active_cited_keys)}"
            ),
            failures,
        ),
    ]

    status = "PASS" if not failures else "FAIL"
    payload = {
        "generated_at_unix": _generated_at_unix(),
        "status": status,
        "active_tex_files": [
            str(path.relative_to(PAPER_DIR)) for path in active_files
        ],
        "active_cited_keys": active_cited_keys,
        "active_cited_key_count": len(active_cited_keys),
        "submission_bib_entry_count": len(bib_entries),
        "archival_bib_entry_count": len(archival_entries),
        "doi_entry_count": doi_count,
        "url_entry_count": url_count,
        "locator_entry_count": locator_count,
        "reserved_entry_keys": reserved_keys,
        "expected_reserved_entry_keys": EXPECTED_RESERVED_KEYS,
        "duplicate_keys": duplicate_keys,
        "active_missing_from_submission_bib": active_missing,
        "active_archival_only_keys": active_archival_only,
        "field_failures": field_failures,
        "no_doi_entries": no_doi_entries,
        "no_doi_entry_count": len(no_doi_entries),
        "no_doi_manual_verification_count": sum(
            1 for entry in no_doi_entries if entry["manual_verification"]
        ),
        "missing_no_doi_reasons": missing_no_doi_reasons,
        "stale_no_doi_reasons": stale_no_doi_reasons,
        "compiled_bibliography": bbl,
        "checks": checks,
        "failures": failures,
    }

    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# JSS Bibliography Metadata Audit",
        "",
        f"Status: {status}",
        f"Active TeX inputs: {len(active_files)}",
        f"Active cited keys: {len(active_cited_keys)}",
        f"Submission bibliography entries: {len(bib_entries)}",
        f"Reserved entries: {len(reserved_keys)} ({', '.join(reserved_keys)})",
        f"Archival bibliography entries: {len(archival_entries)}",
        f"Entries with DOI: {doi_count}",
        f"Entries with URL field: {url_count}",
        f"Entries with DOI/URL/ISBN/eprint/howpublished locator: {locator_count}",
        f"No-DOI entries with manual reasons: {payload['no_doi_manual_verification_count']}/{len(no_doi_entries)}",
        (
            "Compiled main.bbl bibitems: "
            + (
                f"{bbl['bibitem_count']} (thebibliography={bbl['thebibliography_count']})"
                if bbl["present"]
                else "not present"
            )
        ),
        "",
        "## Checks",
        "",
        "| Requirement | Status | Evidence |",
        "|---|---:|---|",
    ]
    for check in checks:
        lines.append(
            f"| {check['requirement']} | {'PASS' if check['ok'] else 'FAIL'} | {check['evidence']} |"
        )
    lines.extend(
        [
            "",
            "## No-DOI Entries",
            "",
            "| Key | Scope | Locator | Manual verification reason |",
            "|---|---|---:|---|",
        ]
    )
    for entry in no_doi_entries:
        scope = "active" if entry["active_cited"] else "reserved"
        locator = "yes" if entry["has_locator"] else "no"
        reason = entry["manual_verification"] or "MISSING"
        lines.append(f"| `{entry['key']}` | {scope} | {locator} | {reason} |")
    lines.extend(
        [
            "",
            "Failures: " + (", ".join(failures) if failures else "none"),
            "",
            "Machine-readable detail: `replication/results/bibliography_metadata_audit.json`",
        ]
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if failures:
        print("FAIL -- bibliography metadata audit found citation metadata gaps")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"OK -- wrote {OUT_JSON}")
    print(f"OK -- wrote {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

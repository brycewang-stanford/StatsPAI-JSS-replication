#!/usr/bin/env python3
"""Check every DOI-bearing reference in the submission bib against Crossref.

The project's citation policy makes a fabricated or drifted reference a
red line: a reader who opens one DOI and finds the wrong paper has a
reason to doubt every number in the article. The offline
``bibliography_metadata_audit`` enforces the *shape* of the bibliography
-- required fields, no duplicate keys, a manual reason for every entry
without a DOI -- but it cannot tell whether ``10.1111/rssb.12027``
actually resolves to "Covariate Balancing Propensity Score" in volume
76(1) of JRSS-B. Only the registry can.

This tool is deliberately **not** part of ``make audit``. The audit chain
must run offline and deterministically for a reviewer with no network,
and a rate-limited third-party API satisfies neither. Run it by hand
before submission, and after adding any reference::

    python replication/scripts/verify_bib_against_crossref.py
    python replication/scripts/verify_bib_against_crossref.py --json out.json

For each entry it compares, against the Crossref record: the title (token
overlap, because publishers inject markup and subtitle punctuation), the
first author's family name, the publication year (accepting either the
print or the online year, since the two differ for many entries and the
bibliography follows the print year), and the container title. Anything
that does not line up is printed for a human to adjudicate -- the tool
reports, it does not edit.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:  # _paths.py sits beside this script
    sys.path.insert(0, _SCRIPTS_DIR)

from _paths import PAPER_ROOT

BIB = PAPER_ROOT / "manuscript" / "jss-bib.bib"
#: Crossref asks for a contact address in the User-Agent; it buys a
#: politer rate limit and lets them tell us if we misbehave.
USER_AGENT = "statspai-jss-bib-check/1.0 (mailto:brycew6m@stanford.edu)"
API = "https://api.crossref.org/works/"
#: arXiv registers its DOIs with DataCite, so a 10.48550/* prefix is a
#: Crossref 404 by construction rather than a bad reference. Fall back to
#: the registry that actually holds the record.
DATACITE_API = "https://api.datacite.org/dois/"

#: Title-comparison threshold. Publisher records carry markup, dropped
#: subtitles, and inconsistent capitalisation, so exact equality produces
#: noise; a two-thirds token overlap separates "same paper" from "wrong
#: DOI" without hand-tuning per entry.
TITLE_OVERLAP_MIN = 0.67

#: Entries whose registry record legitimately differs from the printed
#: reference, with the reason. Same discipline as the parity harness's
#: registered tolerances: a difference is allowed only when it is named,
#: so an unexplained one stays visible instead of drowning in noise.
#: Keyed by bib key; the value must be a substring of the reported
#: problem, so a *new* problem on the same entry is still surfaced.
KNOWN_BENIGN: dict[str, tuple[str, str]] = {
    "angrist2009mostly": (
        "title overlap",
        "Crossref registers the short title 'Mostly Harmless Econometrics'; "
        "the entry prints the book's full title including the subtitle "
        "'An Empiricist's Companion', which is what the title page carries.",
    ),
    "lam2015numba": (
        "title overlap",
        "Crossref registers the one-word proceedings title 'Numba'; the "
        "entry prints the full title from the ACM record, "
        "'Numba: A LLVM-Based Python JIT Compiler'.",
    ),
    "wang2020minimal": (
        "year 2020 is not among the registry",
        "Crossref carries only the 2019 advance-article date. The Oxford "
        "Academic article page gives the print issue as Biometrika 107(1), "
        "93-105, March 2020, which is the year the entry prints.",
    ),
}

_ENTRY = re.compile(r"@(\w+)\s*\{\s*([^,]+),(.*?)\n\}", re.S)
_FIELD = re.compile(r"(\w+)\s*=\s*[{\"](.*?)[}\"]\s*,?\s*\n", re.S)


def _tokens(text: str, *, min_length: int = 3) -> set[str]:
    """Comparable word tokens.

    ``min_length`` drops articles and initials from *titles*. It must not
    be applied to surnames: "Ho", "Xu" and "Li" are three real first
    authors in this bibliography, and a three-character floor silently
    reduced each of them to the empty set, which then failed to overlap
    with itself and reported a fabricated author mismatch.
    """
    text = re.sub(r"<[^>]+>", " ", text)          # publisher markup
    text = re.sub(r"[{}\\$^_]", " ", text)         # TeX residue
    return {
        t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) >= min_length
    }


def parse_bib(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    entries = []
    for kind, key, body in _ENTRY.findall(text):
        fields = {name.lower(): value for name, value in _FIELD.findall(body + "\n")}
        fields["_key"] = key.strip()
        fields["_kind"] = kind
        entries.append(fields)
    return entries


def _datacite(doi: str) -> dict | None:
    """Fetch a DataCite record and shape it like a Crossref message."""
    request = urllib.request.Request(
        DATACITE_API + urllib.parse.quote(doi, safe="/"),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            attributes = json.loads(response.read().decode("utf-8"))["data"][
                "attributes"
            ]
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError,
            TimeoutError, json.JSONDecodeError):
        return None
    titles = [t.get("title", "") for t in attributes.get("titles") or []]
    authors = [
        {"family": (c.get("familyName") or c.get("name", "").split(",")[0])}
        for c in attributes.get("creators") or []
    ]
    year = attributes.get("publicationYear")
    return {
        "title": titles or [""],
        "author": authors,
        "container-title": [attributes.get("publisher") or "arXiv"],
        "issued": {"date-parts": [[year]] if year else []},
        "_registry": "DataCite",
    }


def crossref(doi: str, *, retries: int = 4) -> dict | None:
    request = urllib.request.Request(
        API + urllib.parse.quote(doi, safe="/"),
        headers={"User-Agent": USER_AGENT},
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))["message"]
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return _datacite(doi)
            time.sleep(2 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            time.sleep(2 * (attempt + 1))
    return None


def _years(record: dict) -> set[int]:
    """Every year Crossref associates with the record.

    Print and online years differ for a large minority of entries, and a
    bibliography that follows the print year is right to. Accept either.
    """
    years: set[int] = set()
    for field in ("published-print", "published-online", "issued", "created"):
        parts = (record.get(field) or {}).get("date-parts") or []
        for part in parts:
            if part and isinstance(part[0], int):
                years.add(part[0])
    return years


def check(entry: dict[str, str]) -> dict[str, object]:
    key, doi = entry["_key"], entry.get("doi", "").strip()
    result: dict[str, object] = {"key": key, "doi": doi, "problems": []}
    problems: list[str] = result["problems"]  # type: ignore[assignment]

    record = crossref(doi)
    result["registry"] = (record or {}).get("_registry", "Crossref")
    if record is None:
        problems.append("DOI resolves in neither the Crossref nor the DataCite registry")
        result["status"] = "UNRESOLVED"
        return result

    bib_title = entry.get("title", "")
    xref_title = (record.get("title") or [""])[0]
    bib_tokens, xref_tokens = _tokens(bib_title), _tokens(xref_title)
    overlap = (
        len(bib_tokens & xref_tokens) / max(len(bib_tokens), 1) if bib_tokens else 0.0
    )
    result["title_overlap"] = round(overlap, 3)
    result["crossref_title"] = xref_title
    if overlap < TITLE_OVERLAP_MIN:
        problems.append(f"title overlap {overlap:.0%}: registry says {xref_title!r}")

    authors = record.get("author") or []
    if authors and entry.get("author"):
        first_family = (authors[0].get("family") or "").lower()
        bib_first = entry["author"].split(" and ")[0]
        bib_family = _tokens(bib_first.split(",")[0], min_length=1)
        if first_family and not (_tokens(first_family, min_length=1) & bib_family):
            problems.append(
                f"first author {bib_first!r} vs registry {authors[0].get('family')!r}"
            )
    result["crossref_first_author"] = authors[0].get("family") if authors else None

    bib_year = entry.get("year", "").strip()
    xref_years = _years(record)
    result["crossref_years"] = sorted(xref_years)
    if bib_year.isdigit() and xref_years and int(bib_year) not in xref_years:
        problems.append(
            f"year {bib_year} is not among the registry's {sorted(xref_years)}"
        )

    bib_venue = entry.get("journal") or entry.get("booktitle") or ""
    xref_venue = (record.get("container-title") or [""])[0]
    result["crossref_container"] = xref_venue
    if bib_venue and xref_venue:
        venue_overlap = len(_tokens(bib_venue) & _tokens(xref_venue)) / max(
            len(_tokens(bib_venue)), 1
        )
        # Container titles are the noisiest field (publishers register
        # "The Stata Journal: Promoting communications on statistics and
        # Stata"), so this is reported, never failed on overlap alone.
        result["venue_overlap"] = round(venue_overlap, 3)

    if problems and key in KNOWN_BENIGN:
        marker, reason = KNOWN_BENIGN[key]
        if all(marker in problem for problem in problems):
            result["status"] = "EXPLAINED"
            result["explanation"] = reason
            return result
    result["status"] = "OK" if not problems else "REVIEW"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, help="write the full report here")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="seconds between Crossref requests")
    args = parser.parse_args()

    entries = parse_bib(BIB)
    with_doi = [e for e in entries if e.get("doi")]
    without = [e["_key"] for e in entries if not e.get("doi")]
    print(f"{BIB.name}: {len(entries)} entries, {len(with_doi)} with a DOI, "
          f"{len(without)} without")

    results = []
    for index, entry in enumerate(with_doi, start=1):
        result = check(entry)
        results.append(result)
        flag = {
            "OK": "ok       ",
            "EXPLAINED": "explained",
            "REVIEW": "REVIEW   ",
            "UNRESOLVED": "NOT FOUND",
        }[str(result["status"])]
        print(f"[{index:3d}/{len(with_doi)}] {flag} {result['key']}")
        for problem in result["problems"]:  # type: ignore[union-attr]
            print(f"              - {problem}")
        time.sleep(args.delay)

    explained = [r for r in results if r["status"] == "EXPLAINED"]
    flagged = [r for r in results if r["status"] not in ("OK", "EXPLAINED")]
    print()
    print(
        f"Resolved and consistent: "
        f"{len(results) - len(flagged) - len(explained)}/{len(results)}"
    )
    if explained:
        print(f"Registry differs for a named reason: {len(explained)}")
        for result in explained:
            print(f"  {result['key']}: {result['explanation']}")
    if without:
        print(f"No DOI (checked by hand, see paper.bib annote): {', '.join(sorted(without))}")
    if flagged:
        print("\nNeeds a human look:")
        for result in flagged:
            print(f"  {result['key']}: {'; '.join(result['problems'])}")  # type: ignore[arg-type]
    if args.json:
        args.json.write_text(
            json.dumps({"entries": results, "no_doi": sorted(without)}, indent=2),
            encoding="utf-8",
        )
        print(f"\nWrote {args.json}")
    return 1 if flagged else 0


if __name__ == "__main__":
    raise SystemExit(main())

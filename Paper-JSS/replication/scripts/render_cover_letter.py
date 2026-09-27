#!/usr/bin/env python3
"""Render ``cover-letter.md`` from its template and the generated artifacts.

The cover letter quotes a dozen numbers -- release, registry census, schema
parameters, parity modules, Tier 1 steps, page count, archive size and file
count, evidence-map cards, data-provenance counts. They used to be typed by
hand and drifted from the manuscript within a day (the 1.31.0 letter said
142 validated / 690 api_stable / 9,635 parameters / 52 pages while the PDF
said 143 / 689 / 9,664 / 53). Every number now comes from the artifact that
owns it:

* ``manuscript/generated_claims.tex`` -- release and registry/schema counts,
  the same macros the manuscript prints;
* ``manuscript/main.pdf`` -- page count;
* ``replication/results/reproduce_tier1_output.txt`` -- Tier 1 steps;
* ``replication/results/reproduction_environment_audit.json`` -- reproduced
  R / Stata module counts;
* ``replication/results/reviewer_evidence_map.json`` -- card / route counts;
* ``replication/results/data_provenance_audit.json`` -- data inventory;
* ``build/statspai-jss-submission-manifest.json`` -- archive size and files.

The archive contains the letter, so its size depends on the letter. ``--sync``
re-renders and repackages until the two agree (normally one round).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from io import BytesIO
from pathlib import Path

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _paths import PAPER_ROOT, withheld_editor_doc  # noqa: E402

TEMPLATE = PAPER_ROOT / "cover-letter.template.md"
OUTPUT = PAPER_ROOT / "cover-letter.md"
CLAIMS = PAPER_ROOT / "manuscript" / "generated_claims.tex"
MAIN_PDF = PAPER_ROOT / "manuscript" / "main.pdf"
RESULTS = PAPER_ROOT / "replication" / "results"
TIER1 = RESULTS / "reproduce_tier1_output.txt"
REPRO_ENV = RESULTS / "reproduction_environment_audit.json"
EVIDENCE_MAP = RESULTS / "reviewer_evidence_map.json"
DATA_PROVENANCE = RESULTS / "data_provenance_audit.json"
PACKAGE_MANIFEST = PAPER_ROOT / "build" / "statspai-jss-submission-manifest.json"
PACKAGER = PAPER_ROOT / "replication" / "scripts" / "jss_submission_package.py"
#: Other archive members that state the archive's own size; the verifier
#: checks them against the final zip, so --sync keeps them current too.
SIZE_DISCLOSURE_DOCS = (
    PAPER_ROOT / "README.md",
    PAPER_ROOT / "REVIEWER-HARDENING-AUDIT.md",
)
#: Generated reports inside the archive that record its size or file count.
SIZE_DEPENDENT_REPORTS = (
    (
        PAPER_ROOT / "replication" / "scripts" / "reviewer_evidence_map.py",
        PAPER_ROOT / "replication" / "results" / "reviewer_evidence_map.json",
    ),
    (
        PAPER_ROOT / "replication" / "scripts" / "editor_screening_checklist.py",
        PAPER_ROOT / "replication" / "results" / "editor_screening_checklist.json",
    ),
)
_SIZE_PHRASE = re.compile(
    r"\d+\.\d{2} MiB \(\d+\.\d{2} MB decimal\)(?P<mid>[^.]{0,40}?)"
    r"(?:\d{1,3}(?:,\d{3})*|\d+) files"
)

_FIELD = re.compile(r"\{\{(\w+)\}\}")


def _claims() -> dict[str, str]:
    """Plain-text values of the manuscript's generated macros."""
    text = CLAIMS.read_text(encoding="utf-8")
    values = {}
    for name, raw in re.findall(r"\\newcommand\{\\(\w+)\}\{(.*)\}\s*$", text, re.M):
        values[name] = raw.replace("{,}", ",").replace("\\%", "%")
    return values


def _json(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"FAIL -- {path.relative_to(PAPER_ROOT)} is missing; build it first")
    return json.loads(path.read_text(encoding="utf-8"))


def _page_count() -> int:
    from pypdf import PdfReader  # noqa: PLC0415

    return len(PdfReader(BytesIO(MAIN_PDF.read_bytes())).pages)


def _tier1() -> str:
    match = re.search(r"(\d+/\d+) steps passed", TIER1.read_text(encoding="utf-8"))
    if match is None:
        raise SystemExit(f"FAIL -- no Tier 1 summary in {TIER1.relative_to(PAPER_ROOT)}")
    return match.group(1)


def _fields() -> dict[str, str]:
    claims = _claims()
    repro = _json(REPRO_ENV)
    evidence = _json(EVIDENCE_MAP)["summary"]
    data = _json(DATA_PROVENANCE)["summary"]
    categories = data["category_counts"]
    package = _json(PACKAGE_MANIFEST)
    pages = _page_count()
    fields = {
        "Version": claims["StatsPAIVersion"],
        "RegistryTotal": claims["RegistryTotal"],
        "RegistryCertified": claims["RegistryCertified"],
        "RegistryValidated": claims["RegistryValidated"],
        "RegistryApiStable": claims["RegistryApiStable"],
        "RegistryExperimental": claims["RegistryExperimental"],
        "SchemaParameterTotal": claims["SchemaParameterTotal"],
        "RModules": str(repro["r_reproduced_modules"]),
        "StataModules": str(repro["stata_reproduced_modules"]),
        "Tier1Steps": _tier1(),
        "PageCount": str(pages),
        "ArchiveMiB": f"{package['size_mib']:.2f}",
        "ArchiveMB": f"{package['size_mb_decimal']:.2f}",
        "ArchiveFiles": f"{package['file_count']:,}",
        # The map's card and route sets are fixed by the map itself; whether
        # every card passes is re-derived by verify_submission_package from
        # the final archive. Counting only passing cards here fed a failed
        # previous run's zero back into the letter, whose check then failed
        # the map: a loop the expected identity sets break.
        "EvidenceCards": str(len(evidence["expected_card_ids"])),
        "ReviewRoutes": str(len(evidence["expected_route_ids"])),
        "PackagedDatasetCsv": str(categories.get("packaged_public_dataset_csv", 0)),
        "OriginalExtractCsv": str(categories.get("public_original_extract_csv", 0)),
        "SameByteFixtureCsv": str(categories.get("same_byte_r_stata_fixture_csv", 0)),
        "ReferenceFixtureCsv": str(categories.get("reference_fixture_csv", 0)),
    }
    # The letter states these as zero / PASS. The authoritative gates are
    # downstream (jss_full_audit and verify_submission_package re-derive
    # them from the final archive); the letter is rendered mid-pipeline,
    # when these JSONs may still be the previous run's, so only warn here.
    for key in ("forbidden_raw_member_count", "high_risk_path_hit_count"):
        if data.get(key):
            print(f"WARN -- data_provenance_audit reports {key}={data[key]}")
    if _json(DATA_PROVENANCE).get("unknown_category_paths"):
        print("WARN -- data_provenance_audit reports unknown categories")
    if evidence.get("failed_cards"):
        print("WARN -- reviewer_evidence_map has failed cards")
    return fields


def render() -> str:
    fields = _fields()
    template = TEMPLATE.read_text(encoding="utf-8")
    missing = sorted(set(_FIELD.findall(template)) - set(fields))
    if missing:
        raise SystemExit(f"FAIL -- template fields without a source: {missing}")
    return _FIELD.sub(lambda m: fields[m.group(1)], template)


def _sync_size_disclosures() -> list[Path]:
    """Rewrite the archive-size phrase in the other disclosing documents."""
    package = _json(PACKAGE_MANIFEST)
    changed = []
    for doc in SIZE_DISCLOSURE_DOCS:
        text = doc.read_text(encoding="utf-8")
        new = _SIZE_PHRASE.sub(
            lambda m: (
                f"{package['size_mib']:.2f} MiB ({package['size_mb_decimal']:.2f} MB decimal)"
                f"{m.group('mid')}{package['file_count']:,} files"
            ),
            text,
        )
        if new != text:
            doc.write_text(new, encoding="utf-8")
            changed.append(doc)
    return changed


#: The data-provenance counts those documents quote, keyed by the summary
#: field of data_provenance_audit.json that owns each number.
_PROVENANCE_PHRASES = (
    ("scoped_data_file_count", "scoped data/result files"),
    ("csv_file_count", "CSV files"),
    ("packaged_public_dataset_csv_count", "packaged public dataset CSVs"),
    ("public_original_extract_csv_count", "public original-data extract CSVs"),
    ("same_byte_r_stata_fixture_csv_count", "same-byte R/Stata fixture CSVs"),
    ("reference_fixture_csv_count", "reference fixture CSVs"),
)


def _sync_provenance_counts() -> list[Path]:
    """Rewrite the data-provenance counts in the disclosing documents."""
    summary = _json(DATA_PROVENANCE)["summary"]
    changed = []
    for doc in SIZE_DISCLOSURE_DOCS:
        text = doc.read_text(encoding="utf-8")
        new = text
        for key, phrase in _PROVENANCE_PHRASES:
            new = re.sub(
                rf"\b\d{{1,3}}(?:,\d{{3}})*(?= {re.escape(phrase)})",
                f"{summary[key]:,}",
                new,
            )
        if new != text:
            doc.write_text(new, encoding="utf-8")
            changed.append(doc)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true",
                      help="fail if cover-letter.md differs from a fresh render")
    mode.add_argument("--sync", action="store_true",
                      help="render and repackage until the archive size is stable")
    args = parser.parse_args()

    if withheld_editor_doc("Paper-JSS/cover-letter.template.md"):
        print("SKIP -- public snapshot: the cover letter is withheld")
        return 0

    if args.check:
        actual = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if actual != render():
            print("FAIL -- cover-letter.md is stale; run `make cover-letter`")
            return 1
        print("OK -- cover-letter.md matches the generated artifacts")
        return 0

    if not args.sync:
        OUTPUT.write_text(render(), encoding="utf-8")
        print(f"OK -- wrote {OUTPUT.relative_to(PAPER_ROOT)}")
        return 0

    # Package, then bring every archive member that states the archive's
    # own size or file count up to date with that package, and repeat until
    # a whole round changes nothing: then the last archive built is the one
    # those members describe. The evidence map and editor checklist record
    # the size too, so they are regenerated inside the loop (their pass /
    # fail status is the full audit's business, not this loop's).
    for _ in range(5):
        subprocess.run([sys.executable, str(PACKAGER)], check=True, cwd=PAPER_ROOT)
        changed = _sync_size_disclosures()
        changed += [d for d in _sync_provenance_counts() if d not in changed]
        expected = render()
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if expected != current:
            OUTPUT.write_text(expected, encoding="utf-8")
            changed.append(OUTPUT)
        for script, report in SIZE_DEPENDENT_REPORTS:
            if not report.exists():
                continue
            before = report.read_bytes()
            subprocess.run([sys.executable, str(script)], check=False, cwd=PAPER_ROOT,
                           stdout=subprocess.DEVNULL)
            if report.read_bytes() != before:
                changed.append(report)
        if not changed:
            print("OK -- cover letter, size disclosures and archive agree")
            return 0
        names = ", ".join(p.relative_to(PAPER_ROOT).as_posix() for p in changed)
        print(f"OK -- updated {names}; repackaging")
    print("FAIL -- archive size did not stabilise after 5 rounds")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

# JSS Bibliography Metadata Audit

Status: PASS
Active TeX inputs: 23
Active cited keys: 102
Submission bibliography entries: 103
Reserved entries: 1 (brown2020language)
Archival bibliography entries: 59
Entries with DOI: 86
Entries with URL field: 16
Entries with DOI/URL/ISBN/eprint/howpublished locator: 101
No-DOI entries with manual reasons: 17/17
Compiled main.bbl bibitems: 102 (thebibliography=102)

## Checks

| Requirement | Status | Evidence |
|---|---:|---|
| active manuscript citations resolve inside jss-bib.bib | PASS | missing=[] |
| submission bibliography has no duplicate keys | PASS | duplicates=[] |
| reserved bibliography keys are explicit and stable | PASS | reserved=['brown2020language']; expected=['brown2020language'] |
| active citations are not archival-only | PASS | active_archival_only=[] |
| submission bibliography entries keep required fields | PASS | field_failures=[] |
| no-DOI entries have manual verification reasons | PASS | missing_reasons=[]; stale_reasons=[] |
| compiled bibliography count matches active citations when main.bbl exists | PASS | bbl_present=True; bibitems=102; active_citations=102 |

## No-DOI Entries

| Key | Scope | Locator | Manual verification reason |
|---|---|---:|---|
| `bach2022doubleml` | active | yes | JMLR software paper; URL to the official JMLR article page is present, and no DOI is recorded in the submission bibliography. |
| `berge2018efficient` | active | yes | CREA discussion paper for the fixest implementation lineage; URL to the institution-hosted PDF is present, and no DOI is recorded. |
| `brown2020language` | reserved | yes | NeurIPS 2020 proceedings paper; the proceedings carry no DOI, so the entry records the official proceedings URL plus the arXiv eprint (2005.14165) rather than attaching the preprint's DOI to the venue record. |
| `card1995using` | active | yes | Book-chapter citation; booktitle, editors, publisher, pages, and year are present, and no DOI is expected. |
| `correia2017linear` | active | no | Author-hosted working paper behind the reghdfe command; URL to the author's PDF is present, and no DOI is registered. |
| `econml` | active | yes | Software repository citation; URL is rendered from the howpublished field rather than a DOI. |
| `hernan2020causal` | active | yes | Book with no Crossref DOI (StatsPAI master annote, searched 2026-08-24). Authors, title, publisher, place and year follow the authors' own citation line at miguelhernan.org/whatifbook; the ISBN is listed for this title and first author at isbnsearch.org (both read 2026-11-16). |
| `lalonde1986evaluating` | active | no | American Economic Review 1986 article from the pre-routine-DOI era; journal, volume, issue, pages, and year are present, and no DOI is fabricated. |
| `mcp2026specification` | active | yes | Web specification, revision 2026-07-28; URL and access date are rendered, verified 2026-11-02 against the specification site. |
| `nicholls2020riskbased` | active | yes | R Validation Hub white paper with no DOI, verified 2026-11-02 against the dated PDF and the project's white-paper page. |
| `pedregosa2011scikit` | active | yes | JMLR article; JMLR registers no DOIs, so the entry carries the official JMLR article URL, verified 2026-09-05 against the JMLR page and the arXiv record 1201.0490 (title, authors, journal_ref). |
| `pyfixest2025pyfixest` | active | yes | Python package citation in the form its own CITATION.cff requests; the repository URL is present, and the package registers no DOI. |
| `pymclabs2026causalpy` | active | yes | Software with no DOI yet (its README says one is planned), verified 2026-11-02 against the README and the 0.9.0 wheel metadata. |
| `rcoreteam2025r` | active | yes | The citation R itself prints from citation(); organization, address, version, and project URL are present, and R registers no DOI. |
| `rios2022csdid` | active | yes | Reserved software documentation citation; URL and access date are rendered from howpublished/note fields. |
| `statacorp2023stata` | active | yes | Software citation in the form StataCorp's citing FAQ prescribes; publisher, address, and URL are present, and no DOI exists. |
| `vanrossum2009python` | active | yes | Printed reference manual; publisher, address, year, and ISBN are present. ACM lists it under its non-resolving 10.5555 prefix, so no DOI is attached. |

Failures: none

Machine-readable detail: `replication/results/bibliography_metadata_audit.json`

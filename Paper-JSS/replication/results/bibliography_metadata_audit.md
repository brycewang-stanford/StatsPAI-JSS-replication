# JSS Bibliography Metadata Audit

Status: PASS
Active TeX inputs: 20
Active cited keys: 72
Submission bibliography entries: 73
Reserved entries: 1 (brown2020language)
Archival bibliography entries: 59
Entries with DOI: 60
Entries with URL field: 5
Entries with DOI/URL/ISBN/eprint/howpublished locator: 71
No-DOI entries with manual reasons: 13/13
Compiled main.bbl bibitems: 72 (thebibliography=72)

## Checks

| Requirement | Status | Evidence |
|---|---:|---|
| active manuscript citations resolve inside jss-bib.bib | PASS | missing=[] |
| submission bibliography has no duplicate keys | PASS | duplicates=[] |
| reserved bibliography keys are explicit and stable | PASS | reserved=['brown2020language']; expected=['brown2020language'] |
| active citations are not archival-only | PASS | active_archival_only=[] |
| submission bibliography entries keep required fields | PASS | field_failures=[] |
| no-DOI entries have manual verification reasons | PASS | missing_reasons=[]; stale_reasons=[] |
| compiled bibliography count matches active citations when main.bbl exists | PASS | bbl_present=True; bibitems=72; active_citations=72 |

## No-DOI Entries

| Key | Scope | Locator | Manual verification reason |
|---|---|---:|---|
| `anthropic2024mcp` | active | yes | Software/web specification citation; URL and access date are rendered from howpublished/note fields. |
| `bach2022doubleml` | active | yes | JMLR software paper; URL to the official JMLR article page is present, and no DOI is recorded in the submission bibliography. |
| `berge2018efficient` | active | no | CREA discussion paper for the fixest implementation lineage; URL to the institution-hosted PDF is present, and no DOI is recorded. |
| `brown2020language` | reserved | yes | NeurIPS 2020 proceedings paper; the proceedings carry no DOI, so the entry records the official proceedings URL plus the arXiv eprint (2005.14165) rather than attaching the preprint's DOI to the venue record. |
| `card1995using` | active | yes | Book-chapter citation; booktitle, editors, publisher, pages, and year are present, and no DOI is expected. |
| `chen2025efficient` | active | yes | arXiv preprint (2506.17729) with no journal publication as of verification; the eprint field is the identifier and the note says so. |
| `econml` | active | yes | Software repository citation; URL is rendered from the howpublished field rather than a DOI. |
| `ghanem2026selection` | active | yes | arXiv preprint (2203.09001, v15 dated 2026-07-24) with no journal publication as of verification; the eprint field is the identifier. |
| `lalonde1986evaluating` | active | no | American Economic Review 1986 article from the pre-routine-DOI era; journal, volume, issue, pages, and year are present, and no DOI is fabricated. |
| `liang2023helm` | active | yes | Transactions on Machine Learning Research article; TMLR issues no DOI, so the entry carries the arXiv eprint (2211.09110) whose journal_ref names the TMLR publication. |
| `patil2023gorilla` | active | yes | arXiv preprint (2305.15334) cited as such; the eprint field is the identifier and no DOI is fabricated. |
| `pedregosa2011scikit` | active | yes | JMLR article; JMLR registers no DOIs, so the entry carries the official JMLR article URL, verified 2026-09-05 against the JMLR page and the arXiv record 1201.0490 (title, authors, journal_ref). |
| `rios2022csdid` | active | yes | Reserved software documentation citation; URL and access date are rendered from howpublished/note fields. |

Failures: none

Machine-readable detail: `replication/results/bibliography_metadata_audit.json`

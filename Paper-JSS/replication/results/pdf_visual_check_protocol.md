# PDF Visual Check Protocol

Status: PASS

Protocol for the final full-document human visual spot-check before JSS upload; not a completed acceptance record.
This generated file does not certify that a human visual review has already been completed.

## Boundary

- Main PDF: `manuscript/main.pdf`
- PDF render audit: `replication/results/pdf_render_audit.json`
- Expected archive: `build/statspai-jss-submission.zip`
- Expected archive manifest: `build/statspai-jss-submission-manifest.md`
- Packaged PDF member: `Paper-JSS/manuscript/main.pdf`
- PDF pages: `54`
- Sampled pages from machine render audit: `1, 2, 27, 54`
- Manual visual check status: `PENDING_MANUAL_REVIEW`
- Full-document machine scan pages: `54`
- Full-document machine scan failures: `0`
- Full-document machine scan is not human review: `True`
- Claimed manual acceptance: `False`
- Recorded by this protocol: `False`
- Manual action required before upload: `True`
- Machine render is not human review: `True`
- JSS upload blocking: `False`

## Checklist

| Item | Action | Record |
|---|---|---|
| `open_packaged_pdf` | Open the packaged manuscript/main.pdf from the final JSS submission archive, not a stale working-tree copy. | viewer, archive filename, and archive timestamp |
| `page_count_matches_audits` | Confirm that the viewer reports 54 pages and that the count matches pdf_render_audit and jss_full_audit. | observed page count |
| `archive_manifest_crosscheck` | Before accepting the visual review, confirm that the PDF was opened from `Paper-JSS/manuscript/main.pdf` after extracting `build/statspai-jss-submission.zip`, then compare the archive size and file count with `build/statspai-jss-submission-manifest.md` or the final verifier output. | archive size, file count, PDF member path, and manifest/verifier source |
| `use_page_inventory` | Use the generated page inventory below to jump to front matter, section starts, tables, figures, references, and boundary-text pages before the full page-by-page scan. | pages checked from inventory plus any mismatch |
| `all_pages_nonblank` | Inspect pages 1 through 54 for blank pages, missing content, or unexpected dark/empty pages. | first failing page if any |
| `front_matter_and_metadata` | Check title, authors, affiliations, abstract, keywords, date, JSS class styling, and page headers. | front-matter issues if any |
| `text_and_equation_layout` | Scan every page for clipped text, overlapping lines, broken equations, unreadable code font, or orphaned headings. | page and object for each issue |
| `tables_figures_captions` | Check that all tables, figures, captions, and legends are readable and not split or clipped in a way that blocks review. | table or figure label for each issue |
| `links_references_citations` | Spot-check references, citations, URLs, and internal links for visible rendering and unresolved-marker drift. | marker, citation, or URL issue if any |
| `boundary_text_visible` | Confirm that validation-tier, source-snapshot, data-provenance, agent-claim, and final manual PDF visual-check boundary wording is visible. | missing boundary wording if any |
| `compare_machine_samples` | Compare the first, second, middle, and last pages against the Poppler sample pages named in pdf_render_audit. | sample-page mismatch if any |
| `record_human_acceptance` | After all checks pass, record reviewer name, date, viewer, archive name, and any accepted residual visual issue in the upload worklog. Do not change this generated protocol to claim acceptance unless the human review is actually done. | human reviewer/date in upload worklog |

## Page Inventory

| Page | Text chars | Section markers | Float markers | Boundary markers |
|---:|---:|---|---|---|
| 1 | 2221 | front_matter, introduction | -- | validation_tier |
| 2 | 4094 | -- | Figure 3 | -- |
| 3 | 3210 | -- | Listing 1 | -- |
| 4 | 3627 | -- | Figure 4, Table 1 | -- |
| 5 | 3222 | software_architecture | -- | validation_tier |
| 6 | 2991 | -- | Listing 2 | validation_tier |
| 7 | 2997 | agent_registry_api | -- | -- |
| 8 | 3234 | -- | -- | -- |
| 9 | 3151 | worked_examples | Table 2 | -- |
| 10 | 2457 | -- | Listing 1, Listing 3, Table 9 | -- |
| 11 | 3406 | -- | Listing 1, Listing 4, Table 3, Table 8, Table 9 | -- |
| 12 | 2040 | -- | Figure 1, Listing 5, Table 3, Table 9 | -- |
| 13 | 2741 | -- | Listing 5, Listing 6 | -- |
| 14 | 3790 | -- | Figure 2, Listing 5, Table 18, Table 9 | -- |
| 15 | 2051 | -- | Figure 2 | -- |
| 16 | 3266 | -- | Listing 7 | -- |
| 17 | 3362 | validation_evidence | Table 4 | -- |
| 18 | 3395 | -- | Figure 3 | -- |
| 19 | 3117 | -- | Table 5, Table 6 | -- |
| 20 | 2886 | -- | Table 6, Table 9 | -- |
| 21 | 2883 | -- | Table 7, Table 8, Table 9 | -- |
| 22 | 3052 | -- | Table 8, Table 9 | -- |
| 23 | 3604 | -- | Table 9 | -- |
| 24 | 3419 | -- | Listing 8, Table 9 | -- |
| 25 | 3836 | -- | Listing 3, Table 10, Table 5 | -- |
| 26 | 3245 | -- | Table 10, Table 3 | -- |
| 27 | 4125 | -- | Table 11 | -- |
| 28 | 3709 | -- | Table 12 | -- |
| 29 | 3174 | -- | Table 11 | -- |
| 30 | 3402 | -- | Table 12, Table 18 | -- |
| 31 | 3402 | performance | Table 16, Table 6 | source_snapshot |
| 32 | 3246 | -- | Figure 4, Table 13 | -- |
| 33 | 3093 | -- | Table 13 | -- |
| 34 | 1930 | agent_interface_checks | Figure 4, Table 13, Table 14 | -- |
| 35 | 3096 | -- | Table 14 | -- |
| 36 | 3003 | computational_details | Table 15 | agent_claim_boundary |
| 37 | 3592 | -- | Table 16 | -- |
| 38 | 3039 | discussion | Table 16 | -- |
| 39 | 4207 | -- | Table 18 | -- |
| 40 | 2423 | references | -- | agent_claim_boundary |
| 41 | 2754 | -- | -- | -- |
| 42 | 2662 | -- | -- | -- |
| 43 | 2682 | -- | -- | -- |
| 44 | 2894 | -- | -- | -- |
| 45 | 2672 | -- | -- | -- |
| 46 | 2551 | -- | Table 17, Table 8 | -- |
| 47 | 2021 | -- | Table 17 | -- |
| 48 | 2308 | -- | Table 17 | -- |
| 49 | 2275 | -- | Table 17 | -- |
| 50 | 2111 | -- | Table 17 | -- |
| 51 | 2195 | -- | Table 17 | -- |
| 52 | 3251 | -- | Table 10, Table 17, Table 18 | -- |
| 53 | 4326 | -- | Listing 6, Table 18 | -- |
| 54 | 795 | -- | -- | -- |

## Metrics

- `page_count`: `54`
- `sampled_pages`: `[1, 2, 27, 54]`
- `checklist_item_count`: `12`
- `pdf_render_status`: `PASS`
- `pdf_render_failure_count`: `0`
- `full_document_machine_scan_pages`: `54`
- `full_document_machine_scan_failures`: `0`
- `full_document_machine_scan_not_human_review`: `True`
- `page_inventory_count`: `54`
- `page_inventory_text_pages`: `54`
- `page_inventory_min_text_chars`: `795`
- `page_inventory_section_markers`: `['agent_interface_checks', 'agent_registry_api', 'computational_details', 'discussion', 'front_matter', 'introduction', 'performance', 'references', 'software_architecture', 'validation_evidence', 'worked_examples']`
- `page_inventory_float_marker_count`: `75`
- `manual_visual_check_required`: `True`
- `manual_visual_check_status`: `PENDING_MANUAL_REVIEW`
- `claimed_manual_acceptance`: `False`
- `recorded_by_this_protocol`: `False`
- `manual_action_required_before_upload`: `True`
- `machine_render_not_human_review`: `True`
- `jss_upload_blocking`: `False`
- `archive_name`: `build/statspai-jss-submission.zip`
- `archive_manifest`: `build/statspai-jss-submission-manifest.md`
- `packaged_pdf_member`: `Paper-JSS/manuscript/main.pdf`
- `scope`: `Protocol for the final full-document human visual spot-check before JSS upload; not a completed acceptance record.`

Failures: none

Machine-readable detail: `replication/results/pdf_visual_check_protocol.json`

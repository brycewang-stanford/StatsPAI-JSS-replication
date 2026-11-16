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
- PDF pages: `48`
- Sampled pages from machine render audit: `1, 2, 24, 48`
- Manual visual check status: `PENDING_MANUAL_REVIEW`
- Full-document machine scan pages: `48`
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
| `page_count_matches_audits` | Confirm that the viewer reports 48 pages and that the count matches pdf_render_audit and jss_full_audit. | observed page count |
| `archive_manifest_crosscheck` | Before accepting the visual review, confirm that the PDF was opened from `Paper-JSS/manuscript/main.pdf` after extracting `build/statspai-jss-submission.zip`, then compare the archive size and file count with `build/statspai-jss-submission-manifest.md` or the final verifier output. | archive size, file count, PDF member path, and manifest/verifier source |
| `use_page_inventory` | Use the generated page inventory below to jump to front matter, section starts, tables, figures, references, and boundary-text pages before the full page-by-page scan. | pages checked from inventory plus any mismatch |
| `all_pages_nonblank` | Inspect pages 1 through 48 for blank pages, missing content, or unexpected dark/empty pages. | first failing page if any |
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
| 1 | 2025 | front_matter | -- | validation_tier |
| 2 | 4040 | introduction | Figure 3 | -- |
| 3 | 3122 | -- | Listing 1 | -- |
| 4 | 3500 | -- | Table 1 | -- |
| 5 | 2813 | software_architecture | Listing 2 | validation_tier |
| 6 | 3220 | -- | Listing 2 | validation_tier |
| 7 | 2659 | agent_registry_api | Listing 3 | -- |
| 8 | 3366 | agent_interface_checks | Table 2 | -- |
| 9 | 2251 | -- | Table 2, Table 3 | agent_claim_boundary |
| 10 | 2812 | worked_examples | Table 4 | -- |
| 11 | 2343 | -- | Listing 1, Listing 4, Table 11 | -- |
| 12 | 2587 | -- | Figure 1, Listing 1, Listing 5, Listing 6, Table 5 | -- |
| 13 | 2473 | -- | Listing 6, Listing 7, Table 11, Table 5 | -- |
| 14 | 2247 | -- | Figure 1, Listing 6, Table 11, Table 5, Table 6 | -- |
| 15 | 3246 | -- | Figure 2, Listing 7, Listing 8, Table 19 | -- |
| 16 | 1458 | -- | Figure 2, Listing 7, Listing 8 | -- |
| 17 | 3224 | -- | Listing 9 | -- |
| 18 | 2736 | -- | Listing 10, Table 7 | -- |
| 19 | 3711 | validation_evidence | Figure 3, Table 7, Table 8, Table 9 | -- |
| 20 | 3025 | -- | Figure 3, Table 9 | -- |
| 21 | 2537 | -- | Table 11, Table 8, Table 9 | -- |
| 22 | 3156 | -- | Table 10, Table 11 | -- |
| 23 | 3531 | -- | Table 11 | -- |
| 24 | 3529 | -- | Listing 11, Table 5 | -- |
| 25 | 3878 | -- | Listing 4, Table 12, Table 5 | -- |
| 26 | 3626 | -- | Table 12, Table 14 | -- |
| 27 | 3805 | -- | Table 13, Table 14, Table 19 | -- |
| 28 | 2368 | -- | Table 14, Table 15 | -- |
| 29 | 3183 | -- | Table 15 | -- |
| 30 | 3681 | -- | Table 19 | -- |
| 31 | 3398 | performance | -- | -- |
| 32 | 3181 | -- | Figure 4, Table 16 | -- |
| 33 | 2984 | computational_details | Table 16 | -- |
| 34 | 2119 | -- | Figure 4, Table 16 | -- |
| 35 | 3729 | -- | Table 17 | -- |
| 36 | 3270 | discussion | Table 17 | -- |
| 37 | 2573 | -- | -- | agent_claim_boundary |
| 38 | 2571 | references | -- | -- |
| 39 | 2621 | -- | -- | -- |
| 40 | 2828 | -- | -- | -- |
| 41 | 2546 | -- | -- | -- |
| 42 | 2976 | -- | -- | -- |
| 43 | 2691 | -- | -- | -- |
| 44 | 2645 | -- | -- | -- |
| 45 | 2916 | -- | Table 18 | -- |
| 46 | 3538 | -- | Table 18 | -- |
| 47 | 3953 | -- | Table 18, Table 19 | -- |
| 48 | 3326 | -- | Table 19 | -- |

## Metrics

- `page_count`: `48`
- `sampled_pages`: `[1, 2, 24, 48]`
- `checklist_item_count`: `12`
- `pdf_render_status`: `PASS`
- `pdf_render_failure_count`: `0`
- `full_document_machine_scan_pages`: `48`
- `full_document_machine_scan_failures`: `0`
- `full_document_machine_scan_not_human_review`: `True`
- `page_inventory_count`: `48`
- `page_inventory_text_pages`: `48`
- `page_inventory_min_text_chars`: `1458`
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

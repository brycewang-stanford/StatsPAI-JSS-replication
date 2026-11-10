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
| 1 | 2236 | front_matter, introduction | -- | validation_tier |
| 2 | 4107 | -- | Figure 3 | -- |
| 3 | 3118 | -- | Listing 1 | -- |
| 4 | 3199 | -- | Table 1 | -- |
| 5 | 2876 | software_architecture | Listing 2 | validation_tier |
| 6 | 3147 | -- | Listing 2 | validation_tier |
| 7 | 2805 | agent_registry_api | Listing 3 | -- |
| 8 | 3327 | agent_interface_checks | Table 2 | -- |
| 9 | 2340 | worked_examples | Table 2, Table 3, Table 4 | agent_claim_boundary |
| 10 | 2997 | -- | Listing 1, Listing 4, Table 4 | -- |
| 11 | 2440 | -- | Listing 1, Listing 4, Table 11 | -- |
| 12 | 2709 | -- | Figure 1, Listing 1, Listing 5, Listing 6, Table 5 | -- |
| 13 | 1649 | -- | Figure 1, Listing 6, Listing 7, Table 11, Table 5 | -- |
| 14 | 3155 | -- | Listing 7, Table 11, Table 6 | -- |
| 15 | 2824 | -- | Listing 7, Listing 8, Table 19, Table 6 | -- |
| 16 | 1828 | -- | Figure 2, Listing 7, Listing 9 | -- |
| 17 | 2775 | -- | Listing 10, Listing 9 | -- |
| 18 | 2957 | validation_evidence | Listing 10, Table 7 | -- |
| 19 | 3588 | -- | Figure 3, Table 7, Table 8, Table 9 | -- |
| 20 | 3047 | -- | Figure 3 | -- |
| 21 | 2805 | -- | Table 11, Table 8, Table 9 | -- |
| 22 | 3091 | -- | Table 10, Table 11 | -- |
| 23 | 3265 | -- | Table 11 | -- |
| 24 | 3602 | -- | Listing 11, Listing 4, Table 5 | -- |
| 25 | 3652 | -- | Table 12, Table 5 | -- |
| 26 | 3928 | -- | Table 14, Table 5 | -- |
| 27 | 3339 | -- | Table 13, Table 14, Table 15, Table 19 | -- |
| 28 | 2929 | -- | Table 14 | -- |
| 29 | 3281 | -- | Table 15 | -- |
| 30 | 3654 | -- | Table 19 | -- |
| 31 | 3087 | performance | -- | -- |
| 32 | 3278 | -- | Figure 4, Table 16 | -- |
| 33 | 3190 | computational_details | Table 16 | -- |
| 34 | 1895 | -- | Figure 4, Table 16 | -- |
| 35 | 3604 | discussion | Table 17 | -- |
| 36 | 3518 | -- | Table 17 | -- |
| 37 | 2258 | references | -- | agent_claim_boundary |
| 38 | 2624 | -- | -- | -- |
| 39 | 2649 | -- | -- | -- |
| 40 | 2677 | -- | -- | -- |
| 41 | 2654 | -- | -- | -- |
| 42 | 3019 | -- | -- | -- |
| 43 | 2668 | -- | -- | -- |
| 44 | 2731 | -- | -- | -- |
| 45 | 3131 | -- | Table 18 | -- |
| 46 | 3716 | -- | Table 18 | -- |
| 47 | 4280 | -- | Table 19 | -- |
| 48 | 1917 | -- | Table 19 | -- |

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
- `page_inventory_min_text_chars`: `1649`
- `page_inventory_section_markers`: `['agent_interface_checks', 'agent_registry_api', 'computational_details', 'discussion', 'front_matter', 'introduction', 'performance', 'references', 'software_architecture', 'validation_evidence', 'worked_examples']`
- `page_inventory_float_marker_count`: `76`
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

# Manuscript listings execution audit

Every `lstlisting` block compiled into `main.tex` is executed
verbatim against the live package (REPL transcripts are replayed
line by line; quoted output values are pinned by assertions).

| Section | Listing | Status | Time (s) |
|---|---|---|---:|
| 01-introduction-compact.tex | `lst:motivating` | PASS | 0.0 |
| 02-architecture-compact.tex | `lst:validation-tier-output` | PASS | 0.0 |
| 04-examples-compact.tex | `lst:card-output` | PASS | 0.0 |
| 04-examples-compact.tex | `lst:card-cate` | PASS | 0.0 |
| 04-examples-compact.tex | `lst:csdid` | PASS | 0.0 |
| 04-examples-compact.tex | `lst:csdid-output` | PASS | 0.0 |
| 04-examples-compact.tex | `lst:fect` | PASS | 0.0 |

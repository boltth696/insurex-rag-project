# Accuracy review — 2026-10-03

The latest verification passed **287 local tests** and **126 targeted live checks across runs and scenario retests**: 50 customer turns, 25 factual questions, 29 stress turns, 11 budget-frequency/negation checks, five payment-wording checks and six entry-age checks. This establishes behavior for these examples, not perfect accuracy for all future wording. The existing `gpt-4.1-mini` model and FAISS index remain in use.

## Fixes

- Segment wording such as poor, frugal, medium mass and high mass cannot substitute for stated age, budget and goal. Unqualified protection prompts clarification among death benefits, illness cash and medical bills.
- Human-supported profile facts persist across follow-ups. Invalid newer quotations cannot erase verified older details. Explicit budget corrections and loss of existing cover override stale extraction. Family-event questions retain age, budget and requested payout while clarifying death versus disability/illness.
- A different customer establishes a persistent boundary. Names, corrections and negated switches cannot silently reset a customer. Numeric quotations cannot borrow digits from larger amounts.
- Detailed rider, entry-age and minimum-sum questions bypass the catalog shortcut. Rewriting preserves named products. Complete matching pages are retrieved; named comparisons retry missing citations, including partial answers with evidence limitations.
- Reviewed notes now cover all five brochures. Premium examples preserve the requested plan, sum insured, age, sex and annual-payment row. Savings answers provide requested amounts. Cancer payouts, early-benefit deductions, waiver, termination and rider limitations stay separate.
- Manual review found a deductible exception inversion that passed fragment checks. The final health deductible-scope answer now uses reviewed structured facts: benefit 2.2's exception applies to minor surgery only. The corrected result replaces the earlier answer in the summary.
- Conflicting pension figures are disclosed rather than silently resolved.
- Lead drafts survive factual interruptions. Income is distinguished from premium budget, newer corrections prevail, invalid phones are rejected, and success is reported only after SQLite confirms a save. Negated cancellation does not terminate collection.
- SQLite connections close immediately. Local session/lead commands avoid importing API/native retrieval libraries. The CLI supports separate test storage with `--storage-dir`.
- PDF parsing is isolated in a disposable process with one bounded crash retry. A remaining failure reports an error and does not index an empty result. FAISS checks source hashes so an old index cannot silently answer from changed PDFs.
- Budget amounts without monthly/yearly frequency prompt clarification. English spelled payment periods and coordinated lists are interpreted without borrowing the customer's age as a payment term.
- Published entry-age limits filter recommendations and plan variants, independently of coverage-ending ages. The health rider starts at age 11; the pension and CI variants have separate limits. Numerical and English spelled ages are checked; unknown ages and ranges do not establish eligibility. Rider terms and underwriting acceptance remain separate.
- Graph nodes use a small Runnable wrapper to avoid unnecessary automatic closure-bytecode inspection. Configuration still reaches the lead tool; checkpoint and graph tests pass.

## Results and traceability

| Suite | Latest results | Evidence |
|---|---:|---|
| Full local regressions | 287/287 | `tests/`; final run included real PDF evidence audit |
| Customer variations | 50/50 across final run and scenario retests | `variations-expanded-release.json`, `variations-expanded-last-fixes.json`, `variations-expanded-confirmation.json`, `variations-flat-nodes.json`, `variations-final-profile-confirmation.json` |
| Factual questions | 25/25 after manual wording review and deductible correction | `variations-factual-release.json`, `variations-deductible-final.json` |
| Stress conversations | 29/29 | `variations-stress-release.json` |
| Budget frequency and negation | 11/11 | `variations-frequency-initial.json` |
| Payment wording | 5/5 | `variations-payment-wording-final.json` |
| Entry-age boundaries | 6/6 | `variations-entry-age-final.json` |

`final-test-summary.json` identifies the source result file for every latest check. Earlier failures remain in their original result files. Equivalent wording such as “greatest” was accepted only after inspecting the actual reply; generated answers were not rewritten. Passing fragment checks alone is insufficient, as the corrected deductible inversion demonstrates.

Live evaluations used approved brochure pages and synthetic profiles through OpenAI, with temporary session memory and temporary lead databases. No real saved customer records were read or sent for these evaluations. Earlier offline CLI regression versions wrote their own `catalog-regression` demonstration session to the default session database; the regression now uses temporary separate storage. Existing customer records were not deleted to clean up demonstration data.

## Remaining limits

The Windows Python process still intermittently suffers native access violations. They appeared in PDF extraction, graph/import code, pytest collection and retrieved page preparation. The final full 287-test run passed, but the immediately preceding run crashed in `page_evidence`. The underlying runtime cause is unresolved. PDF isolation contains the parser failure path. The graph-node wrapper passed two 3,000-iteration construction probes, including one with FAISS, but a later fault demonstrates that it is not a general interpreter fix. Alternate project-local environments were tested and are not selected for normal use.

Brochures do not supply complete policy/rider conditions or personalized quotes for every customer, and some pages conflict. The chatbot must disclose missing evidence, require matching quotes for budget fit and avoid guaranteeing acceptance. Citation checks establish source coverage, not truth of every generated statement.

Bonus Task 1 implements the LangChain **Tooling** path using Pydantic and SQLite. An MCP server, external CRM and authenticated multi-user web service are not implemented. CLI session IDs separate local conversations; they are not authentication.

## Restart

At the chatbot's `You:` prompt, type `/exit`. In the project PowerShell terminal, start a fresh test conversation:

```powershell
.\.venv\Scripts\python.exe -m insurex.cli chat --session accuracy-final-001
```

Reuse an existing session ID to restore its history. Opening `.env` does not start or restart chat. No re-ingestion is required for this update.

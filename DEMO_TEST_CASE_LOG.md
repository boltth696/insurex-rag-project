# Submission demo and test-case log

Review date: **2026-10-04 (Asia/Bangkok)**. All customer data in these logs is synthetic. Existing customer databases were not read, modified or packaged.

## Objective and requirement coverage

The system supports sales staff with grounded brochure answers and systematic lead collection. The original assessment's Test Case 2 and its two bonus tasks are covered as follows:

| Requirement | Implementation | Verification evidence |
|---|---|---|
| LangChain framework | Model, document, embedding and StructuredTool components | `insurex/graph.py`, `vectorstore.py`, `leads.py`; local regressions |
| LangGraph workflow/state | Routing, retrieval, answer, recommendation and lead nodes; persisted AgentState | Executed node names in [actual online log](submission-demo.md); [workflow](workflow.md) |
| FAISS vector database | Persisted vector index with JSON docstore and source manifest | Index round-trip/source mismatch tests; `release-validation.json` |
| Answers from all five PDFs | Reviewed catalog, relevant page reconstruction, cited source answers | Online log entries 1–2 and 9, 21–24; PDF/catalog audits |
| Missing-answer/error handling | Evidence limitations, bounded repair and explicit fallback paths | Nonexistent-product entry 25; retrieval/model/invalid-citation regression tests |
| Bonus 1: interest mode | Explicit product interest triggers collection; missing-field requests | Entries 6–7, 15–16 and 18–19 |
| Bonus 1: structured data | Pydantic name, occupation, income, phone and evidence | Entries 13 and 17 show actual stored JSON |
| Bonus 1: database/tool | LangChain `save_insurance_lead` writes validated SQLite records | Incomplete draft absent at entry 11; complete save at 12–13; cancellation absent at 20 |
| Bonus 2: conversation memory | SQLite checkpoint restored before subsequent processing | Entry 8 reads the unfinished draft in an independent Python process; entry 9 continues after recreating the agent |
| Bonus 2: session separation | Distinct LangGraph thread IDs and customer boundaries | Customer A/B entries 3–5 and 14; separate stored IDs at 26; isolation regression tests |
| Source/dependencies/README | Python source, direct requirements, exact lock and one neutral setup README | Archive manifest and extracted-package smoke check |
| Demo/test log | Actual dialogue, node trace, JSON records and reproducible demo | `run_submission_demo.py`, this log and linked raw results |

Bonus 1 uses the assessment's **Tooling** implementation: a LangChain tool rather than an MCP transport server. The local UI is not an authenticated public service.

## Recorded results

| Check | Result | Record |
|---|---:|---|
| Final local regression suite | **305 passed, 0 failed** | [release-validation.json](release-validation.json) |
| Final online synthetic demo | **26/26 reviewed checks** | [submission-demo.md](submission-demo.md), [raw JSON](submission-demo.json) |
| Offline catalog/session demo | **5/5** | [offline-demo.md](offline-demo.md), [raw JSON](offline-demo.json) |
| Dependency consistency | No broken requirements | `release-validation.json` |
| Saved-information browser checks | Search, details, filtered download and matching chat resume passed | [saved-information-checks.json](saved-information-checks.json) |
| Earlier live variations | 126 targeted checks across runs and retests | [final-test-summary.json](final-test-summary.json), [dated review](variation-review.md) |

These are recorded checks, not an official assessment score or a guarantee of future model accuracy. The final regression suite makes no API calls; model stubs test implementation paths, while the online demo uses the configured `gpt-4.1-mini` model with actual brochure evidence.

The actual extracted submission also passed **305 tests** and its offline demo. Its default session and lead stores were empty. A desktop browser check then used isolated synthetic data copied from the recorded demo to verify chat, saved lead fields, filtered JSON download, profile/history viewing and resuming the matching chat, without API calls. Screenshots: [chat](screenshots/chat.png), [saved lead](screenshots/saved-leads.png), [remembered profile/history](screenshots/saved-conversation.png).

## Improvements found during final review

Manual review caught an unsupported CI 50 illness count even though initial fragment checks passed. The final answer explicitly says that complete CI 50 definitions/count are not established by the supplied pages. The implementation now makes one repair attempt and rejects the observed count claim if it persists. The original output is preserved in [submission-demo-before-fix.json](submission-demo-before-fix.json).

A universal pension question now receives a direct explanation rather than only a catalog listing: payment until age 55 depends on the customer's age at entry, and a male-age-45 worked example does not establish ten years for everyone.

The final run's strict checker initially reported 25/26 because it required the literal phrase “entry age.” Its correct answer used “age at entry.” Source review accepted that paraphrase, and the checker was updated to accept either phrase. **No recorded answers were rewritten.** The original strict-checker result remains in [submission-demo-checker-original.json](submission-demo-checker-original.json); the decision is documented in [submission-manual-review.json](submission-manual-review.json).

Setup and usage are consolidated into `README.md`. The catalog heading reads its count from the catalog. Git exclusions and the ZIP allowlist keep API keys, real customer records, virtual environments and development scratch files out of the submission.

## Reproduce the demonstration

Follow the project's README setup first. From the project folder:

```powershell
# No API calls
.\.venv\Scripts\python.exe demo/run_submission_demo.py
# Online structured collection and detailed RAG; uses API credit
.\.venv\Scripts\python.exe demo/run_submission_demo.py --live
# Regression suite with temporary databases; no API calls
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --basetemp work/pytest-demo-001
```

New demo logs go to `work/submission-demo/`. Online runs send synthetic customer messages and relevant supplied brochure pages to OpenAI. Demos create isolated temporary SQLite databases, inspect their saved records, and remove that temporary storage after completion. The packaged transcript contains JSON observations so extraction and persistence can be inspected without distributing a customer database.

## Suggested interactive demonstration

1. Ask `What products are available?` and verify five source-backed product families.
2. Ask the Cheeva/CI Plus critical illness comparison; inspect both source references and the rider limitations.
3. In customer A's conversation give age 22, annual budget 20000 THB and a death-benefit goal.
4. Create customer B's conversation with age 45, budget 60000 THB and a hospital-bill goal. Return to A and ask for their age/budget/goal; B's facts must not appear.
5. Tell A `I am interested in Khum Cheeva.` Supply the synthetic name, occupation and income. Restart the app before supplying the phone, then restore A's conversation.
6. Ask a factual question during collection, then supply the synthetic phone. Inspect the completed JSON under **Saved information → Leads**.
7. Start another collection and use `/cancel-lead`; verify no completed lead was created.

Brochures do not establish personalized premiums or underwriting acceptance for all customers. The final system keeps those limitations explicit rather than claiming unsupported affordability or coverage.

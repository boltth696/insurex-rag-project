# Bonus Task 1: structured lead collection

This implements the Tooling option: a Pydantic extraction schema, explicit LangGraph collection mode, and the LangChain `save_insurance_lead` tool backed by SQLite. No MCP server or external CRM is configured.

## Try it

Restart normal API chat in the project terminal with a new test session:

```powershell
.\.venv\Scripts\python.exe -m insurex.cli chat --session lead-test-001
```

Use fake details for a demonstration:

1. `I am interested in Khum Cheeva.`
2. `My name is Test Customer. I work as a developer. My income is 30000 baht per month.`
3. `My contact number is 0800000000.`

The chatbot should ask only for missing name, occupation, income or contact number. If the product is unclear, it asks which product you mean. Once all fields are verified and the number passes format checks, it saves the record and confirms the local save. This is not an insurance application or coverage approval.

`/cancel-lead` ends collection without saving an incomplete draft. `/exit` closes chat; the same session resumes an unfinished collection after restart. Offline chat does not perform lead extraction. Ordinary benefit/catalog/recommendation questions alone do not establish buying interest. A factual question during collection can use brochure answers while the draft remains available.

To inspect saved structured JSON for that session, without an API call:

```powershell
.\.venv\Scripts\python.exe -m insurex.cli leads --session lead-test-001
```

## Stored fields and evidence

Records contain `lead_id`, `session_id`, `product_id`, `name`, `occupation`, `income`, `contact_number` and an `evidence` dictionary of exact human quotes. SQL columns also hold these fields plus the complete structured JSON and timestamps. The database is `storage/leads.sqlite`; conversational drafts remain in `storage/sessions.sqlite`. The storage directory is ignored by Git.

Income remains the customer's exact text, preserving any stated currency and monthly/yearly period. A premium budget does not become income. Contact numbers retain their original formatting and must contain 8–15 digits; this is format validation, not proof of ownership or ability to receive calls. Unsupported/fabricated field quotes are rejected. Collection uses only human messages from the current interest/collection onward, so another earlier customer's details are not copied into the lead.

The save tool's database path comes from application configuration, not model arguments. Queries are parameterized. A retry with the same lead/session ID updates the existing row rather than duplicating it. The chat confirms saving only after the tool reports success. A cancelled incomplete draft is not written to the lead table, although the CLI's normal conversation history still records messages.

## Verification

Local lead tests use synthetic data and model stubs with temporary databases. They check SQLite save/read, JSON schema, product interest and ordinary questions, field evidence, missing/invalid details, income/budget separation, cancellation, factual interruption, idempotent saves, SQL strings and session scope. An end-to-end test collects details, closes the graph, restores its SQLite checkpoint, and saves after receiving the phone number. The actual online demo also records English/Thai extraction, separate-process draft restoration and database contents; see [submission-demo.md](submission-demo.md).

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_leads.py -q
```

These tests establish implementation and persistence behavior, not full MCP protocol support or accuracy for every future message. Live demos make billable OpenAI calls with synthetic messages and relevant brochure pages.

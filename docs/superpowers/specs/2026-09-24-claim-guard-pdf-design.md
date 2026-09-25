# ClaimGuard PDF MVP — design

## Intent and scope

Extend the existing JSON agent with a demonstrable path from a small text-based PDF to the same validated `AgentRequest` and deterministic audit. Keep React, SQLite, tariff rules, and the existing `/agent` contract unchanged. No OCR, arbitrary file execution, model download in CI, or real personal data.

## Public flow

`POST /agent/pdf` accepts multipart fields `file` (PDF) and `prompt` (nonblank text). It returns the existing `AgentResponse`. The PDF branch starts from `feature/agent-core`, not `main`; pushing it runs the existing backend/frontend workflows without merging either branch.

1. `extract_pdf_text(bytes) -> str` uses `pypdf.PdfReader` and only extracts embedded text. Reject empty/invalid, encrypted, oversized, too-many-page, and textless PDFs with a public-safe code. Cap input at 5 MiB, 20 pages, extracted text at 30,000 characters.
2. `InvoiceExtractor(ChatClient).extract(text) -> Factura` asks Ollama for a structured, nullable invoice extraction. Missing fields remain `null`; the model must not fill absent values. Code validates with Pydantic and rejects missing/invalid fields. Required string and numeric values must be traceable to the source text; unsupported normalized formats fail closed rather than being guessed.
3. A small PDF pipeline obtains the text, extracts and validates the invoice, builds `AgentRequest`, then calls the existing `AgentOrchestrator`. It prepends real `pdf_text_extracted` and `invoice_extracted` steps; an extraction error produces `AgentResponse(status="failed")` with a controlled error and no audit result.

The LLM never audits prices or executes business rules. `audit_invoice` remains the only audit tool and uses `backend/auditoria.py`.

## Failure boundaries

Return controlled codes for invalid PDF, encrypted PDF, no embedded text, size/page/text limits, incomplete invoice, invalid invoice values, and Ollama unavailability/timeout/invalid structured JSON. No stack trace, extracted text, prompts, or sensitive values in public errors or logs. `OllamaClient` retains its single corrective retry; there is no extraction-specific retry loop. The API rejects missing upload/form fields with FastAPI's 422; malformed PDF/extraction returns a failed `AgentResponse`.

## Verification

Use hand-generated synthetic PDF fixtures with embedded text and empty pages. Unit-test PDF extraction and invoice extraction with a fake `ChatClient`; integration-test `POST /agent/pdf` through the real extractor, real registry, real audit rules, and a fake Ollama boundary. Cover valid PDF, empty/no-text PDF, incomplete invoice, invalid quantity/price, invented mandatory values, invalid model JSON, and model outage. Run `pytest`, `npm test`, `npm run build`, and YAML checks locally. CI remains mock-only; a separately labeled local smoke test may use the installed Ollama model.

## Dependencies and documentation

Add only `pypdf` and `python-multipart` to backend requirements. Document a multipart `curl` example, text-only limitation, and which tests are mocked versus live. No frontend PDF upload in this phase; the existing UI remains a JSON client.

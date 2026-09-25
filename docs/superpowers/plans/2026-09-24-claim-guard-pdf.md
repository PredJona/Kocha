# ClaimGuard PDF MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Accept a small text-based PDF, extract a validated invoice with Ollama, and run the existing deterministic ClaimGuard agent.

**Architecture:** `POST /agent/pdf` passes uploaded bytes through a pure PDF-text extractor, a structured `InvoiceExtractor`, and the existing `AgentOrchestrator`. Extraction failures return a controlled `AgentResponse`; no OCR, new audit rule, or React PDF UI.

**Tech Stack:** Python 3.12, FastAPI, pypdf 6.19.0, python-multipart 0.0.32, Pydantic 2, Ollama via existing `ChatClient`, Pytest.

**Spec:** `docs/superpowers/specs/2026-09-24-claim-guard-pdf-design.md`

## Global Constraints

- Work only on `feature/pdf-extraction` based on `feature/agent-core`; never push or merge `main`.
- PDFs with embedded text only; no OCR or heavyweight OCR dependencies.
- PDF maximum 5 MiB, 20 pages, 30,000 extracted characters; reject on limit, never silently truncate.
- Reuse `AgentRequest`, `AgentResponse`, `AgentOrchestrator`, `OllamaClient`, and deterministic tools; no audit logic in the extractor.
- Only `pypdf==6.19.0` and `python-multipart==0.0.32` are new runtime packages.
- CI uses fake Ollama; no model pull or local server in GitHub Actions. Test fixtures are synthetic only.
- Model output is always parsed and validated; the existing Ollama client permits at most one corrective retry.
- Keep frontend and Persona 3 business rules unchanged except the minimal FastAPI PDF route.

## Review Focus

1. PDF with header but broken xref must fail with a safe public error, not an exception page (Task 1 test).
2. Scanned/blank PDF must not trigger Ollama; it must report `PDF_NO_TEXT` (Tasks 1 and 3 tests).
3. Candidate with apparently valid but absent invoice identifier must fail source verification, not be audited (Task 2 test).
4. Candidate with valid strings but invented price must fail source verification, not be audited (Task 2 test).
5. `POST /agent/pdf` must carry real extraction steps and a real audit result from the submitted PDF, not fabricated trace entries (Task 3 test).

---

### Task 1: Text-only PDF extractor and synthetic fixture

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/agent/extractors/__init__.py`, `backend/agent/extractors/pdf_extractor.py`, `tests/agent/pdf_fixture.py`, `tests/agent/test_pdf_extractor.py`

**Interfaces:**
- Produces: `extract_pdf_text(pdf_bytes: bytes) -> str`.
- Fails using `AgentExecutionError(code, public_message)` with codes `PDF_INVALID`, `PDF_ENCRYPTED`, `PDF_NO_TEXT`, `PDF_TOO_LARGE`, `PDF_TOO_MANY_PAGES`, `PDF_TEXT_TOO_LONG`.
- Independent of Ollama and DB.

- [ ] **Step 1: Write failing extractor tests and fixture helper.** `make_text_pdf(text: str) -> bytes` builds a one-page synthetic PDF with Helvetica text and correct byte offsets; `make_blank_pdf() -> bytes` uses an empty page. Assert extracted invoice text, no-text error, malformed-header/xref error, non-PDF error, size limit, page limit, and text limit. The tests must call the real extractor, not mock pypdf.
- [ ] **Step 2: Run RED:** `.venv/bin/python -m pytest -q tests/agent/test_pdf_extractor.py`; expected import failure for missing extractor.
- [ ] **Step 3: Pin and install dependencies:** add `pypdf==6.19.0`, `python-multipart==0.0.32` to requirements; install with `.venv/bin/python -m pip install -r backend/requirements.txt`.
- [ ] **Step 4: Implement minimal extractor:** reject non-bytes, empty/non-PDF, oversized, encrypted, >20 pages, no text, >30,000 characters. Use `PdfReader(BytesIO(pdf_bytes))`, `page.extract_text() or ""`, and catch parser/decryption exceptions to emit public-safe codes. Do not log PDF text.
- [ ] **Step 5: Run GREEN and regression:** `.venv/bin/python -m pytest -q tests/agent/test_pdf_extractor.py`, then `.venv/bin/python -m pytest -q`. Both exit 0.
- [ ] **Step 6: Review diff, `git diff --check`, commit:** `feat: extract embedded text from bounded PDFs`.

### Task 2: Structured invoice extraction and source checks

**Files:**
- Create: `backend/agent/extractors/invoice_extractor.py`, `tests/agent/test_invoice_extractor.py`

**Interfaces:**
- Consumes: existing `ChatClient.chat(messages: list[ChatMessage], response_model: type[T]) -> T`, `AgentRequest(invoice=..., prompt=...)`, `AgentExecutionError`.
- Produces: `InvoiceExtractor(client: ChatClient).extract(text: str) -> Factura`.
- Candidate schema: nullable `numero`, `siniestro_id`, `taller`, and nullable list of items with nullable `codigo`, `descripcion`, strict integer `cantidad`, and Decimal-compatible `precio_unitario`.
- Fails with `INVOICE_INCOMPLETE` for missing essential fields, `INVOICE_INVALID` for invalid quantity/price/Pydantic invoice, `INVOICE_UNVERIFIED` when a non-null mandatory string or numeric item value has no representation in the PDF text. Transport/JSON failures retain existing `MODEL_*` codes.

- [ ] **Step 1: Write failing fake-client tests.** Assert valid extraction returns `Factura` with exact fields and `Decimal`; missing header/item fields fail `INVOICE_INCOMPLETE`; `cantidad=0`/`precio_unitario<=0` fail `INVOICE_INVALID`; invented invoice number/item price fail `INVOICE_UNVERIFIED`; model error propagates as safe `AgentExecutionError`. The fake boundary records response schema but no test asserts only the fake's own behavior.
- [ ] **Step 2: Run RED:** `.venv/bin/python -m pytest -q tests/agent/test_invoice_extractor.py`; expected import failure.
- [ ] **Step 3: Implement minimal Pydantic candidate and extractor.** Use a short system prompt: copy data from text, emit null when absent, no assumptions. Verify mandatory string values by normalized, case-folded substring; verify quantities and prices against numeric tokens from source, with decimal comma/dot normalization. Fail closed on unsupported formats. Then call `AgentRequest.model_validate({"invoice": candidate_data, "prompt": "Audita esta factura"})` to reuse strict invoice boundary and return its `invoice`.
- [ ] **Step 4: Run GREEN and regression:** focused test file then `.venv/bin/python -m pytest -q`, both exit 0.
- [ ] **Step 5: Review diff, `git diff --check`, commit:** `feat: validate invoice extraction against PDF text`.

### Task 3: PDF pipeline, route, trace, and documentation

**Files:**
- Create: `backend/agent/pdf_pipeline.py`, `tests/agent/test_pdf_pipeline.py`, `tests/test_agent_pdf_api.py`
- Modify: `backend/agent/schemas.py`, `backend/agent/factory.py`, `backend/main.py`, `README.md`

**Interfaces:**
- Consumes: Task 1 `extract_pdf_text(bytes)`, Task 2 `InvoiceExtractor.extract(text)`, existing `AgentOrchestrator.run(AgentRequest)`.
- Produces: `run_pdf_agent(pdf_bytes: bytes, prompt: str, invoice_extractor: InvoiceExtractor, orchestrator: AgentOrchestrator) -> AgentResponse`; `POST /agent/pdf` multipart `file` and `prompt` returns `AgentResponse`.
- Add `pdf_text_extracted` and `invoice_extracted` to `AgentStep.type` literals. On failure, preserve only steps actually completed, append a failed `error` step and public-safe `AgentError`; never call the orchestrator on extraction failure.

- [ ] **Step 1: Write failing pipeline and API tests.** Use the Task 1 synthetic PDF generator, a fake ChatClient for invoice and decisions, real `ToolRegistry`/database fixture/audit tool, and FastAPI `TestClient`. Assert successful audit result and ordered real trace, blank PDF never calls model, incomplete invoice never calls orchestrator, invalid model JSON returns structured `MODEL_INVALID_RESPONSE`, and missing multipart field is 422 without traceback.
- [ ] **Step 2: Run RED:** `.venv/bin/python -m pytest -q tests/agent/test_pdf_pipeline.py tests/test_agent_pdf_api.py`; expected missing route/module behavior.
- [ ] **Step 3: Implement pipeline and route.** Keep route thin: `UploadFile`+`Form` (requiring python-multipart), read at most 5 MiB + 1, pass to pipeline. Compose extractor with `OllamaClient(AgentSettings.from_env())` in factory. Do not modify `/agent` or React.
- [ ] **Step 4: Update README.** Show `curl -F file=@invoice.pdf -F 'prompt=Audita esta factura' http://127.0.0.1:8000/agent/pdf`; explicitly distinguish CI mocks and optional real-Ollama smoke; state no OCR or React PDF upload.
- [ ] **Step 5: Run GREEN and regression:** focused tests; `.venv/bin/python -m pytest -q`, `npm test`, `npm run build`; parse both GitHub Actions YAML files; `git diff --check`. Record exact counts and warnings.
- [ ] **Step 6: Review diff and commit:** `feat: route text PDFs through validated agent`.

### Task 4: Whole-branch verification and push

**Files:** no product edits unless review finds a defect; test/docs fixes receive their own commits.

- [ ] **Step 1:** Obtain independent whole-branch review against this spec and acceptance criteria. Fix Critical/Important findings with failing tests first.
- [ ] **Step 2:** Re-run `.venv/bin/python -m pytest -q`, `npm test`, `npm run build`, YAML parsing, `git diff --check`, and `git status --short --branch`. Report exact outcomes.
- [ ] **Step 3:** If Ollama is available locally, run a separately labeled real-PDF smoke against `/agent/pdf`; do not count this as CI. Do not download a model.
- [ ] **Step 4:** `git push -u origin feature/pdf-extraction`; observe backend/frontend workflow outcomes via `gh run list`/`gh run view`. Do not merge or push `main`.

## Task Interfaces and Sequencing

Task 1 and Task 2 are file-disjoint and may run in parallel after this plan is frozen. Task 3 waits for both interfaces. Task 4 waits for Task 3. No two agents edit the same file simultaneously; root reviews, verifies, and commits each result before integration.

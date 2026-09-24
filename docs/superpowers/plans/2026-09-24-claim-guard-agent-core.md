# ClaimGuard Agent Core — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Use `superpowers:test-driven-development` for each behavior, `superpowers:systematic-debugging` for failures, `superpowers:requesting-code-review` at the review gates, and `superpowers:verification-before-completion` before declaring Phase 1 complete.

**Goal:** Replace the frontend's simulated agent sequence with a controlled Ollama-backed agent that validates structured decisions, executes only three registered deterministic tools, and returns a real trace.

**Architecture:** A synchronous orchestrator asks an injected chat client for a Pydantic-validated decision: either a permitted tool request or a final answer. A registry validates tool arguments and invokes wrappers around the existing database and audit functions; tool results return to the model until it answers or reaches `MAX_TOOL_STEPS = 5`. FastAPI exposes one thin endpoint and React consumes its typed result without redesigning the UI.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, HTTPX, Ollama HTTP API, Pytest, React/TypeScript/Vite/Vitest, GitHub Actions.

**Spec:** `README.md` plus the Persona 2 — Agente IA + Ollama brief supplied on 2026-09-24. This plan covers Phase 1 only; Phase 2 gets a separate plan after the Phase 1 quality gate passes.

## Global Constraints

- Work only on `feature/agent-core`; do not push, merge, close PRs, or delete branches without explicit authorization.
- Keep audit rules, tariffs, claims, SQL, and persistence deterministic; the model may select a tool but may not implement these rules.
- Do not add LangChain, LangGraph, CrewAI, AutoGen, RAG, vector databases, n8n, OCR, fine-tuning, or arbitrary command execution.
- Keep Ollama behind one `chat(...)` abstraction; configure `OLLAMA_HOST`, `OLLAMA_MODEL`, and `OLLAMA_TIMEOUT` from the environment.
- Permit one corrective retry for invalid structured output and at most five tool calls.
- Never log full invoices, prompts, secrets, environment contents, or raw sensitive payloads.
- Preserve current unversioned backend routes and frontend appearance.
- Every task ends with diff review, focused tests, regression tests appropriate to the touched layer, and one local commit.
- Agents assigned in parallel must have non-overlapping writable files.

## Repository Diagnosis

### Verified current behavior

- `backend/main.py` defines `Factura`/`ItemFactura`, persists invoices at `POST /facturas`, exposes claims and tariffs, and calls `auditar_factura` at `POST /auditar`.
- `backend/auditoria.py` deterministically detects duplicate codes, missing claims, missing tariffs, prices above the tariff, and items not authorized for the claim.
- `backend/database.py` owns all SQLite queries needed by the three proposed tools: `obtener_siniestro`, `obtener_tarifa`, and the queries transitively used by `auditar_factura`.
- `src/App.tsx` performs real direct API calls, but always runs the same fixed sequence for any prompt and creates its visible activity messages locally.
- The frontend has `npm test` and `npm run build`; one smoke test exists. No backend tests or GitHub Actions workflows exist.

### Ownership boundaries

- Persona 1 owns React, TypeScript, Vite, CSS, and visual behavior. The only planned frontend edits are the API contract, mirrored types, and replacement of synthetic trace generation with backend-provided steps. No CSS or layout changes.
- Persona 2 owns agent schemas, Ollama transport, structured decision parsing, prompts, registry, tool adapters, orchestration, and their tests/documentation.
- Persona 3 owns FastAPI, SQLite, persistence, claims, tariffs, and audit rules. Planned changes to its files are limited to moving the existing invoice models to a shared import-safe module and adding a thin endpoint/dependency adapter; no SQL or audit rule is rewritten.

### Gaps and discrepancies

- There is no Ollama client, configuration, prompt, structured decision parser, tool registry, orchestrator, real trace, backend test suite, or CI.
- `backend/main.py` creates and seeds SQLite at import time; tests must isolate `DATABASE_PATH` rather than using the developer database.
- `backend/requirements.txt` is UTF-16 LE/CRLF. It must become UTF-8 before CI can depend on it reliably.
- The root app reports version `1.5.0` while `/` returns `1.4`; unrelated to Persona 2 and not part of this plan.
- The README mentions future PDF and `/api/v1/audits` work, but neither exists. PDF is explicitly deferred.
- `.gitignore` protects `.env` but not `.env.*`; environment-specific secret files need coverage while allowing an optional example file.
- Baseline verification was blocked by absent local dependencies: `pytest` and FastAPI are not installed, `node_modules` is absent, `npm test` cannot find Vitest, and `npm run build` cannot resolve frontend packages. These are environment failures, not proof of code defects or success.

## Chosen Design and Rejected Alternatives

1. **Chosen: model-neutral JSON decisions validated by Pydantic.** The Ollama request includes the decision JSON Schema, but the registry—not Ollama—authorizes and executes tools. This works with models that support structured JSON even if their native tool-calling dialect differs.
2. **Rejected for MVP: Ollama-native tool-calling objects.** It reduces prompt ceremony but couples behavior to model/template support and makes interchangeability less reliable.
3. **Rejected: deterministic backend chooses all tools and Ollama only summarizes.** It is simpler, but it does not meet the requirement that the LLM select requested tools.

## Stable Interfaces

These names are fixed before parallel implementation begins:

```python
class ChatClient(Protocol):
    def chat(self, messages: list[ChatMessage], response_model: type[T]) -> T: ...

class ToolRegistry:
    def register(self, definition: ToolDefinition) -> None: ...
    def describe(self) -> list[dict[str, object]]: ...
    def execute(self, call: ToolCall) -> ToolResult: ...

class AgentOrchestrator:
    def run(self, request: AgentRequest) -> AgentResponse: ...
```

`AgentRequest` contains `prompt` and the current validated `Factura`. `AgentResponse` contains `status`, a user-facing `message`, real `steps`, `tool_results`, optional latest `claim` and `audit`, and an optional structured `error`. A model decision is a discriminated union of `tool_call` and `final_answer`. Tool names remain strings at the LLM boundary so an unknown name can be rejected by the registry and tested.

The concrete MVP fields are:

```text
AgentStep: type, tool?, status (running|completed|failed), message
ToolCall: call_id (assigned by the orchestrator), name, arguments
ToolResult: call_id, tool, status (success|error), output?, error?, duration_ms
AgentError: code, message

get_claim input: claim_id
get_claim output: id, placa, descripcion_dano, items_autorizados
get_tariff input: item_code
get_tariff output: codigo, descripcion, precio_maximo_centavos
audit_invoice input: invoice (the shared Factura model)
audit_invoice output: factura, estado, cantidad_inconsistencias, inconsistencias
```

The two accepted model response shapes are exactly a tool decision such as `{"type":"tool_call","name":"get_claim","arguments":{"claim_id":"SIN-001"}}` or a final decision such as `{"type":"final_answer","message":"..."}`. The orchestrator assigns stable per-run IDs (`tool-1`, `tool-2`, …), so model text never controls correlation identifiers.

## Review Focus

- Blank or malformed invoice fields must fail at Pydantic/FastAPI validation before Ollama is called; Task 1 and Task 7 pin this behavior.
- Ollama can return HTTP 200 with missing/blank `message.content`; Task 2 treats that as a controlled empty-response error.
- A model can repeatedly request a missing or failing tool; Task 6 counts every request toward the five-step limit.
- A tool handler can return a shape that violates its declared output model; Task 3 converts it to a failed `ToolResult` without leaking an exception.
- A failed agent response can contain partial steps/results; Task 6 verifies the trace is preserved and no synthetic successful step is added.

---

### Task 1: Test foundation and shared contracts

**Owner:** Contract / Schema Agent, sequential and first.

**Files:**
- Create: `backend/schemas.py`
- Create: `backend/agent/__init__.py`
- Create: `backend/agent/schemas.py`
- Create: `tests/conftest.py`
- Create: `tests/test_schemas.py`
- Modify: `backend/main.py`
- Modify: `backend/requirements.txt`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: existing JSON field names from `Factura` and `ItemFactura`.
- Produces: shared invoice models plus `AgentRequest`, `AgentResponse`, `AgentStep`, `AgentError`, `ChatMessage`, `ToolCall`, `ToolResult`, `ToolDecision`, `FinalDecision`, and `AgentDecision`.

- [ ] Convert `backend/requirements.txt` to UTF-8 while preserving current pins; add exact compatible pins for `httpx` and `pytest`. Extend `.gitignore` with `.env.*` and `!.env.example`.
- [ ] Write schema tests for valid round trips; positive quantity/price; missing invoice fields; blank prompt; discriminated decisions; all step statuses; failed responses with structured errors; and JSON-safe `Decimal` serialization.
- [ ] Run `python -m pytest tests/test_schemas.py -v` and record the expected initial import failures.
- [ ] Move the existing invoice models unchanged from `backend/main.py` into `backend/schemas.py` and import them back into `main.py`. Implement only the agent data contracts required by the tests.
- [ ] Run `python -m pytest tests/test_schemas.py -v` and `python -m pytest -v`; both must pass.
- [ ] Review `git diff --check` and `git diff -- backend/main.py backend/schemas.py backend/agent/schemas.py tests/test_schemas.py backend/requirements.txt .gitignore`.
- [ ] Commit only these files with `test/feat: add shared agent contracts`.

### Task 2: Ollama configuration, transport, and structured parsing

**Owner:** Ollama Agent. May run in parallel with Tasks 3 and 4 only after Task 1 is committed.

**Files:**
- Create: `backend/agent/config.py`
- Create: `backend/agent/errors.py`
- Create: `backend/agent/ollama_client.py`
- Create: `tests/agent/test_config.py`
- Create: `tests/agent/test_ollama_client.py`

**Interfaces:**
- Consumes: `ChatMessage` and generic Pydantic response models from Task 1.
- Produces: `AgentSettings.from_env()`, `ChatClient`, and `OllamaClient.chat(messages, response_model)`.

- [ ] Write tests that load defaults and environment overrides and reject a non-positive/non-numeric `OLLAMA_TIMEOUT` or blank host/model.
- [ ] Write HTTP-boundary tests with `httpx.MockTransport` for a valid structured response, invalid JSON followed by a valid corrective retry, two invalid responses, blank content, connection refusal, timeout, model-not-found response, and other non-success status.
- [ ] Run the two test files and confirm they fail because the modules do not exist.
- [ ] Implement one settings loader with development defaults (`OLLAMA_HOST=http://127.0.0.1:11434`, `OLLAMA_MODEL=qwen2.5:3b`, and `OLLAMA_TIMEOUT=30`). Treat the model as an ordinary setting with no model-specific branches, and normalize the host in one place.
- [ ] Implement `OllamaClient.chat`: POST only to `/api/chat`, send `stream: false`, pass `response_model.model_json_schema()` as `format`, validate `message.content`, retry invalid structured output once with a corrective message, and map HTTP/transport failures to typed public-safe errors.
- [ ] Log endpoint category, model name, elapsed time, and error class only; never log messages or full response bodies.
- [ ] Run focused tests and full backend tests; inspect the diff and commit with `feat: add validated Ollama client`.

### Task 3: Explicit tool registry

**Owner:** Tool Registry Agent. May run in parallel with Tasks 2 and 4 after Task 1; writable scope is limited to the files below.

**Files:**
- Create: `backend/agent/tools/__init__.py`
- Create: `backend/agent/tools/registry.py`
- Create: `tests/agent/tools/test_registry.py`

**Interfaces:**
- Consumes: `ToolCall` and `ToolResult` from Task 1.
- Produces: `ToolDefinition(name, description, input_model, output_model, handler)` and `ToolRegistry` methods fixed above.

- [ ] Write tests for registration and catalog schema, duplicate registration, unknown tool, invalid arguments, successful execution, handler failure, and invalid handler output.
- [ ] Confirm the tests fail before implementation.
- [ ] Implement dictionary lookup only. Validate inputs before the handler and outputs after it. Return a failed `ToolResult` for expected validation/execution errors; do not use reflection, imports from generated names, `eval`, `exec`, subprocesses, or shell calls.
- [ ] Add elapsed milliseconds to tool results/logging without logging arguments or outputs.
- [ ] Run focused and full backend tests, review the diff, and commit with `feat: add safe tool registry`.

### Task 4: Prompt and decision contract

**Owner:** Prompt / Output Agent. May run in parallel with Tasks 2 and 3 after Task 1; it must not edit schemas.

**Files:**
- Create: `backend/agent/prompts.py`
- Create: `tests/agent/test_prompts.py`

**Interfaces:**
- Consumes: serialized `AgentRequest` plus `ToolRegistry.describe()` output.
- Produces: `SYSTEM_PROMPT` and pure message-builder functions for the first decision, tool-result continuation, corrective retry, and final decision.

- [ ] Write behavior tests that the generated context contains the three registered tool descriptions and current invoice, while the system instruction forbids invented claims/tariffs/audits, payment approval, and fraud declarations.
- [ ] Confirm tests fail, then implement a short prompt. Keep authorization, retry, and step limits in code rather than prose.
- [ ] Ensure tool results are clearly marked as deterministic facts and model prose as interpretation.
- [ ] Run focused/full backend tests, review the diff, and commit with `feat: add ClaimGuard decision prompts`.

### Task 5: Deterministic tool adapters

**Owner:** Tool Adapter Agent, sequential after Tasks 1 and 3.

**Files:**
- Create: `backend/agent/tools/claim_tool.py`
- Create: `backend/agent/tools/tariff_tool.py`
- Create: `backend/agent/tools/audit_tool.py`
- Create: `backend/agent/tools/defaults.py`
- Create: `tests/agent/tools/test_claim_tool.py`
- Create: `tests/agent/tools/test_tariff_tool.py`
- Create: `tests/agent/tools/test_audit_tool.py`
- Modify: `tests/conftest.py` only for the shared temporary SQLite fixture.

**Interfaces:**
- Consumes: `obtener_siniestro`, `obtener_tarifa`, `auditar_factura`, shared `Factura`, and `ToolDefinition`.
- Produces: definitions named exactly `get_claim`, `get_tariff`, and `audit_invoice`; `build_default_registry()`.

- [ ] Add a fixture that monkeypatches `backend.database.DATABASE_PATH` to a per-test temporary file and runs `crear_tablas()`. Never touch `backend/auditoria.db`.
- [ ] Write real adapter tests for an existing/missing claim, existing/missing tariff, clean invoice, duplicate item, over-tariff item, unauthorized item, and invalid tool inputs.
- [ ] Confirm failures, then implement thin adapters that call existing functions exactly once and only translate results into declared Pydantic output models.
- [ ] Do not add SQL or duplicate any condition from `auditoria.py`. Missing claim/tariff becomes a controlled failed `ToolResult` through the registry.
- [ ] Run the three focused files and the full backend suite, review the diff, and commit with `feat: expose deterministic audit tools`.

### Task 6: Bounded agent orchestrator and real trace

**Owner:** Orchestrator Agent, sequential after Tasks 2–5.

**Files:**
- Create: `backend/agent/orchestrator.py`
- Create: `tests/agent/test_orchestrator.py`

**Interfaces:**
- Consumes: injected `ChatClient`, `ToolRegistry`, prompt builders, and Task 1 schemas.
- Produces: `MAX_TOOL_STEPS = 5` and `AgentOrchestrator.run(request) -> AgentResponse`.

- [ ] Build a queued fake `ChatClient` in the test file; mock only the model boundary, never the orchestrator or registry.
- [ ] Write tests for direct final answer; `get_claim`; `get_tariff`; `audit_invoice`; unknown tool followed by recovery; invalid arguments followed by recovery; handler failure followed by recovery; Ollama unavailable; timeout; invalid structured output after retry; empty response; exactly five tool calls then final; a sixth tool request; and preservation of partial trace on failure.
- [ ] Confirm failures, then implement the minimal loop. Append steps only when validation/model calls/tool execution/final generation actually occurs. Count every requested tool, including unknown/failed ones.
- [ ] Catch only known domain errors into `AgentResponse(status="failed")`; log unexpected exceptions internally and return a generic `internal_error` without stack traces in the response.
- [ ] Populate optional `claim` and `audit` only from successful matching tool results. Never manufacture them from model text.
- [ ] Run focused/full backend tests, review the diff, and commit with `feat: orchestrate bounded ClaimGuard tool calls`.

### Task 7: Thin FastAPI integration

**Owner:** Integration Agent, sequential after Task 6; this is the only Persona 3 integration touchpoint.

**Files:**
- Create: `backend/agent/factory.py`
- Create: `tests/test_agent_api.py`
- Modify: `backend/main.py`

**Interfaces:**
- Consumes: `AgentRequest`, `AgentResponse`, `OllamaClient`, default registry, and orchestrator.
- Produces: `POST /agent` with `AgentResponse`; a FastAPI dependency/provider that tests can override.

- [ ] Write endpoint tests that use FastAPI dependency override with a real orchestrator, queued fake chat client, and real registry: successful audit flow, invalid invoice rejected before model use, and controlled Ollama failure. Assert no call requires a live Ollama server.
- [ ] Confirm the new endpoint is absent, then implement the provider and one route. Preserve `/facturas`, `/tarifas`, `/siniestros/{id}`, and `/auditar` unchanged.
- [ ] Ensure request-validation and agent failures are JSON responses without raw exception or traceback text.
- [ ] Run endpoint/full backend tests, review only the narrow `main.py` diff, and commit with `feat: expose ClaimGuard agent endpoint`.

### Task 8: Replace simulated frontend steps with backend trace

**Owner:** Integration Agent with Persona 1 review. Do not edit CSS or component layout.

**Files:**
- Modify: `src/types/audit.ts`
- Modify: `src/services/api.ts`
- Modify: `src/App.tsx`
- Modify: `src/App.test.tsx`

**Interfaces:**
- Consumes: `POST /agent` request/response from Task 7.
- Produces: `runClaimGuardAgent(request)` and UI activity entries derived exclusively from `AgentResponse.steps`.

- [ ] Add a Vitest fetch fake and write tests asserting one `/api/agent` request, returned tool steps displayed in order, returned final text displayed, returned audit rendered, and a failed response displayed without invented success events.
- [ ] Run `npm test -- --run src/App.test.tsx` and confirm the new tests fail.
- [ ] Mirror only the required Pydantic contract in TypeScript and add the service call. Replace `runAgent`'s direct `getClaim`/`saveInvoice`/`auditInvoice` sequence and hard-coded activity strings with the single agent call and returned steps.
- [ ] Preserve all visual markup/classes. Keep legacy API helpers exported for backward compatibility but unused by the agent flow.
- [ ] Run `npm test` and `npm run build`, review the four-file diff with Persona 1 boundaries in mind, and commit with `feat: render backend agent trace`.

### Task 9: Reproducible GitHub Actions quality gates

**Owner:** CI Agent, after backend and frontend commands are known to pass locally.

**Files:**
- Create: `.github/workflows/backend-tests.yml`
- Create: `.github/workflows/frontend-tests.yml`

**Interfaces:**
- Consumes: `backend/requirements.txt`, pytest suite, lockfile, npm scripts.
- Produces: independent `backend-tests` and `frontend-tests` checks on `push` and `pull_request`.

- [ ] Add backend workflow: `actions/checkout`, `actions/setup-python` with Python 3.12 and pip cache, install the UTF-8 requirements file, then `python -m pytest -v`.
- [ ] Add frontend workflow: checkout, `actions/setup-node` with Node 22 and npm cache, `npm ci`, `npm test`, then `npm run build`.
- [ ] Search workflows for `ollama`, `ollama pull`, model downloads, or live-host assumptions; the result must be empty.
- [ ] Parse both YAML files locally with an available YAML parser and manually inspect action indentation/triggers. If `actionlint` is already installed, run it; do not add it as a product dependency.
- [ ] Run the same backend/frontend commands locally, review the diff, and commit with `ci: verify backend and frontend`.

### Task 10: Documentation, final review, and Phase 1 gate

**Owner:** Documentation Agent followed by independent Test / Review Agent.

**Files:**
- Modify: `README.md`
- Review: all Phase 1 files; no drive-by refactors.

**Interfaces:**
- Consumes: final environment variables, route, commands, error behavior, and CI design.
- Produces: reproducible local setup and an evidence report.

- [ ] Document Python/frontend installation, Ollama installation link/command assumptions, `ollama serve`, model pull chosen by the developer, `OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`, backend/frontend startup, JSON request example for `/agent`, tests, and model switching.
- [ ] State explicitly that CI uses fake/model-boundary tests and does not prove live Ollama integration. Label the documented manual real-Ollama smoke flow as a local integration check.
- [ ] Run an independent code review against every Phase 1 acceptance criterion. Fix high/medium findings through the original task owner, rerun focused and full tests, and create separate corrective commits.
- [ ] Run final verification from a clean dependency state where practical:

```bash
python -m pytest -v
npm ci
npm test
npm run build
git diff --check
git status --short --branch
```

- [ ] Record command, exit code, test count, and failures exactly. Do not claim Ollama integration passed unless the separately labeled local live smoke was actually run.
- [ ] Commit documentation with `docs: explain local Ollama agent setup`. Stop before push, PR, merge, or Phase 2.

## Phase 2 Gate

Do not create PDF code on this branch. After Phase 1 is green and reviewed, create `feature/pdf-extraction` and a separate plan for `pdf_extractor.py`, `invoice_extractor.py`, synthetic PDF fixtures, missing-field handling, and optional live-Ollama verification. OCR remains outside the MVP.

## Planned File Map

```text
backend/
├── schemas.py                         # shared existing invoice contracts
└── agent/
    ├── __init__.py
    ├── config.py                      # OLLAMA_* environment settings
    ├── errors.py                      # controlled domain errors
    ├── schemas.py                     # agent/decision/trace contracts
    ├── ollama_client.py               # sole Ollama HTTP boundary
    ├── prompts.py                     # short system/context messages
    ├── orchestrator.py                # bounded decision/tool loop
    ├── factory.py                     # production composition
    └── tools/
        ├── __init__.py
        ├── registry.py
        ├── defaults.py
        ├── claim_tool.py
        ├── tariff_tool.py
        └── audit_tool.py
tests/
├── conftest.py
├── test_schemas.py
├── test_agent_api.py
└── agent/
    ├── test_config.py
    ├── test_ollama_client.py
    ├── test_prompts.py
    ├── test_orchestrator.py
    └── tools/
        ├── test_registry.py
        ├── test_claim_tool.py
        ├── test_tariff_tool.py
        └── test_audit_tool.py
.github/workflows/
├── backend-tests.yml
└── frontend-tests.yml
```

## Execution Coordination

1. Contract / Schema Agent completes Task 1; root reviews, tests, and commits.
2. Ollama, Registry, and Prompt agents execute Tasks 2–4 in parallel with exclusive file scopes; root integrates and runs the entire backend suite after all three commits.
3. Tool Adapter Agent, Orchestrator Agent, and Integration Agent execute Tasks 5–8 sequentially because each consumes the preceding contract.
4. CI and documentation may proceed only after command lines are stable.
5. A fresh reviewer checks the entire branch, then `superpowers:verification-before-completion` governs the final evidence report.

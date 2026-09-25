# Kocha PDF Demo Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make FAC-DEMO-002 extract and audit reliably while giving users concise evidence and actionable errors.

**Architecture:** Parse the known repair-invoice text deterministically before falling back to Ollama, then pass the same validated `Factura` through the existing orchestrator and audit tools. Seed only the synthetic claim and tariffs required by the fixture. React renders the returned invoice as evidence and avoids duplicating controlled backend errors.

**Tech Stack:** Python 3.12, Pydantic 2, FastAPI, SQLite, React, TypeScript, Vitest.

**Spec:** Approved in-chat plan from 2026-09-25.

## Global Constraints

- Keep `/agent`, `/agent/pdf`, audit rules, and database schema unchanged.
- No OCR, new agent framework, persistence subsystem, or model download.
- Continue automatically after successful extraction.
- Never map `CLM-2026-002` to `SIN-001`.

## Review Focus

- Table totals must not become invoice items.
- Unit quantities such as `4 h` must become positive integers.
- Unsupported shipping invoices must fall back and report missing fields.
- Existing JSON and `SIN-001` behavior must remain unchanged.
- Controlled backend errors must appear only once in the UI.

---

### Task 1: Deterministic repair-invoice parser

- [ ] Add failing tests for the five FAC-DEMO-002 items, currency and hour normalization, totals exclusion, and unsupported-layout fallback.
- [ ] Implement `parse_repair_invoice_text(text: str) -> dict[str, object] | None` in a focused extractor module.
- [ ] Integrate deterministic-first extraction with the current verified Ollama fallback.
- [ ] Run extractor and pipeline tests.

### Task 2: Synthetic demo claim and audit data

- [ ] Add failing claim and audit tests for `CLM-2026-002` and the expected two over-tariff findings.
- [ ] Seed the synthetic claim, authorized items, and missing tariffs with `INSERT OR IGNORE`.
- [ ] Run database tool and audit tests.

### Task 3: Evidence and controlled-error UX

- [ ] Add failing frontend tests for extracted evidence, no duplicate controlled error, and preserved follow-up context.
- [ ] Add a compact, collapsible invoice-evidence component and render it from `AgentResponse.invoice`.
- [ ] Reserve the composer error banner for transport/HTTP/client failures.
- [ ] Run frontend tests and production build.

### Task 4: Model configuration and full verification

- [ ] Align the documented demo model with `qwen3:4b-instruct` while retaining the 120-second timeout.
- [ ] Run backend tests under the project environment, frontend tests, build, and `git diff --check`.
- [ ] Run separately labeled live smoke tests for both supplied PDFs without counting them as CI.

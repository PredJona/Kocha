from collections import deque

import pytest

from backend.agent.errors import AgentExecutionError
from backend.agent.extractors.invoice_extractor import InvoiceExtractor
from backend.agent.orchestrator import AgentOrchestrator
from backend.agent.pdf_pipeline import run_pdf_agent
from backend.agent.tools.defaults import build_default_registry
from pdf_fixture import make_blank_pdf, make_text_pdf


SOURCE = "Factura FAC-001 Siniestro SIN-001 Taller Taller Norte REP-001 Parachoques delantero 2 125.50"


class FakeChat:
    def __init__(self, *responses):
        self.responses = deque(responses)
        self.calls = 0

    def chat(self, messages, response_model):
        self.calls += 1
        response = self.responses.popleft()
        if isinstance(response, Exception):
            raise response
        return response_model.model_validate(response)


def run(data, fake):
    return run_pdf_agent(data, "Audita esta factura", InvoiceExtractor(fake), AgentOrchestrator(fake, build_default_registry()))


def test_pdf_pipeline_audits_extracted_invoice(invoice_data, temporary_database):
    fake = FakeChat(
        invoice_data,
        {"type": "final_answer", "message": "Revisión completada."},
    )

    result = run(make_text_pdf(SOURCE), fake)

    assert result.status == "completed"
    assert result.invoice.numero == "FAC-001"
    assert result.audit["estado"] == "CORRECTA"
    assert [step.type for step in result.steps] == [
        "pdf_text_extracted", "invoice_extracted", "invoice_validated", "tool_call",
        "model_call", "response_generated",
    ]
    assert all(step.status == "completed" for step in result.steps)
    assert fake.calls == 2


def test_pdf_pipeline_detects_an_over_tariff_item(invoice_data, temporary_database):
    over_tariff_invoice = {
        **invoice_data,
        "items": [{**invoice_data["items"][0], "precio_unitario": "450.00"}],
    }
    fake = FakeChat(
        over_tariff_invoice,
        {"type": "final_answer", "message": "Se detectó una posible inconsistencia tarifaria."},
    )

    result = run(make_text_pdf(SOURCE.replace("125.50", "450.00")), fake)

    assert result.status == "completed"
    assert result.audit["estado"] == "CON_INCONSISTENCIAS"
    assert result.audit["inconsistencias"][0]["tipo"] == "PRECIO_SUPERA_TARIFA"


def test_blank_pdf_fails_before_model_or_orchestrator(temporary_database):
    fake = FakeChat()

    result = run(make_blank_pdf(), fake)

    assert result.status == "failed"
    assert result.error.code == "PDF_NO_TEXT"
    assert [step.type for step in result.steps] == ["error"]
    assert result.audit is None
    assert fake.calls == 0


def test_incomplete_invoice_fails_before_orchestrator(invoice_data, temporary_database):
    fake = FakeChat({**invoice_data, "numero": None})

    result = run(make_text_pdf(SOURCE), fake)

    assert result.status == "failed"
    assert result.error.code == "INVOICE_INCOMPLETE"
    assert [step.type for step in result.steps] == ["pdf_text_extracted", "error"]
    assert result.audit is None
    assert fake.calls == 1


def test_invalid_model_json_is_controlled(invoice_data, temporary_database):
    fake = FakeChat(AgentExecutionError("MODEL_INVALID_RESPONSE", "El modelo devolvió una respuesta inválida."))

    result = run(make_text_pdf(SOURCE), fake)

    assert result.status == "failed"
    assert result.error.code == "MODEL_INVALID_RESPONSE"
    assert [step.type for step in result.steps] == ["pdf_text_extracted", "error"]
    assert result.audit is None
    assert fake.calls == 1


def test_pdf_pipeline_preserves_a_model_timeout_as_a_distinct_failure(temporary_database):
    fake = FakeChat(AgentExecutionError("MODEL_TIMEOUT", "Se agotó el tiempo de espera del modelo."))

    result = run(make_text_pdf(SOURCE), fake)

    assert result.status == "failed"
    assert result.error.code == "MODEL_TIMEOUT"
    assert result.message == "Se agotó el tiempo de espera del modelo."
    assert [step.type for step in result.steps] == ["pdf_text_extracted", "error"]


def test_unexpected_extraction_error_is_public_safe(temporary_database):
    fake = FakeChat(RuntimeError("FAC-SECRET in model failure"))

    result = run(make_text_pdf(SOURCE), fake)

    assert result.status == "failed"
    assert result.error.code == "internal_error"
    assert "FAC-SECRET" not in result.message
    assert [step.type for step in result.steps] == ["pdf_text_extracted", "error"]
    assert fake.calls == 1


def test_invalid_pdf_bytes_fails_before_model(temporary_database):
    fake = FakeChat()

    result = run(b"not a pdf", fake)

    assert result.status == "failed"
    assert result.error.code == "PDF_INVALID"
    assert [step.type for step in result.steps] == ["error"]
    assert result.audit is None
    assert fake.calls == 0


def test_unverified_invoice_fails_before_orchestrator(invoice_data, temporary_database):
    fake = FakeChat({**invoice_data, "numero": "FAC-999"})

    result = run(make_text_pdf(SOURCE), fake)

    assert result.status == "failed"
    assert result.error.code == "INVOICE_UNVERIFIED"
    assert [step.type for step in result.steps] == ["pdf_text_extracted", "error"]
    assert result.audit is None
    assert fake.calls == 1


def test_invalid_invoice_values_fail_before_orchestrator(invoice_data, temporary_database):
    invalid_items = [{**invoice_data["items"][0], "cantidad": 0}]
    fake = FakeChat({**invoice_data, "items": invalid_items})

    result = run(make_text_pdf(SOURCE), fake)

    assert result.status == "failed"
    assert result.error.code == "INVOICE_INVALID"
    assert [step.type for step in result.steps] == ["pdf_text_extracted", "error"]
    assert result.audit is None
    assert fake.calls == 1


def test_blank_prompt_fails_validation_with_completed_extraction_steps(invoice_data, temporary_database):
    fake = FakeChat(invoice_data)

    result = run_pdf_agent(
        make_text_pdf(SOURCE),
        "   ",
        InvoiceExtractor(fake),
        AgentOrchestrator(fake, build_default_registry()),
    )

    assert result.status == "failed"
    assert result.error.code == "invalid_request"
    assert [step.type for step in result.steps] == ["pdf_text_extracted", "invoice_extracted", "error"]
    assert result.audit is None
    assert fake.calls == 1

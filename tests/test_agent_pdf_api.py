
from fastapi.testclient import TestClient

from backend.agent.errors import AgentExecutionError
from backend.agent.ollama_client import OllamaClient
from backend.main import app
from agent.pdf_fixture import make_blank_pdf, make_text_pdf


SOURCE = "Factura FAC-001 Siniestro SIN-001 Taller Taller Norte REP-001 Parachoques delantero 2 125.50"


def test_pdf_endpoint_runs_real_audit(invoice_data, temporary_database, monkeypatch):
    responses = iter([
        invoice_data,
        {"type": "tool_call", "name": "audit_invoice", "arguments": {"invoice": invoice_data}},
        {"type": "final_answer", "message": "Revisión completada."},
    ])

    def fake_chat(self, messages, response_model):
        return response_model.model_validate(next(responses))

    monkeypatch.setattr(OllamaClient, "chat", fake_chat)
    response = TestClient(app).post(
        "/agent/pdf",
        files={"file": ("invoice.pdf", make_text_pdf(SOURCE), "application/pdf")},
        data={"prompt": "Audita esta factura"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["audit"]["estado"] == "CORRECTA"
    assert [step["type"] for step in body["steps"]][:3] == [
        "pdf_text_extracted", "invoice_extracted", "invoice_validated",
    ]


def test_pdf_endpoint_reports_textless_pdf(temporary_database, monkeypatch):
    def unexpected_chat(self, messages, response_model):
        raise AssertionError("Ollama must not be called for textless PDF")

    monkeypatch.setattr(OllamaClient, "chat", unexpected_chat)
    response = TestClient(app).post(
        "/agent/pdf",
        files={"file": ("blank.pdf", make_blank_pdf(), "application/pdf")},
        data={"prompt": "Audita esta factura"},
    )

    assert response.status_code == 200
    assert response.json()["error"]["code"] == "PDF_NO_TEXT"
    assert "Traceback" not in response.text


def test_pdf_endpoint_rejects_missing_multipart_fields(temporary_database):
    client = TestClient(app)

    assert client.post("/agent/pdf", data={"prompt": "Audita"}).status_code == 422
    assert client.post("/agent/pdf", files={"file": ("invoice.pdf", make_text_pdf(SOURCE))}).status_code == 422


def test_pdf_endpoint_rejects_oversized_upload_before_model(temporary_database, monkeypatch):
    def unexpected_chat(self, messages, response_model):
        raise AssertionError("Ollama must not be called for oversized PDF")

    monkeypatch.setattr(OllamaClient, "chat", unexpected_chat)
    response = TestClient(app).post(
        "/agent/pdf",
        files={"file": ("large.pdf", b"%PDF-1.4\n" + b"x" * (5 * 1024 * 1024), "application/pdf")},
        data={"prompt": "Audita"},
    )

    assert response.status_code == 200
    assert response.json()["error"]["code"] == "PDF_TOO_LARGE"


def test_pdf_endpoint_stops_after_incomplete_extraction(invoice_data, temporary_database, monkeypatch):
    calls = 0

    def fake_chat(self, messages, response_model):
        nonlocal calls
        calls += 1
        return response_model.model_validate({**invoice_data, "numero": None})

    monkeypatch.setattr(OllamaClient, "chat", fake_chat)
    response = TestClient(app).post(
        "/agent/pdf",
        files={"file": ("invoice.pdf", make_text_pdf(SOURCE), "application/pdf")},
        data={"prompt": "Audita"},
    )

    assert response.status_code == 200
    assert response.json()["error"]["code"] == "INVOICE_INCOMPLETE"
    assert response.json()["audit"] is None
    assert calls == 1


def test_pdf_endpoint_returns_structured_model_error(temporary_database, monkeypatch):
    def fake_chat(self, messages, response_model):
        raise AgentExecutionError("MODEL_INVALID_RESPONSE", "El modelo devolvió una respuesta inválida.")

    monkeypatch.setattr(OllamaClient, "chat", fake_chat)
    response = TestClient(app).post(
        "/agent/pdf",
        files={"file": ("invoice.pdf", make_text_pdf(SOURCE), "application/pdf")},
        data={"prompt": "Audita"},
    )

    assert response.status_code == 200
    assert response.json()["error"]["code"] == "MODEL_INVALID_RESPONSE"
    assert "Traceback" not in response.text


def test_pdf_endpoint_rejects_blank_prompt(temporary_database):
    response = TestClient(app).post(
        "/agent/pdf",
        files={"file": ("invoice.pdf", make_text_pdf(SOURCE), "application/pdf")},
        data={"prompt": "   "},
    )

    assert response.status_code == 422
    assert "Traceback" not in response.text

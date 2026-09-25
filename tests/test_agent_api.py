from collections import deque

from fastapi.testclient import TestClient

from backend.agent.errors import AgentExecutionError
from backend.agent.schemas import AgentDecision, FinalDecision
from backend.agent.tools.defaults import build_default_registry


class FakeChat:
    def __init__(self, *decisions):
        self.decisions = deque(decisions)
        self.calls = 0

    def chat(self, messages, response_model):
        self.calls += 1
        decision = self.decisions.popleft()
        if isinstance(decision, Exception):
            raise decision
        return decision


def final(text):
    return AgentDecision(root=FinalDecision(type="final_answer", message=text))


def make_client(fake, temporary_database):
    from backend.agent.factory import get_agent_orchestrator
    from backend.agent.orchestrator import AgentOrchestrator
    from backend.main import app

    app.dependency_overrides[get_agent_orchestrator] = lambda: AgentOrchestrator(fake, build_default_registry())
    return app, TestClient(app)


def test_agent_endpoint_executes_real_audit_and_returns_trace(invoice_data, temporary_database):
    fake = FakeChat(
        final("Se encontró un hallazgo para revisión humana."),
    )
    app, client = make_client(fake, temporary_database)
    try:
        response = client.post("/agent", json={"invoice": invoice_data, "prompt": "Audita esta factura"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["message"] == "Se encontró un hallazgo para revisión humana."
    assert body["audit"]["estado"] == "CORRECTA"
    assert body["audit"]["cantidad_inconsistencias"] == 0
    assert [step["type"] for step in body["steps"]] == [
        "invoice_validated", "tool_call", "model_call", "response_generated"
    ]
    assert body["tool_results"][0]["tool"] == "audit_invoice"
    assert fake.calls == 1


def test_invalid_invoice_never_calls_model(invoice_data, temporary_database):
    fake = FakeChat(final("unused"))
    app, client = make_client(fake, temporary_database)
    invalid = {**invoice_data, "items": [{**invoice_data["items"][0], "cantidad": 0}]}
    try:
        response = client.post("/agent", json={"invoice": invalid, "prompt": "Audita"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert fake.calls == 0
    assert "Traceback" not in response.text


def test_model_failure_has_structured_error_without_traceback(invoice_data, temporary_database):
    fake = FakeChat(AgentExecutionError("MODEL_UNAVAILABLE", "No se pudo contactar al modelo."))
    app, client = make_client(fake, temporary_database)
    try:
        response = client.post("/agent", json={"invoice": invoice_data, "prompt": "Audita"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["error"]["code"] == "MODEL_UNAVAILABLE"
    assert "Traceback" not in response.text

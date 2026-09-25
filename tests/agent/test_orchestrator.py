from collections import deque

import pytest

from backend.agent.errors import AgentExecutionError
from backend.agent.schemas import AgentDecision, AgentRequest, FinalDecision, ToolDecision
from backend.agent.tools.defaults import build_default_registry


class QueuedChatClient:
    """A deterministic double at the external model boundary only."""

    def __init__(self, *replies):
        self.replies = deque(replies)
        self.calls = []

    def chat(self, messages, response_model):
        self.calls.append((messages, response_model))
        reply = self.replies.popleft()
        if isinstance(reply, Exception):
            raise reply
        assert isinstance(reply, response_model)
        return reply


def final(message="Listo"):
    return AgentDecision(root=FinalDecision(type="final_answer", message=message))


def tool(name, arguments):
    return AgentDecision(root=ToolDecision(type="tool_call", name=name, arguments=arguments))


def request(invoice_data):
    return AgentRequest.model_validate({"invoice": invoice_data, "prompt": "Revisa esta factura"})


def run_with(client, invoice_data, temporary_database):
    from backend.agent.orchestrator import AgentOrchestrator

    return AgentOrchestrator(client=client, registry=build_default_registry()).run(request(invoice_data))


def test_direct_answer_has_only_actions_that_really_happened(invoice_data, temporary_database):
    client = QueuedChatClient(final("La factura requiere revisión humana."))

    response = run_with(client, invoice_data, temporary_database)

    assert response.status == "completed"
    assert response.message == "La factura requiere revisión humana."
    assert [step.type for step in response.steps] == [
        "invoice_validated", "model_call", "response_generated"
    ]
    assert [step.status for step in response.steps] == ["completed"] * 3
    assert response.tool_results == []
    assert response.claim is None
    assert response.audit is None


def test_runs_three_real_tools_and_only_returns_successful_tool_facts(invoice_data, temporary_database):
    client = QueuedChatClient(
        tool("get_claim", {"claim_id": "SIN-001"}),
        tool("get_tariff", {"item_code": "REP-001"}),
        tool("audit_invoice", {"invoice": invoice_data}),
        final("La factura coincide con el siniestro y la tarifa."),
    )

    response = run_with(client, invoice_data, temporary_database)

    assert response.status == "completed"
    assert response.message == "La factura coincide con el siniestro y la tarifa."
    assert [result.tool for result in response.tool_results] == [
        "get_claim", "get_tariff", "audit_invoice"
    ]
    assert [result.status for result in response.tool_results] == ["success"] * 3
    assert response.claim == {
        "id": "SIN-001",
        "placa": "ABC123",
        "descripcion_dano": "Daño frontal del vehículo",
        "items_autorizados": ["MAN-001", "REP-001"],
    }
    assert response.audit == {
        "factura": "FAC-001",
        "estado": "CORRECTA",
        "cantidad_inconsistencias": 0,
        "inconsistencias": [],
    }
    assert [step.type for step in response.steps].count("tool_call") == 3
    assert len(client.calls) == 4


@pytest.mark.parametrize(
    ("decision", "code"),
    [
        (tool("not_a_tool", {}), "unknown_tool"),
        (tool("get_claim", {"claim_id": ""}), "invalid_arguments"),
        (tool("get_claim", {"claim_id": "SIN-NOT-FOUND"}), "claim_not_found"),
    ],
)
def test_tool_errors_are_returned_and_model_can_recover(
    invoice_data, temporary_database, decision, code
):
    client = QueuedChatClient(decision, final("Continuaré con los datos disponibles."))

    response = run_with(client, invoice_data, temporary_database)

    assert response.status == "completed"
    assert response.tool_results[0].status == "error"
    assert response.tool_results[0].error.code == code
    assert response.steps[2].type == "tool_call"
    assert response.steps[2].status == "failed"
    assert response.steps[-1].type == "response_generated"
    assert response.steps[-1].status == "completed"


def test_modified_invoice_is_rejected_without_auditing_it(invoice_data, temporary_database):
    modified = {**invoice_data, "taller": "Taller cambiado por el modelo"}
    client = QueuedChatClient(
        tool("audit_invoice", {"invoice": modified}),
        final("No pude auditar la factura original."),
    )

    response = run_with(client, invoice_data, temporary_database)

    assert response.status == "completed"
    assert response.tool_results[0].error.code == "invalid_arguments"
    assert response.audit is None


def test_equivalent_numeric_invoice_price_is_bound_to_original_facts(invoice_data, temporary_database):
    numeric_invoice = {**invoice_data, "items": [dict(invoice_data["items"][0])]}
    numeric_invoice["items"][0]["precio_unitario"] = 125.50
    client = QueuedChatClient(
        tool("audit_invoice", {"invoice": numeric_invoice}),
        final("La factura original fue auditada."),
    )

    response = run_with(client, invoice_data, temporary_database)

    assert response.status == "completed"
    assert response.tool_results[0].status == "success"
    assert response.audit["factura"] == "FAC-001"


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (AgentExecutionError("MODEL_UNAVAILABLE", "No se pudo contactar al modelo."), "MODEL_UNAVAILABLE"),
        (AgentExecutionError("MODEL_TIMEOUT", "Se agotó el tiempo de espera del modelo."), "MODEL_TIMEOUT"),
        (AgentExecutionError("MODEL_INVALID_RESPONSE", "El modelo devolvió una respuesta inválida."), "MODEL_INVALID_RESPONSE"),
    ],
)
def test_known_model_errors_return_safe_failure_with_partial_trace(
    invoice_data, temporary_database, error, code
):
    client = QueuedChatClient(tool("get_claim", {"claim_id": "SIN-001"}), error)

    response = run_with(client, invoice_data, temporary_database)

    assert response.status == "failed"
    assert response.error.code == code
    assert "Traceback" not in response.message
    assert [step.type for step in response.steps] == [
        "invoice_validated", "model_call", "tool_call", "model_call", "error"
    ]
    assert response.steps[1].status == "completed"
    assert response.steps[3].status == "failed"
    assert len(response.tool_results) == 1
    assert response.claim == response.tool_results[0].output


def test_empty_final_response_is_reported_as_invalid_structured_output(invoice_data, temporary_database):
    client = QueuedChatClient(
        AgentExecutionError("MODEL_INVALID_RESPONSE", "El modelo devolvió una respuesta inválida.")
    )

    response = run_with(client, invoice_data, temporary_database)

    assert response.status == "failed"
    assert response.error.code == "MODEL_INVALID_RESPONSE"
    assert response.steps[-2].type == "model_call"
    assert response.steps[-2].status == "failed"


def test_five_tool_calls_can_be_followed_by_a_final_answer(invoice_data, temporary_database):
    client = QueuedChatClient(
        tool("get_tariff", {"item_code": "REP-001"}),
        tool("get_tariff", {"item_code": "MAN-001"}),
        tool("get_claim", {"claim_id": "SIN-001"}),
        tool("get_claim", {"claim_id": "SIN-001"}),
        tool("audit_invoice", {"invoice": invoice_data}),
        final("Completado después de cinco consultas."),
    )

    response = run_with(client, invoice_data, temporary_database)

    assert response.status == "completed"
    assert response.message == "Completado después de cinco consultas."
    assert len(response.tool_results) == 5
    assert response.audit["estado"] == "CORRECTA"
    assert len(client.calls) == 6


def test_sixth_tool_request_is_rejected_before_dispatch_with_partial_trace(
    invoice_data, temporary_database
):
    replies = [tool("get_tariff", {"item_code": "REP-001"}) for _ in range(6)]
    client = QueuedChatClient(*replies)

    response = run_with(client, invoice_data, temporary_database)

    assert response.status == "failed"
    assert response.error.code == "tool_step_limit"
    assert len(response.tool_results) == 5
    assert len(client.calls) == 6
    assert [step.type for step in response.steps].count("tool_call") == 6
    assert response.steps[-2].type == "tool_call"
    assert response.steps[-2].status == "failed"
    assert response.steps[-1].type == "error"
    assert response.steps[-1].status == "failed"


def test_unexpected_exception_is_redacted_and_preserves_trace(invoice_data, temporary_database):
    client = QueuedChatClient(RuntimeError("secret invoice text"))

    response = run_with(client, invoice_data, temporary_database)

    assert response.status == "failed"
    assert response.error.code == "internal_error"
    assert "secret invoice text" not in response.message
    assert "secret invoice text" not in response.error.message
    assert [step.type for step in response.steps] == ["invoice_validated", "model_call", "error"]

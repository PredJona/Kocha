import json
from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from backend.agent.schemas import (
    AgentDecision,
    AgentError,
    AgentInvoice,
    AgentRequest,
    AgentResponse,
    AgentStep,
    ChatMessage,
    FinalDecision,
    ToolCall,
    ToolDecision,
    ToolResult,
)
from backend.schemas import Factura, ItemFactura


def test_legacy_invoice_fields_round_trip_and_keep_old_validation(invoice_data):
    invoice = Factura.model_validate(invoice_data)

    assert invoice.numero == "FAC-001"
    assert invoice.items[0].precio_unitario == Decimal("125.50")
    assert Factura.model_validate(invoice.model_dump()).model_dump() == invoice.model_dump()
    assert Factura(numero="", siniestro_id="", taller="", items=[]).items == []
    assert ItemFactura(codigo="", descripcion="", cantidad="1", precio_unitario="1").cantidad == 1


@pytest.mark.parametrize("field", ["numero", "siniestro_id", "taller"])
def test_agent_request_rejects_missing_invoice_fields(invoice_data, field):
    del invoice_data[field]

    with pytest.raises(ValidationError):
        AgentRequest(invoice=invoice_data, prompt="Revisa la factura")


@pytest.mark.parametrize("field", ["numero", "siniestro_id", "taller"])
@pytest.mark.parametrize("value", ["", " \t "])
def test_agent_request_rejects_blank_invoice_strings(invoice_data, field, value):
    invoice_data[field] = value

    with pytest.raises(ValidationError):
        AgentRequest(invoice=invoice_data, prompt="Revisa la factura")


@pytest.mark.parametrize("field", ["codigo", "descripcion"])
@pytest.mark.parametrize("value", ["", "  "])
def test_agent_request_rejects_blank_item_strings(invoice_data, field, value):
    invoice_data["items"][0][field] = value

    with pytest.raises(ValidationError):
        AgentRequest(invoice=invoice_data, prompt="Revisa la factura")


def test_agent_request_rejects_empty_items(invoice_data):
    invoice_data["items"] = []

    with pytest.raises(ValidationError):
        AgentRequest(invoice=invoice_data, prompt="Revisa la factura")


@pytest.mark.parametrize("items", [None, 3, "invalid"])
def test_agent_request_rejects_malformed_items_with_validation_error(invoice_data, items):
    invoice_data["items"] = items

    with pytest.raises(ValidationError):
        AgentRequest(invoice=invoice_data, prompt="Revisa la factura")


@pytest.mark.parametrize("value", [0, -1, 1.0, "2", True])
def test_agent_request_requires_strict_positive_integer_quantity(invoice_data, value):
    invoice_data["items"][0]["cantidad"] = value

    with pytest.raises(ValidationError):
        AgentRequest(invoice=invoice_data, prompt="Revisa la factura")


@pytest.mark.parametrize("value", ["0", "-1", "NaN", "Infinity", "-Infinity"])
def test_agent_request_requires_finite_positive_price(invoice_data, value):
    invoice_data["items"][0]["precio_unitario"] = value

    with pytest.raises(ValidationError):
        AgentRequest(invoice=invoice_data, prompt="Revisa la factura")


@pytest.mark.parametrize("prompt", ["", "   \t"])
def test_agent_request_rejects_blank_prompt(invoice_data, prompt):
    with pytest.raises(ValidationError):
        AgentRequest(invoice=invoice_data, prompt=prompt)


def test_agent_request_accepts_valid_invoice_model(invoice_data):
    invoice = Factura.model_validate(invoice_data)

    request = AgentRequest(invoice=invoice, prompt="Revisa la factura")

    assert request.invoice is invoice
    assert request.prompt == "Revisa la factura"


def test_agent_request_checks_prebuilt_invoice_for_blanks():
    invoice = Factura(numero="", siniestro_id="SIN-001", taller="Taller", items=[])

    with pytest.raises(ValidationError):
        AgentRequest(invoice=invoice, prompt="Revisa la factura")


def test_agent_invoice_alias_reuses_strict_validation(invoice_data):
    adapter = TypeAdapter(AgentInvoice)
    assert adapter.validate_python(invoice_data).numero == "FAC-001"

    invoice_data["items"][0]["cantidad"] = 1.0
    with pytest.raises(ValidationError):
        adapter.validate_python(invoice_data)


@pytest.mark.parametrize(
    ("payload", "decision_type"),
    [
        ({"type": "tool_call", "name": "get_claim", "arguments": {"claim_id": "SIN-001"}}, ToolDecision),
        ({"type": "final_answer", "message": "Factura revisada"}, FinalDecision),
    ],
)
def test_agent_decision_discriminates_and_round_trips(payload, decision_type):
    decision = AgentDecision.model_validate(payload)

    assert isinstance(decision.root, decision_type)
    assert AgentDecision.model_validate_json(decision.model_dump_json()).model_dump() == payload
    assert AgentDecision.model_json_schema()


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "unknown", "message": "x"},
        {"type": "final_answer", "message": "   "},
        {"type": "tool_call", "name": "get_claim", "arguments": {}, "extra": 1},
        {"type": "final_answer", "message": "done", "extra": 1},
    ],
)
def test_agent_decision_rejects_bad_or_extra_fields(payload):
    with pytest.raises(ValidationError):
        AgentDecision.model_validate(payload)


@pytest.mark.parametrize("status", ["running", "completed", "failed"])
def test_agent_step_accepts_each_status(status):
    step = AgentStep(type="tool_call", tool="get_claim", status=status, message="Consultando")

    assert step.status == status


@pytest.mark.parametrize("step_type", ["invoice_validated", "model_call", "tool_call", "response_generated", "error"])
def test_agent_step_accepts_each_type(step_type):
    step = AgentStep(type=step_type, status="completed", message="Hecho")

    assert step.type == step_type


def test_agent_step_rejects_unsupported_status():
    with pytest.raises(ValidationError):
        AgentStep(type="tool_call", status="unknown", message="Oops")


def test_failed_agent_response_preserves_trace_and_structured_error():
    error = AgentError(code="MODEL_TIMEOUT", message="No se pudo consultar el modelo")
    result = ToolResult(call_id="tool-1", tool="get_claim", status="error", error=error, duration_ms=12)
    response = AgentResponse(
        status="failed",
        message="No se completó la revisión",
        steps=[AgentStep(type="tool_call", tool="get_claim", status="failed", message="Falló")],
        tool_results=[result],
        error=error,
    )

    assert AgentResponse.model_validate_json(response.model_dump_json()) == response
    assert response.tool_results[0].error.code == "MODEL_TIMEOUT"


def test_agent_request_decimal_serialization_is_json_safe(invoice_data):
    request = AgentRequest(invoice=invoice_data, prompt="Revisa la factura")

    payload = json.loads(request.model_dump_json())

    assert payload["invoice"]["items"][0]["precio_unitario"] == "125.50"


def test_chat_and_tool_call_contracts_are_json_serializable():
    message = ChatMessage(role="assistant", content="Resultado")
    call = ToolCall(call_id="tool-1", name="get_claim", arguments={"claim_id": "SIN-001"})

    assert json.loads(message.model_dump_json()) == {"role": "assistant", "content": "Resultado"}
    assert json.loads(call.model_dump_json())["call_id"] == "tool-1"

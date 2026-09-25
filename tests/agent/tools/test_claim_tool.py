from backend.agent.tools.claim_tool import claim_tool
from backend.agent.tools.defaults import build_default_registry
from backend.agent.tools.registry import ToolCall, ToolRegistry


def test_get_claim_returns_database_claim_and_authorized_items(temporary_database):
    registry = ToolRegistry()
    registry.register(claim_tool())

    result = registry.execute(
        ToolCall(call_id="claim-1", name="get_claim", arguments={"claim_id": "SIN-001"})
    )

    assert result.status == "success"
    assert result.output == {
        "id": "SIN-001",
        "placa": "ABC123",
        "descripcion_dano": "Daño frontal del vehículo",
        "items_autorizados": ["MAN-001", "REP-001"],
    }


def test_missing_claim_is_a_safe_registry_failure(temporary_database):
    registry = ToolRegistry()
    registry.register(claim_tool())

    result = registry.execute(
        ToolCall(call_id="claim-2", name="get_claim", arguments={"claim_id": "SIN-404"})
    )

    assert result.status == "error"
    assert result.output is None
    assert result.error.code == "claim_not_found"
    assert result.error.message == "Siniestro no encontrado"


def test_get_claim_rejects_invalid_or_extra_input(temporary_database):
    registry = ToolRegistry()
    registry.register(claim_tool())

    for arguments in ({}, {"claim_id": " ", "private": "value"}):
        result = registry.execute(ToolCall(call_id="claim-3", name="get_claim", arguments=arguments))
        assert result.status == "error"
        assert result.error.code == "invalid_arguments"


def test_default_registry_exposes_only_the_three_deterministic_tools(temporary_database):
    descriptions = build_default_registry().describe()

    assert [tool["name"] for tool in descriptions] == [
        "get_claim",
        "get_tariff",
        "audit_invoice",
    ]

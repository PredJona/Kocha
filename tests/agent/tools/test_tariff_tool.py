from backend.agent.tools.registry import ToolCall, ToolRegistry
from backend.agent.tools.tariff_tool import tariff_tool


def test_get_tariff_returns_database_tariff(temporary_database):
    registry = ToolRegistry()
    registry.register(tariff_tool())

    result = registry.execute(
        ToolCall(call_id="tariff-1", name="get_tariff", arguments={"item_code": "REP-001"})
    )

    assert result.status == "success"
    assert result.output == {
        "codigo": "REP-001",
        "descripcion": "Parachoques delantero",
        "precio_maximo_centavos": 30000,
    }


def test_missing_tariff_is_a_safe_registry_failure(temporary_database):
    registry = ToolRegistry()
    registry.register(tariff_tool())

    result = registry.execute(
        ToolCall(call_id="tariff-2", name="get_tariff", arguments={"item_code": "REP-404"})
    )

    assert result.status == "error"
    assert result.output is None
    assert result.error.code == "tariff_not_found"
    assert result.error.message == "Tarifa no encontrada"


def test_get_tariff_rejects_invalid_or_extra_input(temporary_database):
    registry = ToolRegistry()
    registry.register(tariff_tool())

    for arguments in ({}, {"item_code": " ", "private": "value"}):
        result = registry.execute(ToolCall(call_id="tariff-3", name="get_tariff", arguments=arguments))
        assert result.status == "error"
        assert result.error.code == "invalid_arguments"

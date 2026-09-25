from backend.agent.tools.audit_tool import audit_tool
from backend.agent.tools.registry import ToolCall, ToolRegistry


def _audit(temporary_database, invoice):
    registry = ToolRegistry()
    registry.register(audit_tool())
    return registry.execute(
        ToolCall(call_id="audit-1", name="audit_invoice", arguments={"invoice": invoice})
    )


def test_audit_invoice_returns_the_auditar_contract_for_clean_invoice(temporary_database, invoice_data):
    result = _audit(temporary_database, invoice_data)

    assert result.status == "success"
    assert result.output == {
        "factura": "FAC-001",
        "estado": "CORRECTA",
        "cantidad_inconsistencias": 0,
        "inconsistencias": [],
    }


def test_audit_invoice_reports_duplicate_item(temporary_database, invoice_data):
    invoice_data["items"].append(dict(invoice_data["items"][0]))

    result = _audit(temporary_database, invoice_data)

    assert result.status == "success"
    assert result.output["estado"] == "CON_INCONSISTENCIAS"
    assert result.output["cantidad_inconsistencias"] == 1
    assert result.output["inconsistencias"][0]["tipo"] == "ITEM_DUPLICADO"


def test_audit_invoice_reports_over_tariff_item(temporary_database, invoice_data):
    invoice_data["items"][0]["precio_unitario"] = "350.00"

    result = _audit(temporary_database, invoice_data)

    assert result.status == "success"
    assert result.output["inconsistencias"][0]["tipo"] == "PRECIO_SUPERA_TARIFA"


def test_audit_invoice_reports_item_unauthorized_for_claim(temporary_database, invoice_data):
    invoice_data["items"][0]["codigo"] = "REP-002"

    result = _audit(temporary_database, invoice_data)

    assert result.status == "success"
    assert result.output["inconsistencias"][0]["tipo"] == "ITEM_NO_CORRESPONDE_SINIESTRO"


def test_audit_invoice_rejects_invalid_tool_input(temporary_database, invoice_data):
    registry = ToolRegistry()
    registry.register(audit_tool())
    invoice_data["items"][0]["cantidad"] = 1.5

    result = registry.execute(
        ToolCall(call_id="audit-2", name="audit_invoice", arguments={"invoice": invoice_data})
    )

    assert result.status == "error"
    assert result.error.code == "invalid_arguments"


def test_audit_invoice_rejects_extra_input_fields(temporary_database, invoice_data):
    registry = ToolRegistry()
    registry.register(audit_tool())

    result = registry.execute(
        ToolCall(
            call_id="audit-3",
            name="audit_invoice",
            arguments={"invoice": invoice_data, "override": True},
        )
    )

    assert result.status == "error"
    assert result.error.code == "invalid_arguments"

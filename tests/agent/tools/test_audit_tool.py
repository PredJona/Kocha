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


def test_fac_demo_invoice_reports_only_two_over_tariff_items(temporary_database):
    invoice = {
        "numero": "FAC-DEMO-002",
        "siniestro_id": "CLM-2026-002",
        "taller": "Taller Automotriz Panama, S.A.",
        "items": [
            {"codigo": "REP-001", "descripcion": "Parachoques delantero", "cantidad": 1, "precio_unitario": "450.00"},
            {"codigo": "REP-002", "descripcion": "Faro delantero derecho", "cantidad": 1, "precio_unitario": "185.00"},
            {"codigo": "MAT-001", "descripcion": "Pintura y materiales", "cantidad": 1, "precio_unitario": "120.00"},
            {"codigo": "MO-001", "descripcion": "Mano de obra - carroceria", "cantidad": 4, "precio_unitario": "35.00"},
            {"codigo": "MO-002", "descripcion": "Mano de obra - pintura", "cantidad": 3, "precio_unitario": "30.00"},
        ],
    }

    result = _audit(temporary_database, invoice)

    assert result.status == "success"
    assert result.output["cantidad_inconsistencias"] == 2
    assert [finding["codigo"] for finding in result.output["inconsistencias"]] == ["REP-001", "REP-002"]
    assert all(finding["tipo"] == "PRECIO_SUPERA_TARIFA" for finding in result.output["inconsistencias"])


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

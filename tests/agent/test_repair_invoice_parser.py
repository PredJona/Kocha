from decimal import Decimal


REPAIR_INVOICE_TEXT = """TALLER AUTOMOTRIZ PANAMA, S.A.
FACTURA DE SERVICIOS DE REPARACION
 FACTURA N.º
FAC-DEMO-002
Fecha
25/09/2026
Cliente / Reclamo
Cliente
Carlos Mendoza
Reclamo
CLM-2026-002
Vehiculo
Toyota Corolla 2022
Placa
AB1234
Motivo
Reparacion por colision frontal
Detalle de reparacion
Codigo
Descripcion
Cant.
Precio unit.
Total
REP-001
Parachoques delantero
1
B/. 450.00
B/. 450.00
REP-002
Faro delantero derecho
1
B/. 185.00
B/. 185.00
MAT-001
Pintura y materiales
1
B/. 120.00
B/. 120.00
MO-001
Mano de obra - carroceria
4 h
B/. 35.00
B/. 140.00
MO-002
Mano de obra - pintura
3 h
B/. 30.00
B/. 90.00
Subtotal
B/. 985.00
ITBMS (7%)
B/. 68.95
TOTAL
B/. 1,053.95
Informacion del taller
Taller Automotriz Panama, S.A.
"""

SHIPPING_INVOICE_TEXT = """Shippy
Factura
# Fact-0125969
Facturar a:
Jonathan Romero
# Tracking & Descripción Peso Tarifa Total
1 TBA334713200120 2 2.75 5.50
"""


def test_parses_all_repair_items_and_excludes_totals():
    from backend.agent.extractors.repair_invoice_parser import parse_repair_invoice_text

    result = parse_repair_invoice_text(REPAIR_INVOICE_TEXT)

    assert result == {
        "numero": "FAC-DEMO-002",
        "siniestro_id": "CLM-2026-002",
        "taller": "TALLER AUTOMOTRIZ PANAMA, S.A.",
        "items": [
            {"codigo": "REP-001", "descripcion": "Parachoques delantero", "cantidad": 1, "precio_unitario": "450.00"},
            {"codigo": "REP-002", "descripcion": "Faro delantero derecho", "cantidad": 1, "precio_unitario": "185.00"},
            {"codigo": "MAT-001", "descripcion": "Pintura y materiales", "cantidad": 1, "precio_unitario": "120.00"},
            {"codigo": "MO-001", "descripcion": "Mano de obra - carroceria", "cantidad": 4, "precio_unitario": "35.00"},
            {"codigo": "MO-002", "descripcion": "Mano de obra - pintura", "cantidad": 3, "precio_unitario": "30.00"},
        ],
    }
    assert all(item["precio_unitario"] != Decimal("985.00") for item in result["items"])


def test_unsupported_invoice_layout_returns_none():
    from backend.agent.extractors.repair_invoice_parser import parse_repair_invoice_text

    assert parse_repair_invoice_text(SHIPPING_INVOICE_TEXT) is None

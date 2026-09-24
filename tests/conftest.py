import pytest


@pytest.fixture
def invoice_data():
    return {
        "numero": "FAC-001",
        "siniestro_id": "SIN-001",
        "taller": "Taller Norte",
        "items": [
            {
                "codigo": "REP-001",
                "descripcion": "Parachoques delantero",
                "cantidad": 2,
                "precio_unitario": "125.50",
            }
        ],
    }

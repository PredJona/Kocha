import pytest
from fastapi.testclient import TestClient

import backend.database as database
from backend.main import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def base_datos_temporal(
    tmp_path,
    monkeypatch
):
    ruta_temporal = (
        tmp_path / "test_api.db"
    )

    monkeypatch.setattr(
        database,
        "DATABASE_PATH",
        ruta_temporal
    )

    database.crear_tablas()


def test_inicio():
    respuesta = client.get("/")

    assert respuesta.status_code == 200

    datos = respuesta.json()

    assert datos["version"] == "1.8"


def test_obtener_tarifas():
    respuesta = client.get(
        "/tarifas"
    )

    assert respuesta.status_code == 200

    tarifas = respuesta.json()

    assert len(tarifas) == 3


def test_consultar_siniestro():
    respuesta = client.get(
        "/siniestros/SIN-001"
    )

    assert respuesta.status_code == 200

    datos = respuesta.json()

    assert datos["id"] == "SIN-001"

    assert (
        "REP-001"
        in datos["items_autorizados"]
    )


def test_auditar_factura():
    factura = {
        "numero": "FAC-TEST-001",
        "siniestro_id": "SIN-001",
        "taller": "Taller Prueba",
        "items": [
            {
                "codigo": "REP-001",
                "descripcion": (
                    "Parachoques delantero"
                ),
                "cantidad": 1,
                "precio_unitario": 350
            }
        ]
    }

    respuesta = client.post(
        "/auditar",
        json=factura
    )

    assert respuesta.status_code == 200

    resultado = respuesta.json()

    assert resultado["estado"] == (
        "CON_INCONSISTENCIAS"
    )

    assert (
        resultado["cantidad_inconsistencias"]
        == 1
    )

    assert (
        resultado["inconsistencias"][0]["tipo"]
        == "PRECIO_SUPERA_TARIFA"
    )
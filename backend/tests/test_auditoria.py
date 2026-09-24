from decimal import Decimal

import pytest

import backend.database as database
from backend.auditoria import auditar_factura
from backend.main import Factura, ItemFactura


@pytest.fixture(autouse=True)
def base_datos_temporal(tmp_path, monkeypatch):
    ruta_temporal = tmp_path / "test_auditoria.db"

    monkeypatch.setattr(
        database,
        "DATABASE_PATH",
        ruta_temporal
    )

    database.crear_tablas()


def crear_factura(items, siniestro_id="SIN-001"):
    return Factura(
        numero="FAC-TEST",
        siniestro_id=siniestro_id,
        taller="Taller Prueba",
        items=items
    )


def test_factura_correcta():
    factura = crear_factura([
        ItemFactura(
            codigo="REP-001",
            descripcion="Parachoques delantero",
            cantidad=1,
            precio_unitario=Decimal("280")
        )
    ])

    inconsistencias = auditar_factura(factura)

    assert inconsistencias == []


def test_detecta_precio_superior_tarifa():
    factura = crear_factura([
        ItemFactura(
            codigo="REP-001",
            descripcion="Parachoques delantero",
            cantidad=1,
            precio_unitario=Decimal("350")
        )
    ])

    inconsistencias = auditar_factura(factura)

    tipos = [
        inconsistencia["tipo"]
        for inconsistencia in inconsistencias
    ]

    assert "PRECIO_SUPERA_TARIFA" in tipos


def test_detecta_item_duplicado():
    factura = crear_factura([
        ItemFactura(
            codigo="REP-001",
            descripcion="Parachoques delantero",
            cantidad=1,
            precio_unitario=Decimal("280")
        ),
        ItemFactura(
            codigo="REP-001",
            descripcion="Parachoques delantero",
            cantidad=1,
            precio_unitario=Decimal("280")
        )
    ])

    inconsistencias = auditar_factura(factura)

    tipos = [
        inconsistencia["tipo"]
        for inconsistencia in inconsistencias
    ]

    assert "ITEM_DUPLICADO" in tipos


def test_detecta_item_no_autorizado():
    factura = crear_factura([
        ItemFactura(
            codigo="REP-002",
            descripcion="Faro delantero",
            cantidad=1,
            precio_unitario=Decimal("150")
        )
    ])

    inconsistencias = auditar_factura(factura)

    tipos = [
        inconsistencia["tipo"]
        for inconsistencia in inconsistencias
    ]

    assert "ITEM_NO_CORRESPONDE_SINIESTRO" in tipos


def test_detecta_siniestro_inexistente():
    factura = crear_factura(
        [
            ItemFactura(
                codigo="REP-001",
                descripcion="Parachoques delantero",
                cantidad=1,
                precio_unitario=Decimal("280")
            )
        ],
        siniestro_id="SIN-999"
    )

    inconsistencias = auditar_factura(factura)

    assert inconsistencias[0]["tipo"] == (
        "SINIESTRO_NO_ENCONTRADO"
    )
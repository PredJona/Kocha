import pytest

from backend import database


@pytest.fixture
def temporary_database(tmp_path, monkeypatch):
    """Initialize a real isolated SQLite database for backend integration tests."""
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test-auditoria.db")
    database.crear_tablas()
    return database.DATABASE_PATH


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

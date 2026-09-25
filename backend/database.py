import sqlite3
from decimal import Decimal
from pathlib import Path


DATABASE_PATH = Path(__file__).parent / "auditoria.db"


def conectar():
    conexion = sqlite3.connect(DATABASE_PATH)
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion


def crear_tablas():
    with conectar() as conexion:
        cursor = conexion.cursor()

        # -------------------------
        # Facturas
        # -------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS facturas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero TEXT NOT NULL UNIQUE,
                siniestro_id TEXT NOT NULL,
                taller TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS items_factura (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                factura_id INTEGER NOT NULL,
                codigo TEXT NOT NULL,
                descripcion TEXT NOT NULL,
                cantidad INTEGER NOT NULL,
                precio_unitario_centavos INTEGER NOT NULL,

                FOREIGN KEY (factura_id)
                    REFERENCES facturas(id)
            )
        """)

        # -------------------------
        # Tarifario
        # -------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tarifas (
                codigo TEXT PRIMARY KEY,
                descripcion TEXT NOT NULL,
                precio_maximo_centavos INTEGER NOT NULL
            )
        """)

        cursor.executemany("""
            INSERT OR IGNORE INTO tarifas (
                codigo,
                descripcion,
                precio_maximo_centavos
            )
            VALUES (?, ?, ?)
        """, [
            (
                "REP-001",
                "Parachoques delantero",
                30000
            ),
            (
                "MAN-001",
                "Mano de obra",
                5000
            ),
            (
                "REP-002",
                "Faro delantero",
                18000
            ),
            (
                "MAT-001",
                "Pintura y materiales",
                15000
            ),
            (
                "MO-001",
                "Mano de obra - carrocería",
                5000
            ),
            (
                "MO-002",
                "Mano de obra - pintura",
                5000
            )
        ])

        # -------------------------
        # Siniestros
        # -------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS siniestros (
                id TEXT PRIMARY KEY,
                placa TEXT NOT NULL,
                descripcion_dano TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS items_siniestro (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                siniestro_id TEXT NOT NULL,
                codigo_item TEXT NOT NULL,

                FOREIGN KEY (siniestro_id)
                    REFERENCES siniestros(id),

                UNIQUE (
                    siniestro_id,
                    codigo_item
                )
            )
        """)

        # Siniestro de prueba
        cursor.execute("""
            INSERT OR IGNORE INTO siniestros (
                id,
                placa,
                descripcion_dano
            )
            VALUES (?, ?, ?)
        """, (
            "SIN-001",
            "ABC123",
            "Daño frontal del vehículo"
        ))

        # Ítems autorizados para SIN-001
        cursor.executemany("""
            INSERT OR IGNORE INTO items_siniestro (
                siniestro_id,
                codigo_item
            )
            VALUES (?, ?)
        """, [
            (
                "SIN-001",
                "REP-001"
            ),
            (
                "SIN-001",
                "MAN-001"
            )
        ])

        cursor.execute("""
            INSERT OR IGNORE INTO siniestros (
                id,
                placa,
                descripcion_dano
            )
            VALUES (?, ?, ?)
        """, (
            "CLM-2026-002",
            "AB1234",
            "Reparación por colisión frontal"
        ))

        cursor.executemany("""
            INSERT OR IGNORE INTO items_siniestro (
                siniestro_id,
                codigo_item
            )
            VALUES (?, ?)
        """, [
            ("CLM-2026-002", "REP-001"),
            ("CLM-2026-002", "REP-002"),
            ("CLM-2026-002", "MAT-001"),
            ("CLM-2026-002", "MO-001"),
            ("CLM-2026-002", "MO-002"),
        ])


def convertir_a_centavos(precio: Decimal) -> int:
    """
    Convierte dólares a centavos.

    Ejemplo:
    350.00 -> 35000
    """
    return int(precio * 100)


def guardar_factura(factura):
    """
    Guarda una factura y todos sus ítems.
    """

    with conectar() as conexion:
        cursor = conexion.cursor()

        cursor.execute(
            """
            INSERT INTO facturas (
                numero,
                siniestro_id,
                taller
            )
            VALUES (?, ?, ?)
            """,
            (
                factura.numero,
                factura.siniestro_id,
                factura.taller
            )
        )

        factura_id = cursor.lastrowid

        for item in factura.items:
            cursor.execute(
                """
                INSERT INTO items_factura (
                    factura_id,
                    codigo,
                    descripcion,
                    cantidad,
                    precio_unitario_centavos
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    factura_id,
                    item.codigo,
                    item.descripcion,
                    item.cantidad,
                    convertir_a_centavos(
                        item.precio_unitario
                    )
                )
            )

        return factura_id


def obtener_tarifa(codigo):
    """
    Busca un ítem dentro del tarifario.
    """

    with conectar() as conexion:
        conexion.row_factory = sqlite3.Row
        cursor = conexion.cursor()

        cursor.execute(
            """
            SELECT
                codigo,
                descripcion,
                precio_maximo_centavos
            FROM tarifas
            WHERE codigo = ?
            """,
            (codigo,)
        )

        tarifa = cursor.fetchone()

        if tarifa is None:
            return None

        return dict(tarifa)


def listar_tarifas():
    """
    Devuelve todas las tarifas.
    """

    with conectar() as conexion:
        conexion.row_factory = sqlite3.Row
        cursor = conexion.cursor()

        cursor.execute("""
            SELECT
                codigo,
                descripcion,
                precio_maximo_centavos
            FROM tarifas
            ORDER BY codigo
        """)

        tarifas = cursor.fetchall()

        return [
            dict(tarifa)
            for tarifa in tarifas
        ]


def obtener_siniestro(siniestro_id):
    """
    Busca un siniestro y devuelve
    sus ítems autorizados.
    """

    with conectar() as conexion:
        conexion.row_factory = sqlite3.Row
        cursor = conexion.cursor()

        cursor.execute(
            """
            SELECT
                id,
                placa,
                descripcion_dano
            FROM siniestros
            WHERE id = ?
            """,
            (siniestro_id,)
        )

        siniestro = cursor.fetchone()

        if siniestro is None:
            return None

        cursor.execute(
            """
            SELECT codigo_item
            FROM items_siniestro
            WHERE siniestro_id = ?
            ORDER BY codigo_item
            """,
            (siniestro_id,)
        )

        items = cursor.fetchall()

        resultado = dict(siniestro)

        resultado["items_autorizados"] = [
            item["codigo_item"]
            for item in items
        ]

        return resultado

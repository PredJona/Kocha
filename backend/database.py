import sqlite3
from decimal import Decimal
from pathlib import Path


# La base de datos se guardará dentro de la carpeta backend
DATABASE_PATH = Path(__file__).parent / "auditoria.db"


def conectar():
    """
    Crea una conexión con la base de datos SQLite.
    """
    return sqlite3.connect(DATABASE_PATH)


def crear_tablas():
    """
    Crea las tablas necesarias para el sistema
    si todavía no existen.
    """

    with conectar() as conexion:
        cursor = conexion.cursor()

        # Tabla principal de facturas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS facturas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero TEXT NOT NULL UNIQUE,
                siniestro_id TEXT NOT NULL,
                taller TEXT NOT NULL
            )
        """)

        # Ítems que pertenecen a cada factura
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

        # Tarifario acordado con los talleres
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tarifas (
                codigo TEXT PRIMARY KEY,
                descripcion TEXT NOT NULL,
                precio_maximo_centavos INTEGER NOT NULL
            )
        """)

        # Datos ficticios para nuestro MVP
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
            )
        ])


def convertir_a_centavos(precio: Decimal) -> int:
    """
    Convierte un precio en dólares a centavos.

    Ejemplo:
    350.00 -> 35000
    """
    return int(precio * 100)


def guardar_factura(factura):
    """
    Guarda una factura y todos sus ítems
    dentro de SQLite.
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
    Busca una tarifa utilizando el código
    del repuesto o servicio.
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
    Devuelve todas las tarifas registradas.
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
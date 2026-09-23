import sqlite3
from decimal import Decimal
from pathlib import Path


DATABASE_PATH = Path(__file__).parent / "auditoria.db"


def conectar():
    return sqlite3.connect(DATABASE_PATH)


def crear_tablas():
    with conectar() as conexion:
        cursor = conexion.cursor()

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
                FOREIGN KEY (factura_id) REFERENCES facturas(id)
            )
        """)


def convertir_a_centavos(precio: Decimal) -> int:
    return int(precio * 100)


def guardar_factura(factura):
    with conectar() as conexion:
        cursor = conexion.cursor()

        cursor.execute(
            """
            INSERT INTO facturas (numero, siniestro_id, taller)
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
                    convertir_a_centavos(item.precio_unitario)
                )
            )

        return factura_id
import sqlite3
from decimal import Decimal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from backend.auditoria import auditar_factura
from backend.database import (
    crear_tablas,
    guardar_factura,
    listar_tarifas,
    obtener_siniestro,
)


app = FastAPI(
    title="Kocha - Auditor de Facturación",
    version="1.4.0"
)


crear_tablas()


class ItemFactura(BaseModel):
    codigo: str
    descripcion: str
    cantidad: int = Field(
        gt=0
    )
    precio_unitario: Decimal = Field(
        gt=0
    )


class Factura(BaseModel):
    numero: str
    siniestro_id: str
    taller: str
    items: list[ItemFactura]


@app.get("/")
def inicio():
    return {
        "mensaje": (
            "Backend del Reto 2 funcionando"
        ),
        "version": "1.4"
    }


@app.post("/facturas")
def recibir_factura(
    factura: Factura
):
    try:
        factura_id = guardar_factura(
            factura
        )

        return {
            "mensaje": (
                "Factura guardada correctamente"
            ),
            "id": factura_id,
            "numero": factura.numero
        }

    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail=(
                "La factura ya fue registrada "
                "anteriormente"
            )
        )


@app.get("/tarifas")
def obtener_tarifas():
    return listar_tarifas()


@app.get(
    "/siniestros/{siniestro_id}"
)
def consultar_siniestro(
    siniestro_id: str
):
    siniestro = obtener_siniestro(
        siniestro_id
    )

    if siniestro is None:
        raise HTTPException(
            status_code=404,
            detail="Siniestro no encontrado"
        )

    return siniestro


@app.post("/auditar")
def auditar(
    factura: Factura
):
    inconsistencias = auditar_factura(
        factura
    )

    if inconsistencias:
        estado = "CON_INCONSISTENCIAS"

    else:
        estado = "CORRECTA"

    return {
        "factura": factura.numero,
        "estado": estado,
        "cantidad_inconsistencias": (
            len(inconsistencias)
        ),
        "inconsistencias": inconsistencias
    }
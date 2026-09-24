import sqlite3
from decimal import Decimal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.auditoria import auditar_factura
from backend.database import (
    crear_tablas,
    guardar_auditoria,
    guardar_factura,
    listar_auditorias,
    listar_tarifas,
    obtener_auditoria,
    obtener_siniestro,
)


app = FastAPI(
    title="Kocha - Auditor de Facturación",
    description=(
        "API para auditar facturas de talleres contra "
        "tarifarios y siniestros reportados."
    ),
    version="1.8.0"
)


# --------------------------------------------------
# CORS
# Permite que el frontend pueda comunicarse
# con el backend durante el desarrollo.
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Crear las tablas al iniciar la aplicación
crear_tablas()


# --------------------------------------------------
# Modelos
# --------------------------------------------------

class ItemFactura(BaseModel):
    codigo: str = Field(
        min_length=1
    )

    descripcion: str = Field(
        min_length=1
    )

    cantidad: int = Field(
        gt=0
    )

    precio_unitario: Decimal = Field(
        gt=0
    )


class Factura(BaseModel):
    numero: str = Field(
        min_length=1
    )

    siniestro_id: str = Field(
        min_length=1
    )

    taller: str = Field(
        min_length=1
    )

    items: list[ItemFactura] = Field(
        min_length=1
    )


# --------------------------------------------------
# Estado del backend
# --------------------------------------------------

@app.get("/")
def inicio():
    return {
        "mensaje": (
            "Backend del Reto 2 funcionando"
        ),
        "version": "1.8"
    }


# --------------------------------------------------
# Facturas
# --------------------------------------------------

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


# --------------------------------------------------
# Tarifario
# --------------------------------------------------

@app.get("/tarifas")
def obtener_tarifas():
    return listar_tarifas()


# --------------------------------------------------
# Siniestros
# --------------------------------------------------

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


# --------------------------------------------------
# Auditoría
# --------------------------------------------------

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

    auditoria_id = guardar_auditoria(
        factura,
        estado,
        inconsistencias
    )

    return {
        "auditoria_id": auditoria_id,
        "factura": factura.numero,
        "estado": estado,
        "cantidad_inconsistencias": (
            len(inconsistencias)
        ),
        "inconsistencias": inconsistencias
    }


# --------------------------------------------------
# Historial de auditorías
# --------------------------------------------------

@app.get("/auditorias")
def consultar_auditorias():
    return listar_auditorias()


@app.get(
    "/auditorias/{auditoria_id}"
)
def consultar_auditoria(
    auditoria_id: int
):
    auditoria = obtener_auditoria(
        auditoria_id
    )

    if auditoria is None:
        raise HTTPException(
            status_code=404,
            detail="Auditoría no encontrada"
        )

    return auditoria
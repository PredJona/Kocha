from decimal import Decimal

from fastapi import FastAPI
from pydantic import BaseModel, Field


app = FastAPI(
    title="Kocha - Auditor de Facturación",
    version="1.1.0"
)


class ItemFactura(BaseModel):
    codigo: str
    descripcion: str
    cantidad: int = Field(gt=0)
    precio_unitario: Decimal = Field(gt=0)


class Factura(BaseModel):
    numero: str
    siniestro_id: str
    taller: str
    items: list[ItemFactura]


@app.get("/")
def inicio():
    return {
        "mensaje": "Backend del Reto 2 funcionando",
        "version": "1.1"
    }


@app.post("/facturas")
def recibir_factura(factura: Factura):
    return {
        "mensaje": "Factura recibida correctamente",
        "factura": factura
    }
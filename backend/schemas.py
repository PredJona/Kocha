from decimal import Decimal

from pydantic import BaseModel, Field


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

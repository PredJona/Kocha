"""Read-only adapter for tariff lookup."""

from pydantic import BaseModel, ConfigDict, field_validator

from backend.agent.tools.registry import ToolDefinition, ToolExecutionError
from backend.database import obtener_tarifa


class TariffInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_code: str

    @field_validator("item_code")
    @classmethod
    def validate_item_code(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("item_code must not be blank")
        return value


class TariffOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: str
    descripcion: str
    precio_maximo_centavos: int


def _get_tariff(request: TariffInput) -> TariffOutput:
    tariff = obtener_tarifa(request.item_code)
    if tariff is None:
        raise ToolExecutionError("tariff_not_found", "Tarifa no encontrada")
    return TariffOutput(
        codigo=tariff["codigo"],
        descripcion=tariff["descripcion"],
        precio_maximo_centavos=tariff["precio_maximo_centavos"],
    )


def tariff_tool() -> ToolDefinition:
    return ToolDefinition(
        name="get_tariff",
        description="Consulta el precio máximo acordado para un ítem.",
        input_model=TariffInput,
        output_model=TariffOutput,
        handler=_get_tariff,
    )

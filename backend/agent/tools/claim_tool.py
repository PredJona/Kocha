"""Read-only adapter for claim lookup."""

from pydantic import BaseModel, ConfigDict, field_validator

from backend.agent.tools.registry import ToolDefinition, ToolExecutionError
from backend.database import obtener_siniestro


class ClaimInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str

    @field_validator("claim_id")
    @classmethod
    def validate_claim_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("claim_id must not be blank")
        return value


class ClaimOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    placa: str
    descripcion_dano: str
    items_autorizados: list[str]


def _get_claim(request: ClaimInput) -> ClaimOutput:
    claim = obtener_siniestro(request.claim_id)
    if claim is None:
        raise ToolExecutionError("claim_not_found", "Siniestro no encontrado")
    return ClaimOutput(
        id=claim["id"],
        placa=claim["placa"],
        descripcion_dano=claim["descripcion_dano"],
        items_autorizados=claim["items_autorizados"],
    )


def claim_tool() -> ToolDefinition:
    return ToolDefinition(
        name="get_claim",
        description="Consulta un siniestro y sus ítems autorizados.",
        input_model=ClaimInput,
        output_model=ClaimOutput,
        handler=_get_claim,
    )

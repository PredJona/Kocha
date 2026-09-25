"""Thin adapter around the deterministic invoice audit."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from backend.agent.schemas import AgentInvoice
from backend.agent.tools.registry import ToolDefinition
from backend.auditoria import auditar_factura


class AuditInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invoice: AgentInvoice


class AuditOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    factura: str
    estado: Literal["CORRECTA", "CON_INCONSISTENCIAS"]
    cantidad_inconsistencias: int
    inconsistencias: list[dict[str, Any]]


def _audit_invoice(request: AuditInput) -> AuditOutput:
    inconsistencias = auditar_factura(request.invoice)
    return AuditOutput(
        factura=request.invoice.numero,
        estado="CON_INCONSISTENCIAS" if inconsistencias else "CORRECTA",
        cantidad_inconsistencias=len(inconsistencias),
        inconsistencias=inconsistencias,
    )


def audit_tool() -> ToolDefinition:
    return ToolDefinition(
        name="audit_invoice",
        description="Audita una factura con las reglas deterministas del sistema.",
        input_model=AuditInput,
        output_model=AuditOutput,
        handler=_audit_invoice,
    )

"""Bounded orchestration loop for ClaimGuard's structured tool decisions."""

import logging
import re
from typing import Any

from pydantic import ValidationError

from backend.agent.errors import AgentExecutionError
from backend.agent.ollama_client import ChatClient
from backend.agent.prompts import initial_messages, tool_messages
from backend.agent.schemas import (
    AgentDecision,
    AgentError,
    AgentRequest,
    AgentResponse,
    AgentStep,
    ChatMessage,
    FinalDecision,
    ToolCall,
    ToolDecision,
    ToolResult,
)
from backend.agent.tools.audit_tool import AuditInput
from backend.agent.tools.registry import ToolRegistry
from backend.schemas import Factura


logger = logging.getLogger(__name__)
MAX_TOOL_STEPS = 5
_AUDIT_REQUEST_RE = re.compile(
    r"\b(?:audita(?:r)?|auditor[ií]as?|audit(?:s|ed|ing)?|"
    r"revis(?:a|ar|e|i[oó]n)|review(?:s|ed|ing)?|"
    r"comprueba|comprobar|compruebe|check(?:s|ed|ing)?)\b",
    re.IGNORECASE,
)
_AUDIT_REMINDER = (
    "La solicitud requiere una auditoría. Llama a audit_invoice con la factura original "
    "incluida en la solicitud, espera el resultado y después responde."
)
_AUDIT_NOT_PERFORMED = "No se pudo completar la auditoría solicitada."


class AgentOrchestrator:
    def __init__(self, client: ChatClient, registry: ToolRegistry) -> None:
        self.client = client
        self.registry = registry

    def run(self, request: AgentRequest) -> AgentResponse:
        steps: list[AgentStep] = [
            AgentStep(
                type="invoice_validated",
                status="completed",
                message="La factura fue validada.",
            )
        ]
        tool_results: list[ToolResult] = []
        claim: dict[str, Any] | None = None
        audit: dict[str, Any] | None = None
        try:
            messages = initial_messages(request, self.registry.describe())
            tool_steps = 0
            audit_required = _AUDIT_REQUEST_RE.search(request.prompt) is not None
            audit_reminded = False

            while True:
                if audit_required and audit is None and tool_steps == 0:
                    decision = ToolDecision(
                        type="tool_call",
                        name="audit_invoice",
                        arguments={"invoice": request.invoice.model_dump(mode="json")},
                    )
                else:
                    model_step = AgentStep(
                        type="model_call",
                        status="running",
                        message="Consultando al modelo.",
                    )
                    steps.append(model_step)
                    try:
                        response_model = (
                            ToolDecision if audit_required and audit is None else AgentDecision
                        )
                        decision_response = self.client.chat(messages, response_model)
                    except Exception:
                        steps[-1] = model_step.model_copy(update={"status": "failed"})
                        raise
                    steps[-1] = model_step.model_copy(
                        update={"status": "completed", "message": "El modelo respondió."}
                    )

                    decision = (
                        decision_response.root
                        if isinstance(decision_response, AgentDecision)
                        else decision_response
                    )
                if isinstance(decision, FinalDecision):
                    if audit_required and audit is None:
                        if not audit_reminded:
                            messages.append(ChatMessage(role="user", content=_AUDIT_REMINDER))
                            audit_reminded = True
                            continue
                        return self._failed(
                            "audit_not_performed",
                            _AUDIT_NOT_PERFORMED,
                            steps,
                            tool_results,
                            request.invoice,
                            claim,
                            audit,
                        )
                    steps.append(
                        AgentStep(
                            type="response_generated",
                            status="completed",
                            message="Se generó la respuesta final.",
                        )
                    )
                    return AgentResponse(
                        status="completed",
                        message=decision.message,
                        steps=steps,
                        tool_results=tool_results,
                        invoice=request.invoice,
                        claim=claim,
                        audit=audit,
                    )

                if not isinstance(decision, ToolDecision):
                    raise RuntimeError("chat client returned an invalid decision type")

                tool_steps += 1
                if tool_steps > MAX_TOOL_STEPS:
                    steps.append(
                        AgentStep(
                            type="tool_call",
                            tool=decision.name,
                            status="failed",
                            message="Se alcanzó el límite de consultas a herramientas.",
                        )
                    )
                    return self._failed(
                        "tool_step_limit",
                        "Se alcanzó el límite de consultas a herramientas.",
                        steps,
                        tool_results,
                        request.invoice,
                        claim,
                        audit,
                    )

                tool_step = AgentStep(
                    type="tool_call",
                    tool=decision.name,
                    status="running",
                    message="Ejecutando herramienta.",
                )
                steps.append(tool_step)
                call = ToolCall(
                    call_id=f"tool-{tool_steps}",
                    name=decision.name,
                    arguments=decision.arguments,
                )
                try:
                    result = self._execute(request, call)
                except Exception:
                    steps[-1] = tool_step.model_copy(update={"status": "failed"})
                    raise
                steps[-1] = tool_step.model_copy(
                    update={
                        "status": "completed" if result.status == "success" else "failed",
                        "message": "La herramienta terminó." if result.status == "success" else "La herramienta devolvió un error.",
                    }
                )
                tool_results.append(result)
                if result.status == "success" and result.output is not None:
                    if result.tool == "get_claim":
                        claim = result.output
                    elif result.tool == "audit_invoice":
                        audit = result.output
                messages.extend(tool_messages(decision, result))
                if (
                    audit_required
                    and audit is None
                    and result.tool == "audit_invoice"
                    and result.status == "error"
                    and not audit_reminded
                ):
                    messages.append(ChatMessage(role="user", content=_AUDIT_REMINDER))
                    audit_reminded = True

        except AgentExecutionError as exc:
            return self._failed(exc.code, exc.message, steps, tool_results, request.invoice, claim, audit)
        except Exception as exc:
            # Error messages and stack traces can include invoice/model data; log only a safe class label.
            logger.error("Unexpected agent orchestration failure error_class=%s", type(exc).__name__)
            return self._failed(
                "internal_error",
                "Ocurrió un error interno al procesar la solicitud.",
                steps,
                tool_results,
                request.invoice,
                claim,
                audit,
            )

    def _execute(self, request: AgentRequest, call: ToolCall) -> ToolResult:
        if call.name == "audit_invoice":
            try:
                audit_input = AuditInput.model_validate(call.arguments)
            except ValidationError:
                audit_input = None
            if audit_input is None or audit_input.invoice != request.invoice:
                return ToolResult(
                    call_id=call.call_id,
                    tool=call.name,
                    status="error",
                    error=AgentError(
                        code="invalid_arguments",
                        message="Invalid tool arguments",
                    ),
                    duration_ms=0,
                )
        return self.registry.execute(call)

    @staticmethod
    def _failed(
        code: str,
        message: str,
        steps: list[AgentStep],
        tool_results: list[ToolResult],
        invoice: Factura,
        claim: dict[str, Any] | None,
        audit: dict[str, Any] | None,
    ) -> AgentResponse:
        steps.append(AgentStep(type="error", status="failed", message=message))
        return AgentResponse(
            status="failed",
            message=message,
            steps=steps,
            tool_results=tool_results,
            invoice=invoice,
            claim=claim,
            audit=audit,
            error=AgentError(code=code, message=message),
        )

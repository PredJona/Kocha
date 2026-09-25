"""Validated path from embedded PDF text to the existing agent."""

import logging

from pydantic import ValidationError

from backend.agent.errors import AgentExecutionError
from backend.agent.extractors.invoice_extractor import InvoiceExtractor
from backend.agent.extractors.pdf_extractor import extract_pdf_text
from backend.agent.orchestrator import AgentOrchestrator
from backend.agent.schemas import AgentError, AgentRequest, AgentResponse, AgentStep


logger = logging.getLogger(__name__)


def run_pdf_agent(
    pdf_bytes: bytes,
    prompt: str,
    invoice_extractor: InvoiceExtractor,
    orchestrator: AgentOrchestrator,
) -> AgentResponse:
    """Extract, validate and audit a PDF with a trace of completed stages."""
    steps: list[AgentStep] = []
    try:
        text = extract_pdf_text(pdf_bytes)
        steps.append(AgentStep(type="pdf_text_extracted", status="completed", message="Se extrajo el texto del PDF."))
        invoice = invoice_extractor.extract(text)
        steps.append(AgentStep(type="invoice_extracted", status="completed", message="Se extrajo la factura."))
        request = AgentRequest(invoice=invoice, prompt=prompt)
    except AgentExecutionError as exc:
        return _failure(exc.code, exc.message, steps)
    except ValidationError:
        return _failure("invalid_request", "La solicitud es inválida.", steps)
    except Exception as exc:
        logger.error("Unexpected PDF extraction failure error_class=%s", type(exc).__name__)
        return _failure("internal_error", "Ocurrió un error interno al procesar la solicitud.", steps)

    response = orchestrator.run(request)
    return response.model_copy(update={"steps": steps + response.steps})


def _failure(code: str, message: str, steps: list[AgentStep]) -> AgentResponse:
    return AgentResponse(
        status="failed",
        message=message,
        steps=[*steps, AgentStep(type="error", status="failed", message=message)],
        error=AgentError(code=code, message=message),
    )

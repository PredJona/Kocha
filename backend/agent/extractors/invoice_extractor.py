"""Extract an invoice from PDF text without trusting unsupported model values."""

import re
import unicodedata
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, ConfigDict, StrictFloat, StrictInt, ValidationError

from backend.agent.errors import AgentExecutionError
from backend.agent.ollama_client import ChatClient
from backend.agent.schemas import AgentRequest, ChatMessage
from backend.schemas import Factura


class CandidateItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: str | None = None
    descripcion: str | None = None
    cantidad: StrictInt | StrictFloat | str | None = None
    precio_unitario: StrictInt | StrictFloat | str | None = None


class CandidateInvoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    numero: str | None = None
    siniestro_id: str | None = None
    taller: str | None = None
    items: list[CandidateItem] | None = None


_SYSTEM_PROMPT = (
    "Extrae los datos de la factura del texto. Copia solo valores presentes; "
    "usa null para campos ausentes. No hagas suposiciones ni audites la factura."
)
_NUMBER_TOKEN = re.compile(r"(?<![\w.,+-])\d+(?:[.,]\d+)*(?![\w.,])")


def _normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _source_numbers(text: str) -> set[Decimal]:
    numbers: set[Decimal] = set()
    for match in _NUMBER_TOKEN.finditer(text):
        token = match.group()
        if token.count(".") + token.count(",") > 1:
            continue
        try:
            numbers.add(Decimal(token.replace(",", ".")))
        except InvalidOperation:
            continue
    return numbers


class InvoiceExtractor:
    def __init__(self, client: ChatClient) -> None:
        self.client = client

    def extract(self, text: str) -> Factura:
        candidate = self.client.chat(
            [ChatMessage(role="system", content=_SYSTEM_PROMPT), ChatMessage(role="user", content=text)],
            CandidateInvoice,
        )
        data = candidate.model_dump()
        headers = (candidate.numero, candidate.siniestro_id, candidate.taller)
        if any(value is None or not value.strip() for value in headers):
            raise AgentExecutionError("INVOICE_INCOMPLETE", "La factura no contiene todos los campos obligatorios.")
        if not candidate.items or any(
            item.codigo is None
            or not item.codigo.strip()
            or item.descripcion is None
            or not item.descripcion.strip()
            or item.cantidad is None
            or item.precio_unitario is None
            for item in candidate.items
        ):
            raise AgentExecutionError("INVOICE_INCOMPLETE", "La factura no contiene todos los campos obligatorios.")

        try:
            invoice = AgentRequest.model_validate({"invoice": data, "prompt": "Audita esta factura"}).invoice
        except ValidationError as exc:
            raise AgentExecutionError("INVOICE_INVALID", "La factura contiene valores inválidos.") from exc

        source = _normalized(text)
        numbers = _source_numbers(text)
        for value in (invoice.numero, invoice.siniestro_id, invoice.taller):
            if _normalized(value) not in source:
                raise AgentExecutionError("INVOICE_UNVERIFIED", "No se pudieron verificar los datos de la factura.")
        for item in invoice.items:
            if (
                _normalized(item.codigo) not in source
                or _normalized(item.descripcion) not in source
                or Decimal(item.cantidad) not in numbers
                or item.precio_unitario not in numbers
            ):
                raise AgentExecutionError("INVOICE_UNVERIFIED", "No se pudieron verificar los datos de la factura.")
        return invoice

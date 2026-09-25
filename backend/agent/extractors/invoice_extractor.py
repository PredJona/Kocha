"""Extract an invoice from PDF text without trusting unsupported model values."""

import re
import unicodedata
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, ConfigDict, StrictFloat, StrictInt, ValidationError

from backend.agent.errors import AgentExecutionError
from backend.agent.ollama_client import ChatClient
from backend.agent.schemas import AgentRequest, ChatMessage
from backend.agent.extractors.repair_invoice_parser import parse_repair_invoice_text
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
    "usa null para campos ausentes. No hagas suposiciones ni audites la factura. "
    "numero es el número identificado como Factura, N.º factura o No. factura; "
    "siniestro_id es el identificador señalado como Siniestro, N.º siniestro o Claim; "
    "taller es el nombre señalado como Taller. Para cada concepto extrae código, "
    "descripción, cantidad y precio unitario. Convierte importes con el prefijo B/. "
    "a números decimales sin moneda."
)
_NUMBER_TOKEN = re.compile(r"(?<!\S)[0-9]+(?:[.,][0-9]+)?(?!\S)")
_CURRENCY_PREFIX = re.compile(r"(?:B/\.\s*|\$\s*)(?=[0-9])", re.IGNORECASE)
_CURRENCY_AMOUNT = re.compile(r"\s*(?:B/\.\s*|\$\s*)?([0-9]+(?:[.,][0-9]+)?)\s*", re.IGNORECASE)


def _normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _source_numbers(text: str) -> set[Decimal]:
    numbers: set[Decimal] = set()
    normalized_text = _CURRENCY_PREFIX.sub(" ", text)
    for match in _NUMBER_TOKEN.finditer(normalized_text):
        token = match.group()
        try:
            numbers.add(Decimal(token.replace(",", ".")))
        except InvalidOperation:
            continue
    return numbers


def _normalise_price(value: StrictInt | StrictFloat | str | None) -> StrictInt | StrictFloat | str | None:
    if not isinstance(value, str):
        return value
    match = _CURRENCY_AMOUNT.fullmatch(value)
    return match.group(1).replace(",", ".") if match else value


def _missing_required_fields(candidate: CandidateInvoice) -> list[str]:
    missing = [
        label
        for label, value in (
            ("número de factura", candidate.numero),
            ("siniestro", candidate.siniestro_id),
            ("taller", candidate.taller),
        )
        if value is None or not value.strip()
    ]
    if not candidate.items:
        return [*missing, "conceptos"]
    for index, item in enumerate(candidate.items, start=1):
        for label, value in (
            ("código", item.codigo),
            ("descripción", item.descripcion),
            ("cantidad", item.cantidad),
            ("precio unitario", item.precio_unitario),
        ):
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(f"concepto {index}: {label}")
    return missing


class InvoiceExtractor:
    def __init__(self, client: ChatClient) -> None:
        self.client = client

    def extract(self, text: str) -> Factura:
        parsed = parse_repair_invoice_text(text)
        candidate = (
            CandidateInvoice.model_validate(parsed)
            if parsed is not None
            else self.client.chat(
                [ChatMessage(role="system", content=_SYSTEM_PROMPT), ChatMessage(role="user", content=text)],
                CandidateInvoice,
            )
        )
        data = candidate.model_dump()
        missing = _missing_required_fields(candidate)
        if missing:
            raise AgentExecutionError(
                "INVOICE_INCOMPLETE",
                f"No se pudieron extraer los campos obligatorios: {', '.join(missing)}.",
            )
        for item in data["items"]:
            item["precio_unitario"] = _normalise_price(item["precio_unitario"])

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

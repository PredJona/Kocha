from decimal import Decimal

import pytest

from backend.agent.errors import AgentExecutionError
from backend.agent.extractors.invoice_extractor import InvoiceExtractor
from backend.schemas import Factura
from test_repair_invoice_parser import REPAIR_INVOICE_TEXT


SOURCE = (
    "Factura FAC-001\nSiniestro SIN-001\nTaller Taller Norte\n"
    "REP-001 Parachoques delantero 2 450,00\n"
)
DEMO_SOURCE = (
    "FACTURA N.º: FAC-DEMO-002\n"
    "N.º DE SINIESTRO: SIN-001\n"
    "TALLER: Taller Aurora\n"
    "CÓDIGO | DESCRIPCIÓN | CANTIDAD | PRECIO UNITARIO\n"
    "REP-001 | Parachoques delantero | 1 | B/.450.00\n"
)
VALID = {
    "numero": "FAC-001",
    "siniestro_id": "SIN-001",
    "taller": "Taller Norte",
    "items": [
        {
            "codigo": "REP-001",
            "descripcion": "Parachoques delantero",
            "cantidad": 2,
            "precio_unitario": "B/.450.00",
        }
    ],
}


class FakeClient:
    def __init__(self, data=None, error=None):
        self.data = data
        self.error = error
        self.response_model = None

    def chat(self, messages, response_model):
        self.response_model = response_model
        if self.error:
            raise self.error
        return response_model.model_validate(self.data)


class UnexpectedClient:
    def chat(self, messages, response_model):
        raise AssertionError("Ollama must not be called for the supported repair invoice layout")


def extract(data, text=SOURCE):
    client = FakeClient(data)
    return InvoiceExtractor(client).extract(text)


def test_extract_returns_strict_invoice_with_decimal_price():
    client = FakeClient(VALID)

    invoice = InvoiceExtractor(client).extract(SOURCE.lower())

    assert isinstance(invoice, Factura)
    assert invoice.numero == "FAC-001"
    assert invoice.siniestro_id == "SIN-001"
    assert invoice.taller == "Taller Norte"
    assert len(invoice.items) == 1
    assert invoice.items[0].codigo == "REP-001"
    assert invoice.items[0].descripcion == "Parachoques delantero"
    assert invoice.items[0].cantidad == 2
    assert invoice.items[0].precio_unitario == Decimal("450.00")
    assert client.response_model is not None


def test_supported_repair_invoice_skips_model_extraction():
    invoice = InvoiceExtractor(UnexpectedClient()).extract(REPAIR_INVOICE_TEXT)

    assert invoice.numero == "FAC-DEMO-002"
    assert invoice.siniestro_id == "CLM-2026-002"
    assert len(invoice.items) == 5
    assert invoice.items[3].cantidad == 4


@pytest.mark.parametrize(
    "data",
    [
        {**VALID, "numero": None},
        {**VALID, "taller": "  "},
        {**VALID, "items": None},
        {**VALID, "items": []},
        {**VALID, "items": [{**VALID["items"][0], "codigo": None}]},
        {**VALID, "items": [{**VALID["items"][0], "precio_unitario": None}]},
    ],
)
def test_missing_essential_fields_are_incomplete(data):
    with pytest.raises(AgentExecutionError) as raised:
        extract(data)

    assert raised.value.code == "INVOICE_INCOMPLETE"
    assert "FAC-001" not in raised.value.message


def test_incomplete_invoice_identifies_the_missing_required_fields():
    data = {**VALID, "siniestro_id": None, "items": [{**VALID["items"][0], "precio_unitario": None}]}

    with pytest.raises(AgentExecutionError) as raised:
        extract(data)

    assert raised.value.code == "INVOICE_INCOMPLETE"
    assert raised.value.message == (
        "No se pudieron extraer los campos obligatorios: siniestro, concepto 1: precio unitario."
    )


def test_demo_invoice_layout_accepts_currency_prefixed_price():
    data = {
        "numero": "FAC-DEMO-002",
        "siniestro_id": "SIN-001",
        "taller": "Taller Aurora",
        "items": [{
            "codigo": "REP-001",
            "descripcion": "Parachoques delantero",
            "cantidad": 1,
            "precio_unitario": "450.00",
        }],
    }

    invoice = extract(data, DEMO_SOURCE)

    assert invoice.numero == "FAC-DEMO-002"
    assert invoice.items[0].precio_unitario == Decimal("450.00")


@pytest.mark.parametrize(
    "field,value",
    [
        ("cantidad", 0),
        ("cantidad", -1),
        ("precio_unitario", "0"),
        ("precio_unitario", "-1"),
    ],
)
def test_nonpositive_item_numbers_are_invalid(field, value):
    data = {**VALID, "items": [{**VALID["items"][0], field: value}]}

    with pytest.raises(AgentExecutionError) as raised:
        extract(data)

    assert raised.value.code == "INVOICE_INVALID"


@pytest.mark.parametrize(
    "data",
    [
        {**VALID, "numero": "FAC-999"},
        {**VALID, "items": [{**VALID["items"][0], "precio_unitario": "451.00"}]},
        {**VALID, "items": [{**VALID["items"][0], "cantidad": 3}]},
    ],
)
def test_invented_mandatory_values_are_unverified(data):
    with pytest.raises(AgentExecutionError) as raised:
        extract(data)

    assert raised.value.code == "INVOICE_UNVERIFIED"
    assert "FAC-999" not in raised.value.message


@pytest.mark.parametrize(
    "text",
    [
        SOURCE.replace("2 450,00", "-2 450,00"),
        SOURCE.replace("2 450,00", "2 -450,00"),
        SOURCE.replace("2 450,00", "450,00").replace("FAC-001", "FAC-002").replace("SIN-001", "SIN-002"),
    ],
)
def test_negative_numbers_or_id_digits_do_not_verify_positive_values(text):
    data = {**VALID, "numero": "FAC-002", "siniestro_id": "SIN-002"} if "FAC-002" in text else VALID

    with pytest.raises(AgentExecutionError) as raised:
        extract(data, text)

    assert raised.value.code == "INVOICE_UNVERIFIED"


@pytest.mark.parametrize(
    "text",
    [
        SOURCE.replace("2 450,00", "−2 450,00"),
        SOURCE.replace("2 450,00", "450,00").replace("FAC-001", "FAC/002").replace("SIN-001", "SIN/002"),
    ],
)
def test_unicode_minus_or_slash_id_cannot_verify_quantity(text):
    data = {**VALID, "numero": "FAC/002", "siniestro_id": "SIN/002"} if "FAC/002" in text else VALID

    with pytest.raises(AgentExecutionError) as raised:
        extract(data, text)

    assert raised.value.code == "INVOICE_UNVERIFIED"


def test_whitespace_delimited_numbers_verify_valid_invoice():
    invoice = extract(VALID, SOURCE)

    assert invoice.items[0].cantidad == 2
    assert invoice.items[0].precio_unitario == Decimal("450.00")


@pytest.mark.parametrize(
    "field,value",
    [
        ("cantidad", 2.5),
        ("cantidad", "2"),
        ("precio_unitario", "abc"),
    ],
)
def test_semantically_invalid_model_values_are_invoice_invalid(field, value):
    data = {**VALID, "items": [{**VALID["items"][0], field: value}]}

    with pytest.raises(AgentExecutionError) as raised:
        extract(data)

    assert raised.value.code == "INVOICE_INVALID"


def test_model_error_propagates_without_exposing_source():
    failure = AgentExecutionError("MODEL_UNAVAILABLE", "No se pudo contactar al modelo.")

    with pytest.raises(AgentExecutionError) as raised:
        InvoiceExtractor(FakeClient(error=failure)).extract(SOURCE)

    assert raised.value is failure
    assert SOURCE not in raised.value.message

"""The PDF boundary reads embedded text and rejects unsafe inputs."""

from io import BytesIO

import pytest
from pypdf import PdfReader, PdfWriter

from backend.agent.errors import AgentExecutionError
from backend.agent.extractors.pdf_extractor import extract_pdf_text
from pdf_fixture import make_blank_pdf, make_pdf_pages, make_text_pdf


def assert_pdf_error(data: object, code: str) -> None:
    with pytest.raises(AgentExecutionError) as raised:
        extract_pdf_text(data)
    assert raised.value.code == code
    assert raised.value.message
    assert "FAC-SECRET" not in raised.value.message


def test_extracts_embedded_invoice_text() -> None:
    text = "Factura FAC-001 Taller Demo 1 pieza 450"

    assert extract_pdf_text(make_text_pdf(text)) == text


def test_rejects_blank_page() -> None:
    assert_pdf_error(make_blank_pdf(), "PDF_NO_TEXT")


@pytest.mark.parametrize("data", [b"", b"not a PDF", "not bytes", None])
def test_rejects_non_pdf_input(data: object) -> None:
    assert_pdf_error(data, "PDF_INVALID")


def test_rejects_malformed_xref() -> None:
    pdf = make_text_pdf("FAC-SECRET")
    assert_pdf_error(pdf[:pdf.index(b"xref\n")], "PDF_INVALID")


def test_rejects_malformed_pdf_header() -> None:
    assert_pdf_error(b"%PDF-broken\n%%EOF", "PDF_INVALID")


def test_rejects_encrypted_pdf() -> None:
    writer = PdfWriter()
    writer.append_pages_from_reader(PdfReader(BytesIO(make_text_pdf("FAC-SECRET"))))
    writer.encrypt("synthetic-password")
    output = BytesIO()
    writer.write(output)

    assert_pdf_error(output.getvalue(), "PDF_ENCRYPTED")


def test_rejects_oversized_input() -> None:
    assert_pdf_error(b"%PDF-1.4\n" + b"x" * (5 * 1024 * 1024), "PDF_TOO_LARGE")


def test_rejects_more_than_twenty_pages() -> None:
    assert_pdf_error(make_pdf_pages(["page"] * 21), "PDF_TOO_MANY_PAGES")


def test_accepts_twenty_pages() -> None:
    assert extract_pdf_text(make_pdf_pages(["page"] * 20)) == "\n".join(["page"] * 20)


def test_rejects_more_than_thirty_thousand_extracted_characters() -> None:
    assert_pdf_error(make_text_pdf("A" * 30_001), "PDF_TEXT_TOO_LONG")


def test_accepts_thirty_thousand_extracted_characters() -> None:
    assert extract_pdf_text(make_text_pdf("A" * 30_000)) == "A" * 30_000


def test_counts_page_separators_toward_text_limit() -> None:
    assert_pdf_error(make_pdf_pages(["A" * 15_000, "B" * 15_000]), "PDF_TEXT_TOO_LONG")


def test_rejects_small_compressed_pdf_with_oversized_page_content() -> None:
    pdf = make_pdf_pages(["invoice"], compressed_padding=1024 * 1024)
    assert len(pdf) < 5 * 1024 * 1024

    assert_pdf_error(pdf, "PDF_TOO_LARGE")

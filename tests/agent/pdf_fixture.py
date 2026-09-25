"""Small, valid PDFs with byte-accurate cross-reference offsets for tests."""

import zlib


def make_text_pdf(text: str) -> bytes:
    return make_pdf_pages([text])


def make_blank_pdf() -> bytes:
    return make_pdf_pages([None])


def make_pdf_pages(page_texts: list[str | None], *, compressed_padding: int = 0) -> bytes:
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids ["
        + b" ".join(f"{4 + 2 * index} 0 R".encode("ascii") for index in range(len(page_texts)))
        + b"] /Count "
        + str(len(page_texts)).encode("ascii")
        + b" >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for index, text in enumerate(page_texts):
        content_id = 5 + 2 * index
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 3 0 R >> >> "
            + f"/Contents {content_id} 0 R >>".encode("ascii")
        )
        if text is None:
            stream = b""
        else:
            escaped = text.encode("ascii").replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
            stream = b"BT /F1 12 Tf 72 720 Td (" + escaped + b") Tj ET"
        if compressed_padding:
            stream += b"\n%" + b"A" * compressed_padding + b"\n"
            stream = zlib.compress(stream)
            filter_entry = b" /Filter /FlateDecode"
        else:
            filter_entry = b""
        objects.append(
            b"<< /Length " + str(len(stream)).encode("ascii") + filter_entry + b" >>\nstream\n"
            + stream + b"\nendstream"
        )

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode("ascii"))
        pdf.extend(body)
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        b"trailer\n<< /Size " + str(len(offsets)).encode("ascii")
        + b" /Root 1 0 R >>\nstartxref\n"
        + str(xref_offset).encode("ascii") + b"\n%%EOF\n"
    )
    return bytes(pdf)

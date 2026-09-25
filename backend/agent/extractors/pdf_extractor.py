"""Extract embedded PDF text without exposing uploaded content in errors."""

from io import BytesIO

from pypdf import PdfReader

from backend.agent.errors import AgentExecutionError


MAX_PDF_BYTES = 5 * 1024 * 1024
MAX_PAGES = 20
MAX_TEXT_CHARACTERS = 30_000


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Return embedded text from a small, unencrypted PDF."""
    if not isinstance(pdf_bytes, bytes) or not pdf_bytes.startswith(b"%PDF-"):
        raise AgentExecutionError("PDF_INVALID", "El archivo no es un PDF válido.")
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise AgentExecutionError("PDF_TOO_LARGE", "El PDF supera el tamaño permitido.")

    try:
        reader = PdfReader(BytesIO(pdf_bytes), strict=True)
        if reader.is_encrypted:
            raise AgentExecutionError("PDF_ENCRYPTED", "El PDF está cifrado.")
        if len(reader.pages) > MAX_PAGES:
            raise AgentExecutionError("PDF_TOO_MANY_PAGES", "El PDF tiene demasiadas páginas.")

        parts = []
        length = 0
        for page in reader.pages:
            part = page.extract_text() or ""
            length += len(part) + (1 if parts else 0)
            if length > MAX_TEXT_CHARACTERS:
                raise AgentExecutionError("PDF_TEXT_TOO_LONG", "El texto del PDF es demasiado largo.")
            parts.append(part)
    except AgentExecutionError:
        raise
    except Exception as exc:
        raise AgentExecutionError("PDF_INVALID", "El archivo no es un PDF válido.") from exc

    text = "\n".join(parts)
    if not text.strip():
        raise AgentExecutionError("PDF_NO_TEXT", "El PDF no contiene texto extraíble.")
    return text

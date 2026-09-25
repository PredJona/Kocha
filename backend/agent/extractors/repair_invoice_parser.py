"""Deterministic parser for the text layout used by repair invoices in the demo."""

import re
import unicodedata
from decimal import Decimal, InvalidOperation


_ITEM_CODE = re.compile(r"[A-Z]{2,4}-[0-9]{3,}")
_QUANTITY = re.compile(r"([0-9]+)(?:\s*[A-Za-z]+)?")
_MONEY = re.compile(r"B/\.\s*([0-9]+(?:[.,][0-9]+)?)", re.IGNORECASE)


def _key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).casefold()
    return "".join(character for character in normalized if not unicodedata.combining(character)).strip()


def _value_after(lines: list[str], labels: set[str], value_pattern: re.Pattern[str] | None = None) -> str | None:
    for index, line in enumerate(lines[:-1]):
        if _key(line) not in labels:
            continue
        value = lines[index + 1]
        if value_pattern is None or value_pattern.fullmatch(value):
            return value
    return None


def _price(value: str) -> str | None:
    match = _MONEY.fullmatch(value)
    if not match:
        return None
    token = match.group(1).replace(",", ".")
    try:
        return f"{Decimal(token):.2f}"
    except InvalidOperation:
        return None


def parse_repair_invoice_text(text: str) -> dict[str, object] | None:
    """Return invoice-shaped data for the known repair table, otherwise ``None``."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    keys = [_key(line) for line in lines]
    if "detalle de reparacion" not in keys or "subtotal" not in keys:
        return None

    numero = _value_after(
        lines,
        {"factura n.o", "factura no", "factura nº", "factura n.º"},
        re.compile(r"FAC-[A-Za-z0-9-]+", re.IGNORECASE),
    )
    siniestro_id = _value_after(lines, {"reclamo", "siniestro", "claim"})
    detail_index = keys.index("detalle de reparacion")
    subtotal_index = keys.index("subtotal", detail_index)
    taller = lines[0] if detail_index > 0 else None

    items: list[dict[str, object]] = []
    index = detail_index + 1
    while index < subtotal_index:
        if not _ITEM_CODE.fullmatch(lines[index]) or index + 4 >= subtotal_index:
            index += 1
            continue
        quantity_match = _QUANTITY.fullmatch(lines[index + 2])
        unit_price = _price(lines[index + 3])
        line_total = _price(lines[index + 4])
        if quantity_match and unit_price is not None and line_total is not None:
            items.append(
                {
                    "codigo": lines[index],
                    "descripcion": lines[index + 1],
                    "cantidad": int(quantity_match.group(1)),
                    "precio_unitario": unit_price,
                }
            )
            index += 5
            continue
        index += 1

    if not numero or not siniestro_id or not taller or not items:
        return None
    return {"numero": numero, "siniestro_id": siniestro_id, "taller": taller, "items": items}

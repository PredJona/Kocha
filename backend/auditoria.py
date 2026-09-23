from collections import Counter

from backend.database import (
    convertir_a_centavos,
    obtener_siniestro,
    obtener_tarifa,
)


def auditar_factura(factura):
    inconsistencias = []

    validar_items_duplicados(
        factura,
        inconsistencias
    )

    siniestro = obtener_siniestro(
        factura.siniestro_id
    )

    # -------------------------
    # Validar siniestro
    # -------------------------

    if siniestro is None:
        inconsistencias.append({
            "tipo": "SINIESTRO_NO_ENCONTRADO",
            "siniestro_id": factura.siniestro_id,
            "mensaje": (
                "El siniestro indicado no existe."
            )
        })

        return inconsistencias

    # -------------------------
    # Revisar cada ítem
    # -------------------------

    for item in factura.items:

        validar_tarifa(
            item,
            inconsistencias
        )

        validar_item_siniestro(
            item,
            siniestro,
            inconsistencias
        )

    return inconsistencias


def validar_items_duplicados(
    factura,
    inconsistencias
):
    codigos = [
        item.codigo
        for item in factura.items
    ]

    conteo = Counter(codigos)

    for codigo, cantidad in conteo.items():

        if cantidad > 1:
            inconsistencias.append({
                "tipo": "ITEM_DUPLICADO",
                "codigo": codigo,
                "cantidad_apariciones": cantidad,
                "mensaje": (
                    "El ítem aparece más de una vez "
                    "en la factura."
                )
            })


def validar_tarifa(
    item,
    inconsistencias
):
    tarifa = obtener_tarifa(
        item.codigo
    )

    if tarifa is None:
        inconsistencias.append({
            "tipo": "ITEM_SIN_TARIFA",
            "codigo": item.codigo,
            "descripcion": item.descripcion,
            "mensaje": (
                "El ítem no existe "
                "en el tarifario."
            )
        })

        return

    precio_facturado = convertir_a_centavos(
        item.precio_unitario
    )

    precio_maximo = tarifa[
        "precio_maximo_centavos"
    ]

    if precio_facturado > precio_maximo:
        inconsistencias.append({
            "tipo": "PRECIO_SUPERA_TARIFA",
            "codigo": item.codigo,
            "descripcion": item.descripcion,
            "precio_facturado": (
                f"{precio_facturado / 100:.2f}"
            ),
            "precio_maximo": (
                f"{precio_maximo / 100:.2f}"
            ),
            "mensaje": (
                "El precio facturado supera "
                "el tarifario acordado."
            )
        })


def validar_item_siniestro(
    item,
    siniestro,
    inconsistencias
):
    if (
        item.codigo
        not in siniestro["items_autorizados"]
    ):
        inconsistencias.append({
            "tipo": (
                "ITEM_NO_CORRESPONDE_SINIESTRO"
            ),
            "codigo": item.codigo,
            "descripcion": item.descripcion,
            "mensaje": (
                "El ítem facturado no corresponde "
                "al siniestro reportado."
            )
        })
        
from backend.database import obtener_tarifa, convertir_a_centavos


def auditar_factura(factura):
    inconsistencias = []

    for item in factura.items:
        tarifa = obtener_tarifa(item.codigo)

        if tarifa is None:
            inconsistencias.append({
                "tipo": "ITEM_SIN_TARIFA",
                "codigo": item.codigo,
                "descripcion": item.descripcion,
                "mensaje": "El ítem no existe en el tarifario."
            })

            continue

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

    return inconsistencias
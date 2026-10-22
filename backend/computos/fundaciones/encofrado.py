"""Cómputo trazable del encofrado lateral de zapatas."""

from decimal import Decimal


NOMBRES_CARAS_LATERALES = ("X1", "X2", "Y1", "Y2")


def _crear_cara(nombre, largo, alto, incluida):
    """Construye el detalle verificable de una cara lateral."""

    area_geometrica = largo * alto
    area_computable = (
        area_geometrica
        if incluida
        else Decimal("0")
    )

    return {
        "cara": nombre,
        "largo_m": largo,
        "alto_m": alto,
        "formula": "largo × alto",
        "sustitucion": f"{largo} × {alto}",
        "area_geometrica_m2": area_geometrica,
        "incluida_en_computo": incluida,
        "area_m2": area_computable,
    }


def _crear_elementos_individuales(
    referencia,
    cantidad,
    area_unitaria,
):
    """
    Genera identificadores internos para cada aparición.

    Estos identificadores todavía no representan ejes del plano.
    Posteriormente podrán vincularse con la posición detectada.
    """

    return [
        {
            "identificador": f"{referencia}-{numero:02d}",
            "referencia": referencia,
            "numero": numero,
            "area_encofrado_esperada_m2": area_unitaria,
            "ubicacion_confirmada": False,
        }
        for numero in range(1, cantidad + 1)
    ]


def calcular_encofrado_zapatas(
    dimensiones,
    conteo,
    usar_encofrado=True,
):
    """
    Calcula el área de las cuatro caras laterales.

    Fórmula general:

        A = 2 × (X + Y) × h

    El detalle permite verificar:

    - cada una de las cuatro caras;
    - el área unitaria;
    - la cantidad de fundaciones;
    - el total por referencia;
    - la igualdad entre caras, unidades y total.
    """

    resultados = []
    total = Decimal("0")

    for fundacion in dimensiones:
        referencia = fundacion["referencia"]

        if referencia not in conteo:
            raise ValueError(
                f"No existe cantidad detectada para {referencia}."
            )

        cantidad = int(conteo[referencia])
        x = fundacion["x"]
        y = fundacion["y"]
        h = fundacion["h"]

        if cantidad < 0:
            raise ValueError(
                f"La cantidad de {referencia} no puede ser negativa."
            )

        if x <= 0 or y <= 0 or h <= 0:
            raise ValueError(
                f"Las dimensiones de {referencia} deben ser positivas."
            )

        caras = [
            _crear_cara(
                nombre="X1",
                largo=x,
                alto=h,
                incluida=usar_encofrado,
            ),
            _crear_cara(
                nombre="X2",
                largo=x,
                alto=h,
                incluida=usar_encofrado,
            ),
            _crear_cara(
                nombre="Y1",
                largo=y,
                alto=h,
                incluida=usar_encofrado,
            ),
            _crear_cara(
                nombre="Y2",
                largo=y,
                alto=h,
                incluida=usar_encofrado,
            ),
        ]

        area_unitaria = sum(
            (
                cara["area_m2"]
                for cara in caras
            ),
            Decimal("0"),
        )

        area_formula = (
            Decimal("2") * (x + y) * h
            if usar_encofrado
            else Decimal("0")
        )

        area_total = (
            area_unitaria * Decimal(cantidad)
        )

        elementos = _crear_elementos_individuales(
            referencia=referencia,
            cantidad=cantidad,
            area_unitaria=area_unitaria,
        )

        suma_elementos = sum(
            (
                elemento["area_encofrado_esperada_m2"]
                for elemento in elementos
            ),
            Decimal("0"),
        )

        resultados.append(
            {
                # Identificación
                "referencia": referencia,
                "cantidad": cantidad,

                # Dimensiones utilizadas
                "dimensiones_m": {
                    "x": x,
                    "y": y,
                    "h": h,
                },

                # Criterio técnico
                "criterio": {
                    "descripcion": (
                        "Cuatro caras laterales de la zapata."
                        if usar_encofrado
                        else "Encofrado desactivado para el proyecto."
                    ),
                    "caras_incluidas": (
                        list(NOMBRES_CARAS_LATERALES)
                        if usar_encofrado
                        else []
                    ),
                    "caras_excluidas": [
                        "base",
                        "cara_superior",
                    ],
                },

                # Trazabilidad de la fórmula
                "formula": {
                    "expresion": "2 × (X + Y) × h",
                    "sustitucion": (
                        f"2 × ({x} + {y}) × {h}"
                    ),
                    "resultado_m2": area_formula,
                },

                # Desglose de las caras
                "caras": caras,

                # Resultados existentes
                "area_unitaria_m2": area_unitaria,
                "area_total_m2": area_total,

                # Elementos individuales
                "elementos": elementos,

                # Validaciones internas
                "comprobaciones": {
                    "area_formula_m2": area_formula,
                    "suma_caras_m2": area_unitaria,
                    "suma_elementos_m2": suma_elementos,
                    "formula_coincide_con_caras": (
                        area_formula == area_unitaria
                    ),
                    "elementos_coinciden_con_total": (
                        suma_elementos == area_total
                    ),
                    "estado": (
                        "verificado"
                        if (
                            area_formula == area_unitaria
                            and suma_elementos == area_total
                        )
                        else "inconsistente"
                    ),
                },
            }
        )

        total += area_total

    return resultados, total
"""Cálculos determinísticos de acero para columnas validadas.

Este módulo no decide qué armadura corresponde a cada referencia. Recibe
armaduras previamente detectadas y confirmadas por un profesional, junto con
alturas reales ya validadas. Si falta alguno de esos datos, se detiene sin
inventar longitudes ni cantidades.
"""

from __future__ import annotations

from collections import defaultdict
from fractions import Fraction
from math import ceil


def _numero(valor, predeterminado=None):
    if valor is None:
        return predeterminado

    try:
        return float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return predeterminado


def _referencia(fila):
    return str(
        fila.get("referencia")
        or fila.get("referencia_columna")
        or fila.get("referencia_columna_vinculada")
        or ""
    ).strip().upper()


def _clave_referencia(referencia):
    texto = str(referencia or "")
    prefijo = "".join(
        caracter
        for caracter in texto
        if not caracter.isdigit()
    )
    numero = "".join(
        caracter
        for caracter in texto
        if caracter.isdigit()
    )
    return (
        prefijo,
        int(numero) if numero else 0,
        texto,
    )


def _clave_diametro(diametro):
    try:
        return (0, float(Fraction(str(diametro))))
    except (ValueError, ZeroDivisionError):
        return (1, str(diametro))


def _datos_diametro(valor):
    texto = "".join(str(valor or "").split())

    try:
        pulgadas = float(Fraction(texto))
    except (ValueError, ZeroDivisionError):
        return None

    if pulgadas <= 0:
        return None

    diametro_mm = pulgadas * 25.4
    return {
        "diametro_pulgadas": texto,
        "diametro_mm": round(diametro_mm, 3),
        "peso_unitario_kg_m": round(
            diametro_mm**2 / 162,
            3,
        ),
    }


def _validar_armadura(referencia, armadura):
    problemas = []

    if not isinstance(armadura, dict):
        return ["no tiene una armadura detectada"]

    if armadura.get("estado") != "CORRECTO":
        problemas.append(
            "la armadura detectada todavía requiere revisión"
        )

    grupos = armadura.get("grupos_longitudinales")

    if not isinstance(grupos, list) or not grupos:
        problemas.append(
            "no tiene barras longitudinales completas"
        )
    else:
        for grupo in grupos:
            cantidad = _numero(grupo.get("cantidad"))
            diametro = _datos_diametro(
                grupo.get("diametro_pulgadas")
            )

            if cantidad is None or cantidad <= 0 or diametro is None:
                problemas.append(
                    "contiene un grupo longitudinal incompleto"
                )
                break

    estribo = armadura.get("estribo")

    if not isinstance(estribo, dict):
        problemas.append("no tiene estribos completos")
    else:
        if _datos_diametro(
            estribo.get("diametro_pulgadas")
        ) is None:
            problemas.append(
                "no tiene diámetro de estribo válido"
            )

        if (_numero(estribo.get("separacion_m")) or 0) <= 0:
            problemas.append(
                "no tiene separación de estribos válida"
            )

        if (
            _numero(estribo.get("longitud_indicada_m"))
            or 0
        ) <= 0:
            problemas.append(
                "no tiene longitud indicada para cada estribo"
            )

    return [
        f"{referencia}: {problema}"
        for problema in problemas
    ]


def calcular_acero_columnas(
    columnas,
    armaduras,
    *,
    referencias_confirmadas=None,
    longitud_adicional_por_extremo_m=0.0,
):
    """Calcula acero solo con alturas y armaduras confirmadas.

    La barra longitudinal utiliza ``altura + 2 × adicional por extremo``.
    La cantidad de estribos es ``ceil(altura / separación) + 1`` y su
    longitud unitaria debe estar indicada en el detalle estructural.
    """

    filas = [
        dict(fila)
        for fila in columnas or []
        if isinstance(fila, dict)
    ]

    if not filas:
        raise ValueError(
            "No hay columnas con geometría validada para calcular acero."
        )

    adicional = _numero(
        longitud_adicional_por_extremo_m,
        0.0,
    )

    if adicional is None or adicional < 0 or adicional > 10:
        raise ValueError(
            "La longitud adicional por extremo debe estar entre 0 y 10 m."
        )

    referencias = {
        _referencia(fila)
        for fila in filas
        if _referencia(fila)
    }
    confirmadas = {
        str(referencia or "").strip().upper()
        for referencia in (
            referencias_confirmadas
            if referencias_confirmadas is not None
            else referencias
        )
        if str(referencia or "").strip()
    }
    faltan_confirmar = sorted(
        referencias - confirmadas,
        key=_clave_referencia,
    )

    if faltan_confirmar:
        raise ValueError(
            "Falta confirmar la armadura de: "
            + ", ".join(faltan_confirmar)
            + "."
        )

    por_referencia = {
        _referencia(armadura): armadura
        for armadura in armaduras or []
        if isinstance(armadura, dict)
        and _referencia(armadura)
    }
    problemas = []

    for referencia in sorted(
        referencias,
        key=_clave_referencia,
    ):
        problemas.extend(
            _validar_armadura(
                referencia,
                por_referencia.get(referencia),
            )
        )

    for fila in filas:
        referencia = _referencia(fila)
        altura = _numero(fila.get("altura_m"))

        if altura is None or altura <= 0:
            problemas.append(
                f"{referencia or 'Columna'}: falta la altura real validada"
            )

    if problemas:
        raise ValueError(
            "No se puede calcular el acero de columnas. "
            + " ".join(dict.fromkeys(problemas))
        )

    detalle = []
    acumulado_diametros = defaultdict(
        lambda: {
            "metros_longitudinales": 0.0,
            "metros_estribos": 0.0,
            "peso_kg": 0.0,
        }
    )

    for indice, fila in enumerate(filas, start=1):
        referencia = _referencia(fila)
        altura = _numero(fila.get("altura_m"))
        armadura = por_referencia[referencia]
        longitud_barra = altura + 2 * adicional
        por_diametro = defaultdict(
            lambda: {
                "metros_longitudinales": 0.0,
                "metros_estribos": 0.0,
                "peso_kg": 0.0,
            }
        )
        metros_longitudinales = 0.0
        peso_longitudinal = 0.0

        for grupo in armadura["grupos_longitudinales"]:
            cantidad = int(_numero(grupo["cantidad"]))
            diametro = _datos_diametro(
                grupo["diametro_pulgadas"]
            )
            metros = cantidad * longitud_barra
            peso = metros * diametro["peso_unitario_kg_m"]
            clave = diametro["diametro_pulgadas"]

            metros_longitudinales += metros
            peso_longitudinal += peso
            por_diametro[clave][
                "metros_longitudinales"
            ] += metros
            por_diametro[clave]["peso_kg"] += peso

        estribo = armadura["estribo"]
        datos_estribo = _datos_diametro(
            estribo["diametro_pulgadas"]
        )
        separacion = _numero(estribo["separacion_m"])
        longitud_estribo = _numero(
            estribo["longitud_indicada_m"]
        )
        cantidad_estribos = max(
            2,
            ceil(altura / separacion) + 1,
        )
        metros_estribos = cantidad_estribos * longitud_estribo
        peso_estribos = (
            metros_estribos
            * datos_estribo["peso_unitario_kg_m"]
        )
        clave_estribo = datos_estribo[
            "diametro_pulgadas"
        ]
        por_diametro[clave_estribo][
            "metros_estribos"
        ] += metros_estribos
        por_diametro[clave_estribo][
            "peso_kg"
        ] += peso_estribos
        acero_por_diametro = []

        for diametro, datos in sorted(
            por_diametro.items(),
            key=lambda item: _clave_diametro(item[0]),
        ):
            registro = {
                "diametro_pulgadas": diametro,
                "metros_longitudinales": round(
                    datos["metros_longitudinales"],
                    3,
                ),
                "metros_estribos": round(
                    datos["metros_estribos"],
                    3,
                ),
                "metros_totales": round(
                    datos["metros_longitudinales"]
                    + datos["metros_estribos"],
                    3,
                ),
                "peso_kg": round(datos["peso_kg"], 3),
            }
            acero_por_diametro.append(registro)
            acumulado_diametros[diametro][
                "metros_longitudinales"
            ] += datos["metros_longitudinales"]
            acumulado_diametros[diametro][
                "metros_estribos"
            ] += datos["metros_estribos"]
            acumulado_diametros[diametro][
                "peso_kg"
            ] += datos["peso_kg"]

        peso_total = peso_longitudinal + peso_estribos
        detalle.append(
            {
                **fila,
                "columna_id": (
                    fila.get("columna_id")
                    or f"{referencia}-{indice:02d}"
                ),
                "referencia": referencia,
                "armadura_columna": armadura,
                "longitud_barra_longitudinal_m": round(
                    longitud_barra,
                    3,
                ),
                "longitud_adicional_por_extremo_m": round(
                    adicional,
                    3,
                ),
                "metros_barras_longitudinales": round(
                    metros_longitudinales,
                    3,
                ),
                "peso_barras_longitudinales_kg": round(
                    peso_longitudinal,
                    3,
                ),
                "cantidad_estribos": cantidad_estribos,
                "longitud_unidad_estribo_m": round(
                    longitud_estribo,
                    3,
                ),
                "metros_estribos": round(
                    metros_estribos,
                    3,
                ),
                "peso_estribos_kg": round(
                    peso_estribos,
                    3,
                ),
                "peso_acero_total_kg": round(
                    peso_total,
                    3,
                ),
                "acero_por_diametro": acero_por_diametro,
                "estado_acero": "computado",
                "estado": "computado_con_revision_profesional",
            }
        )

    grupos_resumen = defaultdict(list)

    for fila in detalle:
        grupos_resumen[
            (
                fila["referencia"],
                _numero(fila.get("ancho_m")),
                _numero(fila.get("largo_m")),
                _numero(fila.get("altura_m")),
            )
        ].append(fila)

    resumen_por_tipo = []

    for clave, elementos in sorted(
        grupos_resumen.items(),
        key=lambda item: _clave_referencia(
            item[0][0]
        ),
    ):
        referencia, ancho, largo, altura = clave
        resumen_por_tipo.append(
            {
                "referencia": referencia,
                "ancho_m": ancho,
                "largo_m": largo,
                "altura_m": altura,
                "cantidad": len(elementos),
                "volumen_total_m3": round(
                    sum(
                        _numero(
                            fila.get("volumen_total_m3"),
                            0.0,
                        )
                        for fila in elementos
                    ),
                    3,
                ),
                "encofrado_total_m2": round(
                    sum(
                        _numero(
                            fila.get("encofrado_total_m2"),
                            0.0,
                        )
                        for fila in elementos
                    ),
                    3,
                ),
                "peso_acero_total_kg": round(
                    sum(
                        fila["peso_acero_total_kg"]
                        for fila in elementos
                    ),
                    3,
                ),
            }
        )

    resumen_acero = [
        {
            "diametro_pulgadas": diametro,
            "metros_longitudinales": round(
                datos["metros_longitudinales"],
                3,
            ),
            "metros_estribos": round(
                datos["metros_estribos"],
                3,
            ),
            "metros_totales": round(
                datos["metros_longitudinales"]
                + datos["metros_estribos"],
                3,
            ),
            "peso_kg": round(datos["peso_kg"], 3),
        }
        for diametro, datos in sorted(
            acumulado_diametros.items(),
            key=lambda item: _clave_diametro(item[0]),
        )
    ]

    return {
        "detalles": detalle,
        "resumen_por_tipo": resumen_por_tipo,
        "resumen_acero": resumen_acero,
        "acero_total_kg": round(
            sum(
                fila["peso_acero_total_kg"]
                for fila in detalle
            ),
            3,
        ),
        "referencias_confirmadas": sorted(
            referencias,
            key=_clave_referencia,
        ),
        "longitud_adicional_por_extremo_m": round(
            adicional,
            3,
        ),
        "criterio_longitudinal": (
            "altura_real_mas_adicional_por_extremo"
        ),
        "criterio_estribos": (
            "ceil_altura_sobre_separacion_mas_uno"
        ),
    }

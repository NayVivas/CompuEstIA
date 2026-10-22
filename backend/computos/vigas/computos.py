"""Cómputos métricos de vigas de riostra a partir del plano vectorial.

El módulo no interpreta puntos PDF como metros directamente. Primero obtiene
una escala a partir de cadenas de cotas alineadas (o utiliza una escala
configurada explícitamente), relaciona cada eje vectorial con un único rótulo
de viga y recién entonces calcula longitudes, hormigón y encofrado.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from fractions import Fraction
from math import ceil, hypot
import re
from statistics import median

from computos.vigas.riostra import (
    detectar_apoyos_columnas_vectoriales,
    reconstruir_tramos_vigas_entre_apoyos,
)


PATRON_COTA_METROS = re.compile(
    r"^\d{1,3}[,.]\d{1,3}$"
)

PATRON_TITULO_VIGA_RIOSTRA = re.compile(
    r"VIGA\s+DE\s+RIOSTRA\s*(\d+)"
    r".*?V\s*\.?\s*R\s*\.?\s*(\d+)",
    re.IGNORECASE,
)

PATRON_BARRAS_LONGITUDINALES = re.compile(
    r"=\s*(\d+)\s*[ØΦ]\s*"
    r"(\d+(?:\s*/\s*\d+)?)\s*[\"”]?",
    re.IGNORECASE,
)

PATRON_ESTRIBOS = re.compile(
    r"EST\.?\s*[ØΦ]\s*"
    r"(\d+(?:\s*/\s*\d+)?)\s*[\"”]?"
    r"\s*C\s*/?\s*D\s*"
    r"(\d+(?:[,.]\d+)?)\s*CM(?:S)?\.?.*?"
    r"L\s*=\s*(\d+(?:[,.]\d+)?)\s*M",
    re.IGNORECASE,
)

PATRON_DIMENSION_SECCION = re.compile(
    r"^0[,.]\d{2}$"
)


def _numero(valor, predeterminado=None):
    if valor is None:
        return predeterminado

    try:
        return float(valor)
    except (TypeError, ValueError):
        return predeterminado


def _valor_campo(objeto, campo, predeterminado=None):
    if isinstance(objeto, dict):
        return objeto.get(campo, predeterminado)

    return getattr(objeto, campo, predeterminado)


def _coordenada_palabra(palabra, campo):
    """Lee coordenadas planas y también ``caja_pdf`` anidada."""

    valor = _valor_campo(palabra, campo)

    if valor is not None:
        return _numero(valor)

    caja = _valor_campo(palabra, "caja_pdf")

    if caja is None:
        return None

    return _numero(
        _valor_campo(caja, campo)
    )


def _normalizar_diametro_pulgadas(valor):
    return re.sub(
        r"\s+",
        "",
        str(valor).strip(),
    )


def _datos_diametro(valor):
    """Normaliza un diámetro nominal expresado en pulgadas."""

    texto = _normalizar_diametro_pulgadas(
        valor
    )

    try:
        pulgadas = float(Fraction(texto))
    except (ValueError, ZeroDivisionError):
        return None

    if pulgadas <= 0:
        return None

    diametro_mm = pulgadas * 25.4

    # Relación usual para barras corrugadas:
    # peso [kg/m] = diámetro [mm]² / 162.
    peso_unitario = diametro_mm**2 / 162

    return {
        "diametro_pulgadas": texto,
        "diametro_mm": round(diametro_mm, 3),
        "peso_unitario_kg_m": round(
            peso_unitario,
            3,
        ),
    }


def _agrupar_palabras_en_lineas(palabras):
    """Reconstruye líneas usando los identificadores nativos del PDF."""

    grupos = defaultdict(list)

    for indice, palabra in enumerate(palabras):
        texto = str(
            _valor_campo(
                palabra,
                "texto",
                "",
            )
        ).strip()

        if not texto:
            continue

        pagina = int(
            _numero(
                _valor_campo(
                    palabra,
                    "pagina",
                    1,
                ),
                1,
            )
        )

        bloque = _valor_campo(
            palabra,
            "numero_bloque",
            _valor_campo(
                palabra,
                "bloque",
            ),
        )
        linea = _valor_campo(
            palabra,
            "numero_linea",
            _valor_campo(
                palabra,
                "linea",
            ),
        )
        posicion = _valor_campo(
            palabra,
            "numero_palabra",
            _valor_campo(
                palabra,
                "posicion",
                indice,
            ),
        )

        if bloque is None or linea is None:
            clave = (
                pagina,
                "palabra",
                indice,
            )
        else:
            clave = (
                pagina,
                int(_numero(bloque, 0)),
                int(_numero(linea, 0)),
            )

        grupos[clave].append(
            {
                "texto": texto,
                "posicion": int(
                    _numero(posicion, indice)
                ),
                "x0": _coordenada_palabra(
                    palabra,
                    "x0",
                ),
                "y0": _coordenada_palabra(
                    palabra,
                    "y0",
                ),
                "x1": _coordenada_palabra(
                    palabra,
                    "x1",
                ),
                "y1": _coordenada_palabra(
                    palabra,
                    "y1",
                ),
            }
        )

    resultado = []

    for clave, palabras_linea in grupos.items():
        coordenadas_validas = [
            palabra
            for palabra in palabras_linea
            if None
            not in (
                palabra["x0"],
                palabra["y0"],
                palabra["x1"],
                palabra["y1"],
            )
        ]

        if not coordenadas_validas:
            continue

        palabras_ordenadas = sorted(
            palabras_linea,
            key=lambda palabra: palabra[
                "posicion"
            ],
        )

        x0 = min(
            palabra["x0"]
            for palabra in coordenadas_validas
        )
        y0 = min(
            palabra["y0"]
            for palabra in coordenadas_validas
        )
        x1 = max(
            palabra["x1"]
            for palabra in coordenadas_validas
        )
        y1 = max(
            palabra["y1"]
            for palabra in coordenadas_validas
        )

        resultado.append(
            {
                "pagina": clave[0],
                "texto": " ".join(
                    palabra["texto"]
                    for palabra in palabras_ordenadas
                ),
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
                "centro_x": (x0 + x1) / 2,
                "centro_y": (y0 + y1) / 2,
            }
        )

    return resultado


def extraer_armaduras_vigas_riostra(
    palabras,
    *,
    origen=None,
    distancia_perpendicular_maxima_pdf=90.0,
    distancia_principal_maxima_pdf=80.0,
):
    """Extrae secciones y armaduras de detalles VR por proximidad espacial.

    La función descubre los títulos ``VIGA DE RIOSTRA n (V.R.n)`` y divide
    cada página en bandas según la dirección dominante de esos títulos. Las
    anotaciones de sección, barras y estribos se asocian únicamente dentro de
    la banda correspondiente.
    """

    lineas = _agrupar_palabras_en_lineas(
        palabras
    )
    titulos_por_pagina = defaultdict(list)

    for linea in lineas:
        coincidencia = (
            PATRON_TITULO_VIGA_RIOSTRA.search(
                linea["texto"]
            )
        )

        if coincidencia is None:
            continue

        numero_titulo = int(
            coincidencia.group(1)
        )
        numero_referencia = int(
            coincidencia.group(2)
        )

        titulos_por_pagina[
            linea["pagina"]
        ].append(
            {
                **linea,
                "referencia": (
                    f"VR{numero_referencia}"
                ),
                "numero_titulo": numero_titulo,
                "coincide_numeracion": (
                    numero_titulo
                    == numero_referencia
                ),
            }
        )

    especificaciones = []

    for pagina, titulos in sorted(
        titulos_por_pagina.items()
    ):
        if not titulos:
            continue

        span_x = (
            max(titulo["centro_x"] for titulo in titulos)
            - min(titulo["centro_x"] for titulo in titulos)
        )
        span_y = (
            max(titulo["centro_y"] for titulo in titulos)
            - min(titulo["centro_y"] for titulo in titulos)
        )
        eje_principal = (
            "x" if span_x > span_y else "y"
        )
        campo_principal = (
            "centro_x"
            if eje_principal == "x"
            else "centro_y"
        )
        campo_perpendicular = (
            "centro_y"
            if eje_principal == "x"
            else "centro_x"
        )

        titulos_ordenados = sorted(
            titulos,
            key=lambda titulo: titulo[
                campo_principal
            ],
        )
        lineas_pagina = [
            linea
            for linea in lineas
            if linea["pagina"] == pagina
        ]
        asignadas = defaultdict(list)

        for linea in lineas_pagina:
            titulo = min(
                titulos_ordenados,
                key=lambda candidato: abs(
                    linea[campo_principal]
                    - candidato[
                        campo_principal
                    ]
                ),
            )

            distancia_principal = abs(
                linea[campo_principal]
                - titulo[campo_principal]
            )

            distancia_perpendicular = abs(
                linea[campo_perpendicular]
                - titulo[campo_perpendicular]
            )

            if (
                distancia_principal
                > distancia_principal_maxima_pdf
                or
                distancia_perpendicular
                > distancia_perpendicular_maxima_pdf
            ):
                continue

            asignadas[
                titulo["referencia"]
            ].append(linea)

        for titulo in titulos_ordenados:
            referencia = titulo["referencia"]
            candidatas = asignadas[
                referencia
            ]

            dimensiones = []
            barras = []
            estribos = []

            for linea in candidatas:
                texto = linea["texto"].strip()
                texto_compacto = re.sub(
                    r"\s+",
                    "",
                    texto,
                )

                if PATRON_DIMENSION_SECCION.fullmatch(
                    texto_compacto
                ):
                    dimensiones.append(
                        {
                            "valor": _numero(
                                texto_compacto.replace(
                                    ",",
                                    ".",
                                )
                            ),
                            "linea": linea,
                        }
                    )

                coincidencia_barra = (
                    PATRON_BARRAS_LONGITUDINALES.search(
                        texto
                    )
                )

                if coincidencia_barra is not None:
                    datos_diametro = _datos_diametro(
                        coincidencia_barra.group(2)
                    )

                    if datos_diametro is not None:
                        barras.append(
                            {
                                "cantidad": int(
                                    coincidencia_barra.group(
                                        1
                                    )
                                ),
                                **datos_diametro,
                                "texto_original": texto,
                            }
                        )

                coincidencia_estribo = (
                    PATRON_ESTRIBOS.search(texto)
                )

                if coincidencia_estribo is not None:
                    datos_diametro = _datos_diametro(
                        coincidencia_estribo.group(1)
                    )

                    if datos_diametro is not None:
                        estribos.append(
                            {
                                **datos_diametro,
                                "separacion_m": (
                                    _numero(
                                        coincidencia_estribo.group(
                                            2
                                        ).replace(
                                            ",",
                                            ".",
                                        )
                                    )
                                    / 100
                                ),
                                "longitud_unidad_m": (
                                    _numero(
                                        coincidencia_estribo.group(
                                            3
                                        ).replace(
                                            ",",
                                            ".",
                                        )
                                    )
                                ),
                                "texto_original": texto,
                            }
                        )

            dimensiones = sorted(
                dimensiones,
                key=lambda dimension: abs(
                    dimension["linea"][
                        campo_principal
                    ]
                    - titulo[campo_principal]
                ),
            )[:2]
            valores_dimension = [
                dimension["valor"]
                for dimension in dimensiones
                if dimension["valor"] is not None
            ]

            if len(valores_dimension) == 2:
                ancho_m = min(valores_dimension)
                alto_m = max(valores_dimension)
            else:
                ancho_m = None
                alto_m = None

            problemas = []

            if not titulo["coincide_numeracion"]:
                problemas.append(
                    "numeracion_titulo_inconsistente"
                )

            if ancho_m is None or alto_m is None:
                problemas.append(
                    "seccion_no_detectada"
                )

            if not barras:
                problemas.append(
                    "barras_longitudinales_no_detectadas"
                )

            if len(estribos) != 1:
                problemas.append(
                    "estribo_no_univoco"
                )

            especificaciones.append(
                {
                    "referencia": referencia,
                    "pagina": pagina,
                    "ancho_m": ancho_m,
                    "alto_m": alto_m,
                    "armadura_longitudinal": barras,
                    "estribo": (
                        estribos[0]
                        if len(estribos) == 1
                        else None
                    ),
                    "origen": origen,
                    "texto_titulo": titulo["texto"],
                    "estado": (
                        "CORRECTO"
                        if not problemas
                        else "REVISAR"
                    ),
                    "problemas": problemas,
                }
            )

    especificaciones.sort(
        key=lambda fila: _clave_referencia(
            fila["referencia"]
        )
    )

    return especificaciones


def _secciones_coinciden(
    ancho_tramo,
    alto_tramo,
    especificacion,
    tolerancia_m,
):
    seccion_tramo = [
        _numero(ancho_tramo),
        _numero(alto_tramo),
    ]
    seccion_detalle = [
        _numero(
            especificacion.get("ancho_m")
        ),
        _numero(
            especificacion.get("alto_m")
        ),
    ]

    if None in seccion_tramo or None in seccion_detalle:
        return False

    seccion_tramo.sort()
    seccion_detalle.sort()

    return all(
        abs(valor_tramo - valor_detalle)
        <= tolerancia_m
        for valor_tramo, valor_detalle
        in zip(seccion_tramo, seccion_detalle)
    )


def _calcular_acero_tramo(
    fila,
    especificacion,
    *,
    tolerancia_seccion_m,
    longitud_adicional_por_extremo_m,
):
    resultado = {
        "armadura_viga": especificacion,
        "estado_acero": "pendiente_armadura",
        "metros_acero_longitudinal": None,
        "metros_acero_estribos": None,
        "peso_acero_longitudinal_kg": None,
        "peso_acero_estribos_kg": None,
        "peso_acero_total_kg": None,
        "acero_por_diametro": [],
    }

    if fila.get("estado") != "computado":
        resultado["estado_acero"] = (
            "pendiente_geometria"
        )
        return resultado

    if especificacion is None:
        return resultado

    if especificacion.get("estado") != "CORRECTO":
        resultado["estado_acero"] = (
            "pendiente_revision_detalle"
        )
        return resultado

    if not _secciones_coinciden(
        fila.get("ancho_m"),
        fila.get("alto_m"),
        especificacion,
        tolerancia_seccion_m,
    ):
        resultado["estado_acero"] = (
            "seccion_no_coincide_con_detalle"
        )
        return resultado

    longitud_longitudinal_m = _numero(
        fila.get(
            "longitud_entre_ejes_m",
            fila.get("longitud_m"),
        )
    )
    longitud_libre_m = _numero(
        fila.get(
            "longitud_libre_entre_caras_m",
            fila.get("longitud_m"),
        )
    )

    if (
        longitud_longitudinal_m is None
        or longitud_longitudinal_m <= 0
        or longitud_libre_m is None
        or longitud_libre_m <= 0
    ):
        resultado["estado_acero"] = (
            "pendiente_longitud"
        )
        return resultado

    por_diametro = defaultdict(
        lambda: {
            "metros_longitudinales": 0.0,
            "metros_estribos": 0.0,
            "peso_kg": 0.0,
        }
    )
    metros_longitudinales = 0.0
    peso_longitudinal = 0.0

    longitud_unidad_barra = (
        longitud_longitudinal_m
        + 2 * longitud_adicional_por_extremo_m
    )

    for barra in especificacion[
        "armadura_longitudinal"
    ]:
        metros = (
            barra["cantidad"]
            * longitud_unidad_barra
        )
        peso = (
            metros
            * barra["peso_unitario_kg_m"]
        )
        diametro = barra[
            "diametro_pulgadas"
        ]

        metros_longitudinales += metros
        peso_longitudinal += peso
        por_diametro[diametro][
            "metros_longitudinales"
        ] += metros
        por_diametro[diametro][
            "peso_kg"
        ] += peso

    estribo = especificacion["estribo"]
    separacion_m = estribo["separacion_m"]
    cantidad_estribos = max(
        2,
        ceil(
            longitud_libre_m
            / separacion_m
        )
        + 1,
    )
    metros_estribos = (
        cantidad_estribos
        * estribo["longitud_unidad_m"]
    )
    peso_estribos = (
        metros_estribos
        * estribo["peso_unitario_kg_m"]
    )
    diametro_estribo = estribo[
        "diametro_pulgadas"
    ]

    por_diametro[diametro_estribo][
        "metros_estribos"
    ] += metros_estribos
    por_diametro[diametro_estribo][
        "peso_kg"
    ] += peso_estribos

    resultado.update(
        {
            "estado_acero": "computado",
            "longitud_barra_longitudinal_m": round(
                longitud_unidad_barra,
                3,
            ),
            "cantidad_estribos": cantidad_estribos,
            "metros_acero_longitudinal": round(
                metros_longitudinales,
                3,
            ),
            "metros_acero_estribos": round(
                metros_estribos,
                3,
            ),
            "peso_acero_longitudinal_kg": round(
                peso_longitudinal,
                3,
            ),
            "peso_acero_estribos_kg": round(
                peso_estribos,
                3,
            ),
            "peso_acero_total_kg": round(
                peso_longitudinal
                + peso_estribos,
                3,
            ),
            "acero_por_diametro": [
                {
                    "diametro_pulgadas": diametro,
                    "metros_longitudinales": round(
                        datos[
                            "metros_longitudinales"
                        ],
                        3,
                    ),
                    "metros_estribos": round(
                        datos["metros_estribos"],
                        3,
                    ),
                    "peso_kg": round(
                        datos["peso_kg"],
                        3,
                    ),
                }
                for diametro, datos in sorted(
                    por_diametro.items()
                )
            ],
            "criterio_acero": (
                "barras longitudinales entre ejes; "
                "estribos sobre longitud libre"
            ),
        }
    )

    return resultado


def calcular_acero_tramo_validado_manualmente(
    fila,
    especificacion,
    *,
    tolerancia_seccion_m=0.025,
    longitud_adicional_por_extremo_m=0.0,
):
    """Calcula el acero después de una validación profesional.

    La decisión manual autoriza de forma explícita utilizar la armadura
    extraída del detalle con la sección validada para un único tramo. La
    especificación original no se modifica y permanece disponible como
    evidencia de auditoría.
    """

    if not isinstance(fila, dict):
        raise TypeError(
            "La fila del tramo debe ser un diccionario."
        )

    if not isinstance(especificacion, dict):
        raise ValueError(
            "El tramo no tiene una armadura detectada que pueda validarse."
        )

    if especificacion.get("estado") != "CORRECTO":
        raise ValueError(
            "La armadura detectada no está en estado CORRECTO."
        )

    ancho_validado = _numero(fila.get("ancho_m"))
    alto_validado = _numero(fila.get("alto_m"))

    if (
        ancho_validado is None
        or ancho_validado <= 0
        or alto_validado is None
        or alto_validado <= 0
    ):
        raise ValueError(
            "La sección validada debe contener dimensiones positivas."
        )

    especificacion_calculo = deepcopy(
        especificacion
    )
    especificacion_calculo["ancho_m"] = ancho_validado
    especificacion_calculo["alto_m"] = alto_validado

    calculo = _calcular_acero_tramo(
        fila,
        especificacion_calculo,
        tolerancia_seccion_m=tolerancia_seccion_m,
        longitud_adicional_por_extremo_m=(
            longitud_adicional_por_extremo_m
        ),
    )

    if calculo.get("estado_acero") != "computado":
        raise ValueError(
            "No fue posible recalcular el acero con la sección validada: "
            f"{calculo.get('estado_acero')}."
        )

    # Se conserva el detalle original, incluida su sección, para que el
    # resultado nunca oculte la discrepancia que motivó la revisión.
    calculo["armadura_viga"] = deepcopy(
        especificacion
    )
    calculo["seccion_validada_manualmente"] = True
    calculo["seccion_usada_para_calculo_m"] = {
        "ancho": ancho_validado,
        "alto": alto_validado,
    }

    return calculo


def _incorporar_acero_vigas_riostra(
    resultado,
    especificaciones,
    *,
    tolerancia_seccion_m,
    longitud_adicional_por_extremo_m,
):
    """Agrega acero a un resultado geométrico sin ocultar faltantes."""

    especificaciones_por_referencia = {
        especificacion["referencia"]: especificacion
        for especificacion in especificaciones
    }
    detalle = resultado.get(
        "vigas_riostra_computo_detalle",
        [],
    )

    for fila in detalle:
        especificacion = (
            especificaciones_por_referencia.get(
                str(
                    fila.get("referencia", "")
                ).strip().upper()
            )
        )
        fila.update(
            _calcular_acero_tramo(
                fila,
                especificacion,
                tolerancia_seccion_m=(
                    tolerancia_seccion_m
                ),
                longitud_adicional_por_extremo_m=(
                    longitud_adicional_por_extremo_m
                ),
            )
        )

    filas_acero_computado = [
        fila
        for fila in detalle
        if fila.get("estado_acero")
        == "computado"
    ]
    filas_geometria_computada = [
        fila
        for fila in detalle
        if fila.get("estado") == "computado"
    ]

    for resumen in resultado.get(
        "resumen_vigas_riostra_por_tipo",
        [],
    ):
        filas_grupo = [
            fila
            for fila in detalle
            if (
                fila.get("referencia")
                == resumen.get("referencia")
                and _numero(fila.get("ancho_m"))
                == _numero(resumen.get("ancho_m"))
                and _numero(fila.get("alto_m"))
                == _numero(resumen.get("alto_m"))
            )
        ]
        filas_grupo_computadas = [
            fila
            for fila in filas_grupo
            if fila.get("estado_acero")
            == "computado"
        ]

        resumen.update(
            {
                "tramos_acero_computados": len(
                    filas_grupo_computadas
                ),
                "peso_acero_kg": (
                    round(
                        sum(
                            fila[
                                "peso_acero_total_kg"
                            ]
                            for fila
                            in filas_grupo_computadas
                        ),
                        3,
                    )
                    if filas_grupo_computadas
                    else None
                ),
                "estado_acero": (
                    "computado"
                    if filas_grupo
                    and len(
                        filas_grupo_computadas
                    )
                    == len(filas_grupo)
                    else (
                        "parcial"
                        if filas_grupo_computadas
                        else "pendiente"
                    )
                ),
            }
        )

    acumulado_diametros = defaultdict(
        lambda: {
            "metros_longitudinales": 0.0,
            "metros_estribos": 0.0,
            "peso_kg": 0.0,
        }
    )

    for fila in filas_acero_computado:
        for diametro in fila[
            "acero_por_diametro"
        ]:
            referencia = diametro[
                "diametro_pulgadas"
            ]
            acumulado_diametros[referencia][
                "metros_longitudinales"
            ] += diametro[
                "metros_longitudinales"
            ]
            acumulado_diametros[referencia][
                "metros_estribos"
            ] += diametro["metros_estribos"]
            acumulado_diametros[referencia][
                "peso_kg"
            ] += diametro["peso_kg"]

    resumen_diametros = [
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
            "peso_kg": round(
                datos["peso_kg"],
                3,
            ),
        }
        for diametro, datos in sorted(
            acumulado_diametros.items(),
            key=lambda item: float(
                Fraction(item[0])
            ),
        )
    ]

    estados_pendientes = Counter(
        fila.get("estado_acero")
        for fila in filas_geometria_computada
        if fila.get("estado_acero")
        != "computado"
    )
    resultado_completo = (
        bool(filas_geometria_computada)
        and len(filas_acero_computado)
        == len(filas_geometria_computada)
    )
    acero_total = (
        round(
            sum(
                fila["peso_acero_total_kg"]
                for fila in filas_acero_computado
            ),
            3,
        )
        if filas_acero_computado
        else None
    )

    validacion_acero = {
        "tipos_armadura_detectados": len(
            especificaciones
        ),
        "tipos_armadura_correctos": sum(
            especificacion.get("estado")
            == "CORRECTO"
            for especificacion in especificaciones
        ),
        "tramos_geometria_computada": len(
            filas_geometria_computada
        ),
        "tramos_acero_computado": len(
            filas_acero_computado
        ),
        "tramos_acero_pendiente": (
            len(filas_geometria_computada)
            - len(filas_acero_computado)
        ),
        "estados_pendientes": dict(
            sorted(estados_pendientes.items())
        ),
        "resultado_completo": resultado_completo,
        "tolerancia_seccion_m": (
            tolerancia_seccion_m
        ),
        "longitud_adicional_por_extremo_m": (
            longitud_adicional_por_extremo_m
        ),
        "advertencias": [
            (
                "Las barras longitudinales se computan "
                "entre ejes de apoyo."
            ),
            (
                "Los estribos se distribuyen sobre la "
                "longitud libre entre caras."
            ),
            (
                "Los tramos cuya sección no coincide con "
                "el detalle quedan fuera del subtotal."
            ),
        ],
    }

    resultado.update(
        {
            "armaduras_vigas_riostra": (
                especificaciones
            ),
            # Puede ser un subtotal si la validación informa
            # tramos pendientes. Nunca se completa con ceros.
            "acero_vigas_riostra_kg": acero_total,
            "resumen_acero_vigas_riostra": (
                resumen_diametros
            ),
            "validacion_acero_vigas_riostra": (
                validacion_acero
            ),
        }
    )

    validacion_geometrica = resultado.get(
        "validacion_computo_vigas_riostra",
        {},
    )
    validacion_geometrica.update(
        {
            "acero_disponible": bool(
                filas_acero_computado
            ),
            "acero_resultado_completo": (
                resultado_completo
            ),
            "tramos_acero_computado": len(
                filas_acero_computado
            ),
            "tramos_acero_pendiente": (
                len(filas_geometria_computada)
                - len(filas_acero_computado)
            ),
        }
    )

    return resultado


def _datos_cota(palabra):
    texto = str(
        _valor_campo(palabra, "texto", "")
    ).strip()

    if not PATRON_COTA_METROS.fullmatch(texto):
        return None

    valor_m = _numero(
        texto.replace(",", ".")
    )

    # Excluye espesores diminutos y números propios del cajetín.
    if (
        valor_m is None
        or valor_m < 0.20
        or valor_m > 50.0
    ):
        return None

    x0 = _coordenada_palabra(palabra, "x0")
    y0 = _coordenada_palabra(palabra, "y0")
    x1 = _coordenada_palabra(palabra, "x1")
    y1 = _coordenada_palabra(palabra, "y1")

    if None in (x0, y0, x1, y1):
        return None

    ancho = abs(x1 - x0)
    alto = abs(y1 - y0)

    if alto >= ancho * 1.25:
        orientacion = "vertical"
        alineacion = (x0 + x1) / 2
        posicion = (y0 + y1) / 2
    elif ancho >= alto * 1.25:
        orientacion = "horizontal"
        alineacion = (y0 + y1) / 2
        posicion = (x0 + x1) / 2
    else:
        return None

    return {
        "pagina": int(
            _numero(
                _valor_campo(palabra, "pagina", 1),
                1,
            )
        ),
        "texto": texto,
        "valor_m": valor_m,
        "orientacion": orientacion,
        "alineacion_pdf": alineacion,
        "posicion_pdf": posicion,
    }


def _agrupar_cotas_alineadas(
    cotas,
    tolerancia_alineacion_pdf,
):
    grupos = []

    for cota in sorted(
        cotas,
        key=lambda item: (
            item["pagina"],
            item["orientacion"],
            item["alineacion_pdf"],
        ),
    ):
        grupo_compatible = None

        for grupo in reversed(grupos):
            primera = grupo[0]

            if (
                primera["pagina"]
                != cota["pagina"]
                or primera["orientacion"]
                != cota["orientacion"]
            ):
                continue

            alineacion_media = sum(
                item["alineacion_pdf"]
                for item in grupo
            ) / len(grupo)

            if (
                abs(
                    cota["alineacion_pdf"]
                    - alineacion_media
                )
                <= tolerancia_alineacion_pdf
            ):
                grupo_compatible = grupo
                break

        if grupo_compatible is None:
            grupos.append([cota])
        else:
            grupo_compatible.append(cota)

    return grupos


def detectar_escala_desde_cotas(
    palabras,
    *,
    escala_configurada=None,
    tolerancia_alineacion_pdf=1.25,
    tolerancia_relativa=0.05,
    minimo_cotas_por_cadena=3,
):
    """Obtiene metros por punto PDF utilizando cadenas de cotas.

    En una cadena continua, el centro de cada texto se encuentra cerca del
    centro de su intervalo. Para dos cotas consecutivas ``a`` y ``b``:

        metros_por_punto = (a + b) / (2 * distancia_entre_textos)

    Se toma la mediana del grupo consistente para tolerar pequeños errores de
    posición. Una escala explícita siempre tiene prioridad.
    """

    escala_manual = _numero(escala_configurada)

    if escala_configurada is not None:
        if escala_manual is None or escala_manual <= 0:
            raise ValueError(
                "escala_configurada debe ser un número mayor que cero."
            )

        return {
            "estado": "confirmada",
            "fuente": "configuracion_proyecto",
            "confianza": "configurada",
            "metros_por_punto_pdf": round(
                escala_manual,
                9,
            ),
            "cantidad_cotas_detectadas": 0,
            "cantidad_cadenas_utilizadas": 0,
            "cantidad_estimaciones_utilizadas": 0,
            "dispersion_relativa": 0.0,
        }

    cotas = []

    for palabra in palabras:
        cota = _datos_cota(palabra)

        if cota is not None:
            cotas.append(cota)

    grupos = _agrupar_cotas_alineadas(
        cotas,
        tolerancia_alineacion_pdf,
    )

    estimaciones = []
    cadenas_candidatas = 0

    for indice_grupo, grupo in enumerate(grupos):
        grupo_ordenado = sorted(
            grupo,
            key=lambda item: item["posicion_pdf"],
        )

        grupo_sin_repetidos = []

        for cota in grupo_ordenado:
            if grupo_sin_repetidos:
                anterior = grupo_sin_repetidos[-1]

                if (
                    abs(
                        cota["posicion_pdf"]
                        - anterior["posicion_pdf"]
                    )
                    <= 0.50
                    and cota["valor_m"]
                    == anterior["valor_m"]
                ):
                    continue

            grupo_sin_repetidos.append(cota)

        if (
            len(grupo_sin_repetidos)
            < minimo_cotas_por_cadena
        ):
            continue

        cadenas_candidatas += 1

        for primera, segunda in zip(
            grupo_sin_repetidos,
            grupo_sin_repetidos[1:],
        ):
            distancia = abs(
                segunda["posicion_pdf"]
                - primera["posicion_pdf"]
            )

            if distancia < 5.0:
                continue

            escala = (
                primera["valor_m"]
                + segunda["valor_m"]
            ) / (2 * distancia)

            if 0.001 <= escala <= 10.0:
                estimaciones.append(
                    {
                        "grupo": indice_grupo,
                        "escala": escala,
                    }
                )

    if len(estimaciones) < 2:
        return {
            "estado": "pendiente_escala",
            "fuente": None,
            "confianza": "insuficiente",
            "metros_por_punto_pdf": None,
            "cantidad_cotas_detectadas": len(cotas),
            "cantidad_cadenas_utilizadas": 0,
            "cantidad_estimaciones_utilizadas": 0,
            "dispersion_relativa": None,
            "advertencia": (
                "No se encontraron cadenas de cotas suficientes. "
                "Debe indicarse la escala en metros por punto PDF."
            ),
        }

    mejor_grupo = []

    for estimacion_central in estimaciones:
        centro = estimacion_central["escala"]
        compatibles = [
            estimacion
            for estimacion in estimaciones
            if (
                abs(estimacion["escala"] - centro)
                / centro
                <= tolerancia_relativa
            )
        ]

        if len(compatibles) > len(mejor_grupo):
            mejor_grupo = compatibles

    escala_mediana = median(
        item["escala"]
        for item in mejor_grupo
    )

    mejor_grupo = [
        item
        for item in estimaciones
        if (
            abs(item["escala"] - escala_mediana)
            / escala_mediana
            <= tolerancia_relativa
        )
    ]

    escala_mediana = median(
        item["escala"]
        for item in mejor_grupo
    )

    dispersion = median(
        abs(item["escala"] - escala_mediana)
        for item in mejor_grupo
    ) / escala_mediana

    grupos_utilizados = {
        item["grupo"]
        for item in mejor_grupo
    }

    if (
        len(mejor_grupo) >= 5
        and len(grupos_utilizados) >= 2
        and dispersion <= 0.03
    ):
        confianza = "alta"
        estado = "confirmada"
    elif (
        len(mejor_grupo) >= 3
        and dispersion <= 0.05
    ):
        confianza = "media"
        estado = "revisar_escala"
    else:
        confianza = "baja"
        estado = "pendiente_escala"

    return {
        "estado": estado,
        "fuente": "cadenas_cotas_pdf",
        "confianza": confianza,
        "metros_por_punto_pdf": round(
            escala_mediana,
            9,
        ),
        "cantidad_cotas_detectadas": len(cotas),
        "cantidad_cadenas_utilizadas": len(
            grupos_utilizados
        ),
        "cantidad_estimaciones_utilizadas": len(
            mejor_grupo
        ),
        "dispersion_relativa": round(
            dispersion,
            6,
        ),
    }


def _distancia_punto_a_eje(
    punto_x,
    punto_y,
    eje,
):
    x_inicial = _numero(eje.get("x_inicial"))
    y_inicial = _numero(eje.get("y_inicial"))
    x_final = _numero(eje.get("x_final"))
    y_final = _numero(eje.get("y_final"))

    if None in (
        x_inicial,
        y_inicial,
        x_final,
        y_final,
    ):
        return None

    diferencia_x = x_final - x_inicial
    diferencia_y = y_final - y_inicial
    longitud_cuadrada = (
        diferencia_x**2
        + diferencia_y**2
    )

    if longitud_cuadrada == 0:
        return None

    proyeccion = (
        (punto_x - x_inicial) * diferencia_x
        + (punto_y - y_inicial) * diferencia_y
    ) / longitud_cuadrada

    proyeccion_limitada = min(
        1.0,
        max(0.0, proyeccion),
    )

    punto_proyectado_x = (
        x_inicial
        + proyeccion_limitada * diferencia_x
    )

    punto_proyectado_y = (
        y_inicial
        + proyeccion_limitada * diferencia_y
    )

    return {
        "distancia_pdf": hypot(
            punto_x - punto_proyectado_x,
            punto_y - punto_proyectado_y,
        ),
        "proyeccion": proyeccion,
    }


def _orientacion_eje(eje):
    angulo = _numero(
        eje.get("angulo_pdf_grados"),
        0.0,
    ) % 180

    if min(angulo, 180 - angulo) <= 20:
        return "horizontal"

    if abs(angulo - 90) <= 20:
        return "vertical"

    return "inclinada"


def _orientacion_rotulo(rotulo):
    ancho = abs(
        _numero(rotulo.get("x1"), 0.0)
        - _numero(rotulo.get("x0"), 0.0)
    )

    alto = abs(
        _numero(rotulo.get("y1"), 0.0)
        - _numero(rotulo.get("y0"), 0.0)
    )

    if ancho >= alto * 1.25:
        return "horizontal"

    if alto >= ancho * 1.25:
        return "vertical"

    return "inclinada"


def asociar_ejes_con_rotulos(
    ejes,
    rotulos,
    *,
    distancia_maxima_pdf=15.0,
    margen_proyeccion=0.30,
):
    """Realiza una asignación uno a uno entre ejes y rótulos de vigas."""

    candidatos = []

    for indice_eje, eje in enumerate(ejes):
        orientacion_eje = _orientacion_eje(eje)

        for indice_rotulo, rotulo in enumerate(rotulos):
            if (
                eje.get("pagina")
                != rotulo.get("pagina")
            ):
                continue

            orientacion_rotulo = _orientacion_rotulo(
                rotulo
            )

            if (
                orientacion_eje != "inclinada"
                and orientacion_rotulo != "inclinada"
                and orientacion_eje
                != orientacion_rotulo
            ):
                continue

            centro_x = _numero(
                rotulo.get("centro_x")
            )
            centro_y = _numero(
                rotulo.get("centro_y")
            )

            if centro_x is None or centro_y is None:
                continue

            medicion = _distancia_punto_a_eje(
                centro_x,
                centro_y,
                eje,
            )

            if medicion is None:
                continue

            if (
                medicion["distancia_pdf"]
                > distancia_maxima_pdf
                or medicion["proyeccion"]
                < -margen_proyeccion
                or medicion["proyeccion"]
                > 1 + margen_proyeccion
            ):
                continue

            candidatos.append(
                {
                    "indice_eje": indice_eje,
                    "indice_rotulo": indice_rotulo,
                    **medicion,
                }
            )

    candidatos.sort(
        key=lambda item: (
            item["distancia_pdf"],
            abs(item["proyeccion"] - 0.5),
        )
    )

    ejes_utilizados = set()
    rotulos_utilizados = set()
    asociaciones = []

    for candidato in candidatos:
        indice_eje = candidato["indice_eje"]
        indice_rotulo = candidato["indice_rotulo"]

        if (
            indice_eje in ejes_utilizados
            or indice_rotulo in rotulos_utilizados
        ):
            continue

        ejes_utilizados.add(indice_eje)
        rotulos_utilizados.add(indice_rotulo)

        asociaciones.append(
            {
                "eje": dict(ejes[indice_eje]),
                "rotulo": dict(rotulos[indice_rotulo]),
                "distancia_rotulo_eje_pdf": round(
                    candidato["distancia_pdf"],
                    3,
                ),
                "proyeccion_rotulo_sobre_eje": round(
                    candidato["proyeccion"],
                    4,
                ),
            }
        )

    ejes_sin_rotulo = [
        dict(eje)
        for indice, eje in enumerate(ejes)
        if indice not in ejes_utilizados
    ]

    rotulos_sin_eje = [
        dict(rotulo)
        for indice, rotulo in enumerate(rotulos)
        if indice not in rotulos_utilizados
    ]

    return {
        "asociaciones": asociaciones,
        "ejes_sin_rotulo": ejes_sin_rotulo,
        "rotulos_sin_eje": rotulos_sin_eje,
        "diagnostico": {
            "cantidad_ejes_entrada": len(ejes),
            "cantidad_rotulos_entrada": len(rotulos),
            "ejes_asociados": len(asociaciones),
            "ejes_sin_rotulo": len(ejes_sin_rotulo),
            "rotulos_sin_eje": len(rotulos_sin_eje),
            "distancia_maxima_pdf": distancia_maxima_pdf,
            "margen_proyeccion": margen_proyeccion,
            "asignacion_unica": True,
        },
    }


def _longitud_eje_pdf(eje):
    longitud = _numero(
        eje.get("longitud_pdf")
    )

    if longitud is not None and longitud > 0:
        return longitud

    x_inicial = _numero(eje.get("x_inicial"))
    y_inicial = _numero(eje.get("y_inicial"))
    x_final = _numero(eje.get("x_final"))
    y_final = _numero(eje.get("y_final"))

    if None in (
        x_inicial,
        y_inicial,
        x_final,
        y_final,
    ):
        return None

    return hypot(
        x_final - x_inicial,
        y_final - y_inicial,
    )


def _clave_referencia(referencia):
    coincidencia = re.search(
        r"(\d+)",
        str(referencia),
    )

    return (
        int(coincidencia.group(1))
        if coincidencia
        else 10**9,
        str(referencia),
    )


def _calcular_computos_vigas_riostra_legacy(
    *,
    palabras_planta,
    ejes_vigas,
    rotulos_vigas,
    escala_metros_por_punto=None,
    incluir_fondo_encofrado=False,
    distancia_maxima_rotulo_eje_pdf=15.0,
    margen_proyeccion_rotulo=0.30,
):
    """Calcula cantidades solamente para tramos geométricamente trazables."""

    escala = detectar_escala_desde_cotas(
        palabras_planta,
        escala_configurada=(
            escala_metros_por_punto
        ),
    )

    asociacion = asociar_ejes_con_rotulos(
        ejes_vigas,
        rotulos_vigas,
        distancia_maxima_pdf=(
            distancia_maxima_rotulo_eje_pdf
        ),
        margen_proyeccion=(
            margen_proyeccion_rotulo
        ),
    )

    escala_confirmada = (
        escala["estado"] == "confirmada"
    )

    metros_por_punto = (
        escala["metros_por_punto_pdf"]
        if escala_confirmada
        else None
    )

    asociaciones_ordenadas = sorted(
        asociacion["asociaciones"],
        key=lambda item: (
            item["eje"].get("pagina") or 0,
            _numero(
                item["eje"].get("centro_y"),
                0.0,
            ),
            _numero(
                item["eje"].get("centro_x"),
                0.0,
            ),
            item["eje"].get("id_eje") or 0,
        ),
    )

    apariciones = Counter()
    detalle = []

    for asociacion_eje in asociaciones_ordenadas:
        eje = asociacion_eje["eje"]
        rotulo = asociacion_eje["rotulo"]

        referencia = str(
            rotulo.get("referencia", "")
        ).strip().upper()

        apariciones[referencia] += 1

        ancho_m = _numero(
            rotulo.get("ancho_m")
        )
        alto_m = _numero(
            rotulo.get("alto_m")
        )
        longitud_pdf = _longitud_eje_pdf(eje)

        tiene_seccion = (
            ancho_m is not None
            and ancho_m > 0
            and alto_m is not None
            and alto_m > 0
        )

        if not tiene_seccion:
            estado = "sin_seccion"
        elif not escala_confirmada:
            estado = "pendiente_escala"
        elif longitud_pdf is None or longitud_pdf <= 0:
            estado = "sin_longitud_vectorial"
        else:
            estado = "computado"

        if estado == "computado":
            longitud_m = (
                longitud_pdf
                * metros_por_punto
            )
            volumen_m3 = (
                ancho_m
                * alto_m
                * longitud_m
            )
            encofrado_laterales_m2 = (
                2
                * alto_m
                * longitud_m
            )
            encofrado_fondo_m2 = (
                ancho_m
                * longitud_m
            )
            encofrado_total_m2 = (
                encofrado_laterales_m2
                + (
                    encofrado_fondo_m2
                    if incluir_fondo_encofrado
                    else 0.0
                )
            )
        else:
            longitud_m = None
            volumen_m3 = None
            encofrado_laterales_m2 = None
            encofrado_fondo_m2 = None
            encofrado_total_m2 = None

        detalle.append(
            {
                "identificador": (
                    f"{referencia}-"
                    f"{apariciones[referencia]:02d}"
                ),
                "referencia": referencia,
                "pagina": eje.get("pagina"),
                "id_eje": eje.get("id_eje"),
                "texto_original": rotulo.get(
                    "texto_original"
                ),
                "ancho_m": ancho_m,
                "alto_m": alto_m,
                "longitud_pdf": (
                    round(longitud_pdf, 3)
                    if longitud_pdf is not None
                    else None
                ),
                "metros_por_punto_pdf": (
                    metros_por_punto
                    if escala_confirmada
                    else None
                ),
                "longitud_m": (
                    round(longitud_m, 3)
                    if longitud_m is not None
                    else None
                ),
                "volumen_hormigon_m3": (
                    round(volumen_m3, 3)
                    if volumen_m3 is not None
                    else None
                ),
                "encofrado_laterales_m2": (
                    round(
                        encofrado_laterales_m2,
                        3,
                    )
                    if encofrado_laterales_m2
                    is not None
                    else None
                ),
                "encofrado_fondo_m2": (
                    round(encofrado_fondo_m2, 3)
                    if encofrado_fondo_m2
                    is not None
                    else None
                ),
                "encofrado_total_m2": (
                    round(encofrado_total_m2, 3)
                    if encofrado_total_m2
                    is not None
                    else None
                ),
                "encofrado_incluye_fondo": (
                    incluir_fondo_encofrado
                ),
                "distancia_rotulo_eje_pdf": (
                    asociacion_eje[
                        "distancia_rotulo_eje_pdf"
                    ]
                ),
                "proyeccion_rotulo_sobre_eje": (
                    asociacion_eje[
                        "proyeccion_rotulo_sobre_eje"
                    ]
                ),
                "eje_pdf": {
                    "x_inicial": eje.get(
                        "x_inicial"
                    ),
                    "y_inicial": eje.get(
                        "y_inicial"
                    ),
                    "x_final": eje.get("x_final"),
                    "y_final": eje.get("y_final"),
                    "angulo_grados": eje.get(
                        "angulo_pdf_grados"
                    ),
                },
                "metodo_longitud": (
                    "longitud del eje central vectorial"
                ),
                "estado": estado,
            }
        )

    filas_computadas = [
        fila
        for fila in detalle
        if fila["estado"] == "computado"
    ]

    grupos = defaultdict(list)

    for fila in filas_computadas:
        clave = (
            fila["referencia"],
            fila["ancho_m"],
            fila["alto_m"],
        )
        grupos[clave].append(fila)

    resumen_por_tipo = []

    for (
        referencia,
        ancho_m,
        alto_m,
    ), filas in sorted(
        grupos.items(),
        key=lambda item: (
            _clave_referencia(item[0][0]),
            item[0][1],
            item[0][2],
        ),
    ):
        resumen_por_tipo.append(
            {
                "referencia": referencia,
                "ancho_m": ancho_m,
                "alto_m": alto_m,
                "cantidad_tramos": len(filas),
                "longitud_total_m": round(
                    sum(
                        fila["longitud_m"]
                        for fila in filas
                    ),
                    3,
                ),
                "volumen_hormigon_m3": round(
                    sum(
                        fila["volumen_hormigon_m3"]
                        for fila in filas
                    ),
                    3,
                ),
                "encofrado_laterales_m2": round(
                    sum(
                        fila["encofrado_laterales_m2"]
                        for fila in filas
                    ),
                    3,
                ),
                "encofrado_fondo_m2": round(
                    sum(
                        fila["encofrado_fondo_m2"]
                        for fila in filas
                    ),
                    3,
                ),
                "encofrado_total_m2": round(
                    sum(
                        fila["encofrado_total_m2"]
                        for fila in filas
                    ),
                    3,
                ),
            }
        )

    total_ejes = len(ejes_vigas)

    validacion = {
        **asociacion["diagnostico"],
        "escala_confirmada": escala_confirmada,
        "confianza_escala": escala["confianza"],
        "tramos_computados": len(filas_computadas),
        "tramos_sin_seccion": sum(
            fila["estado"] == "sin_seccion"
            for fila in detalle
        ),
        "tramos_pendientes_escala": sum(
            fila["estado"] == "pendiente_escala"
            for fila in detalle
        ),
        "cobertura_ejes_porcentaje": round(
            (
                len(filas_computadas)
                / total_ejes
                * 100
            )
            if total_ejes
            else 0.0,
            2,
        ),
        "resultado_completo": (
            total_ejes > 0
            and len(filas_computadas)
            == total_ejes
        ),
        "advertencias": [
            (
                "Los totales incluyen únicamente ejes asociados "
                "de manera única con un rótulo de viga."
            ),
            (
                "El área del fondo se informa por separado; "
                "su incorporación al total es configurable."
            ),
        ],
    }

    if not escala_confirmada or total_ejes == 0:
        longitud_total = None
        hormigon_total = None
        laterales_total = None
        fondo_total = None
        encofrado_total = None
    else:
        longitud_total = round(
            sum(
                fila["longitud_m"]
                for fila in filas_computadas
            ),
            3,
        )
        hormigon_total = round(
            sum(
                fila["volumen_hormigon_m3"]
                for fila in filas_computadas
            ),
            3,
        )
        laterales_total = round(
            sum(
                fila["encofrado_laterales_m2"]
                for fila in filas_computadas
            ),
            3,
        )
        fondo_total = round(
            sum(
                fila["encofrado_fondo_m2"]
                for fila in filas_computadas
            ),
            3,
        )
        encofrado_total = round(
            sum(
                fila["encofrado_total_m2"]
                for fila in filas_computadas
            ),
            3,
        )

    return {
        "escala_plano_vigas": escala,
        "vigas_riostra_computo_detalle": detalle,
        "resumen_vigas_riostra_por_tipo": (
            resumen_por_tipo
        ),
        "ejes_vigas_sin_rotulo": (
            asociacion["ejes_sin_rotulo"]
        ),
        "longitud_total_vigas_riostra_m": (
            longitud_total
        ),
        "hormigon_vigas_riostra_m3": (
            hormigon_total
        ),
        "encofrado_laterales_vigas_riostra_m2": (
            laterales_total
        ),
        "encofrado_fondo_vigas_riostra_m2": (
            fondo_total
        ),
        "encofrado_vigas_riostra_m2": (
            encofrado_total
        ),
        "validacion_computo_vigas_riostra": (
            validacion
        ),
    }


def calcular_computos_vigas_riostra(
    *,
    palabras_planta,
    ejes_vigas,
    rotulos_vigas,
    palabras_detalles=None,
    origen_detalles=None,
    armaduras_vigas=None,
    ruta_planta=None,
    rotulos_columnas=None,
    escala_metros_por_punto=None,
    criterio_longitud="entre_ejes",
    incluir_fondo_encofrado=False,
    distancia_maxima_rotulo_eje_pdf=15.0,
    margen_proyeccion_rotulo=0.30,
    tolerancia_seccion_armadura_m=0.025,
    longitud_adicional_barra_por_extremo_m=0.0,
):
    """Calcula una fila por tramo estructural entre dos columnas.

    ``entre_ejes`` coincide con las cotas usuales del plano. La alternativa
    ``entre_caras`` descuenta media sección gráfica de cada apoyo. Ambas
    longitudes se devuelven siempre para que el criterio del cómputo sea
    explícito y auditable.

    Si no se recibe la ruta de la planta o no hay rótulos de columnas, se
    conserva el comportamiento anterior para no romper llamadas existentes.
    """

    if criterio_longitud not in {
        "entre_ejes",
        "entre_caras",
    }:
        raise ValueError(
            "criterio_longitud debe ser 'entre_ejes' "
            "o 'entre_caras'."
        )

    if armaduras_vigas is None:
        armaduras_vigas = (
            extraer_armaduras_vigas_riostra(
                palabras_detalles,
                origen=origen_detalles,
            )
            if palabras_detalles
            else []
        )

    if ruta_planta is None or not rotulos_columnas:
        resultado = _calcular_computos_vigas_riostra_legacy(
            palabras_planta=palabras_planta,
            ejes_vigas=ejes_vigas,
            rotulos_vigas=rotulos_vigas,
            escala_metros_por_punto=(
                escala_metros_por_punto
            ),
            incluir_fondo_encofrado=(
                incluir_fondo_encofrado
            ),
            distancia_maxima_rotulo_eje_pdf=(
                distancia_maxima_rotulo_eje_pdf
            ),
            margen_proyeccion_rotulo=(
                margen_proyeccion_rotulo
            ),
        )
        resultado[
            "modo_geometria_vigas_riostra"
        ] = "ejes_vectoriales_legacy"
        return _incorporar_acero_vigas_riostra(
            resultado,
            armaduras_vigas,
            tolerancia_seccion_m=(
                tolerancia_seccion_armadura_m
            ),
            longitud_adicional_por_extremo_m=(
                longitud_adicional_barra_por_extremo_m
            ),
        )

    escala = detectar_escala_desde_cotas(
        palabras_planta,
        escala_configurada=escala_metros_por_punto,
    )
    escala_confirmada = (
        escala["estado"] == "confirmada"
    )
    metros_por_punto = (
        escala["metros_por_punto_pdf"]
        if escala_confirmada
        else None
    )

    deteccion_apoyos = (
        detectar_apoyos_columnas_vectoriales(
            ruta_planta,
            rotulos_columnas,
        )
    )
    red = reconstruir_tramos_vigas_entre_apoyos(
        ruta_planta,
        deteccion_apoyos["apoyos"],
        rotulos_vigas,
    )

    # Se conserva el diagnóstico anterior para poder comparar la cobertura
    # del viejo detector de doble borde con la nueva red entre apoyos.
    diagnostico_legacy = asociar_ejes_con_rotulos(
        ejes_vigas,
        rotulos_vigas,
        distancia_maxima_pdf=(
            distancia_maxima_rotulo_eje_pdf
        ),
        margen_proyeccion=margen_proyeccion_rotulo,
    )

    detalle = []

    for tramo in red["tramos"]:
        ancho_m = _numero(tramo.get("ancho_m"))
        alto_m = _numero(tramo.get("alto_m"))
        longitud_entre_ejes_pdf = _numero(
            tramo.get("longitud_entre_ejes_pdf")
        )
        longitud_libre_pdf = _numero(
            tramo.get(
                "longitud_libre_entre_caras_pdf"
            )
        )

        if criterio_longitud == "entre_ejes":
            longitud_computada_pdf = (
                longitud_entre_ejes_pdf
            )
        else:
            longitud_computada_pdf = longitud_libre_pdf

        tiene_seccion = (
            ancho_m is not None
            and ancho_m > 0
            and alto_m is not None
            and alto_m > 0
        )

        if not tiene_seccion:
            estado = "sin_seccion"
        elif not escala_confirmada:
            estado = "pendiente_escala"
        elif (
            longitud_computada_pdf is None
            or longitud_computada_pdf <= 0
        ):
            estado = "sin_longitud_vectorial"
        elif tramo.get("requiere_revision"):
            estado = "pendiente_revision_geometrica"
        else:
            estado = "computado"

        if escala_confirmada:
            longitud_entre_ejes_m = (
                longitud_entre_ejes_pdf
                * metros_por_punto
                if longitud_entre_ejes_pdf is not None
                else None
            )
            longitud_libre_m = (
                longitud_libre_pdf
                * metros_por_punto
                if longitud_libre_pdf is not None
                else None
            )
            longitud_m = (
                longitud_computada_pdf
                * metros_por_punto
                if longitud_computada_pdf is not None
                else None
            )
        else:
            longitud_entre_ejes_m = None
            longitud_libre_m = None
            longitud_m = None

        if estado == "computado":
            volumen_m3 = ancho_m * alto_m * longitud_m
            encofrado_laterales_m2 = (
                2 * alto_m * longitud_m
            )
            encofrado_fondo_m2 = ancho_m * longitud_m
            encofrado_total_m2 = (
                encofrado_laterales_m2
                + (
                    encofrado_fondo_m2
                    if incluir_fondo_encofrado
                    else 0.0
                )
            )
        else:
            volumen_m3 = None
            encofrado_laterales_m2 = None
            encofrado_fondo_m2 = None
            encofrado_total_m2 = None

        detalle.append(
            {
                "identificador": tramo["tramo_id"],
                "tramo_id": tramo["tramo_id"],
                "referencia": tramo["referencia"],
                "pagina": tramo["pagina"],
                "texto_original": tramo.get(
                    "texto_original"
                ),
                "apoyo_inicial_id": tramo[
                    "apoyo_inicial_id"
                ],
                "referencia_apoyo_inicial": tramo[
                    "referencia_apoyo_inicial"
                ],
                "apoyo_final_id": tramo[
                    "apoyo_final_id"
                ],
                "referencia_apoyo_final": tramo[
                    "referencia_apoyo_final"
                ],
                "ancho_m": ancho_m,
                "alto_m": alto_m,
                "longitud_entre_ejes_pdf": (
                    longitud_entre_ejes_pdf
                ),
                "longitud_libre_entre_caras_pdf": (
                    longitud_libre_pdf
                ),
                "longitud_computada_pdf": (
                    longitud_computada_pdf
                ),
                "metros_por_punto_pdf": (
                    metros_por_punto
                    if escala_confirmada
                    else None
                ),
                "longitud_entre_ejes_m": (
                    round(longitud_entre_ejes_m, 3)
                    if longitud_entre_ejes_m
                    is not None
                    else None
                ),
                "longitud_libre_entre_caras_m": (
                    round(longitud_libre_m, 3)
                    if longitud_libre_m is not None
                    else None
                ),
                "longitud_m": (
                    round(longitud_m, 3)
                    if longitud_m is not None
                    else None
                ),
                "criterio_longitud_computo": (
                    criterio_longitud
                ),
                "volumen_hormigon_m3": (
                    round(volumen_m3, 3)
                    if volumen_m3 is not None
                    else None
                ),
                "encofrado_laterales_m2": (
                    round(encofrado_laterales_m2, 3)
                    if encofrado_laterales_m2
                    is not None
                    else None
                ),
                "encofrado_fondo_m2": (
                    round(encofrado_fondo_m2, 3)
                    if encofrado_fondo_m2 is not None
                    else None
                ),
                "encofrado_total_m2": (
                    round(encofrado_total_m2, 3)
                    if encofrado_total_m2 is not None
                    else None
                ),
                "encofrado_incluye_fondo": (
                    incluir_fondo_encofrado
                ),
                "punto_inicial_pdf": tramo[
                    "punto_inicial_pdf"
                ],
                "punto_final_pdf": tramo[
                    "punto_final_pdf"
                ],
                "eje_pdf": {
                    "x_inicial": tramo[
                        "punto_inicial_pdf"
                    ]["x"],
                    "y_inicial": tramo[
                        "punto_inicial_pdf"
                    ]["y"],
                    "x_final": tramo[
                        "punto_final_pdf"
                    ]["x"],
                    "y_final": tramo[
                        "punto_final_pdf"
                    ]["y"],
                    "angulo_grados": tramo[
                        "angulo_pdf_grados"
                    ],
                },
                "distancia_rotulo_tramo_pdf": tramo.get(
                    "distancia_rotulo_tramo_pdf"
                ),
                "proyeccion_rotulo_sobre_tramo": tramo.get(
                    "proyeccion_rotulo_sobre_tramo"
                ),
                "evidencia_vectorial": tramo[
                    "evidencia_vectorial"
                ],
                "metodo_longitud": (
                    "distancia entre centros vectoriales "
                    "de apoyos"
                    if criterio_longitud == "entre_ejes"
                    else (
                        "distancia libre entre caras "
                        "vectoriales de apoyos"
                    )
                ),
                "metodo_asignacion_referencia": tramo[
                    "metodo_asignacion_referencia"
                ],
                "confianza_geometria": tramo[
                    "confianza_geometria"
                ],
                "estado": estado,
            }
        )

    filas_computadas = [
        fila
        for fila in detalle
        if fila["estado"] == "computado"
    ]
    grupos = defaultdict(list)

    for fila in filas_computadas:
        grupos[
            (
                fila["referencia"],
                fila["ancho_m"],
                fila["alto_m"],
            )
        ].append(fila)

    resumen_por_tipo = []

    for (
        referencia,
        ancho_m,
        alto_m,
    ), filas in sorted(
        grupos.items(),
        key=lambda item: (
            _clave_referencia(item[0][0]),
            item[0][1],
            item[0][2],
        ),
    ):
        resumen_por_tipo.append(
            {
                "referencia": referencia,
                "ancho_m": ancho_m,
                "alto_m": alto_m,
                "cantidad_tramos": len(filas),
                "criterio_longitud": criterio_longitud,
                "longitud_total_entre_ejes_m": round(
                    sum(
                        fila["longitud_entre_ejes_m"]
                        for fila in filas
                    ),
                    3,
                ),
                "longitud_total_libre_m": round(
                    sum(
                        fila[
                            "longitud_libre_entre_caras_m"
                        ]
                        for fila in filas
                    ),
                    3,
                ),
                "longitud_total_m": round(
                    sum(
                        fila["longitud_m"]
                        for fila in filas
                    ),
                    3,
                ),
                "volumen_hormigon_m3": round(
                    sum(
                        fila["volumen_hormigon_m3"]
                        for fila in filas
                    ),
                    3,
                ),
                "encofrado_laterales_m2": round(
                    sum(
                        fila["encofrado_laterales_m2"]
                        for fila in filas
                    ),
                    3,
                ),
                "encofrado_fondo_m2": round(
                    sum(
                        fila["encofrado_fondo_m2"]
                        for fila in filas
                    ),
                    3,
                ),
                "encofrado_total_m2": round(
                    sum(
                        fila["encofrado_total_m2"]
                        for fila in filas
                    ),
                    3,
                ),
            }
        )

    cantidad_objetivo = len(red["tramos"])
    diagnostico_red = red["diagnostico"]
    validacion = {
        **diagnostico_legacy["diagnostico"],
        "modo_geometria": "red_entre_apoyos",
        "apoyos_columnas_detectados": len(
            deteccion_apoyos["apoyos"]
        ),
        "tramos_entre_apoyos_detectados": len(
            red["tramos"]
        ),
        "rotulos_asignados_a_tramos": (
            diagnostico_red[
                "rotulos_asignados_a_tramos"
            ]
        ),
        "rotulos_sin_tramo": diagnostico_red[
            "rotulos_sin_tramo"
        ],
        "candidatos_vectoriales_sin_rotulo": (
            diagnostico_red["aristas_sin_referencia"]
        ),
        "escala_confirmada": escala_confirmada,
        "confianza_escala": escala["confianza"],
        "criterio_longitud_computo": criterio_longitud,
        "tramos_computados": len(filas_computadas),
        "tramos_sin_seccion": sum(
            fila["estado"] == "sin_seccion"
            for fila in detalle
        ),
        "tramos_pendientes_escala": sum(
            fila["estado"] == "pendiente_escala"
            for fila in detalle
        ),
        "tramos_pendientes_revision": sum(
            fila["estado"]
            == "pendiente_revision_geometrica"
            for fila in detalle
        ),
        "tramos_confianza_geometrica_alta": sum(
            fila["confianza_geometria"] == "alta"
            for fila in detalle
        ),
        "tramos_confianza_geometrica_media": sum(
            fila["confianza_geometria"] == "media"
            for fila in detalle
        ),
        "cobertura_rotulos_porcentaje": (
            diagnostico_red[
                "cobertura_rotulos_vigas_porcentaje"
            ]
        ),
        "cobertura_tramos_porcentaje": round(
            (
                len(filas_computadas)
                / cantidad_objetivo
                * 100
            )
            if cantidad_objetivo
            else 0.0,
            2,
        ),
        "resultado_completo": (
            escala_confirmada
            and cantidad_objetivo > 0
            and len(filas_computadas)
            == cantidad_objetivo
            and diagnostico_red["rotulos_sin_tramo"]
            == 0
        ),
        "advertencias": [
            (
                "Cada fila representa un tramo delimitado "
                "por dos apoyos vectoriales consecutivos."
            ),
            (
                "Los candidatos vectoriales sin rótulo ni "
                "continuidad confirmada se excluyen del total."
            ),
            (
                "El área del fondo se informa por separado; "
                "su incorporación al total es configurable."
            ),
        ],
    }

    def total(campo):
        if not escala_confirmada or not filas_computadas:
            return None

        return round(
            sum(fila[campo] for fila in filas_computadas),
            3,
        )

    resultado = {
        "modo_geometria_vigas_riostra": (
            "tramos_entre_apoyos"
        ),
        "escala_plano_vigas": escala,
        "apoyos_columnas_vigas": deteccion_apoyos[
            "apoyos"
        ],
        "diagnostico_apoyos_columnas": (
            deteccion_apoyos["diagnostico"]
        ),
        "tramos_vigas_riostra": red["tramos"],
        "diagnostico_red_vigas_riostra": (
            diagnostico_red
        ),
        "rotulos_vigas_sin_tramo": red[
            "rotulos_sin_tramo"
        ],
        "candidatos_vectoriales_sin_rotulo": red[
            "aristas_sin_referencia"
        ],
        "vigas_riostra_computo_detalle": detalle,
        "resumen_vigas_riostra_por_tipo": (
            resumen_por_tipo
        ),
        "ejes_vigas_sin_rotulo": (
            diagnostico_legacy["ejes_sin_rotulo"]
        ),
        "longitud_total_entre_ejes_vigas_riostra_m": (
            total("longitud_entre_ejes_m")
        ),
        "longitud_total_libre_vigas_riostra_m": (
            total("longitud_libre_entre_caras_m")
        ),
        "longitud_total_vigas_riostra_m": total(
            "longitud_m"
        ),
        "hormigon_vigas_riostra_m3": total(
            "volumen_hormigon_m3"
        ),
        "encofrado_laterales_vigas_riostra_m2": total(
            "encofrado_laterales_m2"
        ),
        "encofrado_fondo_vigas_riostra_m2": total(
            "encofrado_fondo_m2"
        ),
        "encofrado_vigas_riostra_m2": total(
            "encofrado_total_m2"
        ),
        "validacion_computo_vigas_riostra": validacion,
    }

    return _incorporar_acero_vigas_riostra(
        resultado,
        armaduras_vigas,
        tolerancia_seccion_m=(
            tolerancia_seccion_armadura_m
        ),
        longitud_adicional_por_extremo_m=(
            longitud_adicional_barra_por_extremo_m
        ),
    )

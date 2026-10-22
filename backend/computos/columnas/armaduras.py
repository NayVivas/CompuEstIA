"""Extracción determinística de armaduras en detalles de columnas.

El módulo trabaja con palabras y coordenadas extraídas del PDF. No presupone
que el texto esté horizontal: reconstruye líneas horizontales y verticales,
algo necesario para planos exportados con rotación de página.

La armadura encontrada describe la columna. El motor de pedestales puede
usarla como respaldo cuando no existe una especificación propia del pedestal;
esa procedencia se conserva para que el resultado siga siendo auditable.
"""

from __future__ import annotations

from collections import defaultdict
from math import hypot
import re

from computos.columnas.deteccion import detectar_columnas


PATRON_BARRAS_LONGITUDINALES = re.compile(
    r"(?:^|\s|=)(?P<cantidad>\d{1,2})\s*"
    r"[ØΦ]\s*"
    r"(?P<diametro>\d+(?:\s*/\s*\d+)?)\s*[\"”]?",
    re.IGNORECASE,
)

PATRON_ESTRIBOS = re.compile(
    r"\bEST(?:RIBOS?)?\.?\s*"
    r"[ØΦ]\s*"
    r"(?P<diametro>\d+(?:\s*/\s*\d+)?)\s*[\"”]?\s*"
    r"(?:C\s*/\s*D|CADA|@)\s*"
    r"(?P<separacion>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unidad>CM|CMS|CM\.|CMS\.|M|M\.)\b",
    re.IGNORECASE,
)

PATRON_LONGITUD = re.compile(
    r"\bL\s*=\s*(?P<longitud>\d+(?:[.,]\d+)?)\s*M\.?\b",
    re.IGNORECASE,
)

PATRON_DISTRIBUCION = re.compile(
    r"(?:C\s*/\s*D|CADA|@)",
    re.IGNORECASE,
)


def _numero(valor):
    if valor is None:
        return None

    try:
        return float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _texto_normalizado(texto) -> str:
    return " ".join(
        str(texto or "")
        .replace("Φ", "Ø")
        .replace("ø", "Ø")
        .replace("”", '"')
        .replace("“", '"')
        .split()
    ).upper()


def _diametro_normalizado(texto) -> str:
    return re.sub(r"\s+", "", str(texto or "")).strip()


def _centro(palabra: dict) -> tuple[float, float]:
    return (
        (_numero(palabra.get("x0")) + _numero(palabra.get("x1"))) / 2,
        (_numero(palabra.get("y0")) + _numero(palabra.get("y1"))) / 2,
    )


def _palabras_compatibles(palabras) -> list[dict]:
    resultado = []

    for palabra in palabras:
        if not isinstance(palabra, dict):
            raise TypeError(
                "extraer_armaduras_columnas requiere palabras convertidas "
                "a diccionarios."
            )

        coordenadas = [
            _numero(palabra.get(campo))
            for campo in ("x0", "y0", "x1", "y1")
        ]

        if any(valor is None for valor in coordenadas):
            continue

        texto = str(palabra.get("texto") or "").strip()

        if not texto:
            continue

        resultado.append(
            {
                **palabra,
                "texto": texto,
                "pagina": int(_numero(palabra.get("pagina")) or 1),
                "x0": coordenadas[0],
                "y0": coordenadas[1],
                "x1": coordenadas[2],
                "y1": coordenadas[3],
            }
        )

    return resultado


def _crear_linea(
    palabras: list[dict],
    orientacion: str,
) -> dict:
    x0 = min(palabra["x0"] for palabra in palabras)
    y0 = min(palabra["y0"] for palabra in palabras)
    x1 = max(palabra["x1"] for palabra in palabras)
    y1 = max(palabra["y1"] for palabra in palabras)

    return {
        "pagina": palabras[0]["pagina"],
        "orientacion": orientacion,
        "texto": " ".join(
            palabra["texto"]
            for palabra in palabras
        ),
        "x0": x0,
        "y0": y0,
        "x1": x1,
        "y1": y1,
        "centro_x": (x0 + x1) / 2,
        "centro_y": (y0 + y1) / 2,
    }


def _dividir_por_separacion(
    palabras: list[dict],
    *,
    orientacion: str,
    separacion_maxima_pt: float,
) -> list[list[dict]]:
    if not palabras:
        return []

    if orientacion == "vertical":
        palabras = sorted(
            palabras,
            key=lambda palabra: (
                palabra["y0"],
                palabra["x0"],
            ),
        )
        inicio = "y0"
        final = "y1"
    else:
        palabras = sorted(
            palabras,
            key=lambda palabra: (
                palabra["x0"],
                palabra["y0"],
            ),
        )
        inicio = "x0"
        final = "x1"

    grupos = [[palabras[0]]]

    for palabra in palabras[1:]:
        anterior = grupos[-1][-1]
        separacion = palabra[inicio] - anterior[final]

        if separacion > separacion_maxima_pt:
            grupos.append([palabra])
        else:
            grupos[-1].append(palabra)

    return grupos


def _agrupar_lineas(
    palabras: list[dict],
    *,
    orientacion: str,
    tolerancia_alineacion_pt: float,
    separacion_maxima_pt: float,
) -> list[dict]:
    """Reconstruye líneas aun cuando la página está rotada."""

    por_pagina = defaultdict(list)

    for palabra in palabras:
        por_pagina[palabra["pagina"]].append(palabra)

    lineas = []

    for palabras_pagina in por_pagina.values():
        if orientacion == "vertical":
            coordenada = lambda palabra: _centro(palabra)[0]
        else:
            coordenada = lambda palabra: _centro(palabra)[1]

        ordenadas = sorted(
            palabras_pagina,
            key=lambda palabra: (
                coordenada(palabra),
                palabra["y0"],
                palabra["x0"],
            ),
        )
        bandas: list[dict] = []

        for palabra in ordenadas:
            valor = coordenada(palabra)

            if (
                not bandas
                or abs(valor - bandas[-1]["promedio"])
                > tolerancia_alineacion_pt
            ):
                bandas.append(
                    {
                        "promedio": valor,
                        "palabras": [palabra],
                    }
                )
                continue

            banda = bandas[-1]
            banda["palabras"].append(palabra)
            cantidad = len(banda["palabras"])
            banda["promedio"] = (
                banda["promedio"] * (cantidad - 1)
                + valor
            ) / cantidad

        for banda in bandas:
            for grupo in _dividir_por_separacion(
                banda["palabras"],
                orientacion=orientacion,
                separacion_maxima_pt=separacion_maxima_pt,
            ):
                lineas.append(
                    _crear_linea(
                        grupo,
                        orientacion,
                    )
                )

    return lineas


def _reconstruir_lineas(
    palabras: list[dict],
    *,
    tolerancia_alineacion_pt: float,
    separacion_maxima_pt: float,
) -> list[dict]:
    return [
        *_agrupar_lineas(
            palabras,
            orientacion="horizontal",
            tolerancia_alineacion_pt=tolerancia_alineacion_pt,
            separacion_maxima_pt=separacion_maxima_pt,
        ),
        *_agrupar_lineas(
            palabras,
            orientacion="vertical",
            tolerancia_alineacion_pt=tolerancia_alineacion_pt,
            separacion_maxima_pt=separacion_maxima_pt,
        ),
    ]


def _distancia_linea_titulo(
    linea: dict,
    titulo: dict,
) -> float:
    centro_x = _numero(titulo.get("centro_x"))
    centro_y = _numero(titulo.get("centro_y"))

    if centro_x is None or centro_y is None:
        centro_x = (
            _numero(titulo.get("x0"))
            + _numero(titulo.get("x1"))
        ) / 2
        centro_y = (
            _numero(titulo.get("y0"))
            + _numero(titulo.get("y1"))
        ) / 2

    return hypot(
        linea["centro_x"] - centro_x,
        linea["centro_y"] - centro_y,
    )


def _titulo_mas_cercano(
    linea: dict,
    titulos: list[dict],
    distancia_maxima_pt: float,
):
    candidatos = [
        titulo
        for titulo in titulos
        if titulo.get("pagina") == linea.get("pagina")
    ]

    if not candidatos:
        return None, None

    titulo = min(
        candidatos,
        key=lambda candidato: _distancia_linea_titulo(
            linea,
            candidato,
        ),
    )
    distancia = _distancia_linea_titulo(
        linea,
        titulo,
    )

    if distancia > distancia_maxima_pt:
        return None, distancia

    return titulo, distancia


def _clave_titulo(titulo: dict) -> tuple:
    return (
        titulo.get("pagina"),
        round(_numero(titulo.get("centro_x")) or 0.0, 3),
        round(_numero(titulo.get("centro_y")) or 0.0, 3),
    )


def _orientacion_titulo_detalle(
    titulo: dict,
    lineas: list[dict],
) -> str | None:
    candidatas = []

    for linea in lineas:
        if linea.get("pagina") != titulo.get("pagina"):
            continue

        texto = _texto_normalizado(linea.get("texto"))

        if "DETALLE" not in texto or "COLUMNA" not in texto:
            continue

        distancia = _distancia_linea_titulo(
            linea,
            titulo,
        )

        if distancia <= 45:
            candidatas.append(
                (distancia, linea["orientacion"])
            )

    if not candidatas:
        return None

    return min(candidatas)[1]


def _clave_referencia(referencia: str) -> tuple:
    coincidencia = re.fullmatch(r"([A-Z]+)(\d+)", referencia)

    if coincidencia:
        return (
            coincidencia.group(1),
            int(coincidencia.group(2)),
        )

    return (referencia, 0)


def _huella_armadura(armadura: dict) -> tuple:
    grupos = tuple(
        sorted(
            (
                int(grupo.get("cantidad") or 0),
                str(
                    grupo.get("diametro_pulgadas")
                    or ""
                ),
            )
            for grupo in armadura.get(
                "grupos_longitudinales",
                [],
            )
        )
    )
    estribo = armadura.get("estribo") or {}

    return (
        grupos,
        str(estribo.get("diametro_pulgadas") or ""),
        _numero(estribo.get("separacion_m")),
        _numero(estribo.get("longitud_indicada_m")),
    )


def consolidar_armaduras_columnas(
    *colecciones,
    selecciones=None,
) -> list[dict]:
    """Consolida fuentes sin ocultar especificaciones contradictorias.

    La primera colección tiene prioridad cuando dos fuentes completas son
    equivalentes. Si sus armaduras son distintas, la referencia queda en
    estado ``REVISAR`` y ambas alternativas permanecen documentadas.
    """

    por_referencia = defaultdict(list)
    selecciones = selecciones or {}

    for prioridad, coleccion in enumerate(colecciones):
        for armadura in coleccion or []:
            referencia = str(
                armadura.get("referencia") or ""
            ).strip().upper()

            if not referencia:
                continue

            por_referencia[referencia].append(
                (prioridad, armadura)
            )

    consolidadas = []

    for referencia, alternativas in por_referencia.items():
        seleccion = selecciones.get(("armadura", referencia))
        alternativas.sort(
            key=lambda item: (
                item[1].get("estado") != "CORRECTO",
                not bool(
                    seleccion
                    and str(item[1].get("origen") or "") == seleccion.get("origen")
                    and item[1].get("pagina") == seleccion.get("pagina")
                ),
                item[0],
            )
        )
        seleccionada = dict(alternativas[0][1])
        correctas = [
            armadura
            for _, armadura in alternativas
            if armadura.get("estado") == "CORRECTO"
        ]
        huellas = {
            _huella_armadura(armadura)
            for armadura in correctas
        }
        seleccion_coincidente = bool(
            seleccion
            and any(
                str(armadura.get("origen") or "") == seleccion.get("origen")
                and armadura.get("pagina") == seleccion.get("pagina")
                and armadura.get("estado") == "CORRECTO"
                for _, armadura in alternativas
            )
        )
        conflicto = len(huellas) > 1 and not seleccion_coincidente
        fuentes = list(
            dict.fromkeys(
                str(armadura.get("origen") or "")
                for _, armadura in alternativas
                if armadura.get("origen")
            )
        )
        seleccionada["fuentes_detectadas"] = fuentes
        seleccionada["conflicto_entre_fuentes"] = conflicto
        if seleccion_coincidente:
            seleccionada["seleccion_profesional"] = dict(seleccion)
        seleccionada["alternativas_detectadas"] = [
            {
                "origen": armadura.get("origen"),
                "estado": armadura.get("estado"),
                "grupos_longitudinales": armadura.get(
                    "grupos_longitudinales",
                    [],
                ),
                "estribo": armadura.get("estribo"),
            }
            for _, armadura in alternativas
        ]

        if conflicto:
            seleccionada["estado"] = "REVISAR"
            seleccionada["confianza"] = "baja"
            seleccionada.setdefault(
                "advertencias",
                [],
            ).append(
                "Se detectaron armaduras diferentes para la misma "
                "referencia en más de una fuente."
            )

        consolidadas.append(seleccionada)

    consolidadas.sort(
        key=lambda item: _clave_referencia(
            item["referencia"]
        )
    )
    return consolidadas


def extraer_armaduras_columnas(
    palabras,
    origen,
    correcciones=None,
    *,
    distancia_maxima_titulo_pt=80.0,
    tolerancia_alineacion_pt=1.25,
    separacion_maxima_pt=12.0,
) -> list[dict]:
    """Extrae armaduras longitudinales y estribos por columna.

    El resultado identifica la armadura de la columna y conserva la evidencia
    original. ``uso_en_pedestal_confirmado`` sigue indicando que no se leyó
    una confirmación explícita del plano. En una etapa posterior, la regla de
    respaldo puede aplicarla al pedestal de la misma referencia.
    """

    correcciones = correcciones or {}
    palabras = _palabras_compatibles(palabras)
    titulos = detectar_columnas(palabras)
    lineas = _reconstruir_lineas(
        palabras,
        tolerancia_alineacion_pt=float(
            tolerancia_alineacion_pt
        ),
        separacion_maxima_pt=float(
            separacion_maxima_pt
        ),
    )

    resultados = {
        _clave_titulo(titulo): {
            "titulo": titulo,
            "orientacion_titulo": (
                _orientacion_titulo_detalle(
                    titulo,
                    lineas,
                )
            ),
            "grupos_longitudinales": [],
            "estribos": [],
        }
        for titulo in titulos
    }

    longitudinales_vistos = set()
    estribos_vistos = set()

    for linea in lineas:
        texto = _texto_normalizado(linea.get("texto"))

        if not texto:
            continue

        # Una expresión con separación corresponde a barras distribuidas o
        # estribos, no a un grupo longitudinal de columna.
        if not PATRON_DISTRIBUCION.search(texto):
            for coincidencia in (
                PATRON_BARRAS_LONGITUDINALES.finditer(texto)
            ):
                titulo, distancia = _titulo_mas_cercano(
                    linea,
                    titulos,
                    float(distancia_maxima_titulo_pt),
                )

                if titulo is None:
                    continue

                datos_titulo = resultados[
                    _clave_titulo(titulo)
                ]

                # En páginas rotadas pueden formarse líneas horizontales
                # accidentales al cruzar dos textos verticales próximos.
                # El título DETALLE COLUMNA define la orientación verdadera
                # de las anotaciones de ese detalle.
                if (
                    datos_titulo["orientacion_titulo"]
                    and linea["orientacion"]
                    != datos_titulo["orientacion_titulo"]
                ):
                    continue

                cantidad = int(
                    coincidencia.group("cantidad")
                )
                diametro = _diametro_normalizado(
                    coincidencia.group("diametro")
                )
                clave = (
                    _clave_titulo(titulo),
                    cantidad,
                    diametro,
                    round(linea["centro_x"], 1),
                    round(linea["centro_y"], 1),
                )

                if clave in longitudinales_vistos:
                    continue

                longitudinales_vistos.add(clave)
                resultados[_clave_titulo(titulo)][
                    "grupos_longitudinales"
                ].append(
                    {
                        "cantidad": cantidad,
                        "diametro_pulgadas": diametro,
                        "texto_original": linea["texto"],
                        "orientacion_texto": linea[
                            "orientacion"
                        ],
                        "distancia_al_titulo_pdf": round(
                            distancia,
                            3,
                        ),
                        "rectangulo_pdf": {
                            campo: round(linea[campo], 3)
                            for campo in ("x0", "y0", "x1", "y1")
                        },
                    }
                )

        coincidencia_estribo = PATRON_ESTRIBOS.search(
            texto
        )

        if coincidencia_estribo is None:
            continue

        titulo, distancia = _titulo_mas_cercano(
            linea,
            titulos,
            float(distancia_maxima_titulo_pt),
        )

        if titulo is None:
            continue

        datos_titulo = resultados[
            _clave_titulo(titulo)
        ]

        if (
            datos_titulo["orientacion_titulo"]
            and linea["orientacion"]
            != datos_titulo["orientacion_titulo"]
        ):
            continue

        separacion = _numero(
            coincidencia_estribo.group("separacion")
        )
        unidad = coincidencia_estribo.group(
            "unidad"
        ).upper()
        separacion_m = (
            separacion / 100
            if unidad.startswith("CM")
            else separacion
        )
        coincidencia_longitud = PATRON_LONGITUD.search(
            texto
        )
        longitud_m = (
            _numero(
                coincidencia_longitud.group("longitud")
            )
            if coincidencia_longitud
            else None
        )
        diametro = _diametro_normalizado(
            coincidencia_estribo.group("diametro")
        )
        clave = (
            _clave_titulo(titulo),
            diametro,
            round(separacion_m, 4),
            round(linea["centro_x"], 1),
            round(linea["centro_y"], 1),
        )

        if clave in estribos_vistos:
            continue

        estribos_vistos.add(clave)
        resultados[_clave_titulo(titulo)][
            "estribos"
        ].append(
            {
                "diametro_pulgadas": diametro,
                "separacion_m": round(
                    separacion_m,
                    4,
                ),
                "longitud_indicada_m": longitud_m,
                "texto_original": linea["texto"],
                "orientacion_texto": linea[
                    "orientacion"
                ],
                "distancia_al_titulo_pdf": round(
                    distancia,
                    3,
                ),
                "rectangulo_pdf": {
                    campo: round(linea[campo], 3)
                    for campo in ("x0", "y0", "x1", "y1")
                },
            }
        )

    armaduras = []

    for datos in resultados.values():
        titulo = datos["titulo"]
        referencia_original = str(
            titulo.get("referencia") or ""
        ).strip().upper()
        referencia = str(
            correcciones.get(
                (
                    titulo.get("pagina"),
                    referencia_original,
                ),
                correcciones.get(
                    referencia_original,
                    referencia_original,
                ),
            )
        ).strip().upper()
        grupos = sorted(
            datos["grupos_longitudinales"],
            key=lambda grupo: (
                -grupo["cantidad"],
                grupo["diametro_pulgadas"],
            ),
        )
        estribos = sorted(
            datos["estribos"],
            key=lambda estribo: (
                estribo["distancia_al_titulo_pdf"],
                estribo["diametro_pulgadas"],
            ),
        )
        estribo = estribos[0] if estribos else None
        advertencias = []

        titulo_detalle_confirmado = bool(
            datos["orientacion_titulo"]
        )

        if not titulo_detalle_confirmado:
            advertencias.append(
                "La referencia no está acompañada por el título "
                "DETALLE COLUMNA."
            )

        if not grupos:
            advertencias.append(
                "No se detectaron grupos de barras longitudinales."
            )

        if estribo is None:
            advertencias.append(
                "No se detectó una especificación de estribos."
            )

        estado = (
            "CORRECTO"
            if grupos and estribo is not None
            else "REVISAR"
        )
        confianza = (
            "alta"
            if estado == "CORRECTO"
            and titulo_detalle_confirmado
            else (
                "media"
                if estado == "CORRECTO"
                else "baja"
            )
        )

        armaduras.append(
            {
                "referencia_original": referencia_original,
                "referencia": referencia,
                "pagina": titulo.get("pagina"),
                "origen": origen,
                "fue_corregida": (
                    referencia != referencia_original
                ),
                "grupos_longitudinales": grupos,
                "cantidad_barras_longitudinales": sum(
                    grupo["cantidad"]
                    for grupo in grupos
                ),
                "diametros_longitudinales_pulgadas": sorted(
                    {
                        grupo["diametro_pulgadas"]
                        for grupo in grupos
                    }
                ),
                "estribo": estribo,
                "cantidad_especificaciones_estribos": len(
                    estribos
                ),
                "estado": estado,
                "confianza": confianza,
                "advertencias": advertencias,
                "uso_en_pedestal_confirmado": False,
                "uso_en_pedestal_como_respaldo": True,
                "regla_uso_pedestal": (
                    "usar_si_no_hay_armadura_especifica_de_pedestal"
                ),
                "estado_uso_pedestal": (
                    "PENDIENTE_CONFIRMACION_PROFESIONAL"
                ),
                "posicion_titulo_pdf": {
                    "x": round(
                        _numero(titulo.get("centro_x")) or 0.0,
                        3,
                    ),
                    "y": round(
                        _numero(titulo.get("centro_y")) or 0.0,
                        3,
                    ),
                },
            }
        )

    armaduras.sort(
        key=lambda item: (
            item.get("pagina") or 0,
            _clave_referencia(item["referencia"]),
        )
    )
    return armaduras

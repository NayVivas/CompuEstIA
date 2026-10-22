"""Lectura geométrica de alturas de columnas en elevaciones de pórticos.

El extractor trabaja con coordenadas visuales normalizadas. No depende del
nombre del archivo ni de referencias concretas: relaciona cada rótulo de
columna con la cota vertical de su fila, el pórtico, el eje local y los niveles
que delimitan el tramo. Las dos vistas ortogonales de una misma columna se
consolidan mediante ``eje global + intervalo de niveles``.

Las observaciones contradictorias se conservan para revisión; nunca se elige
silenciosamente una referencia o una altura entre fuentes incompatibles.
"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import re
import unicodedata

from computos.documentos.analisis import extraer_palabras_normalizadas


_COLUMNA = re.compile(r"^C[-_ ]?(\d{1,3}[A-Z]?)$", re.IGNORECASE)
_NUMERO_DECIMAL = re.compile(r"^[+-]?(\d{1,2})[,.](\d{1,3})$")
_NIVEL = re.compile(r"^(?:NT|NPB|NS\d+|N\d+)$", re.IGNORECASE)
_ELEVACION = re.compile(r"^\(([+\-±]?[0-9]+(?:[,.][0-9]+)?)\)$")
_EJE_LETRA = re.compile(r"^[A-Z](?:'{1,2})?$")
_EJE_NUMERO = re.compile(r"^\d{1,2}(?:'{1,2})?$")


def _texto(valor: object) -> str:
    normal = unicodedata.normalize("NFKD", str(valor or ""))
    normal = "".join(
        caracter
        for caracter in normal
        if not unicodedata.combining(caracter)
    )
    return (
        normal.upper()
        .replace("’", "'")
        .replace("′", "'")
        .replace("″", "''")
        .strip()
    )


def _centro_x(palabra) -> float:
    return (palabra.caja_visual.x0 + palabra.caja_visual.x1) / 2


def _centro_y(palabra) -> float:
    return (palabra.caja_visual.y0 + palabra.caja_visual.y1) / 2


def _caja(palabra) -> dict:
    caja = palabra.caja_visual
    return {
        "x0": round(caja.x0, 2),
        "y0": round(caja.y0, 2),
        "x1": round(caja.x1, 2),
        "y1": round(caja.y1, 2),
    }


def _altura(texto: str) -> float | None:
    coincidencia = _NUMERO_DECIMAL.fullmatch(_texto(texto))
    if not coincidencia:
        return None
    valor = float(f"{coincidencia.group(1)}.{coincidencia.group(2)}")
    # Rango deliberadamente amplio para edificios. Fuera de él la cifra puede
    # ser una escala, una coordenada o una dimensión horizontal.
    if not 1.0 <= valor <= 12.0:
        return None
    return round(valor, 3)


def _elevacion(texto: str) -> float | None:
    coincidencia = _ELEVACION.fullmatch(_texto(texto))
    if not coincidencia:
        return None
    valor = coincidencia.group(1).replace("±", "0").replace(",", ".")
    try:
        return round(float(valor), 3)
    except ValueError:
        return None


def _rotulos_columnas(palabras) -> list[dict]:
    """Reconoce C13, C-13 y también C + 13 exportados por separado."""

    rotulos = []
    usados = set()

    for indice, palabra in enumerate(palabras):
        normal = _texto(palabra.texto)
        coincidencia = _COLUMNA.fullmatch(normal)
        if coincidencia:
            rotulos.append(
                {
                    "referencia": f"C{coincidencia.group(1)}",
                    "x": _centro_x(palabra),
                    "y": _centro_y(palabra),
                    "caja": _caja(palabra),
                }
            )
            usados.add(indice)

    for indice, palabra in enumerate(palabras):
        if indice in usados or _texto(palabra.texto) not in {"C", "COL"}:
            continue
        candidatos = [
            (otro_indice, otra)
            for otro_indice, otra in enumerate(palabras)
            if otro_indice not in usados
            and otro_indice != indice
            and re.fullmatch(r"\d{1,3}[A-Z]?", _texto(otra.texto))
            and abs(_centro_y(otra) - _centro_y(palabra)) <= 2.5
            and 0 <= otra.caja_visual.x0 - palabra.caja_visual.x1 <= 8
        ]
        if not candidatos:
            continue
        otro_indice, otra = min(
            candidatos,
            key=lambda item: item[1].caja_visual.x0,
        )
        referencia = f"C{_texto(otra.texto)}"
        rotulos.append(
            {
                "referencia": referencia,
                "x": (palabra.caja_visual.x0 + otra.caja_visual.x1) / 2,
                "y": (_centro_y(palabra) + _centro_y(otra)) / 2,
                "caja": {
                    "x0": round(palabra.caja_visual.x0, 2),
                    "y0": round(min(palabra.caja_visual.y0, otra.caja_visual.y0), 2),
                    "x1": round(otra.caja_visual.x1, 2),
                    "y1": round(max(palabra.caja_visual.y1, otra.caja_visual.y1), 2),
                },
            }
        )
        usados.update({indice, otro_indice})

    return rotulos


def _titulos_porticos(palabras) -> list[dict]:
    titulos = []
    for palabra in palabras:
        if _texto(palabra.texto) not in {"PORTICO", "PORTICOS"}:
            continue
        candidatos = [
            otra
            for otra in palabras
            if otra is not palabra
            and 0 <= otra.caja_visual.x0 - palabra.caja_visual.x1 <= 35
            and abs(_centro_y(otra) - _centro_y(palabra)) <= 2.5
            and (
                _EJE_LETRA.fullmatch(_texto(otra.texto))
                or _EJE_NUMERO.fullmatch(_texto(otra.texto))
            )
        ]
        if not candidatos:
            continue
        designacion = min(candidatos, key=lambda item: item.caja_visual.x0)
        titulos.append(
            {
                "designacion": _texto(designacion.texto),
                "x": _centro_x(palabra),
                "y": _centro_y(palabra),
            }
        )
    return titulos


def _niveles(palabras) -> list[dict]:
    resultado = []
    for palabra in palabras:
        nombre = _texto(palabra.texto)
        if not _NIVEL.fullmatch(nombre):
            continue
        candidatos = [
            otra
            for otra in palabras
            if otra is not palabra
            and 0 <= otra.caja_visual.x0 - palabra.caja_visual.x1 <= 55
            and abs(_centro_y(otra) - _centro_y(palabra)) <= 2.5
            and _elevacion(otra.texto) is not None
        ]
        cota = None
        if candidatos:
            cota = _elevacion(
                min(candidatos, key=lambda item: item.caja_visual.x0).texto
            )
        resultado.append(
            {
                "nombre": nombre,
                "cota_m": cota,
                "x": _centro_x(palabra),
                "y": _centro_y(palabra),
            }
        )
    return resultado


def _agrupar_marcadores(marcadores: list[dict]) -> list[list[dict]]:
    """Agrupa columnas de cotas verticales pertenecientes a un pórtico."""

    por_x = []
    for marcador in sorted(marcadores, key=lambda item: (item["x"], item["y"])):
        grupo_x = next(
            (
                grupo
                for grupo in por_x
                if abs(grupo[0]["x"] - marcador["x"]) <= 3.0
            ),
            None,
        )
        if grupo_x is None:
            grupo_x = []
            por_x.append(grupo_x)
        grupo_x.append(marcador)

    grupos = []
    for grupo_x in por_x:
        actual = []
        for marcador in sorted(grupo_x, key=lambda item: item["y"]):
            if actual and marcador["y"] - actual[-1]["y"] > 65:
                grupos.append(actual)
                actual = []
            actual.append(marcador)
        if actual:
            grupos.append(actual)
    return grupos


def _titulo_del_grupo(grupo, titulos):
    ultimo_y = max(item["y"] for item in grupo)
    x = sum(item["x"] for item in grupo) / len(grupo)
    candidatos = [
        titulo
        for titulo in titulos
        if 20 <= titulo["y"] - ultimo_y <= 65
        and abs(titulo["x"] - x) <= 100
    ]
    if not candidatos:
        return None
    return min(
        candidatos,
        key=lambda item: (
            abs(item["x"] - x),
            item["y"] - ultimo_y,
        ),
    )


def _intervalo_niveles(y: float, niveles: list[dict]) -> tuple[dict | None, dict | None]:
    superiores = [nivel for nivel in niveles if nivel["y"] < y - 2]
    inferiores = [nivel for nivel in niveles if nivel["y"] > y + 2]
    superior = max(superiores, key=lambda nivel: nivel["y"], default=None)
    inferior = min(inferiores, key=lambda nivel: nivel["y"], default=None)
    if superior and y - superior["y"] > 45:
        superior = None
    if inferior and inferior["y"] - y > 45:
        inferior = None
    return superior, inferior


def _completar_intervalo(
    superior: dict | None,
    inferior: dict | None,
    altura: float,
    niveles_globales: list[dict],
) -> tuple[dict | None, dict | None]:
    """Completa un nivel cortado del borde usando cotas explícitas del juego."""

    candidatos = [
        nivel
        for nivel in niveles_globales
        if nivel.get("cota_m") is not None
    ]
    if superior and not inferior and superior.get("cota_m") is not None:
        objetivo = superior["cota_m"] - altura
        coincidencias = [
            nivel
            for nivel in candidatos
            if abs(nivel["cota_m"] - objetivo) <= 0.12
        ]
        if coincidencias:
            inferior = min(
                coincidencias,
                key=lambda nivel: abs(nivel["cota_m"] - objetivo),
            )
    elif inferior and not superior and inferior.get("cota_m") is not None:
        objetivo = inferior["cota_m"] + altura
        coincidencias = [
            nivel
            for nivel in candidatos
            if abs(nivel["cota_m"] - objetivo) <= 0.12
        ]
        if coincidencias:
            superior = min(
                coincidencias,
                key=lambda nivel: abs(nivel["cota_m"] - objetivo),
            )
    return superior, inferior


def _ejes_del_grupo(palabras, grupo, titulo, rotulos) -> list[dict]:
    if not titulo or not rotulos:
        return []
    numerico = _EJE_NUMERO.fullmatch(titulo["designacion"]) is not None
    patron = _EJE_LETRA if numerico else _EJE_NUMERO
    y_esperada = titulo["y"] - 12.5
    minimo_x = min(rotulo["x"] for rotulo in rotulos) - 12
    maximo_x = max(rotulo["x"] for rotulo in rotulos) + 12
    return [
        {
            "nombre": _texto(palabra.texto),
            "x": _centro_x(palabra),
            "y": _centro_y(palabra),
        }
        for palabra in palabras
        if patron.fullmatch(_texto(palabra.texto))
        and abs(_centro_y(palabra) - y_esperada) <= 4.0
        and minimo_x <= _centro_x(palabra) <= maximo_x
    ]


def _eje_global(portico: str | None, eje_local: str | None) -> str | None:
    if not portico or not eje_local:
        return None
    if _EJE_NUMERO.fullmatch(portico) and _EJE_LETRA.fullmatch(eje_local):
        return f"{eje_local}-{portico}"
    if _EJE_LETRA.fullmatch(portico) and _EJE_NUMERO.fullmatch(eje_local):
        return f"{portico}-{eje_local}"
    return None


def _id_tramo(clave: str) -> str:
    legible = re.sub(r"[^A-Z0-9]+", "-", _texto(clave)).strip("-")
    huella = sha256(clave.encode("utf-8")).hexdigest()[:8]
    return f"COL-{legible[:48]}-{huella}"


def _orientacion_portico(valor: object) -> str | None:
    nombre = _texto(valor)
    if _EJE_LETRA.fullmatch(nombre):
        return "alfabetico"
    if _EJE_NUMERO.fullmatch(nombre):
        return "numerico"
    return None


def _evidencia_geometrica_fuerte(observacion: dict) -> bool:
    """Exige una unión precisa entre título, eje, rótulo y niveles.

    Una lectura débil se conserva para auditoría, pero no puede convertir por
    sí sola una diferencia de texto en una inconsistencia bloqueante.
    """

    distancia_eje = observacion.get("distancia_eje_pdf")
    distancia_titulo_x = observacion.get("distancia_titulo_x_pdf")
    distancia_titulo_y = observacion.get("distancia_titulo_y_pdf")
    return bool(
        observacion.get("eje_global")
        and observacion.get("nivel_superior")
        and observacion.get("nivel_inferior")
        and observacion.get("orientacion_portico")
        and isinstance(distancia_eje, (int, float))
        and distancia_eje <= 7.0
        and isinstance(distancia_titulo_x, (int, float))
        and distancia_titulo_x <= 60.0
        and isinstance(distancia_titulo_y, (int, float))
        and 20.0 <= distancia_titulo_y <= 65.0
    )


def _consolidar(observaciones: list[dict]) -> list[dict]:
    grupos = defaultdict(list)
    for observacion in observaciones:
        if (
            observacion.get("eje_global")
            and observacion.get("nivel_superior")
            and observacion.get("nivel_inferior")
        ):
            clave = "|".join(
                (
                    observacion["eje_global"],
                    observacion["nivel_inferior"],
                    observacion["nivel_superior"],
                )
            )
        else:
            clave = f"OBS|{observacion['observacion_id']}"
        grupos[clave].append(observacion)

    tramos = []
    for clave, fuentes in grupos.items():
        referencias = sorted({item["referencia"] for item in fuentes})
        alturas = sorted({round(item["altura_detectada_m"], 2) for item in fuentes})
        completa = not clave.startswith("OBS|")
        fuentes_fuertes = [
            item for item in fuentes if _evidencia_geometrica_fuerte(item)
        ]
        orientaciones_fuertes = {
            item["orientacion_portico"] for item in fuentes_fuertes
        }
        vistas_ortogonales_confirmadas = orientaciones_fuertes == {
            "alfabetico",
            "numerico",
        }
        referencias_fuertes = sorted(
            {item["referencia"] for item in fuentes_fuertes}
        )
        alturas_fuertes = sorted(
            {round(item["altura_detectada_m"], 2) for item in fuentes_fuertes}
        )
        conflictos = []
        if vistas_ortogonales_confirmadas and len(referencias_fuertes) > 1:
            conflictos.append("referencia")
        if vistas_ortogonales_confirmadas and len(alturas_fuertes) > 1:
            conflictos.append("altura")
        discrepancias_no_confirmadas = []
        if len(referencias) > 1 and "referencia" not in conflictos:
            discrepancias_no_confirmadas.append("referencia")
        if len(alturas) > 1 and "altura" not in conflictos:
            discrepancias_no_confirmadas.append("altura")
        referencia_confiable = (
            referencias_fuertes[0]
            if len(referencias_fuertes) == 1
            else referencias[0]
            if len(referencias) == 1
            else None
        )
        altura_confiable = (
            alturas_fuertes[0]
            if len(alturas_fuertes) == 1
            else alturas[0]
            if len(alturas) == 1
            else None
        )
        estado = (
            "conflicto_entre_vistas"
            if conflictos
            else "discrepancia_no_confirmada"
            if discrepancias_no_confirmadas
            and (referencia_confiable is None or altura_confiable is None)
            else "detectado_confirmable"
            if completa
            else "identidad_incompleta"
        )
        primera = fuentes[0]
        tramos.append(
            {
                "tramo_id": _id_tramo(clave),
                "eje_global": primera.get("eje_global"),
                "nivel_inferior": primera.get("nivel_inferior"),
                "nivel_superior": primera.get("nivel_superior"),
                "cota_inferior_m": primera.get("cota_inferior_m"),
                "cota_superior_m": primera.get("cota_superior_m"),
                "referencia": referencia_confiable,
                "referencias_candidatas": referencias,
                "altura_detectada_m": altura_confiable,
                "alturas_candidatas_m": alturas,
                "estado_extraccion": estado,
                "conflictos": conflictos,
                "discrepancias_no_confirmadas": discrepancias_no_confirmadas,
                "vistas_ortogonales_confirmadas": vistas_ortogonales_confirmadas,
                "cantidad_evidencias_fuertes": len(fuentes_fuertes),
                "cantidad_observaciones": len(fuentes),
                "paginas": sorted({item["pagina_origen"] for item in fuentes}),
                "porticos": sorted({item["portico"] for item in fuentes if item.get("portico")}),
                "evidencias": fuentes,
            }
        )
    return sorted(
        tramos,
        key=lambda item: (
            item.get("eje_global") or "ZZZ",
            item.get("cota_inferior_m")
            if item.get("cota_inferior_m") is not None
            else 999,
            item["tramo_id"],
        ),
    )


def extraer_alturas_porticos(
    ruta_pdf: str | Path,
    *,
    paginas_origen: list[int] | None = None,
) -> dict:
    """Extrae y consolida tramos de columna desde láminas de pórticos."""

    palabras = extraer_palabras_normalizadas(ruta_pdf)
    por_pagina = defaultdict(list)
    for palabra in palabras:
        por_pagina[palabra.pagina].append(palabra)

    niveles_globales = []
    claves_niveles = set()
    for palabras_pagina in por_pagina.values():
        for nivel in _niveles(palabras_pagina):
            clave = (nivel["nombre"], nivel.get("cota_m"))
            if clave not in claves_niveles:
                niveles_globales.append(nivel)
                claves_niveles.add(clave)

    observaciones = []
    paginas_diagnosticadas = []
    for pagina_motor, palabras_pagina in sorted(por_pagina.items()):
        pagina_origen = (
            paginas_origen[pagina_motor - 1]
            if paginas_origen and pagina_motor <= len(paginas_origen)
            else pagina_motor
        )
        rotulos = _rotulos_columnas(palabras_pagina)
        titulos = _titulos_porticos(palabras_pagina)
        niveles = _niveles(palabras_pagina)
        numeros = [
            {
                "altura": valor,
                "x": _centro_x(palabra),
                "y": _centro_y(palabra),
                "texto": palabra.texto,
                "caja": _caja(palabra),
            }
            for palabra in palabras_pagina
            if (valor := _altura(palabra.texto)) is not None
        ]

        marcadores = []
        for numero in numeros:
            inmediatos = [
                rotulo
                for rotulo in rotulos
                if 0 <= rotulo["x"] - numero["x"] <= 35
                and abs(rotulo["y"] - numero["y"]) <= 3.0
            ]
            if inmediatos:
                marcadores.append(numero)

        grupos = _agrupar_marcadores(marcadores)
        observaciones_antes = len(observaciones)
        for grupo in grupos:
            titulo = _titulo_del_grupo(grupo, titulos)
            portico = titulo["designacion"] if titulo else None
            centro_grupo_x = sum(item["x"] for item in grupo) / len(grupo)
            ultimo_grupo_y = max(item["y"] for item in grupo)
            rotulos_grupo = []
            por_marcador = []
            for marcador in grupo:
                siguientes = [
                    otro
                    for otro in marcadores
                    if otro["x"] > marcador["x"] + 5
                    and abs(otro["y"] - marcador["y"]) <= 3.0
                ]
                limite_x = min((item["x"] for item in siguientes), default=float("inf"))
                fila = [
                    rotulo
                    for rotulo in rotulos
                    if rotulo["x"] > marcador["x"]
                    and rotulo["x"] < limite_x
                    and abs(rotulo["y"] - marcador["y"]) <= 3.0
                ]
                rotulos_grupo.extend(fila)
                por_marcador.append((marcador, fila))

            ejes = _ejes_del_grupo(
                palabras_pagina,
                grupo,
                titulo,
                rotulos_grupo,
            )
            for marcador, fila in por_marcador:
                superior, inferior = _intervalo_niveles(marcador["y"], niveles)
                superior, inferior = _completar_intervalo(
                    superior,
                    inferior,
                    marcador["altura"],
                    niveles_globales,
                )
                for rotulo in fila:
                    eje = min(
                        ejes,
                        key=lambda item: abs(item["x"] - rotulo["x"]),
                        default=None,
                    )
                    if eje and abs(eje["x"] - rotulo["x"]) > 14:
                        eje = None
                    eje_local = eje["nombre"] if eje else None
                    clave_observacion = (
                        f"{pagina_origen}|{portico}|{rotulo['x']:.2f}|"
                        f"{rotulo['y']:.2f}|{rotulo['referencia']}"
                    )
                    observaciones.append(
                        {
                            "observacion_id": sha256(
                                clave_observacion.encode("utf-8")
                            ).hexdigest()[:16],
                            "pagina_motor": pagina_motor,
                            "pagina_origen": pagina_origen,
                            "portico": portico,
                            "orientacion_portico": _orientacion_portico(portico),
                            "eje_local": eje_local,
                            "eje_global": _eje_global(portico, eje_local),
                            "distancia_eje_pdf": (
                                round(abs(eje["x"] - rotulo["x"]), 2)
                                if eje
                                else None
                            ),
                            "distancia_titulo_x_pdf": (
                                round(abs(titulo["x"] - centro_grupo_x), 2)
                                if titulo
                                else None
                            ),
                            "distancia_titulo_y_pdf": (
                                round(titulo["y"] - ultimo_grupo_y, 2)
                                if titulo
                                else None
                            ),
                            "nivel_superior": superior["nombre"] if superior else None,
                            "nivel_inferior": inferior["nombre"] if inferior else None,
                            "cota_superior_m": superior.get("cota_m") if superior else None,
                            "cota_inferior_m": inferior.get("cota_m") if inferior else None,
                            "referencia": rotulo["referencia"],
                            "altura_detectada_m": marcador["altura"],
                            "texto_altura": marcador["texto"],
                            "posicion_rotulo_pdf": rotulo["caja"],
                            "posicion_altura_pdf": marcador["caja"],
                        }
                    )

        paginas_diagnosticadas.append(
            {
                "pagina_motor": pagina_motor,
                "pagina_origen": pagina_origen,
                "porticos_detectados": sorted(
                    {titulo["designacion"] for titulo in titulos}
                ),
                "rotulos_columnas": len(rotulos),
                "cotas_verticales": len(marcadores),
                "observaciones_generadas": len(observaciones) - observaciones_antes,
            }
        )

    tramos = _consolidar(observaciones)
    confirmables = [
        tramo
        for tramo in tramos
        if tramo["estado_extraccion"] == "detectado_confirmable"
    ]
    conflictos = [
        tramo
        for tramo in tramos
        if tramo["estado_extraccion"] == "conflicto_entre_vistas"
    ]
    incompletos = [
        tramo
        for tramo in tramos
        if tramo["estado_extraccion"] == "identidad_incompleta"
    ]
    discrepancias = [
        tramo
        for tramo in tramos
        if tramo.get("discrepancias_no_confirmadas")
    ]
    advertencias = []
    if conflictos:
        advertencias.append(
            "Hay tramos con referencias o alturas distintas entre vistas de pórtico."
        )
    if incompletos:
        advertencias.append(
            "Hay observaciones sin eje global o intervalo de niveles; se conservan fuera del cómputo automático."
        )
    if discrepancias:
        advertencias.append(
            "Hay diferencias con evidencia geométrica insuficiente; se conservan como observaciones no bloqueantes."
        )
    if not confirmables:
        advertencias.append(
            "No se obtuvo ningún tramo con columna, altura, eje y niveles completos."
        )

    return {
        "estado": "detectado" if observaciones else "sin_alturas_detectables",
        "paginas_analizadas": len(por_pagina),
        "paginas": paginas_diagnosticadas,
        "observaciones": observaciones,
        "tramos": tramos,
        "cantidad_observaciones": len(observaciones),
        "cantidad_tramos": len(tramos),
        "cantidad_tramos_confirmables": len(confirmables),
        "cantidad_conflictos": len(conflictos),
        "cantidad_discrepancias_no_confirmadas": len(discrepancias),
        "cantidad_identidad_incompleta": len(incompletos),
        "advertencias": advertencias,
        "criterio_deduplicacion": "eje_global_mas_intervalo_de_niveles",
    }


def asociar_secciones_porticos(analisis: dict, secciones: list[dict]) -> dict:
    """Añade secciones inequívocas a los tramos sin resolver conflictos."""

    resultado = deepcopy(analisis)
    dimensiones = defaultdict(set)
    origenes = defaultdict(list)
    for seccion in secciones or []:
        if not isinstance(seccion, dict) or seccion.get("estado") != "CORRECTO":
            continue
        referencia = _texto(seccion.get("referencia"))
        try:
            ancho = round(float(seccion.get("dimension_1_m")), 4)
            largo = round(float(seccion.get("dimension_2_m")), 4)
        except (TypeError, ValueError):
            continue
        if not referencia or ancho <= 0 or largo <= 0:
            continue
        dimensiones[referencia].add((ancho, largo))
        origenes[(referencia, ancho, largo)].append(
            {
                "archivo": seccion.get("origen"),
                "pagina": seccion.get("pagina"),
            }
        )

    disponibles = 0
    faltantes = set()
    conflictos = set()
    for tramo in resultado.get("tramos", []):
        referencia = _texto(tramo.get("referencia"))
        opciones = dimensiones.get(referencia, set())
        if len(opciones) == 1:
            ancho, largo = next(iter(opciones))
            tramo.update(
                {
                    "ancho_m": ancho,
                    "largo_m": largo,
                    "estado_seccion": "detectada",
                    "fuentes_seccion": origenes[(referencia, ancho, largo)],
                }
            )
            disponibles += 1
        elif len(opciones) > 1:
            tramo["estado_seccion"] = "conflicto_entre_fuentes"
            tramo["secciones_candidatas_m"] = [
                {"ancho_m": ancho, "largo_m": largo}
                for ancho, largo in sorted(opciones)
            ]
            if referencia:
                conflictos.add(referencia)
        else:
            tramo["estado_seccion"] = "sin_seccion"
            if referencia:
                faltantes.add(referencia)

    resultado["cantidad_tramos_con_seccion"] = disponibles
    resultado["referencias_sin_seccion"] = sorted(faltantes)
    resultado["referencias_con_conflicto_seccion"] = sorted(conflictos)
    return resultado

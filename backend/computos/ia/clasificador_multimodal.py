"""Fusión multimodal explicable para páginas de planos técnicos.

EXP19 observa la secuencia de texto. EXP22 conserva esa señal y la combina
con la posición de las palabras, el aspecto renderizado de la página, la
geometría vectorial del PDF y OCR adaptativo. La fuerza informada no es una
probabilidad: cada etiqueta conserva las fuentes que respaldan su decisión.

Este módulo no calcula cantidades ni contiene nombres de proyectos, archivos
o números de página. Su única responsabilidad es describir y enrutar páginas.
"""

from __future__ import annotations

from copy import deepcopy
import math
import os
import re
import unicodedata
from typing import Any

import numpy as np
import pymupdf


VERSION_EXP22 = "22.0"
LADO_RENDER = 160
OBJETIVOS = ("disciplinas", "roles_documentales", "contenidos")

CONTENIDOS_ESTRUCTURALES = {
    "armaduras_acero",
    "columnas_pilares",
    "elementos_estructurales_generales",
    "escaleras_estructurales",
    "fundaciones",
    "losas_forjados",
    "muros_estructurales",
    "porticos",
    "rampas",
    "vigas",
}

CONTENIDOS_POR_DISCIPLINA = {
    "sanitaria": {
        "agua_caliente",
        "agua_fria",
        "artefactos_sanitarios",
        "canerias_sanitarias",
        "cloacal",
        "instalaciones_sanitarias",
        "pluvial",
    },
    "sanitarias": {
        "agua_caliente",
        "agua_fria",
        "artefactos_sanitarios",
        "canerias_sanitarias",
        "cloacal",
        "instalaciones_sanitarias",
        "pluvial",
    },
    "electricidad": {
        "baja_tension",
        "fuerza",
        "iluminacion",
        "instalaciones_electricas",
    },
    "electrica": {
        "baja_tension",
        "fuerza",
        "iluminacion",
        "instalaciones_electricas",
    },
    "gas": {"instalaciones_gas"},
}

UMBRALES_MODELO = {
    "disciplinas": 0.10,
    "roles_documentales": 0.20,
    "contenidos": 0.20,
}

PATRONES_ESPACIALES = {
    "disciplinas": {
        "estructura": r"\b(?:ESTRUCTUR|HORMIGON ARMADO|CONCRETO ARMADO|CIMENTACION|FUNDACION)\w*\b",
        "arquitectura": r"\b(?:ARQUITECTUR|FACHADA|DISTRIBUCION)\w*\b",
        "sanitaria": r"\b(?:SANITARI|HIDRAULIC|CLOACAL|DESAGUE)\w*\b",
        "sanitarias": r"\b(?:SANITARI|HIDRAULIC|CLOACAL|DESAGUE)\w*\b",
        "electricidad": r"\b(?:ELECTRIC|ILUMINACION|TOMACORRIENTE|UNIFILAR)\w*\b",
        "electrica": r"\b(?:ELECTRIC|ILUMINACION|TOMACORRIENTE|UNIFILAR)\w*\b",
        "gas": r"\b(?:INSTALACION DE GAS|GAS NATURAL|GASODUCTO)\b",
    },
    "roles_documentales": {
        "planta": r"\b(?:PLANTA|IMPLANTACION)\b",
        "detalle": r"\bDETALLE\w*\b",
        "cuadro_planilla": r"\b(?:CUADRO|PLANILLA|TABLA)\b",
        "corte": r"\b(?:CORTE|SECCION)\b",
        "elevacion_fachada": r"\b(?:ELEVACION|FACHADA|ALZADO)\b",
        "elevacion_porticos": r"\bPORTICO\w*\b",
        "isometrico": r"\bISOMETRI\w*\b",
    },
    "contenidos": {
        "fundaciones": r"\b(?:FUNDACION|CIMENTACION|CIMIENTO|ZAPATA|PILOTE|ENCEPADO)\w*\b",
        "columnas_pilares": r"\b(?:COLUMNA|PILAR|CASTILLO|PEDESTAL|DADO)\w*\b",
        "vigas": r"\b(?:VIGA|RIOSTRA|TRABE|DALA)\w*\b",
        "losas_forjados": r"\b(?:LOSA|FORJADO|LOSACERO)\w*\b",
        "armaduras_acero": r"\b(?:ARMADURA|ARMADO|ESTRIBO|ACERO|VARILLA)\w*\b",
        "muros_estructurales": r"\b(?:MURO ESTRUCTURAL|MURO DE CONTENCION|PANTALLA)\w*\b",
        "porticos": r"\bPORTICO\w*\b",
        "instalaciones_sanitarias": r"\b(?:SANITARI|HIDRAULIC|CLOACAL|DESAGUE)\w*\b",
        "instalaciones_electricas": r"\b(?:ELECTRIC|ILUMINACION|TOMACORRIENTE|UNIFILAR)\w*\b",
        "instalaciones_gas": r"\b(?:INSTALACION DE GAS|GAS NATURAL|GASODUCTO)\b",
    },
}


def _normalizar(texto: str) -> str:
    texto = "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", str(texto).upper())
        if not unicodedata.combining(caracter)
    )
    return re.sub(r"\s+", " ", texto).strip()


def _numero(valor: Any, predeterminado: float = 0.0) -> float:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return predeterminado


def _orientacion_linea(punto_a, punto_b) -> str:
    dx = abs(float(punto_b.x) - float(punto_a.x))
    dy = abs(float(punto_b.y) - float(punto_a.y))
    longitud = math.hypot(dx, dy)
    if longitud < 0.5:
        return "punto"
    if dy <= max(0.8, dx * 0.08):
        return "horizontal"
    if dx <= max(0.8, dy * 0.08):
        return "vertical"
    return "diagonal"


def _rasgos_vectoriales(pagina: pymupdf.Page) -> dict:
    try:
        dibujos = pagina.get_drawings()
    except Exception:
        dibujos = []

    segmentos = {"horizontal": 0, "vertical": 0, "diagonal": 0}
    rectangulos = 0
    curvas = 0
    trazos_discontinuos = 0
    longitudes = []
    for dibujo in dibujos:
        guiones = str(dibujo.get("dashes") or "").strip()
        if guiones and guiones not in {"[] 0", "[]0"}:
            trazos_discontinuos += 1
        for item in dibujo.get("items") or []:
            tipo = item[0]
            if tipo == "l" and len(item) >= 3:
                orientacion = _orientacion_linea(item[1], item[2])
                if orientacion in segmentos:
                    segmentos[orientacion] += 1
                    longitudes.append(
                        math.hypot(item[2].x - item[1].x, item[2].y - item[1].y)
                    )
            elif tipo == "re":
                rectangulos += 1
            elif tipo in {"c", "qu"}:
                curvas += 1

    return {
        "objetos_vectoriales": len(dibujos),
        "segmentos": sum(segmentos.values()),
        "segmentos_horizontales": segmentos["horizontal"],
        "segmentos_verticales": segmentos["vertical"],
        "segmentos_diagonales": segmentos["diagonal"],
        "rectangulos": rectangulos,
        "curvas": curvas,
        "trazos_discontinuos": trazos_discontinuos,
        "longitud_vectorial_mediana_pt": round(float(np.median(longitudes)), 3)
        if longitudes
        else 0.0,
    }


def _rasgos_raster(pagina: pymupdf.Page) -> dict:
    ancho = float(pagina.rect.width)
    alto = float(pagina.rect.height)
    vacio = {
        "densidad_tinta": 0.0,
        "contraste_horizontal": 0.0,
        "contraste_vertical": 0.0,
        "cuadrantes_tinta": [0.0] * 16,
    }
    if ancho <= 0 or alto <= 0:
        return vacio

    escala = (LADO_RENDER - 2) / max(ancho, alto)
    try:
        pixmap = pagina.get_pixmap(
            matrix=pymupdf.Matrix(escala, escala),
            colorspace=pymupdf.csGRAY,
            alpha=False,
        )
        gris = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
            pixmap.height, pixmap.width, pixmap.n
        )[..., 0]
    except Exception:
        return vacio

    lienzo = np.full((LADO_RENDER, LADO_RENDER), 255, dtype=np.uint8)
    y0 = (LADO_RENDER - pixmap.height) // 2
    x0 = (LADO_RENDER - pixmap.width) // 2
    lienzo[y0 : y0 + pixmap.height, x0 : x0 + pixmap.width] = gris
    normalizado = lienzo.astype(np.float32) / 255.0
    tinta = 1.0 - normalizado
    cuadrantes = tinta.reshape(4, 40, 4, 40).mean(axis=(1, 3)).ravel()
    return {
        "densidad_tinta": round(float(tinta.mean()), 6),
        "contraste_horizontal": round(
            float(np.abs(np.diff(normalizado, axis=0)).mean()), 6
        ),
        "contraste_vertical": round(
            float(np.abs(np.diff(normalizado, axis=1)).mean()), 6
        ),
        "cuadrantes_tinta": [round(float(valor), 6) for valor in cuadrantes],
    }


def _rasgos_espaciales(pagina: pymupdf.Page, texto: str) -> dict:
    palabras = pagina.get_text("words", sort=False) or []
    ancho = max(float(pagina.rect.width), 1.0)
    alto = max(float(pagina.rect.height), 1.0)
    zonas = {
        "superior": [],
        "central": [],
        "inferior": [],
        "izquierda": [],
        "derecha": [],
    }
    numeros = 0
    diametros = 0
    for palabra in palabras:
        if len(palabra) < 5:
            continue
        x0, y0, x1, y1, contenido = palabra[:5]
        contenido = str(contenido).strip()
        if not contenido:
            continue
        cx = (float(x0) + float(x1)) / (2 * ancho)
        cy = (float(y0) + float(y1)) / (2 * alto)
        if cy < 0.25:
            zonas["superior"].append(contenido)
        elif cy > 0.75:
            zonas["inferior"].append(contenido)
        else:
            zonas["central"].append(contenido)
        if cx < 0.30:
            zonas["izquierda"].append(contenido)
        elif cx > 0.70:
            zonas["derecha"].append(contenido)
        if re.search(r"\d", contenido):
            numeros += 1
        if re.search(r"[Ø∅#]|(?:DIAM|DIAMETRO)", _normalizar(contenido)):
            diametros += 1

    total = max(len(palabras), 1)
    normal = _normalizar(texto)
    terminos_tecnicos = len(
        re.findall(
            r"\b(?:FUNDACION|CIMENTACION|CIMIENTO|ZAPATA|COLUMNA|PILAR|"
            r"CASTILLO|VIGA|RIOSTRA|ARMADURA|ESTRIBO|PORTICO|LOSA|CORTE|"
            r"SECCION|DETALLE|PLANTA)S?\b",
            normal,
        )
    )
    return {
        "palabras": len(palabras),
        "fraccion_palabras_numericas": round(numeros / total, 6),
        "marcas_diametro": diametros,
        "terminos_tecnicos": terminos_tecnicos,
        "texto_por_zona": {
            nombre: " ".join(contenidos)[:1200]
            for nombre, contenidos in zonas.items()
        },
    }


def extraer_caracteristicas_multimodales(
    pagina: pymupdf.Page,
    texto: str,
) -> dict:
    """Extrae rasgos compactos y auditables de cuatro modalidades."""

    return {
        "version": VERSION_EXP22,
        "pagina": {
            "ancho_pt": round(float(pagina.rect.width), 3),
            "alto_pt": round(float(pagina.rect.height), 3),
            "rotacion_grados": int(pagina.rotation),
            "imagenes": len(pagina.get_images(full=True) or []),
        },
        "texto_espacial": _rasgos_espaciales(pagina, texto),
        "geometria_vectorial": _rasgos_vectoriales(pagina),
        "imagen_renderizada": _rasgos_raster(pagina),
    }


def motivos_ocr_adaptativo(texto: str, caracteristicas: dict) -> list[str]:
    """Decide si conviene complementar el texto, no solo si está vacío."""

    if os.getenv("COMPUTOESTIA_OCR_ADAPTATIVO", "1").strip().casefold() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return []
    caracteres = len(str(texto or "").strip())
    vector = caracteristicas.get("geometria_vectorial", {})
    espacial = caracteristicas.get("texto_espacial", {})
    objetos = int(vector.get("objetos_vectoriales", 0))
    terminos = int(espacial.get("terminos_tecnicos", 0))
    if caracteres < 10:
        return ["sin_texto_nativo"]
    if caracteres < 80 and objetos >= 50:
        return ["texto_nativo_escaso_en_plano_vectorial"]
    if caracteres < 250 and objetos >= 1000 and terminos == 0:
        return ["texto_parcial_sin_contexto_tecnico"]
    return []


def fusionar_textos(texto_nativo: str, texto_ocr: str) -> str:
    """Une OCR y texto nativo sin repetir líneas idénticas."""

    salida = []
    vistas = set()
    for origen in (texto_nativo, texto_ocr):
        for linea in str(origen or "").replace("\r", "\n").split("\n"):
            linea = re.sub(r"\s+", " ", linea).strip()
            clave = _normalizar(linea)
            if not clave or clave in vistas:
                continue
            vistas.add(clave)
            salida.append(linea)
    return "\n".join(salida)


def _detalle_modelo(modelo: dict | None, objetivo: str) -> dict[str, dict]:
    return {
        str(item.get("etiqueta")): item
        for item in (modelo or {})
        .get("objetivos", {})
        .get(objetivo, {})
        .get("detalle", [])
        if item.get("etiqueta")
    }


def _soporte_modelo(item: dict) -> float:
    margen = _numero(item.get("margen"))
    return max(0.0, min(1.0, 0.62 + 0.28 * math.tanh(margen)))


def _compatibilidad_plano_tecnico(caracteristicas: dict) -> tuple[float, list[str]]:
    """Valora si la página se comporta como plano, sin asignar disciplina."""

    espacial = caracteristicas.get("texto_espacial", {})
    vector = caracteristicas.get("geometria_vectorial", {})
    raster = caracteristicas.get("imagen_renderizada", {})
    pagina = caracteristicas.get("pagina", {})
    puntaje = 0.0
    fuentes = []
    palabras = int(espacial.get("palabras", 0))
    tecnicos = int(espacial.get("terminos_tecnicos", 0))
    numericas = _numero(espacial.get("fraccion_palabras_numericas"))
    diametros = int(espacial.get("marcas_diametro", 0))
    objetos = int(vector.get("objetos_vectoriales", 0))
    segmentos = int(vector.get("segmentos", 0))
    densidad = _numero(raster.get("densidad_tinta"))
    imagenes = int(pagina.get("imagenes", 0))

    if palabras >= 5:
        puntaje += 0.08
        fuentes.append("texto_distribuido_en_pagina")
    if tecnicos:
        puntaje += min(0.28, 0.14 + tecnicos * 0.025)
        fuentes.append("vocabulario_tecnico")
    if numericas >= 0.05:
        puntaje += min(0.14, 0.07 + numericas * 0.25)
        fuentes.append("anotaciones_numericas")
    if diametros:
        puntaje += 0.12
        fuentes.append("simbolos_de_armadura")
    if objetos >= 20 or segmentos >= 40:
        puntaje += 0.18
        fuentes.append("geometria_vectorial_de_plano")
    if objetos >= 250 or segmentos >= 600:
        puntaje += 0.08
        fuentes.append("alta_densidad_vectorial")
    if 0.004 <= densidad <= 0.55:
        puntaje += 0.08
        fuentes.append("trazado_visible_renderizado")
    if imagenes and densidad >= 0.02:
        puntaje += 0.12
        fuentes.append("lamina_rasterizada")
    return min(1.0, puntaje), fuentes


def _soporte_espacial(
    objetivo: str,
    etiqueta: str,
    caracteristicas: dict,
) -> tuple[float, list[str]]:
    patron = PATRONES_ESPACIALES.get(objetivo, {}).get(etiqueta)
    if not patron:
        return 0.0, []
    zonas = caracteristicas.get("texto_espacial", {}).get("texto_por_zona", {})
    halladas = [
        zona
        for zona in ("inferior", "derecha", "superior", "central")
        if re.search(patron, _normalizar(zonas.get(zona, "")))
    ]
    if not halladas:
        return 0.0, []
    zonas_titulo = set(halladas).intersection({"inferior", "derecha", "superior"})
    return (
        0.78 if zonas_titulo else 0.62,
        [f"rotulo_en_zona:{zona}" for zona in halladas[:2]],
    )


def _titulo_estructural_explicito(fuente_tecnica: dict) -> bool:
    return bool(fuente_tecnica.get("roles") or fuente_tecnica.get("tipologias"))


def _disciplina_dominante_no_estructural(modelo: dict | None) -> str | None:
    detalle = _detalle_modelo(modelo, "disciplinas")
    candidatas = [
        item
        for etiqueta, item in detalle.items()
        if etiqueta not in {"estructura", "arquitectura", "otra"}
        and item.get("seleccionada")
    ]
    candidatas.sort(key=lambda item: _numero(item.get("margen")), reverse=True)
    if not candidatas:
        return None
    estructura = detalle.get("estructura", {})
    if _numero(candidatas[0].get("margen")) >= 0.20 and _numero(
        estructura.get("margen"), -1.0
    ) < 0:
        return str(candidatas[0]["etiqueta"])
    return None


def fusionar_clasificacion(
    modelo: dict | None,
    evidencia: dict,
    caracteristicas: dict,
    fuente_tecnica: dict,
) -> dict:
    """Fusiona modalidades y conserva la explicación por etiqueta."""

    resultado = deepcopy(evidencia)
    resultado.update(
        {
            "estado": "clasificado_multimodal",
            "metodo": "EXP22_fusion_multimodal_explicable",
            "modelo": "EXP22",
            "modelo_textual_base": "EXP19" if modelo else None,
            "version_modelo": VERSION_EXP22,
            "modalidades": [
                "texto",
                "posicion_textual",
                "imagen_renderizada",
                "geometria_vectorial",
            ],
        }
    )
    compatibilidad, fuentes_tecnicas = _compatibilidad_plano_tecnico(
        caracteristicas
    )
    resultado["caracteristicas_resumen"] = {
        "palabras": caracteristicas.get("texto_espacial", {}).get("palabras", 0),
        "objetos_vectoriales": caracteristicas.get("geometria_vectorial", {}).get(
            "objetos_vectoriales", 0
        ),
        "segmentos": caracteristicas.get("geometria_vectorial", {}).get(
            "segmentos", 0
        ),
        "densidad_tinta": round(
            _numero(
                caracteristicas.get("imagen_renderizada", {}).get(
                    "densidad_tinta", 0
                )
            ),
            4,
        ),
        "compatibilidad_plano_tecnico": round(compatibilidad, 4),
    }
    resultado["evidencia_multimodal_pagina"] = fuentes_tecnicas
    decisiones = []
    propuestas = {objetivo: [] for objetivo in OBJETIVOS}
    dominante_no_estructural = _disciplina_dominante_no_estructural(modelo)

    for objetivo in OBJETIVOS:
        confirmadas = list(
            dict.fromkeys(
                resultado.get("objetivos", {})
                .get(objetivo, {})
                .get("etiquetas", [])
            )
        )
        detalle = _detalle_modelo(modelo, objetivo)
        if (
            objetivo == "disciplinas"
            and "estructura" in confirmadas
            and dominante_no_estructural
            and not _titulo_estructural_explicito(fuente_tecnica)
        ):
            confirmadas.remove("estructura")
            decisiones.append(
                {
                    "objetivo": objetivo,
                    "etiqueta": "estructura",
                    "decision": "descartada_por_conflicto",
                    "fuerza": 0.0,
                    "fuentes": [
                        "evidencia_lexica_aislada",
                        f"modelo_textual_dominante:{dominante_no_estructural}",
                    ],
                }
            )

        for etiqueta in list(confirmadas):
            soporte_espacial, fuentes_espaciales = _soporte_espacial(
                objetivo, etiqueta, caracteristicas
            )
            fuentes = ["evidencia_textual_contextual", *fuentes_espaciales]
            fuerza = max(0.78, 0.76 + compatibilidad * 0.16, soporte_espacial)
            item = detalle.get(etiqueta)
            if item and item.get("seleccionada"):
                fuentes.append("modelo_textual_EXP19")
                fuerza = max(fuerza, 0.92)
            if objetivo in {"roles_documentales", "contenidos"} and fuente_tecnica.get(
                "roles"
            ):
                fuentes.append("posicion_y_titulo_tecnico")
                fuerza = max(fuerza, 0.94)
            decisiones.append(
                {
                    "objetivo": objetivo,
                    "etiqueta": etiqueta,
                    "decision": "confirmada",
                    "fuerza": round(fuerza, 4),
                    "fuentes": list(dict.fromkeys(fuentes)),
                }
            )

        for etiqueta, item in detalle.items():
            if not item.get("seleccionada") or etiqueta in confirmadas:
                continue
            margen = _numero(item.get("margen"))
            soporte_espacial, fuentes_espaciales = _soporte_espacial(
                objetivo, etiqueta, caracteristicas
            )
            aceptar = margen >= UMBRALES_MODELO[objetivo] and (
                compatibilidad >= 0.25 or soporte_espacial >= 0.60
            )
            if objetivo == "contenidos":
                disciplinas = set(
                    resultado.get("objetivos", {})
                    .get("disciplinas", {})
                    .get("etiquetas", [])
                )
                if dominante_no_estructural:
                    disciplinas.discard("estructura")
                    disciplinas.add(dominante_no_estructural)
                if etiqueta in CONTENIDOS_ESTRUCTURALES and "estructura" not in disciplinas:
                    aceptar = False
                for disciplina, contenidos in CONTENIDOS_POR_DISCIPLINA.items():
                    if etiqueta in contenidos and disciplina not in disciplinas:
                        aceptar = False
            if aceptar:
                confirmadas.append(etiqueta)
                fuerza = _soporte_modelo(item) * 0.70 + max(
                    compatibilidad, soporte_espacial
                ) * 0.30
                decisiones.append(
                    {
                        "objetivo": objetivo,
                        "etiqueta": etiqueta,
                        "decision": "confirmada",
                        "fuerza": round(fuerza, 4),
                        "fuentes": list(
                            dict.fromkeys(
                                [
                                    "modelo_textual_EXP19",
                                    *fuentes_espaciales,
                                    *fuentes_tecnicas[:3],
                                ]
                            )
                        ),
                    }
                )
            else:
                propuestas[objetivo].append(etiqueta)
        resultado.setdefault("objetivos", {}).setdefault(objetivo, {})[
            "etiquetas"
        ] = list(dict.fromkeys(confirmadas))

    if dominante_no_estructural:
        disciplinas = resultado["objetivos"]["disciplinas"]["etiquetas"]
        resultado["objetivos"]["disciplinas"]["etiquetas"] = [
            etiqueta for etiqueta in disciplinas if etiqueta != "estructura"
        ]
        if dominante_no_estructural not in resultado["objetivos"]["disciplinas"][
            "etiquetas"
        ]:
            resultado["objetivos"]["disciplinas"]["etiquetas"].append(
                dominante_no_estructural
            )
        contenidos = resultado["objetivos"]["contenidos"]["etiquetas"]
        retirados = [
            etiqueta for etiqueta in contenidos if etiqueta in CONTENIDOS_ESTRUCTURALES
        ]
        resultado["objetivos"]["contenidos"]["etiquetas"] = [
            etiqueta for etiqueta in contenidos if etiqueta not in CONTENIDOS_ESTRUCTURALES
        ]
        propuestas["contenidos"] = list(
            dict.fromkeys(propuestas["contenidos"] + retirados)
        )

    fuerzas = [
        item["fuerza"]
        for item in decisiones
        if item.get("decision") == "confirmada"
    ]
    confianza = sum(fuerzas) / len(fuerzas) if fuerzas else 0.0
    motivos = []
    if not resultado["objetivos"]["disciplinas"]["etiquetas"]:
        motivos.append("No se pudo identificar la disciplina con respaldo suficiente.")
    if confianza and confianza < 0.65:
        motivos.append("La fusión multimodal produjo evidencia débil.")
    tiene_etiquetas = any(
        resultado.get("objetivos", {}).get(objetivo, {}).get("etiquetas", [])
        for objetivo in OBJETIVOS
    )
    if not tiene_etiquetas:
        resultado["estado"] = "sin_clasificacion"
    resultado.update(
        {
            "decisiones_multimodales": decisiones,
            "propuestas_modelo_sin_evidencia": propuestas,
            "confianza_explicable": round(confianza, 4),
            "nota_confianza": (
                "Fuerza de evidencia usada para ordenar revisiones; no es una probabilidad calibrada."
            ),
            "motivos_revision": motivos,
            "requiere_revision": bool(motivos),
            "tiene_sugerencias": any(propuestas.values()),
        }
    )
    return resultado


def proponer_roles_motor(clasificacion: dict, fuente_tecnica: dict) -> dict:
    """Propone fuentes del motor; títulos y revisiones tienen prioridad."""

    exclusiones = set(fuente_tecnica.get("exclusiones_roles", []))
    explicitos = [
        rol
        for rol in dict.fromkeys(fuente_tecnica.get("roles", []))
        if rol not in exclusiones
    ]
    objetivos = clasificacion.get("objetivos", {})
    disciplinas = set(objetivos.get("disciplinas", {}).get("etiquetas", []))
    roles_documentales = set(
        objetivos.get("roles_documentales", {}).get("etiquetas", [])
    )
    contenidos = set(objetivos.get("contenidos", {}).get("etiquetas", []))
    puntajes = {rol: 1.0 for rol in explicitos}
    origenes = {rol: "titulo_tecnico_explicito" for rol in explicitos}
    if "estructura" not in disciplinas:
        return {
            "roles": explicitos,
            "origen": (
                "titulo_tecnico_explicito"
                if explicitos
                else "sin_compatibilidad_estructural"
            ),
            "origenes": origenes,
            "puntajes": puntajes,
        }

    fuerza = {
        (item["objetivo"], item["etiqueta"]): _numero(item.get("fuerza"))
        for item in clasificacion.get("decisiones_multimodales", [])
        if item.get("decision") == "confirmada"
    }

    def minimo(*claves) -> float:
        valores = [fuerza.get(clave, 0.0) for clave in claves]
        return min(valores) if valores else 0.0

    if "planta" in roles_documentales and "fundaciones" in contenidos:
        puntajes.setdefault("planta", minimo(
            ("disciplinas", "estructura"),
            ("roles_documentales", "planta"),
            ("contenidos", "fundaciones"),
        ))
    if roles_documentales.intersection({"detalle", "cuadro_planilla"}) and "fundaciones" in contenidos:
        rol = max(
            roles_documentales.intersection({"detalle", "cuadro_planilla"}),
            key=lambda etiqueta: fuerza.get(("roles_documentales", etiqueta), 0.0),
        )
        puntajes.setdefault("detalles", minimo(
            ("disciplinas", "estructura"),
            ("roles_documentales", rol),
            ("contenidos", "fundaciones"),
        ))
    if "columnas_pilares" in contenidos and roles_documentales.intersection(
        {"detalle", "cuadro_planilla"}
    ):
        rol = max(
            roles_documentales.intersection({"detalle", "cuadro_planilla"}),
            key=lambda etiqueta: fuerza.get(("roles_documentales", etiqueta), 0.0),
        )
        puntajes.setdefault("columnas", minimo(
            ("disciplinas", "estructura"),
            ("roles_documentales", rol),
            ("contenidos", "columnas_pilares"),
        ))
    if "porticos" in contenidos or "elevacion_porticos" in roles_documentales:
        apoyo = (
            ("contenidos", "porticos")
            if "porticos" in contenidos
            else ("roles_documentales", "elevacion_porticos")
        )
        puntajes.setdefault(
            "porticos", minimo(("disciplinas", "estructura"), apoyo)
        )
    for rol in exclusiones:
        puntajes.pop(rol, None)
        origenes.pop(rol, None)

    # Los rótulos explícitos son una base, no un retorno anticipado. Es muy
    # común que una sola lámina reúna planta, cuadro de zapatas, cuadro de
    # columnas y detalles. En esos casos las otras modalidades pueden completar
    # los roles que no aparecen como título independiente.
    tipologia_explicita = bool(fuente_tecnica.get("tipologias"))
    for rol, puntaje in puntajes.items():
        if rol in origenes or puntaje < 0.70:
            continue
        origenes[rol] = (
            "inferencia_multimodal_con_contexto_tecnico"
            if explicitos and tipologia_explicita and puntaje >= 0.80
            else "inferencia_multimodal"
        )

    roles = [
        rol
        for rol, puntaje in puntajes.items()
        if rol in origenes and (rol in explicitos or puntaje >= 0.70)
    ]
    tipos_origen = set(origenes.get(rol) for rol in roles)
    if not roles:
        origen = "sin_fuente_inequivoca"
    elif tipos_origen == {"titulo_tecnico_explicito"}:
        origen = "titulo_tecnico_explicito"
    elif "titulo_tecnico_explicito" in tipos_origen:
        origen = "titulo_tecnico_mas_inferencia"
    else:
        origen = "inferencia_multimodal"
    return {
        "roles": roles,
        "origen": origen,
        "origenes": {rol: origenes[rol] for rol in roles},
        "puntajes": {rol: round(puntaje, 4) for rol, puntaje in puntajes.items()},
    }

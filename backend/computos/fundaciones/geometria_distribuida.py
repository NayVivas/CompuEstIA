"""Propuestas y cómputo auditable para zapatas acotadas por ocurrencia.

Este flujo se usa cuando no existe un cuadro X/Y/H inequívoco. El extractor
propone datos, pero ninguna cantidad se genera hasta que un profesional revisa
cada ocurrencia o la excluye expresamente.
"""

from __future__ import annotations

import base64
from collections import Counter
import math
from pathlib import Path
import re
from typing import Iterable

import pymupdf

from computos.documentos.analisis import extraer_palabras_normalizadas
from computos.documentos.modelos import Caja, PalabraNormalizada
from computos.referencias import extraer_candidatos_referencias, descubrir_catalogo_referencias
from computos.fundaciones.cuadros import localizar_estructura_cuadro, extraer_dimensiones_cuadro
from computos.fundaciones.geometria_cotas import (
    contornos_y_segmentos, dimensiones_del_contorno, altura_detalle_tipico,
)


PREFIJOS_FUNDACION = {"F", "Z", "ZA", "ZAP", "ZPT"}
PATRON_NUMERO = re.compile(
    r"(?<![\w/])(?P<signo>[+-]?)(?P<valor>(?:\d{1,3}(?:[.,]\d+)?|[.,]\d+))\s*(?P<unidad>MM|CM|M)?(?![\w/])",
    re.I,
)
PATRON_DIMENSION_COMPUESTA = re.compile(
    r"(?P<a>\d+(?:[.,]\d+)?)\s*[X×]\s*(?P<b>\d+(?:[.,]\d+)?)",
    re.I,
)
PATRON_REFERENCIA_REVISADA = re.compile(r"^[A-ZÑ][A-ZÑ0-9._/-]{0,39}$")


def _centro(caja: Caja) -> tuple[float, float]:
    return ((caja.x0 + caja.x1) / 2, (caja.y0 + caja.y1) / 2)


def _caja_diccionario(caja: Caja) -> dict:
    return {
        "x0": round(caja.x0, 3),
        "y0": round(caja.y0, 3),
        "x1": round(caja.x1, 3),
        "y1": round(caja.y1, 3),
    }


def _contexto_linea(
    palabra: PalabraNormalizada,
    palabras: Iterable[PalabraNormalizada],
) -> str:
    return " ".join(
        item.texto
        for item in palabras
        if item.pagina == palabra.pagina
        and item.numero_bloque == palabra.numero_bloque
        and item.numero_linea == palabra.numero_linea
    ).upper()


def _valor_metros(valor: str, unidad: str | None) -> float | None:
    try:
        numero = float(valor.replace(",", "."))
    except ValueError:
        return None
    unidad = (unidad or "").upper()
    if unidad == "CM":
        numero /= 100
    elif unidad == "MM":
        numero /= 1000
    if not 0.20 <= numero <= 12.0:
        return None
    return round(numero, 4)


def _candidatos_dimensiones(
    palabras: list[PalabraNormalizada],
) -> list[dict]:
    candidatos = []
    for indice, palabra in enumerate(palabras):
        texto = palabra.texto.upper().strip()
        contexto = _contexto_linea(palabra, palabras)
        if any(marca in contexto for marca in ("N.P.F", "NPF", "N.P.T", "NPT", "NIVEL", "ELEV.")):
            continue
        if any(marca in contexto for marca in ("EST.", "ESTRIB", "VARILLA", "ARMAD", "ACERO")):
            continue
        if any(simbolo in texto for simbolo in ("Ø", "∅", "@", "#", "/")):
            continue

        compuesta = PATRON_DIMENSION_COMPUESTA.fullmatch(texto.strip("()[]"))
        coincidencias = []
        if compuesta:
            coincidencias = [
                (compuesta.group("a"), None, "compuesta-a"),
                (compuesta.group("b"), None, "compuesta-b"),
            ]
        else:
            completa = PATRON_NUMERO.fullmatch(texto.strip("()[]=:;"))
            if completa and not completa.group("signo"):
                coincidencias = [
                    (completa.group("valor"), completa.group("unidad"), "simple")
                ]

        for valor_texto, unidad, componente in coincidencias:
            valor = _valor_metros(valor_texto, unidad)
            if valor is None:
                continue
            # Los enteros pequeños son frecuentes en cotas generales. Se
            # aceptan como propuesta, pero con menor prioridad que un decimal.
            decimal_explicito = "." in valor_texto or "," in valor_texto or bool(unidad)
            candidatos.append(
                {
                    "id": f"n-{indice}-{componente}",
                    "pagina": palabra.pagina,
                    "valor_m": valor,
                    "texto": palabra.texto,
                    "caja": palabra.caja_visual,
                    "centro": _centro(palabra.caja_visual),
                    "decimal_explicito": decimal_explicito,
                    "grupo": indice,
                    "compuesta": bool(compuesta),
                }
            )
    return candidatos


def _referencias_planta(
    palabras: list[PalabraNormalizada],
    referencias_validas: set[str] | None = None,
) -> list[dict]:
    referencias = []
    ancho = max((palabra.caja_visual.x1 for palabra in palabras), default=1.0)
    alto = max((palabra.caja_visual.y1 for palabra in palabras), default=1.0)
    diagonal = max(math.hypot(ancho, alto), 1.0)
    marcas_detalle = [
        palabra
        for palabra in palabras
        if re.fullmatch(
            r"DETALLES?|CORTE|SECCION|TIPOS?|CUADRO|PLANILLA|TABLA",
            palabra.texto.upper().strip(".:"),
        )
    ]
    for candidato in extraer_candidatos_referencias(palabras):
        ref = candidato.referencia
        if (referencias_validas is not None and ref.canonica not in referencias_validas) or (
            referencias_validas is None and ref.prefijo not in PREFIJOS_FUNDACION
        ):
            continue
        indices = set(candidato.indices_origen)
        origen = next((palabras[indice] for indice in indices), None)
        if origen is None:
            continue
        contexto = _contexto_linea(origen, palabras)
        if re.search(r"\b(?:DETALLES?|CORTE|SECCION|TIPOS?|CUADRO|PLANILLA|TABLA)\b", contexto):
            continue
        centro_candidato = _centro(candidato.caja_visual)
        # No se descarta una referencia solo por estar cerca de la palabra
        # "DETALLE": en láminas densas el título de un croquis puede quedar a
        # pocos centímetros visuales de una zapata válida de la planta. Sí se
        # excluye el rótulo que aparece inmediatamente a la derecha de un
        # encabezado de detalle en la misma banda horizontal.
        if any(
            (
                abs(_centro(marca.caja_visual)[1] - centro_candidato[1])
                <= max(8.0, marca.caja_visual.alto)
                or abs(_centro(marca.caja_visual)[0] - centro_candidato[0])
                <= max(8.0, marca.caja_visual.ancho)
            )
            and math.hypot(
                _centro(marca.caja_visual)[0] - centro_candidato[0],
                _centro(marca.caja_visual)[1] - centro_candidato[1],
            )
            <= diagonal * 0.18
            for marca in marcas_detalle
        ):
            continue
        referencias.append(
            {
                "referencia": ref.canonica,
                "texto": ref.texto_original,
                "pagina": candidato.pagina,
                "caja": candidato.caja_visual,
                "centro": centro_candidato,
                "indices": tuple(candidato.indices_origen),
            }
        )

    # El extractor puede reconocer la misma referencia desde una palabra y
    # desde una combinación de palabras. Se conserva la caja más amplia.
    deduplicadas = {}
    for item in referencias:
        clave = (
            item["pagina"],
            item["referencia"],
            round(item["centro"][0], 1),
            round(item["centro"][1], 1),
        )
        anterior = deduplicadas.get(clave)
        if anterior is None or item["caja"].ancho > anterior["caja"].ancho:
            deduplicadas[clave] = item
    return sorted(
        deduplicadas.values(),
        key=lambda item: (item["pagina"], item["centro"][1], item["centro"][0]),
    )


def _alternativas_dimensiones(
    referencia: dict,
    numeros: list[dict],
    ancho_pagina: float,
    alto_pagina: float,
) -> list[dict]:
    rx, ry = referencia["centro"]
    diagonal = max(math.hypot(ancho_pagina, alto_pagina), 1.0)
    radio = diagonal * 0.18
    cercanos = []
    for numero in numeros:
        if numero["pagina"] != referencia["pagina"]:
            continue
        nx, ny = numero["centro"]
        distancia = math.hypot(nx - rx, ny - ry)
        if distancia > radio:
            continue
        cercanos.append(
            {
                **numero,
                "distancia": distancia,
                "eje_relativo": "horizontal" if abs(nx - rx) >= abs(ny - ry) else "vertical",
            }
        )

    cercanos.sort(
        key=lambda item: (
            item["distancia"] + (0 if item["decimal_explicito"] else diagonal * 0.018),
            item["id"],
        )
    )
    cercanos = cercanos[:12]
    return [
        {
            "valor_m": item["valor_m"],
            "texto": item["texto"],
            "distancia_pt": round(item["distancia"], 2),
            "eje_relativo": item["eje_relativo"],
            "caja_visual": _caja_diccionario(item["caja"]),
        }
        for item in cercanos[:8]
    ]


def _proponer_altura(
    referencia: dict,
    palabras: list[PalabraNormalizada],
) -> float | None:
    # Una H explícita solo pertenece al rótulo si comparte su línea original.
    # La altura de una columna en otro sector no es altura de una zapata.
    for indice in referencia.get("indices", ()):
        contexto = _contexto_linea(palabras[indice], palabras)
        coincidencia = re.search(
            r"\b(?:H|HZ|ESP(?:ESOR)?|PERALTE)\s*[=:]\s*(\d+(?:[.,]\d+)?)\s*(MM|CM|M)?\b",
            contexto,
        )
        if not coincidencia:
            continue
        valor = _valor_metros(coincidencia.group(1), coincidencia.group(2))
        if valor is None:
            continue
        return valor
    return None


def _paginas_vista_previa(ruta: Path) -> list[dict]:
    paginas = []
    with pymupdf.open(ruta) as documento:
        for numero, pagina in enumerate(documento, start=1):
            ancho = float(pagina.rect.width)
            alto = float(pagina.rect.height)
            escala = min(1.8, max(0.7, 1400 / max(ancho, alto, 1)))
            pixmap = pagina.get_pixmap(
                matrix=pymupdf.Matrix(escala, escala),
                colorspace=pymupdf.csRGB,
                alpha=False,
            )
            jpeg = pixmap.tobytes("jpeg", jpg_quality=62)
            paginas.append(
                {
                    "pagina_motor": numero,
                    "ancho_visual_pt": round(ancho, 3),
                    "alto_visual_pt": round(alto, 3),
                    "imagen": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii"),
                }
            )
    return paginas


def preparar_revision_geometrica(
    ruta_planta: str | Path,
    *,
    fuentes_planta: list[dict],
    identidad_fuentes: dict,
    ruta_detalles: str | Path | None = None,
) -> dict:
    """Genera una propuesta por ocurrencia sin convertirla aún en cantidades."""

    ruta_planta = Path(ruta_planta)
    palabras = extraer_palabras_normalizadas(ruta_planta)
    dimensiones_por_tipo = {}
    if ruta_detalles is not None:
        try:
            palabras_detalle = extraer_palabras_normalizadas(ruta_detalles)
            catalogo = descubrir_catalogo_referencias(palabras_detalle)
            cuadro = localizar_estructura_cuadro(palabras_detalle, catalogo, exigir_armadura=False)
            filas = extraer_dimensiones_cuadro(cuadro)
            repetidas = {ref for ref, cantidad in Counter(f['referencia'] for f in filas).items() if cantidad > 1}
            if catalogo.contexto_local_confirmado:
                dimensiones_por_tipo = {f['referencia']: f for f in filas if f['referencia'] not in repetidas}
        except ValueError:
            pass  # Sin una tabla verificable se conservan las propuestas geométricas.
    referencias = _referencias_planta(palabras, set(dimensiones_por_tipo) if dimensiones_por_tipo else None)
    referencias_no_interpretadas = [
        {"texto": p.texto, "pagina_motor": p.pagina,
         "caja_visual": _caja_diccionario(p.caja_visual)}
        for p in palabras if re.fullmatch(r"(?:F|Z|ZA|ZAP|ZPT)[._-][A-ZÑ]", p.texto.upper())
    ]
    # Una planta válida puede no tener rótulos que el lector reconozca. La
    # revisión permite ubicar manualmente esas ocurrencias sin inventarlas.
    numeros = _candidatos_dimensiones(palabras)
    geometria_paginas = {}
    alturas_paginas = {}
    with pymupdf.open(ruta_planta) as documento:
        for pagina_n, pagina in enumerate(documento, start=1):
            rectangulos, segmentos = contornos_y_segmentos(pagina)
            geometria_paginas[pagina_n] = rectangulos
            alturas_paginas[pagina_n] = altura_detalle_tipico(
                [p for p in palabras if p.pagina == pagina_n], numeros, segmentos,
            )
    paginas = _paginas_vista_previa(ruta_planta)
    for pagina in paginas:
        indice = pagina["pagina_motor"] - 1
        if indice < len(fuentes_planta):
            pagina["fuente"] = {
                clave: fuentes_planta[indice].get(clave)
                for clave in ("archivo", "sha256", "pagina")
            }
    dimensiones_pagina = {
        pagina["pagina_motor"]: (
            pagina["ancho_visual_pt"],
            pagina["alto_visual_pt"],
        )
        for pagina in paginas
    }
    apariciones = Counter()
    elementos = []
    for referencia in referencias:
        apariciones[referencia["referencia"]] += 1
        numero = apariciones[referencia["referencia"]]
        ancho, alto = dimensiones_pagina[referencia["pagina"]]
        alternativas = _alternativas_dimensiones(
            referencia,
            numeros,
            ancho,
            alto,
        )
        tipo_tabla = dimensiones_por_tipo.get(referencia['referencia'])
        contorno = dimensiones_del_contorno(
            referencia, numeros, geometria_paginas[referencia['pagina']],
        )
        x_m = contorno['x_m'] if contorno else None
        y_m = contorno['y_m'] if contorno else None
        h_m = _proponer_altura(referencia, palabras)
        altura_tipica = alturas_paginas[referencia['pagina']]
        if h_m is None and altura_tipica:
            h_m = altura_tipica['h_m']
        if tipo_tabla:
            x_m, y_m, h_m = (float(tipo_tabla[c]) for c in ('x', 'y', 'h'))
        fuente = (
            fuentes_planta[referencia["pagina"] - 1]
            if referencia["pagina"] - 1 < len(fuentes_planta)
            else fuentes_planta[0]
        )
        elementos.append(
            {
                "id": f"{referencia['referencia']}-{numero:03d}-p{referencia['pagina']:03d}",
                "referencia_propuesta": referencia["referencia"],
                "texto_original": referencia["texto"],
                "aparicion": numero,
                "pagina_motor": referencia["pagina"],
                "fuente": {
                    "archivo": fuente.get("archivo"),
                    "sha256": fuente.get("sha256"),
                    "pagina": fuente.get("pagina"),
                },
                "caja_visual": _caja_diccionario(referencia["caja"]),
                "centro_visual": {
                    "x": round(referencia["centro"][0], 3),
                    "y": round(referencia["centro"][1], 3),
                },
                "x_m_propuesto": x_m,
                "y_m_propuesto": y_m,
                "h_m_propuesto": h_m,
                "origen_dimensiones": "cuadro_local_tipado" if tipo_tabla else (
                    contorno['origen'] if contorno else 'sin_asociacion_verificable'
                ),
                "evidencia_dimensiones": contorno if not tipo_tabla else None,
                "evidencia_altura": altura_tipica if not tipo_tabla else None,
                "alternativas_dimensiones": alternativas,
                "requiere_revision": True,
            }
        )

    return {
        "version": 1,
        "tipo": "zapatas_aisladas_geometria_distribuida",
        "identidad_fuentes": identidad_fuentes["sha256"],
        "fuentes": identidad_fuentes["fuentes"],
        "cantidad_elementos": len(elementos),
        "cantidad_referencias": len(apariciones),
        "elementos": elementos,
        "referencias_no_interpretadas": referencias_no_interpretadas,
        "paginas": paginas,
        "alcance": (
            "Se proponen dimensiones desde cuadros locales o contornos con dos cotas coherentes; "
            "un número cercano sin asociación queda solo como alternativa, no como dimensión. "
            "Cada ocurrencia puede confirmarse, reubicarse o excluirse; el profesional "
            "puede añadir las omitidas indicando su posición en la planta. "
            "Este flujo habilita hormigón y encofrado; no supone armaduras ausentes."
        ),
    }


def validar_revision_geometrica(decision: dict, propuesta: dict) -> dict:
    if not isinstance(decision, dict):
        raise ValueError("La revisión geométrica debe ser un objeto JSON.")
    if decision.get("identidad_fuentes") != propuesta.get("identidad_fuentes"):
        raise ValueError(
            "La revisión geométrica pertenece a otra combinación de archivos o páginas."
        )
    for campo, minimo, maximo in (("revisor", 2, 160), ("motivo", 10, 1000)):
        valor = decision.get(campo)
        if not isinstance(valor, str) or not minimo <= len(valor.strip()) <= maximo:
            raise ValueError(f"{campo}: longitud inválida en la revisión geométrica.")
    filas = decision.get("elementos")
    if not isinstance(filas, list) or len(filas) > 5000:
        raise ValueError("La revisión geométrica debe contener una lista de elementos.")
    propuestas = {item["id"]: item for item in propuesta["elementos"]}
    recibidas = {item.get("id") for item in filas if isinstance(item, dict)}
    adicionales = recibidas - set(propuestas)
    if (len(recibidas) != len(filas) or not set(propuestas).issubset(recibidas)
            or len(adicionales) > 500 or any(
                not isinstance(identificador, str) or
                not re.fullmatch(r"manual-[0-9a-f-]{36}", identificador)
                for identificador in adicionales
            )):
        raise ValueError(
            "Deben revisarse todas las ocurrencias propuestas; solo se admiten nuevas ubicaciones manuales sin duplicados."
        )

    normalizadas = []
    paginas = {pagina["pagina_motor"]: pagina for pagina in propuesta["paginas"]}
    for fila in filas:
        original = propuestas.get(fila["id"])
        try:
            pagina_numero = int(fila.get("pagina_motor", original["pagina_motor"] if original else 0))
        except (ValueError, TypeError):
            raise ValueError(f"Página inválida en {fila['id']}.") from None
        if (original and pagina_numero != original["pagina_motor"]) or pagina_numero not in paginas:
            raise ValueError(f"La ubicación de {fila['id']} pertenece a otra página.")
        pagina = paginas[pagina_numero]
        incluir = fila.get("incluir") is True
        referencia = str(fila.get("referencia", "")).upper().strip()
        if not PATRON_REFERENCIA_REVISADA.fullmatch(referencia):
            raise ValueError(f"Referencia inválida en {fila.get('id')}.")
        if incluir:
            centro = fila.get("centro_visual") or (original or {}).get("centro_visual")
            if not isinstance(centro, dict):
                raise ValueError(f"Ubicá {fila['id']} en la planta antes de incluirla.")
            try:
                centro = {eje: round(float(centro[eje]), 3) for eje in ("x", "y")}
            except (KeyError, TypeError, ValueError):
                raise ValueError(f"La posición de {fila['id']} es inválida.") from None
            if (not all(math.isfinite(valor) for valor in centro.values())
                    or not 0 <= centro["x"] <= pagina["ancho_visual_pt"]
                    or not 0 <= centro["y"] <= pagina["alto_visual_pt"]):
                raise ValueError(f"La posición de {fila['id']} queda fuera de la planta.")
            dimensiones = []
            for campo in ("x_m", "y_m", "h_m"):
                try:
                    valor = float(str(fila.get(campo, "")).replace(",", "."))
                except (TypeError, ValueError) as error:
                    raise ValueError(f"{campo} es obligatorio en {fila['id']}.") from error
                if not 0 < valor <= 100:
                    raise ValueError(f"{campo} está fuera de rango en {fila['id']}.")
                dimensiones.append(round(valor, 4))
            x_m, y_m, h_m = dimensiones
            motivo_exclusion = None
        else:
            motivo_exclusion = str(fila.get("motivo_exclusion", "")).strip()
            if len(motivo_exclusion) < 10 or len(motivo_exclusion) > 1000:
                raise ValueError(
                    f"Explicá por qué se excluye {fila['id']} con al menos 10 caracteres."
                )
            x_m = y_m = h_m = None
            centro = None
        normalizadas.append(
            {
                "id": fila["id"],
                "incluir": incluir,
                "referencia": referencia,
                "x_m": x_m,
                "y_m": y_m,
                "h_m": h_m,
                "pagina_motor": pagina_numero,
                "centro_visual": centro,
                "origen_ubicacion": "manual" if original is None else (
                    "corregida" if centro != original["centro_visual"] else "detectada"
                ),
                "motivo_exclusion": motivo_exclusion,
            }
        )
    return {
        "version": 1,
        "identidad_fuentes": propuesta["identidad_fuentes"],
        "revisor": decision["revisor"].strip(),
        "motivo": decision["motivo"].strip(),
        "elementos": normalizadas,
    }


def calcular_geometria_revisada(propuesta: dict, decision: dict) -> dict:
    revision = validar_revision_geometrica(decision, propuesta)
    originales = {item["id"]: item for item in propuesta["elementos"]}
    incluidas = [item for item in revision["elementos"] if item["incluir"]]
    if not incluidas:
        raise ValueError("La revisión excluyó todas las fundaciones; no hay cantidades para calcular.")

    fundaciones = []
    ubicaciones = []
    encofrados = []
    conteo = Counter()
    volumen_total = 0.0
    encofrado_total = 0.0
    for fila in incluidas:
        origen = originales.get(fila["id"])
        pagina = next(p for p in propuesta["paginas"] if p["pagina_motor"] == fila["pagina_motor"])
        volumen = fila["x_m"] * fila["y_m"] * fila["h_m"]
        encofrado = 2 * (fila["x_m"] + fila["y_m"]) * fila["h_m"]
        volumen_total += volumen
        encofrado_total += encofrado
        conteo[fila["referencia"]] += 1
        fundaciones.append(
            {
                "identificador": fila["id"],
                "referencia": fila["referencia"],
                "cantidad": 1,
                "x": fila["x_m"],
                "y": fila["y_m"],
                "h": fila["h_m"],
                "volumen_unitario": round(volumen, 6),
                "volumen_total": round(volumen, 6),
                "origen": "revision_profesional_geometria_distribuida",
                "origen_ubicacion": fila["origen_ubicacion"],
            }
        )
        ubicacion = {
            "identificador": fila["id"],
            "fundacion_id": fila["id"],
            "referencia": fila["referencia"],
            "pagina": pagina["fuente"].get("pagina", fila["pagina_motor"]) if pagina.get("fuente") else fila["pagina_motor"],
            "pagina_motor": fila["pagina_motor"],
            "fuente": pagina.get("fuente") or (origen or {}).get("fuente"),
            "centro_x": fila["centro_visual"]["x"],
            "centro_y": fila["centro_visual"]["y"],
            "x_pdf": fila["centro_visual"]["x"],
            "y_pdf": fila["centro_visual"]["y"],
            "posicion": dict(fila["centro_visual"]),
            "rectangulo_pdf": dict(origen["caja_visual"]) if origen else None,
            "origen_ubicacion": fila["origen_ubicacion"],
            "dimensiones_m": {
                "x": fila["x_m"],
                "y": fila["y_m"],
                "h": fila["h_m"],
            },
            "cantidad": 1,
        }
        ubicaciones.append(ubicacion)
        encofrados.append(
            {
                "identificador": fila["id"],
                "referencia": fila["referencia"],
                "cantidad": 1,
                "encofrado_unitario_m2": round(encofrado, 6),
                "encofrado_total_m2": round(encofrado, 6),
            }
        )

    excluidas = [item for item in revision["elementos"] if not item["incluir"]]
    alerta_acero = {
        "id": "fundaciones-acero-sin-fuente-distribuida",
        "severidad": "advertencia",
        "familia": "fundaciones",
        "categoria": "armadura_no_disponible",
        "titulo": "El acero de fundaciones permanece pendiente",
        "mensaje": (
            "Se validó la geometría de las zapatas, pero no existe una fuente tabular o un detalle asociado de armadura suficientemente inequívoco para calcular su peso."
        ),
        "accion_recomendada": "Revisar y asociar los detalles de armadura antes de aprobar el acero.",
        "bloqueante": False,
        "bloquea_resultado": False,
        "excluido_del_computo": True,
        "estado": "pendiente",
    }
    alertas = [alerta_acero]
    revisadas_manualmente = {
        fila["referencia"].upper() for fila in incluidas
        if fila["origen_ubicacion"] == "manual"
    }
    no_interpretadas = [
        referencia for referencia in propuesta.get("referencias_no_interpretadas", [])
        if referencia["texto"].upper() not in revisadas_manualmente
    ]
    if no_interpretadas:
        alertas.append({
            "id": "fundaciones-referencias-no-interpretadas",
            "severidad": "advertencia", "familia": "fundaciones",
            "categoria": "limite_lector_referencias",
            "titulo": "Hay rótulos que el lector no pudo incorporar",
            "mensaje": "Revisar " + ', '.join(sorted({r['texto'] for r in no_interpretadas}))
                + ". Las cantidades corresponden solo a las ocurrencias revisadas; no acreditan cobertura completa de la planta.",
            "accion_recomendada": "Revisar estos rótulos y computar por separado los elementos adicionales o no rectangulares.",
            "evidencia": no_interpretadas, "bloqueante": False,
            "bloquea_resultado": False, "excluido_del_computo": True, "estado": "pendiente",
        })
    return {
        "estado_resultado": "parcial_revisado",
        "computos_disponibles": True,
        "alcance_computo": {
            "calculado": ["hormigon_fundaciones", "encofrado_fundaciones"],
            "pendiente": [
                "acero_fundaciones",
                "pedestales",
                "vigas_riostra",
                "columnas",
            ],
            "motivo": "La fuente contiene geometría distribuida y fue validada por ocurrencia.",
        },
        "cantidad_fundaciones": len(incluidas),
        "cantidad_tipos": len(conteo),
        "cantidad_tipos_fundacion": len(conteo),
        "conteo_por_tipo": dict(sorted(conteo.items())),
        "referencias_fundaciones": sorted(conteo),
        "volumen_hormigon_m3": round(volumen_total, 6),
        "encofrado_zapatas_m2": round(encofrado_total, 6),
        "peso_acero_kg": None,
        "metros_acero": None,
        "barras_comerciales": None,
        "peso_compra_acero_kg": None,
        "fundaciones": fundaciones,
        "fundaciones_planta": ubicaciones,
        "ubicaciones_fundaciones": ubicaciones,
        "encofrado_zapatas_detalle": encofrados,
        "armaduras": [],
        "compra_acero_detalle": [],
        "pedestales_computo_detalle": [],
        "vigas_riostra_computo_detalle": [],
        "columnas_fundaciones": [],
        "columnas_vinculadas_por_viga": [],
        "validacion": {"faltantes": [], "sobrantes": [], "duplicadas": {}},
        "validacion_ubicaciones": {
            "cantidad_computada": len(incluidas),
            "cantidad_ubicada": len(ubicaciones),
            "resultado_completo": not no_interpretadas and not excluidas,
        },
        "validacion_pedestales": {
            "cantidad_pedestales_computados": 0,
            "resultado_completo": False,
            "advertencias": ["No se computaron pedestales en el flujo de geometría distribuida."],
        },
        "validacion_computo_vigas_riostra": {
            "tramos_computados": 0,
            "resultado_completo": False,
            "advertencias": ["No se computaron vigas de riostra en este flujo."],
        },
        "validacion_columnas": {
            "rotulos_columnas_detectados": 0,
            "altura_real_disponible": False,
            "advertencias": ["No se computaron columnas en este flujo."],
        },
        "computos_por_elemento": {
            "fundaciones": {
                "cantidad": len(incluidas),
                "estado": "parcial_sin_acero",
                "hormigon": {"valor": round(volumen_total, 6), "unidad": "m3", "estado": "calculado"},
                "acero": {"valor": None, "unidad": "kg", "estado": "pendiente_fuente"},
                "encofrado": {"valor": round(encofrado_total, 6), "unidad": "m2", "estado": "calculado"},
            }
        },
        "revision_geometria_aplicada": revision,
        "elementos_excluidos": excluidas,
        "referencias_no_interpretadas": no_interpretadas,
        "alertas_analisis": alertas,
        "resumen_alertas": {
            "total": len(alertas),
            "errores": 0,
            "advertencias": len(alertas),
            "informativas": 0,
            "excluidas_del_computo": len(alertas),
        },
        "confianza_lectura_porcentaje": 100,
    }


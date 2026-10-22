"""Extracción, revisión y cómputo auditable de cimientos corridos.

El motor combina tres fuentes independientes:

* texto nativo para localizar rótulos y tipos;
* OCR local para recuperar las cotas de las secciones y las cotas totales;
* geometría vectorial para medir la red de ejes de los cimientos.

Las cantidades siguen requiriendo confirmación profesional. Una propuesta de
longitud solo se emite cuando las mediciones horizontal y vertical pueden
calibrarse con cotas explícitas que concuerdan entre sí. Nunca se interpreta la
cantidad de rótulos como una longitud ni se confía ciegamente en la escala
impresa, porque un PDF puede haber sido reescalado al imprimirlo.
"""

from __future__ import annotations

import base64
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
import io
import math
from pathlib import Path
import re
import statistics
import subprocess
from tempfile import TemporaryDirectory
import unicodedata

import pymupdf

from computos.documentos.ocr import diagnostico_ocr, resolver_tesseract


PATRON_REFERENCIA = re.compile(r"^C\s*[-_.]?\s*(\d{1,3})$", re.I)
PATRON_REFERENCIA_REVISADA = re.compile(r"^C[-_]?[0-9]{1,3}$", re.I)
MATERIALES = {
    "mamposteria_piedra": "Mampostería de piedra",
    "hormigon_ciclopeo": "Hormigón ciclópeo",
    "hormigon_simple": "Hormigón simple",
    "hormigon_armado": "Hormigón armado",
    "otro": "Otro material",
}


@dataclass(frozen=True, slots=True)
class Rotulo:
    referencia: str
    pagina: int
    caja: pymupdf.Rect

    @property
    def centro_x(self) -> float:
        return (self.caja.x0 + self.caja.x1) / 2

    @property
    def centro_y(self) -> float:
        return (self.caja.y0 + self.caja.y1) / 2


def _normalizar_referencia(texto: str) -> str | None:
    coincidencia = PATRON_REFERENCIA.fullmatch(str(texto).strip())
    if not coincidencia:
        return None
    return f"C-{int(coincidencia.group(1))}"


def _normalizar_texto(texto: str) -> str:
    normal = "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", str(texto).upper())
        if not unicodedata.combining(caracter)
    )
    return re.sub(r"\s+", " ", normal).strip()


def _caja_diccionario(caja: pymupdf.Rect) -> dict:
    return {
        "x0": round(float(caja.x0), 3),
        "y0": round(float(caja.y0), 3),
        "x1": round(float(caja.x1), 3),
        "y1": round(float(caja.y1), 3),
    }


def _unir_cajas(cajas: list[pymupdf.Rect]) -> pymupdf.Rect:
    resultado = pymupdf.Rect(cajas[0])
    for caja in cajas[1:]:
        resultado.include_rect(caja)
    return resultado


def _lineas_palabras(pagina: pymupdf.Page) -> list[dict]:
    grupos: dict[tuple[int, int], list[tuple]] = {}
    for palabra in pagina.get_text("words", sort=False):
        grupos.setdefault((int(palabra[5]), int(palabra[6])), []).append(palabra)
    lineas = []
    for palabras in grupos.values():
        palabras.sort(key=lambda item: item[0])
        lineas.append(
            {
                "texto": " ".join(str(item[4]) for item in palabras),
                "caja": _unir_cajas(
                    [
                        pymupdf.Rect(item[0], item[1], item[2], item[3])
                        for item in palabras
                    ]
                ),
            }
        )
    return lineas


def _titulo_tipos_cimientos(pagina: pymupdf.Page) -> pymupdf.Rect | None:
    for linea in _lineas_palabras(pagina):
        texto = re.sub(r"\s+", " ", linea["texto"].upper()).strip()
        if re.search(r"\bTIPOS?\s+DE\s+CIMIENTOS?\b", texto):
            return linea["caja"]
    return None


def _rotulos_exactos(pagina: pymupdf.Page, numero: int) -> list[Rotulo]:
    resultado = []
    for palabra in pagina.get_text("words", sort=False):
        referencia = _normalizar_referencia(str(palabra[4]))
        if referencia:
            resultado.append(
                Rotulo(
                    referencia=referencia,
                    pagina=numero,
                    caja=pymupdf.Rect(
                        palabra[0], palabra[1], palabra[2], palabra[3]
                    ),
                )
            )
    return resultado


def _rotulos_del_detalle(
    pagina: pymupdf.Page,
    numero: int,
    titulo: pymupdf.Rect,
) -> list[Rotulo]:
    candidatos = [
        rotulo
        for rotulo in _rotulos_exactos(pagina, numero)
        if rotulo.caja.y0 >= titulo.y1
        and rotulo.caja.y0 <= titulo.y1 + max(180.0, pagina.rect.height * 0.13)
        and rotulo.caja.x1 >= titulo.x0 - 80.0
        and rotulo.caja.x0
        <= titulo.x0 + max(560.0, pagina.rect.width * 0.38)
    ]
    if not candidatos:
        return []
    bandas: dict[int, list[Rotulo]] = {}
    for rotulo in candidatos:
        bandas.setdefault(round(rotulo.caja.y0 / 12), []).append(rotulo)
    mejor = max(
        bandas.values(),
        key=lambda items: (len(items), -items[0].caja.y0),
    )
    unicos = {
        item.referencia: item
        for item in sorted(mejor, key=lambda item: item.caja.x0)
    }
    return list(unicos.values())


def _numero_ocr_seccion(texto: str) -> float | None:
    limpio = str(texto).upper().replace("O", "0").replace(",", ".")
    coincidencia = re.search(r"\d{1,2}\.\d{1,3}", limpio)
    if coincidencia:
        valor = float(coincidencia.group())
    else:
        digitos = re.sub(r"\D", "", limpio)
        if len(digitos) == 3 and digitos.startswith("0"):
            valor = int(digitos[1:]) / 100
        else:
            return None
    if not 0.05 <= valor <= 5.0:
        return None
    return round(valor, 4)


def _ejecutar_tesseract(
    ruta: Path,
    *,
    psm: int,
    formato: str = "tsv",
) -> str:
    comando = resolver_tesseract()
    if comando is None:
        raise FileNotFoundError("Tesseract no está disponible.")
    proceso = subprocess.run(
        [comando, str(ruta), "stdout", "-l", "eng", "--psm", str(psm), formato],
        check=True,
        capture_output=True,
        text=True,
        timeout=45,
    )
    return proceso.stdout


def _tokens_tesseract(ruta: Path) -> list[dict]:
    tokens = []
    for fila in csv.DictReader(
        io.StringIO(_ejecutar_tesseract(ruta, psm=11)), delimiter="\t"
    ):
        valor = _numero_ocr_seccion(fila.get("text", ""))
        if valor is None:
            continue
        try:
            confianza = float(fila.get("conf", "-1"))
            izquierda = int(fila["left"])
            arriba = int(fila["top"])
            ancho = int(fila["width"])
            alto = int(fila["height"])
        except (TypeError, ValueError, KeyError):
            continue
        if confianza < 20:
            continue
        tokens.append(
            {
                "valor": valor,
                "x": izquierda + ancho / 2,
                "y": arriba + alto / 2,
                "top": arriba,
                "confianza": confianza,
                "texto": fila.get("text", ""),
            }
        )
    return tokens


def _dimensiones_ocr(
    pagina: pymupdf.Page,
    detalle: pymupdf.Rect,
    rotulos: list[Rotulo],
) -> dict[str, dict]:
    if resolver_tesseract() is None or not rotulos:
        return {}
    escala = 400 / 72
    resultado = {rotulo.referencia: {} for rotulo in rotulos}
    try:
        with TemporaryDirectory(prefix="computoestia-cc-ocr-") as temporal:
            ruta_normal = Path(temporal) / "detalle.png"
            ruta_rotada = Path(temporal) / "detalle-90.png"
            pagina.get_pixmap(
                matrix=pymupdf.Matrix(escala, escala),
                clip=detalle,
                colorspace=pymupdf.csRGB,
                alpha=False,
            ).save(ruta_normal)
            pagina.get_pixmap(
                matrix=pymupdf.Matrix(escala, escala).prerotate(90),
                clip=detalle,
                colorspace=pymupdf.csRGB,
                alpha=False,
            ).save(ruta_rotada)
            horizontales = _tokens_tesseract(ruta_normal)
            verticales = _tokens_tesseract(ruta_rotada)
    except (OSError, subprocess.SubprocessError, ValueError):
        return {}

    ordenados = sorted(rotulos, key=lambda item: item.centro_x)
    centros = [item.centro_x for item in ordenados]
    for indice, rotulo in enumerate(ordenados):
        izquierda = (
            (centros[indice - 1] + rotulo.centro_x) / 2
            if indice
            else detalle.x0
        )
        derecha = (
            (rotulo.centro_x + centros[indice + 1]) / 2
            if indice + 1 < len(centros)
            else detalle.x1
        )
        valores = []
        for token in horizontales:
            x_pagina = detalle.x0 + token["x"] / escala
            if izquierda <= x_pagina <= derecha:
                valores.append(token)
        valores.sort(key=lambda item: item["y"])
        distintos = []
        for token in valores:
            if not any(
                math.isclose(
                    token["valor"], previo["valor"], abs_tol=0.002
                )
                and abs(token["y"] - previo["y"]) < 20
                for previo in distintos
            ):
                distintos.append(token)
        if len(distintos) >= 2:
            resultado[rotulo.referencia]["ancho_superior_m"] = distintos[0][
                "valor"
            ]
            resultado[rotulo.referencia]["ancho_base_m"] = distintos[-1][
                "valor"
            ]
        elif distintos:
            resultado[rotulo.referencia]["ancho_base_m"] = distintos[-1][
                "valor"
            ]

    alturas = sorted(verticales, key=lambda item: item["top"])
    if len(alturas) >= len(ordenados):
        for rotulo, token in zip(ordenados, alturas):
            resultado[rotulo.referencia]["altura_m"] = token["valor"]
    return resultado


def _dimensiones_textuales(pagina: pymupdf.Page) -> dict[str, dict]:
    resultado = {}
    for linea in _lineas_palabras(pagina):
        referencia = re.search(
            r"\bC\s*[-_.]?\s*(\d{1,3})\b", linea["texto"], re.I
        )
        if not referencia:
            continue
        numeros = [
            float(valor.replace(",", "."))
            for valor in re.findall(
                r"(?<!\d)(\d+[.,]\d+)(?!\d)", linea["texto"]
            )
        ]
        numeros = [valor for valor in numeros if 0.05 <= valor <= 5]
        if len(numeros) >= 3:
            resultado[f"C-{int(referencia.group(1))}"] = {
                "ancho_superior_m": round(numeros[0], 4),
                "ancho_base_m": round(numeros[1], 4),
                "altura_m": round(numeros[2], 4),
            }
    return resultado


def _detectar_material_textual(textos: list[str]) -> tuple[str, dict | None]:
    texto = _normalizar_texto("\n".join(textos))
    patrones = (
        (
            "mamposteria_piedra",
            r"\b(?:MAMPOSTERIA\s+DE\s+PIEDRA|CIMIENTO\s+DE\s+PIEDRA|PIEDRA\s+BRAZA)\b",
        ),
        (
            "hormigon_ciclopeo",
            r"\b(?:HORMIGON|CONCRETO)\s+CICLOPEO\b",
        ),
        (
            "hormigon_armado",
            r"\bCIMIENT(?:O|OS)\s+CORRID(?:O|OS|A|AS).{0,80}\b(?:HORMIGON|CONCRETO)\s+ARMADO\b",
        ),
        (
            "hormigon_simple",
            r"\bCIMIENT(?:O|OS)\s+CORRID(?:O|OS|A|AS).{0,80}\b(?:HORMIGON|CONCRETO)\s+SIMPLE\b",
        ),
    )
    for material, patron in patrones:
        coincidencia = re.search(patron, texto)
        if coincidencia:
            return material, {
                "metodo": "texto_explicito",
                "evidencia": coincidencia.group(0)[:160],
                "confianza": 0.99,
            }
    return "", None


def _distancia_punto_tramo(
    x: float,
    y: float,
    inicio: tuple[float, float],
    fin: tuple[float, float],
) -> float:
    vx = fin[0] - inicio[0]
    vy = fin[1] - inicio[1]
    denominador = vx * vx + vy * vy
    if denominador <= 1e-9:
        return math.hypot(x - inicio[0], y - inicio[1])
    factor = max(
        0.0,
        min(
            1.0,
            ((x - inicio[0]) * vx + (y - inicio[1]) * vy) / denominador,
        ),
    )
    px = inicio[0] + factor * vx
    py = inicio[1] + factor * vy
    return math.hypot(x - px, y - py)


def _region_busqueda(pagina: pymupdf.Page, rotulos: list[Rotulo]) -> pymupdf.Rect:
    centros_x = [rotulo.centro_x for rotulo in rotulos]
    centros_y = [rotulo.centro_y for rotulo in rotulos]
    extension_x = max(centros_x) - min(centros_x) if len(centros_x) > 1 else 0
    extension_y = max(centros_y) - min(centros_y) if len(centros_y) > 1 else 0
    # Cuando existen suficientes rótulos, su envolvente describe mucho mejor
    # la planta que una fracción fija de toda la lámina. Un margen demasiado
    # grande incorpora las líneas discontinuas de las cotas como si fueran
    # ejes de cimentación y falsea tanto la red como su calibración.
    if len(rotulos) >= 3:
        margen_x = max(24.0, pagina.rect.width * 0.014, extension_x * 0.07)
        margen_y = max(24.0, pagina.rect.height * 0.014, extension_y * 0.07)
    else:
        margen_x = max(60.0, pagina.rect.width * 0.16, extension_x * 0.20)
        margen_y = max(60.0, pagina.rect.height * 0.16, extension_y * 0.20)
    return pymupdf.Rect(
        min(centros_x) - margen_x,
        min(centros_y) - margen_y,
        max(centros_x) + margen_x,
        max(centros_y) + margen_y,
    ) & pagina.rect


def _segmento_intersecta_region(
    inicio: pymupdf.Point,
    fin: pymupdf.Point,
    region: pymupdf.Rect,
) -> bool:
    caja = pymupdf.Rect(
        min(inicio.x, fin.x),
        min(inicio.y, fin.y),
        max(inicio.x, fin.x),
        max(inicio.y, fin.y),
    )
    if caja.is_empty:
        return region.contains(inicio)
    return caja.intersects(region)


def _estilo_eje_vectorial(
    pagina: pymupdf.Page,
    region: pymupdf.Rect,
) -> tuple[float, float] | None:
    por_ancho: dict[float, dict] = defaultdict(
        lambda: {"pequenos": 0, "longitudes": Counter()}
    )
    for dibujo in pagina.get_drawings():
        ancho = dibujo.get("width")
        if ancho is None:
            continue
        clave = round(float(ancho), 2)
        for item in dibujo["items"]:
            if item[0] != "l":
                continue
            inicio, fin = item[1], item[2]
            if not _segmento_intersecta_region(inicio, fin, region):
                continue
            longitud = math.hypot(fin.x - inicio.x, fin.y - inicio.y)
            if longitud <= 0.5:
                por_ancho[clave]["pequenos"] += 1
            elif 1.0 <= longitud <= 30.0:
                por_ancho[clave]["longitudes"][round(longitud, 1)] += 1

    candidatos = []
    for ancho, datos in por_ancho.items():
        if datos["pequenos"] < 4 or not datos["longitudes"]:
            continue
        longitud, repeticiones = max(
            (
                (longitud, cantidad)
                for longitud, cantidad in datos["longitudes"].items()
                if longitud >= 2.0
            ),
            key=lambda item: item[1],
            default=(0.0, 0),
        )
        if repeticiones < 4:
            continue
        puntuacion = repeticiones * 2 + min(datos["pequenos"], repeticiones)
        candidatos.append((puntuacion, ancho, longitud))
    if not candidatos:
        return None
    _, ancho, longitud = max(candidatos)
    return ancho, longitud


def _agrupar_ordenados(
    elementos: list,
    valor,
    tolerancia: float,
) -> list[list]:
    grupos: list[list] = []
    for elemento in sorted(elementos, key=valor):
        if not grupos or valor(elemento) - max(map(valor, grupos[-1])) > tolerancia:
            grupos.append([elemento])
        else:
            grupos[-1].append(elemento)
    return grupos


def _tramos_vectoriales(
    pagina: pymupdf.Page,
    rotulos: list[Rotulo],
) -> tuple[list[dict], dict]:
    if len(rotulos) < 2:
        return [], {"estado": "sin_red", "motivo": "Hay menos de dos rótulos en la planta."}
    region = _region_busqueda(pagina, rotulos)
    estilo = _estilo_eje_vectorial(pagina, region)
    if estilo is None:
        return [], {
            "estado": "sin_red",
            "motivo": "No se identificó un patrón vectorial discontinuo de ejes.",
        }
    ancho_objetivo, paso_guion = estilo
    candidatos = []
    for indice_dibujo, dibujo in enumerate(pagina.get_drawings()):
        ancho = dibujo.get("width")
        if ancho is None or abs(float(ancho) - ancho_objetivo) > max(0.03, ancho_objetivo * 0.08):
            continue
        for item in dibujo["items"]:
            if item[0] != "l":
                continue
            inicio, fin = item[1], item[2]
            if not _segmento_intersecta_region(inicio, fin, region):
                continue
            longitud = math.hypot(fin.x - inicio.x, fin.y - inicio.y)
            if not paso_guion * 0.50 <= longitud <= paso_guion * 1.55:
                continue
            candidatos.append(
                {
                    "angulo": math.degrees(
                        math.atan2(fin.y - inicio.y, fin.x - inicio.x)
                    )
                    % 180,
                    "inicio": inicio,
                    "fin": fin,
                    "dibujo": indice_dibujo,
                }
            )
    if len(candidatos) < 4:
        return [], {
            "estado": "sin_red",
            "motivo": "El patrón de ejes no tuvo continuidad suficiente.",
        }

    grupos_angulares = _agrupar_ordenados(
        candidatos,
        lambda item: item["angulo"],
        2.2,
    )
    tramos = []
    tolerancia_rotulo = max(
        paso_guion * 12,
        min(pagina.rect.width, pagina.rect.height) * 0.04,
    )
    for grupo_angular in grupos_angulares:
        if len(grupo_angular) < 2:
            continue
        angulo = statistics.median(item["angulo"] for item in grupo_angular)
        radianes = math.radians(angulo)
        coseno = math.cos(radianes)
        seno = math.sin(radianes)
        for item in grupo_angular:
            medio_x = (item["inicio"].x + item["fin"].x) / 2
            medio_y = (item["inicio"].y + item["fin"].y) / 2
            item["rho"] = -seno * medio_x + coseno * medio_y
        grupos_soporte = _agrupar_ordenados(
            grupo_angular,
            lambda item: item["rho"],
            max(1.5, paso_guion * 0.32),
        )
        for grupo_soporte in grupos_soporte:
            if len(grupo_soporte) < 2:
                continue
            rho = statistics.median(item["rho"] for item in grupo_soporte)
            intervalos = []
            for item in grupo_soporte:
                proyecciones = (
                    coseno * item["inicio"].x + seno * item["inicio"].y,
                    coseno * item["fin"].x + seno * item["fin"].y,
                )
                intervalos.append(
                    {
                        "inicio": min(proyecciones),
                        "fin": max(proyecciones),
                        "dibujo": item["dibujo"],
                    }
                )
            # Reunimos los guiones por la distancia real entre el final
            # acumulado y el comienzo del siguiente.
            corridas_reales = []
            for intervalo in sorted(intervalos, key=lambda item: item["inicio"]):
                if (
                    not corridas_reales
                    or intervalo["inicio"]
                    - max(item["fin"] for item in corridas_reales[-1])
                    > paso_guion * 2.7
                ):
                    corridas_reales.append([intervalo])
                else:
                    corridas_reales[-1].append(intervalo)
            for corrida in corridas_reales:
                if len(corrida) < 2:
                    continue
                inicio_t = min(item["inicio"] for item in corrida)
                fin_t = max(item["fin"] for item in corrida)
                longitud = fin_t - inicio_t
                if longitud < paso_guion * 2:
                    continue
                inicio = (
                    coseno * inicio_t - seno * rho,
                    seno * inicio_t + coseno * rho,
                )
                fin = (
                    coseno * fin_t - seno * rho,
                    seno * fin_t + coseno * rho,
                )
                cercanos = sorted(
                    (
                        _distancia_punto_tramo(
                            rotulo.centro_x,
                            rotulo.centro_y,
                            inicio,
                            fin,
                        ),
                        rotulo,
                    )
                    for rotulo in rotulos
                )
                distancia, rotulo = cercanos[0]
                if distancia > tolerancia_rotulo:
                    continue
                tramos.append(
                    {
                        "referencia": rotulo.referencia,
                        "longitud_pt": longitud,
                        "inicio": inicio,
                        "fin": fin,
                        "distancia_rotulo_pt": distancia,
                        "cantidad_guiones": len(corrida),
                    }
                )

    return tramos, {
        "estado": "red_detectada" if tramos else "sin_red",
        "ancho_trazo_pt": round(ancho_objetivo, 4),
        "paso_guion_pt": round(paso_guion, 4),
        "cantidad_tramos": len(tramos),
        "region": _caja_diccionario(region),
    }


def _numero_cota(texto: str) -> float | None:
    limpio = str(texto).strip().replace("O", "0").replace("o", "0")
    coincidencia = re.fullmatch(r"[^0-9]*([0-9]{1,3}(?:[.,][0-9]{1,3})?)[^0-9]*", limpio)
    if not coincidencia:
        return None
    try:
        valor = float(coincidencia.group(1).replace(",", "."))
    except ValueError:
        return None
    return valor if 0.5 <= valor <= 500 else None


def _numeros_ocr_clip(
    pagina: pymupdf.Page,
    clip: pymupdf.Rect,
    *,
    rotacion: int,
) -> list[float]:
    if resolver_tesseract() is None or clip.is_empty:
        return []
    escala = 400 / 72
    valores = []
    try:
        with TemporaryDirectory(prefix="computoestia-cotas-") as temporal:
            ruta = Path(temporal) / "cotas.png"
            pagina.get_pixmap(
                matrix=pymupdf.Matrix(escala, escala).prerotate(rotacion),
                clip=clip,
                colorspace=pymupdf.csRGB,
                alpha=False,
            ).save(ruta)
            for psm in (6, 11):
                salida = _ejecutar_tesseract(ruta, psm=psm)
                for fila in csv.DictReader(io.StringIO(salida), delimiter="\t"):
                    valor = _numero_cota(fila.get("text", ""))
                    if valor is not None:
                        valores.append(valor)
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    return sorted(set(round(valor, 4) for valor in valores))


def _calibrar_por_cotas(
    pagina: pymupdf.Page,
    tramos: list[dict],
) -> dict:
    if not tramos:
        return {"estado": "sin_calibracion", "motivo": "No existe una red vectorial medible."}
    x0 = min(min(item["inicio"][0], item["fin"][0]) for item in tramos)
    y0 = min(min(item["inicio"][1], item["fin"][1]) for item in tramos)
    x1 = max(max(item["inicio"][0], item["fin"][0]) for item in tramos)
    y1 = max(max(item["inicio"][1], item["fin"][1]) for item in tramos)
    ancho_pt = x1 - x0
    alto_pt = y1 - y0
    if ancho_pt <= 0 or alto_pt <= 0:
        return {"estado": "sin_calibracion", "motivo": "La extensión de la red es inválida."}

    margen_vertical = max(85.0, pagina.rect.height * 0.045)
    margen_horizontal = max(85.0, pagina.rect.width * 0.055)
    clips_horizontales = (
        pymupdf.Rect(x0 - 15, y0 - margen_vertical, x1 + 15, y0 - 1),
        pymupdf.Rect(x0 - 15, y1 + 1, x1 + 15, y1 + margen_vertical),
    )
    clips_verticales = (
        pymupdf.Rect(x0 - margen_horizontal, y0 - 15, x0 - 1, y1 + 15),
        pymupdf.Rect(x1 + 1, y0 - 15, x1 + margen_horizontal, y1 + 15),
    )
    valores_h = []
    valores_v = []
    for clip in clips_horizontales:
        valores_h.extend(
            _numeros_ocr_clip(pagina, clip & pagina.rect, rotacion=0)
        )
    for clip in clips_verticales:
        valores_v.extend(
            _numeros_ocr_clip(pagina, clip & pagina.rect, rotacion=90)
        )

    candidatos_h = [
        (ancho_pt / valor, valor)
        for valor in sorted(set(valores_h))
        if 5 <= ancho_pt / valor <= 250
    ]
    candidatos_v = [
        (alto_pt / valor, valor)
        for valor in sorted(set(valores_v))
        if 5 <= alto_pt / valor <= 250
    ]
    pares = []
    for escala_h, valor_h in candidatos_h:
        for escala_v, valor_v in candidatos_v:
            promedio = (escala_h + escala_v) / 2
            diferencia = abs(escala_h - escala_v) / promedio
            pares.append(
                (diferencia, -(valor_h + valor_v), escala_h, valor_h, escala_v, valor_v)
            )
    if not pares:
        return {
            "estado": "sin_calibracion",
            "motivo": "No se recuperaron cotas totales ortogonales para calibrar la medición.",
            "cotas_horizontales_ocr": sorted(set(valores_h)),
            "cotas_verticales_ocr": sorted(set(valores_v)),
        }
    mejor = min(pares)
    diferencia, _, escala_h, valor_h, escala_v, valor_v = mejor
    if diferencia > 0.06:
        return {
            "estado": "calibracion_inconsistente",
            "motivo": "Las escalas deducidas de las cotas horizontal y vertical no coinciden.",
            "cota_horizontal_m": valor_h,
            "cota_vertical_m": valor_v,
            "diferencia_relativa": round(diferencia, 6),
        }
    puntos_por_metro = (escala_h + escala_v) / 2
    return {
        "estado": "calibrado",
        "metodo": "cotas_totales_ocr_mas_red_vectorial",
        "cota_horizontal_m": valor_h,
        "cota_vertical_m": valor_v,
        "extension_horizontal_pt": round(ancho_pt, 4),
        "extension_vertical_pt": round(alto_pt, 4),
        "puntos_por_metro": round(puntos_por_metro, 8),
        "diferencia_relativa": round(diferencia, 6),
        "confianza": round(max(0.86, 0.99 - diferencia * 2), 3),
    }


def _medir_longitudes(
    ruta: Path,
    apariciones: dict[str, list[Rotulo]],
) -> tuple[dict[str, float], dict]:
    por_pagina: dict[int, list[Rotulo]] = defaultdict(list)
    for rotulos in apariciones.values():
        for rotulo in rotulos:
            por_pagina[rotulo.pagina].append(rotulo)
    longitudes_pt = Counter()
    recorridos = []
    diagnosticos = []
    with pymupdf.open(ruta) as documento:
        for numero, rotulos in sorted(por_pagina.items()):
            if not 1 <= numero <= len(documento):
                continue
            pagina = documento[numero - 1]
            tramos, red = _tramos_vectoriales(pagina, rotulos)
            calibracion = _calibrar_por_cotas(pagina, tramos)
            diagnostico = {
                "pagina_motor": numero,
                "red_vectorial": red,
                "calibracion": calibracion,
            }
            if calibracion.get("estado") == "calibrado":
                escala = calibracion["puntos_por_metro"]
                for indice, tramo in enumerate(tramos, start=1):
                    longitud_m = tramo["longitud_pt"] / escala
                    longitudes_pt[tramo["referencia"]] += longitud_m
                    recorridos.append({
                        "id": f"tramo-p{numero}-{indice}",
                        "referencia": tramo["referencia"],
                        "pagina_motor": numero,
                        "inicio": {"x": round(tramo["inicio"][0], 3), "y": round(tramo["inicio"][1], 3)},
                        "fin": {"x": round(tramo["fin"][0], 3), "y": round(tramo["fin"][1], 3)},
                        "longitud_m": round(longitud_m, 5),
                        "puntos_por_metro": escala,
                    })
                diagnostico["tramos_por_referencia"] = dict(
                    Counter(tramo["referencia"] for tramo in tramos)
                )
            diagnosticos.append(diagnostico)
    longitudes = {
        referencia: round(longitud, 2)
        for referencia, longitud in longitudes_pt.items()
        if longitud > 0
    }
    paginas_calibradas = sum(
        item["calibracion"].get("estado") == "calibrado"
        for item in diagnosticos
    )
    return longitudes, {
        "estado": "medido" if longitudes else "pendiente",
        "metodo": "ejes_vectoriales_calibrados_por_cotas_ocr",
        "paginas_calibradas": paginas_calibradas,
        "paginas_analizadas": len(diagnosticos),
        "paginas": diagnosticos,
        "tramos_candidatos": recorridos,
    }


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
            paginas.append(
                {
                    "pagina_motor": numero,
                    "ancho_visual_pt": round(ancho, 3),
                    "alto_visual_pt": round(alto, 3),
                    "imagen": "data:image/jpeg;base64,"
                    + base64.b64encode(
                        pixmap.tobytes("jpeg", jpg_quality=62)
                    ).decode("ascii"),
                }
            )
    return paginas


def preparar_revision_cimientos_corridos(
    ruta_planta: str | Path,
    ruta_detalles: str | Path,
    *,
    fuentes_planta: list[dict],
    identidad_fuentes: dict,
    fuentes_detalles: list[dict] | None = None,
) -> dict:
    """Propone secciones y longitudes con evidencia, sin inventar datos."""

    ruta_planta = Path(ruta_planta)
    ruta_detalles = Path(ruta_detalles)
    secciones: dict[str, dict] = {}
    cajas_detalle: dict[tuple[int, str], pymupdf.Rect] = {}
    textos = []
    with pymupdf.open(ruta_detalles) as documento:
        for numero, pagina in enumerate(documento, start=1):
            textos.append(pagina.get_text("text"))
            titulo = _titulo_tipos_cimientos(pagina)
            if titulo is None:
                continue
            rotulos = _rotulos_del_detalle(pagina, numero, titulo)
            if not rotulos:
                continue
            detalle = pymupdf.Rect(
                min(titulo.x0, min(item.caja.x0 for item in rotulos)) - 50,
                titulo.y0 - 25,
                max(item.caja.x1 for item in rotulos) + 50,
                max(item.caja.y1 for item in rotulos) + 25,
            ) & pagina.rect
            detectadas = _dimensiones_textuales(pagina)
            for referencia, valores in _dimensiones_ocr(
                pagina, detalle, rotulos
            ).items():
                detectadas.setdefault(referencia, {}).update(
                    {
                        clave: valor
                        for clave, valor in valores.items()
                        if valor is not None
                    }
                )
            for rotulo in rotulos:
                secciones.setdefault(rotulo.referencia, {}).update(
                    detectadas.get(rotulo.referencia, {})
                )
                cajas_detalle[(numero, rotulo.referencia)] = rotulo.caja

    apariciones: dict[str, list[Rotulo]] = {}
    with pymupdf.open(ruta_planta) as documento:
        for numero, pagina in enumerate(documento, start=1):
            if ruta_planta != ruta_detalles:
                textos.append(pagina.get_text("text"))
            titulo = _titulo_tipos_cimientos(pagina)
            rotulos_detalle = (
                _rotulos_del_detalle(pagina, numero, titulo) if titulo else []
            )
            cajas_excluidas = [item.caja for item in rotulos_detalle]
            for rotulo in _rotulos_exactos(pagina, numero):
                if any(
                    rotulo.caja.intersects(caja)
                    or (
                        abs(rotulo.caja.y0 - caja.y0) < 8
                        and abs(rotulo.caja.x0 - caja.x0) < 80
                    )
                    for caja in cajas_excluidas
                ):
                    continue
                apariciones.setdefault(rotulo.referencia, []).append(rotulo)

    referencias_usadas = sorted(
        set(apariciones) | set(secciones),
        key=lambda referencia: int(re.sub(r"\D", "", referencia)),
    )
    if not referencias_usadas:
        raise ValueError(
            "Se reconocieron cimientos corridos, pero no se localizaron tipos C-n para revisar."
        )

    longitudes, diagnostico_medicion = _medir_longitudes(
        ruta_planta, apariciones
    )
    material_propuesto, evidencia_material = _detectar_material_textual(textos)
    estado_ocr = diagnostico_ocr()
    elementos = []
    recorridos = diagnostico_medicion.get("tramos_candidatos", [])
    for referencia in referencias_usadas:
        ocurrencias = apariciones.get(referencia, [])
        origen = ocurrencias[0] if ocurrencias else None
        detalle = next(
            ((numero, caja) for (numero, ref), caja in cajas_detalle.items()
             if ref == referencia), None,
        )
        pagina_motor = origen.pagina if origen else (detalle[0] if detalle else 1)
        fuentes = fuentes_planta if origen else (fuentes_detalles or fuentes_planta)
        fuente = fuentes[pagina_motor - 1] if pagina_motor - 1 < len(fuentes) else fuentes[0]
        dimensiones = secciones.get(referencia, {})
        caja = origen.caja if origen else (detalle[1] if detalle else None)
        longitud = longitudes.get(referencia)
        elementos.append(
            {
                "id": f"cimiento-corrido-{referencia}",
                "referencia_propuesta": referencia,
                "apariciones_rotulo": len(ocurrencias),
                "origen_referencia": "planta" if origen else "solo_detalle",
                "motivo_exclusion_propuesto": (
                    "Tipo presente en el detalle: sus cotas son de sección y no se localizó un recorrido longitudinal en las plantas seleccionadas."
                    if not origen else None
                ),
                "pagina_motor": pagina_motor,
                "fuente": {
                    "archivo": fuente.get("archivo"),
                    "sha256": fuente.get("sha256"),
                    "pagina": fuente.get("pagina"),
                },
                "caja_visual": _caja_diccionario(caja) if caja else None,
                "ancho_superior_m_propuesto": dimensiones.get(
                    "ancho_superior_m"
                ),
                "ancho_base_m_propuesto": dimensiones.get("ancho_base_m"),
                "altura_m_propuesta": dimensiones.get("altura_m"),
                "longitud_m_propuesta": longitud,
                "material_propuesto": material_propuesto,
                "evidencia_seccion": {
                    "metodo": "texto_o_ocr_del_detalle",
                    "completa": all(
                        dimensiones.get(campo) is not None
                        for campo in (
                            "ancho_superior_m",
                            "ancho_base_m",
                            "altura_m",
                        )
                    ),
                },
                "evidencia_longitud": (
                    {
                        "metodo": "red_vectorial_calibrada_por_cotas_ocr",
                        "valor_m": longitud,
                        "caracter": "propuesta_revisable",
                    }
                    if longitud is not None
                    else None
                ),
                "tramos_propuestos": [
                    {**tramo, "fuente": {
                        clave: fuentes_planta[tramo["pagina_motor"] - 1].get(clave)
                        for clave in ("archivo", "sha256", "pagina")
                    }}
                    for tramo in recorridos if tramo["referencia"] == referencia
                    and tramo["pagina_motor"] <= len(fuentes_planta)
                ],
                "evidencia_material": evidencia_material,
                "requiere_revision": True,
            }
        )

    return {
        "version": 4,
        "tipo": "cimientos_corridos_geometria_distribuida",
        "identidad_fuentes": identidad_fuentes["sha256"],
        "fuentes": identidad_fuentes["fuentes"],
        "cantidad_elementos": len(elementos),
        "cantidad_referencias": len(elementos),
        "tipos_solo_detalle": [
            {"referencia": item["referencia_propuesta"], "fuente": item["fuente"],
             "motivo": item["motivo_exclusion_propuesto"]}
            for item in elementos if item["origen_referencia"] == "solo_detalle"
        ],
        "elementos": elementos,
        "paginas": [
            {**pagina, "fuente": {
                clave: fuentes_planta[pagina["pagina_motor"] - 1].get(clave)
                for clave in ("archivo", "sha256", "pagina")
            }} if pagina["pagina_motor"] <= len(fuentes_planta) else pagina
            for pagina in _paginas_vista_previa(ruta_planta)
        ],
        "materiales_permitidos": [
            {"id": identificador, "nombre": nombre}
            for identificador, nombre in MATERIALES.items()
        ],
        "diagnostico_ocr": estado_ocr,
        "diagnostico_medicion": diagnostico_medicion,
        "alcance": (
            "Los anchos y la altura de sección se proponen desde el detalle; "
            "sus cotas no representan la longitud construida. Las longitudes vienen de "
            "ejes vectoriales calibrados por cotas ortogonales. El profesional "
            "debe confirmarlas; los rótulos nunca se convierten en metros."
        ),
    }


def validar_revision_cimientos_corridos(decision: dict, propuesta: dict) -> dict:
    if not isinstance(decision, dict):
        raise ValueError("La revisión de cimientos corridos debe ser un objeto JSON.")
    if decision.get("identidad_fuentes") != propuesta.get("identidad_fuentes"):
        raise ValueError("La revisión pertenece a otra combinación de archivos o páginas.")
    if decision.get("version") != propuesta.get("version"):
        raise ValueError(
            "La revisión guardada pertenece a una versión anterior. Revisá las nuevas propuestas antes de calcular."
        )
    for campo, minimo, maximo in (("revisor", 2, 160), ("motivo", 10, 1000)):
        valor = decision.get(campo)
        if not isinstance(valor, str) or not minimo <= len(valor.strip()) <= maximo:
            raise ValueError(f"{campo}: longitud inválida en la revisión de cimientos corridos.")
    filas = decision.get("elementos")
    propuestas = {item["id"]: item for item in propuesta["elementos"]}
    if (
        not isinstance(filas, list)
        or {item.get("id") for item in filas if isinstance(item, dict)}
        != set(propuestas)
        or len(filas) != len(propuestas)
    ):
        raise ValueError("Deben revisarse exactamente todos los tipos de cimiento propuestos.")

    normalizadas = []
    paginas = {pagina["pagina_motor"]: pagina for pagina in propuesta.get("paginas", [])}
    escalas = {
        item["pagina_motor"]: item["calibracion"].get("puntos_por_metro")
        for item in propuesta.get("diagnostico_medicion", {}).get("paginas", [])
        if item.get("calibracion", {}).get("estado") == "calibrado"
    }
    for fila in filas:
        incluir = fila.get("incluir") is True
        original = propuestas[fila["id"]]
        referencia = str(fila.get("referencia", "")).upper().replace("_", "-").strip()
        if not PATRON_REFERENCIA_REVISADA.fullmatch(referencia):
            raise ValueError(f"Referencia inválida en {fila.get('id')}.")
        referencia = _normalizar_referencia(referencia) or referencia
        if incluir:
            valores = {}
            for campo, limite in (
                ("ancho_superior_m", 10),
                ("ancho_base_m", 10),
                ("altura_m", 10),
                ("longitud_m", 10000),
            ):
                try:
                    valor = float(str(fila.get(campo, "")).replace(",", "."))
                except (TypeError, ValueError) as error:
                    raise ValueError(f"{campo} es obligatorio en {fila['id']}.") from error
                if not 0 < valor <= limite:
                    raise ValueError(f"{campo} está fuera de rango en {fila['id']}.")
                valores[campo] = round(valor, 4)
            if valores["ancho_base_m"] < valores["ancho_superior_m"]:
                raise ValueError(
                    f"El ancho de base no puede ser menor que el superior en {fila['id']}."
                )
            material_bruto = str(fila.get("material") or "").strip()
            if material_bruto and material_bruto not in MATERIALES:
                raise ValueError(f"Seleccioná un material válido en {fila['id']}.")
            material = material_bruto or None
            motivo_exclusion = None
            motivo_inclusion = str(fila.get("motivo_inclusion") or "").strip()
            if original.get("origen_referencia") == "solo_detalle" and not 10 <= len(motivo_inclusion) <= 1000:
                raise ValueError(
                    f"Documentá dónde verificaste el recorrido de {fila['id']} antes de incluirlo."
                )
            elegidos = fila.get("tramos", [])
            if not isinstance(elegidos, list) or len(elegidos) > 2000:
                raise ValueError(f"La lista de tramos de {fila['id']} es inválida.")
            candidatos = {tramo["id"]: tramo for tramo in original.get("tramos_propuestos", [])}
            ids = set()
            tramos = []
            for elegido in elegidos:
                if not isinstance(elegido, dict) or not isinstance(elegido.get("id"), str):
                    raise ValueError(f"Tramo inválido en {fila['id']}.")
                identificador = elegido["id"]
                if identificador in ids:
                    raise ValueError(f"Tramo duplicado en {fila['id']}.")
                ids.add(identificador)
                if identificador in candidatos:
                    tramo = {**candidatos[identificador], "origen_trazo": "propuesta_confirmada"}
                else:
                    if not re.fullmatch(r"manual-[0-9a-f-]{36}", identificador):
                        raise ValueError(f"Tramo desconocido en {fila['id']}.")
                    try:
                        numero = int(elegido["pagina_motor"])
                        pagina = paginas[numero]
                        escala = float(escalas[numero])
                        inicio = {eje: round(float(elegido["inicio"][eje]), 3) for eje in ("x", "y")}
                        fin = {eje: round(float(elegido["fin"][eje]), 3) for eje in ("x", "y")}
                    except (KeyError, TypeError, ValueError, ZeroDivisionError):
                        raise ValueError(f"El tramo manual de {fila['id']} necesita una página calibrada y dos extremos.") from None
                    if (not math.isfinite(escala) or escala <= 0 or
                            not all(math.isfinite(valor) for punto in (inicio, fin) for valor in punto.values()) or
                            any(not 0 <= punto["x"] <= pagina["ancho_visual_pt"] or
                                not 0 <= punto["y"] <= pagina["alto_visual_pt"] for punto in (inicio, fin))):
                        raise ValueError(f"El tramo manual de {fila['id']} queda fuera de la planta.")
                    longitud = math.dist((inicio["x"], inicio["y"]), (fin["x"], fin["y"])) / escala
                    if not 0.05 <= longitud <= 10000:
                        raise ValueError(f"La longitud del tramo manual de {fila['id']} es inválida.")
                    tramo = {
                        "id": identificador, "pagina_motor": numero,
                        "inicio": inicio, "fin": fin,
                        "longitud_m": round(longitud, 5),
                        "puntos_por_metro": escala,
                        "fuente": pagina.get("fuente"),
                        "origen_trazo": "manual_calibrado",
                    }
                tramos.append({**tramo, "referencia": referencia, "tipo_id": fila["id"]})
            if tramos:
                suma = sum(tramo["longitud_m"] for tramo in tramos)
                if abs(suma - valores["longitud_m"]) > max(0.03, suma * 0.005):
                    raise ValueError(
                        f"La longitud de {fila['id']} no coincide con los tramos seleccionados. "
                        "Corregí el recorrido o quitá los tramos para indicar una longitud manual sin modelo 3D."
                    )
                valores["longitud_m"] = round(suma, 4)
        else:
            motivo_exclusion = str(fila.get("motivo_exclusion", "")).strip()
            if not 10 <= len(motivo_exclusion) <= 1000:
                raise ValueError(
                    f"Explicá la exclusión de {fila['id']} con al menos 10 caracteres."
                )
            valores = {
                "ancho_superior_m": None,
                "ancho_base_m": None,
                "altura_m": None,
                "longitud_m": None,
            }
            material = None
            motivo_inclusion = None
            tramos = []
        normalizadas.append(
            {
                "id": fila["id"],
                "incluir": incluir,
                "referencia": referencia,
                **valores,
                "material": material,
                "motivo_exclusion": motivo_exclusion,
                "motivo_inclusion": motivo_inclusion or None,
                "tramos": tramos,
            }
        )
    return {
        "version": propuesta["version"],
        "tipo": "cimientos_corridos_geometria_distribuida",
        "identidad_fuentes": propuesta["identidad_fuentes"],
        "revisor": decision["revisor"].strip(),
        "motivo": decision["motivo"].strip(),
        "elementos": normalizadas,
    }


def calcular_cimientos_corridos_revisados(propuesta: dict, decision: dict) -> dict:
    revision = validar_revision_cimientos_corridos(decision, propuesta)
    incluidas = [item for item in revision["elementos"] if item["incluir"]]
    if not incluidas:
        raise ValueError("La revisión excluyó todos los cimientos corridos.")

    detalle = []
    recorridos_confirmados = []
    totales_material = Counter()
    longitud_total = 0.0
    volumen_total = 0.0
    for fila in incluidas:
        recorridos_confirmados.extend({
            **tramo,
            "ancho_superior_m": fila["ancho_superior_m"],
            "ancho_base_m": fila["ancho_base_m"],
            "altura_m": fila["altura_m"],
        } for tramo in fila["tramos"])
        area = (
            (fila["ancho_superior_m"] + fila["ancho_base_m"])
            / 2
            * fila["altura_m"]
        )
        volumen = area * fila["longitud_m"]
        longitud_total += fila["longitud_m"]
        volumen_total += volumen
        if fila["material"]:
            totales_material[fila["material"]] += volumen
        detalle.append(
            {
                "identificador": fila["id"],
                "referencia": fila["referencia"],
                "material": fila["material"],
                "material_nombre": MATERIALES.get(
                    fila["material"], "Material no confirmado"
                ),
                "longitud_m": fila["longitud_m"],
                "ancho_superior_m": fila["ancho_superior_m"],
                "ancho_base_m": fila["ancho_base_m"],
                "altura_m": fila["altura_m"],
                "area_seccion_m2": round(area, 6),
                "volumen_total_m3": round(volumen, 6),
                "volumen_total": round(volumen, 6),
                "origen": "revision_profesional_cimientos_corridos",
                "motivo_inclusion": fila["motivo_inclusion"],
                "cantidad_tramos_confirmados": len(fila["tramos"]),
            }
        )

    volumen_hormigon = sum(
        totales_material[material]
        for material in (
            "hormigon_simple",
            "hormigon_armado",
            "hormigon_ciclopeo",
        )
    )
    volumen_mamposteria = totales_material["mamposteria_piedra"]
    alertas = []
    if any(item["material"] is None for item in incluidas):
        alertas.append(
            {
                "id": "cimientos-corridos-material-pendiente",
                "severidad": "advertencia",
                "familia": "fundaciones",
                "categoria": "material_no_confirmado",
                "titulo": "El volumen geométrico fue calculado sin clasificar el material",
                "mensaje": "La lámina no nombra inequívocamente el material de todos los tipos incluidos.",
                "accion_recomendada": "Confirmar el material para obtener subtotales por material.",
                "bloqueante": False,
                "bloquea_resultado": False,
                "excluido_del_computo": False,
                "estado": "pendiente",
            }
        )
    if any(item["material"] == "hormigon_armado" for item in incluidas):
        alertas.append(
            {
                "id": "cimientos-corridos-acero-pendiente",
                "severidad": "advertencia",
                "familia": "fundaciones",
                "categoria": "armadura_no_disponible",
                "titulo": "El acero no se dedujo de la sección geométrica",
                "mensaje": "El volumen fue calculado con la sección y longitud validadas. El acero requiere un detalle explícito de armadura.",
                "accion_recomendada": "Asociar y confirmar el detalle de armadura del cimiento de hormigón armado.",
                "bloqueante": False,
                "bloquea_resultado": False,
                "excluido_del_computo": True,
                "estado": "pendiente",
            }
        )
    alertas.append(
        {
            "id": "cimientos-corridos-plantilla-encofrado-pendientes",
            "severidad": "informacion",
            "familia": "fundaciones",
            "categoria": "dato_requerido",
            "titulo": "Plantilla y encofrado no incluidos",
            "mensaje": "No se obtuvo de forma inequívoca el espesor de la plantilla ni una condición de encofrado lateral.",
            "accion_recomendada": "Incorporar esos datos únicamente si están especificados en el proyecto.",
            "bloqueante": False,
            "bloquea_resultado": False,
            "excluido_del_computo": True,
            "estado": "pendiente",
        }
    )
    excluidas = [item for item in revision["elementos"] if not item["incluir"]]
    return {
        "estado_resultado": "parcial_revisado",
        "computos_disponibles": True,
        "tipologia_fundacion": "cimientos_corridos",
        "alcance_computo": {
            "calculado": ["longitud_cimientos_corridos", "volumen_cimientos_corridos"],
            "pendiente": ["acero", "encofrado", "plantilla", "pedestales", "vigas_riostra", "columnas"],
            "motivo": "Las secciones y longitudes fueron confirmadas por un profesional.",
        },
        "cantidad_fundaciones": len(incluidas),
        "cantidad_tipos": len(incluidas),
        "cantidad_tipos_fundacion": len(incluidas),
        "conteo_por_tipo": {item["referencia"]: 1 for item in incluidas},
        "referencias_fundaciones": sorted(item["referencia"] for item in incluidas),
        "longitud_total_cimientos_corridos_m": round(longitud_total, 6),
        "volumen_cimientos_corridos_m3": round(volumen_total, 6),
        "volumen_mamposteria_m3": round(volumen_mamposteria, 6),
        "volumen_hormigon_m3": round(volumen_hormigon, 6),
        "encofrado_zapatas_m2": None,
        "peso_acero_kg": None,
        "metros_acero": None,
        "barras_comerciales": None,
        "peso_compra_acero_kg": None,
        "cimientos_corridos_detalle": detalle,
        "cimientos_corridos_tramos": recorridos_confirmados,
        "fundaciones": detalle,
        "fundaciones_planta": [],
        "ubicaciones_fundaciones": [],
        "encofrado_zapatas_detalle": [],
        "armaduras": [],
        "compra_acero_detalle": [],
        "pedestales_computo_detalle": [],
        "vigas_riostra_computo_detalle": [],
        "columnas_fundaciones": [],
        "columnas_vinculadas_por_viga": [],
        "computos_por_elemento": {
            "cimientos_corridos": {
                "cantidad_tipos": len(incluidas),
                "estado": "parcial_revisado",
                "longitud": {"valor": round(longitud_total, 6), "unidad": "m", "estado": "calculado"},
                "volumen": {"valor": round(volumen_total, 6), "unidad": "m3", "estado": "calculado"},
                "acero": {"valor": None, "unidad": "kg", "estado": "pendiente_fuente"},
                "encofrado": {"valor": None, "unidad": "m2", "estado": "pendiente_condicion"},
            }
        },
        "revision_geometria_aplicada": revision,
        "elementos_excluidos": excluidas,
        "alertas_analisis": alertas,
        "resumen_alertas": {
            "total": len(alertas),
            "errores": 0,
            "advertencias": sum(item["severidad"] == "advertencia" for item in alertas),
            "informativas": sum(item["severidad"] == "informacion" for item in alertas),
            "excluidas_del_computo": sum(item["excluido_del_computo"] for item in alertas),
        },
        "confianza_lectura_porcentaje": 100,
    }

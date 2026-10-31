r"""Asociación espacial genérica entre referencias y cotas de una lámina.

El módulo no conoce prefijos de proyecto ni nombres de archivo. Trabaja con
las cajas que entrega PyMuPDF y con los contornos vectoriales del PDF:

1. Extrae palabras con ``page.get_text("words")``.
2. Clasifica cada token por su forma: referencia, dimensión, armadura,
   elevación, número o rótulo.
3. Fusiona tokens partidos por CAD (``30`` + ``x`` + ``30``).
4. Calcula distancias euclidianas borde-a-borde entre cajas.
5. Usa alineación, misma línea/bloque, líneas guía y contornos como evidencia.
6. Asigna cada dimensión a la referencia con mejor score. Si hay empate o
   evidencia insuficiente, no inventa la asociación: la deja para revisión.

La geometría pura (``asociar_cajas``) se puede probar sin abrir un PDF.
``asociar_pagina`` y ``asociar_pdf`` agregan la extracción con PyMuPDF.

Los contornos raster de páginas escaneadas no se reconstruyen aquí: esta etapa
trabaja con geometría vectorial. Un escaneo requiere OCR y contornos raster en
una etapa anterior.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Sequence

import pymupdf

from computos.documentos.analisis import normalizar_caja_visual
from computos.documentos.modelos import Caja
from computos.documentos.procesamiento_pdf import validar_pdf

__all__ = [
    "AsociacionEspacial",
    "CajaTexto",
    "ConfiguracionAsociacion",
    "Contorno",
    "NoAsociado",
    "ReferenciaAsociada",
    "ResultadoAsociacion",
    "TipoToken",
    "asociar_cajas",
    "asociar_pagina",
    "asociar_pdf",
    "clasificar_token",
    "distancia_caja_contorno",
    "distancia_centros",
    "distancia_entre_cajas",
    "distancia_punto_caja",
    "distancia_punto_segmento",
    "extraer_cajas_texto",
    "extraer_contornos",
    "extraer_lineas_guia",
    "fusionar_tokens_dimension",
    "preparar_cajas_texto",
]


# ---------------------------------------------------------------------------
# Patrones genéricos. No dependen de prefijos de proyecto.
# ---------------------------------------------------------------------------

DIMENSION_MULTI = re.compile(
    r"^\d+(?:[.,]\d+)?(?:\s*[xX×]\s*\d+(?:[.,]\d+)?){1,2}$"
)
DIMENSION_SINGLE = re.compile(
    r"^\d+(?:[.,]\d+)?\s*(?:cm|mm|m|mts|mt|pulg|\")$",
    re.IGNORECASE,
)
FRACTION = re.compile(
    r"^(?:Ø|ø|#)?\s*\d+\s*/\s*\d+\s*(?:\"|pulg)?$",
    re.IGNORECASE,
)
REBAR = re.compile(
    r"^(?:\d+\s*)?(?:Ø|ø|#)\s*\d+(?:\s*/\s*\d+)?(?:\s*@\s*\d+(?:[.,]\d+)?)?$",
    re.IGNORECASE,
)
ELEVATION = re.compile(
    r"^(?:NPT|N\.P\.T\.?)\s*[+-]?\s*\d+[.,]\d+\s*(?:m|mts)?$"
    r"|^[+-]\s*\d+[.,]\d+\s*(?:m|mts)?$",
    re.IGNORECASE,
)
REFERENCE = re.compile(r"^[A-ZÑ]{1,10}[.\-_/]*\d{1,4}[A-ZÑ]?$")
PURE_NUMBER = re.compile(r"^[+-]?\d+(?:[.,]\d+)?$")

DRAWING_STOPWORDS = frozenset(
    {
        "PLANTA", "CORTE", "DETALLE", "DETALLES", "ELEVACION", "ELEVACIÓN",
        "ESCALA", "ESC", "NPT", "NIVEL", "PROYECTO", "PROPIETARIO", "FECHA",
        "LAMINA", "LÁMINA", "PLANO", "PLANOS", "ESTRUCTURA", "ESTRUCTURAL",
        "FUNDACION", "FUNDACIÓN", "FUNDACIONES", "COLUMNA", "COLUMNAS",
        "VIGA", "VIGAS", "LOSA", "LOSAS", "MURO", "MUROS", "PEDESTAL",
        "PEDESTALES", "RIOSTRA", "RIOSTRAS", "CIMIENTO", "CIMIENTOS",
        "ARQUITECTURA", "SANITARIA", "ELECTRICA", "ELÉCTRICA", "GAS",
        "TABLA", "CUADRO", "PLANTILLA", "SIMBOLOGIA", "SÍMBOLOGÍA",
    }
)
UNIT_WORDS = frozenset({"CM", "MM", "M", "M2", "M3", "MTS", "MT", "KG", "PULG", '"'})
UNIDADES_EXCLUIDAS_REFERENCIA = frozenset(
    {"M1", "M2", "M3", "KG", "CM", "MM", "MT", "MTS"}
)


class TipoToken(StrEnum):
    """Forma sintáctica de un token dentro de una lámina."""

    REFERENCIA = "referencia"
    DIMENSION = "dimension"
    DIMENSION_LINEAL = "dimension_lineal"
    ARMADURA = "armadura"
    ELEVACION = "elevacion"
    NUMERO = "numero"
    ROTULO = "rotulo"
    TEXTO = "texto"
    VACIO = "vacio"


TIPOS_DIMENSION = frozenset(
    {
        TipoToken.DIMENSION,
        TipoToken.DIMENSION_LINEAL,
        TipoToken.ARMADURA,
        TipoToken.ELEVACION,
        TipoToken.NUMERO,
    }
)

PESO_TIPO_DIMENSION = {
    TipoToken.DIMENSION: 1.0,
    TipoToken.DIMENSION_LINEAL: 0.95,
    TipoToken.ARMADURA: 0.90,
    TipoToken.ELEVACION: 0.80,
    TipoToken.NUMERO: 0.55,
}

Segmento = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class ConfiguracionAsociacion:
    """Umbrales explícitos para que el resultado sea reproducible."""

    max_distancia_factor: float = 0.18
    min_score: float = 0.22
    min_margen: float = 0.03
    margen_contencion: float = 4.0
    tolerancia_linea_guia: float = 6.0
    max_distancia_contorno_factor: float = 0.10


@dataclass(frozen=True, slots=True)
class CajaTexto:
    """Palabra o token visual extraído de una página."""

    pagina: int
    texto: str
    caja: Caja
    bloque: int
    linea: int
    palabra: int
    tipo: TipoToken

    @property
    def centro(self) -> tuple[float, float]:
        return _centro(self.caja)

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return (self.caja.x0, self.caja.y0, self.caja.x1, self.caja.y1)


@dataclass(frozen=True, slots=True)
class Contorno:
    """Rectángulo envolvente de un dibujo vectorial cerrado."""

    pagina: int
    id: int
    caja: Caja
    tipo: str = "vector"

    @property
    def area(self) -> float:
        return max(self.caja.ancho, 0.0) * max(self.caja.alto, 0.0)

    def contiene_punto(
        self,
        punto: tuple[float, float],
        margen: float = 0.0,
    ) -> bool:
        x, y = punto
        return (
            self.caja.x0 - margen <= x <= self.caja.x1 + margen
            and self.caja.y0 - margen <= y <= self.caja.y1 + margen
        )

    def contiene_caja(self, caja: Caja, margen: float = 0.0) -> bool:
        return (
            self.caja.x0 - margen <= caja.x0
            and self.caja.y0 - margen <= caja.y0
            and caja.x1 <= self.caja.x1 + margen
            and caja.y1 <= self.caja.y1 + margen
        )


@dataclass(frozen=True, slots=True)
class AsociacionEspacial:
    """Una dimensión asociada a una referencia, con evidencia geométrica."""

    pagina: int
    referencia: str
    dimension: str
    tipo_dimension: TipoToken
    score: float
    distancia_px: float
    distancia_centros_px: float
    confianza: str
    requiere_revision: bool
    evidencia: dict[str, object] = field(default_factory=dict)
    contorno_id: int | None = None
    referencia_caja: Caja | None = None
    dimension_caja: Caja | None = None


@dataclass(frozen=True, slots=True)
class NoAsociado:
    """Dimensión que no pudo asociarse de forma defendible."""

    pagina: int
    texto: str
    tipo: TipoToken
    caja: Caja
    motivo: str
    mejor_referencia: str | None = None
    score: float | None = None
    margen: float | None = None


@dataclass(frozen=True, slots=True)
class ReferenciaAsociada:
    """Agrupación de todas las dimensiones asociadas a una referencia."""

    pagina: int
    referencia: str
    caja: Caja
    contorno_id: int | None
    asociaciones: tuple[AsociacionEspacial, ...]
    requiere_revision: bool


@dataclass(frozen=True, slots=True)
class ResultadoAsociacion:
    """Resultado completo y serializable de una página."""

    pagina: int
    ancho_pagina: float
    alto_pagina: float
    cajas: tuple[CajaTexto, ...]
    contornos: tuple[Contorno, ...]
    asociaciones: tuple[AsociacionEspacial, ...]
    referencias: tuple[ReferenciaAsociada, ...]
    no_asociados: tuple[NoAsociado, ...]

    @property
    def resumen(self) -> dict[str, int]:
        return {
            "cajas": len(self.cajas),
            "referencias": len(self.referencias),
            "dimensiones": sum(
                1 for caja in self.cajas if caja.tipo in TIPOS_DIMENSION
            ),
            "contornos": len(self.contornos),
            "asociaciones": len(self.asociaciones),
            "asociaciones_alta": sum(
                1 for item in self.asociaciones if item.confianza == "alta"
            ),
            "asociaciones_media": sum(
                1 for item in self.asociaciones if item.confianza == "media"
            ),
            "asociaciones_baja": sum(
                1 for item in self.asociaciones if item.confianza == "baja"
            ),
            "no_asociados": len(self.no_asociados),
        }

    def a_diccionario(self) -> dict:
        """Convierte el resultado a estructuras JSON-friendly."""

        return {
            "pagina": self.pagina,
            "ancho_pagina": round(self.ancho_pagina, 3),
            "alto_pagina": round(self.alto_pagina, 3),
            "cajas": [asdict(caja) for caja in self.cajas],
            "contornos": [
                {
                    "pagina": contorno.pagina,
                    "id": contorno.id,
                    "caja": asdict(contorno.caja),
                    "tipo": contorno.tipo,
                    "area": round(contorno.area, 3),
                }
                for contorno in self.contornos
            ],
            "asociaciones": [asdict(item) for item in self.asociaciones],
            "referencias": [
                {
                    "pagina": referencia.pagina,
                    "referencia": referencia.referencia,
                    "caja": asdict(referencia.caja),
                    "contorno_id": referencia.contorno_id,
                    "asociaciones": [
                        asdict(item) for item in referencia.asociaciones
                    ],
                    "requiere_revision": referencia.requiere_revision,
                }
                for referencia in self.referencias
            ],
            "no_asociados": [asdict(item) for item in self.no_asociados],
            "resumen": self.resumen,
        }


# ---------------------------------------------------------------------------
# Geometría pura
# ---------------------------------------------------------------------------


def _centro(caja: Caja) -> tuple[float, float]:
    return ((caja.x0 + caja.x1) / 2.0, (caja.y0 + caja.y1) / 2.0)


def distancia_entre_cajas(a: Caja, b: Caja) -> float:
    """Distancia euclidiana borde-a-borde entre dos cajas.

    Si las cajas se tocan o se solapan, la distancia es 0. Se usa esta medida
    y no la distancia entre centros porque dos cajas de tamaños muy distintos
    pueden tener centros lejanos aunque sus bordes estén próximos.
    """

    dx = max(0.0, max(a.x0, b.x0) - min(a.x1, b.x1))
    dy = max(0.0, max(a.y0, b.y0) - min(a.y1, b.y1))
    return math.hypot(dx, dy)


def distancia_centros(a: Caja, b: Caja) -> float:
    ax, ay = _centro(a)
    bx, by = _centro(b)
    return math.hypot(ax - bx, ay - by)


def distancia_punto_caja(punto: tuple[float, float], caja: Caja) -> float:
    x, y = punto
    dx = max(caja.x0 - x, x - caja.x1, 0.0)
    dy = max(caja.y0 - y, y - caja.y1, 0.0)
    return math.hypot(dx, dy)


def distancia_caja_contorno(caja: Caja, contorno: Contorno) -> float:
    """Distancia de una caja al contorno; 0 si está dentro o lo intersecta."""

    if contorno.contiene_caja(caja):
        return 0.0
    return distancia_entre_cajas(caja, contorno.caja)


def distancia_punto_segmento(
    punto: tuple[float, float],
    segmento: Segmento,
) -> float:
    """Distancia euclidiana de un punto al segmento más cercano."""

    px, py = punto
    x1, y1, x2, y2 = segmento
    dx, dy = x2 - x1, y2 - y1
    if dx == 0.0 and dy == 0.0:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def _alineacion(a: Caja, b: Caja) -> tuple[bool, bool]:
    alto = max(a.alto, b.alto, 1.0)
    ancho = max(a.ancho, b.ancho, 1.0)
    ax, ay = _centro(a)
    bx, by = _centro(b)
    horizontal = abs(ay - by) <= alto * 0.9
    vertical = abs(ax - bx) <= ancho * 0.9
    return horizontal, vertical


def _contencion(
    referencia: Caja,
    dimension: Caja,
    contornos: Sequence[Contorno],
    margen: float,
) -> tuple[float, int | None]:
    centro_referencia = _centro(referencia)
    centro_dimension = _centro(dimension)

    # El contorno más específico es el más pequeño que contiene ambos centros.
    completos = [
        contorno
        for contorno in contornos
        if contorno.contiene_punto(centro_referencia, margen)
        and contorno.contiene_punto(centro_dimension, margen)
    ]
    if completos:
        contorno = min(completos, key=lambda item: (item.area, item.id))
        return 1.0, contorno.id

    parciales = [
        contorno
        for contorno in contornos
        if contorno.contiene_punto(centro_referencia, margen)
        or contorno.contiene_punto(centro_dimension, margen)
    ]
    if not parciales:
        return 0.0, None
    contorno = min(parciales, key=lambda item: (item.area, item.id))
    return 0.5, contorno.id


def _linea_guia(
    referencia: Caja,
    dimension: Caja,
    segmentos: Sequence[Segmento],
    tolerancia: float,
) -> float:
    centro_referencia = _centro(referencia)
    centro_dimension = _centro(dimension)
    for segmento in segmentos:
        if (
            distancia_punto_segmento(centro_referencia, segmento) <= tolerancia
            and distancia_punto_segmento(centro_dimension, segmento) <= tolerancia
        ):
            return 1.0
    return 0.0


# ---------------------------------------------------------------------------
# Normalización y fusión de tokens
# ---------------------------------------------------------------------------


def _normalizar_token(texto: str) -> str:
    return (
        texto.replace("×", "x")
        .replace("–", "-")
        .replace("—", "-")
        .replace("−", "-")
        .strip()
    )


def _compactar(texto: str) -> str:
    return re.sub(r"\s+", "", _normalizar_token(texto))


def clasificar_token(texto: str) -> TipoToken:
    """Clasifica un token por su forma, sin mirar el proyecto ni el archivo."""

    normalizado = _normalizar_token(texto)
    if not normalizado:
        return TipoToken.VACIO
    compacto = _compactar(normalizado).upper()

    if DIMENSION_MULTI.match(compacto):
        return TipoToken.DIMENSION
    if DIMENSION_SINGLE.match(compacto):
        return TipoToken.DIMENSION_LINEAL
    if REBAR.match(compacto) or FRACTION.match(compacto):
        return TipoToken.ARMADURA
    if ELEVATION.match(compacto):
        return TipoToken.ELEVACION
    if compacto in UNIT_WORDS:
        return TipoToken.ROTULO
    if PURE_NUMBER.match(compacto):
        return TipoToken.NUMERO
    if (
        REFERENCE.match(compacto)
        and compacto not in DRAWING_STOPWORDS
        and compacto not in UNIDADES_EXCLUIDAS_REFERENCIA
    ):
        return TipoToken.REFERENCIA
    if compacto in DRAWING_STOPWORDS:
        return TipoToken.ROTULO
    return TipoToken.TEXTO


def _union_cajas(cajas: Sequence[CajaTexto]) -> Caja:
    return Caja(
        x0=min(caja.caja.x0 for caja in cajas),
        y0=min(caja.caja.y0 for caja in cajas),
        x1=max(caja.caja.x1 for caja in cajas),
        y1=max(caja.caja.y1 for caja in cajas),
    )


def fusionar_tokens_dimension(
    cajas: Sequence[CajaTexto],
) -> list[CajaTexto]:
    """Une tokens que CAD separó, por ejemplo ``30`` + ``x`` + ``30``.

    Solo fusiona si el texto combinado cumple un patrón de dimensión, armadura
    o elevación. Nunca fusiona una referencia con una dimensión.
    """

    if not cajas:
        return []

    ordenadas = sorted(
        cajas,
        key=lambda item: (
            item.pagina,
            round(item.centro[1], 3),
            round(item.caja.x0, 3),
            item.bloque,
            item.linea,
            item.palabra,
            item.texto,
        ),
    )
    usadas = [False] * len(ordenadas)
    salida: list[CajaTexto] = []

    for indice, caja in enumerate(ordenadas):
        if usadas[indice]:
            continue
        mejor_fin = indice
        mejor_texto = caja.texto
        mejor_tipo = caja.tipo

        for fin in range(indice + 1, min(indice + 4, len(ordenadas))):
            anterior = ordenadas[fin - 1]
            actual = ordenadas[fin]
            if actual.pagina != caja.pagina:
                break
            alto = max(anterior.caja.alto, actual.caja.alto, 1.0)
            separacion = actual.caja.x0 - anterior.caja.x1
            if separacion > alto * 1.2:
                break
            if abs(actual.centro[1] - caja.centro[1]) > alto * 0.8:
                break
            candidato = " ".join(
                item.texto for item in ordenadas[indice : fin + 1]
            )
            tipo_candidato = clasificar_token(_compactar(candidato))
            if tipo_candidato in TIPOS_DIMENSION:
                mejor_fin = fin
                mejor_texto = candidato
                mejor_tipo = tipo_candidato

        if mejor_fin > indice:
            grupo = ordenadas[indice : mejor_fin + 1]
            salida.append(
                CajaTexto(
                    pagina=caja.pagina,
                    texto=mejor_texto,
                    caja=_union_cajas(grupo),
                    bloque=caja.bloque,
                    linea=caja.linea,
                    palabra=caja.palabra,
                    tipo=mejor_tipo,
                )
            )
            for posicion in range(indice, mejor_fin + 1):
                usadas[posicion] = True
        else:
            usadas[indice] = True
            salida.append(caja)

    return sorted(
        salida,
        key=lambda item: (
            item.pagina,
            round(item.caja.y0, 3),
            round(item.caja.x0, 3),
            item.texto,
        ),
    )


# ---------------------------------------------------------------------------
# Extracción PyMuPDF
# ---------------------------------------------------------------------------


def _numero_pagina(pagina: pymupdf.Page, numero_pagina: int | None) -> int:
    return int(numero_pagina) if numero_pagina is not None else pagina.number + 1


def extraer_cajas_texto(
    pagina: pymupdf.Page,
    *,
    numero_pagina: int | None = None,
) -> list[CajaTexto]:
    """Extrae palabras y sus cajas en coordenadas visuales.

    PyMuPDF entrega las palabras sobre la página sin rotar. Se aplica la
    matriz de rotación para que cajas, contornos y dimensiones de página
    compartan el mismo sistema de coordenadas que ve el usuario.
    """

    numero = _numero_pagina(pagina, numero_pagina)
    cajas: list[CajaTexto] = []

    for palabra in pagina.get_text("words", sort=False):
        x0, y0, x1, y1, texto, bloque, linea, posicion = palabra
        texto = str(texto).strip()
        if not texto:
            continue
        caja_pdf = Caja(
            x0=round(float(x0), 3),
            y0=round(float(y0), 3),
            x1=round(float(x1), 3),
            y1=round(float(y1), 3),
        )
        cajas.append(
            CajaTexto(
                pagina=numero,
                texto=texto,
                caja=normalizar_caja_visual(pagina, caja_pdf),
                bloque=int(bloque),
                linea=int(linea),
                palabra=int(posicion),
                tipo=clasificar_token(texto),
            )
        )

    return sorted(
        cajas,
        key=lambda item: (
            round(item.caja.y0, 3),
            round(item.caja.x0, 3),
            item.bloque,
            item.linea,
            item.palabra,
            item.texto,
        ),
    )


def preparar_cajas_texto(
    pagina: pymupdf.Page,
    *,
    numero_pagina: int | None = None,
) -> list[CajaTexto]:
    """Extrae y fusiona tokens de dimensión en una sola llamada."""

    return fusionar_tokens_dimension(
        extraer_cajas_texto(pagina, numero_pagina=numero_pagina)
    )


def _es_contorno_cerrado(dibujo: dict) -> bool:
    """Indica si un dibujo vectorial delimita una región.

    PyMuPDF entrega rectángulos, curvas y polilíneas en la misma lista. Una
    línea de cota suelta no es un contorno; un rectángulo, un círculo o una
    polilínea que vuelve a su origen sí lo son.
    """

    items = dibujo.get("items") or []
    if not items:
        return False
    if dibujo.get("closePath") or dibujo.get("fill") is not None:
        return True
    if any(item[0] in {"re", "qu"} for item in items):
        return True

    inicio = items[0][1]
    fin = items[-1][-1]
    return math.hypot(
        float(inicio.x) - float(fin.x),
        float(inicio.y) - float(fin.y),
    ) <= 0.5


def extraer_contornos(
    pagina: pymupdf.Page,
    *,
    numero_pagina: int | None = None,
) -> list[Contorno]:
    """Extrae contornos vectoriales cerrados útiles para asociar elementos.

    Se descartan trazos abiertos, dibujos demasiado pequeños y el marco
    completo de la lámina. No se reconstruyen curvas complejas: se usa el
    rectángulo envolvente del dibujo.
    """

    numero = _numero_pagina(pagina, numero_pagina)
    area_pagina = max(pagina.rect.width * pagina.rect.height, 1.0)
    vistos: dict[tuple[float, float, float, float], Caja] = {}

    for dibujo in pagina.get_drawings():
        if not _es_contorno_cerrado(dibujo):
            continue
        rectangulo = dibujo.get("rect")
        if rectangulo is None:
            continue
        caja_pdf = Caja(
            x0=round(float(rectangulo.x0), 3),
            y0=round(float(rectangulo.y0), 3),
            x1=round(float(rectangulo.x1), 3),
            y1=round(float(rectangulo.y1), 3),
        )
        caja = normalizar_caja_visual(pagina, caja_pdf)
        ancho, alto = caja.ancho, caja.alto
        area = ancho * alto
        if ancho < 8.0 or alto < 8.0 or area < 100.0:
            continue
        if area > area_pagina * 0.85:
            continue
        vistos.setdefault((caja.x0, caja.y0, caja.x1, caja.y1), caja)

    ordenadas = sorted(
        vistos.values(),
        key=lambda caja: (
            round(caja.y0, 3),
            round(caja.x0, 3),
            round(caja.x1, 3),
            round(caja.y1, 3),
        ),
    )
    return [
        Contorno(pagina=numero, id=indice, caja=caja)
        for indice, caja in enumerate(ordenadas)
    ]


def extraer_lineas_guia(pagina: pymupdf.Page) -> list[Segmento]:
    """Extrae segmentos rectos del PDF en coordenadas visuales."""

    segmentos: set[Segmento] = set()
    for dibujo in pagina.get_drawings():
        for item in dibujo.get("items", []):
            if item[0] != "l":
                continue
            inicio, fin = item[1], item[2]
            inicio_visual = inicio * pagina.rotation_matrix
            fin_visual = fin * pagina.rotation_matrix
            segmento = (
                round(float(inicio_visual.x), 3),
                round(float(inicio_visual.y), 3),
                round(float(fin_visual.x), 3),
                round(float(fin_visual.y), 3),
            )
            if math.hypot(segmento[2] - segmento[0], segmento[3] - segmento[1]) == 0:
                continue
            segmentos.add(segmento)
    return sorted(segmentos)


# ---------------------------------------------------------------------------
# Scoring y asignación
# ---------------------------------------------------------------------------


Candidato = tuple[float, CajaTexto, int | None, dict[str, object]]


def _score_candidato(
    referencia: CajaTexto,
    dimension: CajaTexto,
    *,
    diagonal: float,
    contornos: Sequence[Contorno],
    segmentos: Sequence[Segmento],
    competencia: int,
    configuracion: ConfiguracionAsociacion,
) -> tuple[float, int | None, dict[str, object]]:
    distancia = distancia_entre_cajas(referencia.caja, dimension.caja)
    proximidad = math.exp(
        -distancia / max(diagonal * 0.04, 1.0)
    )
    alineacion_horizontal, alineacion_vertical = _alineacion(
        referencia.caja,
        dimension.caja,
    )
    alineacion = (
        1.0 if alineacion_horizontal else (0.7 if alineacion_vertical else 0.0)
    )
    misma_linea = (
        referencia.bloque == dimension.bloque
        and referencia.linea == dimension.linea
    )
    mismo_bloque = referencia.bloque == dimension.bloque
    contencion, contorno_id = _contencion(
        referencia.caja,
        dimension.caja,
        contornos,
        configuracion.margen_contencion,
    )
    linea_guia = _linea_guia(
        referencia.caja,
        dimension.caja,
        segmentos,
        configuracion.tolerancia_linea_guia,
    )
    peso_tipo = PESO_TIPO_DIMENSION.get(dimension.tipo, 0.5)
    penalizacion = 1.0 / (1.0 + max(competencia - 1, 0))

    score = peso_tipo * (
        0.45 * proximidad
        + 0.20 * alineacion
        + 0.10 * (1.0 if misma_linea else 0.0)
        + 0.05 * (1.0 if mismo_bloque else 0.0)
        + 0.15 * contencion
        + 0.05 * linea_guia
    ) * penalizacion

    evidencia = {
        "distancia_borde_px": round(distancia, 3),
        "distancia_centros_px": round(
            distancia_centros(referencia.caja, dimension.caja),
            3,
        ),
        "proximidad": round(proximidad, 6),
        "alineacion": round(alineacion, 3),
        "misma_linea": misma_linea,
        "mismo_bloque": mismo_bloque,
        "contencion": round(contencion, 3),
        "linea_guia": round(linea_guia, 3),
        "competencia": competencia,
        "penalizacion": round(penalizacion, 6),
    }
    return score, contorno_id, evidencia


def _confianza(score: float, margen: float) -> str:
    if score >= 0.52 and margen >= 0.08:
        return "alta"
    if score >= 0.32 and margen >= 0.04:
        return "media"
    return "baja"


def _orden_candidato(
    item: tuple[float, CajaTexto, int | None, dict[str, object]],
    dimension: CajaTexto,
) -> tuple:
    score, referencia, contorno_id, _ = item
    return (
        -round(score, 9),
        round(distancia_entre_cajas(referencia.caja, dimension.caja), 6),
        referencia.texto,
        round(referencia.caja.y0, 3),
        round(referencia.caja.x0, 3),
        contorno_id if contorno_id is not None else -1,
    )


def _ordenar_entradas(
    cajas: Sequence[CajaTexto],
    contornos: Sequence[Contorno],
    lineas_guia: Sequence[Segmento],
) -> tuple[
    tuple[CajaTexto, ...],
    tuple[Contorno, ...],
    tuple[Segmento, ...],
    int,
]:
    cajas_ordenadas = tuple(
        sorted(
            cajas,
            key=lambda item: (
                item.pagina,
                round(item.caja.y0, 3),
                round(item.caja.x0, 3),
                item.texto,
            ),
        )
    )
    contornos_ordenados = tuple(
        sorted(
            contornos,
            key=lambda item: (
                item.pagina,
                round(item.caja.y0, 3),
                round(item.caja.x0, 3),
                item.id,
            ),
        )
    )
    segmentos = tuple(sorted(lineas_guia))

    paginas = {item.pagina for item in cajas_ordenadas}
    paginas.update(item.pagina for item in contornos_ordenados)
    if len(paginas) > 1:
        raise ValueError(
            "asociar_cajas procesa una sola página; "
            "usá asociar_pdf para varias páginas."
        )
    return cajas_ordenadas, contornos_ordenados, segmentos, next(iter(paginas), 1)


def _dimensiones_pagina(
    cajas: Sequence[CajaTexto],
    contornos: Sequence[Contorno],
    ancho_pagina: float | None,
    alto_pagina: float | None,
) -> tuple[float, float, float]:
    ancho = (
        float(ancho_pagina)
        if ancho_pagina is not None
        else max(
            [item.caja.x1 for item in cajas]
            + [item.caja.x1 for item in contornos]
            + [1.0]
        )
    )
    alto = (
        float(alto_pagina)
        if alto_pagina is not None
        else max(
            [item.caja.y1 for item in cajas]
            + [item.caja.y1 for item in contornos]
            + [1.0]
        )
    )
    return ancho, alto, max(math.hypot(ancho, alto), 1.0)


def _separar_tokens(
    cajas: Sequence[CajaTexto],
) -> tuple[list[tuple[int, CajaTexto]], list[tuple[int, CajaTexto]]]:
    referencias = [
        (indice, caja)
        for indice, caja in enumerate(cajas)
        if caja.tipo == TipoToken.REFERENCIA
    ]
    dimensiones = [
        (indice, caja)
        for indice, caja in enumerate(cajas)
        if caja.tipo in TIPOS_DIMENSION
    ]
    return referencias, dimensiones


def _competencia_por_dimension(
    referencias: Sequence[tuple[int, CajaTexto]],
    dimensiones: Sequence[tuple[int, CajaTexto]],
    max_distancia: float,
) -> dict[int, int]:
    return {
        indice: sum(
            1
            for _, referencia in referencias
            if distancia_centros(referencia.caja, dimension.caja) <= max_distancia
        )
        for indice, dimension in dimensiones
    }


def _candidatos_por_dimension(
    referencias: Sequence[tuple[int, CajaTexto]],
    dimensiones: Sequence[tuple[int, CajaTexto]],
    *,
    diagonal: float,
    max_distancia: float,
    contornos: Sequence[Contorno],
    segmentos: Sequence[Segmento],
    competencia: dict[int, int],
    configuracion: ConfiguracionAsociacion,
) -> dict[int, list[Candidato]]:
    candidatos: dict[int, list[Candidato]] = {}
    for indice_dimension, dimension in dimensiones:
        for _, referencia in referencias:
            if distancia_centros(referencia.caja, dimension.caja) > max_distancia:
                continue
            score, contorno_id, evidencia = _score_candidato(
                referencia,
                dimension,
                diagonal=diagonal,
                contornos=contornos,
                segmentos=segmentos,
                competencia=competencia.get(indice_dimension, 1),
                configuracion=configuracion,
            )
            candidatos.setdefault(indice_dimension, []).append(
                (score, referencia, contorno_id, evidencia)
            )
    return candidatos


def _crear_asociacion(
    pagina: int,
    referencia: CajaTexto,
    dimension: CajaTexto,
    *,
    score: float,
    contorno_id: int | None,
    evidencia: dict[str, object],
    confianza: str,
    requiere_revision: bool | None = None,
) -> AsociacionEspacial:
    return AsociacionEspacial(
        pagina=pagina,
        referencia=referencia.texto,
        dimension=dimension.texto,
        tipo_dimension=dimension.tipo,
        score=round(score, 6),
        distancia_px=round(
            distancia_entre_cajas(referencia.caja, dimension.caja),
            3,
        ),
        distancia_centros_px=round(
            distancia_centros(referencia.caja, dimension.caja),
            3,
        ),
        confianza=confianza,
        requiere_revision=(
            confianza != "alta"
            if requiere_revision is None
            else requiere_revision
        ),
        evidencia=evidencia,
        contorno_id=contorno_id,
        referencia_caja=referencia.caja,
        dimension_caja=dimension.caja,
    )


def _asignar_por_score(
    pagina: int,
    dimensiones: Sequence[tuple[int, CajaTexto]],
    candidatos_por_dimension: dict[int, list[Candidato]],
    configuracion: ConfiguracionAsociacion,
) -> tuple[list[AsociacionEspacial], dict[int, NoAsociado], set[int]]:
    asociaciones: list[AsociacionEspacial] = []
    no_asociados: dict[int, NoAsociado] = {}
    dimensiones_asociadas: set[int] = set()

    for indice_dimension, dimension in dimensiones:
        candidatos = candidatos_por_dimension.get(indice_dimension, [])
        if not candidatos:
            no_asociados[indice_dimension] = NoAsociado(
                pagina=pagina,
                texto=dimension.texto,
                tipo=dimension.tipo,
                caja=dimension.caja,
                motivo="sin_referencia_en_radio",
            )
            continue

        candidatos.sort(key=lambda item: _orden_candidato(item, dimension))
        mejor_score, mejor_referencia, contorno_id, evidencia = candidatos[0]
        segundo_score = candidatos[1][0] if len(candidatos) > 1 else 0.0
        margen = mejor_score - segundo_score

        if (
            mejor_score < configuracion.min_score
            or margen < configuracion.min_margen
        ):
            no_asociados[indice_dimension] = NoAsociado(
                pagina=pagina,
                texto=dimension.texto,
                tipo=dimension.tipo,
                caja=dimension.caja,
                motivo="asociacion_ambigua",
                mejor_referencia=mejor_referencia.texto,
                score=round(mejor_score, 6),
                margen=round(margen, 6),
            )
            continue

        confianza = _confianza(mejor_score, margen)
        asociaciones.append(
            _crear_asociacion(
                pagina,
                mejor_referencia,
                dimension,
                score=mejor_score,
                contorno_id=contorno_id,
                evidencia=evidencia,
                confianza=confianza,
            )
        )
        dimensiones_asociadas.add(indice_dimension)

    return asociaciones, no_asociados, dimensiones_asociadas


def _asociar_por_contorno(
    *,
    pagina: int,
    dimensiones: Sequence[tuple[int, CajaTexto]],
    referencias: Sequence[tuple[int, CajaTexto]],
    contornos: Sequence[Contorno],
    dimensiones_asociadas: set[int],
    diagonal: float,
    configuracion: ConfiguracionAsociacion,
) -> tuple[list[AsociacionEspacial], set[int]]:
    asociaciones: list[AsociacionEspacial] = []
    indices: set[int] = set()
    max_distancia_contorno = (
        diagonal * configuracion.max_distancia_contorno_factor
    )

    for indice_dimension, dimension in dimensiones:
        if indice_dimension in dimensiones_asociadas:
            continue

        candidatos = []
        for contorno in contornos:
            distancia = distancia_caja_contorno(dimension.caja, contorno)
            if distancia > max_distancia_contorno:
                continue
            referencias_dentro = [
                referencia
                for _, referencia in referencias
                if contorno.contiene_punto(
                    referencia.centro,
                    configuracion.margen_contencion,
                )
            ]
            if len(referencias_dentro) != 1:
                continue
            candidatos.append(
                (
                    distancia,
                    contorno.area,
                    contorno.id,
                    referencias_dentro[0],
                    contorno,
                )
            )

        if not candidatos:
            continue

        distancia, _, _, referencia, contorno = min(
            candidatos,
            key=lambda item: (
                round(item[0], 6),
                round(item[1], 6),
                item[2],
                item[3].texto,
                round(item[3].caja.y0, 3),
                round(item[3].caja.x0, 3),
            ),
        )
        score = max(
            0.33,
            0.55 - distancia / max(max_distancia_contorno, 1.0) * 0.20,
        )
        asociaciones.append(
            _crear_asociacion(
                pagina,
                referencia,
                dimension,
                score=score,
                contorno_id=contorno.id,
                evidencia={
                    "asociacion_por_contorno": True,
                    "distancia_contorno_px": round(distancia, 3),
                    "referencias_en_contorno": 1,
                },
                confianza="media",
                requiere_revision=True,
            )
        )
        indices.add(indice_dimension)

    return asociaciones, indices


def _agrupar_referencias(
    pagina: int,
    referencias: Sequence[tuple[int, CajaTexto]],
    asociaciones: Sequence[AsociacionEspacial],
) -> tuple[ReferenciaAsociada, ...]:
    por_referencia: dict[tuple[str, Caja], list[AsociacionEspacial]] = {}
    for asociacion in asociaciones:
        if asociacion.referencia_caja is None:
            continue
        clave = (asociacion.referencia, asociacion.referencia_caja)
        por_referencia.setdefault(clave, []).append(asociacion)

    salida = []
    for _, referencia in referencias:
        items = sorted(
            por_referencia.get((referencia.texto, referencia.caja), []),
            key=lambda item: (
                item.tipo_dimension,
                item.distancia_px,
                item.dimension,
            ),
        )
        salida.append(
            ReferenciaAsociada(
                pagina=pagina,
                referencia=referencia.texto,
                caja=referencia.caja,
                contorno_id=items[0].contorno_id if items else None,
                asociaciones=tuple(items),
                requiere_revision=(
                    any(item.requiere_revision for item in items)
                    or not items
                ),
            )
        )
    return tuple(salida)


def asociar_cajas(
    cajas: Sequence[CajaTexto],
    *,
    contornos: Sequence[Contorno] = (),
    lineas_guia: Sequence[Segmento] = (),
    ancho_pagina: float | None = None,
    alto_pagina: float | None = None,
    configuracion: ConfiguracionAsociacion | None = None,
) -> ResultadoAsociacion:
    """Asocia dimensiones a referencias usando solo geometría.

    ``cajas`` debe contener tokens ya fusionados con
    :func:`fusionar_tokens_dimension`. Todas las cajas y contornos deben
    pertenecer a la misma página.
    """

    configuracion = configuracion or ConfiguracionAsociacion()
    cajas_ordenadas, contornos_ordenados, segmentos, pagina = _ordenar_entradas(
        cajas,
        contornos,
        lineas_guia,
    )
    ancho, alto, diagonal = _dimensiones_pagina(
        cajas_ordenadas,
        contornos_ordenados,
        ancho_pagina,
        alto_pagina,
    )
    max_distancia = diagonal * configuracion.max_distancia_factor
    referencias, dimensiones = _separar_tokens(cajas_ordenadas)

    competencia = _competencia_por_dimension(
        referencias,
        dimensiones,
        max_distancia,
    )
    candidatos_por_dimension = _candidatos_por_dimension(
        referencias,
        dimensiones,
        diagonal=diagonal,
        max_distancia=max_distancia,
        contornos=contornos_ordenados,
        segmentos=segmentos,
        competencia=competencia,
        configuracion=configuracion,
    )

    asociaciones, no_asociados, dimensiones_asociadas = _asignar_por_score(
        pagina,
        dimensiones,
        candidatos_por_dimension,
        configuracion,
    )

    # Segunda pasada: una cota puede estar fuera del contorno del elemento.
    # Si el contorno contiene una única referencia, se asocia a ese elemento
    # aunque no haya una referencia a corta distancia. Siempre queda en revisión.
    asociaciones_contorno, indices_contorno = _asociar_por_contorno(
        pagina=pagina,
        dimensiones=dimensiones,
        referencias=referencias,
        contornos=contornos_ordenados,
        dimensiones_asociadas=dimensiones_asociadas,
        diagonal=diagonal,
        configuracion=configuracion,
    )
    asociaciones.extend(asociaciones_contorno)
    dimensiones_asociadas |= indices_contorno
    for indice in indices_contorno:
        no_asociados.pop(indice, None)

    referencias_salida = _agrupar_referencias(
        pagina,
        referencias,
        asociaciones,
    )

    return ResultadoAsociacion(
        pagina=pagina,
        ancho_pagina=ancho,
        alto_pagina=alto,
        cajas=cajas_ordenadas,
        contornos=contornos_ordenados,
        asociaciones=tuple(
            sorted(
                asociaciones,
                key=lambda item: (
                    item.referencia,
                    item.distancia_px,
                    item.dimension,
                ),
            )
        ),
        referencias=tuple(referencias_salida),
        no_asociados=tuple(
            no_asociados[indice]
            for indice in sorted(no_asociados)
        ),
    )


# ---------------------------------------------------------------------------
# API de página y PDF
# ---------------------------------------------------------------------------


def asociar_pagina(
    pagina: pymupdf.Page,
    *,
    numero_pagina: int | None = None,
    configuracion: ConfiguracionAsociacion | None = None,
) -> ResultadoAsociacion:
    """Extrae y asocia una página completa."""

    numero = _numero_pagina(pagina, numero_pagina)
    cajas = preparar_cajas_texto(pagina, numero_pagina=numero)
    contornos = extraer_contornos(pagina, numero_pagina=numero)
    segmentos = extraer_lineas_guia(pagina)
    return asociar_cajas(
        cajas,
        contornos=contornos,
        lineas_guia=segmentos,
        ancho_pagina=pagina.rect.width,
        alto_pagina=pagina.rect.height,
        configuracion=configuracion,
    )


def asociar_pdf(
    ruta_pdf: str | Path,
    *,
    configuracion: ConfiguracionAsociacion | None = None,
) -> list[ResultadoAsociacion]:
    """Procesa todas las páginas de un PDF en orden estable."""

    ruta = Path(ruta_pdf).expanduser().resolve()
    validar_pdf(ruta)
    resultados: list[ResultadoAsociacion] = []
    with pymupdf.open(ruta) as documento:
        for numero, pagina in enumerate(documento, start=1):
            resultados.append(
                asociar_pagina(
                    pagina,
                    numero_pagina=numero,
                    configuracion=configuracion,
                )
            )
    return resultados

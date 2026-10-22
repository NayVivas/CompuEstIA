"""Inspección general de documentos PDF antes de interpretar la estructura.

Este módulo no busca F1, C1 ni ningún elemento particular. Su responsabilidad
es describir cómo está construido cada PDF y normalizar sus coordenadas.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import unicodedata

import pymupdf

from computos.documentos.modelos import (
    AnalisisDocumento,
    AnalisisPagina,
    Caja,
    OrientacionPagina,
    PalabraNormalizada,
    RolPagina,
    TipoContenidoPagina,
)
from computos.documentos.procesamiento_pdf import validar_pdf


@dataclass(frozen=True, slots=True)
class UmbralesAnalisisPDF:
    """Valores generales usados solamente para diagnosticar el PDF."""

    caracteres_minimos_texto: int = 10
    palabras_minimas_texto: int = 3
    cobertura_imagen_dominante: float = 0.65
    diferencia_cuadrada_pt: float = 1.0
    cantidad_muestra_palabras: int = 25


PALABRAS_CLAVE_ROLES: dict[RolPagina, tuple[str, ...]] = {
    RolPagina.PLANTA: (
        "PLANTA",
        "PLANO DE PLANTA",
        "PLANTA DE FUNDACIONES",
        "PLANTA ESTRUCTURAL",
        "IMPLANTACION",
    ),
    RolPagina.CUADRO: (
        "CUADRO",
        "TABLA",
        "PLANILLA",
        "CUADRO DE FUNDACIONES",
        "CUADRO DE COLUMNAS",
    ),
    RolPagina.DETALLE: (
        "DETALLE",
        "DETALLES",
        "CORTE",
        "SECCION",
        "ARMADURA",
    ),
    RolPagina.COLUMNAS: (
        "COLUMNA",
        "COLUMNAS",
        "PILAR",
        "PILARES",
    ),
    RolPagina.PORTICO: (
        "PORTICO",
        "PORTICOS",
        "ELEVACION DE PORTICO",
        "ELEVACIONES DE PORTICOS",
    ),
}


def _redondear(valor: float) -> float:
    return round(float(valor), 3)


def _normalizar_texto(texto: str) -> str:
    """Pasa un texto a mayúsculas y elimina tildes para poder compararlo."""

    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(caracter for caracter in texto if not unicodedata.combining(caracter))
    texto = re.sub(r"\s+", " ", texto.upper()).strip()
    return texto


def _contiene_expresion(texto: str, expresion: str) -> bool:
    patron_normal = rf"(?<!\w){re.escape(expresion)}(?!\w)"
    if re.search(patron_normal, texto):
        return True

    # Algunos programas CAD exportan los títulos como "C U A D R O".
    # Este segundo patrón admite espacios entre las letras sin modificar el
    # texto original ni imponer ese formato al resto del programa.
    palabras = expresion.split()
    palabras_espaciadas = [
        r"\s*".join(re.escape(letra) for letra in palabra)
        for palabra in palabras
    ]
    patron_espaciado = rf"(?<!\w){r'\s+'.join(palabras_espaciadas)}(?!\w)"
    return re.search(patron_espaciado, texto) is not None


def detectar_roles_pagina(texto: str) -> tuple[list[RolPagina], dict[str, list[str]]]:
    """Devuelve roles candidatos; nunca obliga a elegir un único rol."""

    texto_normalizado = _normalizar_texto(texto)
    evidencias: dict[str, list[str]] = {}

    for rol, expresiones in PALABRAS_CLAVE_ROLES.items():
        encontradas = [
            expresion
            for expresion in expresiones
            if _contiene_expresion(texto_normalizado, expresion)
        ]
        if encontradas:
            evidencias[rol.value] = encontradas

    roles = [
        rol
        for rol in PALABRAS_CLAVE_ROLES
        if rol.value in evidencias
    ]
    if not roles:
        roles = [RolPagina.DESCONOCIDO]

    return roles, evidencias


def determinar_orientacion(
    ancho_visual: float,
    alto_visual: float,
    diferencia_cuadrada_pt: float = 1.0,
) -> OrientacionPagina:
    if abs(ancho_visual - alto_visual) <= diferencia_cuadrada_pt:
        return OrientacionPagina.CUADRADA
    if ancho_visual > alto_visual:
        return OrientacionPagina.HORIZONTAL
    return OrientacionPagina.VERTICAL


def normalizar_caja_visual(pagina: pymupdf.Page, caja_pdf: Caja) -> Caja:
    """Transforma coordenadas internas del PDF a las que ve el usuario.

    PyMuPDF entrega el texto sobre la página sin rotar. Aplicar la matriz de
    rotación permite que una tabla se analice igual aunque el PDF tenga una
    rotación de 0, 90, 180 o 270 grados.
    """

    rectangulo_pdf = pymupdf.Rect(
        caja_pdf.x0,
        caja_pdf.y0,
        caja_pdf.x1,
        caja_pdf.y1,
    )
    rectangulo_visual = rectangulo_pdf * pagina.rotation_matrix
    return Caja(
        x0=_redondear(rectangulo_visual.x0),
        y0=_redondear(rectangulo_visual.y0),
        x1=_redondear(rectangulo_visual.x1),
        y1=_redondear(rectangulo_visual.y1),
    )


def extraer_palabras_normalizadas(
    ruta_pdf: str | Path,
    ordenar_visualmente: bool = True,
) -> list[PalabraNormalizada]:
    """Extrae palabras que comparten un sistema visual de coordenadas."""

    ruta_pdf = Path(ruta_pdf)
    validar_pdf(ruta_pdf)
    resultado: list[PalabraNormalizada] = []

    with pymupdf.open(ruta_pdf) as documento:
        for numero_pagina, pagina in enumerate(documento, start=1):
            for palabra in pagina.get_text("words", sort=False):
                x0, y0, x1, y1, texto, bloque, linea, posicion = palabra
                texto = texto.strip()
                if not texto:
                    continue

                caja_pdf = Caja(
                    x0=_redondear(x0),
                    y0=_redondear(y0),
                    x1=_redondear(x1),
                    y1=_redondear(y1),
                )
                resultado.append(
                    PalabraNormalizada(
                        pagina=numero_pagina,
                        texto=texto,
                        caja_pdf=caja_pdf,
                        caja_visual=normalizar_caja_visual(pagina, caja_pdf),
                        numero_bloque=int(bloque),
                        numero_linea=int(linea),
                        numero_palabra=int(posicion),
                    )
                )

    if ordenar_visualmente:
        resultado.sort(
            key=lambda palabra: (
                palabra.pagina,
                palabra.caja_visual.y0,
                palabra.caja_visual.x0,
            )
        )

    return resultado


def _calcular_cobertura_imagenes(pagina: pymupdf.Page) -> tuple[int, float]:
    """Estima qué parte de la página está cubierta por imágenes raster."""

    rectangulos: set[tuple[float, float, float, float]] = set()

    for imagen in pagina.get_images(full=True):
        xref = imagen[0]
        for rectangulo in pagina.get_image_rects(xref):
            recortado = rectangulo & pagina.mediabox
            if recortado.is_empty:
                continue
            rectangulos.add(
                (
                    _redondear(recortado.x0),
                    _redondear(recortado.y0),
                    _redondear(recortado.x1),
                    _redondear(recortado.y1),
                )
            )

    area_pagina = float(pagina.mediabox.get_area())
    area_imagenes = sum(
        pymupdf.Rect(rectangulo).get_area()
        for rectangulo in rectangulos
    )
    cobertura = min(area_imagenes / area_pagina, 1.0) if area_pagina else 0.0
    return len(rectangulos), round(cobertura, 4)


def clasificar_contenido_pagina(
    *,
    cantidad_palabras: int,
    cantidad_caracteres: int,
    cantidad_objetos_vectoriales: int,
    cantidad_imagenes: int,
    cobertura_imagenes: float,
    umbrales: UmbralesAnalisisPDF,
) -> TipoContenidoPagina:
    tiene_texto = (
        cantidad_palabras >= umbrales.palabras_minimas_texto
        or cantidad_caracteres >= umbrales.caracteres_minimos_texto
    )
    tiene_vectores = cantidad_objetos_vectoriales > 0
    tiene_imagenes = cantidad_imagenes > 0
    imagen_dominante = cobertura_imagenes >= umbrales.cobertura_imagen_dominante

    if not tiene_texto and not tiene_vectores and not tiene_imagenes:
        return TipoContenidoPagina.VACIA
    if imagen_dominante and (tiene_texto or tiene_vectores):
        return TipoContenidoPagina.MIXTA
    if imagen_dominante or (tiene_imagenes and not tiene_texto and not tiene_vectores):
        return TipoContenidoPagina.ESCANEADA
    if tiene_texto or tiene_vectores:
        return TipoContenidoPagina.VECTORIAL
    return TipoContenidoPagina.ESCANEADA


def _analizar_pagina(
    pagina: pymupdf.Page,
    numero: int,
    umbrales: UmbralesAnalisisPDF,
) -> AnalisisPagina:
    texto = pagina.get_text("text", sort=False)
    palabras_crudas = pagina.get_text("words", sort=False)
    cantidad_imagenes, cobertura_imagenes = _calcular_cobertura_imagenes(pagina)
    cantidad_vectores = len(pagina.get_drawings())
    tipo_contenido = clasificar_contenido_pagina(
        cantidad_palabras=len(palabras_crudas),
        cantidad_caracteres=len(texto.strip()),
        cantidad_objetos_vectoriales=cantidad_vectores,
        cantidad_imagenes=cantidad_imagenes,
        cobertura_imagenes=cobertura_imagenes,
        umbrales=umbrales,
    )
    roles, evidencias = detectar_roles_pagina(texto)
    advertencias: list[str] = []

    if tipo_contenido == TipoContenidoPagina.ESCANEADA:
        advertencias.append(
            "La página parece escaneada y no ofrece texto vectorial suficiente."
        )
    elif tipo_contenido == TipoContenidoPagina.MIXTA:
        advertencias.append(
            "La página combina una imagen dominante con texto o trazos vectoriales."
        )
    elif tipo_contenido == TipoContenidoPagina.VACIA:
        advertencias.append("La página no contiene información detectable.")

    if roles == [RolPagina.DESCONOCIDO]:
        advertencias.append(
            "No se pudo inferir la función de la página; deberá confirmarla el usuario."
        )

    palabras_visuales = []
    for palabra in palabras_crudas:
        texto_palabra = palabra[4].strip()
        if not texto_palabra:
            continue
        caja_pdf = Caja(*(_redondear(valor) for valor in palabra[:4]))
        caja_visual = normalizar_caja_visual(pagina, caja_pdf)
        palabras_visuales.append((caja_visual.y0, caja_visual.x0, texto_palabra))
    palabras_visuales.sort()

    return AnalisisPagina(
        numero=numero,
        ancho_original_pt=_redondear(pagina.mediabox.width),
        alto_original_pt=_redondear(pagina.mediabox.height),
        ancho_visual_pt=_redondear(pagina.rect.width),
        alto_visual_pt=_redondear(pagina.rect.height),
        rotacion_grados=int(pagina.rotation),
        orientacion=determinar_orientacion(
            pagina.rect.width,
            pagina.rect.height,
            umbrales.diferencia_cuadrada_pt,
        ),
        tipo_contenido=tipo_contenido,
        cantidad_palabras=len(palabras_crudas),
        cantidad_caracteres=len(texto.strip()),
        cantidad_objetos_vectoriales=cantidad_vectores,
        cantidad_imagenes=cantidad_imagenes,
        cobertura_imagenes=cobertura_imagenes,
        roles_candidatos=roles,
        evidencias_roles=evidencias,
        muestra_palabras=[
            palabra[2]
            for palabra in palabras_visuales[: umbrales.cantidad_muestra_palabras]
        ],
        requiere_revision=tipo_contenido
        in {
            TipoContenidoPagina.ESCANEADA,
            TipoContenidoPagina.MIXTA,
            TipoContenidoPagina.VACIA,
        }
        or roles == [RolPagina.DESCONOCIDO],
        advertencias=advertencias,
    )


def _sha256_archivo(ruta: Path) -> str:
    resumen = hashlib.sha256()
    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
            resumen.update(bloque)
    return resumen.hexdigest()


def _clasificar_documento(paginas: list[AnalisisPagina]) -> TipoContenidoPagina:
    if not paginas:
        return TipoContenidoPagina.VACIA
    tipos = {pagina.tipo_contenido for pagina in paginas}
    if len(tipos) == 1:
        return next(iter(tipos))
    return TipoContenidoPagina.MIXTA


def analizar_documento_pdf(
    ruta_pdf: str | Path,
    umbrales: UmbralesAnalisisPDF | None = None,
) -> AnalisisDocumento:
    """Analiza un PDF completo sin suponer qué elementos estructurales contiene."""

    ruta_pdf = Path(ruta_pdf).expanduser().resolve()
    validar_pdf(ruta_pdf)
    umbrales = umbrales or UmbralesAnalisisPDF()

    try:
        with pymupdf.open(ruta_pdf) as documento:
            if documento.needs_pass:
                raise ValueError(f"El PDF está protegido con contraseña: {ruta_pdf}")
            paginas = [
                _analizar_pagina(pagina, numero, umbrales)
                for numero, pagina in enumerate(documento, start=1)
            ]
    except (pymupdf.FileDataError, RuntimeError) as error:
        raise ValueError(f"No se pudo leer el PDF {ruta_pdf}: {error}") from error

    return AnalisisDocumento(
        ruta=str(ruta_pdf),
        nombre=ruta_pdf.name,
        sha256=_sha256_archivo(ruta_pdf),
        cantidad_paginas=len(paginas),
        tipo_contenido=_clasificar_documento(paginas),
        total_palabras=sum(pagina.cantidad_palabras for pagina in paginas),
        total_caracteres=sum(pagina.cantidad_caracteres for pagina in paginas),
        total_objetos_vectoriales=sum(
            pagina.cantidad_objetos_vectoriales for pagina in paginas
        ),
        total_imagenes=sum(pagina.cantidad_imagenes for pagina in paginas),
        requiere_modo_asistido=(
            not paginas
            or any(
                pagina.tipo_contenido
                in {
                    TipoContenidoPagina.ESCANEADA,
                    TipoContenidoPagina.MIXTA,
                    TipoContenidoPagina.VACIA,
                }
                for pagina in paginas
            )
        ),
        paginas=paginas,
    )


def resolver_rutas_pdf(entradas: list[str | Path]) -> list[Path]:
    """Acepta archivos o carpetas y devuelve PDF únicos en orden estable."""

    encontrados: list[Path] = []
    vistos: set[Path] = set()

    for entrada in entradas:
        ruta = Path(entrada).expanduser().resolve()
        if not ruta.exists():
            raise FileNotFoundError(f"No se encontró la entrada: {ruta}")

        candidatos = (
            [ruta]
            if ruta.is_file()
            else sorted(
                candidato
                for candidato in ruta.rglob("*")
                if candidato.is_file() and candidato.suffix.lower() == ".pdf"
            )
        )
        for candidato in candidatos:
            candidato = candidato.resolve()
            validar_pdf(candidato)
            if candidato not in vistos:
                vistos.add(candidato)
                encontrados.append(candidato)

    if not encontrados:
        raise ValueError("No se encontraron archivos PDF en las entradas indicadas.")

    return encontrados


def crear_manifiesto_documentos(documentos: list[AnalisisDocumento]) -> dict:
    """Agrupa los análisis bajo un formato versionado para etapas posteriores."""

    return {
        "version_formato": 1,
        "cantidad_documentos": len(documentos),
        "requiere_modo_asistido": any(
            documento.requiere_modo_asistido for documento in documentos
        ),
        "documentos": [documento.a_diccionario() for documento in documentos],
    }

"""OCR local y opcional para páginas PDF sin texto utilizable.

El resultado no es solamente una cadena: también se conserva una página PDF
buscable. De ese modo los motores posteriores reciben palabras con coordenadas
y no pierden la relación entre el texto reconocido y el dibujo.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import subprocess
import math

import pymupdf


@dataclass(frozen=True, slots=True)
class ResultadoOCR:
    texto: str
    ruta_pdf_buscable: Path
    idioma: str
    dpi: int
    palabras_agregadas: int = 0
    preserva_vectores: bool = True


class OCRNoDisponible(RuntimeError):
    """Indica que el OCR local no está instalado o no pudo ejecutarse."""


def ocr_habilitado() -> bool:
    return os.getenv("COMPUTOESTIA_OCR", "1").strip().casefold() not in {
        "0",
        "false",
        "no",
        "off",
    }


def resolver_tesseract() -> str | None:
    """Localiza Tesseract también en las rutas habituales de Windows.

    La instalación oficial de Windows no siempre agrega el ejecutable a
    ``PATH``.  El motor no debe confundir ese caso con un PDF ilegible.
    ``COMPUTOESTIA_TESSERACT_CMD`` permite indicar otra ubicación sin tocar
    el código.
    """

    configurado = os.getenv("COMPUTOESTIA_TESSERACT_CMD", "").strip()
    if configurado:
        ruta = Path(configurado).expanduser()
        if ruta.is_file():
            return str(ruta)
        localizado = shutil.which(configurado)
        if localizado:
            return localizado

    localizado = shutil.which("tesseract")
    if localizado:
        return localizado

    candidatos = []
    for variable in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.getenv(variable, "").strip()
        if not base:
            continue
        raiz = Path(base)
        candidatos.extend(
            (
                raiz / "Tesseract-OCR" / "tesseract.exe",
                raiz / "Programs" / "Tesseract-OCR" / "tesseract.exe",
            )
        )
    return next((str(ruta) for ruta in candidatos if ruta.is_file()), None)


def diagnostico_ocr() -> dict:
    """Estado real del OCR para la API y las pantallas de diagnóstico."""

    habilitado = ocr_habilitado()
    comando = resolver_tesseract() if habilitado else None
    tessdata = resolver_tessdata(comando) if comando else None
    idiomas = sorted(_idiomas_disponibles(tessdata)) if tessdata else []
    ejecutable_valido = False
    if comando:
        try:
            prueba = subprocess.run([comando, "--version"], capture_output=True, text=True, timeout=5)
            ejecutable_valido = prueba.returncode == 0 and "tesseract" in (prueba.stdout + prueba.stderr).lower()
        except (OSError, subprocess.SubprocessError):
            pass
    listo = habilitado and ejecutable_valido and bool(set(idiomas) - {"osd", "equ"})
    if listo:
        mensaje = "Tesseract está disponible para recuperar cotas y texto rasterizado."
    elif not habilitado:
        mensaje = "El OCR local está desactivado por COMPUTOESTIA_OCR."
    elif comando and not ejecutable_valido:
        mensaje = "Se encontró Tesseract, pero su ejecutable no pudo iniciarse. Ejecutá VERIFICAR_ENTORNO.bat."
    elif comando and not (set(idiomas) - {"osd", "equ"}):
        mensaje = "Se encontró Tesseract, pero faltan sus datos de idioma. Ejecutá INSTALAR_OCR_WINDOWS.bat y volvé a verificar."
    else:
        mensaje = (
            "Tesseract no se encontró. Instalalo o definí "
            "COMPUTOESTIA_TESSERACT_CMD con la ruta a tesseract.exe."
        )
    return {
        "habilitado": habilitado,
        "tesseract_disponible": comando is not None,
        "listo": listo,
        "comando": comando,
        "idiomas": idiomas,
        "tessdata": str(tessdata) if tessdata else None,
        "mensaje": mensaje,
    }


def resolver_tessdata(comando: str | None = None) -> Path | None:
    """Encuentra también los idiomas junto al ejecutable de Windows."""
    candidatos = []
    configurado = os.getenv("TESSDATA_PREFIX", "").strip()
    if configurado:
        candidatos.append(Path(configurado))
    if comando:
        candidatos.extend([Path(comando).parent / "tessdata", Path(comando).parent / "share" / "tessdata"])
    try:
        candidatos.append(Path(pymupdf.get_tessdata()))
    except Exception:
        pass
    return next((p for p in candidatos if p.is_dir() and any(p.glob("*.traineddata"))), None)


def _dpi_configurado() -> int:
    try:
        dpi = int(os.getenv("COMPUTOESTIA_OCR_DPI", "200"))
    except ValueError:
        dpi = 200
    return max(150, min(dpi, 400))


def _idiomas_disponibles(tessdata: Path) -> set[str]:
    if not tessdata.is_dir():
        return set()
    return {archivo.stem for archivo in tessdata.glob("*.traineddata")}


def _seleccionar_idiomas(tessdata: Path) -> str:
    solicitados = [
        parte.strip()
        for parte in re.split(
            r"[+,;\s]+",
            os.getenv("COMPUTOESTIA_OCR_LANG", "spa+eng"),
        )
        if parte.strip()
    ]
    disponibles = _idiomas_disponibles(tessdata) - {"osd", "equ"}
    seleccionados = [idioma for idioma in solicitados if idioma in disponibles]
    if not seleccionados and "eng" in disponibles:
        seleccionados = ["eng"]
    if not seleccionados and disponibles:
        seleccionados = [sorted(disponibles)[0]]
    if not seleccionados:
        raise OCRNoDisponible(
            "Tesseract está instalado, pero no se encontraron idiomas entrenados."
        )
    return "+".join(seleccionados)


def reconocer_pagina(
    pagina: pymupdf.Page,
    destino: str | Path,
) -> ResultadoOCR:
    """Reconoce una página y crea un PDF de una página con texto posicional."""

    if not ocr_habilitado():
        raise OCRNoDisponible("El OCR local está desactivado por configuración.")
    if resolver_tesseract() is None:
        raise OCRNoDisponible(
            "Tesseract no está instalado. También podés indicar su ruta "
            "mediante COMPUTOESTIA_TESSERACT_CMD."
        )

    tessdata = resolver_tessdata(resolver_tesseract())
    if tessdata is None:
        raise OCRNoDisponible(
            "PyMuPDF no pudo localizar los datos de idioma de Tesseract."
        )

    idioma = _seleccionar_idiomas(tessdata)
    dpi = _dpi_configurado()
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)

    try:
        # TextPage mantiene las coordenadas PDF originales. No se sustituye la
        # planta vectorial por una imagen ni se reescala la página al aplicar OCR.
        textpage = pagina.get_textpage_ocr(language=idioma, dpi=dpi, full=True, tessdata=str(tessdata))
        reconocidas = pagina.get_text("words", textpage=textpage, sort=False)
        originales = [pymupdf.Rect(w[:4]) for w in pagina.get_text("words", sort=False)]
        direcciones = {}
        for indice, bloque in enumerate(pagina.get_text("dict", textpage=textpage).get("blocks", [])):
            for linea_i, linea in enumerate(bloque.get("lines", [])):
                dx, dy = linea.get("dir", (1, 0))
                direcciones[(bloque.get("number", indice), linea_i)] = int(round(math.degrees(math.atan2(-dy, dx)) / 90) * 90) % 360
        agregadas = 0
        with pymupdf.open() as copia:
            copia.insert_pdf(pagina.parent, from_page=pagina.number, to_page=pagina.number)
            salida = copia[0]
            for x0, y0, x1, y1, valor, bloque, linea, _pos in reconocidas:
                caja = pymupdf.Rect(x0, y0, x1, y1)
                if not valor.strip() or caja.is_empty:
                    continue
                if any((caja & otra).get_area() / max(1.0, min(caja.get_area(), otra.get_area())) > .25 for otra in originales):
                    continue  # El texto nativo tiene prioridad sobre una lectura OCR.
                rotacion = direcciones.get((bloque, linea), 0)
                alto = caja.height if rotacion in {0, 180} else caja.width
                tamano = max(2.0, alto / 1.375)
                punto = {
                    0: (x0, y1 - alto * .2), 90: (x1 - alto * .2, y1),
                    180: (x1, y0 + alto * .2), 270: (x0 + alto * .2, y0),
                }[rotacion]
                salida.insert_text(punto, valor, fontsize=tamano, fontname="helv", rotate=rotacion, render_mode=3)
                agregadas += 1
            texto = salida.get_text("text", sort=False).strip()
            copia.save(destino, no_new_id=True)
    except Exception as error:
        destino.unlink(missing_ok=True)
        raise OCRNoDisponible(
            "Tesseract no pudo reconocer esta página."
        ) from error

    if len(texto) < 10:
        destino.unlink(missing_ok=True)
        raise OCRNoDisponible(
            "El OCR terminó, pero no recuperó texto suficiente para clasificar."
        )

    return ResultadoOCR(
        texto=texto,
        ruta_pdf_buscable=destino,
        idioma=idioma,
        dpi=dpi,
        palabras_agregadas=agregadas,
    )


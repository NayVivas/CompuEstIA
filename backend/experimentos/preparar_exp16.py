"""Prepara el ZIP de nuevos proyectos para anotarlo como EXP16.

Uso desde la carpeta ``backend``::

    python experimentos/preparar_exp16.py --zip "C:\\ruta\\compressed_Nuevos.zip"

El script extrae únicamente PDF, conserva los grupos de fuente, genera el
inventario de páginas y no modifica anotaciones profesionales existentes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import shutil
import stat
import sys
import unicodedata
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath

import pymupdf as fitz


BACKEND_DIR = Path(__file__).resolve().parents[1]
DATASET_DIR = BACKEND_DIR / "data" / "dataset_exp16"
DOCUMENTOS_DIR = DATASET_DIR / "documentos"
INVENTARIO = DATASET_DIR / "EXP16_paginas_inventario.csv"
ANOTACIONES = DATASET_DIR / "EXP16_anotaciones.json"

MAXIMO_TOTAL_DESCOMPRIMIDO = 4 * 1024 * 1024 * 1024
MAXIMO_ARCHIVO = 500 * 1024 * 1024
MINIMO_CARACTERES_NATIVOS = 50

DUPLICADOS_PARA_REVISION = {
    "Proyecto02_colegio/plano23.pdf": "revision_colegio_01",
    "Proyecto02_colegio/plano24.pdf": "revision_colegio_01",
    "Proyecto02_colegio/plano56.pdf": "revision_colegio_02",
    "Proyecto02_colegio/plano57.pdf": "revision_colegio_02",
}

CAMPOS_INVENTARIO = [
    "proyecto_id",
    "grupo_fuente",
    "documento",
    "ruta_relativa",
    "pagina",
    "cantidad_palabras",
    "cantidad_caracteres",
    "cantidad_imagenes",
    "cantidad_objetos_vectoriales",
    "tiene_texto",
    "tiene_imagenes",
    "requiere_ocr",
    "tipo_contenido",
    "es_topografia_origen",
    "rotacion_grados",
    "ancho_pt",
    "alto_pt",
    "sha256_archivo",
    "pistas_texto",
    "grupo_revision_duplicado",
]


def _argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepara los nuevos proyectos para el anotador EXP16.",
    )
    parser.add_argument(
        "--zip",
        dest="ruta_zip",
        type=Path,
        required=True,
        help="Ruta del archivo compressed_Nuevos.zip.",
    )
    return parser.parse_args()


def _natural_key(value: str):
    return [
        int(piece) if piece.isdigit() else piece.casefold()
        for piece in re.split(r"(\d+)", value)
    ]


def _normalizar_texto(texto: str) -> str:
    texto = unicodedata.normalize("NFKC", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _sha256(ruta: Path) -> str:
    calculo = hashlib.sha256()
    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
            calculo.update(bloque)
    return calculo.hexdigest()


def _es_enlace(info: zipfile.ZipInfo) -> bool:
    modo = info.external_attr >> 16
    return stat.S_ISLNK(modo)


def _ruta_segura(info: zipfile.ZipInfo) -> PurePosixPath:
    ruta = PurePosixPath(info.filename.replace("\\", "/"))
    if ruta.is_absolute() or ".." in ruta.parts:
        raise ValueError(f"Ruta insegura dentro del ZIP: {info.filename}")
    if _es_enlace(info):
        raise ValueError(f"El ZIP contiene un enlace no permitido: {info.filename}")
    return ruta


def _miembros_pdf(archivo_zip: zipfile.ZipFile) -> list[tuple[zipfile.ZipInfo, PurePosixPath]]:
    resultado = []
    total = 0
    for info in archivo_zip.infolist():
        ruta = _ruta_segura(info)
        if info.is_dir():
            continue
        if info.file_size > MAXIMO_ARCHIVO:
            raise ValueError(f"Archivo demasiado grande dentro del ZIP: {info.filename}")
        total += info.file_size
        if total > MAXIMO_TOTAL_DESCOMPRIMIDO:
            raise ValueError("El tamaño descomprimido del ZIP supera el límite de seguridad.")
        if ruta.suffix.casefold() == ".pdf":
            resultado.append((info, ruta))
    if not resultado:
        raise ValueError("El ZIP no contiene archivos PDF.")
    return sorted(resultado, key=lambda item: _natural_key(item[1].as_posix()))


def _sin_raiz_nuevos(ruta: PurePosixPath) -> PurePosixPath:
    partes = ruta.parts
    if partes and partes[0].casefold() == "nuevos":
        partes = partes[1:]
    if len(partes) < 2:
        raise ValueError(f"El PDF no está dentro de una carpeta de fuente: {ruta}")
    return PurePosixPath(*partes)


def _grupo_y_proyecto(ruta_interna: PurePosixPath) -> tuple[str, str, bool]:
    partes = ruta_interna.parts
    carpeta = partes[0]
    if carpeta.casefold() != "topogrefia":
        return carpeta, carpeta, False
    if len(partes) >= 3 and partes[1].casefold().startswith("proyecto"):
        return (
            f"Topogrefia/{partes[1]}",
            f"Topografia_{partes[1]}",
            True,
        )
    return (
        "Topogrefia/Sueltos_fuente_desconocida",
        "Topografia_Sueltos",
        True,
    )


def _tipo_contenido(caracteres: int, imagenes: int, dibujos: int) -> str:
    if caracteres >= MINIMO_CARACTERES_NATIVOS and dibujos >= 10:
        return "texto_y_vectores"
    if caracteres >= MINIMO_CARACTERES_NATIVOS:
        return "texto_nativo"
    if imagenes > 0:
        return "escaneado_o_imagen"
    if dibujos >= 10:
        return "vector_sin_texto_suficiente"
    return "contenido_escaso"


def _extraer_documentos(
    archivo_zip: zipfile.ZipFile,
    miembros: list[tuple[zipfile.ZipInfo, PurePosixPath]],
) -> list[tuple[Path, PurePosixPath]]:
    if DOCUMENTOS_DIR.exists() and any(DOCUMENTOS_DIR.rglob("*.pdf")):
        raise RuntimeError(
            "dataset_exp16/documentos ya contiene PDF. "
            "No se sobrescribió para proteger el trabajo existente."
        )
    DOCUMENTOS_DIR.mkdir(parents=True, exist_ok=True)
    extraidos = []
    for info, ruta_zip in miembros:
        destino = DOCUMENTOS_DIR.joinpath(*ruta_zip.parts)
        destino.parent.mkdir(parents=True, exist_ok=True)
        with archivo_zip.open(info) as origen, destino.open("wb") as salida:
            shutil.copyfileobj(origen, salida, length=1024 * 1024)
        extraidos.append((destino, _sin_raiz_nuevos(ruta_zip)))
    return extraidos


def _inventariar(
    documentos: list[tuple[Path, PurePosixPath]],
) -> list[dict]:
    filas = []
    for ruta_pdf, ruta_interna in documentos:
        grupo, proyecto_id, es_topografia = _grupo_y_proyecto(ruta_interna)
        sha = _sha256(ruta_pdf)
        grupo_duplicado = DUPLICADOS_PARA_REVISION.get(
            ruta_interna.as_posix(),
            "",
        )
        with fitz.open(ruta_pdf) as documento:
            for indice, pagina in enumerate(documento, start=1):
                texto = _normalizar_texto(pagina.get_text("text") or "")
                palabras = pagina.get_text("words") or []
                imagenes = pagina.get_images(full=True) or []
                try:
                    dibujos = len(pagina.get_drawings())
                except Exception:
                    dibujos = 0
                caracteres = len(texto)
                tipo = _tipo_contenido(caracteres, len(imagenes), dibujos)
                filas.append(
                    {
                        "proyecto_id": proyecto_id,
                        "grupo_fuente": grupo,
                        "documento": ruta_pdf.name,
                        "ruta_relativa": ruta_pdf.relative_to(DATASET_DIR).as_posix(),
                        "pagina": indice,
                        "cantidad_palabras": len(palabras),
                        "cantidad_caracteres": caracteres,
                        "cantidad_imagenes": len(imagenes),
                        "cantidad_objetos_vectoriales": dibujos,
                        "tiene_texto": caracteres >= MINIMO_CARACTERES_NATIVOS,
                        "tiene_imagenes": bool(imagenes),
                        "requiere_ocr": caracteres < MINIMO_CARACTERES_NATIVOS,
                        "tipo_contenido": tipo,
                        "es_topografia_origen": es_topografia,
                        "rotacion_grados": int(pagina.rotation),
                        "ancho_pt": round(float(pagina.rect.width), 2),
                        "alto_pt": round(float(pagina.rect.height), 2),
                        "sha256_archivo": sha,
                        "pistas_texto": texto[:700],
                        "grupo_revision_duplicado": grupo_duplicado,
                    }
                )
    return filas


def _guardar_inventario(filas: list[dict]) -> None:
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    temporal = INVENTARIO.with_suffix(".tmp")
    with temporal.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=CAMPOS_INVENTARIO)
        escritor.writeheader()
        escritor.writerows(filas)
    temporal.replace(INVENTARIO)
    if not ANOTACIONES.exists():
        ANOTACIONES.write_text("{}\n", encoding="utf-8")


def main() -> int:
    argumentos = _argumentos()
    ruta_zip = argumentos.ruta_zip.expanduser().resolve()
    if not ruta_zip.is_file():
        print(f"No se encontró el ZIP: {ruta_zip}", file=sys.stderr)
        return 2

    try:
        with zipfile.ZipFile(ruta_zip) as archivo_zip:
            miembros = _miembros_pdf(archivo_zip)
            documentos = _extraer_documentos(archivo_zip, miembros)
        filas = _inventariar(documentos)
        _guardar_inventario(filas)
    except Exception as error:
        print(f"No se pudo preparar EXP16: {error}", file=sys.stderr)
        return 1

    proyectos = Counter(fila["proyecto_id"] for fila in filas)
    print(f"PDF extraídos: {len(documentos)}")
    print(f"Páginas inventariadas: {len(filas)}")
    print(f"Grupos para clasificar: {len(proyectos)}")
    print(f"Páginas que requieren OCR: {sum(fila['requiere_ocr'] for fila in filas)}")
    print(f"Inventario: {INVENTARIO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

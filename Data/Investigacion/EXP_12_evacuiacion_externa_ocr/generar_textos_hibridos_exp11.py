"""Genera texto PDF + OCR para EXP-11 sin consultar sus etiquetas.

La política es deliberadamente idéntica a EXP-09: se conserva todo texto
nativo no vacío y se usa OCR únicamente cuando la página no contiene texto
PDF. Los umbrales y la búsqueda de orientación se importan del generador
anterior para impedir ajustes oportunistas sobre el conjunto de evaluación.

Ejemplo desde la raíz del proyecto::

    python backend/experimentos/generar_textos_hibridos_exp11.py \
      --etiquetas Data/EXP_11_nuevos_proyectos/EXP11_GROUND_TRUTH_FINAL.json \
      --zip Nuevos_Proyectos.zip
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from zipfile import ZipFile

import pymupdf

from generar_textos_hibridos import (
    MINIMO_PALABRAS_FIABLES,
    UMBRAL_CONFIANZA,
    idioma_disponible,
    ocr_orientado,
)


RAIZ = Path(__file__).resolve().parents[2]


def _cargar_filas(ruta: Path) -> list[dict]:
    contenido = json.loads(ruta.read_text(encoding="utf-8-sig"))
    filas = contenido.get("filas")
    if not isinstance(filas, list) or not filas:
        raise ValueError("El Ground Truth no contiene una lista 'filas' válida")
    claves = [(fila.get("archivo"), int(fila.get("pagina", 0))) for fila in filas]
    if len(claves) != len(set(claves)):
        raise ValueError("El Ground Truth contiene páginas repetidas")
    return filas


def generar(
    etiquetas: Path,
    archivo_zip: Path,
    salida: Path,
    idioma: str,
    dpi: int,
) -> dict:
    if not 90 <= dpi <= 250:
        raise ValueError("Usá un DPI entre 90 y 250")

    filas = _cargar_filas(etiquetas)
    registros = []
    estados = Counter()
    estados_metricas = Counter()

    salida.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(archivo_zip) as comprimido:
        miembros = set(comprimido.namelist())
        pdf_anterior = None
        documento_pdf = None
        try:
            for numero, fila in enumerate(filas, start=1):
                archivo = fila["archivo"]
                pagina_numero = int(fila["pagina"])
                if archivo not in miembros:
                    raise FileNotFoundError(f"No está en el ZIP: {archivo}")

                if archivo != pdf_anterior:
                    if documento_pdf is not None:
                        documento_pdf.close()
                    documento_pdf = pymupdf.open(
                        stream=comprimido.read(archivo), filetype="pdf"
                    )
                    pdf_anterior = archivo

                indice = pagina_numero - 1
                if not 0 <= indice < len(documento_pdf):
                    raise ValueError(f"Página inválida: {archivo}#{pagina_numero}")

                pagina = documento_pdf[indice]
                texto_nativo = pagina.get_text("text").strip()
                registro = {
                    "archivo": archivo,
                    "proyecto_id": fila["proyecto_id"],
                    "pagina": pagina_numero,
                    "incluir_en_metricas": fila.get("incluir_en_metricas") is not False,
                    "texto_pagina": texto_nativo,
                    "estado": "texto_pdf" if texto_nativo else None,
                    "idioma_ocr": "",
                    "rotacion_ocr": None,
                    "palabras_fiables": None,
                    "confianza_media_fiable": None,
                }

                if not texto_nativo:
                    resultado = ocr_orientado(pagina, idioma, dpi)
                    registro.update({
                        "estado": resultado["estado"],
                        "idioma_ocr": idioma,
                        "rotacion_ocr": resultado["rotacion_ocr"],
                        "palabras_fiables": resultado["palabras_fiables"],
                        "confianza_media_fiable": resultado["confianza_media_fiable"],
                    })
                    if resultado["estado"] == "ocr_con_texto":
                        registro["texto_pagina"] = resultado["texto_pagina"]

                registros.append(registro)
                estados[registro["estado"]] += 1
                if registro["incluir_en_metricas"]:
                    estados_metricas[registro["estado"]] += 1
                if numero % 25 == 0 or numero == len(filas):
                    print(
                        f"{numero}/{len(filas)} páginas; "
                        f"OCR recuperado: {estados['ocr_con_texto']}",
                        flush=True,
                    )
        finally:
            if documento_pdf is not None:
                documento_pdf.close()

    salida.write_text(
        json.dumps(registros, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    resumen = {
        "metodo": "texto PDF nativo; OCR solo si el texto nativo está vacío",
        "paginas": len(registros),
        "paginas_incluidas_en_metricas": sum(
            registro["incluir_en_metricas"] for registro in registros
        ),
        "idioma_ocr": idioma,
        "dpi": dpi,
        "umbral_confianza_palabra": UMBRAL_CONFIANZA,
        "minimo_palabras_fiables": MINIMO_PALABRAS_FIABLES,
        "estados": dict(estados),
        "estados_en_metricas": dict(estados_metricas),
    }
    salida.with_suffix(".resumen.json").write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return resumen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--etiquetas", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument(
        "--salida",
        type=Path,
        default=RAIZ / "Data/EXP_12_ocr_externo/EXP12_TEXTO_HIBRIDO.json",
    )
    parser.add_argument("--idioma", help="Idioma instalado de Tesseract")
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args()
    idioma = idioma_disponible(args.idioma)
    resumen = generar(args.etiquetas, args.zip, args.salida, idioma, args.dpi)
    print(json.dumps(resumen, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

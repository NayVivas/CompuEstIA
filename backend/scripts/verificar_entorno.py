"""Diagnóstico ejecutable en Windows, sin depender del arranque de FastAPI."""

from pathlib import Path
import argparse
import json
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pymupdf

from computos.documentos.ocr import diagnostico_ocr, reconocer_pagina


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--requerir-ocr", action="store_true")
    args = parser.parse_args()
    estado = diagnostico_ocr()
    print(json.dumps({"python": sys.version.split()[0], "pymupdf": pymupdf.VersionBind, "ocr": estado}, ensure_ascii=True, indent=2))
    if not estado["listo"]:
        print("OCR NO OPERATIVO: ejecutar INSTALAR_OCR_WINDOWS.bat antes de procesar planos escaneados o texto dibujado.")
        return 2 if args.requerir_ocr else 0
    try:
        with TemporaryDirectory(prefix="computoestia-prueba-ocr-") as carpeta:
            with pymupdf.open() as fuente:
                pagina = fuente.new_page(width=650, height=220)
                pagina.insert_text((40, 110), "COMPUTOESTIA OCR 1234", fontsize=32)
                imagen = pagina.get_pixmap(matrix=pymupdf.Matrix(2, 2)).tobytes("png")
            with pymupdf.open() as escaneado:
                pagina = escaneado.new_page(width=650, height=220)
                pagina.insert_image(pagina.rect, stream=imagen)
                resultado = reconocer_pagina(pagina, Path(carpeta) / "prueba.pdf")
            if "OCR" not in resultado.texto.upper() or "1234" not in resultado.texto:
                raise RuntimeError("La prueba no recupero las palabras esperadas.")
        print("OCR OPERATIVO: prueba real de reconocimiento y coordenadas completada.")
    except Exception as error:
        print(f"OCR NO OPERATIVO: {error}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

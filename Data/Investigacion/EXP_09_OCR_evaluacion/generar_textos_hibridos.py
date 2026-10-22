"""Construye un cache de texto PDF + OCR para EXP-03, sin usar etiquetas.

Desde la raíz del proyecto:
    python backend/experimentos/generar_textos_hibridos.py

Se necesita Tesseract instalado y disponible en PATH. Si existen datos de
entrenamiento nuevos, reconstruir el cache desde los PDF antes de reentrenar.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from io import BytesIO
import json
from pathlib import Path
import shutil
import subprocess
from zipfile import ZipFile

import pymupdf


CLAVE = ("proyecto_id", "documento", "pagina")
UMBRAL_CONFIANZA = 50
MINIMO_PALABRAS_FIABLES = 8


def leer_csv(ruta: Path) -> list[dict[str, str]]:
    with ruta.open("r", encoding="utf-8-sig", newline="") as archivo:
        return list(csv.DictReader(archivo))


def clave(fila: dict[str, str]) -> tuple[str, str, str]:
    return tuple(fila[campo] for campo in CLAVE)


def idioma_disponible(solicitado: str | None) -> str:
    if not shutil.which("tesseract"):
        raise RuntimeError("Instalá Tesseract OCR y agregá tesseract al PATH.")
    salida = subprocess.run(["tesseract", "--list-langs"], text=True,
                            capture_output=True, check=True)
    idiomas = set(salida.stdout.splitlines()[1:] + salida.stderr.splitlines()[1:])
    if solicitado:
        faltantes = set(solicitado.split("+")) - idiomas
        if faltantes:
            raise ValueError(f"Faltan idiomas de Tesseract: {sorted(faltantes)}")
        return solicitado
    return "spa+eng" if {"spa", "eng"} <= idiomas else ("spa" if "spa" in idiomas else "eng")


def ocr_orientado(pagina: pymupdf.Page, idioma: str, dpi: int) -> dict:
    """Evalúa 0/180; si no hay señal, prueba las otras dos orientaciones."""
    resultados = []
    for rotacion in (0, 180, 90, 270):
        if rotacion in (90, 270) and max(
            (resultado["palabras_fiables"] for resultado in resultados), default=0
        ) >= MINIMO_PALABRAS_FIABLES:
            break
        matriz = pymupdf.Matrix(dpi / 72, dpi / 72).prerotate(rotacion)
        imagen = pagina.get_pixmap(matrix=matriz, alpha=False).tobytes("png")
        resultado = subprocess.run(
            ["tesseract", "stdin", "stdout", "-l", idioma, "--psm", "11", "tsv"],
            input=imagen, capture_output=True, check=True,
        )
        filas = csv.DictReader(
            BytesIO(resultado.stdout).read().decode("utf-8-sig").splitlines(),
            delimiter="\t",
        )
        palabras = []
        confiables = []
        for fila in filas:
            palabra = fila["text"].strip()
            try:
                confianza = float(fila["conf"])
            except ValueError:
                continue
            if palabra and confianza >= 30:
                palabras.append(palabra)
            if len(palabra) >= 2 and confianza >= UMBRAL_CONFIANZA:
                confiables.append(confianza)
        resultados.append({
            "rotacion_ocr": rotacion,
            "texto_pagina": " ".join(palabras),
            "palabras_fiables": len(confiables),
            "confianza_media_fiable": round(sum(confiables) / len(confiables), 2)
            if confiables else 0.0,
            "puntuacion": sum(confiables),
        })
    mejor = max(resultados, key=lambda resultado: resultado["puntuacion"])
    return {
        **mejor,
        "estado": "ocr_con_texto" if mejor["palabras_fiables"] >= MINIMO_PALABRAS_FIABLES
        else "ocr_baja_calidad",
    }


def abrir_pdf(fila: dict, raiz_pdfs: Path, archivo_zip: ZipFile | None) -> bytes:
    proyecto, documento = fila["proyecto_id"], fila["documento"]
    if Path(documento).name != documento or Path(proyecto).name != proyecto:
        raise ValueError("Nombres de proyecto o PDF inválidos en el inventario")
    if archivo_zip:
        miembro = f"ComputoEstIA/backend/data/dataset_exp02/{proyecto}/{documento}"
        return archivo_zip.read(miembro)
    return (raiz_pdfs / proyecto / documento).read_bytes()


def generar(data_dir: Path, raiz_pdfs: Path, salida: Path, idioma: str,
            dpi: int, ruta_zip: Path | None = None) -> dict:
    if not 90 <= dpi <= 250:
        raise ValueError("Usá un DPI entre 90 y 250")
    cache = leer_csv(data_dir / "EXP_07_tfidf_logreg/EXP07_TEXT_CACHE.csv")
    paginas = leer_csv(data_dir / "EXP_03_protocolo_split/EXP03_DATASET_CON_SPLIT.csv")
    indices = {clave(fila): fila for fila in cache}
    if len(indices) != len(cache) or {clave(f) for f in paginas} != set(indices):
        raise ValueError("Cache de texto y EXP-03 tienen páginas duplicadas o diferentes")

    # ZipFile abierto una sola vez; cada PDF se abre solo para las páginas sin texto.
    archivo_zip = ZipFile(ruta_zip) if ruta_zip else None
    salida.parent.mkdir(parents=True, exist_ok=True)
    resumen = Counter()
    por_split: dict[str, Counter] = {}
    campos = [*CLAVE, "split", "texto_pagina", "estado", "idioma_ocr",
              "rotacion_ocr", "palabras_fiables", "confianza_media_fiable"]
    pdf_anterior = None
    documento_pdf = None
    try:
        with salida.open("w", encoding="utf-8", newline="") as archivo:
            escritor = csv.DictWriter(archivo, fieldnames=campos)
            escritor.writeheader()
            for fila in paginas:
                k = clave(fila)
                split = fila["split"]
                texto_nativo = indices[k]["texto_pagina"].strip()
                registro = {campo: fila[campo] for campo in CLAVE}
                registro.update({"split": split, "texto_pagina": texto_nativo,
                                 "estado": "texto_pdf" if texto_nativo else None,
                                 "idioma_ocr": "", "rotacion_ocr": "",
                                 "palabras_fiables": "", "confianza_media_fiable": ""})
                if not texto_nativo:
                    pdf = (fila["proyecto_id"], fila["documento"])
                    if pdf != pdf_anterior:
                        if documento_pdf is not None:
                            documento_pdf.close()
                        documento_pdf = pymupdf.open(stream=abrir_pdf(fila, raiz_pdfs, archivo_zip),
                                                      filetype="pdf")
                        pdf_anterior = pdf
                    indice_pagina = int(fila["pagina"]) - 1
                    if not 0 <= indice_pagina < len(documento_pdf):
                        raise ValueError(f"Página {fila['pagina']} inválida en {pdf}")
                    resultado = ocr_orientado(documento_pdf[indice_pagina], idioma, dpi)
                    registro.update({campo: resultado[campo] for campo in (
                        "estado", "rotacion_ocr", "palabras_fiables",
                        "confianza_media_fiable")})
                    registro["idioma_ocr"] = idioma
                    if resultado["estado"] == "ocr_con_texto":
                        registro["texto_pagina"] = resultado["texto_pagina"]
                escritor.writerow(registro)
                resumen[registro["estado"]] += 1
                por_split.setdefault(split, Counter())[registro["estado"]] += 1
                if sum(resumen.values()) % 25 == 0:
                    print(f"{sum(resumen.values())}/{len(paginas)} páginas, "
                          f"OCR recuperado: {resumen['ocr_con_texto']}", flush=True)
    finally:
        if documento_pdf is not None:
            documento_pdf.close()
        if archivo_zip is not None:
            archivo_zip.close()
    return {"paginas": len(paginas), "idioma_ocr": idioma, "dpi": dpi,
            "estados": dict(resumen),
            "estados_por_split": {split: dict(c) for split, c in por_split.items()}}


def main() -> None:
    raiz = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=raiz / "Data")
    parser.add_argument("--pdf-root", type=Path, default=raiz / "backend/data/dataset_exp02")
    parser.add_argument("--zip", type=Path, help="ZIP original, útil si aún no extrajiste los PDF")
    parser.add_argument("--salida", type=Path,
                        default=raiz / "Data/EXP_09_auditoria/EXP09_TEXTO_HIBRIDO.csv")
    parser.add_argument("--idioma", help="Idioma(s) instalados de Tesseract: spa+eng, spa o eng")
    parser.add_argument("--dpi", type=int, default=150)
    argumentos = parser.parse_args()
    idioma = idioma_disponible(argumentos.idioma)
    resumen = generar(argumentos.data_dir, argumentos.pdf_root, argumentos.salida,
                      idioma, argumentos.dpi, argumentos.zip)
    ruta_resumen = argumentos.salida.with_suffix(".resumen.json")
    ruta_resumen.write_text(json.dumps(resumen, indent=2, ensure_ascii=False),
                           encoding="utf-8")
    print(f"Texto: {argumentos.salida}\nResumen: {ruta_resumen}")


if __name__ == "__main__":
    main()

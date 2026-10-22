"""Extrae texto nativo y OCR para las páginas de EXP17."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory

import fitz


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
EXP17_DIR = PROJECT_DIR / "Data" / "EXP17_dataset_integrado"
MANIFEST = EXP17_DIR / "EXP17_DATASET.jsonl"
TEXT_CACHE = EXP17_DIR / "EXP17_TEXT_CACHE.csv"
ROOTS = {
    "EXP02": BACKEND_DIR / "data" / "dataset_exp02",
    "EXP11": BACKEND_DIR / "data" / "dataset_exp11",
    "EXP16": BACKEND_DIR / "data" / "dataset_exp16",
}
FIELDS = ["registro_id", "dataset_origen", "proyecto_id", "documento", "pagina", "split", "requiere_ocr", "metodo_extraccion", "caracteres_texto_nativo", "caracteres_texto_ocr", "texto_nativo", "texto_ocr", "texto_combinado", "error_extraccion"]


def _clean_text(value):
    value = value.replace("\x00", " ")
    value = re.sub(r"[ \t\f\v]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _load_manifest(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_cache(path):
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return {row["registro_id"]: row for row in csv.DictReader(stream) if row.get("registro_id")}


def _write_cache(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader(); writer.writerows(rows)
    temporary.replace(path)


def _ocr(page, dpi):
    with TemporaryDirectory(prefix="exp17_ocr_") as temporary:
        image = Path(temporary) / "pagina.png"
        page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY, alpha=False).save(image)
        process = subprocess.run(
            ["tesseract", str(image), "stdout", "-l", "eng", "--psm", "11"],
            capture_output=True, text=True, check=False, timeout=90,
            env={**os.environ, "OMP_THREAD_LIMIT": "1"},
        )
        if process.returncode:
            raise RuntimeError(process.stderr.strip() or "Tesseract terminó con error.")
        return _clean_text(process.stdout)


def _extract(row, dpi):
    path = ROOTS[row["dataset_origen"]] / row["ruta_relativa"]
    native = ocr = error = ""
    methods = []
    try:
        if not path.is_file():
            raise FileNotFoundError(path)
        with fitz.open(path) as document:
            page = document[int(row["pagina"]) - 1]
            native = _clean_text(page.get_text("text"))
            if native:
                methods.append("texto_nativo")
            if bool(row.get("requiere_ocr")) or len(native) < 40:
                ocr = _ocr(page, dpi)
                if ocr:
                    methods.append("ocr_tesseract")
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    combined = _clean_text("\n".join(part for part in (native, ocr) if part))
    return {
        "registro_id": row["registro_id"], "dataset_origen": row["dataset_origen"],
        "proyecto_id": row["proyecto_id"], "documento": row["documento"],
        "pagina": row["pagina"], "split": row["split"],
        "requiere_ocr": bool(row.get("requiere_ocr")),
        "metodo_extraccion": "+".join(methods) or "sin_texto",
        "caracteres_texto_nativo": len(native), "caracteres_texto_ocr": len(ocr),
        "texto_nativo": native, "texto_ocr": ocr, "texto_combinado": combined,
        "error_extraccion": error,
    }


def build(*, manifest=MANIFEST, output=TEXT_CACHE, dpi=160, workers=6, rebuild=False):
    records = _load_manifest(manifest)
    cached = {} if rebuild else _load_cache(output)
    pending = [row for row in records if row["registro_id"] not in cached]
    if any(row.get("requiere_ocr") for row in pending) and shutil.which("tesseract") is None:
        raise RuntimeError("Tesseract no está instalado o no está en PATH.")
    completed = dict(cached)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [executor.submit(_extract, row, dpi) for row in pending]
        for index, future in enumerate(as_completed(futures), 1):
            result = future.result(); completed[result["registro_id"]] = result
            if index % 25 == 0:
                _write_cache(output, [completed[row["registro_id"]] for row in records if row["registro_id"] in completed])
    ordered = [completed[row["registro_id"]] for row in records]
    _write_cache(output, ordered)
    return {
        "registros_manifiesto": len(records), "registros_reutilizados_cache": len(cached),
        "registros_extraidos": len(pending),
        "registros_con_error": sum(bool(row["error_extraccion"]) for row in ordered),
        "registros_sin_texto": sum(not row["texto_combinado"] for row in ordered),
        "paginas_con_ocr": sum("ocr_tesseract" in row["metodo_extraccion"] for row in ordered),
        "salida": str(output),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifiesto", type=Path, default=MANIFEST)
    parser.add_argument("--salida", type=Path, default=TEXT_CACHE)
    parser.add_argument("--dpi", type=int, default=160)
    parser.add_argument("--trabajadores", type=int, default=max(1, min(6, os.cpu_count() or 1)))
    parser.add_argument("--rehacer", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(manifest=args.manifiesto, output=args.salida, dpi=args.dpi, workers=args.trabajadores, rebuild=args.rehacer), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

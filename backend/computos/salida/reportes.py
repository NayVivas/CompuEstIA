"""Escritura de resultados en JSON y CSV."""

import csv
from decimal import Decimal
import json
from pathlib import Path


def _serializar(valor):
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, set):
        return sorted(valor)
    raise TypeError(f"No se puede serializar {type(valor).__name__}.")


def guardar_json(datos, ruta: Path):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(
        json.dumps(datos, ensure_ascii=False, indent=4, default=_serializar),
        encoding="utf-8",
    )


def guardar_csv(filas, ruta: Path):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if not filas:
        ruta.write_text("", encoding="utf-8")
        return
    columnas = list(filas[0].keys())
    with ruta.open("w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(filas)

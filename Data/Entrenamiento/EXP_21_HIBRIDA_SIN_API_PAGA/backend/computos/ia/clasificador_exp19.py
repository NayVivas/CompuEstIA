"""Clasificador local de documentos basado en los artefactos de EXP19."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from threading import Lock
from typing import Any

import joblib
import numpy as np
import pymupdf


OBJETIVOS = (
    "disciplinas",
    "roles_documentales",
    "contenidos",
)

LIMITE_CARACTERES_TEXTO = 1_000_000


class ModelosExp19NoDisponibles(RuntimeError):
    """Los artefactos locales no existen o no pueden cargarse."""


def ruta_modelos_predeterminada() -> Path:
    """Resuelve la carpeta de modelos sin depender del directorio actual."""

    configurada = os.getenv(
        "COMPUTOESTIA_EXP19_DIR",
        "",
    ).strip()

    if configurada:
        return Path(configurada).expanduser().resolve()

    backend = Path(__file__).resolve().parents[2]
    return backend / "data" / "modelos" / "exp19"


def extraer_texto_nativo_pdf(ruta_pdf: Path) -> tuple[str, dict]:
    """Extrae texto nativo por página para alimentar el modelo local."""

    ruta_pdf = Path(ruta_pdf)

    if not ruta_pdf.is_file():
        raise FileNotFoundError(ruta_pdf)
    if ruta_pdf.suffix.casefold() != ".pdf":
        raise ValueError("EXP19 solo admite archivos PDF.")

    textos = []
    paginas_con_texto = 0

    with pymupdf.open(ruta_pdf) as documento:
        cantidad_paginas = len(documento)

        for numero, pagina in enumerate(documento, start=1):
            texto = pagina.get_text("text", sort=True).strip()
            if texto:
                paginas_con_texto += 1

            textos.append(
                f"\n--- PAGINA {numero} ---\n{texto}"
            )

    texto_completo = "".join(textos).strip()
    fue_truncado = len(texto_completo) > LIMITE_CARACTERES_TEXTO

    if fue_truncado:
        texto_completo = texto_completo[:LIMITE_CARACTERES_TEXTO]

    return texto_completo, {
        "cantidad_paginas": cantidad_paginas,
        "paginas_con_texto_nativo": paginas_con_texto,
        "cantidad_caracteres": len(texto_completo),
        "texto_truncado": fue_truncado,
    }


class ClasificadorExp19:
    """Carga una vez los modelos y aplica sus umbrales congelados."""

    def __init__(self, ruta_modelos: Path | None = None) -> None:
        self.ruta_modelos = Path(
            ruta_modelos or ruta_modelos_predeterminada()
        )
        self._bloqueo = Lock()
        self._cargado = False
        self._vectorizador = None
        self._modelos: dict[str, Any] = {}
        self._binarizadores: dict[str, Any] = {}
        self._umbrales: dict[str, dict[str, float]] = {}
        self._configuracion: dict = {}

    def _archivo(self, nombre: str) -> Path:
        ruta = self.ruta_modelos / nombre
        if not ruta.is_file():
            raise ModelosExp19NoDisponibles(
                f"Falta el artefacto de EXP19: {ruta}"
            )
        return ruta

    def _cargar(self) -> None:
        if self._cargado:
            return

        with self._bloqueo:
            if self._cargado:
                return

            try:
                self._vectorizador = joblib.load(
                    self._archivo("EXP19_TFIDF_HIBRIDO.joblib")
                )

                for objetivo in OBJETIVOS:
                    self._modelos[objetivo] = joblib.load(
                        self._archivo(
                            f"EXP19_{objetivo}_MODELO.joblib"
                        )
                    )
                    self._binarizadores[objetivo] = joblib.load(
                        self._archivo(
                            f"EXP19_{objetivo}_BINARIZADOR.joblib"
                        )
                    )

                self._configuracion = json.loads(
                    self._archivo("EXP19_CONFIG.json").read_text(
                        encoding="utf-8"
                    )
                )

                umbrales = {objetivo: {} for objetivo in OBJETIVOS}
                with self._archivo(
                    "EXP19_UMBRALES_POR_ETIQUETA.csv"
                ).open(
                    "r",
                    encoding="utf-8-sig",
                    newline="",
                ) as archivo:
                    for fila in csv.DictReader(archivo):
                        objetivo = fila["target"]
                        if objetivo in umbrales:
                            umbrales[objetivo][fila["label"]] = float(
                                fila["threshold"]
                            )

                self._umbrales = umbrales
            except ModelosExp19NoDisponibles:
                raise
            except Exception as error:
                raise ModelosExp19NoDisponibles(
                    "No se pudieron cargar los artefactos locales de EXP19."
                ) from error

            self._cargado = True

    def _puntajes(self, objetivo: str, matriz) -> np.ndarray:
        configuracion = self._configuracion[
            "configuracion_seleccionada"
        ][objetivo]
        modelo = self._modelos[objetivo]

        if configuracion["score_kind"] == "probability":
            puntajes = modelo.predict_proba(matriz)
        else:
            puntajes = modelo.decision_function(matriz)

        puntajes = np.asarray(puntajes, dtype=float)
        if puntajes.ndim == 1:
            puntajes = puntajes.reshape(1, -1)
        return puntajes[0]

    def clasificar_texto(self, texto: str) -> dict:
        """Clasifica sin convertir márgenes SVC en probabilidades falsas."""

        texto = str(texto or "").strip()
        if not texto:
            return {
                "estado": "sin_texto_nativo",
                "modelo": "EXP19",
                "objetivos": {
                    objetivo: {
                        "etiquetas": [],
                        "detalle": [],
                    }
                    for objetivo in OBJETIVOS
                },
                "compatible_computo_estructural": False,
                "requiere_revision": True,
                "advertencias": [
                    "El PDF no contiene texto nativo utilizable por EXP19."
                ],
            }

        self._cargar()
        matriz = self._vectorizador.transform([texto])
        objetivos = {}

        for objetivo in OBJETIVOS:
            clases = [
                str(clase)
                for clase in self._binarizadores[objetivo].classes_
            ]
            puntajes = self._puntajes(objetivo, matriz)
            global_threshold = float(
                self._configuracion["configuracion_seleccionada"][
                    objetivo
                ]["global_threshold"]
            )

            detalle = []
            for indice, etiqueta in enumerate(clases):
                umbral = self._umbrales[objetivo].get(
                    etiqueta,
                    global_threshold,
                )
                puntaje = float(puntajes[indice])
                detalle.append(
                    {
                        "etiqueta": etiqueta,
                        "puntaje": round(puntaje, 6),
                        "umbral": round(float(umbral), 6),
                        "margen": round(puntaje - float(umbral), 6),
                        "seleccionada": puntaje >= float(umbral),
                    }
                )

            detalle.sort(
                key=lambda item: item["margen"],
                reverse=True,
            )
            objetivos[objetivo] = {
                "etiquetas": [
                    item["etiqueta"]
                    for item in detalle
                    if item["seleccionada"]
                ],
                "detalle": detalle,
                "tipo_puntaje": self._configuracion[
                    "configuracion_seleccionada"
                ][objetivo]["score_kind"],
            }

        disciplinas = set(
            objetivos["disciplinas"]["etiquetas"]
        )
        contenidos = set(
            objetivos["contenidos"]["etiquetas"]
        )
        contenidos_estructurales = {
            "armaduras_acero",
            "columnas_pilares",
            "elementos_estructurales_generales",
            "fundaciones",
            "losas_forjados",
            "muros_estructurales",
            "vigas",
        }

        compatible = bool(
            "estructura" in disciplinas
            and contenidos.intersection(contenidos_estructurales)
        )
        advertencias = []
        if "estructura" not in disciplinas:
            advertencias.append(
                "EXP19 no seleccionó la disciplina estructura."
            )
        if not contenidos.intersection(contenidos_estructurales):
            advertencias.append(
                "EXP19 no seleccionó contenido estructural computable."
            )

        return {
            "estado": "clasificado",
            "modelo": "EXP19",
            "objetivos": objetivos,
            "compatible_computo_estructural": compatible,
            "requiere_revision": not compatible,
            "advertencias": advertencias,
            "nota_puntajes": (
                "Los puntajes son márgenes del clasificador respecto de "
                "umbrales calibrados; no son probabilidades."
            ),
        }

    def clasificar_pdf(self, ruta_pdf: Path) -> dict:
        texto, metadatos = extraer_texto_nativo_pdf(ruta_pdf)
        resultado = self.clasificar_texto(texto)
        resultado.update(
            {
                "archivo": Path(ruta_pdf).name,
                "metadatos_pdf": metadatos,
            }
        )
        if metadatos["texto_truncado"]:
            resultado["advertencias"].append(
                "El texto fue truncado al límite admitido por el clasificador."
            )
            resultado["requiere_revision"] = True
        return resultado


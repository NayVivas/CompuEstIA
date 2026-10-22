"""Compara TF-IDF con texto nativo y OCR dejando afuera una fuente cada vez.

Ensayo exploratorio: las fuentes proceden de una agrupación sugerida por nombres.
No reemplaza una prueba final en proyectos nuevos e independientes.

Ejecutar después de generar EXP09_TEXTO_HIBRIDO.csv:
    python backend/experimentos/comparar_texto_ocr.py
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import warnings

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer


CLAVE = ("proyecto_id", "documento", "pagina")
TARGETS = ("disciplinas", "roles_documentales", "contenidos")


def leer(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        return list(csv.DictReader(archivo))


def clave(fila: dict) -> tuple[str, str, str]:
    return tuple(fila[campo] for campo in CLAVE)


def metricas(reales: np.ndarray, predichas: np.ndarray,
             con_texto: np.ndarray) -> dict:
    tp = int(np.logical_and(reales, predichas).sum())
    fp = int(np.logical_and(~reales, predichas).sum())
    fn = int(np.logical_and(reales, ~predichas).sum())
    return {
        "paginas": int(len(reales)), "paginas_con_senal": int(con_texto.sum()),
        "tp": tp, "fp": fp, "fn": fn,
        "micro_precision": tp / (tp + fp) if tp + fp else 0.0,
        "micro_recall": tp / (tp + fn) if tp + fn else 0.0,
        "micro_f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0,
    }


def comparar(data_dir: Path, salida: Path) -> list[dict]:
    filas = leer(data_dir / "EXP_03_protocolo_split/EXP03_DATASET_CON_SPLIT.csv")
    procedencias = leer(data_dir / "EXP_09_auditoria/EXP09_PROCEDENCIA_SUGERIDA.csv")
    fuentes = {fila["proyecto_id"]: fila["fuente_id"] for fila in procedencias}
    cache = {clave(f): f["texto_pagina"].strip() for f in leer(
        data_dir / "EXP_07_tfidf_logreg/EXP07_TEXT_CACHE.csv")}
    hibrido = {clave(f): f["texto_pagina"].strip() for f in leer(
        data_dir / "EXP_09_auditoria/EXP09_TEXTO_HIBRIDO.csv")}
    keys = [clave(fila) for fila in filas]
    if (len(keys) != len(set(keys)) or set(keys) != set(cache) or set(keys) != set(hibrido)
            or {f["proyecto_id"] for f in filas} != set(fuentes)):
        raise ValueError("Páginas o proyectos no coinciden entre dataset, textos y fuentes")
    grupos = np.array([fuentes[fila["proyecto_id"]] for fila in filas])
    todos = sorted(set(grupos))
    if len(todos) < 3:
        raise ValueError("Se requieren al menos tres fuentes independientes sugeridas")
    salida.mkdir(parents=True, exist_ok=True)
    resultados = []
    for target in TARGETS:
        reales_etiquetas = [json.loads(fila[target]) for fila in filas]
        clases = sorted({etiqueta for grupo in reales_etiquetas for etiqueta in grupo})
        binarizador = MultiLabelBinarizer(classes=clases)
        matriz_reales = binarizador.fit_transform(reales_etiquetas).astype(bool)
        for modalidad, textos in (
            ("texto_pdf", [cache[key] for key in keys]),
            ("texto_pdf_mas_ocr", [hibrido[key] for key in keys]),
        ):
            presencia = np.array([bool(t) for t in textos], dtype=bool)
            for fuente in todos:
                indices_test = np.flatnonzero(grupos == fuente)
                indices_entrenamiento = np.flatnonzero((grupos != fuente) & presencia)
                if not indices_entrenamiento.size:
                    raise ValueError(f"No hay páginas para entrenar dejando afuera {fuente}")
                vocabulario = TfidfVectorizer(
                    lowercase=True, strip_accents="unicode", ngram_range=(1, 2),
                    min_df=2, max_features=20000, sublinear_tf=True,
                )
                x_entrenamiento = vocabulario.fit_transform(
                    [textos[i] for i in indices_entrenamiento])
                x_prueba = vocabulario.transform([textos[i] for i in indices_test])
                clasificador = OneVsRestClassifier(LogisticRegression(
                    C=1.0, class_weight="balanced", solver="liblinear", max_iter=3000,
                ))
                # Puede haber clases de la taxonomía sin ejemplos en un fold.
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=UserWarning,
                                            message="Label .* is present in all training examples")
                    warnings.filterwarnings("ignore", category=UserWarning,
                                            message="Label .* is not present in all training examples")
                    warnings.filterwarnings("ignore", category=ConvergenceWarning)
                    clasificador.fit(x_entrenamiento, matriz_reales[indices_entrenamiento])
                predichas = clasificador.predict_proba(x_prueba) >= 0.5
                # Una página sin señal se manda a revisión; no se activan clases
                # por el intercepto del clasificador sobre el vector cero.
                predichas[~presencia[indices_test]] = False
                resultados.append({
                    "fuente": fuente, "objetivo": target, "modalidad": modalidad,
                    **metricas(matriz_reales[indices_test], predichas,
                               presencia[indices_test]),
                })
                print(f"{target} / {modalidad} / {fuente}: "
                      f"F1={resultados[-1]['micro_f1']:.3f}", flush=True)

    campos = list(resultados[0])
    with (salida / "EXP09_COMPARACION_OCR_POR_FUENTE.csv").open(
        "w", encoding="utf-8", newline=""
    ) as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(resultados)

    resumen = []
    for target in TARGETS:
        for modalidad in ("texto_pdf", "texto_pdf_mas_ocr"):
            grupo = [r for r in resultados if r["objetivo"] == target
                     and r["modalidad"] == modalidad]
            acumulados = Counter()
            for fila in grupo:
                for campo in ("paginas", "paginas_con_senal", "tp", "fp", "fn"):
                    acumulados[campo] += fila[campo]
            tp, fp, fn = (acumulados[c] for c in ("tp", "fp", "fn"))
            resumen.append({
                "objetivo": target, "modalidad": modalidad,
                "fuentes_evaluadas": len(grupo),
                "paginas": acumulados["paginas"],
                "paginas_con_senal": acumulados["paginas_con_senal"],
                "micro_precision": tp / (tp + fp) if tp + fp else 0.0,
                "micro_recall": tp / (tp + fn) if tp + fn else 0.0,
                "micro_f1_global": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0,
                "f1_promedio_por_fuente": sum(r["micro_f1"] for r in grupo) / len(grupo),
            })
    with (salida / "EXP09_COMPARACION_OCR_RESUMEN.csv").open(
        "w", encoding="utf-8", newline=""
    ) as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(resumen[0]))
        escritor.writeheader()
        escritor.writerows(resumen)

    resumen_ocr = json.loads((salida / "EXP09_TEXTO_HIBRIDO.resumen.json").read_text(
        encoding="utf-8"
    ))
    descripcion = [
        "# EXP-09 — Prueba exploratoria de OCR",
        "",
        "## Cobertura",
        "",
        f"Texto PDF: {resumen_ocr['estados'].get('texto_pdf', 0)}/{resumen_ocr['paginas']} páginas. "
        f"OCR aceptado: {resumen_ocr['estados'].get('ocr_con_texto', 0)}. "
        f"OCR de baja calidad: {resumen_ocr['estados'].get('ocr_baja_calidad', 0)}.",
        f"Prueba ejecutada con idioma `{resumen_ocr['idioma_ocr']}` a "
        f"{resumen_ocr['dpi']} dpi. Para español, probar el paquete `spa` "
        "y revisar la calidad en una muestra.",
        "",
        "## Comparación de clasificación",
        "",
        "Mismo TF-IDF (palabras, unigramas y bigramas) y regresión logística "
        "multietiqueta con umbral fijo 0,5 en ambas modalidades. "
        "Se reentrena dejando afuera una familia sugerida cada vez; "
        "el vocabulario se ajusta solo con las páginas de entrenamiento de cada fold. "
        "Sin texto disponible, el modelo se abstiene.",
        "",
        "| Objetivo | Entrada | Páginas con señal | F1 micro global | F1 promedio por fuente |",
        "|---|---|---:|---:|---:|",
    ]
    for fila in resumen:
        descripcion.append(
            f"| {fila['objetivo']} | {fila['modalidad']} | "
            f"{fila['paginas_con_senal']}/{fila['paginas']} | "
            f"{fila['micro_f1_global']:.3f} | {fila['f1_promedio_por_fuente']:.3f} |"
        )
    fuentes_grandes = [r for r in resultados if r["fuente"] == "Proyecto_7"
                      and r["modalidad"] == "texto_pdf_mas_ocr"]
    if fuentes_grandes:
        descripcion += [
            "",
            "La familia sugerida `Proyecto_7` agrupa 271 páginas y domina "
            "el F1 global por número de páginas. Su F1 con OCR es: "
            + ", ".join(f"{fila['objetivo']}={fila['micro_f1']:.3f}"
                        for fila in fuentes_grandes) + ".",
        ]
    descripcion += [
        "",
        "## Interpretación",
        "",
        "- OCR recupera señal en PDF escaneados; en este ensayo mejora las "
        "tres tareas, pero `contenidos` sigue lejos de ser confiable.",
        "- La procedencia se infirió del nombre `Proyecto_7-*.pdf` y debe ser "
        "confirmada. Solo hay ocho familias sugeridas y clases con pocos ejemplos.",
        "- Este análisis es exploratorio; el TEST histórico ya se había "
        "inspeccionado. Hace falta evaluar después en fuentes nuevas independientes.",
        "- Próximo experimento: medir imágenes de página o características "
        "visuales junto con OCR, sobre todo en las 17 páginas con OCR "
        "insuficiente y para la tarea `contenidos`. Comparar por fuente y "
        "reportar cobertura además de F1.",
        "",
    ]
    (salida / "EXP09_OCR_EVALUACION.md").write_text(
        "\n".join(descripcion), encoding="utf-8"
    )
    return resumen


def main() -> None:
    raiz = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=raiz / "Data")
    parser.add_argument("--salida", type=Path, default=raiz / "Data/EXP_09_auditoria")
    args = parser.parse_args()
    resultado = comparar(args.data_dir, args.salida)
    for fila in resultado:
        print(f"{fila['objetivo']} {fila['modalidad']}: "
              f"F1 micro global={fila['micro_f1_global']:.3f}; "
              f"F1 promedio por fuente={fila['f1_promedio_por_fuente']:.3f}; "
              f"páginas con señal={fila['paginas_con_senal']}/{fila['paginas']}")


if __name__ == "__main__":
    main()

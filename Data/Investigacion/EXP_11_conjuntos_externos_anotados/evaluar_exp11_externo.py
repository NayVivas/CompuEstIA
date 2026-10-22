"""Evalúa EXP-11 sin usar sus etiquetas para entrenar ni ajustar umbrales.

Ejemplo desde la raíz del proyecto::

    python backend/experimentos/evaluar_exp11_externo.py \
      --etiquetas EXP11_GROUND_TRUTH_EXPORTADO.json \
      --zip Data/EXP_11_nuevos_proyectos/Nuevos_Proyectos.zip

Reproduce los rasgos y los hiperparámetros de EXP-10; el entrenamiento usa
solamente el corpus anterior. No es el modelo desplegado en FastAPI.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import warnings
from zipfile import ZipFile

import numpy as np
import pymupdf
from scipy.sparse import csr_matrix, hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer, StandardScaler, normalize

from exp10_comparar_vision import rasgos_pagina


TARGETS = ("disciplinas", "roles_documentales", "contenidos")
RAIZ = Path(__file__).resolve().parents[2]


def leer_csv(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        return list(csv.DictReader(archivo))


def clave(r: dict) -> tuple:
    return (r["proyecto_id"], r["documento"], str(r["pagina"]))


def cargar_datos(data_dir: Path, etiquetas: Path) -> tuple[list[dict], list[str], np.ndarray, list[dict]]:
    antiguos = leer_csv(data_dir / "EXP_03_protocolo_split/EXP03_DATASET_CON_SPLIT.csv")
    textos = {clave(fila): fila["texto_pagina"] for fila in leer_csv(
        data_dir / "EXP_07_tfidf_logreg/EXP07_TEXT_CACHE.csv"
    )}
    claves = [clave(fila) for fila in antiguos]
    if len(claves) != len(set(claves)) or set(claves) != set(textos):
        raise ValueError("El inventario antiguo y su caché de texto no coinciden")
    with np.load(data_dir / "EXP_10_vision/EXP10_RASGOS_VISUALES.npz", allow_pickle=False) as archivo:
        if list(archivo["claves"]) != ["|".join(k) for k in claves]:
            raise ValueError("La caché visual antigua no corresponde al inventario")
        visual = archivo["rasgos"].copy()
    if visual.shape != (len(antiguos), 419):
        raise ValueError("Forma inesperada de rasgos visuales antiguos")
    nuevos = json.loads(etiquetas.read_text(encoding="utf-8-sig"))["filas"]
    ids = [(r["archivo"], int(r["pagina"])) for r in nuevos]
    if len(ids) != len(set(ids)):
        raise ValueError("Hay páginas duplicadas en la exportación de EXP-11")
    if any(r["proyecto_id"] != r["archivo"].split("/", 1)[0] for r in nuevos):
        raise ValueError("La carpeta no coincide con el proyecto de la etiqueta")
    for r in nuevos:
        if r.get("decision") != "confirmada" or r.get("ambiguo") != "no":
            continue
        if any(not isinstance(r.get(t), list) or not r[t] for t in TARGETS):
            raise ValueError(f"Faltan etiquetas confirmadas: {r['archivo']}")
    return antiguos, [textos[k] for k in claves], visual, nuevos


def escoger_paginas(nuevos: list[dict]) -> tuple[list[dict], list[dict]]:
    por_imagen = defaultdict(list)
    for fila in nuevos:
        por_imagen[fila["huella_visual_256"]].append(fila)
    conflictos = []
    excluidos = set()
    for grupo in por_imagen.values():
        if len(grupo) <= 1:
            continue
        ids = [f"{p['archivo']}#pagina={p['pagina']}" for p in grupo]
        if any(group[t] != grupo[0][t] for group in grupo[1:] for t in TARGETS):
            conflictos.append({"paginas": ids,
                               "etiquetas": [{t: f[t] for t in TARGETS} for f in grupo]})
            excluidos.update(ids)
        else:
            excluidos.update(ids[1:])
    seleccion = [r for r in nuevos
                 if r.get("decision") == "confirmada" and r.get("ambiguo") == "no"
                 and r.get("incluir_en_metricas") is not False
                 and f"{r['archivo']}#pagina={r['pagina']}" not in excluidos]
    if not seleccion:
        raise ValueError("No hay páginas elegibles para evaluar")
    return seleccion, conflictos


def textos_e_imagenes(nuevos: list[dict], archivo_zip: Path) -> tuple[list[str], np.ndarray]:
    textos, imagenes = [], []
    with ZipFile(archivo_zip) as archivo:
        for fila in nuevos:
            with pymupdf.open(stream=archivo.read(fila["archivo"]), filetype="pdf") as pdf:
                pagina = pdf[int(fila["pagina"]) - 1]
                texto = pagina.get_text("text")
                textos.append(texto)
                imagenes.append(rasgos_pagina(pagina))
    return textos, np.stack(imagenes)


def metricas(y: np.ndarray, pred: np.ndarray) -> dict:
    tp = int(np.logical_and(y, pred).sum())
    fp = int(np.logical_and(~y, pred).sum())
    fn = int(np.logical_and(y, ~pred).sum())
    return {
        "tp": tp, "fp": fp, "fn": fn,
        "precision_micro": round(tp / (tp + fp), 4) if tp + fp else 0.0,
        "recall_micro": round(tp / (tp + fn), 4) if tp + fn else 0.0,
        "f1_micro": round(2 * tp / (2 * tp + fp + fn), 4) if 2 * tp + fp + fn else 0.0,
    }


def evaluar(data_dir: Path, etiquetas: Path, archivo_zip: Path, salida: Path) -> dict:
    antiguos, textos_antiguos, imagen_antigua, nuevos = cargar_datos(data_dir, etiquetas)
    seleccion, conflictos = escoger_paginas(nuevos)
    textos_nuevos, imagen_nueva = textos_e_imagenes(seleccion, archivo_zip)
    presencia_antigua = np.array([bool(t.strip()) for t in textos_antiguos])
    presencia_nueva = np.array([bool(t.strip()) for t in textos_nuevos])
    vectorizador = TfidfVectorizer(lowercase=True, strip_accents="unicode",
                                   ngram_range=(1, 2), min_df=2,
                                   max_features=20000, sublinear_tf=True)
    vectorizador.fit([t for t in textos_antiguos if t.strip()])
    train_text = vectorizador.transform(textos_antiguos)
    test_text = vectorizador.transform(textos_nuevos)
    escalador = StandardScaler()
    train_imagen = normalize(escalador.fit_transform(imagen_antigua))
    test_imagen = normalize(escalador.transform(imagen_nueva))
    modalidades = {
        "texto_pdf": (train_text, test_text),
        "imagen_sola": (csr_matrix(train_imagen), csr_matrix(test_imagen)),
        "texto_pdf_mas_imagen": (
            hstack((train_text, csr_matrix(train_imagen)), format="csr"),
            hstack((test_text, csr_matrix(test_imagen)), format="csr"),
        ),
    }
    fuentes = sorted({r["proyecto_id"] for r in seleccion})
    resultados = []
    predicciones = []
    por_clase = []
    for tarea in TARGETS:
        clases = sorted({clase for fila in antiguos for clase in json.loads(fila[tarea])})
        desconocidas = sorted({clase for fila in seleccion for clase in fila[tarea]} - set(clases))
        if desconocidas:
            raise ValueError(f"Etiquetas desconocidas para {tarea}: {desconocidas}")
        binarizador = MultiLabelBinarizer(classes=clases)
        y_antiguo = binarizador.fit_transform([json.loads(fila[tarea]) for fila in antiguos]).astype(bool)
        y_nuevo = binarizador.transform([fila[tarea] for fila in seleccion]).astype(bool)
        for nombre, (train, test) in modalidades.items():
            modelo = OneVsRestClassifier(LogisticRegression(
                C=1.0, class_weight="balanced", solver="liblinear", max_iter=3000,
                random_state=0,
            ))
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=UserWarning,
                                        message="Label .* is present in all training examples")
                modelo.fit(train, y_antiguo)
            probas = modelo.predict_proba(test)
            pred = probas >= 0.5
            if nombre == "texto_pdf":
                pred[~presencia_nueva] = False
            globales = metricas(y_nuevo, pred)
            subgrupos = []
            for fuente in fuentes:
                indices = [i for i, fila in enumerate(seleccion) if fila["proyecto_id"] == fuente]
                subgrupos.append({"fuente": fuente, "paginas": len(indices),
                                  **metricas(y_nuevo[indices], pred[indices])})
            resultados.append({
                "tarea": tarea, "modalidad": nombre, "paginas": len(seleccion),
                "paginas_con_texto_pdf": int(presencia_nueva.sum()),
                "f1_promedio_por_fuente": round(sum(f["f1_micro"] for f in subgrupos) / len(subgrupos), 4),
                **globales, "por_fuente": subgrupos,
            })
            for j, clase in enumerate(clases):
                soporte = int(y_nuevo[:, j].sum())
                if soporte:
                    por_clase.append({"tarea": tarea, "modalidad": nombre, "clase": clase,
                                      "soporte": soporte,
                                      **metricas(y_nuevo[:, j], pred[:, j])})
            for i, fila in enumerate(seleccion):
                esperadas = sorted(clases[j] for j in np.flatnonzero(y_nuevo[i]))
                obtenidas = sorted(clases[j] for j in np.flatnonzero(pred[i]))
                predicciones.append({
                    "archivo": fila["archivo"], "pagina": fila["pagina"],
                    "fuente": fila["proyecto_id"], "tarea": tarea,
                    "modalidad": nombre, "real": esperadas, "predicho": obtenidas,
                    "faltantes": sorted(set(esperadas) - set(obtenidas)),
                    "sobrantes": sorted(set(obtenidas) - set(esperadas)),
                    "tiene_texto_pdf": bool(presencia_nueva[i]),
                })
            print(tarea, nombre, 'F1 micro:', globales['f1_micro'], flush=True)

    salida.mkdir(parents=True, exist_ok=True)
    auditoria = {
        "dataset_antiguo_paginas": len(antiguos),
        "nuevas_paginas_exportadas": len(nuevos),
        "nuevas_paginas_evaluadas": len(seleccion),
        "excluidas_por_conflicto_duplicado": conflictos,
        "evidencias_profesionales_vacias": sum(not fila.get("evidencia_profesional") for fila in nuevos),
        "modalidad_texto": "texto nativo del PDF, sin OCR nuevo",
        "umbral_fijo": 0.5,
        "resultados": resultados,
        "por_clase": por_clase,
    }
    (salida / "EXP11_EVALUACION.json").write_text(
        json.dumps(auditoria, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (salida / "EXP11_PREDICCIONES.json").write_text(
        json.dumps(predicciones, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lineas = [
        "# EXP-11 — Primera evaluación en proyectos nuevos", "",
        f"Entrenamiento: {len(antiguos)} páginas del corpus anterior. "
        "Evaluación: datos nuevos, sin usarlos para ajustar el modelo ni el umbral.",
        f"Etiquetas exportadas: {len(nuevos)}; páginas evaluadas: {len(seleccion)}.",
        f"Conflictos en páginas visualmente idénticas: {len(conflictos)} grupos. "
        f"Evidencias profesionales vacías: {auditoria['evidencias_profesionales_vacias']}.",
        "Las fuentes nuevas son carpetas provisionales; aún hay que verificar que sean obras independientes.",
        "", "| Tarea | Entrada | F1 micro | F1 medio por carpeta | Páginas con texto PDF |",
        "|---|---|---:|---:|---:|",
    ]
    for fila in resultados:
        lineas.append(f"| {fila['tarea']} | {fila['modalidad']} | {fila['f1_micro']:.3f} | "
                      f"{fila['f1_promedio_por_fuente']:.3f} | "
                      f"{fila['paginas_con_texto_pdf']}/{fila['paginas']} |")
    lineas += ["", "## Observaciones", "",
               "- Se usa TF-IDF con texto PDF nativo, rasgos de imagen simples, regresión logística "
               "y umbral 0,5. No hay OCR nuevo en esta corrida: las páginas sin texto PDF "
               "aportan solo imagen en las modalidades visuales.",
               "- Esta medición es un diagnóstico experimental reproducible, no una métrica del "
               "clasificador desplegado en FastAPI. Su vocabulario y parámetros se ajustaron "
               "solo con el corpus anterior; los datos nuevos se usaron exclusivamente para evaluar.",
               "- Para evaluar la metodología anterior con OCR habría que generar OCR para las "
               "páginas nuevas con calidad comprobada y repetir el ensayo sin cambiar etiquetas ni umbral.",
               "- Revisar los conflictos y registrar evidencia profesional antes de presentar "
               "estas anotaciones como Ground Truth final.", ""]
    for conflicto in conflictos:
        lineas.append("- Conflicto de etiquetas, mismas imágenes a 256 px: "
                      + "; ".join(conflicto["paginas"]))
    lineas += ["", "## Clases con más errores · texto PDF más imagen", "",
               "Solo clases con cinco o más ejemplos evaluados; se muestran hasta "
               "cinco por tarea, ordenadas primero por F1 y luego por soporte.", "",
               "| Tarea | Clase | Páginas con la clase | F1 |", "|---|---|---:|---:|"]
    for tarea in TARGETS:
        deficientes = sorted(
            (fila for fila in por_clase if fila["tarea"] == tarea
             and fila["modalidad"] == "texto_pdf_mas_imagen" and fila["soporte"] >= 5),
            key=lambda fila: (fila["f1_micro"], -fila["soporte"], fila["clase"]),
        )[:5]
        for fila in deficientes:
            lineas.append(f"| {tarea} | {fila['clase']} | {fila['soporte']} | "
                          f"{fila['f1_micro']:.3f} |")
    lineas += ["", "## Resultados por carpeta · texto PDF más imagen", "",
               "| Carpeta | Disciplinas | Roles | Contenidos |",
               "|---|---:|---:|---:|"]
    res = {(r["tarea"], r["modalidad"]): r for r in resultados}
    for fuente in fuentes:
        valores = []
        for tarea in TARGETS:
            fila = next(f for f in res[(tarea, "texto_pdf_mas_imagen")]["por_fuente"]
                        if f["fuente"] == fuente)
            valores.append(f"{fila['f1_micro']:.3f}")
        lineas.append(f"| {fuente} | {' | '.join(valores)} |")
    (salida / "EXP11_EVALUACION.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return auditoria


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=RAIZ / "Data")
    parser.add_argument("--etiquetas", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--salida", type=Path, default=RAIZ / "Data/EXP_11_nuevos_proyectos")
    args = parser.parse_args()
    d = evaluar(args.data_dir, args.etiquetas, args.zip, args.salida)
    print(f"Páginas evaluadas: {d['nuevas_paginas_evaluadas']}")


if __name__ == "__main__":
    main()

"""Ensayo de rasgos visuales simples para clasificación de planos por página.

El vocabulario, escalador y regresión se ajustan solo en las fuentes de
entrenamiento de cada fold. La familia por nombre de PDF es provisional.

Ejemplo, desde la raíz del proyecto:
    python backend/experimentos/exp10_comparar_vision.py

Para usar los PDF directamente del ZIP proporcionado:
    python backend/experimentos/exp10_comparar_vision.py --zip ComputoEstIA.zip
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import warnings
from zipfile import ZipFile

import numpy as np
import pymupdf
from scipy.sparse import csr_matrix, hstack
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer, StandardScaler, normalize


CLAVE = ("proyecto_id", "documento", "pagina")
TARGETS = ("disciplinas", "roles_documentales", "contenidos")
LADO_IMAGEN = 160
PESO_VISUAL = 1.0  # Fijado antes de observar los resultados.


def leer_csv(ruta: Path) -> list[dict[str, str]]:
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        return list(csv.DictReader(archivo))


def clave_pagina(fila: dict) -> tuple[str, str, str]:
    return tuple(fila[campo] for campo in CLAVE)


def rasgos_pagina(pagina: pymupdf.Page) -> np.ndarray:
    """Densidad de tinta y bordes por celdas; no requiere pesos preentrenados."""
    ancho, alto = pagina.rect.width, pagina.rect.height
    if min(ancho, alto) <= 0:
        raise ValueError("Página PDF sin dimensiones válidas")
    # Reservar dos píxeles: PyMuPDF puede redondear hacia arriba el render.
    escala = (LADO_IMAGEN - 2) / max(ancho, alto)
    pix = pagina.get_pixmap(
        matrix=pymupdf.Matrix(escala, escala),
        colorspace=pymupdf.csRGB, alpha=False,
    )
    if pix.width > LADO_IMAGEN or pix.height > LADO_IMAGEN:
        raise ValueError(f"Render inesperado: {pix.width}×{pix.height}")
    rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, pix.n
    )[..., :3]
    gris = rgb.astype(np.float32).mean(axis=2) / 255.0
    lienzo = np.ones((LADO_IMAGEN, LADO_IMAGEN), dtype=np.float32)
    y0 = (LADO_IMAGEN - pix.height) // 2
    x0 = (LADO_IMAGEN - pix.width) // 2
    lienzo[y0:y0 + pix.height, x0:x0 + pix.width] = gris
    tinta = 1.0 - lienzo
    densidad_16 = tinta.reshape(16, 10, 16, 10).mean(axis=(1, 3)).ravel()
    # Promedios de contraste horizontal/vertical en una cuadrícula 8×8.
    diferencias_x = np.pad(np.abs(np.diff(lienzo, axis=1)), ((0, 0), (0, 1)))
    diferencias_y = np.pad(np.abs(np.diff(lienzo, axis=0)), ((0, 1), (0, 0)))
    bordes_x = diferencias_x.reshape(8, 20, 8, 20).mean(axis=(1, 3)).ravel()
    bordes_y = diferencias_y.reshape(8, 20, 8, 20).mean(axis=(1, 3)).ravel()
    # Densidad por franja: algunos planos concentran cuadros y rótulos en bordes.
    proyeccion_x = tinta.mean(axis=0).reshape(16, 10).mean(axis=1)
    proyeccion_y = tinta.mean(axis=1).reshape(16, 10).mean(axis=1)
    resumen = [float(tinta.mean()), float(tinta.std()), float(ancho / alto)]
    return np.concatenate((densidad_16, bordes_x, bordes_y, proyeccion_x,
                           proyeccion_y, resumen)).astype(np.float32)


def extraer_rasgos(filas: list[dict], pdf_root: Path,
                   archivo_zip: Path | None) -> np.ndarray:
    zip_abierto = ZipFile(archivo_zip) if archivo_zip else None
    documento = None
    ruta_actual = None
    rasgos = []
    try:
        for indice, fila in enumerate(filas, 1):
            proyecto, pdf = fila["proyecto_id"], fila["documento"]
            if Path(proyecto).name != proyecto or Path(pdf).name != pdf:
                raise ValueError("Inventario con ruta de documento inválida")
            ruta = f"{proyecto}/{pdf}"
            if ruta != ruta_actual:
                if documento is not None:
                    documento.close()
                contenido = (zip_abierto.read(
                    f"ComputoEstIA/backend/data/dataset_exp02/{ruta}"
                ) if zip_abierto else (pdf_root / ruta).read_bytes())
                documento = pymupdf.open(stream=contenido, filetype="pdf")
                ruta_actual = ruta
            numero = int(fila["pagina"]) - 1
            if not 0 <= numero < len(documento):
                raise ValueError(f"Página {fila['pagina']} fuera del PDF {ruta}")
            rasgos.append(rasgos_pagina(documento[numero]))
            if indice % 50 == 0:
                print(f"Rasgos visuales: {indice}/{len(filas)}", flush=True)
    finally:
        if documento is not None:
            documento.close()
        if zip_abierto is not None:
            zip_abierto.close()
    return np.stack(rasgos)


def resultado(reales: np.ndarray, predichas: np.ndarray,
              con_senal: np.ndarray) -> dict:
    tp = int(np.logical_and(reales, predichas).sum())
    fp = int(np.logical_and(~reales, predichas).sum())
    fn = int(np.logical_and(reales, ~predichas).sum())
    return {
        "paginas": len(reales), "paginas_con_senal": int(con_senal.sum()),
        "tp": tp, "fp": fp, "fn": fn,
        "precision_micro": tp / (tp + fp) if tp + fp else 0.0,
        "recall_micro": tp / (tp + fn) if tp + fn else 0.0,
        "f1_micro": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0,
    }


def evaluar(data_dir: Path, salida: Path, pdf_root: Path,
            archivo_zip: Path | None, reutilizar: bool = False) -> list[dict]:
    filas = leer_csv(data_dir / "EXP_03_protocolo_split/EXP03_DATASET_CON_SPLIT.csv")
    fuentes = {fila["proyecto_id"]: fila["fuente_id"] for fila in leer_csv(
        data_dir / "EXP_09_auditoria/EXP09_PROCEDENCIA_SUGERIDA.csv")}
    texto = {clave_pagina(f): f["texto_pagina"].strip() for f in leer_csv(
        data_dir / "EXP_09_auditoria/EXP09_TEXTO_HIBRIDO.csv")}
    claves = [clave_pagina(fila) for fila in filas]
    if (len(claves) != len(set(claves)) or set(claves) != set(texto)
            or set(fuentes) != {f["proyecto_id"] for f in filas}):
        raise ValueError("Las páginas o fuentes no coinciden entre los archivos")

    salida.mkdir(parents=True, exist_ok=True)
    cache = salida / "EXP10_RASGOS_VISUALES.npz"
    if reutilizar:
        with np.load(cache, allow_pickle=False) as guardado:
            if list(guardado["claves"]) != ["|".join(k) for k in claves]:
                raise ValueError("La cache visual no corresponde a este inventario")
            visual = guardado["rasgos"]
    else:
        visual = extraer_rasgos(filas, pdf_root, archivo_zip)
        np.savez_compressed(cache, claves=np.array(["|".join(k) for k in claves]),
                            rasgos=visual)

    grupos = np.array([fuentes[f["proyecto_id"]] for f in filas])
    familias = sorted(set(grupos))
    if len(familias) < 3:
        raise ValueError("No hay fuentes suficientes para una validación por grupos")
    textos = [texto[k] for k in claves]
    tiene_texto = np.array([bool(t) for t in textos])
    tiene_imagen = np.linalg.norm(visual[:, :-1], axis=1) > 0
    if visual.shape != (len(filas), 419):
        raise ValueError("Dimensión de rasgos visuales inesperada")

    detalles = []
    for fuente in familias:
        train = np.flatnonzero(grupos != fuente)
        test = np.flatnonzero(grupos == fuente)
        vectorizador = TfidfVectorizer(lowercase=True, strip_accents="unicode",
                                      ngram_range=(1, 2), min_df=2,
                                      max_features=20000, sublinear_tf=True)
        # Conservar el mismo IDF que en el experimento OCR: las páginas vacías
        # no intervienen al ajustar el vocabulario, pero sí pueden aportar imagen.
        train_con_texto = train[tiene_texto[train]]
        if not train_con_texto.size:
            raise ValueError(f"No hay texto de entrenamiento al excluir {fuente}")
        vectorizador.fit([textos[i] for i in train_con_texto])
        x_train_texto = vectorizador.transform([textos[i] for i in train])
        x_test_texto = vectorizador.transform([textos[i] for i in test])
        escalador = StandardScaler()
        imagen_train = normalize(escalador.fit_transform(visual[train]))
        imagen_test = normalize(escalador.transform(visual[test]))
        x_train = {
            "solo_imagen": csr_matrix(imagen_train),
            "ocr_mas_imagen": hstack((x_train_texto,
                                      csr_matrix(PESO_VISUAL * imagen_train)), format="csr"),
        }
        x_test = {
            "solo_imagen": csr_matrix(imagen_test),
            "ocr_mas_imagen": hstack((x_test_texto,
                                     csr_matrix(PESO_VISUAL * imagen_test)), format="csr"),
        }
        for objetivo in TARGETS:
            reales = [json.loads(fila[objetivo]) for fila in filas]
            etiquetas = sorted({v for grupo in reales for v in grupo})
            y = MultiLabelBinarizer(classes=etiquetas).fit_transform(reales).astype(bool)
            for modalidad in x_train:
                clasificador = OneVsRestClassifier(LogisticRegression(
                    C=1.0, class_weight="balanced", solver="liblinear",
                    max_iter=3000,
                ))
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=UserWarning,
                                            message="Label .* is present in all training examples")
                    warnings.filterwarnings("ignore", category=UserWarning,
                                            message="Label .* is not present in all training examples")
                    warnings.filterwarnings("ignore", category=ConvergenceWarning)
                    clasificador.fit(x_train[modalidad], y[train])
                predichas = clasificador.predict_proba(x_test[modalidad]) >= 0.5
                senal = tiene_imagen[test] if modalidad == "solo_imagen" else (
                    tiene_imagen[test] | tiene_texto[test])
                predichas[~senal] = False
                detalles.append({"fuente": fuente, "objetivo": objetivo,
                                 "modalidad": modalidad,
                                 **resultado(y[test], predichas, senal)})
                print(f"{fuente} / {objetivo} / {modalidad}: "
                      f"F1={detalles[-1]['f1_micro']:.3f}", flush=True)

    with (salida / "EXP10_COMPARACION_POR_FUENTE.csv").open(
        "w", encoding="utf-8", newline=""
    ) as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(detalles[0]))
        escritor.writeheader()
        escritor.writerows(detalles)

    anteriores = leer_csv(data_dir / "EXP_09_auditoria/EXP09_COMPARACION_OCR_POR_FUENTE.csv")
    resumen = []
    for objetivo in TARGETS:
        for modalidad, filas_fuente in (
            ("ocr_solo", [x for x in anteriores if x["objetivo"] == objetivo
                          and x["modalidad"] == "texto_pdf_mas_ocr"]),
            ("solo_imagen", [x for x in detalles if x["objetivo"] == objetivo
                             and x["modalidad"] == "solo_imagen"]),
            ("ocr_mas_imagen", [x for x in detalles if x["objetivo"] == objetivo
                                and x["modalidad"] == "ocr_mas_imagen"]),
        ):
            if {x["fuente"] for x in filas_fuente} != set(familias):
                raise ValueError("Las fuentes no coinciden con el ensayo OCR anterior")
            total = Counter()
            for fila in filas_fuente:
                for campo in ("paginas", "paginas_con_senal", "tp", "fp", "fn"):
                    total[campo] += int(fila[campo])
            tp, fp, fn = (total[campo] for campo in ("tp", "fp", "fn"))
            resumen.append({
                "objetivo": objetivo, "modalidad": modalidad,
                "fuentes": len(familias), "paginas": total["paginas"],
                "paginas_con_senal": total["paginas_con_senal"],
                "precision_micro": tp / (tp + fp) if tp + fp else 0.0,
                "recall_micro": tp / (tp + fn) if tp + fn else 0.0,
                "f1_micro_global": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0,
                "f1_promedio_por_fuente": sum(float(
                    f["f1_micro"] if "f1_micro" in f else f["micro_f1"]
                ) for f in filas_fuente) / len(filas_fuente),
            })
    with (salida / "EXP10_COMPARACION_RESUMEN.csv").open(
        "w", encoding="utf-8", newline=""
    ) as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(resumen[0]))
        escritor.writeheader()
        escritor.writerows(resumen)

    notas = [
        "# EXP-10 — Imagen de página y texto OCR",
        "",
        "Validación exploratoria dejando una de ocho fuentes sugeridas afuera "
        "en cada evaluación. Las fuentes se infieren por nombres de PDF y "
        "requieren confirmación. Se usa siempre el mismo umbral fijo 0,5. "
        "El TEST histórico ya se había inspeccionado: este ensayo no es una "
        "prueba final independiente.",
        "",
        "Visualización: render PDF reducido a 160 píxeles en el lado mayor; "
        "densidad de tinta y bordes por cuadrícula. El escalador y TF-IDF "
        "se ajustan exclusivamente sobre las otras fuentes. La imagen no "
        "requiere OCR ni un modelo de visión preentrenado.",
        "",
        "| Objetivo | Entrada | Páginas con señal | F1 micro global | F1 promedio por fuente |",
        "|---|---|---:|---:|---:|",
    ]
    notas.extend(
        f"| {f['objetivo']} | {f['modalidad']} | {f['paginas_con_senal']}/{f['paginas']} "
        f"| {f['f1_micro_global']:.3f} | {f['f1_promedio_por_fuente']:.3f} |"
        for f in resumen
    )
    referencia = {r["objetivo"]: r for r in resumen if r["modalidad"] == "ocr_solo"}
    imagen = {r["objetivo"]: r for r in resumen if r["modalidad"] == "solo_imagen"}
    combinado = {r["objetivo"]: r for r in resumen if r["modalidad"] == "ocr_mas_imagen"}
    cambios_consistentes = [objetivo for objetivo in TARGETS if (
        combinado[objetivo]["f1_micro_global"] > referencia[objetivo]["f1_micro_global"]
        and combinado[objetivo]["f1_promedio_por_fuente"]
        > referencia[objetivo]["f1_promedio_por_fuente"]
    )]
    notas += ["", "## Lectura del resultado", ""]
    if cambios_consistentes:
        notas.append("La fusión mejora ambas métricas en: "
                     + ", ".join(cambios_consistentes) + ".")
    else:
        notas.append("La fusión no mejora simultáneamente el F1 global y "
                     "el F1 promedio por fuente en ninguna tarea.")
    if imagen["contenidos"]["f1_micro_global"] > referencia["contenidos"]["f1_micro_global"]:
        notas.append("Imagen sola mejora el F1 global de contenidos, de "
                     f"{referencia['contenidos']['f1_micro_global']:.3f} a "
                     f"{imagen['contenidos']['f1_micro_global']:.3f}; "
                     "revisar si la media por fuente confirma esa mejora.")
    notas += [
        "",
        "Las 271 páginas de la familia `Proyecto_7` pesan mucho en el F1 global. "
        "Revisar también las métricas por fuente antes de decidir si la "
        "imagen agrega información útil.",
        "Las páginas casi sin texto del catálogo incluyen cortes e isométricos "
        "con trazos reconocibles. Un resumen de densidad y bordes de 160 píxeles "
        "no identifica aún objetos específicos como columnas o armaduras.",
        "",
        "Estos resultados no acreditan generalización a proyectos nuevos. "
        "El experimento se diseñó después de inspeccionar resultados del "
        "TEST anterior y el dataset contiene muy pocas fuentes independientes. "
        "No habilitar automáticamente la fusión en el producto. Validar la "
        "procedencia de los planos y reunir nuevas obras antes de elegir modelo.",
        "",
    ]
    (salida / "EXP10_EVALUACION.md").write_text("\n".join(notas), encoding="utf-8")
    return resumen


def main() -> None:
    raiz = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=raiz / "Data")
    parser.add_argument("--pdf-root", type=Path, default=raiz / "backend/data/dataset_exp02")
    parser.add_argument("--zip", type=Path, help="Usar los PDF del archivo original")
    parser.add_argument("--salida", type=Path,
                        default=raiz / "Data/EXP_10_vision")
    parser.add_argument("--reutilizar", action="store_true",
                        help="Reutilizar rasgos visuales ya calculados")
    args = parser.parse_args()
    resumen = evaluar(args.data_dir, args.salida, args.pdf_root,
                      args.zip, args.reutilizar)
    for fila in resumen:
        print(f"{fila['objetivo']} {fila['modalidad']}: "
              f"F1={fila['f1_micro_global']:.3f}; "
              f"F1 por fuente={fila['f1_promedio_por_fuente']:.3f}")


if __name__ == "__main__":
    main()

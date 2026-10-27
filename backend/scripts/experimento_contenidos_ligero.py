r"""Experimentos ligeros para la etiqueta `contenidos` de EXP19.

Objetivo: comparar variantes de texto y modelos sin tocar TEST. El protocolo es:

  1. Entrenar con TRAIN.
  2. Calibrar umbrales por etiqueta con VALIDATION.
  3. Reportar métricas de VALIDATION.
  4. Elegir una sola variante y recién entonces evaluar TEST una vez.

Variantes incluidas:
  - baseline: texto combinado crudo + TF-IDF híbrido + LinearSVC(C=0.5).
  - limpio: elimina bloque de rótulos, números, cotas y referencias + mismo modelo.
  - balanceado: limpio + class_weight='balanced'.
  - palabras: limpio + solo TF-IDF de palabras (sin char n-grams).
  - lsa: limpio + TF-IDF de palabras + SVD(300) + LogisticRegression.

No instala FastText, LightGBM ni XGBoost. La comparación es reproducible con
scikit-learn, NumPy y SciPy, que ya están en el entorno.

Uso, desde backend:
  .\.venv\Scripts\python.exe scripts\experimento_contenidos_ligero.py --variante limpio
  .\.venv\Scripts\python.exe scripts\experimento_contenidos_ligero.py --variante todas
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_recall_curve
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.svm import LinearSVC


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from computos.ia.limpieza_contenidos import limpiar_texto  # noqa: E402

DATASET_DIR = (
    PROJECT_DIR
    / "Data"
    / "Investigacion"
    / "EXP17_EXP18_Dataset_TRAIN_VALIDATION_TEST"
    / "Data"
    / "EXP17_dataset_integrado"
)
MANIFEST = DATASET_DIR / "EXP17_DATASET.jsonl"
TEXT_CACHE = DATASET_DIR / "EXP17_TEXT_CACHE.csv"
OUTPUT_DIR = BACKEND_DIR / "data" / "experimentos" / "contenidos_ligero"
SEMILLA = 20261026


@dataclass(frozen=True)
class Pagina:
    registro_id: str
    proyecto_id: str
    grupo: str
    split: str
    texto: str
    etiquetas: tuple[str, ...]


def _cargar_paginas(split: str) -> list[Pagina]:
    with TEXT_CACHE.open("r", encoding="utf-8-sig", newline="") as stream:
        textos = {row["registro_id"]: row for row in csv.DictReader(stream)}

    paginas: list[Pagina] = []
    with MANIFEST.open("r", encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if not row.get("incluir_en_metricas", True):
                continue
            if row.get("split") != split:
                continue
            text_row = textos.get(row["registro_id"])
            if text_row is None:
                continue
            texto = (text_row.get("texto_combinado") or "").strip()
            if not texto:
                continue
            paginas.append(
                Pagina(
                    registro_id=row["registro_id"],
                    proyecto_id=row.get("proyecto_id", ""),
                    grupo=row.get("grupo_independencia", row.get("proyecto_id", "")),
                    split=row.get("split", ""),
                    texto=texto,
                    etiquetas=tuple(row.get("contenidos") or ()),
                )
            )
    if not paginas:
        raise ValueError(f"No hay páginas para split={split!r}")
    return paginas


# ---------------------------------------------------------------------------
# Limpieza de texto: se importa desde computos.ia.limpieza_contenidos para
# garantizar que train, validation y test usen exactamente la misma función.
# ---------------------------------------------------------------------------

VARIANTES_CON_LIMPIEZA = frozenset({"limpio", "balanceado", "palabras", "lsa"})


def _textos(paginas: Iterable[Pagina], variante: str) -> list[str]:
    if variante == "baseline":
        return [pagina.texto for pagina in paginas]
    if variante in VARIANTES_CON_LIMPIEZA:
        return [limpiar_texto(pagina.texto) for pagina in paginas]
    raise ValueError(f"Variante desconocida: {variante}")


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------


def _tfidf_hibrido(max_palabras: int = 30000, max_caracteres: int = 30000) -> FeatureUnion:
    return FeatureUnion(
        [
            (
                "palabras",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    max_features=max_palabras,
                    min_df=2,
                    sublinear_tf=True,
                    strip_accents="unicode",
                ),
            ),
            (
                "caracteres",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    max_features=max_caracteres,
                    min_df=2,
                    sublinear_tf=True,
                    strip_accents="unicode",
                ),
            ),
        ],
        transformer_weights={"palabras": 1.0, "caracteres": 0.7},
    )


def _tfidf_palabras(max_palabras: int = 40000) -> TfidfVectorizer:
    return TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=max_palabras,
        min_df=2,
        sublinear_tf=True,
        strip_accents="unicode",
    )


def construir_modelo(variante: str):
    if variante == "baseline":
        return Pipeline(
            [
                ("tfidf", _tfidf_hibrido()),
                (
                    "clf",
                    OneVsRestClassifier(
                        LinearSVC(C=0.5, random_state=SEMILLA),
                        n_jobs=1,
                    ),
                ),
            ]
        )
    if variante == "limpio":
        return Pipeline(
            [
                ("tfidf", _tfidf_hibrido()),
                (
                    "clf",
                    OneVsRestClassifier(
                        LinearSVC(C=0.5, random_state=SEMILLA),
                        n_jobs=1,
                    ),
                ),
            ]
        )
    if variante == "balanceado":
        return Pipeline(
            [
                ("tfidf", _tfidf_hibrido()),
                (
                    "clf",
                    OneVsRestClassifier(
                        LinearSVC(
                            C=0.5,
                            class_weight="balanced",
                            random_state=SEMILLA,
                        ),
                        n_jobs=1,
                    ),
                ),
            ]
        )
    if variante == "palabras":
        # Variante ganadora en VALIDATION (F1=0.6642): limpieza de texto,
        # TF-IDF solo de palabras y LinearSVC balanceado.
        return Pipeline(
            [
                ("tfidf", _tfidf_palabras()),
                (
                    "clf",
                    OneVsRestClassifier(
                        LinearSVC(
                            C=0.5,
                            class_weight="balanced",
                            random_state=SEMILLA,
                        ),
                        n_jobs=1,
                    ),
                ),
            ]
        )
    if variante == "lsa":
        return Pipeline(
            [
                ("tfidf", _tfidf_palabras()),
                ("svd", TruncatedSVD(n_components=300, random_state=SEMILLA)),
                (
                    "clf",
                    OneVsRestClassifier(
                        LogisticRegression(
                            C=1.0,
                            class_weight="balanced",
                            max_iter=2000,
                            solver="liblinear",
                            random_state=SEMILLA,
                        ),
                        n_jobs=1,
                    ),
                ),
            ]
        )
    raise ValueError(f"Variante desconocida: {variante}")


# ---------------------------------------------------------------------------
# Calibración y métricas
# ---------------------------------------------------------------------------


def _scores(modelo, textos: list[str]) -> np.ndarray:
    if hasattr(modelo, "decision_function"):
        scores = modelo.decision_function(textos)
    else:
        scores = modelo.predict_proba(textos)
    scores = np.asarray(scores, dtype=float)
    if scores.ndim == 1:
        scores = scores.reshape(-1, 1)
    return scores


def _umbral_global(y_true: np.ndarray, scores: np.ndarray) -> float:
    """Umbral único que maximiza micro-F1 en VALIDATION.

    Es la referencia a la que se encogen los umbrales por etiqueta. Evita que
    una etiqueta con poco soporte quede con un umbral demasiado permisivo.
    """

    candidatos = np.unique(np.quantile(scores, np.linspace(0.30, 0.995, 200)))
    mejor_f1 = -1.0
    mejor = float(np.median(scores))
    for candidato in candidatos:
        y_pred = (scores >= candidato).astype(int)
        f1 = float(f1_score(y_true, y_pred, average="micro", zero_division=0))
        if f1 > mejor_f1:
            mejor_f1 = f1
            mejor = float(candidato)
    return mejor


def calibrar_umbrales(
    y_true: np.ndarray,
    scores: np.ndarray,
    *,
    beta: float = 1.0,
    shrinkage: float = 5.0,
) -> tuple[np.ndarray, list[dict]]:
    """Umbral por etiqueta con encogimiento hacia un umbral global.

    `beta < 1` prioriza precisión; `beta > 1` prioriza recall. El encogimiento
    `support / (support + shrinkage)` hace que las etiquetas con poco soporte
    se queden cerca del umbral global. Si una etiqueta no tiene positivos en
    validation, se usa `inf` para no predecirla: no se inventa recall que no se
    puede medir.
    """

    beta2 = beta * beta
    umbral_global = _umbral_global(y_true, scores)

    umbrales = []
    detalle = []
    for index in range(y_true.shape[1]):
        support = int(y_true[:, index].sum())
        if support == 0:
            umbrales.append(float("inf"))
            detalle.append(
                {
                    "indice": index,
                    "support_validation": 0,
                    "umbral": None,
                    "fbeta_validation": 0.0,
                    "beta": beta,
                    "motivo": "sin_positivos_en_validation",
                }
            )
            continue
        precision, recall, thresholds = precision_recall_curve(
            y_true[:, index], scores[:, index]
        )
        fbeta = np.divide(
            (1 + beta2) * precision * recall,
            beta2 * precision + recall,
            out=np.zeros_like(precision),
            where=(beta2 * precision + recall) > 0,
        )
        best = int(np.nanargmax(fbeta))
        if best < len(thresholds):
            umbral_etiqueta = float(thresholds[best])
        else:
            umbral_etiqueta = float(np.min(scores[:, index]) - 1e-9)
        peso = support / (support + shrinkage)
        umbral = umbral_global + peso * (umbral_etiqueta - umbral_global)
        umbrales.append(umbral)
        detalle.append(
            {
                "indice": index,
                "support_validation": support,
                "umbral": umbral,
                "umbral_etiqueta_sin_encoger": umbral_etiqueta,
                "umbral_global": umbral_global,
                "peso_encogimiento": peso,
                "fbeta_validation": float(fbeta[best]),
                "beta": beta,
                "motivo": "fbeta_max_encogido",
            }
        )
    return np.asarray(umbrales, dtype=float), detalle


def _metricas(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    tp = int(np.sum(y_true & y_pred))
    fp = int(np.sum(~y_true & y_pred))
    fn = int(np.sum(y_true & ~y_pred))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "exact_match": float(np.mean(np.all(y_true == y_pred, axis=1))),
        "hamming_loss": float(np.mean(y_true != y_pred)),
        "cardinalidad_real": float(np.mean(y_true.sum(axis=1))),
        "cardinalidad_predicha": float(np.mean(y_pred.sum(axis=1))),
        "paginas": int(y_true.shape[0]),
    }


def _bootstrap_por_grupo(
    paginas: list[Pagina],
    y_true: np.ndarray,
    y_pred: np.ndarray,
    *,
    iterations: int = 1000,
    seed: int = SEMILLA,
) -> dict:
    rng = np.random.default_rng(seed)
    grupos = sorted({pagina.grupo for pagina in paginas})
    indices = {
        grupo: np.array([i for i, pagina in enumerate(paginas) if pagina.grupo == grupo])
        for grupo in grupos
    }
    valores = []
    for _ in range(iterations):
        muestra = rng.choice(grupos, size=len(grupos), replace=True)
        seleccion = np.concatenate([indices[grupo] for grupo in muestra])
        valores.append(_metricas(y_true[seleccion], y_pred[seleccion])["f1"])
    valores = np.asarray(valores)
    return {
        "iteraciones": iterations,
        "grupos": len(grupos),
        "f1_media": float(valores.mean()),
        "f1_ic95_inferior": float(np.quantile(valores, 0.025)),
        "f1_ic95_superior": float(np.quantile(valores, 0.975)),
    }


def _escribir_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def ejecutar_variante(
    variante: str,
    train: list[Pagina],
    validation: list[Pagina],
    *,
    beta: float = 1.0,
    shrinkage: float = 5.0,
) -> dict:
    binarizer = MultiLabelBinarizer()
    y_train = binarizer.fit_transform([pagina.etiquetas for pagina in train])
    y_validation = binarizer.transform([pagina.etiquetas for pagina in validation])
    clases = [str(clase) for clase in binarizer.classes_]

    modelo = construir_modelo(variante)
    modelo.fit(_textos(train, variante), y_train)
    scores = _scores(modelo, _textos(validation, variante))
    umbrales, detalle_umbrales = calibrar_umbrales(
        y_validation, scores, beta=beta, shrinkage=shrinkage
    )
    y_pred = (scores >= umbrales.reshape(1, -1)).astype(int)
    metricas = _metricas(y_validation, y_pred)
    bootstrap = _bootstrap_por_grupo(validation, y_validation, y_pred)

    etiquetas = []
    for index, clase in enumerate(clases):
        tp = int(np.sum(y_validation[:, index] & y_pred[:, index]))
        fp = int(np.sum(~y_validation[:, index].astype(bool) & y_pred[:, index].astype(bool)))
        fn = int(np.sum(y_validation[:, index].astype(bool) & ~y_pred[:, index].astype(bool)))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        etiquetas.append(
            {
                "etiqueta": clase,
                "support_validation": int(y_validation[:, index].sum()),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "umbral": detalle_umbrales[index]["umbral"],
            }
        )

    salida = OUTPUT_DIR / f"{variante}_b{beta:g}_s{shrinkage:g}"
    salida.mkdir(parents=True, exist_ok=True)
    _escribir_csv(
        salida / "por_etiqueta.csv",
        [
            "etiqueta", "support_validation", "tp", "fp", "fn", "precision",
            "recall", "f1", "umbral",
        ],
        etiquetas,
    )
    resumen = {
        "variante": variante,
        "beta_calibracion": beta,
        "shrinkage": shrinkage,
        "train_paginas": len(train),
        "validation_paginas": len(validation),
        "etiquetas": len(clases),
        "metricas_validation": metricas,
        "bootstrap_por_grupo": bootstrap,
        "umbrales": [
            {**detalle_umbrales[index], "etiqueta": clase}
            for index, clase in enumerate(clases)
        ],
    }
    (salida / "resumen.json").write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"{variante:12s} P={metricas['precision']:.4f} R={metricas['recall']:.4f} "
        f"F1={metricas['f1']:.4f} macroF1={metricas['macro_f1']:.4f} "
        f"card={metricas['cardinalidad_predicha']:.2f}/{metricas['cardinalidad_real']:.2f} "
        f"IC95=[{bootstrap['f1_ic95_inferior']:.4f},{bootstrap['f1_ic95_superior']:.4f}]"
    )
    return resumen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--variante",
        default="todas",
        choices=("baseline", "limpio", "balanceado", "palabras", "lsa", "todas"),
    )
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument(
        "--beta",
        type=float,
        default=1.0,
        help="Beta de calibración: <1 prioriza precisión, >1 prioriza recall.",
    )
    parser.add_argument(
        "--shrinkage",
        type=float,
        default=5.0,
        help="Encogimiento de umbrales por etiqueta hacia el umbral global.",
    )
    args = parser.parse_args(argv)

    train = _cargar_paginas("train")
    validation = _cargar_paginas("validation")
    variantes = (
        ["baseline", "limpio", "balanceado", "palabras", "lsa"]
        if args.variante == "todas"
        else [args.variante]
    )

    resumenes = []
    for variante in variantes:
        resumenes.append(
            ejecutar_variante(
                variante,
                train,
                validation,
                beta=args.beta,
                shrinkage=args.shrinkage,
            )
        )

    if len(resumenes) > 1:
        _escribir_csv(
            OUTPUT_DIR / f"comparacion_validation_b{args.beta:g}_s{args.shrinkage:g}.csv",
            [
                "variante", "precision", "recall", "f1", "macro_f1",
                "exact_match", "cardinalidad_real", "cardinalidad_predicha",
                "f1_ic95_inferior", "f1_ic95_superior",
            ],
            [
                {
                    "variante": resumen["variante"],
                    **resumen["metricas_validation"],
                    "f1_ic95_inferior": resumen["bootstrap_por_grupo"]["f1_ic95_inferior"],
                    "f1_ic95_superior": resumen["bootstrap_por_grupo"]["f1_ic95_superior"],
                }
                for resumen in resumenes
            ],
        )
    print(f"\nSalidas en: {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


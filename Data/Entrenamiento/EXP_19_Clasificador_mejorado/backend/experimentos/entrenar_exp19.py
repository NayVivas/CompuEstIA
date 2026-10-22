"""EXP19: modelos lineales y umbrales regulares para etiquetas minoritarias.

La selección de modelo y calibración se realiza exclusivamente con VALIDATION.
TEST se transforma y evalúa una sola vez, después de congelar la configuración.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    hamming_loss,
    precision_recall_fscore_support,
    precision_score,
    recall_score,
)
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.svm import LinearSVC


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
EXP17_DIR = PROJECT_DIR / "Data" / "EXP17_dataset_integrado"
EXP18_DIR = PROJECT_DIR / "Data" / "EXP18_tfidf_hibrido"
MANIFEST = EXP17_DIR / "EXP17_DATASET.jsonl"
TEXT_CACHE = EXP17_DIR / "EXP17_TEXT_CACHE.csv"
VECTORIZER = EXP18_DIR / "EXP18_TFIDF_HIBRIDO.joblib"
OUTPUT_DIR = PROJECT_DIR / "Data" / "EXP19_balance_minoritarias"

TARGETS = ("disciplinas", "roles_documentales", "contenidos")
SPLITS = ("train", "validation", "test")
SEED = 20260925
MICRO_TOLERANCE = 0.02


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    family: str
    c_value: float
    score_kind: str


@dataclass(frozen=True)
class ThresholdSpec:
    strategy_id: str
    minimum_support: int | None
    shrinkage: float


MODEL_SPECS = (
    ModelSpec("logreg_c1", "logistic_regression", 1.0, "probability"),
    ModelSpec("logreg_c2", "logistic_regression", 2.0, "probability"),
    ModelSpec("logreg_c4", "logistic_regression", 4.0, "probability"),
    ModelSpec("linearsvc_c05", "linear_svc", 0.5, "decision"),
    ModelSpec("linearsvc_c1", "linear_svc", 1.0, "decision"),
)

THRESHOLD_SPECS = (
    ThresholdSpec("global", None, 0.0),
    ThresholdSpec("por_etiqueta_s5_r10", 5, 10.0),
    ThresholdSpec("por_etiqueta_s5_r25", 5, 25.0),
    ThresholdSpec("por_etiqueta_s10_r10", 10, 10.0),
)


def _load_rows(manifest: Path, text_cache: Path):
    records = [
        json.loads(line)
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    with text_cache.open("r", encoding="utf-8-sig", newline="") as stream:
        texts = {row["registro_id"]: row for row in csv.DictReader(stream)}

    missing = [row["registro_id"] for row in records if row["registro_id"] not in texts]
    if missing:
        raise ValueError(f"Faltan {len(missing)} páginas en el caché de texto.")

    output = []
    for row in records:
        text_row = texts[row["registro_id"]]
        if text_row.get("error_extraccion"):
            raise ValueError(text_row["error_extraccion"])
        text = text_row.get("texto_combinado", "").strip()
        if not text:
            raise ValueError(f"Página sin texto: {row['registro_id']}")
        output.append({**row, "texto_modelo": text})

    return output, texts


def _metrics(y_true, y_pred):
    supported = np.asarray(y_true.sum(axis=0)).ravel() > 0
    macro_supported = (
        f1_score(
            y_true[:, supported],
            y_pred[:, supported],
            average="macro",
            zero_division=0,
        )
        if supported.any()
        else 0.0
    )
    coverage = float(np.mean(np.asarray(y_pred.sum(axis=1)).ravel() > 0))
    return {
        "micro_precision": precision_score(
            y_true, y_pred, average="micro", zero_division=0
        ),
        "micro_recall": recall_score(
            y_true, y_pred, average="micro", zero_division=0
        ),
        "micro_f1": f1_score(y_true, y_pred, average="micro", zero_division=0),
        "macro_precision": precision_score(
            y_true, y_pred, average="macro", zero_division=0
        ),
        "macro_recall": recall_score(
            y_true, y_pred, average="macro", zero_division=0
        ),
        "macro_f1": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "macro_f1_etiquetas_presentes": macro_supported,
        "hamming_loss": hamming_loss(y_true, y_pred),
        "exact_match": accuracy_score(y_true, y_pred),
        "coverage": coverage,
        "abstention": 1.0 - coverage,
        "cardinalidad_real": float(np.mean(y_true.sum(axis=1))),
        "cardinalidad_predicha": float(np.mean(y_pred.sum(axis=1))),
    }


def _write_csv(path: Path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _make_model(spec: ModelSpec, seed: int):
    if spec.family == "logistic_regression":
        estimator = LogisticRegression(
            C=spec.c_value,
            class_weight="balanced",
            solver="liblinear",
            max_iter=2500,
            random_state=seed,
        )
    elif spec.family == "linear_svc":
        estimator = LinearSVC(
            C=spec.c_value,
            class_weight="balanced",
            dual="auto",
            max_iter=5000,
            random_state=seed,
        )
    else:
        raise ValueError(f"Familia no soportada: {spec.family}")

    return OneVsRestClassifier(estimator, n_jobs=1)


def _scores(model, matrix, score_kind: str):
    if score_kind == "probability":
        return np.asarray(model.predict_proba(matrix), dtype=float)
    if score_kind == "decision":
        return np.asarray(model.decision_function(matrix), dtype=float)
    raise ValueError(f"Tipo de score no soportado: {score_kind}")


def _global_candidates(scores, score_kind: str):
    if score_kind == "probability":
        return np.arange(0.05, 0.951, 0.01)

    quantiles = np.quantile(scores.ravel(), np.linspace(0.01, 0.99, 197))
    return np.unique(np.concatenate((quantiles, np.array([0.0]))))


def _choose_global_threshold(y_true, scores, score_kind: str):
    best_threshold = 0.5 if score_kind == "probability" else 0.0
    best_metrics = None
    best_key = (-1.0, -1.0, -1.0)

    for threshold in _global_candidates(scores, score_kind):
        metrics = _metrics(y_true, (scores >= threshold).astype(int))
        key = (
            metrics["micro_f1"],
            metrics["macro_f1_etiquetas_presentes"],
            metrics["micro_precision"],
        )
        if key > best_key:
            best_threshold = float(threshold)
            best_metrics = metrics
            best_key = key

    return best_threshold, best_metrics


def _label_candidates(scores, global_threshold: float, score_kind: str):
    if score_kind == "probability":
        values = np.arange(0.02, 0.941, 0.02)
    else:
        values = np.quantile(scores, np.linspace(0.02, 0.98, 49))
    return np.unique(np.concatenate((values, np.array([global_threshold]))))


def _best_label_threshold(y_true, scores, global_threshold, score_kind):
    best_threshold = float(global_threshold)
    best_key = (-1.0, -1.0, -1.0)

    for threshold in _label_candidates(scores, global_threshold, score_kind):
        predicted = (scores >= threshold).astype(int)
        precision, _recall, f1, _ = precision_recall_fscore_support(
            y_true,
            predicted,
            average="binary",
            zero_division=0,
        )
        key = (float(f1), float(precision), -abs(float(threshold) - global_threshold))
        if key > best_key:
            best_threshold = float(threshold)
            best_key = key

    return best_threshold


def _calibrate_per_label(
    y_true,
    scores,
    *,
    global_threshold: float,
    score_kind: str,
    minimum_support: int | None,
    shrinkage: float,
):
    thresholds = np.full(y_true.shape[1], global_threshold, dtype=float)
    supports = np.asarray(y_true.sum(axis=0)).ravel().astype(int)
    calibrated = np.zeros(y_true.shape[1], dtype=bool)

    if minimum_support is None:
        return thresholds, supports, calibrated

    for index, support in enumerate(supports):
        if support < minimum_support:
            continue
        raw_threshold = _best_label_threshold(
            y_true[:, index],
            scores[:, index],
            global_threshold,
            score_kind,
        )
        weight = support / (support + shrinkage) if shrinkage > 0 else 1.0
        thresholds[index] = global_threshold + weight * (
            raw_threshold - global_threshold
        )
        calibrated[index] = True

    return thresholds, supports, calibrated


def _predict(scores, thresholds):
    return (scores >= np.asarray(thresholds).reshape(1, -1)).astype(int)


def _select_candidate(rows, tolerance=MICRO_TOLERANCE):
    """Elige solo con métricas de VALIDATION; no acepta filas de TEST."""

    if not rows:
        raise ValueError("No hay candidatos para seleccionar.")
    if any(row.get("split") != "validation" for row in rows):
        raise ValueError("La selección de EXP19 solo admite resultados de VALIDATION.")

    best_micro = max(row["micro_f1"] for row in rows)
    eligible = [
        row for row in rows if row["micro_f1"] >= best_micro - tolerance - 1e-12
    ]

    return max(
        eligible,
        key=lambda row: (
            row["macro_f1_etiquetas_presentes"],
            row["micro_f1"],
            row["micro_precision"],
            -abs(row["cardinalidad_predicha"] - row["cardinalidad_real"]),
            row["model_id"],
            row["threshold_strategy"],
        ),
    )


def _label_metric_rows(target, split, classes, y_true, predicted):
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, predicted, average=None, zero_division=0
    )
    return [
        {
            "target": target,
            "split": split,
            "label": label,
            "support": int(support[index]),
            "precision": float(precision[index]),
            "recall": float(recall[index]),
            "f1": float(f1[index]),
        }
        for index, label in enumerate(classes)
    ]


def _segment_rows(
    *, target, split, split_rows, text_rows, y_true, predicted
):
    output = []
    segments = {
        "origen": sorted({row["dataset_origen"] for row in split_rows}),
        "extraccion": ("ocr", "texto_nativo"),
    }

    for segment_type, values in segments.items():
        for value in values:
            if segment_type == "origen":
                mask = np.array([row["dataset_origen"] == value for row in split_rows])
            else:
                mask = np.array(
                    [
                        ("ocr_tesseract" in text_rows[row["registro_id"]]["metodo_extraccion"])
                        == (value == "ocr")
                        for row in split_rows
                    ]
                )
            if mask.any():
                output.append(
                    {
                        "target": target,
                        "split": split,
                        "segmento_tipo": segment_type,
                        "segmento": value,
                        "paginas": int(mask.sum()),
                        **_metrics(y_true[mask], predicted[mask]),
                    }
                )

    return output


def _load_exp18_test_metrics(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return {
            row["target"]: row
            for row in csv.DictReader(stream)
            if row["split"] == "test"
        }


def _load_csv_rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def build(
    *,
    manifest=MANIFEST,
    text_cache=TEXT_CACHE,
    vectorizer_path=VECTORIZER,
    exp18_dir=EXP18_DIR,
    output=OUTPUT_DIR,
    seed=SEED,
):
    rows, texts_by_id = _load_rows(manifest, text_cache)
    indexes = {
        split: [index for index, row in enumerate(rows) if row["split"] == split]
        for split in SPLITS
    }
    texts = [row["texto_modelo"] for row in rows]

    vectorizer = joblib.load(vectorizer_path)
    matrices = {
        split: vectorizer.transform([texts[index] for index in indexes[split]])
        for split in SPLITS
    }

    output.mkdir(parents=True, exist_ok=True)
    joblib.dump(vectorizer, output / "EXP19_TFIDF_HIBRIDO.joblib", compress=3)

    candidate_rows = []
    metric_rows = []
    label_rows = []
    segment_rows = []
    prediction_rows = []
    threshold_rows = []
    selected_config = {}
    test_access_log = []
    metric_names = list(
        _metrics(np.zeros((1, 1), dtype=int), np.zeros((1, 1), dtype=int))
    )

    for target in TARGETS:
        classes = sorted({label for row in rows for label in row[target]})
        binarizer = MultiLabelBinarizer(classes=classes)
        binarizer.fit([[]])
        y = {
            split: binarizer.transform([rows[index][target] for index in indexes[split]])
            for split in SPLITS
        }
        train_support = np.asarray(y["train"].sum(axis=0)).ravel().astype(int)

        fitted_models = {}
        calibration_by_candidate = {}
        target_candidates = []

        # Esta fase nunca transforma ni puntúa TEST.
        for model_spec in MODEL_SPECS:
            model = _make_model(model_spec, seed)
            model.fit(matrices["train"], y["train"])
            validation_scores = _scores(
                model, matrices["validation"], model_spec.score_kind
            )
            global_threshold, _ = _choose_global_threshold(
                y["validation"], validation_scores, model_spec.score_kind
            )
            fitted_models[model_spec.model_id] = (model_spec, model)

            for threshold_spec in THRESHOLD_SPECS:
                thresholds, supports, calibrated = _calibrate_per_label(
                    y["validation"],
                    validation_scores,
                    global_threshold=global_threshold,
                    score_kind=model_spec.score_kind,
                    minimum_support=threshold_spec.minimum_support,
                    shrinkage=threshold_spec.shrinkage,
                )
                predicted = _predict(validation_scores, thresholds)
                candidate = {
                    "target": target,
                    "split": "validation",
                    "model_id": model_spec.model_id,
                    "family": model_spec.family,
                    "C": model_spec.c_value,
                    "score_kind": model_spec.score_kind,
                    "threshold_strategy": threshold_spec.strategy_id,
                    "global_threshold": global_threshold,
                    "labels_calibrated": int(calibrated.sum()),
                    **_metrics(y["validation"], predicted),
                }
                target_candidates.append(candidate)
                candidate_rows.append(candidate)
                calibration_by_candidate[
                    (model_spec.model_id, threshold_spec.strategy_id)
                ] = (thresholds, supports, calibrated)

        selected = _select_candidate(target_candidates)
        for candidate in target_candidates:
            candidate["selected"] = (
                candidate["model_id"] == selected["model_id"]
                and candidate["threshold_strategy"]
                == selected["threshold_strategy"]
            )

        model_spec, model = fitted_models[selected["model_id"]]
        thresholds, validation_support, calibrated = calibration_by_candidate[
            (selected["model_id"], selected["threshold_strategy"])
        ]

        selected_config[target] = {
            "model_id": model_spec.model_id,
            "family": model_spec.family,
            "C": model_spec.c_value,
            "score_kind": model_spec.score_kind,
            "threshold_strategy": selected["threshold_strategy"],
            "global_threshold": selected["global_threshold"],
            "micro_f1_validation": selected["micro_f1"],
            "macro_f1_validation_etiquetas_presentes": selected[
                "macro_f1_etiquetas_presentes"
            ],
        }

        joblib.dump(model, output / f"EXP19_{target}_MODELO.joblib", compress=3)
        joblib.dump(
            binarizer, output / f"EXP19_{target}_BINARIZADOR.joblib", compress=3
        )

        for index, label in enumerate(classes):
            threshold_rows.append(
                {
                    "target": target,
                    "label": label,
                    "model_id": model_spec.model_id,
                    "threshold_strategy": selected["threshold_strategy"],
                    "score_kind": model_spec.score_kind,
                    "support_train": int(train_support[index]),
                    "support_validation": int(validation_support[index]),
                    "global_threshold": selected["global_threshold"],
                    "threshold": float(thresholds[index]),
                    "calibrated": bool(calibrated[index]),
                }
            )

        # La configuración ya quedó congelada. TEST se usa desde este punto una vez.
        for split in ("validation", "test"):
            scores = _scores(model, matrices[split], model_spec.score_kind)
            if split == "test":
                test_access_log.append(
                    {
                        "target": target,
                        "model_id": model_spec.model_id,
                        "threshold_strategy": selected["threshold_strategy"],
                    }
                )
            predicted = _predict(scores, thresholds)
            metrics = _metrics(y[split], predicted)
            metric_rows.append(
                {
                    "target": target,
                    "split": split,
                    "model_id": model_spec.model_id,
                    "threshold_strategy": selected["threshold_strategy"],
                    **metrics,
                }
            )
            label_rows.extend(
                _label_metric_rows(target, split, classes, y[split], predicted)
            )
            split_rows = [rows[index] for index in indexes[split]]
            segment_rows.extend(
                _segment_rows(
                    target=target,
                    split=split,
                    split_rows=split_rows,
                    text_rows=texts_by_id,
                    y_true=y[split],
                    predicted=predicted,
                )
            )

            truths = binarizer.inverse_transform(y[split])
            predictions = binarizer.inverse_transform(predicted)
            for local_index, row_index in enumerate(indexes[split]):
                prediction_rows.append(
                    {
                        "registro_id": rows[row_index]["registro_id"],
                        "dataset_origen": rows[row_index]["dataset_origen"],
                        "proyecto_id": rows[row_index]["proyecto_id"],
                        "split": split,
                        "target": target,
                        "verdadero": json.dumps(
                            truths[local_index], ensure_ascii=False
                        ),
                        "predicho": json.dumps(
                            predictions[local_index], ensure_ascii=False
                        ),
                    }
                )

    candidate_fields = [
        "target", "split", "model_id", "family", "C", "score_kind",
        "threshold_strategy", "global_threshold", "labels_calibrated",
        *metric_names, "selected",
    ]
    _write_csv(output / "EXP19_CANDIDATOS_VALIDATION.csv", candidate_fields, candidate_rows)
    _write_csv(
        output / "EXP19_UMBRALES_POR_ETIQUETA.csv",
        [
            "target", "label", "model_id", "threshold_strategy", "score_kind",
            "support_train", "support_validation", "global_threshold",
            "threshold", "calibrated",
        ],
        threshold_rows,
    )
    _write_csv(
        output / "EXP19_METRICAS.csv",
        ["target", "split", "model_id", "threshold_strategy", *metric_names],
        metric_rows,
    )
    _write_csv(
        output / "EXP19_METRICAS_POR_ETIQUETA.csv",
        ["target", "split", "label", "support", "precision", "recall", "f1"],
        label_rows,
    )
    _write_csv(
        output / "EXP19_METRICAS_POR_SEGMENTO.csv",
        [
            "target", "split", "segmento_tipo", "segmento", "paginas",
            *metric_names,
        ],
        segment_rows,
    )
    _write_csv(
        output / "EXP19_PREDICCIONES.csv",
        [
            "registro_id", "dataset_origen", "proyecto_id", "split", "target",
            "verdadero", "predicho",
        ],
        prediction_rows,
    )

    exp18_test = _load_exp18_test_metrics(exp18_dir / "EXP18_METRICAS.csv")
    comparison_rows = []
    for row in metric_rows:
        if row["split"] != "test":
            continue
        previous = exp18_test[row["target"]]
        comparison_rows.append(
            {
                "target": row["target"],
                "exp18_micro_f1": float(previous["micro_f1"]),
                "exp19_micro_f1": row["micro_f1"],
                "delta_micro_f1": row["micro_f1"] - float(previous["micro_f1"]),
                "exp18_macro_f1": float(previous["macro_f1"]),
                "exp19_macro_f1": row["macro_f1"],
                "delta_macro_f1": row["macro_f1"] - float(previous["macro_f1"]),
                "exp18_recall": float(previous["micro_recall"]),
                "exp19_recall": row["micro_recall"],
                "delta_recall": row["micro_recall"] - float(previous["micro_recall"]),
            }
        )

    _write_csv(
        output / "EXP18_VS_EXP19.csv",
        [
            "target", "exp18_micro_f1", "exp19_micro_f1", "delta_micro_f1",
            "exp18_macro_f1", "exp19_macro_f1", "delta_macro_f1",
            "exp18_recall", "exp19_recall", "delta_recall",
        ],
        comparison_rows,
    )

    exp18_segments = {
        (
            row["target"],
            row["split"],
            row["segmento_tipo"],
            row["segmento"],
        ): row
        for row in _load_csv_rows(exp18_dir / "EXP18_METRICAS_POR_SEGMENTO.csv")
    }
    segment_comparison_rows = []
    for row in segment_rows:
        if row["split"] != "test":
            continue
        key = (
            row["target"],
            row["split"],
            row["segmento_tipo"],
            row["segmento"],
        )
        previous = exp18_segments.get(key)
        if previous is None:
            continue
        segment_comparison_rows.append(
            {
                "target": row["target"],
                "segmento_tipo": row["segmento_tipo"],
                "segmento": row["segmento"],
                "paginas": row["paginas"],
                "exp18_micro_f1": float(previous["micro_f1"]),
                "exp19_micro_f1": row["micro_f1"],
                "delta_micro_f1": row["micro_f1"] - float(previous["micro_f1"]),
                "exp18_recall": float(previous["micro_recall"]),
                "exp19_recall": row["micro_recall"],
                "delta_recall": row["micro_recall"] - float(previous["micro_recall"]),
            }
        )
    _write_csv(
        output / "EXP18_VS_EXP19_POR_SEGMENTO.csv",
        [
            "target", "segmento_tipo", "segmento", "paginas",
            "exp18_micro_f1", "exp19_micro_f1", "delta_micro_f1",
            "exp18_recall", "exp19_recall", "delta_recall",
        ],
        segment_comparison_rows,
    )

    exp18_labels = _load_csv_rows(exp18_dir / "EXP18_METRICAS_POR_ETIQUETA.csv")
    zero_f1_diagnostics = []
    for target in TARGETS:
        for split in ("validation", "test"):
            previous = [
                row for row in exp18_labels
                if row["target"] == target and row["split"] == split
            ]
            current = [
                row for row in label_rows
                if row["target"] == target and row["split"] == split
            ]
            zero_f1_diagnostics.append(
                {
                    "target": target,
                    "split": split,
                    "etiquetas_presentes": sum(
                        float(row["support"]) > 0 for row in current
                    ),
                    "exp18_etiquetas_f1_cero": sum(
                        float(row["support"]) > 0 and float(row["f1"]) == 0
                        for row in previous
                    ),
                    "exp19_etiquetas_f1_cero": sum(
                        int(row["support"]) > 0 and float(row["f1"]) == 0
                        for row in current
                    ),
                }
            )
    _write_csv(
        output / "EXP19_DIAGNOSTICO_ETIQUETAS_F1_CERO.csv",
        [
            "target", "split", "etiquetas_presentes",
            "exp18_etiquetas_f1_cero", "exp19_etiquetas_f1_cero",
        ],
        zero_f1_diagnostics,
    )

    config = {
        "experimento": "EXP19",
        "semilla": seed,
        "fuente_features": str(vectorizer_path),
        "seleccion": "VALIDATION exclusivamente",
        "tolerancia_micro_f1": MICRO_TOLERANCE,
        "modelos_candidatos": [spec.__dict__ for spec in MODEL_SPECS],
        "estrategias_umbrales": [spec.__dict__ for spec in THRESHOLD_SPECS],
        "configuracion_seleccionada": selected_config,
    }
    (output / "EXP19_CONFIG.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    summary = {
        "experimento": "EXP19",
        "objetivo": "mejorar etiquetas minoritarias sin perder más de 0.02 de micro-F1 en VALIDATION",
        "semilla": seed,
        "paginas_por_split": {split: len(indexes[split]) for split in SPLITS},
        "candidatos_evaluados_en_validation": len(candidate_rows),
        "configuracion_seleccionada": selected_config,
        "test_evaluado_despues_de_congelar": len(test_access_log) == len(TARGETS),
        "evaluaciones_test": test_access_log,
        "metricas": metric_rows,
        "comparacion_exp18_exp19": comparison_rows,
        "comparacion_por_segmento": segment_comparison_rows,
        "diagnostico_etiquetas_f1_cero": zero_f1_diagnostics,
    }
    (output / "EXP19_RESUMEN.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    test_metrics = {row["target"]: row for row in metric_rows if row["split"] == "test"}
    comparison = {row["target"]: row for row in comparison_rows}
    contents_by_origin = [
        row for row in segment_comparison_rows
        if row["target"] == "contenidos" and row["segmento_tipo"] == "origen"
    ]
    lines = [
        "# EXP19 - Balance de etiquetas minoritarias",
        "",
        "Se conservaron las características TF-IDF híbridas de EXP18. Los modelos y umbrales se eligieron solo con VALIDATION; TEST se evaluó una vez después de congelar cada configuración.",
        "",
        "Criterio: maximizar macro-F1 de etiquetas presentes entre candidatos cuyo micro-F1 esté a no más de 0,02 del mejor micro-F1 de VALIDATION.",
        "",
        "| Target | Modelo | Umbrales | micro-F1 TEST | Δ micro-F1 | macro-F1 TEST | Δ macro-F1 |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for target in TARGETS:
        metrics = test_metrics[target]
        delta = comparison[target]
        selected = selected_config[target]
        lines.append(
            f"| {target} | {selected['model_id']} | {selected['threshold_strategy']} | "
            f"{metrics['micro_f1']:.4f} | {delta['delta_micro_f1']:+.4f} | "
            f"{metrics['macro_f1']:.4f} | {delta['delta_macro_f1']:+.4f} |"
        )
    lines.extend(
        [
            "",
            "## Contenidos por fuente en TEST",
            "",
            "| Fuente | Páginas | micro-F1 EXP18 | micro-F1 EXP19 | Δ | Recall EXP18 | Recall EXP19 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in contents_by_origin:
        lines.append(
            f"| {row['segmento']} | {row['paginas']} | {row['exp18_micro_f1']:.4f} | "
            f"{row['exp19_micro_f1']:.4f} | {row['delta_micro_f1']:+.4f} | "
            f"{row['exp18_recall']:.4f} | {row['exp19_recall']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Lectura correcta",
            "",
            "EXP19 es una mejora del clasificador textual, no una validación final de producción. Las clases ausentes o casi ausentes en VALIDATION no pueden calibrarse de forma fiable y conservan el umbral global.",
            "",
            "El paso siguiente recomendado es EXP20: incorporar características visuales y de composición de página al texto para reducir el cambio de dominio entre fuentes.",
        ]
    )
    (output / "EXP19_DOCUMENTACION.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifiesto", type=Path, default=MANIFEST)
    parser.add_argument("--textos", type=Path, default=TEXT_CACHE)
    parser.add_argument("--vectorizador", type=Path, default=VECTORIZER)
    parser.add_argument("--exp18", type=Path, default=EXP18_DIR)
    parser.add_argument("--salida", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--semilla", type=int, default=SEED)
    args = parser.parse_args()
    summary = build(
        manifest=args.manifiesto,
        text_cache=args.textos,
        vectorizer_path=args.vectorizador,
        exp18_dir=args.exp18,
        output=args.salida,
        seed=args.semilla,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

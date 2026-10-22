"""Entrena EXP18 con TF-IDF híbrido y Logistic Regression multilabel."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, hamming_loss, precision_recall_fscore_support, precision_score, recall_score
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
EXP17_DIR = PROJECT_DIR / "Data" / "EXP17_dataset_integrado"
MANIFEST = EXP17_DIR / "EXP17_DATASET.jsonl"
TEXT_CACHE = EXP17_DIR / "EXP17_TEXT_CACHE.csv"
OUTPUT_DIR = PROJECT_DIR / "Data" / "EXP18_tfidf_hibrido"
TARGETS = ("disciplinas", "roles_documentales", "contenidos")
SPLITS = ("train", "validation", "test")
SEED = 20260924


def _load_rows(manifest, text_cache):
    records = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
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


def _vectorizer():
    return FeatureUnion([
        ("palabras", TfidfVectorizer(lowercase=True, strip_accents="unicode", ngram_range=(1, 2), min_df=2, max_df=0.995, max_features=40_000, sublinear_tf=True)),
        ("caracteres", TfidfVectorizer(analyzer="char_wb", lowercase=True, strip_accents="unicode", ngram_range=(3, 5), min_df=2, max_features=60_000, sublinear_tf=True)),
    ], transformer_weights={"palabras": 1.0, "caracteres": 0.7})


def _metrics(y_true, y_pred):
    supported = np.asarray(y_true.sum(axis=0)).ravel() > 0
    macro_supported = f1_score(y_true[:, supported], y_pred[:, supported], average="macro", zero_division=0) if supported.any() else 0.0
    coverage = float(np.mean(np.asarray(y_pred.sum(axis=1)).ravel() > 0))
    return {
        "micro_precision": precision_score(y_true, y_pred, average="micro", zero_division=0),
        "micro_recall": recall_score(y_true, y_pred, average="micro", zero_division=0),
        "micro_f1": f1_score(y_true, y_pred, average="micro", zero_division=0),
        "macro_precision": precision_score(y_true, y_pred, average="macro", zero_division=0),
        "macro_recall": recall_score(y_true, y_pred, average="macro", zero_division=0),
        "macro_f1": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "macro_f1_etiquetas_presentes": macro_supported,
        "hamming_loss": hamming_loss(y_true, y_pred),
        "exact_match": accuracy_score(y_true, y_pred),
        "coverage": coverage, "abstention": 1.0 - coverage,
        "cardinalidad_real": float(np.mean(y_true.sum(axis=1))),
        "cardinalidad_predicha": float(np.mean(y_pred.sum(axis=1))),
    }


def _threshold(y_true, probabilities):
    best_threshold, best_metrics, best_key = 0.5, None, (-1.0, -1.0, -1.0)
    for threshold in np.arange(0.10, 0.901, 0.01):
        metrics = _metrics(y_true, (probabilities >= threshold).astype(int))
        key = (metrics["micro_f1"], metrics["macro_f1_etiquetas_presentes"], metrics["micro_precision"])
        if key > best_key:
            best_threshold, best_metrics, best_key = float(round(threshold, 2)), metrics, key
    return best_threshold, best_metrics


def _write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def build(*, manifest=MANIFEST, text_cache=TEXT_CACHE, output=OUTPUT_DIR, seed=SEED):
    rows, texts_by_id = _load_rows(manifest, text_cache)
    indexes = {split: [index for index, row in enumerate(rows) if row["split"] == split] for split in SPLITS}
    texts = [row["texto_modelo"] for row in rows]
    vectorizer = _vectorizer()
    matrices = {"train": vectorizer.fit_transform([texts[i] for i in indexes["train"]])}
    matrices["validation"] = vectorizer.transform([texts[i] for i in indexes["validation"]])
    matrices["test"] = vectorizer.transform([texts[i] for i in indexes["test"]])
    output.mkdir(parents=True, exist_ok=True)
    joblib.dump(vectorizer, output / "EXP18_TFIDF_HIBRIDO.joblib", compress=3)
    metric_rows, label_rows, segment_rows, prediction_rows = [], [], [], []
    thresholds, label_counts = {}, {}
    metric_names = list(_metrics(np.zeros((1, 1), dtype=int), np.zeros((1, 1), dtype=int)))

    for target in TARGETS:
        classes = sorted({label for row in rows for label in row[target]})
        label_counts[target] = len(classes)
        binarizer = MultiLabelBinarizer(classes=classes); binarizer.fit([[]])
        y = {split: binarizer.transform([rows[i][target] for i in indexes[split]]) for split in SPLITS}
        model = OneVsRestClassifier(LogisticRegression(C=2.0, class_weight="balanced", solver="liblinear", max_iter=2500, random_state=seed), n_jobs=1)
        model.fit(matrices["train"], y["train"])
        probabilities = {split: model.predict_proba(matrices[split]) for split in ("validation", "test")}
        threshold, _ = _threshold(y["validation"], probabilities["validation"])
        thresholds[target] = threshold
        joblib.dump(model, output / f"EXP18_{target}_MODELO.joblib", compress=3)
        joblib.dump(binarizer, output / f"EXP18_{target}_BINARIZADOR.joblib", compress=3)

        for split in ("validation", "test"):
            predicted = (probabilities[split] >= threshold).astype(int)
            metric_rows.append({"target": target, "split": split, "threshold": threshold, **_metrics(y[split], predicted)})
            precision, recall, f1, support = precision_recall_fscore_support(y[split], predicted, average=None, zero_division=0)
            for index, label in enumerate(classes):
                label_rows.append({"target": target, "split": split, "label": label, "support": int(support[index]), "precision": float(precision[index]), "recall": float(recall[index]), "f1": float(f1[index])})
            split_rows = [rows[i] for i in indexes[split]]
            for segment_type, values in {"origen": sorted({row["dataset_origen"] for row in split_rows}), "extraccion": ("ocr", "texto_nativo")}.items():
                for value in values:
                    if segment_type == "origen":
                        mask = np.array([row["dataset_origen"] == value for row in split_rows])
                    else:
                        mask = np.array([("ocr_tesseract" in texts_by_id[row["registro_id"]]["metodo_extraccion"]) == (value == "ocr") for row in split_rows])
                    if mask.any():
                        segment_rows.append({"target": target, "split": split, "segmento_tipo": segment_type, "segmento": value, "paginas": int(mask.sum()), **_metrics(y[split][mask], predicted[mask])})
            for local_index, row_index in enumerate(indexes[split]):
                truth = binarizer.inverse_transform(y[split][[local_index]])[0]
                prediction = binarizer.inverse_transform(predicted[[local_index]])[0]
                prediction_rows.append({"registro_id": rows[row_index]["registro_id"], "dataset_origen": rows[row_index]["dataset_origen"], "proyecto_id": rows[row_index]["proyecto_id"], "split": split, "target": target, "verdadero": json.dumps(truth, ensure_ascii=False), "predicho": json.dumps(prediction, ensure_ascii=False)})

    _write_csv(output / "EXP18_METRICAS.csv", ["target", "split", "threshold", *metric_names], metric_rows)
    _write_csv(output / "EXP18_METRICAS_POR_ETIQUETA.csv", ["target", "split", "label", "support", "precision", "recall", "f1"], label_rows)
    _write_csv(output / "EXP18_METRICAS_POR_SEGMENTO.csv", ["target", "split", "segmento_tipo", "segmento", "paginas", *metric_names], segment_rows)
    _write_csv(output / "EXP18_PREDICCIONES.csv", ["registro_id", "dataset_origen", "proyecto_id", "split", "target", "verdadero", "predicho"], prediction_rows)
    text_rows = list(texts_by_id.values())
    summary = {
        "experimento": "EXP18", "semilla": seed,
        "modelo": "TF-IDF palabras+caracteres / Logistic Regression One-vs-Rest",
        "paginas_por_split": {split: len(indexes[split]) for split in SPLITS},
        "paginas_con_ocr": sum("ocr_tesseract" in row["metodo_extraccion"] for row in text_rows),
        "paginas_sin_texto": sum(not row["texto_combinado"].strip() for row in text_rows),
        "vocabulario_total": int(matrices["train"].shape[1]),
        "umbrales": thresholds, "etiquetas_por_target": label_counts, "metricas": metric_rows,
    }
    (output / "EXP18_RESUMEN.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "EXP18_CONFIG.json").write_text(json.dumps({"semilla": seed, "targets": TARGETS, "umbrales": thresholds, "C": 2.0}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    test_rows = [row for row in metric_rows if row["split"] == "test"]
    lines = ["# EXP18 - TF-IDF híbrido con OCR", "", "Split por grupos congelado en EXP17. Umbrales elegidos solo con VALIDATION.", "", "| Target | micro-F1 TEST | Precision | Recall |", "|---|---:|---:|---:|"]
    lines.extend(f"| {row['target']} | {row['micro_f1']:.4f} | {row['micro_precision']:.4f} | {row['micro_recall']:.4f} |" for row in test_rows)
    (output / "EXP18_DOCUMENTACION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifiesto", type=Path, default=MANIFEST)
    parser.add_argument("--textos", type=Path, default=TEXT_CACHE)
    parser.add_argument("--salida", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--semilla", type=int, default=SEED)
    args = parser.parse_args()
    print(json.dumps(build(manifest=args.manifiesto, text_cache=args.textos, output=args.salida, seed=args.semilla), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

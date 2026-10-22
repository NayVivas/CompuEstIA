"""Compara estrategias para detectar el rol documental ``corte``.

La selección se realiza con el corpus histórico agrupado por fuente. EXP-11 se
usa después únicamente como benchmark auditado. La estrategia seleccionada es
un indicio trazable; no modifica las etiquetas humanas.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import sys
import warnings

import numpy as np
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score


RAIZ = Path(__file__).resolve().parents[2]
BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from computos.documentos.reglas_roles import detectar_indicio_corte  # noqa: E402


def _leer_csv(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        return list(csv.DictReader(archivo))


def _clave_antigua(fila: dict) -> tuple[str, str, str]:
    return fila["proyecto_id"], fila["documento"], str(fila["pagina"])


def _metricas(real: np.ndarray, pred: np.ndarray) -> dict:
    tp = int(np.logical_and(real, pred).sum())
    fp = int(np.logical_and(~real, pred).sum())
    fn = int(np.logical_and(real, ~pred).sum())
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(tp / (tp + fp), 4) if tp + fp else 0.0,
        "recall": round(tp / (tp + fn), 4) if tp + fn else 0.0,
        "f1": round(2 * tp / (2 * tp + fp + fn), 4)
        if 2 * tp + fp + fn else 0.0,
    }


def _vectorizadores(nombre: str) -> list[TfidfVectorizer]:
    palabra = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        min_df=2,
        max_features=20000,
        sublinear_tf=True,
    )
    caracteres = TfidfVectorizer(
        analyzer="char_wb",
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(3, 6),
        min_df=2,
        max_features=40000,
        sublinear_tf=True,
    )
    return {
        "tfidf_palabras": [palabra],
        "tfidf_caracteres": [caracteres],
        "tfidf_palabras_mas_caracteres": [palabra, caracteres],
    }[nombre]


def _probabilidades_oof(
    nombre: str,
    textos: list[str],
    real: np.ndarray,
    fuentes: np.ndarray,
) -> np.ndarray:
    probabilidades = np.zeros(len(textos), dtype=float)
    for fuente in sorted(set(fuentes)):
        train = fuentes != fuente
        test = ~train
        textos_train = [textos[i] for i in np.flatnonzero(train)]
        textos_test = [textos[i] for i in np.flatnonzero(test)]
        train_partes = []
        test_partes = []
        for vectorizador in _vectorizadores(nombre):
            train_partes.append(vectorizador.fit_transform(textos_train))
            test_partes.append(vectorizador.transform(textos_test))
        x_train = (
            train_partes[0]
            if len(train_partes) == 1
            else hstack(train_partes, format="csr")
        )
        x_test = (
            test_partes[0]
            if len(test_partes) == 1
            else hstack(test_partes, format="csr")
        )
        modelo = LogisticRegression(
            C=1.0,
            class_weight="balanced",
            solver="liblinear",
            max_iter=3000,
            random_state=0,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            modelo.fit(x_train, real[train])
        probas = modelo.predict_proba(x_test)[:, 1]
        probas[np.array([not texto.strip() for texto in textos_test])] = 0.0
        probabilidades[test] = probas
    return probabilidades


def _evaluar_por_fuente(
    real: np.ndarray,
    pred: np.ndarray,
    fuentes: np.ndarray,
) -> list[dict]:
    resultado = []
    for fuente in sorted(set(fuentes)):
        mascara = fuentes == fuente
        resultado.append({
            "fuente": fuente,
            "paginas": int(mascara.sum()),
            "positivos": int(real[mascara].sum()),
            **_metricas(real[mascara], pred[mascara]),
        })
    return resultado


def _resultado_candidato(
    nombre: str,
    real: np.ndarray,
    pred: np.ndarray,
    fuentes: np.ndarray,
    probabilidades: np.ndarray | None = None,
) -> dict:
    por_fuente = _evaluar_por_fuente(real, pred, fuentes)
    resultado = {
        "estrategia": nombre,
        **_metricas(real, pred),
        "f1_promedio_por_fuente": round(
            sum(fila["f1"] for fila in por_fuente) / len(por_fuente), 4
        ),
        "por_fuente": por_fuente,
    }
    if probabilidades is not None:
        resultado.update({
            "roc_auc": round(float(roc_auc_score(real, probabilidades)), 4),
            "average_precision": round(
                float(average_precision_score(real, probabilidades)), 4
            ),
        })
    else:
        resultado.update({"roc_auc": None, "average_precision": None})
    return resultado


def _evaluar_regla(
    filas: list[dict], textos: list[str]
) -> tuple[np.ndarray, list[dict]]:
    evidencias = [
        detectar_indicio_corte(texto, fila.get("documento") or fila.get("archivo"))
        for fila, texto in zip(filas, textos)
    ]
    return np.array([evidencia["detectado"] for evidencia in evidencias]), evidencias


def ejecutar(
    data_dir: Path,
    etiquetas: Path,
    texto_hibrido_nuevo: Path,
    salida: Path,
) -> dict:
    antiguas = _leer_csv(
        data_dir / "EXP_03_protocolo_split/EXP03_DATASET_CON_SPLIT.csv"
    )
    cache_antigua = {
        _clave_antigua(fila): fila["texto_pagina"]
        for fila in _leer_csv(data_dir / "EXP_09_auditoria/EXP09_TEXTO_HIBRIDO.csv")
    }
    textos_antiguos = [cache_antigua[_clave_antigua(fila)] for fila in antiguas]
    real_antiguo = np.array([
        "corte" in json.loads(fila["roles_documentales"]) for fila in antiguas
    ])
    mapa_fuentes = {
        fila["proyecto_id"]: fila["fuente_id"]
        for fila in _leer_csv(
            data_dir / "EXP_09_auditoria/EXP09_FUENTES_CONFIRMADAS.csv"
        )
    }
    fuentes = np.array([
        mapa_fuentes.get(fila["proyecto_id"], fila["proyecto_id"])
        for fila in antiguas
    ])

    candidatos = []
    for nombre in (
        "tfidf_palabras",
        "tfidf_caracteres",
        "tfidf_palabras_mas_caracteres",
    ):
        probabilidades = _probabilidades_oof(
            nombre, textos_antiguos, real_antiguo, fuentes
        )
        candidatos.append(_resultado_candidato(
            nombre,
            real_antiguo,
            probabilidades >= 0.5,
            fuentes,
            probabilidades,
        ))

    pred_regla, evidencias_antiguas = _evaluar_regla(antiguas, textos_antiguos)
    candidatos.append(_resultado_candidato(
        "regla_corte_literal_y_alias_pdf",
        real_antiguo,
        pred_regla,
        fuentes,
    ))
    elegibles = [fila for fila in candidatos if fila["precision"] >= 0.65]
    if not elegibles:
        raise ValueError("Ninguna estrategia alcanza la precisión histórica mínima")
    seleccionada = max(
        elegibles,
        key=lambda fila: (
            fila["f1_promedio_por_fuente"],
            fila["f1"],
            fila["precision"],
        ),
    )

    contenido_nuevo = json.loads(etiquetas.read_text(encoding="utf-8-sig"))
    nuevas = [
        fila for fila in contenido_nuevo["filas"]
        if fila.get("decision") == "confirmada"
        and fila.get("ambiguo") == "no"
        and fila.get("incluir_en_metricas") is not False
    ]
    cache_nueva = {
        (fila["archivo"], int(fila["pagina"])): fila["texto_pagina"]
        for fila in json.loads(texto_hibrido_nuevo.read_text(encoding="utf-8-sig"))
    }
    textos_nuevos = [
        cache_nueva[(fila["archivo"], int(fila["pagina"]))] for fila in nuevas
    ]
    real_nuevo = np.array([
        "corte" in fila["roles_documentales"] for fila in nuevas
    ])
    pred_nueva, evidencias_nuevas = _evaluar_regla(nuevas, textos_nuevos)
    carpetas = np.array([fila["proyecto_id"] for fila in nuevas])
    resultado_externo = _resultado_candidato(
        seleccionada["estrategia"], real_nuevo, pred_nueva, carpetas
    )

    predicciones_exp12 = json.loads(
        (data_dir / "EXP_12_ocr_externo/EXP12_PREDICCIONES.json").read_text(
            encoding="utf-8"
        )
    )
    base = [
        fila for fila in predicciones_exp12
        if fila["tarea"] == "roles_documentales"
        and fila["modalidad"] == "texto_pdf_mas_ocr"
    ]
    real_base = np.array(["corte" in fila["real"] for fila in base])
    pred_base = np.array(["corte" in fila["predicho"] for fila in base])
    resultado_base = _metricas(real_base, pred_base)

    detalle_externo = []
    for fila, real, pred, evidencia in zip(
        nuevas, real_nuevo, pred_nueva, evidencias_nuevas
    ):
        detalle_externo.append({
            "archivo": fila["archivo"],
            "pagina": fila["pagina"],
            "real_corte": bool(real),
            "predicho_corte": bool(pred),
            "acierto": bool(real) == bool(pred),
            **evidencia,
        })

    configuracion = {
        "rol": "corte",
        "estrategia": seleccionada["estrategia"],
        "precision_historica_minima_para_seleccion": 0.65,
        "patron_general": r"\bcortes?\b",
        "alias_compatibilidad_pdf": "&RUWH",
        "campos_revisados": ["nombre_archivo", "texto_pagina"],
        "salida": "indicio trazable; no reemplaza la validacion humana",
    }
    salida.mkdir(parents=True, exist_ok=True)
    auditoria = {
        "paginas_historicas": len(antiguas),
        "positivos_historicos": int(real_antiguo.sum()),
        "fuentes_historicas": len(set(fuentes)),
        "criterio_seleccion": (
            "precision >= 0.65; luego mayor F1 promedio por fuente, "
            "F1 global y precision"
        ),
        "candidatos_historicos": candidatos,
        "estrategia_seleccionada": seleccionada["estrategia"],
        "benchmark_externo": {
            "paginas": len(nuevas),
            "positivos": int(real_nuevo.sum()),
            "modelo_exp12": resultado_base,
            "regla_trazable": resultado_externo,
            "diferencia_f1": round(resultado_externo["f1"] - resultado_base["f1"], 4),
        },
        "decision": (
            "usar la regla como candidato de rol con evidencia; "
            "mantener revision cuando no hay coincidencia explicita"
        ),
    }
    (salida / "EXP15_REGLA_CORTE.json").write_text(
        json.dumps(configuracion, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (salida / "EXP15_RESULTADOS.json").write_text(
        json.dumps(auditoria, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (salida / "EXP15_PREDICCIONES_CORTE.json").write_text(
        json.dumps(detalle_externo, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lineas = [
        "# EXP-15 — Mejora trazable para el rol corte",
        "",
        "La estrategia se eligió con el corpus histórico agrupado por fuente. EXP-11 "
        "se utiliza únicamente como benchmark auditado.",
        "",
        "## Comparación histórica",
        "",
        "| Estrategia | Precisión | Recall | F1 | F1 promedio por fuente | AUC |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for fila in candidatos:
        auc = "—" if fila["roc_auc"] is None else f"{fila['roc_auc']:.3f}"
        lineas.append(
            f"| {fila['estrategia']} | {fila['precision']:.3f} | "
            f"{fila['recall']:.3f} | {fila['f1']:.3f} | "
            f"{fila['f1_promedio_por_fuente']:.3f} | {auc} |"
        )
    lineas += [
        "",
        f"Estrategia seleccionada: **{seleccionada['estrategia']}**.",
        "",
        "## Benchmark en EXP-11",
        "",
        "| Estrategia | Precisión | Recall | F1 | TP | FP | FN |",
        "|---|---:|---:|---:|---:|---:|---:|",
        f"| Modelo EXP-12 | {resultado_base['precision']:.3f} | "
        f"{resultado_base['recall']:.3f} | {resultado_base['f1']:.3f} | "
        f"{resultado_base['tp']} | {resultado_base['fp']} | {resultado_base['fn']} |",
        f"| Regla trazable | {resultado_externo['precision']:.3f} | "
        f"{resultado_externo['recall']:.3f} | {resultado_externo['f1']:.3f} | "
        f"{resultado_externo['tp']} | {resultado_externo['fp']} | "
        f"{resultado_externo['fn']} |",
        "",
        "## Regla",
        "",
        "1. Buscar `corte` o `cortes` como palabra completa en el nombre del archivo.",
        "2. Buscar la misma expresión en el texto PDF u OCR de la página.",
        "3. Reconocer `&RUWH` como alias auditable de un PDF con texto codificado.",
        "4. Devolver el origen y el fragmento que justifican la detección.",
        "",
        "## Decisión",
        "",
        "La regla mejora ampliamente el rol `corte` y es más trazable que los modelos "
        "probados. Debe generar un candidato visible para revisión, no modificar el Ground "
        "Truth automáticamente. Las páginas sin la palabra explícita todavía requieren una "
        "segunda etapa geométrica o visual.",
    ]
    (salida / "EXP15_EVALUACION.md").write_text(
        "\n".join(lineas) + "\n", encoding="utf-8"
    )
    return auditoria


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=RAIZ / "Data")
    parser.add_argument("--etiquetas", type=Path, required=True)
    parser.add_argument("--texto-hibrido", type=Path, required=True)
    parser.add_argument(
        "--salida", type=Path, default=RAIZ / "Data/EXP_15_deteccion_corte"
    )
    args = parser.parse_args()
    resultado = ejecutar(
        args.data_dir, args.etiquetas, args.texto_hibrido, args.salida
    )
    print(json.dumps(resultado["benchmark_externo"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

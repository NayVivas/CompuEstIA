"""Evalúa en EXP-11 el modelo entrenado con texto PDF + OCR histórico.

EXP-11 se usa solo para evaluación. El vocabulario, los pesos del modelo y
los parámetros visuales se ajustan exclusivamente con las 474 páginas del
corpus anterior. El umbral permanece fijo en 0,5.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import warnings

import numpy as np
from scipy.sparse import csr_matrix, hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer, StandardScaler, normalize

from evaluar_exp11_externo import (
    RAIZ,
    TARGETS,
    cargar_datos,
    clave,
    escoger_paginas,
    leer_csv,
    metricas,
    textos_e_imagenes,
)


def _cargar_textos_antiguos(data_dir: Path, antiguos: list[dict]) -> list[str]:
    ruta = data_dir / "EXP_09_auditoria/EXP09_TEXTO_HIBRIDO.csv"
    filas = leer_csv(ruta)
    indice = {clave(fila): fila["texto_pagina"] for fila in filas}
    claves = [clave(fila) for fila in antiguos]
    if len(indice) != len(filas) or set(indice) != set(claves):
        raise ValueError("El texto híbrido histórico no corresponde a EXP-03")
    return [indice[k] for k in claves]


def _cargar_textos_nuevos(
    ruta: Path, nuevos: list[dict], seleccion: list[dict]
) -> tuple[list[str], list[dict], dict]:
    filas = json.loads(ruta.read_text(encoding="utf-8-sig"))
    if not isinstance(filas, list):
        raise ValueError("La caché OCR nueva debe ser una lista JSON")
    indice = {(fila["archivo"], int(fila["pagina"])): fila for fila in filas}
    claves_nuevas = {(fila["archivo"], int(fila["pagina"])) for fila in nuevos}
    if len(indice) != len(filas) or set(indice) != claves_nuevas:
        raise ValueError("La caché OCR nueva no corresponde al Ground Truth")
    elegidas = [indice[(fila["archivo"], int(fila["pagina"]))] for fila in seleccion]
    cobertura = {
        "estados": dict(Counter(fila["estado"] for fila in elegidas)),
        "paginas_con_senal_textual": sum(bool(fila["texto_pagina"].strip()) for fila in elegidas),
        "paginas_evaluadas": len(elegidas),
    }
    return [fila["texto_pagina"] for fila in elegidas], elegidas, cobertura


def _cargar_linea_base(ruta: Path) -> dict[tuple[str, str], dict]:
    contenido = json.loads(ruta.read_text(encoding="utf-8-sig"))
    return {
        (fila["tarea"], fila["modalidad"]): fila
        for fila in contenido["resultados"]
    }


def _evaluar_ablacion(
    antiguos: list[dict],
    seleccion: list[dict],
    textos_antiguos_nativos: list[str],
    textos_antiguos_hibridos: list[str],
    textos_nuevos_nativos: list[str],
    textos_nuevos_hibridos: list[str],
    train_imagen: np.ndarray,
    test_imagen: np.ndarray,
) -> list[dict]:
    """Separa el efecto del OCR histórico del OCR aplicado a EXP-11."""
    fuentes_train = {
        "nativo": textos_antiguos_nativos,
        "hibrido": textos_antiguos_hibridos,
    }
    fuentes_test = {
        "nativo": textos_nuevos_nativos,
        "hibrido": textos_nuevos_hibridos,
    }
    resultados = []

    for nombre_train, textos_train in fuentes_train.items():
        vectorizador = TfidfVectorizer(
            lowercase=True,
            strip_accents="unicode",
            ngram_range=(1, 2),
            min_df=2,
            max_features=20000,
            sublinear_tf=True,
        )
        vectorizador.fit([texto for texto in textos_train if texto.strip()])
        matriz_train_texto = vectorizador.transform(textos_train)
        matrices_test_texto = {
            nombre: vectorizador.transform(textos)
            for nombre, textos in fuentes_test.items()
        }

        for tarea in TARGETS:
            clases = sorted(
                {clase for fila in antiguos for clase in json.loads(fila[tarea])}
            )
            binarizador = MultiLabelBinarizer(classes=clases)
            y_train = binarizador.fit_transform(
                [json.loads(fila[tarea]) for fila in antiguos]
            ).astype(bool)
            y_test = binarizador.transform(
                [fila[tarea] for fila in seleccion]
            ).astype(bool)

            for modalidad in ("texto", "texto_mas_imagen"):
                matriz_train = (
                    matriz_train_texto
                    if modalidad == "texto"
                    else hstack(
                        (matriz_train_texto, csr_matrix(train_imagen)), format="csr"
                    )
                )
                modelo = OneVsRestClassifier(
                    LogisticRegression(
                        C=1.0,
                        class_weight="balanced",
                        solver="liblinear",
                        max_iter=3000,
                        random_state=0,
                    )
                )
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore",
                        category=UserWarning,
                        message="Label .* is present in all training examples",
                    )
                    modelo.fit(matriz_train, y_train)

                for nombre_test, matriz_test_texto in matrices_test_texto.items():
                    matriz_test = (
                        matriz_test_texto
                        if modalidad == "texto"
                        else hstack(
                            (matriz_test_texto, csr_matrix(test_imagen)), format="csr"
                        )
                    )
                    pred = modelo.predict_proba(matriz_test) >= 0.5
                    if modalidad == "texto":
                        presencia = np.array(
                            [bool(texto.strip()) for texto in fuentes_test[nombre_test]]
                        )
                        pred[~presencia] = False
                    resultados.append({
                        "tarea": tarea,
                        "modalidad": modalidad,
                        "texto_entrenamiento": nombre_train,
                        "texto_evaluacion": nombre_test,
                        **metricas(y_test, pred),
                    })
    return resultados


def evaluar(
    data_dir: Path,
    etiquetas: Path,
    archivo_zip: Path,
    texto_hibrido: Path,
    linea_base: Path,
    salida: Path,
) -> dict:
    antiguos, textos_antiguos_nativos, imagen_antigua, nuevos = cargar_datos(
        data_dir, etiquetas
    )
    seleccion, conflictos = escoger_paginas(nuevos)
    textos_antiguos = _cargar_textos_antiguos(data_dir, antiguos)
    textos_nuevos, registros_texto, cobertura = _cargar_textos_nuevos(
        texto_hibrido, nuevos, seleccion
    )
    textos_nuevos_nativos, imagen_nueva = textos_e_imagenes(seleccion, archivo_zip)

    presencia_nueva = np.array([bool(texto.strip()) for texto in textos_nuevos])
    vectorizador = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        min_df=2,
        max_features=20000,
        sublinear_tf=True,
    )
    vectorizador.fit([texto for texto in textos_antiguos if texto.strip()])
    train_text = vectorizador.transform(textos_antiguos)
    test_text = vectorizador.transform(textos_nuevos)

    escalador = StandardScaler()
    train_imagen = normalize(escalador.fit_transform(imagen_antigua))
    test_imagen = normalize(escalador.transform(imagen_nueva))
    modalidades = {
        "texto_pdf_mas_ocr": (train_text, test_text),
        "imagen_sola": (csr_matrix(train_imagen), csr_matrix(test_imagen)),
        "texto_ocr_mas_imagen": (
            hstack((train_text, csr_matrix(train_imagen)), format="csr"),
            hstack((test_text, csr_matrix(test_imagen)), format="csr"),
        ),
    }
    comparables = {
        "texto_pdf_mas_ocr": "texto_pdf",
        "imagen_sola": "imagen_sola",
        "texto_ocr_mas_imagen": "texto_pdf_mas_imagen",
    }
    base = _cargar_linea_base(linea_base)
    fuentes = sorted({fila["proyecto_id"] for fila in seleccion})

    resultados = []
    predicciones = []
    por_clase = []
    for tarea in TARGETS:
        clases = sorted(
            {clase for fila in antiguos for clase in json.loads(fila[tarea])}
        )
        desconocidas = sorted(
            {clase for fila in seleccion for clase in fila[tarea]} - set(clases)
        )
        if desconocidas:
            raise ValueError(f"Etiquetas desconocidas para {tarea}: {desconocidas}")
        binarizador = MultiLabelBinarizer(classes=clases)
        y_antiguo = binarizador.fit_transform(
            [json.loads(fila[tarea]) for fila in antiguos]
        ).astype(bool)
        y_nuevo = binarizador.transform(
            [fila[tarea] for fila in seleccion]
        ).astype(bool)

        for nombre, (train, test) in modalidades.items():
            modelo = OneVsRestClassifier(
                LogisticRegression(
                    C=1.0,
                    class_weight="balanced",
                    solver="liblinear",
                    max_iter=3000,
                    random_state=0,
                )
            )
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    category=UserWarning,
                    message="Label .* is present in all training examples",
                )
                modelo.fit(train, y_antiguo)
            pred = modelo.predict_proba(test) >= 0.5
            if nombre == "texto_pdf_mas_ocr":
                pred[~presencia_nueva] = False
            globales = metricas(y_nuevo, pred)
            por_fuente = []
            for fuente in fuentes:
                indices = [
                    i for i, fila in enumerate(seleccion)
                    if fila["proyecto_id"] == fuente
                ]
                por_fuente.append({
                    "fuente": fuente,
                    "paginas": len(indices),
                    **metricas(y_nuevo[indices], pred[indices]),
                })
            base_f1 = base[(tarea, comparables[nombre])]["f1_micro"]
            resultado = {
                "tarea": tarea,
                "modalidad": nombre,
                "modalidad_linea_base": comparables[nombre],
                "paginas": len(seleccion),
                "paginas_con_senal_textual": int(presencia_nueva.sum()),
                "f1_linea_base": base_f1,
                "delta_f1_vs_linea_base": round(globales["f1_micro"] - base_f1, 4),
                "f1_promedio_por_fuente": round(
                    sum(fila["f1_micro"] for fila in por_fuente) / len(por_fuente), 4
                ),
                **globales,
                "por_fuente": por_fuente,
            }
            resultados.append(resultado)

            for j, clase in enumerate(clases):
                soporte = int(y_nuevo[:, j].sum())
                if soporte:
                    por_clase.append({
                        "tarea": tarea,
                        "modalidad": nombre,
                        "clase": clase,
                        "soporte": soporte,
                        **metricas(y_nuevo[:, j], pred[:, j]),
                    })
            for i, fila in enumerate(seleccion):
                esperadas = sorted(clases[j] for j in np.flatnonzero(y_nuevo[i]))
                obtenidas = sorted(clases[j] for j in np.flatnonzero(pred[i]))
                predicciones.append({
                    "archivo": fila["archivo"],
                    "pagina": fila["pagina"],
                    "fuente": fila["proyecto_id"],
                    "tarea": tarea,
                    "modalidad": nombre,
                    "real": esperadas,
                    "predicho": obtenidas,
                    "faltantes": sorted(set(esperadas) - set(obtenidas)),
                    "sobrantes": sorted(set(obtenidas) - set(esperadas)),
                    "fuente_texto": registros_texto[i]["estado"],
                })
            print(
                tarea,
                nombre,
                "F1:",
                globales["f1_micro"],
                "delta:",
                resultado["delta_f1_vs_linea_base"],
                flush=True,
            )

    ablacion = _evaluar_ablacion(
        antiguos,
        seleccion,
        textos_antiguos_nativos,
        textos_antiguos,
        textos_nuevos_nativos,
        textos_nuevos,
        train_imagen,
        test_imagen,
    )
    indice_ablacion = {
        (
            fila["tarea"],
            fila["modalidad"],
            fila["texto_entrenamiento"],
            fila["texto_evaluacion"],
        ): fila["f1_micro"]
        for fila in ablacion
    }
    efectos = []
    for tarea in TARGETS:
        for modalidad in ("texto", "texto_mas_imagen"):
            base_f1 = indice_ablacion[(tarea, modalidad, "nativo", "nativo")]
            efectos.append({
                "tarea": tarea,
                "modalidad": modalidad,
                "f1_base_nativo": base_f1,
                "efecto_ocr_solo_en_evaluacion": round(
                    indice_ablacion[(tarea, modalidad, "nativo", "hibrido")]
                    - base_f1,
                    4,
                ),
                "efecto_ocr_solo_en_entrenamiento": round(
                    indice_ablacion[(tarea, modalidad, "hibrido", "nativo")]
                    - base_f1,
                    4,
                ),
                "efecto_metodo_hibrido_completo": round(
                    indice_ablacion[(tarea, modalidad, "hibrido", "hibrido")]
                    - base_f1,
                    4,
                ),
            })

    salida.mkdir(parents=True, exist_ok=True)
    auditoria = {
        "dataset_antiguo_paginas": len(antiguos),
        "entrenamiento_textual": "EXP-09: texto PDF y OCR histórico; no incluye EXP-11",
        "nuevas_paginas_exportadas": len(nuevos),
        "nuevas_paginas_evaluadas": len(seleccion),
        "excluidas_por_conflicto_duplicado": conflictos,
        "politica_ocr_nueva": "OCR solo cuando el texto PDF nativo está vacío",
        "umbral_clasificacion_fijo": 0.5,
        "cobertura_textual": cobertura,
        "resultados": resultados,
        "ablacion_ocr": ablacion,
        "efectos_ocr": efectos,
        "por_clase": por_clase,
    }
    (salida / "EXP12_EVALUACION.json").write_text(
        json.dumps(auditoria, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (salida / "EXP12_PREDICCIONES.json").write_text(
        json.dumps(predicciones, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lineas = [
        "# EXP-12 — OCR controlado sobre la evaluación externa",
        "",
        f"Entrenamiento: {len(antiguos)} páginas anteriores con el texto híbrido de EXP-09. "
        f"Evaluación: {len(seleccion)} páginas únicas de EXP-11.",
        "EXP-11 no se utilizó para entrenar, elegir rasgos, modificar etiquetas ni ajustar el umbral 0,5.",
        "",
        "## Cobertura textual",
        "",
        f"- Páginas evaluadas: {cobertura['paginas_evaluadas']}.",
        f"- Páginas con señal textual final: {cobertura['paginas_con_senal_textual']}.",
        "- Estados: " + ", ".join(
            f"{estado}={cantidad}" for estado, cantidad in sorted(cobertura["estados"].items())
        ) + ".",
        "",
        "## Comparación con la línea base sin OCR nuevo",
        "",
        "| Tarea | Entrada | F1 | F1 base | Diferencia |",
        "|---|---|---:|---:|---:|",
    ]
    for fila in resultados:
        lineas.append(
            f"| {fila['tarea']} | {fila['modalidad']} | {fila['f1_micro']:.3f} | "
            f"{fila['f1_linea_base']:.3f} | {fila['delta_f1_vs_linea_base']:+.3f} |"
        )
    lineas += [
        "",
        "## Ablación 2×2",
        "",
        "Esta tabla separa el efecto de usar OCR en el corpus de entrenamiento del efecto "
        "de recuperar las páginas vacías de EXP-11.",
        "",
        "| Tarea | Entrada | Texto de entrenamiento | Texto de evaluación | F1 |",
        "|---|---|---|---|---:|",
    ]
    for fila in ablacion:
        lineas.append(
            f"| {fila['tarea']} | {fila['modalidad']} | {fila['texto_entrenamiento']} | "
            f"{fila['texto_evaluacion']} | {fila['f1_micro']:.3f} |"
        )
    lineas += [
        "",
        "## Lectura de la ablación",
        "",
        "Las diferencias siguientes usan como referencia entrenamiento nativo y evaluación nativa. "
        "Son diagnósticas: no se usan para elegir una variante sobre este mismo conjunto externo.",
        "",
        "| Tarea | Entrada | OCR solo en evaluación | OCR solo en entrenamiento | Método híbrido completo |",
        "|---|---|---:|---:|---:|",
    ]
    for fila in efectos:
        lineas.append(
            f"| {fila['tarea']} | {fila['modalidad']} | "
            f"{fila['efecto_ocr_solo_en_evaluacion']:+.3f} | "
            f"{fila['efecto_ocr_solo_en_entrenamiento']:+.3f} | "
            f"{fila['efecto_metodo_hibrido_completo']:+.3f} |"
        )
    lineas += [
        "",
        "**Conclusión:** el método híbrido completo mejora el F1 de las tres tareas, "
        "pero el aporte no es uniforme. En texto solo, el OCR nuevo ayuda a las tres; "
        "el OCR histórico ayuda con fuerza a disciplinas, pero aislado perjudica roles y contenidos. "
        "En la fusión con imagen, el OCR nuevo reduce levemente disciplinas cuando el entrenamiento "
        "sigue siendo nativo. Por eso todavía no conviene convertir esta combinación en una regla "
        "única de producción sin validarla en otro grupo de proyectos.",
        "",
        "## Criterio",
        "",
        "- Se preserva cualquier texto PDF no vacío; OCR no lo reemplaza ni lo mezcla.",
        "- Las páginas vacías se procesan con Tesseract, 150 dpi, búsqueda de orientación "
        "y los mismos umbrales fijados en EXP-09.",
        "- La modalidad visual se repite como control: sus diferencias deberían ser nulas.",
        "- Una mejora aislada no autoriza reentrenar con EXP-11; este conjunto continúa siendo externo.",
        "",
        "## Clases con más errores · texto OCR más imagen",
        "",
        "Solo se incluyen clases con cinco o más ejemplos; hasta cinco por tarea.",
        "",
        "| Tarea | Clase | Soporte | F1 |",
        "|---|---|---:|---:|",
    ]
    for tarea in TARGETS:
        deficientes = sorted(
            (
                fila for fila in por_clase
                if fila["tarea"] == tarea
                and fila["modalidad"] == "texto_ocr_mas_imagen"
                and fila["soporte"] >= 5
            ),
            key=lambda fila: (fila["f1_micro"], -fila["soporte"], fila["clase"]),
        )[:5]
        for fila in deficientes:
            lineas.append(
                f"| {tarea} | {fila['clase']} | {fila['soporte']} | {fila['f1_micro']:.3f} |"
            )
    (salida / "EXP12_EVALUACION.md").write_text(
        "\n".join(lineas) + "\n", encoding="utf-8"
    )
    return auditoria


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=RAIZ / "Data")
    parser.add_argument("--etiquetas", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--texto-hibrido", type=Path, required=True)
    parser.add_argument(
        "--linea-base",
        type=Path,
        default=RAIZ / "Data/EXP_11_nuevos_proyectos/EXP11_EVALUACION.json",
    )
    parser.add_argument(
        "--salida", type=Path, default=RAIZ / "Data/EXP_12_ocr_externo"
    )
    args = parser.parse_args()
    resultado = evaluar(
        args.data_dir,
        args.etiquetas,
        args.zip,
        args.texto_hibrido,
        args.linea_base,
        args.salida,
    )
    print(f"Páginas evaluadas: {resultado['nuevas_paginas_evaluadas']}")


if __name__ == "__main__":
    main()

# EXP-05 — Baseline supervisado: Logistic Regression multilabel

## Objetivo
Evaluar un primer modelo supervisado simple sobre las mismas 474 páginas y el split oficial por proyecto de EXP-03.

## Modelo
Se entrenó un modelo Logistic Regression dentro de One-vs-Rest para cada etiqueta de cada una de las tres tareas multilabel. Se utilizó imputación mediana, estandarización y `class_weight="balanced"`. La decisión de etiqueta utiliza umbral fijo 0,5. No se ajustó el umbral con validation en este baseline.

## Variables
cantidad_palabras, cantidad_caracteres, cantidad_imagenes, tiene_texto, tiene_imagenes.

## Controles
- Split por proyecto: 26 train / 5 validation / 6 test.
- No se utilizan Ground Truth como feature.
- No se utiliza el nombre del archivo.
- Imputación y escalado se ajustan únicamente con train mediante Pipeline.
- Validation queda reservada para experimentos posteriores de selección/ajuste.

## Resultado
- disciplina: micro-F1=0.3130, macro-F1=0.2110, micro-precision=0.2228, micro-recall=0.5256, coverage=1.0000, hamming_loss=0.3622.
- rol_documental: micro-F1=0.4752, macro-F1=0.3405, micro-precision=0.3485, micro-recall=0.7468, coverage=1.0000, hamming_loss=0.4472.
- contenido: micro-F1=0.3251, macro-F1=0.2209, micro-precision=0.1974, micro-recall=0.9207, coverage=1.0000, hamming_loss=0.4415.

## Interpretación
Este experimento es una referencia supervisada inicial. No demuestra por sí solo que Logistic Regression sea el modelo final ni que supere reglas en todos los objetivos. La comparación válida se realizará con el mismo split y métricas.

# EXP-04 — Baseline 0B de reglas multilabel

## Objetivo
Construir la primera línea base predictiva válida usando únicamente contenido textual extraído de los PDFs y reglas de conocimiento de dominio, sin usar las etiquetas profesionales del Ground Truth para generar las predicciones.

## Unidad experimental
- Unidad de predicción: página.
- Unidad de independencia: proyecto.
- Dataset: 474 páginas, 37 proyectos, 278 PDFs.
- Evaluación: split oficial EXP-03 por proyecto.

## Targets multilabel
- Disciplina: arquitectura, estructura, sanitarias, electricidad, gas, implantacion_topografia, otra.
- Rol documental: planta, detalle, cuadro_planilla, corte, elevacion_fachada, isometrico, modelo_3d, implantacion, otro.
- Contenido: 40 etiquetas del Ground Truth.

## Construcción de reglas
Las reglas son listas explícitas de términos y expresiones de dominio. Cada coincidencia conserva evidencia textual de la página y un identificador implícito por etiqueta. Una página puede activar cero, una o varias etiquetas por target. Si no hay coincidencia, el sistema se abstiene para ese target.

## Restricciones científicas
- No se usa el nombre del archivo como feature predictiva.
- No se usa el Ground Truth para seleccionar términos ni ajustar umbrales.
- No se mezclan páginas del mismo proyecto entre train/validation/test.
- El Ground Truth se usa únicamente para evaluación.
- Los scores de coincidencias son conteos de reglas activadas; no son probabilidades.

## Métricas
Se reportan precision, recall y F1 micro/macro, F1 por etiqueta, Hamming loss, exact match, coverage y abstention. Coverage indica la proporción de páginas con al menos una predicción en el target; no sustituye precision/recall.

## Resultado global
- disciplina: micro-F1=0.4216; macro-F1=0.2287; coverage=0.3734; abstention=0.6266; exact-match=0.2173.
- rol: micro-F1=0.2314; macro-F1=0.1216; coverage=0.3291; abstention=0.6709; exact-match=0.0886.
- contenido: micro-F1=0.1547; macro-F1=0.0916; coverage=0.3734; abstention=0.6266; exact-match=0.0232.

## Interpretación
Este experimento sí es una línea base predictiva: emite etiquetas antes de consultar el Ground Truth. Su valor científico está en fijar un punto de comparación transparente y reproducible para el modelo supervisado posterior. Una regla puede tener alta precision y baja coverage, o viceversa; por eso ambas dimensiones se reportan.

## Artefactos
- EXP04_BASELINE0B_PREDICCIONES.csv
- EXP04_BASELINE0B_METRICAS.csv
- EXP04_BASELINE0B_METRICAS_POR_SPLIT.csv
- EXP04_BASELINE0B_METRICAS_POR_LABEL.csv
- EXP04_BASELINE0B_ERRORES_TEST.csv
- EXP04_BASELINE0B_CATALOGO_REGLAS.csv
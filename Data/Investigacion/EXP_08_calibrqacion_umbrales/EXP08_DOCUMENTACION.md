# EXP-08 — Calibración de umbrales de EXP-07

## Objetivo
Evaluar si seleccionar el umbral multilabel usando exclusivamente VALIDATION mejora el equilibrio precisión-recall de EXP-07 antes de evaluar una sola vez sobre TEST.

## Hipótesis
H-08: la calibración del umbral de decisión con VALIDATION puede modificar el equilibrio precisión-recall de EXP-07 y reducir errores asociados a una frontera fija de 0,5.

## Protocolo
- Se reutiliza exactamente el split de EXP-03: 26 proyectos train, 5 validation, 6 test.
- Se reutiliza el mismo vectorizador TF-IDF y los mismos modelos de EXP-07; no se reentrena con validation/test.
- Se calculan probabilidades en VALIDATION.
- Se evalúan umbrales de 0,01 a 0,99.
- Criterio principal: máximo micro-F1 en VALIDATION.
- Desempate: mayor macro-F1 y luego mayor micro-precision.
- Los umbrales seleccionados se congelan y se aplican a TEST sin volver a optimizar.
- No se utiliza TEST para elegir umbral.

## Umbrales seleccionados
{'disciplinas': np.float64(0.46), 'roles_documentales': np.float64(0.48000000000000004), 'contenidos': np.float64(0.47000000000000003)}

## Resultados
Ver EXP08_METRICAS.csv y EXP08_COMPARACION_FIXED05.csv.

## Comparación externa
EXP08_COMPARACION_EXP04_EXP05_EXP08.csv compara el TEST de EXP-08 con los valores publicados previamente para EXP-04 y EXP-05.

## Interpretación metodológica
La calibración de umbral es una etapa de decisión, no una nueva representación de datos ni un nuevo modelo. Su finalidad es estudiar cuánto depende el comportamiento multilabel de la frontera de decisión.

Un aumento de F1 en TEST no prueba por sí mismo que el modelo generalice mejor: el umbral fue seleccionado en VALIDATION y debe interpretarse junto con precision, recall, macro-F1, cobertura, Hamming loss y cardinalidad predicha.

## Reproducibilidad
Dataset: EXP-02 Ground Truth recuperado; split: EXP-03; seed histórica: 20260917; modelo base: EXP-07 TF-IDF + One-vs-Rest Logistic Regression.

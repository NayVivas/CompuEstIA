# EXP-06 — Comparación científica: reglas vs Logistic Regression

## Objetivo

Comparar el Baseline 0B de reglas multilabel (EXP-04) con Logistic Regression (EXP-05)
sobre exactamente los mismos proyectos de TEST del protocolo EXP-03.

## Resultado principal

| Tarea | Reglas micro-F1 | Logistic Regression micro-F1 | Δ micro-F1 | Reglas macro-F1 | Logistic Regression macro-F1 | Δ macro-F1 |
|---|---:|---:|---:|---:|---:|---:|
| disciplina | 0.3894 | 0.3130 | -0.0764 | 0.1207 | 0.2110 | +0.0903 |\n| rol_documental | 0.1667 | 0.4752 | +0.3085 | 0.0776 | 0.3405 | +0.2629 |\n| contenido | 0.1632 | 0.3251 | +0.1619 | 0.0839 | 0.2209 | +0.1370 |\n
## Hallazgos descriptivos

- Los dos sistemas se evalúan sobre el mismo TEST por proyecto.
- Logistic Regression emite predicciones para todas las páginas; las reglas pueden abstenerse.
- En disciplina, Logistic Regression aumenta recall pero reduce precision respecto de las reglas.
- En rol documental, Logistic Regression mejora micro-F1 respecto de las reglas.
- En contenido, Logistic Regression aumenta fuertemente recall, pero mantiene precision baja; esto indica sobrepredicción con las features actuales.
- Las reglas aportan trazabilidad directa mediante regla y evidencia textual.
- Logistic Regression todavía utiliza únicamente cinco variables agregadas; no incorpora el vocabulario de la página.

## Precaución con el análisis por etiqueta

El archivo de reglas disponible con métricas por etiqueta es agregado sobre todos los splits.
Por rigor, no se presenta como una métrica TEST por etiqueta. El análisis por etiqueta de EXP-06
usa ese archivo únicamente como contexto y mantiene separada la métrica TEST real de Logistic Regression.

## Decisión metodológica

El siguiente experimento debe ser **EXP-07: TF-IDF + Logistic Regression multilabel**.
Esto permite probar si la representación textual aporta información antes de aumentar la complejidad del algoritmo.

El vocabulario TF-IDF y cualquier transformación deberán ajustarse exclusivamente con TRAIN.
El split de proyectos permanecerá exactamente igual.

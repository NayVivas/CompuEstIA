# EXP-15 — Mejora trazable para el rol corte

La estrategia se eligió con el corpus histórico agrupado por fuente. EXP-11 se utiliza únicamente como benchmark auditado.

## Comparación histórica

| Estrategia | Precisión | Recall | F1 | F1 promedio por fuente | AUC |
|---|---:|---:|---:|---:|---:|
| tfidf_palabras | 0.333 | 0.010 | 0.019 | 0.083 | 0.400 |
| tfidf_caracteres | 0.000 | 0.000 | 0.000 | 0.000 | 0.492 |
| tfidf_palabras_mas_caracteres | 0.000 | 0.000 | 0.000 | 0.000 | 0.464 |
| regla_corte_literal_y_alias_pdf | 0.671 | 0.530 | 0.592 | 0.428 | — |

Estrategia seleccionada: **regla_corte_literal_y_alias_pdf**.

## Benchmark en EXP-11

| Estrategia | Precisión | Recall | F1 | TP | FP | FN |
|---|---:|---:|---:|---:|---:|---:|
| Modelo EXP-12 | 0.200 | 0.021 | 0.038 | 1 | 4 | 47 |
| Regla trazable | 0.809 | 0.354 | 0.493 | 17 | 4 | 31 |

## Regla

1. Buscar `corte` o `cortes` como palabra completa en el nombre del archivo.
2. Buscar la misma expresión en el texto PDF u OCR de la página.
3. Reconocer `&RUWH` como alias auditable de un PDF con texto codificado.
4. Devolver el origen y el fragmento que justifican la detección.

## Decisión

La regla mejora ampliamente el rol `corte` y es más trazable que los modelos probados. Debe generar un candidato visible para revisión, no modificar el Ground Truth automáticamente. Las páginas sin la palabra explícita todavía requieren una segunda etapa geométrica o visual.

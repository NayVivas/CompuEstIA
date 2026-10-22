# EXP-07 — Auditoría de errores

## Objetivo
Analizar los errores del modelo TF-IDF + Logistic Regression en el TEST de 6 proyectos, sin modificar el modelo ni usar TEST para entrenamiento.

## Hallazgos principales

- **contenidos**: 71/71 páginas con al menos un error; exact-match=0.000; media predicha=18.00; media real=4.62; error medio=16.06 etiquetas.
- **disciplinas**: 64/71 páginas con al menos un error; exact-match=0.099; media predicha=2.39; media real=1.10; error medio=2.65 etiquetas.
- **roles_documentales**: 65/71 páginas con al menos un error; exact-match=0.085; media predicha=3.99; media real=2.17; error medio=2.80 etiquetas.

### Sobrepredicción observada
**contenidos**
- Falsos positivos más frecuentes: [('cubiertas', 45), ('canerias_sanitarias', 43), ('cloacal', 42), ('regulacion_gas', 42), ('artefactos_sanitarios', 42), ('baja_tension', 42), ('tomacorrientes', 42), ('pluvial', 42)]
- Falsos negativos más frecuentes: [('armaduras_acero', 19), ('escaleras_estructurales', 13), ('columnas_pilares', 12), ('losas_forjados', 12), ('vigas', 11), ('fundaciones', 7), ('cubiertas_estructurales', 6), ('elementos_estructurales_generales', 6)]
**disciplinas**
- Falsos positivos más frecuentes: [('gas', 42), ('sanitarias', 42), ('electricidad', 42), ('arquitectura', 14)]
- Falsos negativos más frecuentes: [('estructura', 26), ('arquitectura', 22)]
**roles_documentales**
- Falsos positivos más frecuentes: [('isometrico', 41), ('elevacion_fachada', 41), ('corte', 34), ('cuadro_planilla', 29), ('planta', 18), ('detalle', 1)]
- Falsos negativos más frecuentes: [('detalle', 24), ('elevacion_fachada', 6), ('planta', 3), ('cuadro_planilla', 1), ('isometrico', 1)]

## Interpretación metodológica
La auditoría muestra que el problema principal de EXP-07 no es únicamente capacidad predictiva: el umbral 0,5 combinado con clases multilabel y una representación textual generalista produce sobrepredicción en etiquetas frecuentes o lexicalmente correlacionadas. En particular, roles y contenidos presentan páginas donde se activan muchas etiquetas simultáneamente. Esto justifica estudiar calibración/umbrales y representación de contexto antes de aumentar la complejidad del modelo.

## Control de leakage
El análisis utiliza exclusivamente predicciones del TEST ya generadas y el texto cacheado. No se reajusta el vectorizador, no se entrena con TEST y no se modifica el split.

## Próximo experimento metodológicamente justificado
EXP-08: calibración/selección de umbrales multilabel usando únicamente VALIDATION, y evaluación final única sobre TEST. El objetivo es comprobar si la sobrepredicción disminuye sin sacrificar de forma descontrolada el recall.

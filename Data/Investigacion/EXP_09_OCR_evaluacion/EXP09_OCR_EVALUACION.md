# EXP-09 — Prueba exploratoria de OCR

## Cobertura

Texto PDF: 202/474 páginas. OCR aceptado: 255. OCR de baja calidad: 17.
Prueba ejecutada con idioma `eng` a 150 dpi. Para español, probar el paquete `spa` y revisar la calidad en una muestra.

## Comparación de clasificación

Mismo TF-IDF (palabras, unigramas y bigramas) y regresión logística multietiqueta con umbral fijo 0,5 en ambas modalidades. Se reentrena dejando afuera una familia sugerida cada vez; el vocabulario se ajusta solo con las páginas de entrenamiento de cada fold. Sin texto disponible, el modelo se abstiene.

| Objetivo | Entrada | Páginas con señal | F1 micro global | F1 promedio por fuente |
|---|---|---:|---:|---:|
| disciplinas | texto_pdf | 202/474 | 0.261 | 0.465 |
| disciplinas | texto_pdf_mas_ocr | 457/474 | 0.398 | 0.523 |
| roles_documentales | texto_pdf | 202/474 | 0.273 | 0.499 |
| roles_documentales | texto_pdf_mas_ocr | 457/474 | 0.589 | 0.631 |
| contenidos | texto_pdf | 202/474 | 0.028 | 0.082 |
| contenidos | texto_pdf_mas_ocr | 457/474 | 0.188 | 0.284 |

La familia sugerida `Proyecto_7` agrupa 271 páginas y domina el F1 global por número de páginas. Su F1 con OCR es: disciplinas=0.309, roles_documentales=0.577, contenidos=0.101.

## Interpretación

- OCR recupera señal en PDF escaneados; en este ensayo mejora las tres tareas, pero `contenidos` sigue lejos de ser confiable.
- La procedencia se infirió del nombre `Proyecto_7-*.pdf` y debe ser confirmada. Solo hay ocho familias sugeridas y clases con pocos ejemplos.
- Este análisis es exploratorio; el TEST histórico ya se había inspeccionado. Hace falta evaluar después en fuentes nuevas independientes.
- Próximo experimento: medir imágenes de página o características visuales junto con OCR, sobre todo en las 17 páginas con OCR insuficiente y para la tarea `contenidos`. Comparar por fuente y reportar cobertura además de F1.

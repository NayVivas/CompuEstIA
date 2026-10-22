# EXP-10 — Imagen de página y texto OCR

Validación exploratoria dejando una de ocho fuentes sugeridas afuera en cada evaluación. Las fuentes se infieren por nombres de PDF y requieren confirmación. Se usa siempre el mismo umbral fijo 0,5. El TEST histórico ya se había inspeccionado: este ensayo no es una prueba final independiente.

Visualización: render PDF reducido a 160 píxeles en el lado mayor; densidad de tinta y bordes por cuadrícula. El escalador y TF-IDF se ajustan exclusivamente sobre las otras fuentes. La imagen no requiere OCR ni un modelo de visión preentrenado.

| Objetivo | Entrada | Páginas con señal | F1 micro global | F1 promedio por fuente |
|---|---|---:|---:|---:|
| disciplinas | ocr_solo | 457/474 | 0.398 | 0.523 |
| disciplinas | solo_imagen | 474/474 | 0.368 | 0.406 |
| disciplinas | ocr_mas_imagen | 474/474 | 0.423 | 0.486 |
| roles_documentales | ocr_solo | 457/474 | 0.589 | 0.631 |
| roles_documentales | solo_imagen | 474/474 | 0.435 | 0.349 |
| roles_documentales | ocr_mas_imagen | 474/474 | 0.489 | 0.416 |
| contenidos | ocr_solo | 457/474 | 0.188 | 0.284 |
| contenidos | solo_imagen | 474/474 | 0.228 | 0.222 |
| contenidos | ocr_mas_imagen | 474/474 | 0.199 | 0.267 |

## Lectura del resultado

La fusión no mejora simultáneamente el F1 global y el F1 promedio por fuente en ninguna tarea.
Imagen sola mejora el F1 global de contenidos, de 0.188 a 0.228; revisar si la media por fuente confirma esa mejora.

Las 271 páginas de la familia `Proyecto_7` pesan mucho en el F1 global. Revisar también las métricas por fuente antes de decidir si la imagen agrega información útil.
Las páginas casi sin texto del catálogo incluyen cortes e isométricos con trazos reconocibles. Un resumen de densidad y bordes de 160 píxeles no identifica aún objetos específicos como columnas o armaduras.

Estos resultados no acreditan generalización a proyectos nuevos. El experimento se diseñó después de inspeccionar resultados del TEST anterior y el dataset contiene muy pocas fuentes independientes. No habilitar automáticamente la fusión en el producto. Validar la procedencia de los planos y reunir nuevas obras antes de elegir modelo.

# EXP-12 — OCR controlado sobre la evaluación externa

Entrenamiento: 474 páginas anteriores con el texto híbrido de EXP-09. Evaluación: 146 páginas únicas de EXP-11.
EXP-11 no se utilizó para entrenar, elegir rasgos, modificar etiquetas ni ajustar el umbral 0,5.

## Cobertura textual

- Páginas evaluadas: 146.
- Páginas con señal textual final: 146.
- Estados: ocr_con_texto=10, texto_pdf=136.

## Comparación con la línea base sin OCR nuevo

| Tarea | Entrada | F1 | F1 base | Diferencia |
|---|---|---:|---:|---:|
| disciplinas | texto_pdf_mas_ocr | 0.605 | 0.471 | +0.133 |
| disciplinas | imagen_sola | 0.446 | 0.446 | +0.000 |
| disciplinas | texto_ocr_mas_imagen | 0.550 | 0.511 | +0.039 |
| roles_documentales | texto_pdf_mas_ocr | 0.537 | 0.534 | +0.003 |
| roles_documentales | imagen_sola | 0.390 | 0.390 | +0.000 |
| roles_documentales | texto_ocr_mas_imagen | 0.489 | 0.459 | +0.030 |
| contenidos | texto_pdf_mas_ocr | 0.273 | 0.204 | +0.069 |
| contenidos | imagen_sola | 0.214 | 0.214 | +0.000 |
| contenidos | texto_ocr_mas_imagen | 0.297 | 0.236 | +0.061 |

## Ablación 2×2

Esta tabla separa el efecto de usar OCR en el corpus de entrenamiento del efecto de recuperar las páginas vacías de EXP-11.

| Tarea | Entrada | Texto de entrenamiento | Texto de evaluación | F1 |
|---|---|---|---|---:|
| disciplinas | texto | nativo | nativo | 0.471 |
| disciplinas | texto | nativo | hibrido | 0.515 |
| disciplinas | texto_mas_imagen | nativo | nativo | 0.511 |
| disciplinas | texto_mas_imagen | nativo | hibrido | 0.506 |
| roles_documentales | texto | nativo | nativo | 0.534 |
| roles_documentales | texto | nativo | hibrido | 0.552 |
| roles_documentales | texto_mas_imagen | nativo | nativo | 0.459 |
| roles_documentales | texto_mas_imagen | nativo | hibrido | 0.462 |
| contenidos | texto | nativo | nativo | 0.204 |
| contenidos | texto | nativo | hibrido | 0.247 |
| contenidos | texto_mas_imagen | nativo | nativo | 0.236 |
| contenidos | texto_mas_imagen | nativo | hibrido | 0.252 |
| disciplinas | texto | hibrido | nativo | 0.554 |
| disciplinas | texto | hibrido | hibrido | 0.605 |
| disciplinas | texto_mas_imagen | hibrido | nativo | 0.555 |
| disciplinas | texto_mas_imagen | hibrido | hibrido | 0.550 |
| roles_documentales | texto | hibrido | nativo | 0.503 |
| roles_documentales | texto | hibrido | hibrido | 0.537 |
| roles_documentales | texto_mas_imagen | hibrido | nativo | 0.476 |
| roles_documentales | texto_mas_imagen | hibrido | hibrido | 0.489 |
| contenidos | texto | hibrido | nativo | 0.187 |
| contenidos | texto | hibrido | hibrido | 0.273 |
| contenidos | texto_mas_imagen | hibrido | nativo | 0.257 |
| contenidos | texto_mas_imagen | hibrido | hibrido | 0.297 |

## Lectura de la ablación

Las diferencias siguientes usan como referencia entrenamiento nativo y evaluación nativa. Son diagnósticas: no se usan para elegir una variante sobre este mismo conjunto externo.

| Tarea | Entrada | OCR solo en evaluación | OCR solo en entrenamiento | Método híbrido completo |
|---|---|---:|---:|---:|
| disciplinas | texto | +0.043 | +0.083 | +0.133 |
| disciplinas | texto_mas_imagen | -0.005 | +0.044 | +0.039 |
| roles_documentales | texto | +0.017 | -0.031 | +0.003 |
| roles_documentales | texto_mas_imagen | +0.003 | +0.017 | +0.030 |
| contenidos | texto | +0.043 | -0.017 | +0.069 |
| contenidos | texto_mas_imagen | +0.015 | +0.020 | +0.061 |

**Conclusión:** el método híbrido completo mejora el F1 de las tres tareas, pero el aporte no es uniforme. En texto solo, el OCR nuevo ayuda a las tres; el OCR histórico ayuda con fuerza a disciplinas, pero aislado perjudica roles y contenidos. En la fusión con imagen, el OCR nuevo reduce levemente disciplinas cuando el entrenamiento sigue siendo nativo. Por eso todavía no conviene convertir esta combinación en una regla única de producción sin validarla en otro grupo de proyectos.

## Criterio

- Se preserva cualquier texto PDF no vacío; OCR no lo reemplaza ni lo mezcla.
- Las páginas vacías se procesan con Tesseract, 150 dpi, búsqueda de orientación y los mismos umbrales fijados en EXP-09.
- La modalidad visual se repite como control: sus diferencias deberían ser nulas.
- Una mejora aislada no autoriza reentrenar con EXP-11; este conjunto continúa siendo externo.

## Clases con más errores · texto OCR más imagen

Solo se incluyen clases con cinco o más ejemplos; hasta cinco por tarea.

| Tarea | Clase | Soporte | F1 |
|---|---|---:|---:|
| disciplinas | implantacion_topografia | 14 | 0.000 |
| disciplinas | sanitarias | 14 | 0.000 |
| disciplinas | electricidad | 7 | 0.000 |
| disciplinas | arquitectura | 62 | 0.594 |
| disciplinas | estructura | 67 | 0.654 |
| roles_documentales | corte | 48 | 0.000 |
| roles_documentales | elevacion_fachada | 11 | 0.250 |
| roles_documentales | cuadro_planilla | 14 | 0.357 |
| roles_documentales | planta | 91 | 0.616 |
| roles_documentales | detalle | 62 | 0.649 |
| contenidos | terreno | 14 | 0.000 |
| contenidos | pluvial | 8 | 0.000 |
| contenidos | agua_caliente | 7 | 0.000 |
| contenidos | agua_fria | 7 | 0.000 |
| contenidos | baja_tension | 7 | 0.000 |

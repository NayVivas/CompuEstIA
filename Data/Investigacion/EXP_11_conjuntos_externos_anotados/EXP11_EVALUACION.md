# EXP-11 — Primera evaluación en proyectos nuevos

Entrenamiento: 474 páginas del corpus anterior. Evaluación: datos nuevos, sin usarlos para ajustar el modelo ni el umbral.
Etiquetas exportadas: 147; páginas evaluadas: 146.
Conflictos en páginas visualmente idénticas: 0 grupos. Evidencias profesionales vacías: 147.
Las fuentes nuevas son carpetas provisionales; aún hay que verificar que sean obras independientes.

| Tarea | Entrada | F1 micro | F1 medio por carpeta | Páginas con texto PDF |
|---|---|---:|---:|---:|
| disciplinas | texto_pdf | 0.471 | 0.472 | 136/146 |
| disciplinas | imagen_sola | 0.446 | 0.438 | 136/146 |
| disciplinas | texto_pdf_mas_imagen | 0.511 | 0.528 | 136/146 |
| roles_documentales | texto_pdf | 0.534 | 0.514 | 136/146 |
| roles_documentales | imagen_sola | 0.390 | 0.386 | 136/146 |
| roles_documentales | texto_pdf_mas_imagen | 0.459 | 0.455 | 136/146 |
| contenidos | texto_pdf | 0.204 | 0.205 | 136/146 |
| contenidos | imagen_sola | 0.214 | 0.215 | 136/146 |
| contenidos | texto_pdf_mas_imagen | 0.236 | 0.236 | 136/146 |

## Observaciones

- Se usa TF-IDF con texto PDF nativo, rasgos de imagen simples, regresión logística y umbral 0,5. No hay OCR nuevo en esta corrida: las páginas sin texto PDF aportan solo imagen en las modalidades visuales.
- Esta medición es un diagnóstico experimental reproducible, no una métrica del clasificador desplegado en FastAPI. Su vocabulario y parámetros se ajustaron solo con el corpus anterior; los datos nuevos se usaron exclusivamente para evaluar.
- Para evaluar la metodología anterior con OCR habría que generar OCR para las páginas nuevas con calidad comprobada y repetir el ensayo sin cambiar etiquetas ni umbral.
- Revisar los conflictos y registrar evidencia profesional antes de presentar estas anotaciones como Ground Truth final.


## Clases con más errores · texto PDF más imagen

Solo clases con cinco o más ejemplos evaluados; se muestran hasta cinco por tarea, ordenadas primero por F1 y luego por soporte.

| Tarea | Clase | Páginas con la clase | F1 |
|---|---|---:|---:|
| disciplinas | implantacion_topografia | 14 | 0.000 |
| disciplinas | sanitarias | 14 | 0.000 |
| disciplinas | electricidad | 7 | 0.154 |
| disciplinas | arquitectura | 62 | 0.566 |
| disciplinas | estructura | 67 | 0.629 |
| roles_documentales | corte | 48 | 0.000 |
| roles_documentales | cuadro_planilla | 14 | 0.216 |
| roles_documentales | elevacion_fachada | 11 | 0.270 |
| roles_documentales | planta | 91 | 0.593 |
| roles_documentales | detalle | 62 | 0.643 |
| contenidos | terreno | 14 | 0.000 |
| contenidos | pluvial | 8 | 0.000 |
| contenidos | agua_caliente | 7 | 0.000 |
| contenidos | agua_fria | 7 | 0.000 |
| contenidos | cloacal | 7 | 0.000 |

## Resultados por carpeta · texto PDF más imagen

| Carpeta | Disciplinas | Roles | Contenidos |
|---|---:|---:|---:|
| Proyecto_01 | 0.593 | 0.524 | 0.143 |
| Proyecto_02 | 0.769 | 0.486 | 0.527 |
| Proyecto_03 | 0.316 | 0.333 | 0.295 |
| Proyecto_04 | 0.412 | 0.462 | 0.275 |
| Proyecto_05 | 0.424 | 0.258 | 0.034 |
| Proyecto_06 | 0.338 | 0.571 | 0.086 |
| Proyecto_07 | 0.400 | 0.452 | 0.175 |
| Proyecto_08 | 0.897 | 0.353 | 0.486 |
| Proyecto_09 | 0.783 | 0.364 | 0.360 |
| Proyecto_10 | 0.250 | 0.636 | 0.065 |
| Proyecto_11 | 0.625 | 0.562 | 0.154 |

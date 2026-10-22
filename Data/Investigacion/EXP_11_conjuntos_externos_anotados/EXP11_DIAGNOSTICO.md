# EXP-11 — Inventario de nuevos proyectos

ZIP: `Nuevos_Proyectos(1).zip`. Se encontraron **11 carpetas**, **147 PDF** y **147 páginas**.
La carpeta conserva la procedencia provisional; no prueba por sí misma que se trate de una obra independiente.

| Carpeta | PDF | Páginas con ≥10 palabras PDF | 1–9 palabras | Sin texto PDF |
|---|---:|---:|---:|---:|---:|
| Proyecto_01 | 16 | 16 | 16 | 0 | 0 |
| Proyecto_02 | 11 | 11 | 11 | 0 | 0 |
| Proyecto_03 | 9 | 9 | 9 | 0 | 0 |
| Proyecto_04 | 16 | 16 | 16 | 0 | 0 |
| Proyecto_05 | 13 | 13 | 10 | 1 | 2 |
| Proyecto_06 | 30 | 30 | 30 | 0 | 0 |
| Proyecto_07 | 11 | 11 | 11 | 0 | 0 |
| Proyecto_08 | 15 | 15 | 15 | 0 | 0 |
| Proyecto_09 | 11 | 11 | 3 | 0 | 8 |
| Proyecto_10 | 5 | 5 | 5 | 0 | 0 |
| Proyecto_11 | 10 | 10 | 9 | 1 | 0 |
| **Total** | **147** | **147** | **135** | **2** | **10** |

La columna de ≥10 palabras mide solo texto extraíble del PDF; no certifica legibilidad ni calidad semántica. 'Sin texto PDF' indica que la extracción directa no obtuvo palabras. La página puede contener texto dentro de una imagen y requerir OCR.
Las pistas de contenido en el inventario proceden del texto y del nombre; no son etiquetas verificadas.
En `Proyecto_09`, 8 de 11 páginas no tienen texto PDF; revisar OCR sobre la página renderizada, incluso cuando no haya imágenes incrustadas en el archivo.

## Duplicados y lectura

PDF idénticos dentro del ZIP: 0 grupos; PDF idénticos al ZIP anterior: 0; páginas iguales al renderizar a 256 píxeles: 1 grupos; archivos con errores: 0.
La ausencia de PDF idénticos no descarta copias de un mismo plano exportadas de otra manera ni obras compartidas.
Al comparar los renders de 147 páginas nuevas con 477 anteriores a 256 px, coincidieron exactamente 0. Cambios de escala o edición pueden impedir una coincidencia incluso entre copias del mismo plano.
- Mismo aspecto a 256 px (revisar duplicación): `Proyecto_10/Capilla alzado.pdf#pagina=1`; `Proyecto_10/Capilla planta.pdf#pagina=1`

## Evaluación propuesta

1. Verificar que las once carpetas representan obras o documentos de origen distintos. Si dos carpetas comparten planos de una misma obra, asignarlas a una única fuente.
2. Revisar una muestra de páginas de cada carpeta y anotar manualmente disciplina, rol y contenido con `EXP11_PLANTILLA_ETIQUETADO.json`. No equiparar pistas de texto o nombres con verdad terreno.
3. Mantener los proyectos nuevos fuera del entrenamiento y del ajuste de umbrales hasta elegir el conjunto de evaluación. Si un proyecto se reserva como prueba, ninguna de sus páginas debe entrar en entrenamiento.
4. Con etiquetas verificadas, aplicar el clasificador existente sin modificarlo a las fuentes reservadas y medir F1 por fuente, cobertura de OCR y errores por clase. Comparar después propuestas nuevas usando otro conjunto de obras.

Este inventario no calcula F1 ni valida cómputos estructurales: esas mediciones requieren etiquetas revisadas y, para el cómputo completo, planos complementarios.

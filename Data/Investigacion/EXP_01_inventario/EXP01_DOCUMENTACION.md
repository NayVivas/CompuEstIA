# EXP-01 — Inventario del nuevo dataset

## Objetivo
Construir el inventario reproducible del nuevo conjunto de datos antes de realizar
etiquetado profesional o entrenamiento de modelos.

## Fuente
Archivo de entrada: `PDF_PLANOS(1).zip`.

## Estructura observada
El dataset contiene **37 proyectos**, **278 archivos PDF** y **474 páginas** en total.
La estructura se interpreta por las carpetas `Proyecto_1` ... `Proyecto_37`.
Los PDFs dentro de cada carpeta se consideran documentos independientes.

## Resultados
- Proyectos: 37
- PDFs: 278
- Páginas: 474
- Páginas con texto extraíble: 202
- Páginas con al menos una imagen/objeto de imagen: 395

### Distribución por proyecto
Ver `EXP01_resumen_proyectos.csv`.

### Inventario por página
Ver `EXP01_paginas_inventario.csv`.

### Inventario de PDFs
Ver `EXP01_inventario_pdfs.csv`.

## Variables registradas
Por cada página se registran:
- `proyecto_id`
- `documento`
- `pagina`
- `cantidad_palabras`
- `cantidad_caracteres`
- `cantidad_imagenes`
- `tiene_texto`
- `tiene_imagenes`

Estas variables constituyen características descriptivas iniciales y no son etiquetas
de clasificación.

## Limitaciones
Este experimento no asigna clases profesionales y no constituye ground truth.
Tampoco se presentan como medidas aquellas variables que no fueron calculadas de forma
reproducible. En particular, no se incluye una medida de cobertura visual de imágenes.

Las páginas escaneadas pueden tener `cantidad_palabras = 0` aunque contengan información
visual relevante. La ausencia de texto no implica que la página pertenezca a una clase
particular.

## Decisión metodológica
Esta versión reemplaza al inventario preliminar basado en 8 proyectos como dataset
principal para los experimentos posteriores. La versión anterior se conserva como
registro histórico.

## Próximo experimento
EXP-02: segmentación/etiquetado profesional y construcción del ground truth. El split
de entrenamiento/evaluación se definirá posteriormente por `proyecto_id`, evitando
mezclar páginas del mismo proyecto entre conjuntos.
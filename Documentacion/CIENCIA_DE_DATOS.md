# CómputoEstIA — arquitectura de Ciencia de Datos

## Cambio implementado

La entrada ya no depende de `planta`, `detalles` y `columnas`. El frontend permite cargar una cantidad arbitraria de PDFs y el backend analiza cada página por su contenido.

El nombre del archivo queda como metadato de trazabilidad y no participa en la clasificación.

## Pipeline

```text
N PDFs
  ↓
Análisis PDF
  ↓
Feature engineering
  ↓
Clasificación documental explicable
  ↓
Confianza + revisión humana
  ↓
Selección automática de fuentes
  ↓
Motores de Ingeniería Civil
  ↓
Cómputos métricos
```

## Features actuales

Cada página genera características como:

- cantidad de palabras y caracteres;
- cantidad de objetos vectoriales;
- cantidad de imágenes;
- cobertura raster;
- orientación;
- tipo de contenido;
- presencia de términos semánticos de fundaciones, columnas, vigas, losas, cuadros y detalles;
- evidencias de clasificación detectadas por el analizador base.

## Clases iniciales

- `planta_fundaciones`
- `columnas`
- `vigas`
- `losas`
- `cuadro_fundaciones`
- `detalle_estructural`
- `otro/desconocido`

## Importante para la tesis

La confianza mostrada por la versión actual es una **confianza heurística**, no una probabilidad estadística calibrada. Esto se declara explícitamente en la respuesta de la API.

El siguiente paso científico es construir el dataset etiquetado por proyecto y comparar modelos supervisados. El dataset debe dividirse por `proyecto_id` para evitar fuga de información entre páginas del mismo proyecto.

## Respuesta de la API

`POST /api/analisis/` acepta múltiples partes `archivos`:

```text
archivos = PDF_1
archivos = PDF_2
archivos = PDF_3
...
```

La respuesta incluye:

- `clasificacion_documental`;
- características por página;
- confianza y candidatos;
- páginas que requieren revisión;
- `fuentes_seleccionadas`;
- documentos analizados;
- resultados del motor de cómputo;
- ubicaciones y validaciones existentes.

La API anterior con `planta`, `detalles` y `columnas` se conserva temporalmente para compatibilidad con las pruebas y flujos existentes.

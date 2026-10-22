# EXP-02 — Diseño definitivo del Ground Truth

## 1. Decisión de diseño

Después de revisar el dataset actual de EXP-01 (37 proyectos, 278 PDFs, 474 páginas), se adopta un esquema **multietiqueta y jerárquico**.

La unidad científica de anotación es la **página**, no el nombre del PDF.

Motivo: el dataset contiene tanto PDFs multipágina como numerosos PDFs de una sola página, y una misma página puede contener más de una disciplina y más de un contenido técnico.

## 2. Qué NO se hará

No se obligará a que una página tenga una única disciplina.

No se obligará a que una página tenga un único contenido.

No se usará el nombre del archivo como etiqueta.

No se confundirá “fundaciones”, “columnas” o “gas” con el rol documental.

No se agregará una categoría extremadamente específica si no existe evidencia suficiente para aprenderla de manera estadísticamente útil.

## 3. Modelo de anotación

Cada página tendrá cuatro capas principales:

### A. Disciplinas presentes — MULTI-LABEL

Lista de todas las disciplinas realmente presentes en la página.

Códigos:

- `arquitectura`
- `estructura`
- `sanitarias`
- `electricidad`
- `gas`
- `climatizacion`
- `incendio`
- `implantacion_topografia`
- `otra`
- `desconocida`

Ejemplo:

`[sanitarias, gas]`

Una página que combine sanitaria y gas NO se fuerza a una sola clase.

### B. Roles documentales — MULTI-LABEL

Qué tipo de representación aparece en la página.

- `planta`
- `corte`
- `elevacion_fachada`
- `detalle`
- `cuadro_planilla`
- `isometrico`
- `esquema_diagrama`
- `implantacion`
- `situacion`
- `memoria_especificacion`
- `indice_lista_planos`
- `modelo_3d`
- `otro`

Puede haber más de uno. Por ejemplo:

`[planta, detalle]`

si una misma lámina contiene una planta y varios detalles.

### C. Sistemas / elementos / contenidos técnicos — MULTI-LABEL

Qué aparece representado o definido.

#### Estructura

- `fundaciones`
- `columnas_pilares`
- `vigas`
- `losas_forjados`
- `muros_estructurales`
- `escaleras_estructurales`
- `cubiertas_estructurales`
- `armaduras_acero`
- `elementos_estructurales_generales`

#### Arquitectura

- `distribucion_espacios`
- `pisos`
- `cielorrasos`
- `cubiertas`
- `puertas_carpinterias`
- `ventanas_carpinterias`
- `fachadas`
- `terminaciones`
- `detalles_constructivos`

#### Sanitarias

- `agua_fria`
- `agua_caliente`
- `cloacal`
- `pluvial`
- `artefactos_sanitarios`
- `canerias_sanitarias`

#### Electricidad

- `iluminacion`
- `tomacorrientes`
- `fuerza`
- `tableros`
- `canalizaciones`
- `baja_tension`

#### Gas

- `gas_general`
- `artefactos_gas`
- `regulacion_gas`
- `canerias_gas`

#### Climatización

- `equipos`
- `conductos`
- `distribucion_climatizacion`
- `control_climatizacion`

#### Incendio

- `deteccion`
- `extincion`
- `senalizacion_incendio`
- `red_incendio`

#### Implantación / topografía

- `terreno`
- `ejes_replanteo`
- `niveles`
- `coordenadas`
- `implantacion`

### D. Estado de decisión profesional

- `confirmada`
- `ambigua`
- `requiere_revision`
- `no_aplicable`

Una página ambigua conserva las etiquetas candidatas y explica qué impide resolverla.

## 4. Ejemplos reales de cómo se anotaría

### Caso 1 — detalle de armado de fundaciones

Disciplinas:
`[estructura]`

Roles:
`[detalle]`

Contenidos:
`[fundaciones, armaduras_acero]`

### Caso 2 — sanitaria + gas en una misma planta

Disciplinas:
`[sanitarias, gas]`

Roles:
`[planta]`

Contenidos:
`[agua_fria, cloacal, pluvial, canerias_gas]` (solo los que realmente aparezcan)

### Caso 3 — estructura general con fundaciones, columnas y vigas

Disciplinas:
`[estructura]`

Roles:
`[planta]`

Contenidos:
`[fundaciones, columnas_pilares, vigas]`

### Caso 4 — lámina de arquitectura con planta y cortes

Disciplinas:
`[arquitectura]`

Roles:
`[planta, corte]`

Contenidos:
`[distribucion_espacios]`

## 5. Etiquetas principales vs etiquetas derivadas

No se almacenará una única `label_ground_truth` como verdad científica principal.

La verdad científica será el conjunto de etiquetas:

- `disciplinas[]`
- `roles[]`
- `contenidos[]`

Se puede generar una etiqueta plana solamente como derivación para compatibilidad.

Ejemplo:

`estructura + planta + fundaciones + columnas_pilares + vigas`

no se transforma en una única clase científica.

## 6. Por qué este diseño evita rehacer EXP-02

Si mañana aparece una página con:

- arquitectura + estructura;
- sanitaria + gas;
- estructura + electricidad;
- arquitectura + sanitaria + electricidad;

no hay que modificar el modelo de anotación.

Solo se seleccionan varias etiquetas.

Si aparece un contenido nuevo que todavía no existe, se usa `otra` y se documenta en observaciones. La taxonomía se puede ampliar posteriormente sin invalidar las etiquetas anteriores.

## 7. Diseño científico del experimento

EXP-02 alimentará varios experimentos, no un único clasificador.

### Experimento A — disciplina

Predicción multietiqueta de disciplinas.

### Experimento B — rol documental

Predicción multietiqueta de roles.

### Experimento C — contenido técnico

Predicción multietiqueta de sistemas/elementos.

### Experimento D — clasificación jerárquica

Evaluación conjunta:

`página → disciplina → rol → contenido`

Esto permite estudiar en qué nivel se producen los errores.

## 8. Ground Truth y evidencia

Cada decisión debe conservar:

- revisor;
- decisión;
- evidencia profesional;
- observaciones;
- motivo de ambigüedad, cuando corresponda;
- fecha/hora;
- versión de la anotación.

La evidencia debe poder señalar el motivo observable de la decisión: rótulo, título de plano, simbología, cuadro, contenido gráfico, notas, etc.

## 9. Regla para el etiquetado

Primero mirar la página.

Segundo identificar las disciplinas presentes.

Tercero identificar qué representaciones contiene.

Cuarto identificar los sistemas/elementos visibles o definidos.

Quinto marcar ambigüedad si la información no permite decidir sin asumir.

El nombre del archivo sirve únicamente como identificación documental, nunca como evidencia de la clase.

## 10. Regla para clases raras

No se crearán cientos de clases específicas antes de conocer su frecuencia.

Después de etiquetar el conjunto inicial se calculará:

- frecuencia por disciplina;
- frecuencia por rol;
- frecuencia por contenido;
- coocurrencias;
- páginas mixtas;
- etiquetas con muy pocos ejemplos.

Las categorías muy raras podrán mantenerse como subcategorías de análisis, pero no necesariamente como objetivos independientes de un modelo.

## 11. Unidad de evaluación

El split de train/validation/test se hará por `proyecto_id`, nunca mezclando páginas del mismo proyecto entre entrenamiento y prueba.

Esto evita data leakage por estilos gráficos, autores, rótulos y convenciones repetidas dentro de un proyecto.

## 12. Principio final

EXP-02 debe representar cómo son realmente los planos, no obligar a los planos a encajar en una taxonomía artificial.

La clasificación única se abandona cuando la realidad documental es multietiqueta.

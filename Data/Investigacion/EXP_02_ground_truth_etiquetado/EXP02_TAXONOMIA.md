# EXP-02 — Taxonomía jerárquica del Ground Truth

## Objetivo

EXP-02 no etiqueta solamente “tipos de planos estructurales”. La unidad de clasificación es jerárquica:

`página → disciplina → rol documental → subtipo`

Esto permite ampliar CómputoEstIA a arquitectura e instalaciones sin rediseñar el Ground Truth.

## Disciplinas

- estructura
- arquitectura
- instalaciones_sanitarias
- instalaciones_electricas
- instalaciones_gas
- climatizacion
- incendio
- topografia_implantacion
- otros
- desconocido

## Roles documentales

- planta
- detalle
- cuadro_planilla
- corte
- fachada
- isometrico
- esquema_diagrama
- implantacion
- memoria_especificacion
- otro_desconocido

No todos los roles están disponibles para todas las disciplinas; la interfaz muestra únicamente combinaciones válidas.

## Ejemplo estructural

Una página que muestra el **detalle del armado de fundaciones** se etiqueta como:

- disciplina: `estructura`
- rol: `detalle`
- subtipo: `fundaciones_armado`

Una planta donde se ubican físicamente las fundaciones se etiqueta como:

- disciplina: `estructura`
- rol: `planta`
- subtipo: `fundaciones`

Un cuadro de fundaciones se etiqueta como:

- disciplina: `estructura`
- rol: `cuadro_planilla`
- subtipo: `fundaciones`

## Compatibilidad con EXP-02 anterior

Las etiquetas planas anteriores se conservan mediante una migración transparente:

- `planta_fundaciones` → `estructura / planta / fundaciones`
- `columnas` → `estructura / planta / columnas`
- `vigas` → `estructura / planta / vigas`
- `losas` → `estructura / planta / losas`
- `cuadro_fundaciones` → `estructura / cuadro_planilla / fundaciones`
- `detalle_estructural` → `estructura / detalle / estructural_general`
- `otro/desconocido` → `desconocido / otro_desconocido / requiere_revision`

La columna `label_ground_truth` se mantiene como etiqueta plana derivada por compatibilidad. Para el análisis científico, la representación principal es la jerárquica.

## Regla científica

La taxonomía no debe inferirse por nombre de archivo. La decisión profesional debe basarse en la página visual, rótulo, contenido gráfico y evidencia documental. La interfaz registra disciplina, rol, subtipo, ambigüedad, evidencia, observaciones y revisor.

# EXP-02 — Auditoría previa del dataset real

Fecha: 2026-09-19

## Dataset inspeccionado

- 37 proyectos
- 278 PDFs
- 474 páginas
- La unidad de anotación es la página.
- Existen PDFs multipágina y PDFs de una sola página.
- En una misma página pueden coexistir varias disciplinas y varios tipos de representación.

## Evidencia observada

La revisión de las páginas del dataset muestra, entre otros, estos casos:

### Proyecto 1

El conjunto contiene estructura, arquitectura, instalaciones sanitarias y electricidad. También aparecen fundaciones, vigas, columnas, losas, detalles, plantas arquitectónicas, fachadas, instalaciones sanitarias y electricidad.

Conclusión: una taxonomía de una sola clase por página no representa adecuadamente el proyecto.

### Proyecto 2

Se observan planos generales, arquitectura, techos, instalación de gas, fundaciones, direccionamiento de losas y armaduras de losas.

Conclusión: "fundaciones", "gas", "losas" y "arquitectura" son contenidos/sistemas, no una única dimensión de clasificación.

### Proyecto 3

Se observan arquitectura, plano de fundaciones, losa sobre planta baja, previsión de instalaciones sanitarias y detalles estructurales.

Conclusión: una misma disciplina puede tener diferentes roles documentales y diferentes contenidos técnicos.

### Proyecto 4

Se observan plantas arquitectónicas, planta sanitaria, contactos/electricidad, instalaciones de gas e isométricos.

Conclusión: instalaciones sanitarias, gas y electricidad deben poder coexistir en el Ground Truth sin forzar una clase única.

### Proyecto 5

La propia lista de planos contiene arquitectura, estructura, detalles estructurales, cuantificación de materiales, instalación eléctrica y representaciones 3D.

Conclusión: el índice/lista de planos debe poder etiquetarse como un rol documental independiente y no confundirse con una planta o detalle.

### Proyecto 6

El índice distingue arquitectura y estructuras, y el conjunto incluye situación/emplazamiento, plantas, alzados/secciones, cimentación, refuerzos de losa y otros planos estructurales.

Conclusión: situación, planta, corte/alzado y estructura son dimensiones distintas.

### Proyecto 8

Se observan detalles de columnas, detalles de fundaciones y armaduras, además de plantas arquitectónicas y otras láminas.

Conclusión: un detalle de armado de fundaciones debe conservar simultáneamente el contenido `fundaciones` y `armaduras_acero`, no reducirse a una etiqueta única como `detalle_estructural`.

## Decisión metodológica

El esquema definitivo será:

`página → disciplinas[] + roles_documentales[] + contenidos[] + estado de decisión`

No se obliga a una sola disciplina, rol o contenido.

## Consecuencia para el aprendizaje automático

EXP-02 permitirá estudiar tres tareas multietiqueta separadas:

1. clasificación de disciplinas;
2. clasificación de roles documentales;
3. clasificación de contenidos técnicos.

Después se podrá estudiar el comportamiento conjunto.

## Regla de conservación

No se borrarán ni reinterpretarán etiquetas anteriores. Las anotaciones antiguas de una sola etiqueta se migran automáticamente a listas de una sola posición cuando sea posible.

Las futuras ampliaciones agregan etiquetas; no cambian la estructura fundamental del Ground Truth.


FINALES
La auditoría exploratoria del Ground Truth evidenció que la documentación técnica presenta una estructura inherentemente multilabel: las páginas pueden combinar disciplinas, roles documentales y múltiples contenidos simultáneamente. Por este motivo, el problema de clasificación se modelará como una tarea multilabel y no como una clasificación multiclase de etiqueta única.

El dataset no debe tratarse como un conjunto independiente de 474 páginas, sino como 37 grupos de proyectos que contienen páginas relacionadas. Por lo tanto, la partición de entrenamiento y evaluación deberá realizarse a nivel de proyecto para evitar fuga de información y obtener una estimación más realista de la generalización.
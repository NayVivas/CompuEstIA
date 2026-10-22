# EXP-02 — Ground Truth documental (dataset corregido)

## Estado
EXP-02 queda preparado para la revisión profesional sobre el dataset corregido de **37 proyectos, 474 páginas y 278 PDFs**.

Esta versión reemplaza como base experimental la versión anterior construida con 8 proyectos.

## Objetivo
Construir el **ground truth profesional** para la clasificación documental por página.

## Unidad de observación
Una página de un PDF perteneciente a un proyecto.

## Etiquetas
planta_fundaciones, columnas, vigas, losas, cuadro_fundaciones, detalle_estructural, otro/desconocido

## Regla fundamental
La columna `preanotacion_automatica` es solamente una ayuda para acelerar la revisión. **No constituye ground truth ni permite medir rendimiento del modelo.**

## Procedimiento
1. Abrir/revisar visualmente cada página.
2. Seleccionar `label_ground_truth`.
3. Completar `revisor`.
4. Completar `decision`.
5. Si corresponde, marcar `ambiguo` y documentar `motivo_ambiguedad` y `evidencia_profesional`.
6. Usar `observaciones` para información adicional.
7. No utilizar el nombre del archivo como etiqueta.
8. En páginas escaneadas, no inferir la clase por ausencia de texto.

## Criterio de cierre
EXP-02 se considera cerrado cuando las 474 páginas tienen una etiqueta profesional y una decisión registrada, y los casos ambiguos tienen su justificación.

## Relación con EXP-03
Una vez cerrado EXP-02, se podrá ejecutar EXP-03 con split por `proyecto_id`, evitando leakage entre páginas del mismo proyecto.

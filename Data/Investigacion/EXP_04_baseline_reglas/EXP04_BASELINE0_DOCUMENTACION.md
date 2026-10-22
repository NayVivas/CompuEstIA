# EXP-04 — Baseline 0: reglas / preanotación existente

## Resultado de la auditoría

La columna `preanotacion_automatica` del Ground Truth contiene `REVISAR_VISUAL` en las **474/474 páginas**.

- Predicciones automáticas concretas: 0
- Páginas derivadas a revisión: 474
- Cobertura automática: 0 %
- Abstención: 100 %
- Scores automáticos no nulos: 0

Por lo tanto, la preanotación actualmente almacenada no constituye un clasificador predictivo evaluable de las tres tareas multilabel. Constituye un mecanismo de **abstención total**.

## Decisión metodológica

No se debe transformar artificialmente `REVISAR_VISUAL` en una clase profesional ni atribuirle una etiqueta de Ground Truth.

El Baseline 0 se registra como **baseline de abstención**: sirve como control inferior para medir el comportamiento de sistemas que deciden no automatizar.

## Métricas globales

- disciplina: micro-precision=0.0000, micro-recall=0.0000, micro-F1=0.0000, macro-F1=0.0000, cobertura=0.0000, abstención=1.0000.
- rol_documental: micro-precision=0.0000, micro-recall=0.0000, micro-F1=0.0000, macro-F1=0.0000, cobertura=0.0000, abstención=1.0000.
- contenido: micro-precision=0.0000, micro-recall=0.0000, micro-F1=0.0000, macro-F1=0.0000, cobertura=0.0000, abstención=1.0000.

Las métricas de precision/recall/F1 son 0 bajo la convención `zero_division=0` porque el baseline no emite ninguna etiqueta. Esto no significa que exista evidencia de que un clasificador de reglas tenga F1=0; significa exclusivamente que la preanotación disponible no realizó predicciones.

## Implicación para el experimento

No corresponde comparar todavía ML contra esta preanotación como si ambos fueran clasificadores equivalentes.

Para disponer de un Baseline 0 predictivo se necesita una versión de reglas que produzca etiquetas multilabel a partir de información disponible **antes** de observar el Ground Truth profesional, por ejemplo texto extraído del PDF y/o características estructurales de la página.

La regla debe:
1. producir cero o más etiquetas;
2. conservar evidencia de qué regla activó cada etiqueta;
3. permitir abstención cuando no haya evidencia suficiente;
4. ejecutarse sin usar las etiquetas profesionales;
5. evaluarse con el mismo split por proyecto de EXP-03.

## Qué queda demostrado por este experimento

El estado actual confirma que la preanotación usada durante la anotación profesional fue deliberadamente conservadora: no realizó una clasificación automática cuando no encontró coincidencias textuales suficientes.

Por eso, el valor científico de esta versión es principalmente como **control de abstención**, no como modelo competitivo.

## Regla de reproducibilidad

El Baseline 0 queda congelado como referencia de abstención total para EXP-04. Una futura versión de reglas debe registrarse como un baseline nuevo, no sobrescribir este resultado.

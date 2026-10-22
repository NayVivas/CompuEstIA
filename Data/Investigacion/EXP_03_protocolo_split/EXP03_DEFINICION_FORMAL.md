# EXP-03 — Definición formal del experimento ML y partición por proyecto

## 1. Objetivo

Evaluar modelos supervisados para inferir tres dimensiones multilabel de cada página de documentación técnica:

1. disciplina;
2. rol documental;
3. contenido.

El experimento utiliza el Ground Truth profesional de EXP-02.

## 2. Unidad de análisis e independencia

La **unidad de predicción** es una página.

La **unidad de independencia para entrenamiento y evaluación** es el proyecto (`proyecto_id`).

La razón es que varias páginas de un mismo proyecto comparten convenciones gráficas, nomenclatura, formato, tipografías y contexto documental. Si páginas del mismo proyecto aparecieran simultáneamente en train y test, el modelo podría aprovechar patrones específicos del proyecto y producir una estimación artificialmente optimista de generalización.

## 3. Formulación del problema

Se consideran tres tareas multilabel:

- `Y_disciplina`
- `Y_rol_documental`
- `Y_contenido`

Una página puede tener cero, una o varias etiquetas dentro de cada dimensión.

No se reduce la página a una única etiqueta global.

## 4. Variables de entrada

El punto de partida utiliza características observables extraídas automáticamente de los PDFs, entre ellas:

- cantidad de palabras;
- cantidad de caracteres;
- cantidad de imágenes;
- presencia de texto;
- presencia de imágenes;
- otras características que se incorporen posteriormente mediante feature engineering.

Las etiquetas profesionales de EXP-02 no pueden utilizarse como variables de entrada.

El nombre del archivo tampoco se utilizará como feature cuando pueda actuar como etiqueta implícita.

## 5. Ground Truth

EXP-02 contiene:

- 474 páginas;
- 37 proyectos;
- 278 PDFs;
- decisiones profesionales confirmadas para las 474 páginas.

El dataset actual tiene un único revisor. Por ello, permite evaluar contra una referencia profesional, pero no permite calcular acuerdo interobservador.

## 6. Partición experimental

Se fija una partición **70/15/15 aproximadamente por páginas**, pero la asignación se realiza exclusivamente a nivel de proyecto.

Resultado final:

| Split | Proyectos | PDFs | Páginas | % páginas |
|---|---:|---:|---:|---:|
| Train | 26 | 191 | 332 | 70,04 % |
| Validation | 5 | 37 | 71 | 14,98 % |
| Test | 6 | 50 | 71 | 14,98 % |
| Total | 37 | 278 | 474 | 100 % |

La partición fue obtenida mediante una búsqueda aleatorizada reproducible con semilla `20260917`, optimizando:

- proporción de páginas cercana a 70/15/15;
- presencia de las disciplinas principales en los tres splits;
- ausencia de solapamiento de proyectos.

No se utilizó una partición aleatoria de páginas.

## 7. Proyectos asignados

### Train — 26 proyectos

Proyecto_1, Proyecto_10, Proyecto_14, Proyecto_15, Proyecto_16, Proyecto_18, Proyecto_19, Proyecto_2, Proyecto_20, Proyecto_21, Proyecto_22, Proyecto_24, Proyecto_25, Proyecto_26, Proyecto_28, Proyecto_29, Proyecto_3, Proyecto_30, Proyecto_31, Proyecto_32, Proyecto_36, Proyecto_37, Proyecto_4, Proyecto_6, Proyecto_7, Proyecto_9.

### Validation — 5 proyectos

Proyecto_12, Proyecto_13, Proyecto_23, Proyecto_33, Proyecto_5.

### Test — 6 proyectos

Proyecto_11, Proyecto_17, Proyecto_27, Proyecto_34, Proyecto_35, Proyecto_8.

## 8. Cobertura de disciplinas principales

La partición conserva presencia de las cinco disciplinas principales en todos los splits:

| Disciplina | Train | Validation | Test |
|---|---:|---:|---:|
| Arquitectura | 26 | 5 | 6 |
| Estructura | 26 | 5 | 6 |
| Electricidad | 25 | 5 | 5 |
| Sanitarias | 25 | 4 | 5 |
| Gas | 23 | 4 | 5 |

Esto no significa que todas las etiquetas raras estén representadas en todos los splits. Las clases con muy bajo soporte se conservarán y sus métricas se interpretarán según su soporte.

## 9. Baselines

El experimento tendrá al menos dos referencias:

### Baseline 0 — reglas/preanotación

Se medirán las predicciones producidas por las reglas o preanotaciones existentes.

### Baseline 1 — modelo supervisado simple

Se entrenará inicialmente un modelo interpretable y reproducible, antes de probar modelos más complejos.

La hipótesis no presupone que ML será superior al baseline. La comparación es un resultado experimental.

## 10. Métricas

Para cada una de las tres tareas multilabel se reportarán:

- precision;
- recall;
- F1;
- micro-F1;
- macro-F1;
- métricas por etiqueta;
- soporte por etiqueta;
- análisis de errores.

Accuracy no será utilizada como única métrica.

## 11. Control de data leakage

Queda prohibido:

- separar páginas de un mismo proyecto entre train y test;
- utilizar Ground Truth como feature;
- utilizar nombres de archivos como etiquetas implícitas;
- ajustar imputación, escalado o selección de variables utilizando validation/test;
- utilizar información calculada a partir del conjunto completo antes de realizar el split cuando dicha información incorpore conocimiento de las etiquetas.

Las transformaciones aprendidas se ajustarán sobre train y posteriormente se aplicarán a validation/test.

## 12. Tratamiento de clases raras

Las clases raras no se eliminarán para mejorar artificialmente los resultados.

Se conservarán en el Ground Truth.

Cuando una etiqueta tenga soporte insuficiente, se informará explícitamente que su estimación de generalización es limitada.

## 13. Reproducibilidad

Cada experimento deberá guardar:

- versión del dataset;
- semilla;
- lista exacta de proyectos por split;
- variables de entrada;
- transformación de features;
- configuración del modelo;
- hiperparámetros;
- métricas;
- predicciones;
- errores.

## 14. Hipótesis

**H1:** Un modelo supervisado basado en características extraídas automáticamente de la documentación puede aprender patrones que permitan predecir las etiquetas profesionales de disciplina, rol y contenido con rendimiento medible sobre proyectos no observados durante el entrenamiento.

## 15. Alcance

EXP-03 evalúa la interpretación/clasificación documental.

Todavía no demuestra:

- extracción geométrica exacta;
- reconocimiento completo de elementos estructurales;
- extracción confiable de propiedades;
- cálculo automático de cantidades;
- reducción del error de metrado.

Esas capacidades corresponderán a experimentos posteriores.

## 16. Decisión metodológica registrada

La elección del split por proyecto se adopta para medir **generalización a proyectos no observados**, no simplemente capacidad de reconocer páginas parecidas a las utilizadas durante el entrenamiento.

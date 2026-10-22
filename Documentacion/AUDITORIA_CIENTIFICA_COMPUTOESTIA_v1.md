# AUDITORÍA CIENTÍFICA — CómputoEstIA v1

**Fecha:** 2026-09-18  
**Base:** proyecto `ComputoEstIA(2).zip` entregado para revisión  
**Objetivo:** reorientar el proyecto para que el aporte central sea demostrable como Ciencia de Datos/IA aplicada a documentación estructural, manteniendo la aplicación como plataforma de demostración.

---

## 1. Resumen ejecutivo

CómputoEstIA ya contiene una arquitectura sólida de interpretación documental y un núcleo explícito de Ciencia de Datos. Sin embargo, en el estado actual, la mayor parte del comportamiento productivo sigue siendo **feature engineering + reglas explicables**, mientras que el Machine Learning está aislado en un baseline experimental y todavía no constituye el mecanismo principal de decisión.

### Diagnóstico global

| Área | Estado | Papel en la tesis |
|---|---|---|
| Preprocesamiento PDF | 🟢 | Ingeniería de datos / entrada |
| Feature engineering | 🟢 | Ciencia de Datos central |
| Clasificación documental | 🟡 | DS central, hoy basada principalmente en reglas |
| Machine Learning supervisado | 🟡 | Existe baseline, falta dataset/evaluación robusta |
| Extracción de elementos | 🟢 | DS + conocimiento de dominio |
| Extracción de propiedades | 🟢 | DS / Information Extraction |
| Incertidumbre | 🟢 | Aporte científico potencialmente fuerte |
| Human-in-the-Loop | 🟢 | Aporte científico fuerte |
| Cómputo ingenieril | 🟢 | Dominio/aplicación |
| Frontend/API | 🔵 | Ingeniería de software, soporte |
| Evaluación científica | 🔴 | Falta construirla sistemáticamente |
| Dataset etiquetado | 🔴 | Falta construirlo realmente |
| Reproducibilidad experimental | 🟡 | Hay estructura, falta cerrar el ciclo |

**Conclusión:** no hace falta tirar el sistema actual. Hay que cambiar el centro de gravedad: de “hacer que el software calcule” a “medir y demostrar cómo un sistema de datos interpreta documentación, cuantifica incertidumbre y reduce intervención humana sin sacrificar trazabilidad”.

---

# 2. Qué existe actualmente

## 2.1 Entrada documental

El sistema acepta una cantidad arbitraria de PDFs y ya se diseñó para que el nombre del archivo sea solamente metadato de trazabilidad. La intención es que la función documental sea inferida por el contenido.

Esto es importante porque elimina una dependencia artificial como `Fundaciones_1.pdf -> planta`.

**Clasificación:** 🟢 ingeniería de datos + fundamento experimental.

---

## 2.2 Análisis de páginas PDF

`backend/computos/documentos/analisis.py` y `procesamiento_pdf.py` construyen información de página y contenido. El sistema distingue, entre otras cosas, contenido vectorial y escaneado, orientación, palabras, caracteres, objetos vectoriales e imágenes.

Esto constituye la materia prima para feature engineering.

**Clasificación:** 🟢 datos / feature engineering.

---

## 2.3 Feature engineering

`backend/computos/documentos/clasificacion.py` y `backend/computos/percepcion/features.py` generan características tales como:

- cantidad de palabras;
- cantidad de caracteres;
- objetos vectoriales;
- imágenes;
- cobertura de imágenes;
- orientación;
- contenido vectorial/escaneado;
- señales semánticas de fundaciones, columnas, vigas, losas, cuadros, detalles y plantas.

Esto es uno de los componentes más claramente defendibles como Ciencia de Datos.

### Problema actual

Algunas características semánticas están representadas como booleanos `contiene_*`. Para una tesis de DS conviene ampliar el espacio de features con variables cuantitativas y de contexto, sin perder las actuales.

Ejemplos futuros:

- frecuencia de términos por página;
- densidad de texto;
- proporción de números;
- cantidad de referencias estructurales;
- cantidad de patrones geométricos;
- distribución espacial de texto;
- densidad vectorial normalizada por superficie;
- presencia de unidades;
- indicadores de tablas;
- indicadores de cotas;
- características derivadas de OCR cuando la página sea escaneada.

---

# 3. Clasificación documental

`backend/computos/documentos/clasificacion.py` implementa actualmente una clasificación explicable mediante puntajes construidos con reglas.

Ejemplo conceptual:

```text
features
   ↓
reglas semánticas
   ↓
puntajes
   ↓
normalización
   ↓
candidato principal
```

Las clases iniciales son:

- `planta_fundaciones`
- `columnas`
- `vigas`
- `losas`
- `cuadro_fundaciones`
- `detalle_estructural`
- `otro/desconocido`

### Punto científico importante

El código declara correctamente que la confianza actual es **heurística** y no una probabilidad estadística calibrada.

Esto debe mantenerse.

No debemos presentar un valor como `0.91` como “91 % de probabilidad” hasta disponer de un modelo probabilístico evaluado y, si corresponde, calibrado.

### Estado científico

🟡 **Bueno como baseline de reglas; insuficiente como demostración final de ML.**

---

# 4. Machine Learning actual

Existe `backend/experimentos/02_entrenar_baseline.py`.

El baseline utiliza `LogisticRegression` con:

- `cantidad_palabras`
- `cantidad_caracteres`
- `cantidad_objetos_vectoriales`
- `cantidad_imagenes`
- `cobertura_imagenes`

Tiene imputación de valores faltantes y `class_weight="balanced"`.

El código calcula `classification_report`.

### Fortalezas

- modelo simple y reproducible;
- adecuado como baseline;
- evita empezar con un modelo innecesariamente complejo;
- el proyecto ya establece que el split debe hacerse por proyecto.

### Debilidades actuales

1. No existe todavía un dataset real `paginas.csv` etiquetado dentro del proyecto.
2. No existe un conjunto de proyectos de entrenamiento y prueba suficientemente definido.
3. El baseline utiliza solo cinco features numéricas, aunque ya disponemos de más señales.
4. No se guardan sistemáticamente predicciones, matriz de confusión ni métricas en un artefacto de resultados.
5. No existe comparación formal contra el clasificador de reglas.
6. No existe validación cruzada por grupos/proyecto.
7. No existe calibración de probabilidades.
8. No existe análisis de errores por clase.

**Prioridad:** 🔴 alta.

---

# 5. Dataset: principal deuda científica

Existe el contrato documental en `backend/datos_ciencia/README.md`, pero no el dataset etiquetado completo.

El contrato propuesto es correcto:

```text
proyecto_id
documento_id
pagina
label
split
```

Las features deben generarse automáticamente, mientras que el `label` debe provenir de validación profesional.

## Regla fundamental

El split debe realizarse por `proyecto_id`, no por página.

### Motivo

Páginas de un mismo proyecto comparten tipografías, nomenclaturas, estilos gráficos, tablas y convenciones. Si unas páginas del mismo proyecto aparecen en train y otras en test, el modelo puede beneficiarse indirectamente de ese estilo y producir una estimación demasiado optimista.

### Esquema recomendado

```text
Proyecto A ─┐
Proyecto B ─┼── TRAIN
Proyecto C ─┘

Proyecto D ─── VALIDATION

Proyecto E ─┐
Proyecto F ─┴── TEST
```

No debemos fijar porcentajes definitivos hasta conocer el número real de proyectos y el balance de clases.

---

# 6. Detección de elementos estructurales

`backend/computos/percepcion/elementos.py` realiza detección contextual de referencias.

Tiene una decisión de diseño muy importante: una referencia no se promociona automáticamente si no existe contexto de familia suficiente.

Esto ya solucionó falsos positivos graves como referencias aisladas que anteriormente generaban decenas de columnas inexistentes.

### Valor científico

Este módulo permite estudiar:

- precision de detección;
- recall de detección;
- falsos positivos;
- falsos negativos;
- impacto del contexto documental;
- diferencia entre detección basada en reglas y modelos de aprendizaje.

### Recomendación

No reemplazar inmediatamente este detector por ML. Primero debemos convertirlo en un **baseline de detección** y medirlo.

---

# 7. Separación entre ocurrencia y definición

Una de las decisiones de modelado más importantes del proyecto es distinguir:

```text
UBICACIÓN
→ representa una ocurrencia física
→ puede contar unidades

DEFINICIÓN
→ describe geometría/armadura/propiedades
→ no crea una unidad física adicional
```

Esto resolvió el problema de contar referencias de cuadros/detalles como si fueran unidades físicas.

### Ejemplo

```text
plano: F7 aparece 10 veces
detalle: F7 aparece 1 vez

cantidad física = 10
```

No `11`.

### Valor para la tesis

Esto es principalmente conocimiento de dominio y modelado semántico, pero también constituye una excelente demostración de que **los datos necesitan una representación correcta antes del cómputo**.

---

# 8. Extracción de propiedades

`backend/computos/percepcion/propiedades.py` consolida candidatos de propiedades y conserva procedencia.

El sistema puede detectar que una propiedad tiene valores diferentes y no seleccionar automáticamente uno.

Esto es una forma de **resolución de conflictos de información**.

### Potencial científico

Podemos medir:

- exactitud de extracción por atributo;
- tasa de conflictos detectados;
- tasa de conflictos no detectados;
- falsos conflictos;
- porcentaje de propiedades con fuente verificable.

---

# 9. Incertidumbre

Esta es una de las líneas que más conviene fortalecer.

Actualmente el sistema distingue estados como:

- detectado;
- completo;
- incompleto;
- ambiguo;
- no computable.

También distingue severidades de alerta y decisiones profesionales.

### Principio correcto

```text
si evidencia suficiente
    → continuar
si evidencia insuficiente
    → no inventar
    → solicitar revisión
```

Esto debe convertirse en una variable medible.

Ejemplos:

```text
% de páginas clasificadas automáticamente
% de páginas enviadas a revisión
% de elementos ambiguos
% de decisiones humanas
% de predicciones erróneas de alta confianza
```

Especialmente importante:

> **error de alta confianza** debe estudiarse como métrica de riesgo.

---

# 10. Human-in-the-Loop

El sistema ya posee una estructura de `DecisionIngeniero` y mecanismos para conservar decisiones.

Esto permite representar:

```text
modelo
 ↓
propuesta
 ↓
incertidumbre
 ↓
ingeniero
 ↓
decisión
 ↓
recalcular
```

## Armadura

El proyecto contempla explícitamente el caso ambiguo de una notación que puede interpretarse como:

- solo superior;
- solo inferior;
- superior e inferior.

Esta funcionalidad no debe verse solamente como UI. Debe ser tratada como un **caso experimental de decisión humana bajo incertidumbre**.

### Futuro dataset de decisiones

```text
entrada
predicción_modelo
confianza
opciones
decisión_ingeniero
motivo
fuente
```

Eso puede convertirse posteriormente en datos para active learning o mejora supervisada.

---

# 11. Cómputo ingenieril

Los motores de fundaciones, columnas, vigas, armaduras, encofrado, etc. constituyen la capa de dominio.

Su función científica no es demostrar ML sino demostrar que:

> un modelo documental validado puede convertirse en una representación estructurada capaz de alimentar cálculos reproducibles.

Por eso el flujo correcto es:

```text
PDF
 ↓
percepción
 ↓
modelo de datos
 ↓
validación
 ↓
estado de computabilidad
 ↓
motor de ingeniería
```

No debemos permitir que un motor “arregle” silenciosamente datos ambiguos.

---

# 12. Trazabilidad y explicabilidad

El modelo `Fuente` conserva:

- documento;
- página;
- caja/coordenadas;
- evidencia;
- rol de la fuente.

Esto es una fortaleza importante.

Podemos convertirlo en una métrica:

> **Cobertura de trazabilidad = resultados/atributos con evidencia visual verificable ÷ resultados/atributos totales.**

La trazabilidad debe ser parte de la evaluación final, no solamente una función visual.

---

# 13. Evaluación científica que falta

Actualmente hay muchos tests de software, lo cual es positivo, pero **tests de software no equivalen a evaluación científica de modelos**.

## Debemos separar tres niveles

### Nivel A — pruebas de software

```text
¿La función devuelve lo esperado?
```

### Nivel B — evaluación del modelo

```text
¿Qué tan bien generaliza a proyectos no vistos?
```

### Nivel C — evaluación del sistema

```text
¿Qué tan bien transforma PDFs reales en cómputos confiables?
```

Los tres son necesarios.

---

# 14. Métricas propuestas

## Clasificación documental

- Accuracy
- Precision macro
- Recall macro
- F1 macro
- F1 por clase
- matriz de confusión

## Detección de elementos

- Precision
- Recall
- F1
- falsos positivos por página/proyecto
- falsos negativos por página/proyecto

## Extracción de atributos

- exactitud por campo;
- tasa de extracción correcta;
- tasa de conflicto;
- cobertura de atributos.

## Incertidumbre

- porcentaje de casos enviados a revisión;
- errores de alta confianza;
- cobertura automática;
- tasa de abstención;
- precisión condicionada a la confianza.

## Human-in-the-Loop

- decisiones humanas por proyecto;
- decisiones por familia;
- porcentaje de casos resueltos;
- porcentaje de propuestas aceptadas/rechazadas;
- reducción de intervención tras mejora del modelo.

## Cómputo

- diferencia absoluta respecto al ground truth profesional;
- error relativo;
- error por familia;
- error por tipo de material;
- cantidad de elementos excluidos correctamente por falta de evidencia.

## Trazabilidad

- porcentaje de resultados con documento/página/fuente;
- porcentaje con ubicación visual;
- tiempo de recuperación de evidencia.

---

# 15. Experimentos que deberíamos construir

## Experimento 01 — Baseline de reglas

Medir el clasificador documental actual.

**Pregunta:** ¿qué rendimiento obtenemos sin ML?

---

## Experimento 02 — Logistic Regression

Entrenar con features básicas.

**Pregunta:** ¿un modelo supervisado simple mejora el baseline de reglas?

---

## Experimento 03 — Feature engineering ampliado

Agregar features semánticas, geométricas y de densidad.

**Pregunta:** ¿qué features aportan información útil?

---

## Experimento 04 — Comparación de modelos

Evaluar modelos candidatos apropiados al tamaño del dataset.

**Pregunta:** ¿qué comportamiento tienen distintos modelos bajo el mismo split por proyecto?

No debemos decidir de antemano cuál será “el ganador”.

---

## Experimento 05 — Incertidumbre

Analizar la relación entre confianza y error.

**Pregunta:** ¿podemos identificar un umbral operativo donde el sistema deba abstenerse?

---

## Experimento 06 — Human-in-the-Loop

Registrar decisiones del ingeniero.

**Pregunta:** ¿qué proporción de casos necesita intervención humana y qué tipos de ambigüedad aparecen?

---

## Experimento 07 — Extracción estructurada

Medir referencias, dimensiones y armaduras.

**Pregunta:** ¿qué atributos son más fáciles/difíciles de extraer y dónde se concentran los errores?

---

## Experimento 08 — Cómputo final

Comparar contra ground truth profesional.

**Pregunta:** ¿la cadena completa produce cantidades reproducibles y trazables?

---

# 16. Qué NO debemos hacer

### ❌ No presentar la confianza heurística como probabilidad.

### ❌ No entrenar y evaluar mezclando páginas del mismo proyecto.

### ❌ No elegir automáticamente entre dos fuentes contradictorias.

### ❌ No usar el nombre del archivo como etiqueta oculta del modelo.

### ❌ No medir solamente accuracy.

### ❌ No declarar éxito porque todos los tests de software pasen.

### ❌ No reemplazar conocimiento de ingeniería por ML cuando una regla verificable sea más segura.

### ❌ No agregar modelos complejos antes de tener dataset y baseline sólidos.

---

# 17. Qué conservar

Debe conservarse como núcleo:

- arquitectura documental general;
- feature engineering;
- detector contextual;
- consolidación de propiedades;
- representación de fuentes;
- separación ubicación/definición;
- estados de completitud;
- alertas;
- Human-in-the-Loop;
- motores de cálculo;
- tests de regresión;
- documentación de decisiones.

---

# 18. Qué refactorizar

## Alta prioridad

### 18.1 Separar claramente producción de experimentos

El código de `backend/experimentos/` debe producir datasets, modelos y métricas sin mezclarse con la API productiva.

### 18.2 Crear un pipeline experimental reproducible

```text
raw PDFs
 ↓
labels
 ↓
features
 ↓
split por proyecto
 ↓
train
 ↓
predict
 ↓
metrics
 ↓
artifacts
```

### 18.3 Persistir resultados experimentales

Cada experimento debe guardar:

- configuración;
- features utilizadas;
- proyectos train/test;
- modelo;
- métricas;
- predicciones;
- matriz de confusión;
- errores.

### 18.4 Crear ground truth explícito

El sistema necesita distinguir claramente entre:

```text
predicción del sistema
vs.
verdad de referencia
```

---

# 19. Código que hoy parece sobredimensionado para el aporte científico

`backend/computos/flujos/principal.py` y varias implementaciones históricas de vigas/fundaciones concentran una gran cantidad de lógica de dominio.

No significa que deban eliminarse.

Pero para la tesis debemos evitar que su tamaño lleve a la conclusión de que el aporte principal es un sistema de reglas de cómputo.

La documentación deberá presentar esos módulos como:

> **capa de dominio utilizada para validar el valor práctico de la representación generada por el sistema de Ciencia de Datos.**

---

# 20. Problema técnico encontrado durante la auditoría

Se ejecutaron los tests del backend del proyecto.

Resultado actual:

```text
63 passed
1 failed
16 subtests passed
```

El fallo está en:

```text
backend/tests/test_motor_acero_general.py
```

El test espera que una alerta `armadura_ambigua` tenga:

```text
propiedad = armadura_confirmada
```

pero el código actual genera:

```text
propiedad = armadura_nivel
```

Esto es una **inconsistencia de contrato entre implementación y test**, no un problema científico.

No se debe corregir ahora “a ciegas”: cuando hagamos la refactorización científica, decidiremos el nombre canónico de la variable y actualizaremos implementación + tests + documentación juntos.

---

# 21. Problemas de empaquetado

El ZIP contiene `backend/.venv/` y muchos archivos de entorno/cache.

Eso produce un proyecto innecesariamente grande y mezcla:

```text
código fuente
+
entorno local
+
cache
```

Para las próximas entregas debemos excluir:

- `.venv/`
- `__pycache__/`
- `node_modules/`
- artefactos temporales
- caches

El entorno debe reconstruirse desde `requirements.txt` y `package-lock.json`.

---

# 22. Arquitectura científica objetivo

```text
                       PDFs
                        │
                        ▼
                PREPROCESAMIENTO
                        │
                        ▼
                FEATURE ENGINEERING
                        │
             ┌──────────┴──────────┐
             │                     │
             ▼                     ▼
       BASELINE REGLAS        MODELOS ML
             │                     │
             └──────────┬──────────┘
                        ▼
                  PREDICCIÓN
                        │
                        ▼
                INCERTIDUMBRE
                        │
              ┌─────────┴─────────┐
              │                   │
          CONFIABLE            AMBIGUO
              │                   │
              ▼                   ▼
       REPRESENTACIÓN          INGENIERO
        ESTRUCTURADA              │
              │                   ▼
              │              GROUND TRUTH
              │                   │
              └────────┬──────────┘
                       ▼
                   VALIDACIÓN
                       │
                       ▼
                CÓMPUTO CIVIL
                       │
                       ▼
                  EVALUACIÓN
```

---

# 23. Hipótesis de trabajo propuesta

Una formulación inicial, que deberá validarse y eventualmente ajustarse con el director de tesis, es:

> **La incorporación de técnicas de Ciencia de Datos para la interpretación y extracción de información desde documentación estructural, combinadas con mecanismos explícitos de incertidumbre y revisión profesional, permite automatizar una parte del flujo de cómputo manteniendo trazabilidad y control sobre los casos ambiguos.**

Esta hipótesis es más defendible que afirmar que “la IA reemplaza al ingeniero”.

---

# 24. Preguntas de investigación propuestas

1. ¿Qué características de una página PDF permiten discriminar su función documental?
2. ¿Cómo se comporta un baseline basado en reglas frente a modelos supervisados?
3. ¿Qué features contribuyen más a la clasificación documental?
4. ¿Cómo afecta la separación por proyecto a la estimación real de generalización?
5. ¿Puede el sistema identificar casos en los que su predicción no es suficientemente confiable?
6. ¿Qué tipos de ambigüedad requieren intervención profesional?
7. ¿Puede la decisión humana convertirse en información útil para mejorar el sistema?
8. ¿Qué precisión se obtiene al transformar documentación en elementos estructurados?
9. ¿Qué error se obtiene al transformar esos elementos en cantidades de ingeniería?
10. ¿Qué porcentaje del resultado final puede trazarse hasta evidencia documental verificable?

---

# 25. Roadmap oficial a partir de esta auditoría

## Fase 1 — Auditoría científica
**Estado: iniciada/completada con este documento.**

## Fase 2 — Dataset y ground truth
**Próximo objetivo.**

Definir exactamente:

- proyectos disponibles;
- páginas;
- clases;
- reglas de etiquetado;
- protocolo de etiquetado profesional;
- train/validation/test por proyecto.

## Fase 3 — Baselines

Medir formalmente:

- reglas actuales;
- Logistic Regression.

## Fase 4 — Feature engineering

Diseñar, implementar y evaluar nuevas features.

## Fase 5 — Modelos

Comparar modelos bajo el mismo protocolo experimental.

## Fase 6 — Incertidumbre

Determinar cuándo el sistema debe abstenerse.

## Fase 7 — Human-in-the-Loop

Convertir decisiones profesionales en datos auditables.

## Fase 8 — Extracción estructurada

Evaluar referencias, propiedades y armaduras.

## Fase 9 — Cómputo

Validar la cadena completa contra referencia profesional.

## Fase 10 — Tesis y defensa

Construir tablas, gráficos, resultados, discusión, limitaciones y preguntas de defensa a partir de los experimentos reales.

---

# 26. Regla de trabajo desde ahora

Cada modificación importante deberá responder a una de estas preguntas:

```text
¿Mejora la calidad de los datos?
¿Mejora una feature?
¿Mejora un modelo?
¿Mejora la medición de incertidumbre?
¿Mejora la extracción?
¿Mejora la evaluación?
¿Mejora la trazabilidad?
¿Permite una comparación experimental?
```

Si la respuesta es no y solamente mejora la interfaz, se puede hacer, pero se considera **ingeniería de software**, no aporte científico.

---

# 27. Material de estudio para la defensa

Los conceptos que debemos dominar progresivamente son:

1. Dataset
2. Feature
3. Feature engineering
4. Label / ground truth
5. Variable objetivo
6. Clasificación supervisada
7. Baseline
8. Train / validation / test
9. Group split
10. Data leakage
11. Overfitting
12. Generalización
13. Precision
14. Recall
15. F1
16. Matriz de confusión
17. Class imbalance
18. Probabilidad vs. confianza heurística
19. Calibración
20. Incertidumbre
21. Abstención / selective prediction
22. Information extraction
23. Human-in-the-Loop
24. Active learning
25. Trazabilidad
26. Reproducibilidad
27. Error de medición
28. Evaluación end-to-end

Cada concepto deberá documentarse posteriormente con:

```text
CONCEPTO
↓
DEFINICIÓN
↓
EJEMPLO GENERAL
↓
CÓMO APARECE EN CÓMPUTOESTIA
↓
CÓMO LO EVALUAMOS
↓
PREGUNTA POSIBLE DEL JURADO
```

---

# 28. Conclusión de la auditoría

CómputoEstIA **no necesita convertirse en un proyecto completamente distinto**. Ya existe una base apropiada: procesamiento documental, features, clasificación explicable, representación estructurada, incertidumbre, trazabilidad, revisión humana y motores de ingeniería.

La principal transformación necesaria es metodológica:

```text
ANTES
software → reglas → resultado

AHORA
problema
  ↓
datos
  ↓
ground truth
  ↓
features
  ↓
baseline
  ↓
modelos
  ↓
evaluación
  ↓
incertidumbre
  ↓
human-in-the-loop
  ↓
resultado trazable
```

El siguiente trabajo no debe ser agregar más funcionalidades al frontend. Debe ser **construir el dataset científico y establecer el primer experimento reproducible**, porque a partir de ahí podremos medir objetivamente todo lo que hagamos después.

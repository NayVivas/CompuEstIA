# EXP22 — clasificación multimodal explicable

Fecha de integración: 16/10/2026.

## Objetivo

EXP22 clasifica cada página de manera independiente sin utilizar el nombre del
archivo, el número de página ni reglas específicas de un proyecto. Su salida
sirve para organizar la documentación y proponer fuentes al motor; no produce
cantidades por sí sola.

## Modalidades

1. **Texto:** predicciones del clasificador local EXP19 y evidencias léxicas
   contextuales.
2. **Posición textual:** palabras y rótulos separados por zonas de la lámina.
3. **Imagen renderizada:** densidad de tinta y contraste de una vista reducida
   de la página.
4. **Geometría vectorial:** cantidad y orientación de líneas, rectángulos,
   curvas y trazos discontinuos obtenidos del PDF.
5. **OCR adaptativo:** Tesseract se activa cuando falta texto o cuando una
   lámina vectorial densa contiene texto insuficiente.

## Fusión y trazabilidad

Una sugerencia del modelo textual no se confirma automáticamente. Para
aceptarla, EXP22 exige margen suficiente y compatibilidad de la página con un
plano técnico o un rótulo localizado. Cada decisión conserva:

- objetivo y etiqueta;
- decisión confirmada o descartada;
- fuerza de evidencia, que no se presenta como probabilidad;
- fuentes que intervinieron;
- sugerencias que quedaron sin corroborar.

Cuando una disciplina técnica no estructural domina claramente y la página no
posee un título estructural inequívoco, EXP22 retira falsos positivos de
estructura y sus contenidos asociados. Esto evita que palabras incidentales
como “viga” o “losa” conviertan una lámina sanitaria en fuente del motor.

Los títulos técnicos explícitos y las decisiones profesionales tienen
prioridad sobre las inferencias. Si solo existen inferencias, el enrutador
conserva los candidatos de mayor respaldo y evita mezclar indiscriminadamente
todas las páginas estructurales.

Desde EXP22.1, un título explícito no termina prematuramente el enrutamiento.
Una lámina combinada puede aportar planta, cuadro de zapatas, cuadro de
columnas y detalles. Los roles explícitos conservan prioridad y los roles
adicionales solo se incorporan cuando la clasificación multimodal, la
compatibilidad técnica y una tipología estructural los respaldan.

## OCR

En una página puramente raster, el sistema genera un PDF buscable y usa sus
coordenadas. En una página vectorial con texto parcial, fusiona texto nativo y
OCR en una copia de lectura, conservando las líneas y la rotación originales. Desde V12.2 esa copia con palabras y coordenadas alimenta tanto la auditoría como los motores. Toda
página en la que interviene OCR queda marcada para comprobación visual.

## Límites honestos

EXP22 no es un LayoutLMv3 entrenado. El repositorio contiene anotaciones de
clasificación, pero no conserva todavía el conjunto completo y versionado de
imágenes de página necesario para entrenar, validar y reproducir un modelo de
documentos visuales de ese tipo. Declararlo entrenado sería incorrecto.

La arquitectura queda preparada para sustituir o complementar EXP19 con un
modelo visual entrenado cuando exista un dataset con imágenes, cajas, etiquetas
y particiones por proyecto. Mientras tanto, la fusión actual es local,
reproducible y auditable.

## Contrato de integración

- API: 0.4.2.
- Contrato frontend/backend: 6.
- Build: `2026-10-17-v12.2-lector-regional-ocr`.
- Estado esperado: `clasificado_multimodal`.

El frontend consulta `/api/estado` antes de analizar. Si encuentra un contrato
distinto, detiene el envío y solicita cerrar el servidor viejo.

## Validación realizada

- Proyecto 8: 22 de 22 páginas clasificadas; fuentes tabulares preservadas.
- Proyecto 03: 41 de 41 páginas clasificadas; la lámina sanitaria de control no
  se enruta como estructura; 24 zapatas pasan a revisión geométrica.
- Proyecto 09: 10 de 10 páginas clasificadas; dos tipos de cimiento corrido
  pasan a revisión geométrica.
- Proyecto 15: las láminas 8, 9 y 10 se reconocen como candidatas
  estructurales; la lámina 10 se prioriza automáticamente porque reúne el
  cuadro de zapatas, el cuadro de columnas, los detalles y la planta.
- Para la reparación V12.2 consultar `VALIDACION_V12_2.md`. Los resultados anteriores no sustituyen una referencia manual independiente.
- Frontend: ESLint, prueba de persistencia y build de producción aprobados.

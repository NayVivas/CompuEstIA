# Regresión con proyectos externos 03 y 09

Fecha de verificación: 16/10/2026.

Los PDF se usaron únicamente como entradas de prueba y no se incluyen en la
entrega. Las decisiones se obtienen del contenido de cada página; los nombres
de archivo y el número del proyecto no intervienen en la clasificación.

## Proyecto 03 - edificio de cinco pisos

- 41 documentos y 41 páginas con texto nativo.
- 41 páginas clasificadas y 0 conflictos documentales pendientes.
- EXP22 ejecutado con texto, posición textual, imagen renderizada y geometría
  vectorial; EXP19 participó como modalidad textual mediante el runtime
  portátil local.
- Fuentes estructurales seleccionadas por contenido:
  - una planta general de cimentación;
  - el detalle típico de zapata presente en esa misma lámina;
  - tres páginas complementarias de placas y columnas.
- Se descartó como fuente de dimensiones la lámina de conexiones
  viga-zapata; no es un cuadro ni un detalle geométrico de zapatas.
- Se detectaron 24 ocurrencias de zapatas, correspondientes a 9 referencias
  Z1-Z9.
- El flujo solicita revisión de X, Y y H por ocurrencia. Al guardar una
  decisión válida, la API completa hormigón y encofrado de fundaciones y deja
  explícitamente pendientes el acero y las otras familias sin fuente
  inequívoca.

## Proyecto 09 - vivienda multifamiliar

- 10 documentos y 10 páginas con texto nativo.
- 10 páginas clasificadas y 0 conflictos documentales pendientes.
- La lámina estructural se reconoció como planta y detalle de cimentación, con
  tipos de cimientos C-1 a C-4 y tipos de castillos.
- La tipología se identificó como cimientos corridos.
- El sistema no sustituyó esa tipología por fórmulas de zapatas aisladas.
- Se propusieron dos tipos para revisión profesional:
  - C-2: 0,30 m de coronamiento, 0,60 m de base, 0,40 m de altura y 91,32 m de longitud;
  - C-3: 0,30 m de coronamiento, 0,80 m de base, 0,40 m de altura y 96,59 m de longitud.
- El flujo llegó al estado `requiere_revision_geometria` con dos elementos. El
  volumen solo se emite después de confirmar o corregir esas propuestas.

## Control de no regresión

Después de estos ajustes, `Proyecto_8.pdf` conserva 22 de 22 páginas
clasificadas, 0 conflictos documentales y las fuentes tabulares originales:
detalle en la página 2, planta en la página 19, columnas en las páginas 1 y 16
y pórticos en las páginas 6 a 10.

La batería automática terminó con 145 pruebas aprobadas y 4 omitidas por
requerir otros PDF históricos externos. También aprobaron la compilación de
Python, ESLint y el build de producción de Vite.

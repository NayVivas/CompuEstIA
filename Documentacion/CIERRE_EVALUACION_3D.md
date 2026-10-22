# Evaluación de cierre y origen del modelo 3D

Fecha: 19 de octubre de 2026. La corrección del visor no modifica los motores de
cómputo ni convierte etiquetas de página en elementos construidos.

## Error corregido

`Motor3D.jsx` creaba siempre 13 fundaciones de ejemplo cuando no había
ocurrencias de planta. También aceptaba filas del cuadro de detalles o de
encofrado como fuente del 3D. Un cuadro describe tipos y dimensiones, pero no
demuestra que un elemento esté ubicado en la planta.

La escena ahora se alimenta de `fundaciones_planta` o
`ubicaciones_fundaciones` del resultado **del proyecto abierto**. En resultados
anteriores que solo tengan `fundaciones`, exige posiciones explícitas.
Cada malla exige referencia, dos coordenadas y dimensiones X, Y y H positivas;
una fila de planta corresponde a una ocurrencia. No hay tamaños, ubicaciones
ni cantidad 13 predeterminados. La interfaz distingue fundaciones mostradas,
volumen representado y volumen informado por el cálculo. Si el backend
informa más elementos que los que se pueden dibujar, muestra la diferencia.

Para cimientos corridos, el resultado actual guarda secciones y **longitudes
totales por referencia**, pero no el recorrido de ejes con sus extremos sobre
la planta. En este caso el visor explica que no puede reconstruir el 3D;
dibujar barras con una longitud total en posiciones arbitrarias sería falso.

## Comprobaciones realizadas

| Proyecto | Entrada y clasificación | Resultado de cómputo disponible | Consecuencia en 3D |
| --- | --- | --- | --- |
| 09, vivienda con cimientos corridos | 10 PDF, 10 páginas; una fuente de planta y una de detalles; revisión de cimientos | En la validación V12.3 se simularon decisiones para C-2/C-3: 37,6874 m³ geométricos. C-1/C-4 quedaron sin recorrido medido. No se confirmó el material. | No se dibujan las 13 zapatas de ejemplo. Las longitudes totales no bastan para situar los recorridos. |
| 03, edificio | 41 PDF, 41 páginas; planta y detalles para zapatas aisladas | 24 ocurrencias propuestas; 22 con X, Y y H propuestas completas. Una decisión **simulada, no profesional**, incluyó solo esas 22 y produjo 54,096 m³ parciales. | El selector del visor recibió 22 ubicaciones de la planta y 8 tipos, cada una con posición y dimensiones; las otras 2 no se dibujan. |
| 8, supermercado | Un PDF de 22 páginas; fuente de planta y detalle tabular | La prueba V12.3 se detuvo en la revisión del cuadro F12/F13. No se repitió aquí el cómputo completo con una aprobación profesional. | Cuando el cálculo entrega `fundaciones_planta`, el visor toma esas ocurrencias. Si la revisión queda pendiente, muestra ausencia de geometría; no inventa 13 fundaciones. |

La clasificación de páginas se ejecutó nuevamente con el backend de este ZIP.
La simulación de cálculo de Proyecto 03 se realizó con sus PDF originales y
las funciones de revisión geométrica, sin pasar por FastAPI. El entorno de
prueba no tenía FastAPI instalado para repetir los recorridos completos de API
descritos en `VALIDACION_V12_3.md`. Tampoco se ha comparado en esta ronda cada
cantidad con un cómputo manual firmado por el ingeniero. Los números simulados
sirven para probar el contrato de datos del visor, no para aprobar una obra.

Pruebas del cambio: tres casos automatizados del selector (cuadro de 13 tipos,
otro proyecto y posiciones reales), 14 pruebas de los motores de geometría y
fichas, compilación del frontend y ESLint completos. El visor no necesita
que el frontend lea el PDF por su cuenta: utiliza las ubicaciones que el
backend produjo a partir de las páginas clasificadas como planta.

## Criterio para la entrega de la tesis

El MVP acepta PDF sueltos y multipágina, clasifica documentación y puede
revisar y computar ciertas familias cuando hay geometría suficiente. La
evidencia anterior demuestra cómputo parcial en más de un formato, con
decisiones simuladas para probar el flujo. No demuestra detección o cantidades
correctas para cualquier proyecto. Falta una comparación manual completa por
familia y proyecto, y aún no hay un detector visual entrenado.

El siguiente paso de validación consiste en revisar profesionalmente las
ocurrencias y cantidades de los tres proyectos, registrar omisiones y falsos
positivos, y comparar hormigón, encofrado y acero solo donde las fuentes sean
comprobables. La ausencia de recorrido o dimensiones debe seguir visible como
pendiente, tanto en el 3D como en el cómputo.

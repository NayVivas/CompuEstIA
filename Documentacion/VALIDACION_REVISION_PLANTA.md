# Revisión sobre planta y cómputo trazable — 19 de octubre de 2026

Build `2026-10-19-v12.3.2-revision-planta`, contrato API 6. Esta entrega
incorpora reglas geométricas y revisión profesional. No se entrenó ni agregó
un modelo de IA; el clasificador EXP19/EXP22 que ya tenía el proyecto se
conserva. En las pruebas de esta entrega se usó deliberadamente el enrutamiento
determinístico sin modalidad aprendida.

## Qué cambió

- **Zapatas aisladas:** en la revisión se pueden mover marcas propuestas y
  añadir una ocurrencia omitida haciendo clic en la página estructural. Cada
  alta conserva página, archivo y huella SHA-256, posición, referencia y X/Y/H.
  El backend exige dimensiones positivas, la identidad del juego de fuentes,
  una página válida y una posición dentro de ella. Las ocurrencias aceptadas
  aparecen en `fundaciones_planta`; el volumen y el encofrado se recalculan
  desde la decisión guardada. Si no se reconoció ningún rótulo, se puede
  iniciar una revisión completamente manual sobre la planta clasificada.
- **Cimientos corridos:** los ejes vectoriales calibrados conservan extremos,
  página, escala y longitud como propuestas individuales. En la revisión se
  pueden seleccionar o descartar y dibujar segmentos adicionales en las páginas
  que tengan escala confirmada. El backend vuelve a calcular su longitud desde
  los extremos; rechaza un recorrido ajeno, duplicado o fuera de página y una
  longitud declarada que no coincida con los segmentos. Si no hay escala, se
  puede registrar una longitud manual justificada, pero no se genera geometría
  3D de ella.
- **3D:** las zapatas se sitúan según las ubicaciones revisadas. Los cimientos
  corridos cuentan con una escena propia, separada por página, que extruye su
  sección superior/base/altura a lo largo de cada tramo revisado. Muestra metros
  representados y computados por separado. Si una longitud carece de extremos,
  permanece en el cómputo revisado y fuera del modelo visual.
- Las decisiones se guardan con el identificador del proyecto y la identidad
  de los PDF; el backend vuelve a validar la decisión con esos archivos cuando
  se solicita el cómputo. El build actualizado evita mezclar esta interfaz con
  un backend anterior.

## Ensayos y resultados

| Entrada | Observación reproducible | Límite |
| --- | --- | --- |
| Vivienda 09, 10 PDF originales | C-2 y C-3: 39 ejes candidatos con extremos y escala. Simulación que confirmó esos tramos y excluyó C-1/C-4: 187,9126 m de longitud revisada y 37,687888 m³ de volumen geométrico; el visor recibe 39 tramos. | Decisión simulada, pendiente de comprobación profesional. C-1/C-4 sin recorrido, acero/encofrado pendientes; material no confirmado. El resultado anterior, que redondeaba longitud por tipo a centésimas antes de multiplicar, era 37,6874 m³. |
| Edificio 03, 41 PDF originales | Clasificación de zapatas; 24 ocurrencias candidatas, 22 con X/Y/H propuestas completas y un rótulo adicional no interpretado. La nueva interfaz permite ubicar manualmente una ocurrencia omitida. | No se aprobó un cómputo nuevo del proyecto completo; los 22 valores siguen siendo propuestas. La revisión manual de la ubicación no demuestra que los demás elementos estén cubiertos. |
| Prueba controlada de dos zapatas | Una posición corregida y una ocurrencia añadida produjeron 2,1 m³ de volumen y 5,2 m² de encofrado; una posición fuera de la página fue rechazada. | Caso sintético que verifica la conexión decisión → cantidades → ubicaciones. |
| Proyecto 8, 22 páginas | Se conserva su flujo anterior de cuadro y revisión F12/F13. | No se repitió el cómputo integral de ese proyecto en esta entrega. |

Se ejecutaron 176 pruebas de Python, correctas con cuatro omitidas por requerir
PDF históricos; cuatro pruebas del selector 3D del frontend, ESLint sin avisos y
compilación de Vite. El build avisa que el paquete JS es grande. No se ejecutó
la aplicación de escritorio en Windows ni se hizo comparación manual firmada de
los tres proyectos. La lectura real de la vivienda y del edificio se probó
directamente con sus PDF originales; las cantidades arriba señaladas proceden
de decisiones simuladas, no de una aprobación de obra.

## Uso de la revisión

1. Cargar los PDF estructurales. Inspeccionar la clasificación y abrir la
   revisión geométrica.
2. En zapatas, cambiar de página, mover referencias mal ubicadas y pulsar
   «Añadir fundación» para marcar las omitidas. Completar referencia y X/Y/H
   cotejando sus cotas y detalles. Excluir cada propuesta falsa con motivo.
3. En cimientos corridos, abrir «Ver planta», comprobar las líneas rojas y
   desmarcar las incorrectas. Dibujar un tramo mediante dos clics solamente si
   la página indica una escala calibrada. Si se utiliza una longitud medida por
   otro procedimiento, quitar los trazos y escribirla con justificación; esa
   longitud no aparecerá en el 3D.
4. Indicar responsable y criterio, guardar y calcular. En el modelo 3D,
   comparar los metros representados con los metros computados.

## Alcance para tesis y mejoras futuras

El flujo admite PDF individuales o multipágina y permite revisión con rastro
documental aunque falle una propuesta de lectura. Su cobertura cuantitativa
continúa limitada a familias y fuentes que el motor puede interpretar; no
garantiza cómputos automáticos de cualquier plano. Para cerrar la evaluación,
comparar por proyecto y familia con una referencia manual las páginas
clasificadas, ocurrencias detectadas/omitidas, dimensiones, cantidades y tiempo
de revisión. Un detector visual entrenado y una mayor variedad de anotaciones
pueden estudiarse como trabajo futuro, separados de lo implementado y medido.

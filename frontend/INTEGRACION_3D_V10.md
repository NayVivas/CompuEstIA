# Integración del frontend del compañero — V10

## Mejora V10.18 — armaduras completas en el modelo 3D

- Las jaulas de pedestales y columnas ya no dependen de la fundación
  seleccionada: se representan simultáneamente en todas las ubicaciones que
  poseen sección y armadura disponible.
- Se incorporó la armadura real de cada tramo de viga de riostra a partir de
  `vigas_riostra_computo_detalle.armadura_viga`, con barras longitudinales,
  diámetros, estribos, separación y cantidad calculada.
- El hormigón de pedestales, columnas y vigas se vuelve translúcido solamente
  cuando su jaula está visible, de modo que el acero pueda inspeccionarse sin
  ocultar la geometría del elemento.
- Los tramos con acero computado se muestran en cian; un detalle disponible
  pero pendiente de aprobación se mantiene en ámbar y no se presenta como
  resultado validado.
- Una armadura de columna en conflicto también puede verse dentro de su
  pedestal como candidata roja. Su visualización facilita la revisión, pero no
  la incorpora al cómputo ni sustituye la decisión profesional.
- Se agregaron interruptores y contadores independientes para acero de
  pedestales, columnas y vigas, además del detalle técnico al seleccionar una
  viga.
- Las barras y los estribos repetidos usan instancias gráficas para reducir la
  carga del navegador. La malla de cada fundación continúa mostrándose solo en
  la fundación activa, evitando saturar la escena con miles de barras.

## Mejora V10.16 — acero interactivo de columnas y pedestales

- El visor consume `armaduras_columnas` por referencia y dibuja la cantidad y
  diámetro reales de barras longitudinales, además de los estribos con la
  separación detectada.
- La jaula usa la sección real de la columna. Si todavía falta la altura, se
  representa con la altura visual y el panel la identifica como preliminar;
  esa representación no se incorpora al cómputo.
- Al seleccionar una columna o pedestal se activa automáticamente la capa de
  acero correspondiente y su hormigón se vuelve translúcido.
- Se agregaron controles separados para acero de fundaciones, pedestales y
  columnas dentro de la zona activa.
- Las armaduras validadas se distinguen en violeta, las candidatas pendientes
  en ámbar y los conflictos entre fuentes en rojo.
- Un resultado antiguo que todavía no tenga `armadura_pedestal` puede mostrar
  como respaldo visual la armadura correcta de su columna asociada. El panel
  advierte que debe reprocesarse antes de incluir ese acero en cantidades.
- La armadura específica o calculada del pedestal mantiene prioridad sobre el
  respaldo visual de la columna.

## Corrección V10.15 — filtro de falsos positivos en vigas candidatas

- Las vigas sin rótulo solo se incorporan automáticamente al modelo 3D cuando
  poseen doble borde vectorial y confianza alta.
- Un candidato de borde simple o confianza media permanece fuera del visor y
  de los cómputos; podrá mostrarse únicamente si posteriormente queda marcado
  como validado por un profesional.
- Se elimina el falso tramo diagonal `C3-01 — C7-03`, detectado desde una sola
  línea del dibujo y no respaldado por una viga real en el plano.
- Se conservan cuatro tramos sin rótulo respaldados por doble borde. El modelo
  verificado queda con 98 tramos visibles: 94 rotulados y 4 candidatos fiables.
- La regla se basa en la calidad geométrica de la evidencia y no contiene
  referencias particulares del proyecto, por lo que funciona para planos
  diferentes.

## Corrección V10.14 — vigas vectoriales sin rótulo visibles

- El visor combina ahora los tramos computados, las vinculaciones confirmadas
  y los candidatos vectoriales sin rótulo, en lugar de descartar las dos
  últimas fuentes cuando ya existe al menos una viga computada.
- Los candidatos se reconstruyen entre sus apoyos reales mediante
  `apoyos_columnas_vigas` y mantienen la misma transformación espacial de la
  planta; por eso atraviesan el centro de columnas y pedestales.
- La sección visual se toma por continuidad colineal o por la mediana de las
  secciones detectadas. Esa sección queda expresamente marcada como
  provisional y nunca se suma al cómputo.
- Los tramos sin referencia se muestran en ámbar, con sus apoyos, longitud
  geométrica, confianza y posible referencia por continuidad. Permanecen
  excluidos hasta la validación del ingeniero.
- La unión aplica deduplicación por apoyos y por solape geométrico para no
  dibujar dos veces una misma viga que llegue desde fuentes diferentes.
- En el proyecto de verificación se conservan las 94 vigas rotuladas y se
  agregan 5 candidatos vectoriales, para un total de 99 tramos visibles.

## Mejora V10.13 — acero de pedestales heredado de columnas

- Una armadura explícita de pedestal mantiene siempre la prioridad.
- Si no existe esa especificación, el pedestal usa las barras longitudinales,
  el diámetro/separación de estribos y la longitud de estribo de la columna
  con la misma referencia.
- El motor calcula las barras sobre la altura del pedestal, sin inventar
  anclajes ni solapes no indicados, y conserva la procedencia
  `heredada_de_columna` en cada fila.
- Con altura mínima, el subtotal de acero se identifica como preliminar; al
  validar la altura real se recalculan barras, estribos y peso.
- Si una referencia de columna sigue ambigua o incompleta, solo sus pedestales
  quedan fuera del subtotal. Las referencias válidas sí se computan.
- Al confirmar la armadura de columnas, el acero de pedestales se actualiza en
  la misma revisión y la alerta duplicada se cierra automáticamente cuando ya
  existe cobertura completa.
- Resultados y modelo 3D muestran armadura aplicada, procedencia y peso de acero
  del pedestal para que la inferencia sea visible y auditable.
- Al activar armaduras sobre la fundación seleccionada, el visor dibuja la
  jaula del pedestal con la cantidad y diámetro de barras heredadas y los
  estribos con su separación calculada; el hormigón se vuelve translúcido.

## Corrección V10.12 — tramo C7–C16 visible

- Se verificó que el tramo `VR1-23` entre `C7-09` y `C16-03` existe, está
  computado y mide 5,725 m; no era una omisión del motor de vigas.
- Cada viga toma ahora como base visual la cara superior más alta de sus dos
  fundaciones de apoyo, en vez de la fundación más cercana al punto medio.
- Evita que un tramo quede embebido dentro de una fundación más alta, como
  ocurría entre F5-04 (0,85 m) y F1-03 (0,35 m).
- Se agregaron aristas oscuras a las vigas para distinguir tramos colineales y
  mantener visible su contorno sobre el hormigón translúcido.
- El panel de la viga informa que esta cota es la utilizada por el visor.

## Corrección V10.11 — vigas centradas en pedestales

- Unifica la posición 3D de fundaciones, pedestales, columnas y vigas con los
  centros de los apoyos vectoriales detectados en la planta.
- Los rótulos `F...` y `C...` se conservan como evidencia, pero ya no se usan
  como si fueran el centro físico del elemento.
- Cada rótulo de columna se asocia uno a uno con su símbolo vectorial mediante
  referencia, página y proximidad, evitando intercambiar columnas repetidas.
- En el proyecto verificado se alinearon 61 de 61 apoyos directos y los 94
  tramos de vigas coinciden exactamente con sus apoyos inicial y final.
- Cuando el plano no contiene un apoyo vectorial confirmado, se conserva la
  posición anterior y el visor no inventa una coordenada estructural.

## Mejora V10.10 — modelo estructural completo y capas de acero

- Controles independientes para armadura inferior y superior, con cantidad de
  direcciones disponible para la fundación activa.
- Si un tipo no posee acero superior confirmado, el visor lo informa y ofrece
  abrir una fundación que sí lo tenga, sin inventar una malla inexistente.
- Pedestales posicionados bajo su columna asociada con sección y altura real o
  preliminar claramente diferenciadas.
- Columnas consolidadas desde asociaciones y resultados de cómputo, incluida la
  altura profesional validada cuando está disponible.
- Vigas generadas desde `vigas_riostra_computo_detalle`, sus ejes vectoriales,
  sección, apoyos y longitud computada; se mantiene el vínculo anterior como
  respaldo cuando no existe ese detalle.
- Selección individual y panel trazable para fundación, armadura, pedestal,
  columna y viga.
- Encuadre de cámara adaptado a la altura total de pedestales y columnas.

## Mejora V10.9 — armadura constructiva de fundaciones

- Sustituye la cuadrícula simplificada por barras físicas según cantidad de
  posiciones, cantidad indicada, diámetro y separación real calculada.
- Representa recubrimiento, malla inferior y malla superior en cotas distintas.
- Dibuja los dos dobleces incluidos en la longitud calculada de cada barra.
- El acero inferior se identifica en azul y el superior en magenta.
- Cada grupo de armadura puede seleccionarse y muestra diámetro, cantidad,
  separación y longitud por barra en el panel técnico.
- No inventa un radio de doblado cuando ese dato no está informado.

## Mejora V10.8 — selección técnica y evidencia

- Selección individual de fundaciones, columnas y vigas confirmadas.
- Panel contextual con tipo, dimensiones, altura, asociación y estado.
- Colores generales por estado: validado, requiere revisión, inconsistencia y
  dato incompleto, acompañados por una leyenda permanente.
- Acceso a la página original del PDF desde el elemento seleccionado.
- Traducción de la página interna del PDF temporal del motor hacia la página
  real del documento multipágina.
- Cuando falta trazabilidad de origen, el visor lo informa y no inventa una
  página ni un enlace.

## Mejora V10.7 — interacción del motor 3D

- La selección permanece activa al rotar, desplazar o hacer zoom.
- Doble clic sobre una fundación para seleccionarla y enfocarla.
- Selector directo de fundación y botones **Encuadrar**, **Enfocar**,
  **Isométrica**, **Superior**, **Frontal**, acercar y alejar.
- Navegación táctil: un dedo rota y dos dedos desplazan/acercan.
- Brújula de ejes interactiva y realce visual al pasar sobre un elemento.
- Botón central del mouse dedicado al zoom y botón derecho al desplazamiento.

## Corrección V10.6 — falsa alerta de lectura en pórticos

- Se reconoce `pórtico` y `elevación de pórtico` como rol documental general.
- Un PDF vectorial con un rol todavía desconocido puede requerir clasificación,
  pero ya no se declara falsamente ilegible ni exige modo asistido.
- El modo asistido queda reservado para páginas escaneadas, mixtas, vacías o
  sin contenido vectorial aprovechable.

## Mejora V10.5 — filtro de falsos conflictos en pórticos

- Una diferencia solo se considera conflicto bloqueante cuando proviene de
  dos vistas ortogonales completas y con asociación geométrica fuerte.
- Las diferencias producidas por una relación débil entre título, eje, nivel
  y rótulo se conservan como observaciones informativas no bloqueantes.
- Si existe una fuente geométrica fuerte y otra débil contradictoria, se usa
  la fuente fuerte sin ocultar la discrepancia en la auditoría.
- Los conflictos continúan deduplicados por eje global e intervalo de niveles.

## Corrección V10.4 — validación de pórticos

- La API acepta las acciones profesionales `resolver_inconsistencia_portico`
  y `validar_seccion_portico` que ya procesa el motor de revisiones.
- Corrige el error que aparecía al pulsar **Validar y actualizar** en una
  inconsistencia entre pórticos.
- La decisión queda aplicada al análisis y deja de bloquear el cálculo cuando
  no quedan otras alertas excluyentes.

Se conservó íntegramente el flujo actual de CómputoEstIA: carga multipágina, clasificación documental, revisión de inconsistencias, validación profesional, cómputos y persistencia.

## Incorporado

- Auditoría visual de una fundación seleccionada dentro del motor 3D existente.
- Capas independientes para hormigón, armaduras, columnas, vigas, etiquetas y cuadrícula.
- Hormigón translúcido al visualizar las armaduras.
- Malla inferior/superior generada desde las direcciones, diámetros y cantidades entregadas por el backend.
- Panel de armaduras con separación, cantidad de barras, peso por fundación y peso total del tipo.
- Conservación de alturas reales de columnas cuando fueron validadas desde pórticos.

## No incorporado literalmente

El visor del compañero era una proyección isométrica SVG y prorrateaba el acero mediante un promedio global. No reemplazó el motor actual porque CómputoEstIA ya posee un modelo Three.js interactivo y datos de armadura por tipo. Se tomó su propuesta visual y se implementó sobre los datos trazables reales.

Los componentes de carga, dashboard y corrección del frontend recibido utilizaban datos demostrativos o acciones simuladas. No reemplazan las pantallas existentes para evitar romper la conexión con FastAPI y el flujo de revisión profesional.

## Verificación

- ESLint: aprobado.
- Compilación de producción con Vite: aprobada.

## Corrección V10.1

- Las selecciones técnicas guardadas se depuran cuando una corrección, por ejemplo F12 → F13, elimina el conflicto que las originó.
- Una decisión obsoleta ya no bloquea la revalidación ni el botón de ejecutar cómputo.
- Solo las resoluciones que siguen vigentes se envían al motor de cantidades.

## Corrección V10.2

- La inconsistencia por referencias duplicadas ya no muestra el formulario incorrecto de selección de armadura/sección.
- El panel correcto para F12 → F13 queda abierto y visible automáticamente.
- No permite guardar si no se modificó ninguna de las filas duplicadas.
- Después de guardar la fila corregida, el bloqueo de familia se revalida y se habilita el cálculo si no quedan otros bloqueos reales.

## Mejora V10.3

- Las inconsistencias entre pórticos muestran cada observación por separado: página, pórtico, eje local, columna, niveles y altura leída.
- Cada evidencia incorpora un botón para abrir directamente la página correspondiente del PDF original guardado en el navegador.
- Se distingue claramente si el conflicto está en la referencia de columna, en la altura o en ambas.

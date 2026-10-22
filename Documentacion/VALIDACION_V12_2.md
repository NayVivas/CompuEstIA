# V12.2 — reparación, pruebas y límites

Fecha: 17 de octubre de 2026. Build: `2026-10-17-v12.2-lector-regional-ocr`.

## Qué se corrigió

1. **Selección regional de tablas.** El lector vincula cada encabezado a su
   título local y limita sus columnas y filas. Una tabla de columnas, aunque
   tenga más filas, no pasa a ser el cuadro de fundaciones por compartir la
   página. Se mantienen las duplicidades reales del cuadro correcto.
2. **Encabezados incompletos.** Se puede reconstruir una columna REF ausente
   cuando un título inequívoco de fundaciones, los encabezados dimensionales
   y referencias alineadas aportan evidencia suficiente. No se modifica el PDF
   ni se establece un prefijo obligatorio para las referencias de ese cuadro.
3. **OCR integrado.** Las palabras recuperadas se insertan como texto invisible
   en una copia de lectura. Se conservan el texto nativo, sus coordenadas,
   rotación y vectores. Esta copia llega a auditoría y extracción, no solamente
   a la clasificación. Los originales no se modifican.
4. **Recuperación de formatos.** Si el lector tabular no entiende un cuadro de
   zapatas, la API puede abrir la revisión geométrica. Un límite del lector no
   se convierte automáticamente en una inconsistencia del plano ni queda
   encerrado en un formulario que solo permite documentar el error.
5. **Asociación de cotas.** X/Y se proponen desde un cuadro local o desde dos
   cotas exteriores coherentes con un contorno rectangular. Los números
   próximos sin esa relación se muestran como alternativas, no se rellenan
   como dimensiones. H puede proponerse desde una cota lateral del cuerpo de
   un detalle típico o desde una indicación explícita en la línea del elemento;
   no se toma la altura de una columna vecina.
6. **Entorno verificable.** El diagnóstico comprueba ejecutable e idiomas de
   Tesseract. El instalador de Windows ejecuta una prueba real sobre una
   imagen y no informa instalación completa si el OCR no funciona. La
   interfaz advierte la falta de OCR antes de analizar.

Se conserva el motor tabular y el archivo del visor `Motor3D.jsx`, sin cambios
respecto de V12.1. Esta reparación no incorpora un nuevo modelo visual
entrenado ni un servicio de IA de pago.

## Pruebas automatizadas

- Backend: 160 casos ejecutados, **156 aprobados y 4 omitidos**, sin fallos.
  Las omisiones requieren PDF históricos que no están en las rutas de pruebas.
- Frontend: ESLint y compilación de producción aprobados.
- Persistencia: prueba de IndexedDB aprobada; cubre aislamiento por proyecto y
  PDF, conflictos entre pestañas, correcciones y fallo de cuota.
- OCR: prueba real de reconocimiento aprobada; prueba de conservación de
  vectores, rotación, coordenadas nativas y estabilidad de la copia aprobada.
- API: prueba con un PDF nuevo de tres páginas y referencias BA-7/BA-8,
  cuadro sin acero, recuperación a revisión geométrica, confirmación y
  cálculo repetido de 1,512 m³ aprobada, sin inventar peso de acero.

El entorno de ejecución fue Linux, Python 3.12.14, PyMuPDF 1.28.2 y Node 24.
Se instalaron las dependencias fijadas en requirements.txt y package-lock.json.
Los archivos BAT no se ejecutaron en un Windows real en esta revisión. El
diagnóstico incluido permite comprobar el entorno concreto de instalación.
La compilación del frontend avisa de un paquete JavaScript grande; no es un
fallo del build, pero sigue siendo una oportunidad de optimización.

## Recorridos con documentos reales

Las llamadas se hicieron a la API real, sin simular el clasificador o los
motores y sin asignar manualmente roles documentales. Para llegar a cantidades
se enviaron decisiones de prueba equivalentes a confirmar o corregir en la
interfaz. No se trata de aprobaciones profesionales de esos proyectos.

| Caso | Ingreso y clasificación | Extracción y revisión | Resultado del recorrido |
| --- | --- | --- | --- |
| Proyecto 8 | Un PDF de 22 páginas; 22 clasificadas | Se mantiene la duplicidad real F12; en la prueba se documentó la segunda aparición como F13 | API completada; 61 ocurrencias y 13 tipos. Campo de hormigón: 194,71975 m³, reproduciendo el motor existente |
| Edificio 03 | 41 PDF de una página; 41 clasificadas | 24 ocurrencias numéricas; 22 pares X/Y con evidencia de contorno y cotas; H=0,70 m propuesta desde detalle típico. Se completaron manualmente dos Z6 como 5,70 × 1,40 m para la prueba | API completada; cómputo parcial de esas 24 zapatas: 65,268 m³ y 141,82 m² laterales. Acero pendiente. El rótulo Z-A no está computado y se advierte como límite de cobertura |
| Vivienda/cimientos 09 | 10 PDF de una página; 10 clasificadas | C-2: 0,30/0,60 × 0,40 m y 91,32 m; C-3: 0,30/0,80 × 0,40 m y 96,59 m. Propuestas confirmadas en la prueba, sin introducir esas medidas manualmente | API completada: 187,91 m de recorrido y 37,6874 m³ geométricos. Material no identificado; no se presenta ese volumen como hormigón aprobado |

Estas cantidades demuestran que los recorridos terminan y aplican las
decisiones enviadas. **No demuestran precisión métrica general, exhaustividad
de detección ni equivalencia con un cómputo manual independiente.** Las
asociaciones y cantidades propuestas deben comprobarse profesionalmente.

También se probaron PDF sintéticos con varias tablas contiguas, tablas de otra
familia más grandes, referencias sin prefijo F, encabezado REF ausente,
rotación 270°, cotas próximas incorrectas y escalas incompatibles. Estos casos
son regresiones del lector, no un conjunto representativo de toda la práctica
profesional.

## Qué no se debe dar por resuelto

- No existe garantía de lectura o cálculo automático de cualquier proyecto.
  Clasificar una página no demuestra que se extrajeron todos sus elementos.
- Las cuatro familias se conservan en el motor tabular existente cuando sus
  fuentes son compatibles. El flujo geométrico alternativo no generaliza
  todavía acero, pedestales, vigas y columnas a todos los formatos.
- El flujo de zapatas geométricas calcula cuerpos rectangulares confirmados.
  Formas irregulares, referencias no reconocidas, cimentaciones mixtas o
  fuentes/niveles ambiguos pueden requerir cómputo separado. Los avisos de
  límites del lector no son, por sí mismos, errores del proyecto.
- Para cimientos corridos, se debe revisar la calibración y los recorridos.
  La fórmula geométrica no decide si el material es mampostería u hormigón.
- OCR no equivale a entender dibujos: puede fallar en textos diminutos,
  imágenes giradas dentro de la página, símbolos o escaneos de mala calidad.
- No se dispuso de los PDF originales completos de los cuatro videos recientes
  del usuario; no se afirma haber validado sus cantidades ni resuelto todos
  sus casos. Los videos guiaron las regresiones generales de tablas y OCR.

## Reproducir las pruebas

Desde backend:

```powershell
python -m unittest discover -s tests -v
python scripts/verificar_entorno.py --requerir-ocr
```

Desde frontend:

```powershell
npm ci
npm run check
node --test tests/documentReviewStorage.test.mjs
```

Para comprobar los PDF propios, crear un análisis nuevo, comprobar el build,
subir todos los documentos y revisar las fuentes, dimensiones y avisos antes
de confirmar. Los resultados históricos no se recalculan al abrirlos.

## Empaquetado

Se omiten node_modules, entornos virtuales, cachés, compilados, salidas de
pruebas y revisiones generadas durante esta reparación. Los datos y archivos
de investigación se conservan; el modelo operativo permanece en
backend/data/modelos/exp19. No se eliminan resultados ni documentos de la
instalación del usuario.

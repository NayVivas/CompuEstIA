# CómputoEstIA integrado

Para iniciar la recolección de evidencia visual general, consulte
`EXP23_VISION_GENERAL.md`. Incluye el anotador local de cinco familias
estructurales y una evaluación separada por proyectos. Todavía no hay un
detector de objetos entrenado; esta herramienta de investigación no modifica
el cálculo de la aplicación.

La validación de esta entrega está en `VALIDACION_V12_3.md` y las instrucciones
de instalación en `../LEEME_V12_3.txt`. La arquitectura de clasificación
se documenta en `EXP22_MULTIMODAL.md`. EXP22 reemplaza
el enrutamiento puramente textual por una fusión auditable de cinco
modalidades, sin delegar los cómputos métricos a un modelo generativo.

Esta entrega contiene los dos proyectos conectados:

~~~text
ComputoEstIA/
├── backend/    # motor Python + API FastAPI
└── frontend/   # interfaz React + Vite
~~~

La integración vigente procesa uno o varios PDF, incluso un único archivo
multipágina. El frontend ya no utiliza datos de demostración en la pantalla de
resultados.

Requisitos: Python 3.11 o superior y Node.js 20.19 o superior (también sirve
Node.js 22.12 o una versión posterior).

## 1. Preparar y ejecutar el backend

Abra una terminal de PowerShell:

~~~powershell
cd C:\Users\chari\Documents\ComputoEstIA\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
uvicorn computos.api:app --reload --port 8000
~~~

Deje esa terminal abierta. Puede comprobar el servidor en:

- http://127.0.0.1:8000/api/estado
- http://127.0.0.1:8000/docs

## 2. Preparar y ejecutar el frontend

Abra una segunda terminal de PowerShell:

~~~powershell
cd C:\Users\chari\Documents\ComputoEstIA\frontend
npm install
npm run dev
~~~

Abra la dirección indicada por Vite, normalmente http://localhost:5173.

## 3. Prueba completa

1. Ingrese al frontend.
2. Abra o cree un proyecto.
3. Seleccione **Cargar documentación**.
4. Para reproducir el caso histórico, cargue estos archivos:
   - backend\data\pdf\Fundaciones\Fundaciones_1.pdf;
   - backend\data\pdf\Fundaciones\Fundaciones_2.pdf;
   - backend\data\pdf\Columnas\Columnas.pdf.
5. Presione **Iniciar análisis**.

El resultado esperado para este juego de planos es:

- 61 fundaciones;
- 13 tipos;
- 194,720 m³ de hormigón;
- 10.774,309 kg de acero teórico;
- 530 barras comerciales;
- 308,890 m² de encofrado lateral.

El botón **Descargar JSON** guarda el resultado real devuelto por Python.

## Alcance de esta integración

La API recibe archivos de hasta 25 MB y valida extensión y firma PDF. Clasifica
cada página por su contenido y no depende de tres nombres predeterminados. La
configuración histórica `proyecto_actual.json` solo se utiliza cuando se invoca
explícitamente desde la línea de comandos.

Un juego de planos diferente se procesa sin correcciones particulares. En esta
primera versión, si ese proyecto necesita excepciones propias, la API informará
la inconsistencia; la carga de una configuración personalizada será una etapa
posterior.

Los proyectos de ejemplo del dashboard continúan siendo datos de interfaz. El
flujo **cargar → procesar → resultados** sí está conectado al backend real.

## v18 — Motor de acero conectado al núcleo

- Las armaduras se extraen como propiedades documentales estructuradas.
- El núcleo decide si la operación `acero` es computable, parcial o pendiente.
- El motor de fundaciones calcula kg únicamente para elementos declarados computables.
- La cantidad física proviene exclusivamente de fuentes con rol `ubicacion`; los cuadros/detalles solo aportan definiciones.
- Las notaciones `SUPERIOR INFERIOR` con una especificación compartida requieren confirmación profesional antes del cómputo.
- El resultado incluye detalle auditable, fórmulas, resumen por diámetro, barras comerciales y pendientes.

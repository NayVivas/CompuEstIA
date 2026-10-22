# CómputoEstIA — backend V12 / EXP22

Aplicación determinística en Python para extraer información de planos
estructurales PDF y producir cómputos métricos trazables.

La clasificación de páginas utiliza EXP22: fusión explicable de texto,
posición textual, imagen renderizada, geometría vectorial y OCR adaptativo.
EXP19 se conserva como modelo textual base. Los cálculos continúan siendo
determinísticos y no son realizados por el clasificador.

## Estado de la generalización

La arquitectura ya no está atada a que una referencia comience con `F` ni a
una rotación fija del PDF. El flujo de fundaciones:

1. analiza el contenido y la orientación de las páginas;
2. descubre el catálogo de referencias desde el cuadro;
3. admite nomenclaturas como `F1`, `Z-01`, `ZA.002`, `PF_03` o `P-1A`;
4. localiza en la planta solamente las referencias autorizadas por el cuadro;
5. reconstruye filas y columnas por sus posiciones visuales;
6. normaliza dimensiones expresadas en metros, centímetros o milímetros;
7. valida inconsistencias antes de calcular cantidades.

Las excepciones de un juego de planos no están incorporadas al motor general.
Se declaran, con su motivo, en un JSON opcional de `configuraciones/`. Así se
evita que la corrección de un plano altere el procesamiento de todos los demás.

> Importante: esto representa una generalización real del módulo de
> fundaciones, pero todavía no garantiza compatibilidad cuantitativa con todo
> PDF posible. Las páginas escaneadas pasan por OCR local y quedan sujetas a
> confirmación visual. Nuevas tipologías, formas de escribir armaduras y algunas
> variantes de columnas o vigas requieren reglas adicionales o validación del
> usuario.

## Organización del proyecto

```text
ProyectoFinal/
├── app.py                         # acceso al flujo completo
├── analizar_planos.py             # diagnóstico general de PDF
├── requirements.txt
├── configuraciones/
│   ├── README.md
│   └── proyecto_actual.json       # excepciones del caso de validación
├── computos/
│   ├── configuracion/             # rutas y parámetros técnicos
│   ├── documentos/                # análisis, modelos y lectura de PDF
│   ├── fundaciones/               # detección, cuadro, acero y encofrado
│   ├── columnas/                  # detección y asociaciones
│   ├── vigas/                     # vigas de riostra
│   ├── salida/                    # escritura de JSON y CSV
│   └── flujos/                    # coordinación de comandos
├── data/
│   ├── pdf/                       # documentos de entrada
│   ├── analysis/                  # manifiestos de diagnóstico
│   ├── processed/                 # datos estructurados
│   ├── reportes/                  # resultados JSON y CSV
│   ├── png/                       # controles visuales
│   └── registros/                 # salidas históricas de consola
├── tests/                         # pruebas automáticas
└── experimentos/                  # prototipos históricos, no flujo principal
```

Los archivos `app.py` y `analizar_planos.py` de la raíz son accesos pequeños y
estables. La implementación se encuentra dentro del paquete `computos`.

## Instalación en Windows

Use Python 3.12, 3.13 o 3.14. Abra PowerShell dentro de la carpeta
`backend` y ejecute:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

La carpeta `.venv` no está incluida en el ZIP porque depende de cada equipo y
de la versión local de Python. Se genera una sola vez con esos comandos.

## Comprobar la instalación

```powershell
python -m unittest discover -s tests -v
```

La ejecución debe finalizar con `OK`.

## Ejecutar el caso incluido

Los planos suministrados contienen dos rótulos `F12` en el cuadro. La
corrección auditada de la segunda aparición a `F13` está en
`configuraciones/proyecto_actual.json`:

```powershell
python app.py --config-proyecto configuraciones\proyecto_actual.json
```

También se puede usar:

```powershell
python -m computos --config-proyecto configuraciones\proyecto_actual.json
```

## Ejecutar otro juego de planos

Si el nuevo cuadro es consistente y no necesita excepciones:

```powershell
python app.py --planta "C:\ruta\planta.pdf" --detalles "C:\ruta\detalles.pdf" --columnas "C:\ruta\columnas.pdf"
```

No se debe reutilizar `proyecto_actual.json` con archivos distintos. Si el
nuevo proyecto contiene una inconsistencia documentada, cree otro JSON según
el ejemplo explicado en `configuraciones/README.md` y agréguelo con
`--config-proyecto`.

## Analizar documentos antes del cómputo

Para diagnosticar uno o varios PDF sin calcular cantidades:

```powershell
python analizar_planos.py data\pdf
```

El comando informa páginas, rotaciones, cantidad de texto, objetos vectoriales,
roles probables y si un documento requiere un futuro modo asistido. Guarda el
manifiesto en `data/analysis/manifiesto_documentos.json`.

## Resultados

El flujo completo genera, entre otros:

- `data/reportes/resumen_general.json`;
- `data/reportes/volumenes_fundaciones.csv`;
- `data/reportes/acero_fundaciones.csv`;
- `data/reportes/compra_acero.csv`;
- `data/reportes/encofrado_zapatas.csv`;
- `data/processed/catalogo_referencias_fundaciones.json`;
- `data/processed/cuadro_fundaciones_interpretado.json`;
- `data/png/fundaciones_detectadas.png`.

El catálogo y el cuadro interpretado conservan encabezados, referencias,
advertencias, confianza y correcciones aplicadas para poder auditar el cálculo.

## Parámetros generales

Los parámetros técnicos están en
`computos/configuracion/parametros.py`: recubrimiento, doblez, longitud
comercial, desperdicio, unidad predeterminada y tolerancias geométricas.

El motor se detiene en vez de inventar resultados cuando encuentra referencias
duplicadas sin resolver, faltan dimensiones obligatorias o la armadura no se
puede interpretar.

## Alcance pendiente

- OCR: está integrado mediante Tesseract para clasificación y extracción
  posicional, pero su resultado siempre requiere confirmación visual.
- Geometría distribuida: permite revisar X, Y y H por ocurrencia de zapata y
  calcular hormigón y encofrado. El acero permanece pendiente si no existe una
  fuente inequívoca.
- Tipologías: los cimientos corridos cuentan con propuesta y cálculo tras
  revisión geométrica. Las losas de cimentación y los pilotes se clasifican,
  pero todavía no tienen un motor cuantitativo implementado.
- Armaduras: actualmente se interpreta la notación con fracciones de pulgada
  utilizada por los planos de prueba.
- Columnas y pedestales: funcionan para el caso validado, pero necesitan más
  muestras para ampliar sus reglas.
- Vigas de riostra: se detectan rótulos, bordes y ejes candidatos; esos ejes aún
  no se usan para un cómputo definitivo.

El programa es una herramienta de apoyo. Los resultados deben conservar la
revisión profesional del responsable del proyecto estructural.

## API para el frontend

Instale las dependencias del archivo requirements.txt y ejecute:

~~~powershell
uvicorn computos.api:app --reload --port 8000
~~~

Comprobaciones:

- GET http://127.0.0.1:8000/api/estado;
- documentación interactiva en http://127.0.0.1:8000/docs;
- POST http://127.0.0.1:8000/api/analisis/automatico/ con uno o más campos
  `archivos`; cada PDF puede tener una o varias páginas.
- POST http://127.0.0.1:8000/api/analisis/ sigue disponible como ruta heredada
  para los tres campos explícitos `planta`, `detalles` y `columnas`.

La API automática devuelve primero la clasificación y la capacidad real del
motor. Cuando las fuentes son compatibles, devuelve las cantidades y el
diagnóstico de los documentos; si las cotas están distribuidas, solicita una
revisión geométrica vinculada a los PDF exactos. Conserva
en memoria los últimos 50 análisis; reiniciar el servidor elimina ese historial
de API, pero no afecta los resultados guardados por el frontend.

`GET /api/estado` debe devolver la versión `0.4.4`, el contrato `6` y el build
`2026-10-19-v12.3.2-revision-planta`. Si el frontend detecta otro contrato o build, bloquea el
análisis para impedir que se mezclen carpetas de versiones distintas.

## Centro de incidencias y revisión de ingeniería

El análisis ya no depende exclusivamente de excepciones de texto cuando una
validación impide continuar. Los bloqueos se devuelven como `incidencias`
estructuradas con evidencia, severidad, opciones y estado de revisión.

El flujo normal es:

1. el motor detecta la incidencia;
2. la API conserva los PDF de entrada del análisis;
3. el frontend muestra la evidencia y las opciones al ingeniero;
4. la decisión queda registrada con revisor, fecha y justificación;
5. cuando la decisión puede aplicarse automáticamente, se reejecuta el motor;
6. si aparece otra incidencia, se abre un nuevo ciclo de revisión.

`--config-proyecto` continúa disponible como mecanismo avanzado y auditable,
pero ya no es necesario para resolver manualmente desde la interfaz una
incidencia compatible con el centro de revisión.

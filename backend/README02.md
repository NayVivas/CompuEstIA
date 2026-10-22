# CómputoEstIA

Aplicación determinística en Python para extraer información de planos
estructurales PDF y producir cómputos métricos trazables.

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
> fundaciones, pero todavía no garantiza compatibilidad automática con todo PDF
> posible. Los planos escaneados, nuevas formas de escribir armaduras y algunas
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

Abra PowerShell dentro de la carpeta descomprimida y ejecute:

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

- PDF escaneados: requieren OCR o un modo asistido que aún no está integrado.
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
- POST http://127.0.0.1:8000/api/analisis/ con los campos PDF
  planta, detalles y columnas.

La API devuelve el resumen, las 13 filas de fundaciones, el detalle de
armaduras y el diagnóstico de los documentos. Para esta primera prueba conserva
en memoria los últimos 50 análisis; reiniciar el servidor elimina ese historial
de API, pero no afecta los resultados guardados por el frontend.

## EXP20: modo asistido con IA generativa

El modo asistido se limita a planos estructurales. La IA clasifica el documento
y extrae referencias, dimensiones, armaduras y evidencia visible mediante una
salida JSON tipada. No calcula volúmenes, acero ni encofrado: esos resultados
siguen perteneciendo al motor determinístico y requieren revisión profesional.

Configuración en PowerShell:

```powershell
$env:OPENAI_API_KEY="tu-clave"
$env:COMPUTOESTIA_IA_MODEL="gpt-6-sol"
uvicorn computos.api:app --reload --port 8000
```

Endpoints:

- `GET /api/ia/estado` informa si la integración está configurada;
- `POST /api/ia/analizar-estructura/` recibe un campo `plano` en PDF;
- el resultado queda disponible también mediante el endpoint habitual de
  consulta por `analisis_id`.

La clave nunca debe guardarse en el repositorio ni enviarse desde el frontend.

from decimal import Decimal
from pathlib import Path


# ``parametros.py`` vive en ``computos/configuracion``. La raíz del proyecto
# está dos niveles por encima y desde allí se resuelven todas las carpetas de
# entrada y salida, independientemente del directorio desde el que se ejecute.
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
PDF_DIR = DATA_DIR / "pdf"
PNG_DIR = DATA_DIR / "png"
CACHE_DIR = DATA_DIR / "cache"
REPORT_DIR = DATA_DIR / "reportes"
PROCESSED_DIR = DATA_DIR / "processed"
ANALYSIS_DIR = DATA_DIR / "analysis"

for carpeta in (
    PDF_DIR,
    PNG_DIR,
    CACHE_DIR,
    REPORT_DIR,
    PROCESSED_DIR,
    ANALYSIS_DIR,
):
    carpeta.mkdir(parents=True, exist_ok=True)


# Parámetros técnicos ingresados por el usuario.
RECUBRIMIENTO_FUNDACION_CM = Decimal("7.5")
LONGITUD_DOBLEZ_CM = Decimal("15")
LONGITUD_BARRA_COMERCIAL_M = Decimal("12")
DESPERDICIO_ACERO_PORCENTAJE = Decimal("5")
USAR_ENCOFRADO_ZAPATAS = True

# Se usa solamente cuando un cuadro no informa unidades junto a X, Y o H.
# Valores admitidos: "m", "cm" o "mm".
UNIDAD_DIMENSIONES_CUADRO = "m"

# Las correcciones de rótulos concretos se cargan desde un JSON indicado con
# ``--config-proyecto``. No forman parte de los parámetros generales.

INCREMENTO_PEDESTAL_CM = Decimal(
    "10"
)

ALTURA_MINIMA_PEDESTAL_M = Decimal(
    "1.50"
)

USAR_ENCOFRADO_PEDESTALES = True


# Parámetros para leer los bordes vectoriales de las vigas.
# El valor 0.60 fue obtenido inspeccionando Fundaciones_1.pdf.
ESPESOR_VECTOR_VIGA_PT = 0.60
TOLERANCIA_ESPESOR_VECTOR_PT = 0.02
LONGITUD_MINIMA_LINEA_VIGA_PT = 15.0
MARGEN_ZONA_ESTRUCTURAL_PT = 10.0
ESCALA_IMAGEN_DIAGNOSTICO = 2.0
DIFERENCIA_ANGULAR_MAXIMA_BORDES_GRADOS = 0.50
SEPARACION_MINIMA_BORDES_PT = 4.40
SEPARACION_MAXIMA_BORDES_PT = 6.50
SUPERPOSICION_MINIMA_BORDES = 0.90
DIFERENCIA_LONGITUD_MAXIMA_BORDES = 0.20
TOLERANCIA_EJES_DUPLICADOS_PT = 0.50

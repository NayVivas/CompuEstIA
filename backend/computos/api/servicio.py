"""Adaptación del motor de cómputo para su uso desde la API."""

from collections import Counter
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
import json
from pathlib import Path
from threading import Lock

from computos.configuracion.parametros import (
    BASE_DIR,
)
from computos.configuracion.proyecto import (
    ConfiguracionProyecto,
)
from computos.documentos.analisis import (
    analizar_documento_pdf,
)
from computos.flujos.principal import (
    procesar_fundaciones,
)
from computos.fundaciones.revision_cuadro import (
    preparar_revision_cuadro,
    guardar_revision_cuadro,
)


_BLOQUEO_MOTOR = Lock()

_ARCHIVO_UBICACIONES = BASE_DIR / "data" / "processed" / "fundaciones_detectadas.json"


def _seleccionar_configuracion(archivos):
    """Ninguna carga web hereda correcciones del caso de demostración."""
    return ConfiguracionProyecto.vacia(), False


def _aplicar_resoluciones_tecnicas(configuracion, archivos, resoluciones):
    """Convierte decisiones ya validadas en parámetros consumibles por el motor."""

    for decision in resoluciones or []:
        accion = decision.get("accion")
        rol = decision.get("rol")
        if rol not in archivos:
            raise ValueError("La fuente técnica seleccionada no pertenece al motor activo.")
        if accion == "reasignar_referencia_detalle":
            if rol not in {"detalles", "columnas"}:
                raise ValueError(
                    "La reasignación de rótulo debe corresponder a un "
                    "detalle de columna usado por este motor."
                )
            configuracion.reasignaciones_detalles_columnas.append(
                {
                    "rol": rol,
                    "pagina": decision["pagina_motor"],
                    "referencia_original": decision[
                        "referencia_original"
                    ],
                    "referencia_correcta": decision[
                        "referencia_correcta"
                    ],
                    "revisor": decision["revisor"],
                    "motivo": decision["motivo"],
                }
            )
        elif accion == "seleccionar_fuente_columna":
            configuracion.selecciones_fuentes_columnas.append(
                {
                    "campo": decision["campo"],
                    "referencia": decision["referencia"],
                    "origen": Path(archivos[rol]).name,
                    "pagina": decision["pagina_motor"],
                    "revisor": decision["revisor"],
                    "motivo": decision["motivo"],
                }
            )
        elif accion == "definir_seccion_columna":
            configuracion.secciones_manuales_columnas[decision["referencia"]] = {
                "dimension_1_m": decision["dimension_1_m"],
                "dimension_2_m": decision["dimension_2_m"],
                "origen": Path(archivos[rol]).name,
                "pagina": decision["pagina_motor"],
                "revisor": decision["revisor"],
                "motivo": decision["motivo"],
            }
    return configuracion


def _resumir_documento(
    documento,
) -> dict:
    roles = sorted(
        {
            rol.value
            for pagina in documento.paginas
            for rol in (
                pagina.roles_candidatos
            )
        }
    )

    rotaciones = sorted(
        {
            pagina.rotacion_grados
            for pagina in documento.paginas
        }
    )

    return {
        "nombre": documento.nombre,
        "sha256": documento.sha256,
        "cantidad_paginas": (
            documento.cantidad_paginas
        ),
        "tipo_contenido": (
            documento.tipo_contenido.value
        ),
        "total_palabras": (
            documento.total_palabras
        ),
        "total_objetos_vectoriales": (
            documento.total_objetos_vectoriales
        ),
        "requiere_modo_asistido": (
            documento.requiere_modo_asistido
        ),
        "roles_detectados": roles,
        "rotaciones_grados": rotaciones,
    }


def _confianza_lectura(
    resultado: dict,
) -> float:
    niveles = {
        "alta": 100.0,
        "media": 75.0,
        "baja": 40.0,
    }

    catalogo = niveles.get(
        resultado.get(
            "confianza_catalogo"
        ),
        0.0,
    )

    cuadro = niveles.get(
        resultado.get(
            "confianza_cuadro"
        ),
        0.0,
    )

    return min(
        catalogo,
        cuadro,
    )


def _numero(
    valor,
    predeterminado=0.0,
) -> float:
    try:
        return float(valor)
    except (
        TypeError,
        ValueError,
    ):
        return float(
            predeterminado
        )


def _entero(
    valor,
    predeterminado=0,
) -> int:
    try:
        return int(valor)
    except (
        TypeError,
        ValueError,
    ):
        return int(
            predeterminado
        )


def _cargar_detecciones_generadas() -> list[dict]:
    """
    Lee las ubicaciones producidas por el motor.

    El archivo es generado nuevamente en cada análisis,
    dentro del bloqueo del motor.
    """

    if not _ARCHIVO_UBICACIONES.is_file():
        return []

    try:
        contenido = json.loads(
            _ARCHIVO_UBICACIONES.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ):
        return []

    if not isinstance(
        contenido,
        list,
    ):
        return []

    return [
        elemento
        for elemento in contenido
        if isinstance(
            elemento,
            dict,
        )
    ]


def _clave_orden_visual(
    ubicacion: dict,
) -> tuple:
    """
    Ordena visualmente:

    1. página;
    2. de arriba hacia abajo;
    3. de izquierda a derecha.
    """

    return (
        _entero(
            ubicacion.get("pagina"),
            1,
        ),
        _numero(
            ubicacion.get(
                "y0_visual",
                ubicacion.get("y0"),
            )
        ),
        _numero(
            ubicacion.get(
                "x0_visual",
                ubicacion.get("x0"),
            )
        ),
        str(
            ubicacion.get(
                "referencia",
                "",
            )
        ),
    )


def _cantidades_esperadas(
    fundaciones: list[dict],
) -> dict[str, int]:
    cantidades = {}

    for fundacion in fundaciones:
        referencia = str(
            fundacion.get(
                "referencia",
                "",
            )
        ).strip()

        if not referencia:
            continue

        cantidades[referencia] = (
            _entero(
                fundacion.get(
                    "cantidad"
                )
            )
        )

    return cantidades


def _normalizar_ubicaciones(
    detecciones: list[dict],
    fundaciones: list[dict],
) -> tuple[list[dict], dict]:
    """
    Agrega identificadores estables y valida cantidades.

    Los identificadores se generan por referencia:

        F1-01
        F1-02
        F2-01
        etc.
    """

    detecciones_ordenadas = sorted(
        detecciones,
        key=_clave_orden_visual,
    )

    apariciones = Counter()
    ubicaciones = []

    for orden_global, deteccion in enumerate(
        detecciones_ordenadas,
        start=1,
    ):
        referencia = str(
            deteccion.get(
                "referencia",
                "",
            )
        ).strip()

        if not referencia:
            continue

        apariciones[referencia] += 1
        aparicion = apariciones[
            referencia
        ]

        x0_visual = _numero(
            deteccion.get(
                "x0_visual",
                deteccion.get("x0"),
            )
        )

        y0_visual = _numero(
            deteccion.get(
                "y0_visual",
                deteccion.get("y0"),
            )
        )

        x1_visual = _numero(
            deteccion.get(
                "x1_visual",
                deteccion.get("x1"),
            )
        )

        y1_visual = _numero(
            deteccion.get(
                "y1_visual",
                deteccion.get("y1"),
            )
        )

        centro_x_visual = (
            x0_visual + x1_visual
        ) / 2

        centro_y_visual = (
            y0_visual + y1_visual
        ) / 2

        ubicacion = dict(
            deteccion
        )

        ubicacion.update(
            {
                "identificador": (
                    f"{referencia}-"
                    f"{aparicion:02d}"
                ),
                "aparicion": aparicion,
                "orden_visual_global": (
                    orden_global
                ),
                "centro_x_visual": round(
                    centro_x_visual,
                    2,
                ),
                "centro_y_visual": round(
                    centro_y_visual,
                    2,
                ),
                "ubicacion_pdf_detectada": True,
                "ejes_confirmados": False,
                "estado_ubicacion": (
                    "ubicada_en_pdf"
                ),
                "sistema_coordenadas": (
                    "Coordenadas visuales "
                    "normalizadas según "
                    "la rotación del PDF."
                ),
            }
        )

        ubicaciones.append(
            ubicacion
        )

    esperadas = (
        _cantidades_esperadas(
            fundaciones
        )
    )

    detectadas = Counter(
        ubicacion["referencia"]
        for ubicacion in ubicaciones
    )

    diferencias = []

    referencias = list(
        esperadas.keys()
    )

    for referencia in detectadas:
        if referencia not in esperadas:
            referencias.append(
                referencia
            )

    for referencia in referencias:
        cantidad_esperada = (
            esperadas.get(
                referencia,
                0,
            )
        )

        cantidad_detectada = (
            detectadas.get(
                referencia,
                0,
            )
        )

        if (
            cantidad_esperada
            != cantidad_detectada
        ):
            diferencias.append(
                {
                    "referencia": (
                        referencia
                    ),
                    "cantidad_esperada": (
                        cantidad_esperada
                    ),
                    "cantidad_detectada": (
                        cantidad_detectada
                    ),
                    "diferencia": (
                        cantidad_detectada
                        - cantidad_esperada
                    ),
                }
            )

    validacion = {
        "cantidad_esperada": sum(
            esperadas.values()
        ),
        "cantidad_detectada": len(
            ubicaciones
        ),
        "coincide_con_resumen": (
            len(diferencias) == 0
            and sum(
                esperadas.values()
            )
            == len(ubicaciones)
        ),
        "conteo_por_referencia": {
            referencia: (
                detectadas.get(
                    referencia,
                    0,
                )
            )
            for referencia in referencias
        },
        "diferencias": diferencias,
        "criterio_numeracion": (
            "Página, posición vertical "
            "y posición horizontal."
        ),
        "ejes_disponibles": False,
    }

    return (
        ubicaciones,
        validacion,
    )


def procesar_archivos(
    *,
    planta: Path,
    detalles: Path,
    columnas: Path,
    porticos: Path | None = None,
    paginas_origen_porticos: list[int] | None = None,
    revision_cuadro: dict | None = None,
    proyecto_id: str | None = None,
    resoluciones_tecnicas: list[dict] | None = None,
) -> dict:
    """
    Procesa tres PDF cargados y devuelve una respuesta
    trazable para el frontend.
    """

    archivos = {
        "planta": Path(planta),
        "detalles": Path(detalles),
        "columnas": Path(columnas),
    }
    if porticos is not None:
        archivos["porticos"] = Path(porticos)

    (
        configuracion,
        configuracion_automatica,
    ) = _seleccionar_configuracion(
        archivos
    )

    # El motor escribe reportes compartidos.
    # El bloqueo evita mezclar dos análisis simultáneos.
    with (
        _BLOQUEO_MOTOR,
        redirect_stdout(
            StringIO()
        ),
    ):
        configuracion, registro_revision, ruta_revision = preparar_revision_cuadro(
            archivos, configuracion, revision_cuadro, proyecto_id,
        )
        configuracion = _aplicar_resoluciones_tecnicas(
            configuracion, archivos, resoluciones_tecnicas
        )
        resultado = (
            procesar_fundaciones(
                archivos["planta"],
                archivos["detalles"],
                configuracion,
                ruta_columnas=archivos["columnas"],
                ruta_porticos=archivos.get("porticos"),
                paginas_origen_porticos=paginas_origen_porticos,
            )
        )

        detecciones = (
            _cargar_detecciones_generadas()
        )

        (
            ubicaciones,
            validacion_ubicaciones,
        ) = _normalizar_ubicaciones(
            detecciones,
            resultado.get(
                "fundaciones",
                [],
            ),
        )

        documentos = [
            analizar_documento_pdf(ruta)
            for ruta in archivos.values()
        ]
        guardar_revision_cuadro(ruta_revision, registro_revision)

    respuesta = dict(
        resultado
    )
    if registro_revision:
        respuesta["revisiones_cuadro"] = registro_revision["revisiones"]
        respuesta["configuracion_automatica"] = False

    respuesta.update(
        {
            "fecha_analisis": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
            "cantidad_documentos": len(
                documentos
            ),
            "cantidad_tipos": len(
                resultado[
                    "referencias_fundaciones"
                ]
            ),
            "confianza_lectura_porcentaje": (
                _confianza_lectura(
                    resultado
                )
            ),
            "configuracion_automatica": (
                configuracion_automatica and registro_revision is None
            ),
            "documentos": [
                _resumir_documento(
                    documento
                )
                for documento in documentos
            ],
            "ubicaciones_fundaciones": (
                ubicaciones
            ),
            "validacion_ubicaciones": (
                validacion_ubicaciones
            ),
        }
    )

    return respuesta

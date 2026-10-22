"""Aplicación FastAPI que conecta el frontend con el motor de cómputo."""

from collections import OrderedDict
import logging
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from typing import Annotated, Any, Literal
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from computos.api.revisiones import (
    aplicar_revision_ingeniero,
    aplicar_revision_seccion_viga,
)
from computos.api.exp02_anotador import router as exp02_router
from computos.api.exp16_anotador import router as exp16_router
from computos.ia.flujo_hibrido import procesar_archivos_hibrido
from computos.ia.proveedor import (
    ConfiguracionIAError,
    ProveedorIAError,
)
from computos.ia.servicio import analizar_pdf_estructural


LIMITE_ARCHIVO_BYTES = 25 * 1024 * 1024
TAMANIO_BLOQUE_BYTES = 1024 * 1024
MAXIMO_RESULTADOS_MEMORIA = 50

_logger = logging.getLogger(__name__)
_resultados: OrderedDict[str, dict] = OrderedDict()
_bloqueo_resultados = Lock()


class RevisionSeccionVigaEntrada(BaseModel):
    """Decisión profesional para una sección contradictoria."""

    alerta_id: str = Field(
        min_length=1,
        max_length=200,
    )
    tramo_id: str = Field(
        min_length=1,
        max_length=100,
    )
    fuente_seleccionada: Literal[
        "planta",
        "detalle",
        "manual",
    ]
    ancho_m: float | None = Field(
        default=None,
        gt=0,
        le=5,
    )
    alto_m: float | None = Field(
        default=None,
        gt=0,
        le=5,
    )
    motivo: str = Field(
        min_length=10,
        max_length=1000,
    )
    revisor: str = Field(
        min_length=2,
        max_length=160,
    )
    confirmar_armadura_detalle: bool


class RevisionIngenieroEntrada(BaseModel):
    """Decisión profesional aplicable a cualquier familia."""

    alerta_id: str = Field(
        min_length=1,
        max_length=200,
    )
    accion: Literal[
        "validar_seccion",
        "validar_geometria",
        "asignar_armadura",
        "validar_alturas",
        "confirmar_asociacion",
        "descartar_asociacion",
        "confirmar_revision",
        "registrar_observacion",
    ]
    motivo: str = Field(
        min_length=10,
        max_length=1000,
    )
    revisor: str = Field(
        min_length=2,
        max_length=160,
    )
    valores: dict[str, Any] = Field(
        default_factory=dict,
    )
    confirmaciones: dict[str, bool] = Field(
        default_factory=dict,
    )


def _origenes_permitidos() -> list[str]:
    valor = os.getenv(
        "COMPUTOESTIA_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )

    return [
        origen.strip()
        for origen in valor.split(",")
        if origen.strip()
    ]


app = FastAPI(
    title="CómputoEstIA API",
    version="0.1.0",
    description=(
        "API local para procesar y revisar planos estructurales PDF."
    ),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origenes_permitidos(),
    allow_origin_regex=(
        r"^http://(localhost|127\.0\.0\.1):\d+$"
    ),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


async def _guardar_pdf(
    archivo: UploadFile,
    carpeta: Path,
    campo: str,
) -> Path:
    nombre = Path(archivo.filename or "").name

    if (
        not nombre
        or Path(nombre).suffix.casefold() != ".pdf"
    ):
        raise HTTPException(
            status_code=422,
            detail=f"{campo} debe ser un archivo PDF.",
        )

    destino = carpeta / campo / nombre
    destino.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    total = 0

    with destino.open("wb") as salida:
        while bloque := await archivo.read(
            TAMANIO_BLOQUE_BYTES
        ):
            total += len(bloque)

            if total > LIMITE_ARCHIVO_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=(
                        f"{campo} supera el límite de 25 MB."
                    ),
                )

            salida.write(bloque)

    with destino.open("rb") as entrada:
        firma = entrada.read(5)

    if total == 0 or firma != b"%PDF-":
        raise HTTPException(
            status_code=422,
            detail=f"{campo} no contiene un PDF válido.",
        )

    return destino


def _guardar_resultado(
    analisis_id: str,
    respuesta: dict,
) -> None:
    with _bloqueo_resultados:
        _resultados[analisis_id] = respuesta
        _resultados.move_to_end(analisis_id)

        while (
            len(_resultados)
            > MAXIMO_RESULTADOS_MEMORIA
        ):
            _resultados.popitem(last=False)


def _respuesta_analisis(
    analisis_id: str,
    resultado: dict,
) -> dict:
    resultado_con_id = {
        **resultado,
        "analisis_id": analisis_id,
    }

    return jsonable_encoder(
        {
            "analisis_id": analisis_id,
            "estado": "completado",
            "resultado": resultado_con_id,
        }
    )


@app.get("/api/estado", tags=["sistema"])
def consultar_estado() -> dict:
    return {
        "estado": "disponible",
        "servicio": "CómputoEstIA API",
        "version": app.version,
    }


@app.get("/api/ia/estado", tags=["ia-asistida"])
def consultar_estado_ia() -> dict:
    """Informa si el modo asistido puede realizar llamadas reales."""

    return {
        "modo": "asistido_ia_generativa",
        "alcance": "planos_estructurales",
        "configurado": bool(
            os.getenv("OPENAI_API_KEY", "").strip()
        ),
        "modelo": os.getenv(
            "COMPUTOESTIA_IA_MODEL",
            "gpt-6-sol",
        ),
        "calculos_realizados_por_ia": False,
    }


@app.post(
    "/api/ia/analizar-estructura/",
    tags=["ia-asistida"],
)
async def iniciar_analisis_estructural_ia(
    plano: Annotated[
        UploadFile,
        File(
            description=(
                "Plano o conjunto de planos estructurales en PDF"
            )
        ),
    ],
) -> dict:
    """Extrae evidencia estructurada sin delegar los cálculos a la IA."""

    try:
        with TemporaryDirectory(
            prefix="computoestia-ia-"
        ) as temporal:
            ruta = await _guardar_pdf(
                plano,
                Path(temporal),
                "plano",
            )
            try:
                resultado = await run_in_threadpool(
                    analizar_pdf_estructural,
                    ruta,
                )
            except ConfiguracionIAError as error:
                raise HTTPException(
                    status_code=503,
                    detail=str(error),
                ) from error
            except ProveedorIAError as error:
                _logger.exception(
                    "Error del proveedor de IA generativa"
                )
                raise HTTPException(
                    status_code=502,
                    detail=str(error),
                ) from error
            except (FileNotFoundError, ValueError) as error:
                raise HTTPException(
                    status_code=422,
                    detail=str(error),
                ) from error
    finally:
        await plano.close()

    analisis_id = uuid4().hex
    respuesta = _respuesta_analisis(
        analisis_id,
        resultado,
    )
    _guardar_resultado(
        analisis_id,
        respuesta,
    )
    return respuesta


@app.post("/api/analisis/", tags=["analisis"])
async def iniciar_analisis(
    planta: Annotated[
        UploadFile,
        File(
            description=(
                "Plano de planta de fundaciones"
            )
        ),
    ],
    detalles: Annotated[
        UploadFile,
        File(
            description=(
                "Cuadro y detalles de fundaciones"
            )
        ),
    ],
    columnas: Annotated[
        UploadFile,
        File(
            description="Plano general de columnas"
        ),
    ],
) -> dict:
    cargas = {
        "planta": planta,
        "detalles": detalles,
        "columnas": columnas,
    }

    try:
        with TemporaryDirectory(
            prefix="computoestia-"
        ) as temporal:
            carpeta = Path(temporal)
            rutas = {
                campo: await _guardar_pdf(
                    archivo,
                    carpeta,
                    campo,
                )
                for campo, archivo in cargas.items()
            }

            try:
                resultado = await run_in_threadpool(
                    procesar_archivos_hibrido,
                    **rutas,
                )
            except (
                FileNotFoundError,
                ValueError,
            ) as error:
                raise HTTPException(
                    status_code=422,
                    detail=str(error),
                ) from error
            except Exception as error:  # pragma: no cover
                _logger.exception(
                    "Error inesperado al procesar los planos"
                )
                raise HTTPException(
                    status_code=500,
                    detail=(
                        "No se pudieron procesar los planos."
                    ),
                ) from error
    finally:
        for archivo in cargas.values():
            await archivo.close()

    analisis_id = uuid4().hex
    respuesta = _respuesta_analisis(
        analisis_id,
        resultado,
    )
    _guardar_resultado(
        analisis_id,
        respuesta,
    )

    return respuesta


@app.get(
    "/api/analisis/{analisis_id}/resultados/",
    tags=["analisis"],
)
def consultar_resultados(
    analisis_id: str,
) -> dict:
    with _bloqueo_resultados:
        respuesta = _resultados.get(analisis_id)

        if respuesta is not None:
            _resultados.move_to_end(analisis_id)

    if respuesta is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No se encontró el análisis solicitado."
            ),
        )

    return respuesta


@app.post(
    (
        "/api/analisis/{analisis_id}/"
        "revisiones/"
    ),
    tags=["revisiones"],
)
def revisar_alerta_analisis(
    analisis_id: str,
    entrada: RevisionIngenieroEntrada,
) -> dict:
    """Registra y aplica una revisión profesional normalizada."""

    datos = (
        entrada.model_dump()
        if hasattr(entrada, "model_dump")
        else entrada.dict()
    )

    with _bloqueo_resultados:
        respuesta_actual = _resultados.get(
            analisis_id
        )

        if respuesta_actual is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "No se encontró el análisis solicitado."
                ),
            )

        try:
            resultado_actualizado = (
                aplicar_revision_ingeniero(
                    respuesta_actual["resultado"],
                    **datos,
                )
            )
        except LookupError as error:
            raise HTTPException(
                status_code=404,
                detail=str(error),
            ) from error
        except RuntimeError as error:
            raise HTTPException(
                status_code=409,
                detail=str(error),
            ) from error
        except (
            TypeError,
            ValueError,
        ) as error:
            raise HTTPException(
                status_code=422,
                detail=str(error),
            ) from error

        respuesta_actualizada = _respuesta_analisis(
            analisis_id,
            resultado_actualizado,
        )
        _resultados[analisis_id] = (
            respuesta_actualizada
        )
        _resultados.move_to_end(analisis_id)

    return respuesta_actualizada


@app.post(
    (
        "/api/analisis/{analisis_id}/"
        "revisiones/seccion-viga/"
    ),
    tags=["revisiones"],
)
def revisar_seccion_viga(
    analisis_id: str,
    entrada: RevisionSeccionVigaEntrada,
) -> dict:
    """Registra la decisión y recalcula un único tramo."""

    datos = (
        entrada.model_dump()
        if hasattr(entrada, "model_dump")
        else entrada.dict()
    )

    with _bloqueo_resultados:
        respuesta_actual = _resultados.get(
            analisis_id
        )

        if respuesta_actual is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "No se encontró el análisis solicitado."
                ),
            )

        try:
            resultado_actualizado = (
                aplicar_revision_seccion_viga(
                    respuesta_actual["resultado"],
                    **datos,
                )
            )
        except LookupError as error:
            raise HTTPException(
                status_code=404,
                detail=str(error),
            ) from error
        except RuntimeError as error:
            raise HTTPException(
                status_code=409,
                detail=str(error),
            ) from error
        except (
            TypeError,
            ValueError,
        ) as error:
            raise HTTPException(
                status_code=422,
                detail=str(error),
            ) from error

        respuesta_actualizada = _respuesta_analisis(
            analisis_id,
            resultado_actualizado,
        )
        _resultados[analisis_id] = (
            respuesta_actualizada
        )
        _resultados.move_to_end(analisis_id)

    return respuesta_actualizada


app.include_router(exp02_router)
app.include_router(exp16_router)

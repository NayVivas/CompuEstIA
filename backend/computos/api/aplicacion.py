"""Aplicación FastAPI que conecta el frontend con el motor de cómputo."""

from collections import OrderedDict
from copy import deepcopy
import json
import logging
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from typing import Annotated, Any, Literal
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
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
from computos.ia.enrutador_documentos import (
    ROLES_MOTOR,
    enrutar_documentos,
)
from computos.ia.proveedor import (
    ConfiguracionIAError,
    ProveedorIAError,
)
from computos.ia.servicio import analizar_pdf_estructural
from computos.fundaciones.revision_cuadro import RevisionCuadroRequerida
from computos.fundaciones.geometria_distribuida import (
    calcular_geometria_revisada,
    preparar_revision_geometrica,
)
from computos.fundaciones.cimientos_corridos import (
    calcular_cimientos_corridos_revisados,
    preparar_revision_cimientos_corridos,
)
from computos.documentos.ocr import diagnostico_ocr
from computos.documentos.fichas_lector_visual import integrar_fichas_cimientos
from computos.referencias import LecturaCuadroNoCompatible
from computos.incidencias import Incidencia, IncidenciaBloqueante, decision_auditable
from computos.configuracion.parametros import DATA_DIR


LIMITE_ARCHIVO_BYTES = 25 * 1024 * 1024
LIMITE_CARGA_TOTAL_BYTES = 250 * 1024 * 1024
MAXIMO_DOCUMENTOS_POR_ANALISIS = 50
TAMANIO_BLOQUE_BYTES = 1024 * 1024
MAXIMO_RESULTADOS_MEMORIA = 50
VERSION_API = "0.4.4"
VERSION_CONTRATO_API = 6
BUILD_API = "2026-10-19-v12.3.2-revision-planta"

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
        "resolver_inconsistencia_portico",
        "validar_seccion_portico",
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
    version=VERSION_API,
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


def _respuesta_incidencia(error, etapa, diagnostico=None):
    """No inventa cantidades ni permite validar un fallo como cómputo."""
    analisis_id = uuid4().hex
    if isinstance(error, IncidenciaBloqueante):
        incidencia = error.incidencia
    else:
        controlado = isinstance(error, (ValueError, FileNotFoundError))
        if not controlado:
            _logger.exception("Fallo de análisis %s en %s", analisis_id, etapa)
        incidencia = Incidencia(
            tipo="DATOS_NO_INTERPRETABLES" if controlado else "ERROR_EJECUCION",
            categoria="validacion" if controlado else "ejecucion",
            severidad="error",
            titulo="El análisis necesita revisión",
            mensaje=str(error) if controlado else "Ocurrió un error interno. Usá el identificador del análisis para consultar el registro del servidor.",
            evidencias=[{"etiqueta": "Etapa", "valor": etapa}],
            opciones=[{"id": "documentar", "titulo": "Documentar y mantener bloqueado"}],
        )
    cuerpo = jsonable_encoder({
        "analisis_id": analisis_id,
        "estado": "requiere_revision",
        "enrutamiento": diagnostico,
        "resultado": {"analisis_id": analisis_id, "computos_disponibles": False,
                      "incidencias": [incidencia.a_diccionario()]},
    })
    # Los detalles técnicos completos quedan en logs, nunca en la respuesta web.
    for item in cuerpo["resultado"]["incidencias"]:
        item.get("metadatos", {}).pop("traceback", None)
    _guardar_resultado(analisis_id, cuerpo)
    return cuerpo


class NotaIncidenciaEntrada(BaseModel):
    motivo: str = Field(min_length=10, max_length=1000)
    revisor: str = Field(min_length=2, max_length=160)


@app.post("/api/analisis/{analisis_id}/incidencias/{incidencia_id}/documentar")
def documentar_incidencia(analisis_id: str, incidencia_id: str, entrada: NotaIncidenciaEntrada):
    if len(entrada.motivo.strip()) < 10 or len(entrada.revisor.strip()) < 2:
        raise HTTPException(422, "Completá el revisor y un motivo de al menos 10 caracteres.")
    with _bloqueo_resultados:
        actual = _resultados.get(analisis_id)
        if actual is None:
            raise HTTPException(404, "El análisis ya no está disponible. Volvé a cargar los planos.")
        respuesta = deepcopy(actual)
        incidencia = next((i for i in respuesta.get("resultado", {}).get("incidencias", []) if i["id"] == incidencia_id), None)
        if incidencia is None:
            raise HTTPException(404, "Incidencia no encontrada.")
        nota = decision_auditable(accion="documentar", motivo=entrada.motivo, revisor=entrada.revisor)
        nota["identidad_verificada"] = False
        incidencia.setdefault("observaciones", []).append(nota)
        # Documentar NO resuelve, no omite validaciones y no habilita cantidades.
        carpeta = DATA_DIR / "revisiones_incidencias"
        carpeta.mkdir(parents=True, exist_ok=True)
        destino = carpeta / f"{analisis_id}-{uuid4().hex}.json"
        destino.write_text(json.dumps({"analisis_id": analisis_id, "incidencia": incidencia, "enrutamiento": respuesta.get("enrutamiento")}, ensure_ascii=False, indent=2), encoding="utf-8")
        _resultados[analisis_id] = respuesta
    return respuesta


def _leer_asignaciones_documentales(
    valor: str | None,
) -> dict[str, str] | None:
    """Valida una confirmación manual enviada como campo multipart."""

    if valor is None or not valor.strip():
        return None

    try:
        datos = json.loads(valor)
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=422,
            detail="Las asignaciones documentales no contienen JSON válido.",
        ) from error

    if not isinstance(datos, dict):
        raise HTTPException(
            status_code=422,
            detail="Las asignaciones documentales deben ser un objeto JSON.",
        )

    roles_desconocidos = set(datos) - set(ROLES_MOTOR)
    if roles_desconocidos:
        raise HTTPException(
            status_code=422,
            detail=(
                "Se recibieron funciones documentales desconocidas: "
                + ", ".join(sorted(roles_desconocidos))
            ),
        )

    resultado = {}
    for rol, documento_id in datos.items():
        if not isinstance(documento_id, str) or not documento_id.strip():
            raise HTTPException(
                status_code=422,
                detail=f"La asignación de {rol} no es válida.",
            )
        resultado[rol] = documento_id.strip()

    return resultado or None


@app.get("/api/estado", tags=["sistema"])
def consultar_estado() -> dict:
    return {
        "estado": "disponible",
        "servicio": "CómputoEstIA API",
        "version": app.version,
        "version_contrato": VERSION_CONTRATO_API,
        "build": BUILD_API,
        "ocr": diagnostico_ocr(),
        "clasificador": {
            "nombre": "EXP22",
            "version": "22.0",
            "tipo": "fusion_multimodal_explicable",
            "modalidades": [
                "texto",
                "posicion_textual",
                "imagen_renderizada",
                "geometria_vectorial",
                "ocr_adaptativo",
            ],
            "modelo_textual_base": "EXP19",
        },
        "capacidades": {
            "zapatas_aisladas": "calculo_revisado",
            "cimientos_corridos": "propuesta_automatica_y_calculo_revisado",
            "clasificacion_multimodal": "operativa",
            "ocr_adaptativo": "operativo_si_tesseract_disponible",
        },
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
            except RevisionCuadroRequerida as error:
                return jsonable_encoder({"estado": "requiere_revision_cuadro", "revision_cuadro": error.revision, "enrutamiento": {"asignaciones": {}}})
            except Exception as error:
                return _respuesta_incidencia(error, "computo")
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


@app.post(
    "/api/analisis/automatico/",
    tags=["analisis"],
)
async def iniciar_analisis_automatico(
    archivos: Annotated[
        list[UploadFile],
        File(
            description=(
                "Uno o más planos PDF. El sistema determina automáticamente "
                "cuáles contienen planta, cuadro de detalles y columnas."
            )
        ),
    ],
    asignaciones: Annotated[
        str | None,
        Form(
            description=(
                "Objeto JSON opcional con decisiones profesionales: "
                "planta, detalles y columnas apuntando a un documento_id."
            )
        ),
    ] = None,
    revision_cuadro: Annotated[str | None, Form()] = None,
    proyecto_id: Annotated[str | None, Form(max_length=160)] = None,
    ejecutar_computo: Annotated[bool, Form()] = False,
    revision_documental: Annotated[str | None, Form()] = None,
    revision_geometria: Annotated[str | None, Form()] = None,
    correcciones_tecnicas: Annotated[str | None, Form()] = None,
    resoluciones_tecnicas: Annotated[str | None, Form()] = None,
) -> dict:
    """Clasifica una carga libre de PDF y ejecuta el motor si es segura."""

    try:
        decisiones_documentales = json.loads(revision_documental) if revision_documental else []
        decision_geometria = json.loads(revision_geometria) if revision_geometria else None
        if decision_geometria is not None and not isinstance(decision_geometria, dict):
            raise ValueError("La revisión geométrica debe ser un objeto JSON.")
        from computos.ia.revision_documental import validar_revisiones
        validar_revisiones(decisiones_documentales)
        from computos.documentos.correcciones_tecnicas import validar_correcciones, validar_resoluciones
        correcciones_filas = validar_correcciones(json.loads(correcciones_tecnicas) if correcciones_tecnicas else [])
        decisiones_tecnicas = validar_resoluciones(json.loads(resoluciones_tecnicas) if resoluciones_tecnicas else [])
    except (ValueError, TypeError) as error:
        raise HTTPException(422, str(error)) from error

    if not archivos:
        raise HTTPException(
            status_code=422,
            detail="Debe cargarse al menos un documento PDF.",
        )
    if len(archivos) > MAXIMO_DOCUMENTOS_POR_ANALISIS:
        raise HTTPException(
            status_code=413,
            detail=(
                "Se admiten como máximo "
                f"{MAXIMO_DOCUMENTOS_POR_ANALISIS} documentos por análisis."
            ),
        )

    asignaciones_leidas = _leer_asignaciones_documentales(
        asignaciones
    )
    decision_cuadro = None
    if revision_cuadro is not None:
        try:
            decision_cuadro = json.loads(revision_cuadro)
        except json.JSONDecodeError as error:
            raise HTTPException(422, "La revisión del cuadro no contiene JSON válido.") from error
        if not isinstance(decision_cuadro, dict):
            raise HTTPException(422, "La revisión del cuadro debe ser un objeto JSON.")

    try:
        with TemporaryDirectory(
            prefix="computoestia-auto-"
        ) as temporal:
            carpeta = Path(temporal)
            rutas = {}
            nombres = {}
            total_guardado = 0

            for indice, archivo in enumerate(archivos, start=1):
                documento_id = f"doc-{indice:03d}"
                ruta = await _guardar_pdf(
                    archivo,
                    carpeta,
                    documento_id,
                )
                total_guardado += ruta.stat().st_size

                if total_guardado > LIMITE_CARGA_TOTAL_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            "La carga completa supera el límite de 250 MB."
                        ),
                    )

                rutas[documento_id] = ruta
                nombres[documento_id] = Path(
                    archivo.filename or ruta.name
                ).name

            try:
                enrutamiento = await run_in_threadpool(
                    enrutar_documentos,
                    rutas,
                    nombres=nombres,
                    asignaciones=asignaciones_leidas,
                    revisiones=decisiones_documentales,
                )
            except ValueError as error:
                raise HTTPException(422, str(error)) from error
            except Exception as error:
                return _respuesta_incidencia(error, "clasificacion")

            diagnostico = enrutamiento.a_diccionario()
            from computos.documentos.auditoria_tecnica import auditar_documentos
            try:
                diagnostico["auditoria_tecnica"] = await run_in_threadpool(
                    auditar_documentos, enrutamiento.rutas_para_auditoria(), diagnostico, correcciones_filas,
                    decisiones_tecnicas,
                )
            except ValueError as error:
                raise HTTPException(422, str(error)) from error
            except Exception:
                diagnostico["auditoria_tecnica"] = {
                    "estado": "no_evaluado", "incidencias": [],
                    "controles": [],
                    "alcance": "No se completó la revisión técnica. La clasificación sigue disponible; no se puede afirmar que el proyecto esté libre de inconsistencias.",
                }

            if not ejecutar_computo:
                analisis_id = uuid4().hex
                respuesta = jsonable_encoder({
                    "analisis_id": analisis_id,
                    "estado": "clasificacion_documental",
                    "enrutamiento": diagnostico,
                })
                _guardar_resultado(analisis_id, respuesta)
                return respuesta

            if enrutamiento.requiere_revision_geometrica:
                try:
                    fuentes_geometria = enrutamiento.rutas_para_revision_geometrica()
                    grupo_planta = enrutamiento.fuentes_por_rol["planta"]
                    if enrutamiento.tipo_revision_geometrica == "cimientos_corridos":
                        grupo_detalles = enrutamiento.fuentes_por_rol["detalles"]
                        propuesta_geometria = await run_in_threadpool(
                            preparar_revision_cimientos_corridos,
                            fuentes_geometria["planta"],
                            fuentes_geometria["detalles"],
                            fuentes_planta=(grupo_planta.get("fuentes") or [grupo_planta]),
                            identidad_fuentes=enrutamiento.identidad_fuentes(),
                            fuentes_detalles=(grupo_detalles.get("fuentes") or [grupo_detalles]),
                        )
                        try:
                            propuesta_geometria = await run_in_threadpool(
                                integrar_fichas_cimientos,
                                propuesta_geometria,
                                fuentes_geometria["detalles"],
                                grupo_detalles.get("fuentes") or [grupo_detalles],
                            )
                        except Exception:
                            _logger.exception("La lectura de fichas 1.5 no pudo completarse")
                            propuesta_geometria["fichas_lector_15"] = {
                                "fichas": [],
                                "avisos": ["El lector de fichas no pudo completar esta página. Revisá las secciones propuestas por el motor principal."],
                                "ocr_regional_utilizado": False,
                            }
                    else:
                        propuesta_geometria = await run_in_threadpool(
                            preparar_revision_geometrica,
                            fuentes_geometria["planta"],
                            fuentes_planta=(grupo_planta.get("fuentes") or [grupo_planta]),
                            identidad_fuentes=enrutamiento.identidad_fuentes(),
                            ruta_detalles=fuentes_geometria.get("detalles"),
                        )
                    if decision_geometria is None:
                        return jsonable_encoder({
                            "estado": "requiere_revision_geometria",
                            "revision_geometria": propuesta_geometria,
                            "enrutamiento": diagnostico,
                        })
                    if enrutamiento.tipo_revision_geometrica == "cimientos_corridos":
                        resultado = await run_in_threadpool(
                            calcular_cimientos_corridos_revisados,
                            propuesta_geometria,
                            decision_geometria,
                        )
                    else:
                        resultado = await run_in_threadpool(
                            calcular_geometria_revisada,
                            propuesta_geometria,
                            decision_geometria,
                        )
                except ValueError as error:
                    raise HTTPException(422, str(error)) from error
                except Exception as error:
                    return _respuesta_incidencia(
                        error,
                        "revision_geometria_distribuida",
                        diagnostico,
                    )
            elif not enrutamiento.listo:
                analisis_id = uuid4().hex
                respuesta = jsonable_encoder({
                    "analisis_id": analisis_id,
                    "estado": "clasificacion_documental",
                    "enrutamiento": diagnostico,
                })
                _guardar_resultado(analisis_id, respuesta)
                return respuesta

            if enrutamiento.listo:
                try:
                    fuentes_calculo = enrutamiento.rutas_por_rol()
                    paginas_origen_porticos = None
                    if "porticos" in enrutamiento.fuentes_por_rol:
                        paginas_origen_porticos = enrutamiento.fuentes_por_rol[
                            "porticos"
                        ].get("paginas")
                    decisiones_motor = diagnostico.get(
                        "auditoria_tecnica", {}
                    ).get("resoluciones_aplicadas", [])
                    resoluciones_motor = []
                    for decision in decisiones_motor:
                        ubicacion = enrutamiento.fuente_en_motor(
                            decision["sha256"], decision["pagina"]
                        )
                        if ubicacion is None:
                            raise ValueError(
                                "Una resolución técnica corresponde a una página que no forma parte de las fuentes del motor."
                            )
                        resoluciones_motor.append({**decision, **ubicacion})
                    fuente_cuadro = enrutamiento.fuentes_por_rol['detalles']
                    sha_cuadro = next(d['sha256'] for d in diagnostico['documentos'] if d['documento_id']==fuente_cuadro['documento_id'])
                    aplicadas = [d for d in diagnostico.get('auditoria_tecnica',{}).get('revisiones_aplicadas',[]) if d['sha256']==sha_cuadro and d['pagina']==fuente_cuadro['pagina']]
                    if aplicadas and decision_cuadro is None:
                        from computos.fundaciones.revision_cuadro import huellas_archivos
                        decision_cuadro = {'huellas_archivos':huellas_archivos(fuentes_calculo), 'revisor': ', '.join(dict.fromkeys(d['revisor'] for d in aplicadas))[:160],
                            'correcciones_referencias_cuadro':[{k:d[k] for k in ('referencia_original','aparicion','referencia_correcta','motivo')} for d in aplicadas]}
                    resultado = await run_in_threadpool(
                        procesar_archivos_hibrido,
                        **fuentes_calculo,
                        revision_cuadro=decision_cuadro,
                        proyecto_id=proyecto_id,
                        resoluciones_tecnicas=resoluciones_motor,
                        paginas_origen_porticos=paginas_origen_porticos,
                    )
                except RevisionCuadroRequerida as error:
                    error.revision["archivo"] = nombres[enrutamiento.asignaciones["detalles"]]
                    error.revision["pagina_origen"] = enrutamiento.fuentes_por_rol["detalles"]["pagina"]
                    return jsonable_encoder({
                        "estado": "requiere_revision_cuadro",
                        "revision_cuadro": error.revision,
                        "enrutamiento": diagnostico,
                    })
                except LecturaCuadroNoCompatible as error:
                    # Un formato no leído no es una inconsistencia del proyecto.
                    # Si hay zapatas y planta, continuar por geometría en lugar
                    # de encerrar al usuario en el formulario de observaciones.
                    if "zapatas_aisladas" not in enrutamiento.tipologias:
                        return _respuesta_incidencia(error, "extraccion_formato_cuadro", diagnostico)
                    enrutamiento.fuentes_por_rol["detalles"]["modo_geometria"] = "geometria_distribuida"
                    motivo = f"El cuadro no fue interpretable por el lector tabular: {error}. Se abrió la extracción geométrica de las zapatas; esto no implica un error del plano."
                    enrutamiento.motivos_motor.append(motivo)
                    diagnostico = {**enrutamiento.a_diccionario(), "auditoria_tecnica": diagnostico.get("auditoria_tecnica", {}),
                                   "recuperacion_extraccion": {"origen": "tabular", "destino": "geometria", "motivo": str(error)}}
                    fuentes_geometria = enrutamiento.rutas_para_revision_geometrica()
                    grupo_planta = enrutamiento.fuentes_por_rol["planta"]
                    try:
                        propuesta = await run_in_threadpool(
                            preparar_revision_geometrica, fuentes_geometria["planta"],
                            fuentes_planta=grupo_planta.get("fuentes") or [grupo_planta],
                            identidad_fuentes=enrutamiento.identidad_fuentes(),
                            ruta_detalles=fuentes_geometria["detalles"],
                        )
                        if decision_geometria is not None:
                            resultado = await run_in_threadpool(calcular_geometria_revisada, propuesta, decision_geometria)
                        else:
                            return jsonable_encoder({"estado": "requiere_revision_geometria", "revision_geometria": propuesta, "enrutamiento": diagnostico})
                    except Exception as error_geometria:
                        return _respuesta_incidencia(error_geometria, "extraccion_geometrica", diagnostico)
                except Exception as error:
                    return _respuesta_incidencia(error, "computo", diagnostico)
    finally:
        for archivo in archivos:
            await archivo.close()

    resultado = {
        **resultado,
        "enrutamiento_documentos": diagnostico,
    }
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

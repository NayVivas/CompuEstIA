"""Coordinación segura: EXP19 local, motor y generativa opcional."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from computos.ia.clasificador_exp19 import (
    ClasificadorExp19,
    ModelosExp19NoDisponibles,
)
from computos.ia.proveedor import (
    ConfiguracionIAError,
    ProveedorIAError,
)


TIPOS_ARCHIVO = (
    "planta",
    "detalles",
    "columnas",
)


def _bandera_entorno(nombre: str, predeterminado: bool = False) -> bool:
    valor = os.getenv(
        nombre,
        "1" if predeterminado else "0",
    ).strip().casefold()
    return valor in {"1", "true", "si", "sí", "yes", "on"}


def _procesador_deterministico_predeterminado(**archivos) -> dict:
    # Importación diferida para evitar acoplar la carga del paquete IA a FastAPI.
    from computos.api.servicio import procesar_archivos

    return procesar_archivos(**archivos)


def _analizador_ia_predeterminado(ruta_pdf: Path) -> dict:
    from computos.ia.servicio import analizar_pdf_estructural

    return analizar_pdf_estructural(ruta_pdf)


def _clasificar_documentos(
    archivos: dict[str, Path],
    clasificador,
) -> tuple[dict, list[str]]:
    documentos = {}
    advertencias = []

    for tipo, ruta in archivos.items():
        try:
            clasificacion = clasificador.clasificar_pdf(ruta)
        except ModelosExp19NoDisponibles as error:
            clasificacion = {
                "archivo": ruta.name,
                "estado": "modelo_no_disponible",
                "compatible_computo_estructural": None,
                "requiere_revision": True,
                "advertencias": [str(error)],
            }
        except Exception as error:
            clasificacion = {
                "archivo": ruta.name,
                "estado": "error_controlado",
                "compatible_computo_estructural": None,
                "requiere_revision": True,
                "advertencias": [
                    "EXP19 no pudo clasificar el documento.",
                    f"{type(error).__name__}: {error}",
                ],
            }

        documentos[tipo] = clasificacion
        advertencias.extend(
            f"{tipo}: {mensaje}"
            for mensaje in clasificacion.get("advertencias", [])
        )

    return documentos, list(dict.fromkeys(advertencias))


def _ejecutar_ia_opcional(
    archivos: dict[str, Path],
    clasificaciones: dict,
    *,
    habilitada: bool,
    estrategia: str,
    analizador_ia: Callable[[Path], dict],
) -> dict:
    if not habilitada:
        return {
            "estado": "desactivada",
            "motivo": (
                "La IA generativa es opcional y está desactivada. "
                "EXP19 y el motor determinístico funcionaron localmente."
            ),
            "documentos": {},
            "afecto_computos": False,
        }

    if estrategia not in {"solo_revision", "todos"}:
        estrategia = "solo_revision"

    candidatos = [
        tipo
        for tipo in archivos
        if (
            estrategia == "todos"
            or clasificaciones[tipo].get("requiere_revision", True)
        )
    ]

    if not candidatos:
        return {
            "estado": "no_necesaria",
            "motivo": "EXP19 no marcó documentos para revisión asistida.",
            "documentos": {},
            "afecto_computos": False,
        }

    resultados = {}
    exitos = 0

    for tipo in candidatos:
        try:
            resultados[tipo] = {
                "estado": "completada",
                "resultado": analizador_ia(archivos[tipo]),
            }
            exitos += 1
        except ConfiguracionIAError as error:
            resultados[tipo] = {
                "estado": "omitida_sin_configuracion",
                "detalle": str(error),
            }
        except ProveedorIAError as error:
            resultados[tipo] = {
                "estado": "proveedor_no_disponible",
                "detalle": str(error),
            }
        except Exception as error:
            resultados[tipo] = {
                "estado": "error_controlado",
                "detalle": f"{type(error).__name__}: {error}",
            }

    if exitos == len(candidatos):
        estado = "completada"
    elif exitos:
        estado = "completada_parcialmente"
    else:
        estado = "omitida_sin_interrumpir_motor"

    return {
        "estado": estado,
        "estrategia": estrategia,
        "documentos": resultados,
        "afecto_computos": False,
    }


def procesar_archivos_hibrido(
    *,
    planta: Path,
    detalles: Path,
    columnas: Path,
    porticos: Path | None = None,
    paginas_origen_porticos: list[int] | None = None,
    revision_cuadro: dict | None = None,
    proyecto_id: str | None = None,
    resoluciones_tecnicas: list[dict] | None = None,
    usar_ia_generativa: bool | None = None,
    clasificador=None,
    procesador_deterministico: Callable[..., dict] | None = None,
    analizador_ia: Callable[[Path], dict] | None = None,
) -> dict:
    """Ejecuta el motor aunque EXP19 o el proveedor generativo fallen.

    La clasificación y la IA aportan contexto y alertas. Ninguna de ellas
    reemplaza cálculos ni altera silenciosamente cantidades del motor.
    """

    archivos = {
        "planta": Path(planta),
        "detalles": Path(detalles),
        "columnas": Path(columnas),
    }
    if porticos is not None:
        archivos["porticos"] = Path(porticos)
    clasificador = clasificador or ClasificadorExp19()
    procesador_deterministico = (
        procesador_deterministico
        or _procesador_deterministico_predeterminado
    )
    analizador_ia = analizador_ia or _analizador_ia_predeterminado

    clasificaciones, advertencias = _clasificar_documentos(
        archivos,
        clasificador,
    )

    # El único productor de cantidades continúa siendo el motor existente.
    opciones_motor = {}
    if revision_cuadro is not None:
        opciones_motor["revision_cuadro"] = revision_cuadro
    if proyecto_id is not None:
        opciones_motor["proyecto_id"] = proyecto_id
    if resoluciones_tecnicas:
        opciones_motor["resoluciones_tecnicas"] = resoluciones_tecnicas
    if paginas_origen_porticos:
        opciones_motor["paginas_origen_porticos"] = paginas_origen_porticos
    resultado_motor = procesador_deterministico(**archivos, **opciones_motor)

    habilitada = (
        _bandera_entorno("COMPUTOESTIA_IA_GENERATIVA")
        if usar_ia_generativa is None
        else bool(usar_ia_generativa)
    )
    estrategia = os.getenv(
        "COMPUTOESTIA_IA_ESTRATEGIA",
        "solo_revision",
    ).strip().casefold()
    resultado_ia = _ejecutar_ia_opcional(
        archivos,
        clasificaciones,
        habilitada=habilitada,
        estrategia=estrategia,
        analizador_ia=analizador_ia,
    )

    respuesta = dict(resultado_motor)
    respuesta.update(
        {
            "flujo_hibrido": {
                "version": "EXP21",
                "exp19_local": "ejecutado",
                "motor_deterministico": "ejecutado",
                "ia_generativa": resultado_ia["estado"],
                "calculos_producidos_por": "motor_deterministico",
                "funciona_sin_creditos_api": True,
            },
            "clasificacion_documentos_exp19": clasificaciones,
            "validacion_clasificacion_exp19": {
                "documentos_analizados": len(clasificaciones),
                "documentos_para_revision": sum(
                    bool(item.get("requiere_revision", True))
                    for item in clasificaciones.values()
                ),
                "advertencias": advertencias,
            },
            "ia_generativa_opcional": resultado_ia,
        }
    )
    return respuesta

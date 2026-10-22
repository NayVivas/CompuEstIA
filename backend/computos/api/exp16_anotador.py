"""API de anotación profesional para el conjunto independiente EXP16."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

import pymupdf as fitz
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from computos.api.exp02_anotador import (
    CONTENIDOS,
    DECISIONES,
    DISCIPLINAS,
    LEGACY_MAP,
    ROLES,
    _flat_label,
    _key,
    _migrar_anotacion,
    _unique,
)
from computos.configuracion.parametros import BASE_DIR


router = APIRouter(
    prefix="/api/exp16",
    tags=["EXP16 Ground Truth"],
)

DATASET_DIR = BASE_DIR / "data" / "dataset_exp16"
INVENTARIO = DATASET_DIR / "EXP16_paginas_inventario.csv"
ANOTACIONES = DATASET_DIR / "EXP16_anotaciones.json"
LOCK = RLock()

PATRON_CORTE = re.compile(r"(?i)(?<![\w])cortes?(?![\w])|&RUWH")


class AnotacionExp16Entrada(BaseModel):
    proyecto_id: str = Field(min_length=1, max_length=160)
    documento: str = Field(min_length=1, max_length=500)
    pagina: int = Field(ge=1)
    disciplinas: list[str] = Field(default_factory=list)
    roles_documentales: list[str] = Field(default_factory=list)
    contenidos: list[str] = Field(default_factory=list)
    revisor: str = Field(min_length=2, max_length=160)
    decision: str = Field(default="confirmada", max_length=40)
    ambiguo: str = Field(default="no", max_length=5)
    motivo_ambiguedad: str = Field(default="", max_length=1000)
    evidencia_profesional: str = Field(default="", max_length=3000)
    observaciones: str = Field(default="", max_length=3000)
    incluir_en_metricas: bool = True


def _load_inventory() -> pd.DataFrame:
    if not INVENTARIO.is_file():
        raise HTTPException(
            503,
            "EXP16 todavía no fue preparado. Ejecutá "
            "experimentos/preparar_exp16.py con el ZIP de nuevos proyectos.",
        )
    try:
        return pd.read_csv(INVENTARIO).fillna("")
    except Exception as error:
        raise HTTPException(500, f"No se pudo leer el inventario EXP16: {error}") from error


def _load_annotations() -> dict:
    with LOCK:
        if not ANOTACIONES.is_file():
            return {}
        try:
            contenido = json.loads(ANOTACIONES.read_text(encoding="utf-8"))
            return contenido if isinstance(contenido, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}


def _save_annotations(data: dict) -> None:
    with LOCK:
        ANOTACIONES.parent.mkdir(parents=True, exist_ok=True)
        temporal = ANOTACIONES.with_suffix(".tmp")
        temporal.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporal.replace(ANOTACIONES)


def _inventory_row(
    proyecto_id: str,
    documento: str,
    pagina: int,
) -> pd.Series:
    inventario = _load_inventory()
    mascara = (
        (inventario["proyecto_id"].astype(str) == proyecto_id)
        & (inventario["documento"].astype(str) == documento)
        & (inventario["pagina"].astype(int) == pagina)
    )
    coincidencias = inventario[mascara]
    if coincidencias.empty:
        raise HTTPException(404, "La página no pertenece al inventario EXP16.")
    return coincidencias.iloc[0]


def _pdf_path(
    proyecto_id: str,
    documento: str,
    pagina: int,
) -> Path:
    fila = _inventory_row(proyecto_id, documento, pagina)
    relativa = Path(str(fila["ruta_relativa"]))
    raiz = DATASET_DIR.resolve()
    candidata = (DATASET_DIR / relativa).resolve()
    if candidata != raiz and raiz not in candidata.parents:
        raise HTTPException(422, "Ruta de documento inválida en EXP16.")
    if not candidata.is_file() or candidata.suffix.lower() != ".pdf":
        raise HTTPException(404, "PDF no encontrado en el dataset EXP16.")
    return candidata


def _to_native(value):
    if hasattr(value, "item"):
        return value.item()
    return value


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"1", "true", "si", "sí", "yes"}


def _row_dict(row: pd.Series) -> dict:
    return {str(key): _to_native(value) for key, value in row.to_dict().items()}


def _suggestions(row: dict) -> list[dict]:
    suggestions = []
    grupo = str(row.get("grupo_fuente", ""))
    documento = str(row.get("documento", ""))
    pistas = str(row.get("pistas_texto", ""))

    if grupo.casefold().startswith("topogrefia/"):
        suggestions.append(
            {
                "tipo": "disciplina",
                "valor": "implantacion_topografia",
                "mensaje": (
                    "La carpeta de origen es topográfica. "
                    "Confirmá la disciplina mirando la lámina."
                ),
                "confirmada": False,
            }
        )

    coincidencia = PATRON_CORTE.search(f"{documento} {pistas}")
    if coincidencia:
        suggestions.append(
            {
                "tipo": "rol_documental",
                "valor": "corte",
                "mensaje": f"Se encontró el indicio «{coincidencia.group(0)}».",
                "confirmada": False,
            }
        )

    if _as_bool(row.get("requiere_ocr", False)):
        suggestions.append(
            {
                "tipo": "procesamiento",
                "valor": "ocr_asistido",
                "mensaje": "La página tiene texto nativo insuficiente y requiere revisión visual/OCR.",
                "confirmada": False,
            }
        )

    if str(row.get("grupo_revision_duplicado", "")):
        suggestions.append(
            {
                "tipo": "calidad_dataset",
                "valor": "posible_revision_o_duplicado",
                "mensaje": "Comparar esta página con la otra lámina del mismo grupo antes de incluirla en métricas.",
                "confirmada": False,
            }
        )

    return suggestions


@router.get("/taxonomia")
def taxonomia():
    return {
        "disciplinas": DISCIPLINAS,
        "roles": ROLES,
        "contenidos": {
            key: {"grupo": value[0], "label": value[1]}
            for key, value in CONTENIDOS.items()
        },
        "legacy_map": LEGACY_MAP,
    }


@router.get("/resumen")
def resumen():
    inventario = _load_inventory()
    anotaciones = _load_annotations()
    confirmadas = 0
    ambiguas = 0
    excluidas = 0

    for _, row in inventario.iterrows():
        clave = _key(
            str(row["proyecto_id"]),
            str(row["documento"]),
            int(row["pagina"]),
        )
        anotacion = _migrar_anotacion(anotaciones.get(clave, {}))
        if anotacion.get("decision") == "confirmada":
            confirmadas += 1
        if anotacion.get("ambiguo") == "si":
            ambiguas += 1
        if anotacion and not anotacion.get("incluir_en_metricas", True):
            excluidas += 1

    proyectos = list(dict.fromkeys(inventario["proyecto_id"].astype(str)))
    total = len(inventario)
    requiere_ocr = int(inventario["requiere_ocr"].map(_as_bool).sum())
    return {
        "dataset": "EXP16",
        "total_paginas": total,
        "confirmadas": confirmadas,
        "pendientes": total - confirmadas,
        "ambiguas": ambiguas,
        "excluidas_metricas": excluidas,
        "requieren_ocr": requiere_ocr,
        "proyectos": proyectos,
        "pdfs": int(inventario["ruta_relativa"].nunique()),
        "grupos_fuente": int(inventario["grupo_fuente"].nunique()),
    }


@router.get("/paginas")
def paginas(
    proyecto_id: str | None = None,
    limit: int = Query(1000, ge=1, le=5000),
):
    inventario = _load_inventory()
    if proyecto_id:
        inventario = inventario[
            inventario["proyecto_id"].astype(str) == proyecto_id
        ]
    anotaciones = _load_annotations()
    salida = []
    for _, row in inventario.head(limit).iterrows():
        registro = _row_dict(row)
        clave = _key(
            str(registro["proyecto_id"]),
            str(registro["documento"]),
            int(registro["pagina"]),
        )
        registro["anotacion"] = _migrar_anotacion(
            anotaciones.get(clave, {})
        )
        registro["sugerencias"] = _suggestions(registro)
        salida.append(registro)
    return salida


@router.get("/pagina-imagen")
def pagina_imagen(
    proyecto_id: str,
    documento: str,
    pagina: int = Query(..., ge=1),
    escala: float = Query(1.5, ge=0.5, le=3.0),
):
    ruta = _pdf_path(proyecto_id, documento, pagina)
    try:
        with fitz.open(ruta) as pdf:
            if pagina > len(pdf):
                raise HTTPException(404, "La página no existe en el PDF.")
            page = pdf[pagina - 1]
            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(escala, escala),
                alpha=False,
            )
            data = pixmap.tobytes("png")
        return Response(
            content=data,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            500,
            f"No se pudo renderizar la página EXP16: {error}",
        ) from error


@router.post("/anotaciones")
def guardar_anotacion(entrada: AnotacionExp16Entrada):
    disciplinas = _unique(entrada.disciplinas)
    roles = _unique(entrada.roles_documentales)
    contenidos = _unique(entrada.contenidos)

    if not disciplinas:
        raise HTTPException(422, "Seleccioná al menos una disciplina.")
    if not roles:
        raise HTTPException(422, "Seleccioná al menos un rol documental.")
    if not contenidos:
        raise HTTPException(422, "Seleccioná al menos un contenido técnico.")
    invalidas = [value for value in disciplinas if value not in DISCIPLINAS]
    roles_invalidos = [value for value in roles if value not in ROLES]
    contenidos_invalidos = [value for value in contenidos if value not in CONTENIDOS]
    if invalidas:
        raise HTTPException(422, f"Disciplinas no válidas: {invalidas}")
    if roles_invalidos:
        raise HTTPException(422, f"Roles no válidos: {roles_invalidos}")
    if contenidos_invalidos:
        raise HTTPException(422, f"Contenidos no válidos: {contenidos_invalidos}")
    if entrada.decision not in DECISIONES:
        raise HTTPException(422, "Decisión no válida.")
    if entrada.ambiguo not in {"si", "no"}:
        raise HTTPException(422, "El campo ambiguo debe ser si/no.")
    if entrada.ambiguo == "si" and not entrada.motivo_ambiguedad.strip():
        raise HTTPException(422, "Una página ambigua requiere motivo de ambigüedad.")

    _inventory_row(entrada.proyecto_id, entrada.documento, entrada.pagina)
    datos = _load_annotations()
    clave = _key(entrada.proyecto_id, entrada.documento, entrada.pagina)
    anterior = _migrar_anotacion(datos.get(clave, {}))
    fecha = datetime.now(timezone.utc).isoformat()
    payload = entrada.model_dump()
    payload.update(
        {
            "disciplina": disciplinas[0] if len(disciplinas) == 1 else "mixto",
            "rol_documental": roles[0] if len(roles) == 1 else "mixto",
            "subtipo_documental": contenidos[0] if len(contenidos) == 1 else "mixto",
            "label_ground_truth": _flat_label(
                {
                    "disciplinas": disciplinas,
                    "roles_documentales": roles,
                    "contenidos": contenidos,
                }
            ),
            "fecha_ultima_decision": fecha,
            "version_anotacion": int(anterior.get("version_anotacion", 0)) + 1,
        }
    )
    historial = list(anterior.get("historial", []))
    historial.append(
        {
            "fecha": fecha,
            "revisor": entrada.revisor.strip(),
            "decision": entrada.decision,
            "disciplinas": disciplinas,
            "roles_documentales": roles,
            "contenidos": contenidos,
            "incluir_en_metricas": entrada.incluir_en_metricas,
            "evidencia": entrada.evidencia_profesional.strip(),
            "observaciones": entrada.observaciones.strip(),
        }
    )
    payload["historial"] = historial
    datos[clave] = payload
    _save_annotations(datos)
    return {"ok": True, "clave": clave, "anotacion": payload}


@router.get("/exportar")
def exportar():
    inventario = _load_inventory()
    anotaciones = _load_annotations()
    filas = []
    for _, row in inventario.iterrows():
        registro = _row_dict(row)
        clave = _key(
            str(registro["proyecto_id"]),
            str(registro["documento"]),
            int(registro["pagina"]),
        )
        anotacion = _migrar_anotacion(anotaciones.get(clave, {}))
        filas.append({**registro, **anotacion})

    contenido = json.dumps(
        {
            "dataset": "EXP16",
            "unidad": "pagina",
            "filas": filas,
        },
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
    return Response(
        content=contenido,
        media_type="application/json",
        headers={
            "Content-Disposition": (
                "attachment; filename=EXP16_GROUND_TRUTH_EXPORTADO.json"
            )
        },
    )

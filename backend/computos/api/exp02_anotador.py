"""API para construir el Ground Truth profesional de EXP-02.

EXP-02 usa una anotación multietiqueta por página: disciplinas, roles documentales
y contenidos técnicos. Se conserva compatibilidad con anotaciones jerárquicas
anteriores de una sola disciplina/rol/subtipo.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from urllib.parse import unquote

import pymupdf as fitz
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from computos.configuracion.parametros import BASE_DIR

router = APIRouter(prefix="/api/exp02", tags=["EXP-02 Ground Truth"])
DATASET_DIR = BASE_DIR / "data" / "dataset_exp02"
ANOTACIONES = DATASET_DIR / "EXP02_anotaciones.json"
LOCK = RLock()

DISCIPLINAS = {
    "arquitectura": "Arquitectura",
    "estructura": "Estructura",
    "sanitarias": "Instalaciones sanitarias",
    "electricidad": "Instalaciones eléctricas",
    "gas": "Instalaciones de gas",
    "climatizacion": "Climatización",
    "incendio": "Incendio",
    "implantacion_topografia": "Implantación / topografía",
    "otra": "Otra",
    "desconocida": "Desconocida / requiere revisión",
}

ROLES = {
    "planta": "Planta",
    "corte": "Corte",
    "elevacion_fachada": "Elevación / fachada",
    "detalle": "Detalle",
    "cuadro_planilla": "Cuadro / planilla",
    "isometrico": "Isométrico",
    "esquema_diagrama": "Esquema / diagrama",
    "implantacion": "Implantación",
    "situacion": "Situación / emplazamiento",
    "memoria_especificacion": "Memoria / especificación",
    "indice_lista_planos": "Índice / lista de planos",
    "modelo_3d": "Modelo 3D / axonometría",
    "otro": "Otro",
}

CONTENIDOS = {
    "fundaciones": ("Estructura", "Fundaciones"),
    "columnas_pilares": ("Estructura", "Columnas / pilares"),
    "vigas": ("Estructura", "Vigas"),
    "losas_forjados": ("Estructura", "Losas / forjados"),
    "muros_estructurales": ("Estructura", "Muros estructurales"),
    "escaleras_estructurales": ("Estructura", "Escaleras estructurales"),
    "cubiertas_estructurales": ("Estructura", "Cubiertas estructurales"),
    "armaduras_acero": ("Estructura", "Armaduras / acero"),
    "elementos_estructurales_generales": ("Estructura", "Elementos estructurales generales"),
    "distribucion_espacios": ("Arquitectura", "Distribución / espacios"),
    "pisos": ("Arquitectura", "Pisos"),
    "cielorrasos": ("Arquitectura", "Cielorrasos"),
    "cubiertas": ("Arquitectura", "Cubiertas"),
    "puertas_carpinterias": ("Arquitectura", "Puertas / carpinterías"),
    "ventanas_carpinterias": ("Arquitectura", "Ventanas / carpinterías"),
    "fachadas": ("Arquitectura", "Fachadas"),
    "terminaciones": ("Arquitectura", "Terminaciones"),
    "detalles_constructivos": ("Arquitectura", "Detalles constructivos"),
    "agua_fria": ("Sanitarias", "Agua fría"),
    "agua_caliente": ("Sanitarias", "Agua caliente"),
    "cloacal": ("Sanitarias", "Cloacal"),
    "pluvial": ("Sanitarias", "Pluvial"),
    "artefactos_sanitarios": ("Sanitarias", "Artefactos sanitarios"),
    "canerias_sanitarias": ("Sanitarias", "Cañerías sanitarias"),
    "iluminacion": ("Electricidad", "Iluminación"),
    "tomacorrientes": ("Electricidad", "Tomacorrientes"),
    "fuerza": ("Electricidad", "Fuerza"),
    "tableros": ("Electricidad", "Tableros"),
    "canalizaciones": ("Electricidad", "Canalizaciones"),
    "baja_tension": ("Electricidad", "Baja tensión"),
    "gas_general": ("Gas", "Gas general"),
    "artefactos_gas": ("Gas", "Artefactos de gas"),
    "regulacion_gas": ("Gas", "Regulación de gas"),
    "canerias_gas": ("Gas", "Cañerías de gas"),
    "equipos_climatizacion": ("Climatización", "Equipos"),
    "conductos_climatizacion": ("Climatización", "Conductos"),
    "distribucion_climatizacion": ("Climatización", "Distribución"),
    "control_climatizacion": ("Climatización", "Control"),
    "deteccion_incendio": ("Incendio", "Detección"),
    "extincion_incendio": ("Incendio", "Extinción"),
    "senalizacion_incendio": ("Incendio", "Señalización"),
    "red_incendio": ("Incendio", "Red de incendio"),
    "terreno": ("Implantación / topografía", "Terreno"),
    "ejes_replanteo": ("Implantación / topografía", "Ejes / replanteo"),
    "niveles": ("Implantación / topografía", "Niveles"),
    "coordenadas": ("Implantación / topografía", "Coordenadas"),
    "implantacion": ("Implantación / topografía", "Implantación"),
    "otro": ("Otro", "Otro contenido"),
}

DECISIONES = {"pendiente", "confirmada", "ambigua", "requiere_revision", "no_aplicable"}

LEGACY_MAP = {
    "planta_fundaciones": (["estructura"], ["planta"], ["fundaciones"]),
    "columnas": (["estructura"], ["planta"], ["columnas_pilares"]),
    "vigas": (["estructura"], ["planta"], ["vigas"]),
    "losas": (["estructura"], ["planta"], ["losas_forjados"]),
    "cuadro_fundaciones": (["estructura"], ["cuadro_planilla"], ["fundaciones"]),
    "detalle_estructural": (["estructura"], ["detalle"], ["elementos_estructurales_generales"]),
    "otro/desconocido": (["desconocida"], ["otro"], ["otro"]),
}

# Compatibilidad con el zip jerárquico anterior.
OLD_TRIPLES = {
    ("estructura", "planta", "fundaciones"): "planta_fundaciones",
    ("estructura", "planta", "columnas"): "columnas",
    ("estructura", "planta", "vigas"): "vigas",
    ("estructura", "planta", "losas"): "losas",
    ("estructura", "cuadro_planilla", "fundaciones"): "cuadro_fundaciones",
    ("estructura", "detalle", "estructural_general"): "detalle_estructural",
}


class AnotacionEntrada(BaseModel):
    proyecto_id: str = Field(min_length=1, max_length=100)
    documento: str = Field(min_length=1, max_length=500)
    pagina: int = Field(ge=1)
    disciplinas: list[str] = Field(default_factory=list)
    roles_documentales: list[str] = Field(default_factory=list)
    contenidos: list[str] = Field(default_factory=list)
    # Campos individuales se aceptan para no romper clientes antiguos.
    disciplina: str = Field(default="", max_length=80)
    rol_documental: str = Field(default="", max_length=80)
    subtipo_documental: str = Field(default="", max_length=120)
    label_ground_truth: str = Field(default="", max_length=1000)
    revisor: str = Field(min_length=2, max_length=160)
    decision: str = Field(default="confirmada", max_length=40)
    ambiguo: str = Field(default="no", max_length=5)
    motivo_ambiguedad: str = Field(default="", max_length=1000)
    evidencia_profesional: str = Field(default="", max_length=3000)
    observaciones: str = Field(default="", max_length=3000)


def _inventory_path() -> Path:
    p = DATASET_DIR / "EXP01_paginas_inventario.csv"
    if p.exists():
        return p
    raise HTTPException(500, "No se encontró el inventario de EXP-01 en data/dataset_exp02.")


def _load_inventory() -> pd.DataFrame:
    return pd.read_csv(_inventory_path()).fillna("")


def _load_annotations() -> dict:
    with LOCK:
        if not ANOTACIONES.exists():
            return {}
        try:
            return json.loads(ANOTACIONES.read_text(encoding="utf-8"))
        except Exception:
            return {}


def _save_annotations(data: dict) -> None:
    with LOCK:
        ANOTACIONES.parent.mkdir(parents=True, exist_ok=True)
        tmp = ANOTACIONES.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(ANOTACIONES)


def _key(proyecto: str, documento: str, pagina: int) -> str:
    return f"{proyecto}|||{documento}|||{pagina}"


def _pdf_path(proyecto: str, documento: str) -> Path:
    p = DATASET_DIR / Path(proyecto).name / Path(unquote(documento)).name
    if not p.exists() or p.suffix.lower() != ".pdf":
        raise HTTPException(404, "PDF no encontrado en el dataset de EXP-02.")
    return p


def _unique(values):
    return list(dict.fromkeys(v for v in values if v))


def _migrar_anotacion(a: dict) -> dict:
    if not a:
        return {}
    b = dict(a)
    if not b.get("disciplinas"):
        if b.get("disciplina"):
            b["disciplinas"] = [b["disciplina"]]
        else:
            legacy = LEGACY_MAP.get(b.get("label_ground_truth", ""))
            if legacy:
                b["disciplinas"] = legacy[0]
                b["roles_documentales"] = legacy[1]
                b["contenidos"] = legacy[2]
    if not b.get("roles_documentales"):
        if b.get("rol_documental"):
            b["roles_documentales"] = [b["rol_documental"]]
        elif b.get("label_ground_truth") in LEGACY_MAP:
            b["roles_documentales"] = LEGACY_MAP[b["label_ground_truth"]][1]
    if not b.get("contenidos"):
        if b.get("subtipo_documental"):
            st = b["subtipo_documental"]
            # Map old hierarchical subtype names.
            stmap = {"columnas": "columnas_pilares", "losas": "losas_forjados", "estructural_general": "elementos_estructurales_generales", "armaduras": "armaduras_acero"}
            b["contenidos"] = [stmap.get(st, st)]
        elif b.get("label_ground_truth") in LEGACY_MAP:
            b["contenidos"] = LEGACY_MAP[b["label_ground_truth"]][2]
    b["disciplinas"] = _unique(b.get("disciplinas", []))
    b["roles_documentales"] = _unique(b.get("roles_documentales", []))
    b["contenidos"] = _unique(b.get("contenidos", []))
    if b.get("disciplinas") and not b.get("disciplina"):
        b["disciplina"] = b["disciplinas"][0] if len(b["disciplinas"]) == 1 else "mixto"
    if b.get("roles_documentales") and not b.get("rol_documental"):
        b["rol_documental"] = b["roles_documentales"][0] if len(b["roles_documentales"]) == 1 else "mixto"
    return b


def _flat_label(a: dict) -> str:
    ds, rs, cs = a.get("disciplinas", []), a.get("roles_documentales", []), a.get("contenidos", [])
    if len(ds) == len(rs) == len(cs) == 1:
        legacy = OLD_TRIPLES.get((ds[0], rs[0], cs[0]))
        if legacy:
            return legacy
    return json.dumps({"disciplinas": ds, "roles": rs, "contenidos": cs}, ensure_ascii=False, separators=(",", ":"))


@router.get("/taxonomia")
def taxonomia():
    return {"disciplinas": DISCIPLINAS, "roles": ROLES, "contenidos": {k: {"grupo": v[0], "label": v[1]} for k, v in CONTENIDOS.items()}, "legacy_map": LEGACY_MAP}


@router.get("/resumen")
def resumen():
    df = _load_inventory(); anns = _load_annotations(); total = len(df); confirmadas = 0; amb = 0
    for _, r in df.iterrows():
        a = _migrar_anotacion(anns.get(_key(str(r.proyecto_id), str(r.documento), int(r.pagina)), {}))
        if a.get("decision") == "confirmada": confirmadas += 1
        if a.get("ambiguo") == "si": amb += 1
    proyectos = sorted(df["proyecto_id"].astype(str).unique(), key=lambda x: int(x.split("_")[-1]) if x.split("_")[-1].isdigit() else x)
    return {"total_paginas": total, "confirmadas": confirmadas, "pendientes": total - confirmadas, "ambiguas": amb, "proyectos": proyectos, "pdfs": int(df["documento"].nunique())}


@router.get("/paginas")
def paginas(proyecto_id: str | None = None, limit: int = Query(1000, ge=1, le=5000)):
    df = _load_inventory()
    if proyecto_id:
        df = df[df["proyecto_id"].astype(str) == proyecto_id]
    anns = _load_annotations(); out = []
    for _, r in df.head(limit).iterrows():
        k = _key(str(r.proyecto_id), str(r.documento), int(r.pagina))
        a = _migrar_anotacion(anns.get(k, {}))
        out.append({**{c: r[c] for c in df.columns}, "anotacion": a})
    return out


@router.get("/pagina-imagen")
def pagina_imagen(proyecto_id: str, documento: str, pagina: int = Query(..., ge=1), escala: float = Query(1.5, ge=0.5, le=3.0)):
    p = _pdf_path(proyecto_id, documento)
    try:
        d = fitz.open(p)
        if pagina > len(d):
            raise HTTPException(404, "La página no existe en el PDF.")
        page = d[pagina - 1]
        pix = page.get_pixmap(matrix=fitz.Matrix(escala, escala), alpha=False)
        data = pix.tobytes("png"); d.close()
        return Response(content=data, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"No se pudo renderizar la página: {e}")


@router.post("/anotaciones")
def guardar_anotacion(entrada: AnotacionEntrada):
    # Compatibilidad: si llega el esquema anterior, lo convertimos a listas.
    disciplinas = _unique(entrada.disciplinas or ([entrada.disciplina] if entrada.disciplina else []))
    roles = _unique(entrada.roles_documentales or ([entrada.rol_documental] if entrada.rol_documental else []))
    contenidos = _unique(entrada.contenidos or ([entrada.subtipo_documental] if entrada.subtipo_documental else []))
    if not disciplinas:
        raise HTTPException(422, "Seleccioná al menos una disciplina.")
    if not roles:
        raise HTTPException(422, "Seleccioná al menos un rol documental.")
    if not contenidos:
        raise HTTPException(422, "Seleccioná al menos un contenido técnico.")
    bad_d = [x for x in disciplinas if x not in DISCIPLINAS]
    bad_r = [x for x in roles if x not in ROLES]
    bad_c = [x for x in contenidos if x not in CONTENIDOS]
    if bad_d: raise HTTPException(422, f"Disciplinas no válidas: {bad_d}")
    if bad_r: raise HTTPException(422, f"Roles no válidos: {bad_r}")
    if bad_c: raise HTTPException(422, f"Contenidos no válidos: {bad_c}")
    if entrada.decision not in DECISIONES: raise HTTPException(422, "Decisión no válida.")
    if entrada.ambiguo not in {"si", "no"}: raise HTTPException(422, "El campo ambiguo debe ser si/no.")
    df = _load_inventory()
    mask = (df["proyecto_id"].astype(str) == entrada.proyecto_id) & (df["documento"].astype(str) == entrada.documento) & (df["pagina"].astype(int) == entrada.pagina)
    if not mask.any(): raise HTTPException(404, "La página no pertenece al inventario de EXP-02.")
    if entrada.ambiguo == "si" and not entrada.motivo_ambiguedad.strip(): raise HTTPException(422, "Una página ambigua requiere motivo de ambigüedad.")
    data = _load_annotations(); k = _key(entrada.proyecto_id, entrada.documento, entrada.pagina)
    old = _migrar_anotacion(data.get(k, {}))
    now = datetime.now(timezone.utc).isoformat()
    payload = entrada.model_dump()
    payload.update({
        "disciplinas": disciplinas,
        "roles_documentales": roles,
        "contenidos": contenidos,
        "disciplina": disciplinas[0] if len(disciplinas) == 1 else "mixto",
        "rol_documental": roles[0] if len(roles) == 1 else "mixto",
        "subtipo_documental": contenidos[0] if len(contenidos) == 1 else "mixto",
        "label_ground_truth": _flat_label({"disciplinas": disciplinas, "roles_documentales": roles, "contenidos": contenidos}),
        "fecha_ultima_decision": now,
        "version_anotacion": int(old.get("version_anotacion", 0)) + 1,
    })
    history = list(old.get("historial", []))
    history.append({"fecha": now, "revisor": entrada.revisor.strip(), "decision": entrada.decision, "disciplinas": disciplinas, "roles_documentales": roles, "contenidos": contenidos, "evidencia": entrada.evidencia_profesional.strip(), "observaciones": entrada.observaciones.strip()})
    payload["historial"] = history
    data[k] = payload
    _save_annotations(data)
    return {"ok": True, "clave": k, "anotacion": data[k]}


@router.get("/exportar")
def exportar():
    df = _load_inventory(); anns = _load_annotations(); rows = []
    for _, r in df.iterrows():
        raw = anns.get(_key(str(r.proyecto_id), str(r.documento), int(r.pagina)), {})
        a = _migrar_anotacion(raw) if raw else {}
        row = {**{c: r[c] for c in df.columns}, **a}
        for key in ("disciplinas", "roles_documentales", "contenidos", "historial"):
            if key in row:
                row[key] = json.dumps(row[key], ensure_ascii=False)
        rows.append(row)
    out = pd.DataFrame(rows)
    csv = out.to_csv(index=False).encode("utf-8-sig")
    return Response(content=csv, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=EXP02_GROUND_TRUTH_EXPORTADO.csv"})

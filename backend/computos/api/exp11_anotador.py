from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from urllib.parse import unquote
import pymupdf as fitz
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from computos.configuracion.parametros import BASE_DIR

router = APIRouter(prefix="/api/exp11", tags=["EXP-11 evaluación externa"])
DATASET_DIR = BASE_DIR / "data" / "dataset_exp11"
INVENTARIO = DATASET_DIR / "EXP11_INVENTARIO.json"
ANOTACIONES = DATASET_DIR / "EXP11_anotaciones.json"
LOCK = RLock()

DISCIPLINAS = {"arquitectura":"Arquitectura","estructura":"Estructura","sanitarias":"Instalaciones sanitarias","electricidad":"Instalaciones eléctricas","gas":"Instalaciones de gas","climatizacion":"Climatización","incendio":"Incendio","implantacion_topografia":"Implantación / topografía","otra":"Otra","desconocida":"Desconocida / requiere revisión"}
ROLES = {"planta":"Planta","corte":"Corte","elevacion_fachada":"Elevación / fachada","detalle":"Detalle","cuadro_planilla":"Cuadro / planilla","isometrico":"Isométrico","esquema_diagrama":"Esquema / diagrama","implantacion":"Implantación","situacion":"Situación / emplazamiento","memoria_especificacion":"Memoria / especificación","indice_lista_planos":"Índice / lista de planos","modelo_3d":"Modelo 3D / axonometría","otro":"Otro"}
CONTENIDOS = {
 "Estructura":{"fundaciones":"Fundaciones","columnas_pilares":"Columnas / pilares","vigas":"Vigas","losas_forjados":"Losas / forjados","muros_estructurales":"Muros estructurales","escaleras_estructurales":"Escaleras estructurales","cubiertas_estructurales":"Cubiertas estructurales","armaduras_acero":"Armaduras / acero","elementos_estructurales_generales":"Elementos estructurales generales"},
 "Arquitectura":{"distribucion_espacios":"Distribución / espacios","pisos":"Pisos","cielorrasos":"Cielorrasos","cubiertas":"Cubiertas","puertas_carpinterias":"Puertas / carpinterías","ventanas_carpinterias":"Ventanas / carpinterías","fachadas":"Fachadas","terminaciones":"Terminaciones","detalles_constructivos":"Detalles constructivos"},
 "Sanitarias":{"agua_fria":"Agua fría","agua_caliente":"Agua caliente","cloacal":"Cloacal","pluvial":"Pluvial","artefactos_sanitarios":"Artefactos sanitarios","canerias_sanitarias":"Cañerías sanitarias"},
 "Electricidad":{"iluminacion":"Iluminación","tomacorrientes":"Tomacorrientes","fuerza":"Fuerza","tableros":"Tableros","canalizaciones":"Canalizaciones","baja_tension":"Baja tensión"},
 "Gas":{"gas_general":"Gas general","artefactos_gas":"Artefactos de gas","regulacion_gas":"Regulación de gas","canerias_gas":"Cañerías de gas"},
 "Climatización":{"equipos_climatizacion":"Equipos","conductos_climatizacion":"Conductos","distribucion_climatizacion":"Distribución","control_climatizacion":"Control"},
 "Incendio":{"deteccion_incendio":"Detección","extincion_incendio":"Extinción","senalizacion_incendio":"Señalización","red_incendio":"Red de incendio"},
 "Implantación / topografía":{"terreno":"Terreno","ejes_replanteo":"Ejes / replanteo","niveles":"Niveles","coordenadas":"Coordenadas","implantacion":"Implantación"},
 "Otro":{"otro":"Otro contenido"}}
DECISIONES={"pendiente","confirmada","ambigua","requiere_revision","no_aplicable"}

def load_inv():
    if not INVENTARIO.exists(): raise HTTPException(500,"No se encontró EXP11_INVENTARIO.json.")
    return json.loads(INVENTARIO.read_text(encoding="utf-8"))
def rows(): return load_inv().get("paginas",[])
def load_ann():
    with LOCK:
        if not ANOTACIONES.exists(): return {}
        return json.loads(ANOTACIONES.read_text(encoding="utf-8"))
def save_ann(d):
    with LOCK:
        DATASET_DIR.mkdir(parents=True,exist_ok=True); tmp=ANOTACIONES.with_suffix('.tmp'); tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(ANOTACIONES)
def key(p,d,n): return f"{p}|||{d}|||{n}"
def pdf_path(proyecto,documento):
    rel=Path(unquote(documento)); p=DATASET_DIR/rel if rel.parts and rel.parts[0]==Path(proyecto).name else DATASET_DIR/Path(proyecto).name/rel.name
    if not p.exists(): raise HTTPException(404,"PDF no encontrado en EXP-11. Copiá los PDFs respetando Proyecto_01/... hasta Proyecto_11/...")
    return p
class AnotacionEntrada(BaseModel):
    proyecto_id:str=Field(min_length=1,max_length=100); documento:str=Field(min_length=1,max_length=500); pagina:int=Field(ge=1)
    disciplinas:list[str]=Field(default_factory=list); roles_documentales:list[str]=Field(default_factory=list); contenidos:list[str]=Field(default_factory=list)
    revisor:str=Field(min_length=2,max_length=160); decision:str="confirmada"; ambiguo:str="no"; motivo_ambiguedad:str=""; evidencia_profesional:str=""; observaciones:str=""; incluir_en_metricas:bool=True
@router.get('/taxonomia')
def taxonomia(): return {'disciplinas':DISCIPLINAS,'roles':ROLES,'contenidos':CONTENIDOS}
@router.get('/resumen')
def resumen():
    rs=rows(); aa=load_ann(); projects=sorted({r['proyecto_id'] for r in rs},key=lambda x:int(x.split('_')[-1])); done=sum(aa.get(key(r['proyecto_id'],r['archivo'],r['pagina']),{}).get('decision')=='confirmada' for r in rs); amb=sum(aa.get(key(r['proyecto_id'],r['archivo'],r['pagina']),{}).get('ambiguo')=='si' for r in rs); inc=sum(aa.get(key(r['proyecto_id'],r['archivo'],r['pagina']),{}).get('incluir_en_metricas',r.get('incluir_en_metricas',True)) for r in rs)
    return {'total_paginas':len(rs),'confirmadas':done,'pendientes':len(rs)-done,'ambiguas':amb,'incluidas_en_metricas':inc,'excluidas_en_metricas':len(rs)-inc,'proyectos':projects,'pdfs':len({r['archivo'] for r in rs})}
@router.get('/paginas')
def paginas(proyecto_id:str|None=None,limit:int=Query(1000,ge=1,le=5000)):
    rs=rows(); rs=[r for r in rs if not proyecto_id or r['proyecto_id']==proyecto_id]; aa=load_ann(); out=[]
    for r in rs[:limit]: out.append({**r,'documento':r['archivo'],'anotacion':aa.get(key(r['proyecto_id'],r['archivo'],r['pagina']),{})})
    return out
@router.get('/pagina-imagen')
def pagina_imagen(proyecto_id:str,documento:str,pagina:int=Query(...,ge=1),escala:float=Query(1.35,ge=.5,le=3)):
    p=pdf_path(proyecto_id,documento)
    with fitz.open(p) as doc:
        if pagina>len(doc): raise HTTPException(404,'La página no existe en el PDF.')
        pix=doc[pagina-1].get_pixmap(matrix=fitz.Matrix(escala,escala),alpha=False)
        return Response(pix.tobytes('png'),media_type='image/png',headers={'Cache-Control':'public,max-age=3600'})
@router.post('/anotaciones')
def guardar(a:AnotacionEntrada):
    rs=rows(); r=next((x for x in rs if x['proyecto_id']==a.proyecto_id and x['archivo']==a.documento and int(x['pagina'])==a.pagina),None)
    if not r: raise HTTPException(404,'La página no pertenece al inventario de EXP-11.')
    if not a.disciplinas or not a.roles_documentales or not a.contenidos: raise HTTPException(422,'La anotación requiere al menos una disciplina, un rol y un contenido.')
    if any(x not in DISCIPLINAS for x in a.disciplinas): raise HTTPException(422,'Disciplina no válida.')
    if any(x not in ROLES for x in a.roles_documentales): raise HTTPException(422,'Rol no válido.')
    valid={x for g in CONTENIDOS.values() for x in g};
    if any(x not in valid for x in a.contenidos): raise HTTPException(422,'Contenido no válido.')
    if a.decision not in DECISIONES or a.ambiguo not in {'si','no'}: raise HTTPException(422,'Estado de anotación inválido.')
    if a.ambiguo=='si' and not a.motivo_ambiguedad.strip(): raise HTTPException(422,'Una página ambigua requiere motivo.')
    data=load_ann(); k=key(a.proyecto_id,a.documento,a.pagina); old=data.get(k,{}); now=datetime.now(timezone.utc).isoformat(); payload=a.model_dump(); payload.update({'fecha_ultima_decision':now,'version_anotacion':int(old.get('version_anotacion',0))+1})
    hist=list(old.get('historial',[])); hist.append({'fecha':now,'revisor':a.revisor.strip(),'decision':a.decision,'ambiguo':a.ambiguo,'disciplinas':a.disciplinas,'roles_documentales':a.roles_documentales,'contenidos':a.contenidos,'incluir_en_metricas':a.incluir_en_metricas,'evidencia':a.evidencia_profesional.strip(),'observaciones':a.observaciones.strip()}); payload['historial']=hist; data[k]=payload; save_ann(data); return {'ok':True,'clave':k,'anotacion':payload}
@router.get('/exportar')
def exportar():
    rs=rows(); aa=load_ann(); out=[]
    for r in rs:
        a=aa.get(key(r['proyecto_id'],r['archivo'],r['pagina']),{}); out.append({**r,**a,'documento':r['archivo']})
    data=json.dumps({'dataset':'EXP-11','unidad':'pagina','filas':out},ensure_ascii=False,indent=2).encode('utf-8')
    return Response(data,media_type='application/json',headers={'Content-Disposition':'attachment; filename=EXP11_GROUND_TRUTH_EXPORTADO.json'})

"""Decisiones documentales ligadas a la huella exacta del PDF y su página."""
from copy import deepcopy

OBJETIVOS = {'disciplinas', 'roles_documentales', 'contenidos'}


def validar_revisiones(revisiones):
    if not isinstance(revisiones,list) or len(revisiones)>2000:
        raise ValueError('La revisión documental debe ser una lista de hasta 2000 decisiones.')
    claves=set()
    for d in revisiones:
        if not isinstance(d,dict): raise ValueError('Decisión documental inválida.')
        sha=d.get('sha256',''); pagina=d.get('pagina')
        if len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha) or type(pagina) is not int or pagina<1:
            raise ValueError('La decisión debe identificar la huella del PDF y una página válida.')
        if (sha,pagina) in claves: raise ValueError('Hay decisiones duplicadas para una página.')
        claves.add((sha,pagina))
        for campo,minimo,maximo in [('revisor',2,160),('motivo',10,1000)]:
            if not isinstance(d.get(campo),str) or not minimo<=len(d[campo].strip())<=maximo:
                raise ValueError(f'{campo}: longitud inválida.')
        objetivos=d.get('objetivos')
        if not isinstance(objetivos,dict) or set(objetivos)!=OBJETIVOS: raise ValueError('Deben revisarse las tres categorías documentales.')
        for etiquetas in objetivos.values():
            if not isinstance(etiquetas,list) or not 1<=len(etiquetas)<=50 or any(not isinstance(e,str) or not e.strip() or len(e)>100 for e in etiquetas):
                raise ValueError('Cada categoría requiere entre 1 y 50 etiquetas válidas.')
    return revisiones


def aplicar_decision(ficha,decision):
    ficha['clasificacion_automatica']=deepcopy(ficha.get('clasificacion',{}))
    ficha['clasificacion']={**ficha.get('clasificacion',{}),'metodo':'revision_profesional','objetivos':{k:{'etiquetas':v} for k,v in decision['objetivos'].items()},'propuestas_modelo_sin_evidencia':{},'requiere_revision':False,'motivos_revision':[],'tiene_sugerencias':False}
    ficha['decision_documental']=deepcopy(decision)
    ficha['estado']='revisado_profesional'
    ficha['requiere_revision']=False
    # Confirmar una clasificación no repara un fallo de extracción ni crea dimensiones.
    if ficha.get('caracteres',0)<10:
        ficha['requiere_revision']=True
        ficha['advertencias'].append('Clasificación revisada; sigue faltando texto utilizable para extraer cantidades.')
    objetivos=decision['objetivos']
    contenidos=set(objetivos['contenidos']); roles=set(objetivos['roles_documentales'])
    compatibles=[]
    if 'estructura' in objetivos['disciplinas']:
        if 'fundaciones' in contenidos and 'planta' in roles: compatibles.append('planta')
        if 'fundaciones' in contenidos and 'cuadro_planilla' in roles: compatibles.append('detalles')
        if 'columnas_pilares' in contenidos and roles.intersection({'detalle','cuadro_planilla'}): compatibles.append('columnas')
        if 'columnas_pilares' in contenidos and ('porticos' in contenidos or roles.intersection({'elevacion_fachada','corte'})): compatibles.append('porticos')
    # La revisión profesional sí puede corregir el rol de una página. La
    # identidad exacta (huella + página) impide que esa decisión se herede a
    # otro archivo. Aun así, no inventa dimensiones ni una tipología.
    ficha['roles_motor']=list(dict.fromkeys(compatibles))
    tecnico=ficha.setdefault('analisis_fuente',{})
    tecnico['roles']=list(ficha['roles_motor'])
    if 'detalles' in compatibles and not tecnico.get('modo_detalles'):
        tecnico['modo_detalles']='tabular' if 'cuadro_planilla' in roles else 'geometria_distribuida'

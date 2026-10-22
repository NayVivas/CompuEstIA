"""Diagnóstico ejecutable con el mismo Python usado para iniciar Uvicorn."""
import json
import platform
import sys
from importlib.metadata import version, PackageNotFoundError
from computos.ia.clasificador_exp19 import ClasificadorExp19, ruta_modelos_predeterminada


def diagnosticar():
    info = {'python':sys.executable,'version_python':platform.python_version(),'ruta_modelos':str(ruta_modelos_predeterminada()),'dependencias':{}}
    for paquete in ('numpy','scikit-learn','joblib','pymupdf'):
        try: info['dependencias'][paquete] = version(paquete)
        except PackageNotFoundError: info['dependencias'][paquete] = 'no instalado'
    try:
        modelo=ClasificadorExp19()
        r=modelo.clasificar_texto('ESTRUCTURA. DETALLE DE COLUMNAS. ESTRIBOS Y ARMADURAS.')
        info.update(estado='disponible',runtime=r.get('runtime'),prediccion={k:v['etiquetas'] for k,v in r['objetivos'].items()})
    except Exception as error:
        causa=error.__cause__ or error
        info.update(estado='error',tipo=type(causa).__name__,mensaje=str(causa))
    return info

if __name__=='__main__':
    resultado=diagnosticar()
    print(json.dumps(resultado,ensure_ascii=False,indent=2))
    sys.exit(0 if resultado['estado']=='disponible' else 1)

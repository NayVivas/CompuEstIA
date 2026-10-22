"""Revisión previa al cómputo: referencias ambiguas con evidencia y auditoría."""

from base64 import b64encode
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

import pymupdf

from computos.configuracion.parametros import BASE_DIR
from computos.configuracion.proyecto import interpretar_configuracion_proyecto
from computos.documentos.analisis import extraer_palabras_normalizadas
from computos.fundaciones.cuadros import (
    extraer_dimensiones_cuadro,
    localizar_estructura_cuadro,
)
from computos.fundaciones.deteccion import aplicar_correcciones, referencias_duplicadas
from computos.referencias import (
    descubrir_catalogo_referencias,
    extraer_candidatos_referencias,
)


DIRECTORIO_REVISIONES = BASE_DIR / "data" / "revisiones_cuadro"


class RevisionCuadroRequerida(ValueError):
    """El cuadro necesita una decisión; todavía no hay cantidades calculadas."""

    def __init__(self, revision):
        super().__init__(revision["mensaje"])
        self.revision = revision


def huellas_archivos(archivos):
    resultado = {}
    for rol, ruta in archivos.items():
        calculo = sha256()
        with Path(ruta).open("rb") as archivo:
            for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
                calculo.update(bloque)
        resultado[rol] = calculo.hexdigest()
    return resultado


def _ruta_registro(huellas, proyecto_id):
    identidad = json.dumps([str(proyecto_id or "sin-proyecto"), huellas], sort_keys=True)
    return DIRECTORIO_REVISIONES / (sha256(identidad.encode()).hexdigest() + ".json")


def _aplicar(filas, configuracion):
    return aplicar_correcciones(
        filas,
        configuracion.correcciones_referencias_cuadro,
        configuracion.motivos_referencias_cuadro,
    )


def _crear_revision(archivos, huellas, palabras, catalogo, filas, configuracion):
    corregidas = _aplicar(filas, configuracion)
    duplicadas = referencias_duplicadas(corregidas)
    dimensiones = {}
    advertencias = []
    try:
        cuadro = localizar_estructura_cuadro(palabras, catalogo)
        dimensiones = {f["numero_fila"]: f for f in extraer_dimensiones_cuadro(cuadro)}
    except ValueError as error:
        advertencias.append(str(error))

    prefijos = {c.referencia.prefijo for c in catalogo.referencias}
    candidatos = extraer_candidatos_referencias(extraer_palabras_normalizadas(archivos["planta"]))
    referencias_planta = {
        c.referencia.canonica for c in candidatos if c.referencia.prefijo in prefijos
    }
    faltantes = sorted(referencias_planta - {f["referencia"] for f in corregidas})
    filas_revision = []
    paginas = {}
    with pymupdf.open(archivos["detalles"]) as pdf:
        for fila, candidato in zip(corregidas, catalogo.referencias):
            if fila["referencia"] not in duplicadas:
                continue
            pagina = pdf[candidato.pagina - 1]
            if candidato.pagina not in paginas:
                escala = min(1400 / pagina.rect.width, 1800 / pagina.rect.height, 2)
                pix = pagina.get_pixmap(matrix=pymupdf.Matrix(escala, escala), alpha=False)
                paginas[candidato.pagina] = {
                    "pagina": candidato.pagina,
                    "ancho": pagina.rect.width,
                    "alto": pagina.rect.height,
                    "imagen": "data:image/png;base64," + b64encode(pix.tobytes("png")).decode(),
                }
            dimension = dimensiones.get(fila["numero_fila"], {})
            filas_revision.append({
                **fila,
                "pagina": candidato.pagina,
                "caja_visual": asdict(candidato.caja_visual),
                "dimensiones_m": {k: dimension.get(k) for k in ("x", "y", "h")},
            })
    return {
        "categoria": "referencias_duplicadas_cuadro",
        "familia": "fundaciones",
        "mensaje": "El cuadro tiene referencias repetidas. Revisá las filas y documentá la corrección antes de calcular.",
        "archivo": Path(archivos["detalles"]).name,
        "huellas_archivos": huellas,
        "duplicadas": duplicadas,
        "filas": filas_revision,
        "paginas": list(paginas.values()),
        "referencias_planta_sin_cuadro": faltantes,
        "advertencias": advertencias,
        "computos_disponibles": False,
    }


def preparar_revision_cuadro(archivos, configuracion, decision=None, proyecto_id=None):
    """Valida antes de calcular. No guarda una decisión que todavía no se aplicó."""
    huellas = huellas_archivos(archivos)
    ruta = _ruta_registro(huellas, proyecto_id)
    registro = None
    if ruta.is_file():
        registro = json.loads(ruta.read_text(encoding="utf-8"))
        if registro.get("huellas_archivos") != huellas:
            raise ValueError("La revisión guardada no corresponde a los PDF cargados.")
        configuracion = interpretar_configuracion_proyecto(registro["configuracion"])
    else:
        configuracion = deepcopy(configuracion)

    palabras = extraer_palabras_normalizadas(archivos["detalles"])
    catalogo = descubrir_catalogo_referencias(palabras)
    filas = [{"numero_fila": i, "referencia": ref} for i, ref in enumerate(catalogo.canonicas, 1)]
    corregidas = _aplicar(filas, configuracion)
    duplicadas = referencias_duplicadas(corregidas)

    if decision is not None:
        if not isinstance(decision, dict):
            raise ValueError("La revisión del cuadro debe ser un objeto.")
        if decision.get("huellas_archivos") != huellas:
            raise ValueError("Los PDF cambiaron desde la revisión. Volvé a analizarlos antes de corregir.")
        revisor = decision.get("revisor")
        if not isinstance(revisor, str) or not 2 <= len(revisor.strip()) <= 160:
            raise ValueError("Indicá el nombre del profesional que revisa (2 a 160 caracteres).")
        nuevas = decision.get("correcciones_referencias_cuadro")
        if not isinstance(nuevas, list) or not nuevas:
            raise ValueError("Ingresá al menos una corrección de referencia.")
        propuesta = interpretar_configuracion_proyecto({"correcciones_referencias_cuadro": nuevas})
        if all(configuracion.correcciones_referencias_cuadro.get(k)==v for k,v in propuesta.correcciones_referencias_cuadro.items()):
            return configuracion, registro, ruta
        permitidas = {
            (f["referencia_original"], f["aparicion_original"])
            for f in corregidas if f["referencia"] in duplicadas
        }
        for clave, nueva in propuesta.correcciones_referencias_cuadro.items():
            if clave not in permitidas:
                raise ValueError("La corrección no corresponde a una aparición duplicada pendiente.")
            motivo = propuesta.motivos_referencias_cuadro[clave]
            if not 10 <= len(motivo) <= 1000:
                raise ValueError("El motivo debe tener entre 10 y 1000 caracteres.")
            if nueva == clave[0]:
                raise ValueError("La referencia corregida debe ser diferente de la original.")
        configuracion.correcciones_referencias_cuadro.update(propuesta.correcciones_referencias_cuadro)
        configuracion.motivos_referencias_cuadro.update(propuesta.motivos_referencias_cuadro)
        if referencias_duplicadas(_aplicar(filas, configuracion)):
            raise ValueError("La propuesta todavía deja referencias duplicadas. Revisá todas las apariciones.")

        auditoria = {
            "revision_id": uuid4().hex,
            "familia": "fundaciones",
            "tipo_revision": "referencias_duplicadas_cuadro",
            "revisor": revisor.strip(),
            "identidad_verificada": False,
            "fecha_revision": datetime.now(timezone.utc).isoformat(),
            "estado": "aplicada_por_ingeniero",
            "correcciones": propuesta.a_diccionario()["correcciones_referencias_cuadro"],
            "huellas_archivos": huellas,
        }
        registro = {
            "huellas_archivos": huellas,
            "proyecto_id": str(proyecto_id or "sin-proyecto"),
            "configuracion": configuracion.a_diccionario(),
            "revisiones": [*(registro or {}).get("revisiones", []), auditoria],
        }
    elif duplicadas:
        raise RevisionCuadroRequerida(_crear_revision(
            archivos, huellas, palabras, catalogo, filas, configuracion,
        ))

    return configuracion, registro, ruta


def guardar_revision_cuadro(ruta, registro):
    """Guarda atómicamente solo después de completar el motor."""
    if registro is None:
        return
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=ruta.parent, delete=False) as archivo:
        json.dump(registro, archivo, ensure_ascii=False, indent=2)
        temporal = Path(archivo.name)
    try:
        os.replace(temporal, ruta)
    finally:
        temporal.unlink(missing_ok=True)

"""Inventario y anotaciones visuales de elementos estructurales por proyecto.

Las anotaciones son ground truth para investigación. Nunca se convierten en
cantidades ni se presentan como predicciones del motor de cómputo.
"""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
import math
from pathlib import Path
import re

import pymupdf


VERSION = 1
SPLITS = {"train", "validation", "test", "sin_asignar"}
GEOMETRIAS = {
    "fundacion_aislada": {"poligono"},
    "cimiento_corrido": {"poligono", "polilinea"},
    "pedestal": {"poligono"},
    "viga_riostra": {"poligono", "polilinea"},
    "columna": {"poligono"},
}


def _escribir_json(ruta: Path, valor: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    temporal.write_text(json.dumps(valor, ensure_ascii=False, indent=2), encoding="utf-8")
    temporal.replace(ruta)


def _leer_json(ruta: Path, predeterminado: dict) -> dict:
    if not ruta.is_file():
        return predeterminado
    contenido = json.loads(ruta.read_text(encoding="utf-8"))
    if not isinstance(contenido, dict):
        raise ValueError(f"JSON inválido: {ruta.name}.")
    return contenido


def _archivos_pdf(origen: Path) -> list[Path]:
    if origen.is_file() and origen.suffix.casefold() == ".pdf":
        return [origen]
    if not origen.is_dir():
        raise ValueError(f"El proyecto debe ser un PDF o una carpeta: {origen}")
    return sorted(
        (p for p in origen.rglob("*") if p.is_file() and p.suffix.casefold() == ".pdf"),
        key=lambda p: str(p).casefold(),
    )


def _huella_archivo(ruta: Path) -> str:
    resumen = sha256()
    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
            resumen.update(bloque)
    return resumen.hexdigest()


def preparar_dataset(
    proyectos: dict[str, Path],
    salida: Path,
    *,
    splits: dict[str, str] | None = None,
    lado_maximo: int = 1600,
) -> dict:
    if not proyectos:
        raise ValueError("Indicá al menos un proyecto con sus PDF.")
    if not 500 <= lado_maximo <= 3000:
        raise ValueError("El lado máximo debe estar entre 500 y 3000 píxeles.")
    splits = splits or {}
    if set(splits) - set(proyectos) or set(splits.values()) - SPLITS:
        raise ValueError("Las particiones deben corresponder a proyectos y usar train, validation o test.")
    salida = Path(salida).resolve()
    salida.mkdir(parents=True, exist_ok=True)
    paginas = []
    registros = []
    huellas_globales: dict[str, str] = {}

    for proyecto_id, origen in proyectos.items():
        if not re.fullmatch(r"[\w-]{1,80}", proyecto_id):
            raise ValueError(f"Identificador de proyecto inválido: {proyecto_id!r}")
        origen = Path(origen).resolve()
        pdfs = _archivos_pdf(origen)
        if not pdfs:
            raise ValueError(f"No hay PDF en {origen}.")
        split = splits.get(proyecto_id, "sin_asignar")
        slug = re.sub(r"[^A-Za-z0-9_-]", "_", proyecto_id)[:60]
        carpeta = f"{slug}-{sha256(proyecto_id.encode()).hexdigest()[:8]}"
        huellas_proyecto = set()
        agregados = 0
        for ruta in pdfs:
            huella = _huella_archivo(ruta)
            if huella in huellas_proyecto:
                continue
            huellas_proyecto.add(huella)
            anterior = huellas_globales.get(huella)
            if anterior and anterior != proyecto_id:
                raise ValueError(f"El mismo PDF aparece en dos proyectos: {anterior} y {proyecto_id}.")
            huellas_globales[huella] = proyecto_id
            relativo = ruta.name if origen.is_file() else str(ruta.relative_to(origen))
            with pymupdf.open(ruta) as documento:
                if documento.needs_pass or not len(documento):
                    raise ValueError(f"PDF protegido o vacío: {ruta.name}.")
                for numero, pagina in enumerate(documento, start=1):
                    identificador = sha256(
                        f"{proyecto_id}\0{huella}\0{numero}".encode()
                    ).hexdigest()[:24]
                    imagen_relativa = (
                        Path("imagenes") / carpeta / f"{huella[:16]}-p{numero:04d}.jpg"
                    )
                    destino = salida / imagen_relativa
                    if not destino.is_file():
                        destino.parent.mkdir(parents=True, exist_ok=True)
                        escala = lado_maximo / max(pagina.rect.width, pagina.rect.height)
                        pixmap = pagina.get_pixmap(
                            matrix=pymupdf.Matrix(escala, escala),
                            colorspace=pymupdf.csRGB,
                            alpha=False,
                        )
                        destino.write_bytes(pixmap.tobytes("jpeg", jpg_quality=82))
                    paginas.append({
                        "id": identificador,
                        "proyecto_id": proyecto_id,
                        "split": split,
                        "documento": relativo,
                        "sha256_pdf": huella,
                        "pagina": numero,
                        "rotacion_grados": pagina.rotation,
                        "ancho_pt": round(pagina.rect.width, 3),
                        "alto_pt": round(pagina.rect.height, 3),
                        "imagen": imagen_relativa.as_posix(),
                        "texto_nativo": bool(pagina.get_text().strip()),
                    })
                    agregados += 1
        registros.append({"id": proyecto_id, "split": split, "pdfs": len(huellas_proyecto), "paginas": agregados})

    manifiesto = {
        "version": VERSION,
        "objetivo": "anotacion_visual_estructural",
        "geometrias": {k: sorted(v) for k, v in GEOMETRIAS.items()},
        "proyectos": registros,
        "paginas": paginas,
    }
    validar_manifiesto(manifiesto)
    anterior = _leer_json(salida / "anotaciones.json", {"version": VERSION, "paginas": {}})
    anteriores = anterior.get("paginas", {})
    por_id = {pagina["id"]: pagina for pagina in paginas}
    if not isinstance(anteriores, dict) or set(anteriores) - set(por_id):
        raise ValueError("Hay anotaciones de páginas ausentes. Usá otra carpeta de salida o conservá los PDF originales.")
    for clave, anotacion in anteriores.items():
        validar_anotacion_pagina(por_id[clave], anotacion)
    _escribir_json(salida / "manifest.json", manifiesto)
    if not (salida / "anotaciones.json").exists():
        _escribir_json(salida / "anotaciones.json", {"version": VERSION, "paginas": {}})
    return manifiesto


def validar_manifiesto(manifiesto: dict) -> None:
    if manifiesto.get("version") != VERSION or not isinstance(manifiesto.get("paginas"), list):
        raise ValueError("Versión o páginas de manifiesto inválidas.")
    ids = set()
    particiones = {}
    huellas = {}
    for pagina in manifiesto["paginas"]:
        clave = pagina.get("id")
        proyecto = pagina.get("proyecto_id")
        split = pagina.get("split")
        huella = pagina.get("sha256_pdf")
        if not clave or clave in ids or split not in SPLITS or not proyecto:
            raise ValueError("Página duplicada o con proyecto/partición inválidos.")
        ids.add(clave)
        if proyecto in particiones and particiones[proyecto] != split:
            raise ValueError(f"El proyecto {proyecto} aparece en más de una partición.")
        particiones[proyecto] = split
        if huella in huellas and huellas[huella] != proyecto:
            raise ValueError("Un mismo PDF aparece en dos proyectos distintos.")
        huellas[huella] = proyecto
        imagen = Path(str(pagina.get("imagen", "")))
        if imagen.is_absolute() or ".." in imagen.parts or imagen.suffix != ".jpg":
            raise ValueError("Ruta de imagen inválida en el manifiesto.")


def validar_anotacion_pagina(pagina: dict, anotacion: dict) -> dict:
    if not isinstance(anotacion, dict) or anotacion.get("sha256_pdf") != pagina["sha256_pdf"]:
        raise ValueError("La anotación pertenece a otra versión del PDF.")
    estado = anotacion.get("estado")
    if estado not in {"pendiente", "revisada"}:
        raise ValueError("Estado de anotación inválido.")
    revisor = str(anotacion.get("revisor") or "").strip()
    if estado == "revisada" and not 2 <= len(revisor) <= 160:
        raise ValueError("Identificá al revisor para confirmar la página.")
    elementos = anotacion.get("elementos")
    if not isinstance(elementos, list) or len(elementos) > 500:
        raise ValueError("Lista de elementos inválida o demasiado grande.")
    vistos = set()
    normalizados = []
    for item in elementos:
        if not isinstance(item, dict):
            raise ValueError("Cada elemento debe ser un objeto.")
        identificador = str(item.get("id") or "")
        familia = item.get("familia")
        geometria = item.get("geometria")
        if not 1 <= len(identificador) <= 100 or identificador in vistos:
            raise ValueError("Identificador de elemento vacío o duplicado.")
        vistos.add(identificador)
        if geometria not in GEOMETRIAS.get(familia, set()):
            raise ValueError(f"Familia o geometría inválida: {familia}/{geometria}.")
        puntos = item.get("puntos")
        minimo = 3 if geometria == "poligono" else 2
        if not isinstance(puntos, list) or not minimo <= len(puntos) <= 500:
            raise ValueError("Cantidad de puntos inválida.")
        coordenadas = []
        for punto in puntos:
            if not isinstance(punto, list) or len(punto) != 2:
                raise ValueError("Cada punto requiere coordenadas x, y.")
            if any(isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor) or not 0 <= valor <= 1 for valor in punto):
                raise ValueError("Los puntos deben estar normalizados entre 0 y 1.")
            coordenadas.append([round(float(punto[0]), 6), round(float(punto[1]), 6)])
        recorrido = sum(math.dist(a, b) for a, b in zip(coordenadas, coordenadas[1:]))
        if recorrido < 0.002:
            raise ValueError("El elemento necesita una extensión visible.")
        if geometria == "poligono":
            area_doble = abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(coordenadas, coordenadas[1:] + coordenadas[:1])))
            if area_doble < 0.000004:
                raise ValueError("El polígono no delimita una superficie.")
        referencia = str(item.get("referencia") or "").strip()
        nota = str(item.get("nota") or "").strip()
        if len(referencia) > 80 or len(nota) > 500:
            raise ValueError("Referencia o nota demasiado larga.")
        normalizados.append({
            "id": identificador, "familia": familia, "geometria": geometria,
            "puntos": coordenadas, "referencia": referencia, "nota": nota,
        })
    return {
        "sha256_pdf": pagina["sha256_pdf"], "estado": estado,
        "revisor": revisor, "elementos": normalizados,
    }


def guardar_anotacion(salida: Path, pagina_id: str, anotacion: dict) -> dict:
    """Guarda una página revisada, preservando las demás anotaciones."""
    salida = Path(salida)
    validar_dataset(salida)
    manifiesto = _leer_json(salida / "manifest.json", {})
    pagina = next((item for item in manifiesto["paginas"] if item["id"] == pagina_id), None)
    if pagina is None:
        raise ValueError("La página no pertenece a este dataset.")
    normalizada = validar_anotacion_pagina(pagina, anotacion)
    ruta = salida / "anotaciones.json"
    registros = _leer_json(ruta, {"version": VERSION, "paginas": {}})
    registros["paginas"][pagina_id] = normalizada
    _escribir_json(ruta, registros)
    return normalizada


def validar_dataset(salida: Path) -> dict:
    salida = Path(salida)
    manifiesto = _leer_json(salida / "manifest.json", {})
    validar_manifiesto(manifiesto)
    anotaciones = _leer_json(salida / "anotaciones.json", {"version": VERSION, "paginas": {}})
    registros = anotaciones.get("paginas")
    if anotaciones.get("version") != VERSION or not isinstance(registros, dict):
        raise ValueError("Archivo de anotaciones incompatible.")
    por_id = {pagina["id"]: pagina for pagina in manifiesto["paginas"]}
    if set(registros) - set(por_id):
        raise ValueError("Hay anotaciones huérfanas de páginas de otro manifiesto.")
    por_familia = Counter()
    por_split = Counter()
    revisadas_por_split = Counter()
    familias_por_split = {split: Counter() for split in SPLITS}
    revisadas = 0
    for pagina in manifiesto["paginas"]:
        por_split[pagina["split"]] += 1
        if pagina["id"] not in registros:
            continue
        anotacion = validar_anotacion_pagina(pagina, registros[pagina["id"]])
        if anotacion["estado"] == "revisada":
            revisadas += 1
            revisadas_por_split[pagina["split"]] += 1
            por_familia.update(e["familia"] for e in anotacion["elementos"])
            familias_por_split[pagina["split"]].update(e["familia"] for e in anotacion["elementos"])
    return {
        "proyectos": len(manifiesto["proyectos"]),
        "paginas": len(manifiesto["paginas"]),
        "revisadas": revisadas,
        "pendientes": len(manifiesto["paginas"]) - revisadas,
        "paginas_por_split": dict(por_split),
        "paginas_revisadas_por_split": dict(revisadas_por_split),
        "elementos_confirmados_por_familia": dict(por_familia),
        "elementos_por_split": {s: dict(c) for s, c in familias_por_split.items() if c},
        "cobertura_minima": revisadas > 0 and all(
            revisadas_por_split[s] > 0 for s in ("train", "validation", "test")
        ) and all(familias_por_split["train"][f] > 0 for f in GEOMETRIAS),
        "nota": "La cobertura mínima no acredita que haya datos suficientes para entrenar ni generalización del modelo.",
    }

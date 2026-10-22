"""Métricas de localización estructural sobre proyectos separados y revisados."""

from __future__ import annotations

from collections import Counter, defaultdict
import json
import math
from pathlib import Path

from computos.ia.dataset_visual import GEOMETRIAS, validar_anotacion_pagina, validar_dataset


def _dentro(punto: tuple[float, float], poligono: list[list[float]]) -> bool:
    x, y = punto
    dentro = False
    previo = poligono[-1]
    for actual in poligono:
        x1, y1 = previo
        x2, y2 = actual
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            dentro = not dentro
        previo = actual
    return dentro


def _iou_poligonos(primero: list[list[float]], segundo: list[list[float]]) -> float:
    min_x = min(x for poligono in (primero, segundo) for x, _ in poligono)
    max_x = max(x for poligono in (primero, segundo) for x, _ in poligono)
    min_y = min(y for poligono in (primero, segundo) for _, y in poligono)
    max_y = max(y for poligono in (primero, segundo) for _, y in poligono)
    # La cuadrícula se adapta al rectángulo de ambas figuras, también si son pequeñas.
    interseccion = union = 0
    for fila in range(96):
        y = min_y + (fila + .5) * (max_y - min_y) / 96
        for columna in range(96):
            x = min_x + (columna + .5) * (max_x - min_x) / 96
            a = _dentro((x, y), primero)
            b = _dentro((x, y), segundo)
            interseccion += a and b
            union += a or b
    return interseccion / union if union else 0.0


def _escala(puntos: list[list[float]], ancho: float, alto: float) -> list[tuple[float, float]]:
    lado = max(ancho, alto)
    return [(x * ancho / lado, y * alto / lado) for x, y in puntos]


def _muestras(puntos: list[tuple[float, float]]) -> list[tuple[float, float]]:
    segmentos = [(a, b, math.dist(a, b)) for a, b in zip(puntos, puntos[1:])]
    total = sum(longitud for _, _, longitud in segmentos)
    cantidad = max(5, min(200, math.ceil(total / .005)))
    if not total:
        return puntos[:1]
    resultado = []
    for indice in range(cantidad + 1):
        distancia = indice * total / cantidad
        recorrido = 0.0
        for numero, (a, b, longitud) in enumerate(segmentos):
            if distancia <= recorrido + longitud or numero == len(segmentos) - 1:
                factor = min(1.0, max(0.0, (distancia - recorrido) / longitud)) if longitud else 0
                resultado.append((a[0] + factor * (b[0] - a[0]), a[1] + factor * (b[1] - a[1])))
                break
            recorrido += longitud
    return resultado


def _distancia_segmento(p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    denominador = dx * dx + dy * dy
    factor = min(1., max(0., ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / denominador)) if denominador else 0
    return math.dist(p, (a[0] + factor * dx, a[1] + factor * dy))


def _cobertura_linea(origen: list[tuple[float, float]], destino: list[tuple[float, float]]) -> float:
    segmentos = list(zip(destino, destino[1:]))
    muestras = _muestras(origen)
    return sum(min(_distancia_segmento(punto, a, b) for a, b in segmentos) <= .01 for punto in muestras) / len(muestras)


def _similitud(a: dict, b: dict, pagina: dict) -> float:
    if a["familia"] != b["familia"] or a["geometria"] != b["geometria"]:
        return 0.0
    if a["geometria"] == "poligono":
        return _iou_poligonos(a["puntos"], b["puntos"])
    ancho, alto = pagina["ancho_pt"], pagina["alto_pt"]
    linea_a, linea_b = _escala(a["puntos"], ancho, alto), _escala(b["puntos"], ancho, alto)
    return min(_cobertura_linea(linea_a, linea_b), _cobertura_linea(linea_b, linea_a))


def _tasas(cuentas: Counter) -> dict:
    tp, fp, fn = (cuentas[clave] for clave in ("tp", "fp", "fn"))
    precision = tp / (tp + fp) if tp + fp else None
    cobertura = tp / (tp + fn) if tp + fn else None
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None
    return {"aciertos": tp, "falsos_positivos": fp, "omisiones": fn,
            "precision": round(precision, 4) if precision is not None else None,
            "recall": round(cobertura, 4) if cobertura is not None else None,
            "f1": round(f1, 4) if f1 is not None else None}


def evaluar_predicciones(salida: Path, predicciones: Path, *, split: str = "test") -> dict:
    if split not in {"validation", "test"}:
        raise ValueError("La evaluación publicada debe hacerse en validation o test.")
    salida = Path(salida)
    validar_dataset(salida)
    manifiesto = json.loads((salida / "manifest.json").read_text(encoding="utf-8"))
    anotaciones = json.loads((salida / "anotaciones.json").read_text(encoding="utf-8"))["paginas"]
    paginas = {p["id"]: p for p in manifiesto["paginas"] if p["split"] == split}
    if not paginas:
        raise ValueError(f"No hay páginas en la partición {split}.")
    sin_revisar = [p["id"] for p in paginas.values() if anotaciones.get(p["id"], {}).get("estado") != "revisada"]
    if sin_revisar:
        raise ValueError(f"Hay {len(sin_revisar)} páginas sin revisar en {split}; no se pueden contar falsos positivos.")
    contenido = json.loads(Path(predicciones).read_text(encoding="utf-8"))
    datos = contenido.get("predicciones")
    if contenido.get("version") != 1 or not isinstance(datos, dict):
        raise ValueError("Predicciones inválidas: se espera version=1 y predicciones por ID de página.")
    if set(datos) - set(paginas):
        raise ValueError("Hay predicciones fuera de la partición elegida o de otro dataset.")
    total = Counter()
    por_familia = defaultdict(Counter)
    por_proyecto = defaultdict(Counter)
    for pagina_id, pagina in paginas.items():
        por_proyecto[pagina["proyecto_id"]]
        reales = anotaciones[pagina_id]["elementos"]
        enviados = datos.get(pagina_id, [])
        if not isinstance(enviados, list):
            raise ValueError("Las predicciones de cada página deben ser una lista.")
        if any(not isinstance(item, dict) for item in enviados):
            raise ValueError("Cada predicción debe ser un objeto.")
        # Valida familias, geometrías y coordenadas con las mismas reglas del conjunto revisado.
        propuestos = validar_anotacion_pagina(pagina, {
            "sha256_pdf": pagina["sha256_pdf"], "estado": "pendiente", "revisor": "",
            "elementos": [{**item, "id": f"pred-{indice}"} for indice, item in enumerate(enviados)]
        })["elementos"]
        candidatos = defaultdict(list)
        for i, real in enumerate(reales):
            for j, propuesto in enumerate(propuestos):
                if real["familia"] == propuesto["familia"] and real["geometria"] == propuesto["geometria"]:
                    puntuacion = _similitud(real, propuesto, pagina)
                    umbral = .5 if real["geometria"] == "poligono" else .75
                    if puntuacion >= umbral:
                        candidatos[i].append((puntuacion, j))
        # Máxima cantidad de parejas válidas; la similitud ordena las opciones.
        # Un emparejamiento voraz por puntuación puede contar omisiones evitables.
        duenio_pred = {}

        def emparejar(i: int, visitados: set[int]) -> bool:
            for _, j in sorted(candidatos[i], reverse=True):
                if j in visitados:
                    continue
                visitados.add(j)
                if j not in duenio_pred or emparejar(duenio_pred[j], visitados):
                    duenio_pred[j] = i
                    return True
            return False

        for i in sorted(range(len(reales)), key=lambda indice: len(candidatos[indice])):
            emparejar(i, set())
        tomados_real, tomados_pred = set(duenio_pred.values()), set(duenio_pred)
        for i in tomados_real:
            for conteo in (total, por_familia[reales[i]["familia"]], por_proyecto[pagina["proyecto_id"]]):
                conteo["tp"] += 1
        for i, real in enumerate(reales):
            if i not in tomados_real:
                for conteo in (total, por_familia[real["familia"]], por_proyecto[pagina["proyecto_id"]]):
                    conteo["fn"] += 1
        for j, propuesto in enumerate(propuestos):
            if j not in tomados_pred:
                for conteo in (total, por_familia[propuesto["familia"]], por_proyecto[pagina["proyecto_id"]]):
                    conteo["fp"] += 1
    return {
        "split": split, "proyectos": sorted({p["proyecto_id"] for p in paginas.values()}),
        "paginas_revisadas": len(paginas), "umbral_iou_poligono": .5,
        "umbral_cobertura_polilinea": .75, "tolerancia_eje_pagina": .01,
        "global": _tasas(total),
        "por_familia": {familia: _tasas(por_familia[familia]) for familia in GEOMETRIAS},
        "por_proyecto": {proyecto: _tasas(cuentas) for proyecto, cuentas in sorted(por_proyecto.items())},
        "alcance": "Detección visual de elementos; no valida referencias, dimensiones ni cómputos métricos.",
    }

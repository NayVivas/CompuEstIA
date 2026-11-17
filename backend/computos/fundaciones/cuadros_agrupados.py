"""Propuestas por tipo para cuadros que imprimen A × B (y a veces H) en una celda.

Cada terna se toma de la fila del catálogo y de la columna correspondiente.
Las propuestas nunca autorizan cantidades sin revisión profesional.
"""

from __future__ import annotations

from collections import defaultdict
import re

from computos.documentos.modelos import PalabraNormalizada
from computos.referencias import CatalogoReferencias, normalizar_etiqueta


NUMERO = r"\d+(?:[.,]\d+)?"
VALOR = rf"({NUMERO})(mm|cm|m)?"
TERNA = re.compile(rf"^\s*{VALOR}\s*[x×]\s*{VALOR}(?:\s*[x×]\s*{VALOR})?\s*$", re.I)
SIMPLE = re.compile(rf"^\s*{VALOR}\s*$", re.I)
ENCABEZADO_PAR = re.compile(
    r"\s*(?:A\s*[x×]\s*B|X\s*[x×]\s*Y)\s*(?:\(\s*(?:mm|cm|m)\s*\))?\s*", re.I,
)


def es_encabezado_agrupado(texto: str) -> bool:
    limpio = normalizar_etiqueta(texto)
    return bool(ENCABEZADO_PAR.fullmatch(texto)) or limpio in {
        "AXB", "XXY", "AXBMM", "AXBCM", "AXBM", "XXYMM", "XXYCM", "XXYM",
    }


def _x(palabra: PalabraNormalizada) -> float:
    return (palabra.caja_visual.x0 + palabra.caja_visual.x1) / 2


def _y(palabra: PalabraNormalizada) -> float:
    return (palabra.caja_visual.y0 + palabra.caja_visual.y1) / 2


def _metros(numero: str, unidad: str | None, unidad_cuadro: str | None) -> float | None:
    valor = float(numero.replace(",", "."))
    unidad = (unidad or unidad_cuadro or "m").lower()
    valor /= {"m": 1, "cm": 100, "mm": 1000}[unidad]
    return round(valor, 4) if 0 < valor <= 30 else None


def _celda(palabras: list[PalabraNormalizada], fila_y: float, izquierda: float, derecha: float) -> str:
    return " ".join(
        item.texto for item in sorted(palabras, key=_x)
        if izquierda < _x(item) < derecha
        and abs(_y(item) - fila_y) <= max(8, item.caja_visual.alto * 1.2)
    ).strip()


def extraer_tipos_agrupados(
    palabras: list[PalabraNormalizada], catalogo: CatalogoReferencias,
) -> list[dict]:
    """Extrae propuestas trazables; ante ambigüedad devuelve campos vacíos."""

    if not catalogo.contexto_local_confirmado or not catalogo.referencias or not catalogo.palabra_encabezado:
        return []
    palabras = [
        p for p in palabras if p.pagina == catalogo.pagina
        and catalogo.limite_x_izquierdo < _x(p) < catalogo.limite_x_derecho
    ]
    encabezado = catalogo.palabra_encabezado
    # La banda de títulos puede contener el nombre del cuadro en la línea
    # anterior; usar solo la línea del encabezado evita mezclar sus palabras.
    altura = max(encabezado.caja_visual.alto * 0.65, 6)
    primera_fila = min(
        (item.caja_visual.y0 + item.caja_visual.y1) / 2
        for item in catalogo.referencias
    )
    banda = sorted(
        (p for p in palabras if abs(_y(p) - _y(encabezado)) <= altura
         and _y(p) < (_y(encabezado) + primera_fila) / 2), key=_x
    )
    grupos = []
    for i, palabra in enumerate(banda):
        for cantidad in (4, 3, 2, 1):
            parte = banda[i:i + cantidad]
            if len(parte) != cantidad or max(_y(p) for p in parte) - min(_y(p) for p in parte) > altura:
                continue
            texto_cabecera = " ".join(p.texto for p in parte)
            if es_encabezado_agrupado(texto_cabecera):
                grupos.append(((_x(parte[0]) + _x(parte[-1])) / 2,
                               set(range(i, i + cantidad)), texto_cabecera))
                break
    if len(grupos) != 1:
        return []
    centro, indices_grupo, texto_cabecera = grupos[0]
    otras_cabeceras = [
        p for i, p in enumerate(banda) if i not in indices_grupo
        and not (abs(_x(p) - centro) < 55 and
                 re.fullmatch(r"\(?\s*(mm|cm|m)\s*\)?", p.texto, re.I))
    ]
    candidatos_anteriores = [_x(p) for p in otras_cabeceras if _x(p) < centro]
    candidatos_siguientes = [_x(p) for p in otras_cabeceras if _x(p) > centro]
    anterior = max(candidatos_anteriores, default=_x(encabezado))
    siguiente = min(candidatos_siguientes, default=centro + 200)
    izquierda, derecha = (anterior + centro) / 2, (centro + siguiente) / 2

    # Si el encabezado del grupo declara centímetros o milímetros, convertir.
    # Sin unidad explícita se presenta la convención en metros para confirmar.
    unidad_en_cabecera = re.search(r"\(\s*(mm|cm|m)\s*\)", texto_cabecera, re.I)
    unidad_grupo = unidad_en_cabecera.group(1).lower() if unidad_en_cabecera else None
    if unidad_grupo is None:
        for p in banda:
            if abs(_x(p) - centro) < 55:
                unidad = re.fullmatch(r"\(?\s*(mm|cm|m)\s*\)?", p.texto, re.I)
                if unidad:
                    unidad_grupo = unidad.group(1).lower()

    prima = next((p for p in banda if re.fullmatch(r"H\s*['′´]", p.texto, re.I)), None)
    if prima:
        xp = _x(prima)
        x_prev = max((_x(p) for p in banda if _x(p) < xp - 12), default=xp - 100)
        x_next = min((_x(p) for p in banda if _x(p) > xp + 12), default=xp + 100)
        limites_prima = ((x_prev + xp) / 2, (xp + x_next) / 2)
    else:
        limites_prima = None
    h_directa = next((p for p in otras_cabeceras
                      if re.fullmatch(r"\s*(?:H|E|ESPESOR)\s*(?:\(\s*(?:mm|cm|m)\s*\))?\s*", p.texto, re.I)), None)
    if h_directa:
        xp = _x(h_directa)
        x_prev = max((_x(p) for p in banda if _x(p) < xp - 12), default=xp - 100)
        x_next = min((_x(p) for p in banda if _x(p) > xp + 12), default=xp + 100)
        limites_h = ((x_prev + xp) / 2, (xp + x_next) / 2)
    else:
        limites_h = None
    unidad_altura = None
    if h_directa:
        declarada = re.search(r"\(\s*(mm|cm|m)\s*\)", h_directa.texto, re.I)
        unidad_altura = declarada.group(1).lower() if declarada else None

    por_referencia = defaultdict(list)
    for referencia in catalogo.referencias:
        y = (referencia.caja_visual.y0 + referencia.caja_visual.y1) / 2
        texto = _celda(palabras, y, izquierda, derecha)
        coincidencia = TERNA.fullmatch(texto)
        valores = [None, None, None]
        observaciones = []
        if coincidencia:
            partes = coincidencia.groups()
            for i in range(3):
                numero, unidad = partes[2 * i:2 * i + 2]
                if numero is not None:
                    valores[i] = _metros(numero, unidad, unidad_grupo)
            if any(v is None for v in valores[:2]):
                observaciones.append("Dimensiones fuera de rango o unidades no interpretadas.")
        else:
            observaciones.append("No se pudo separar con certeza la celda A × B de esta fila.")

        if limites_h:
            altura_independiente = SIMPLE.fullmatch(_celda(palabras, y, *limites_h))
            if altura_independiente:
                # La columna H puede usar otra unidad que la de A × B.
                h_valor = _metros(altura_independiente.group(1), altura_independiente.group(2), unidad_altura)
                if unidad_grupo and not unidad_altura and not altura_independiente.group(2):
                    h_valor = None
                    observaciones.append("La columna H no declara una unidad verificable.")
                if valores[2] is None:
                    valores[2] = h_valor
                elif h_valor is not None and abs(valores[2] - h_valor) > 0.005:
                    observaciones.append("La altura agrupada difiere del espesor indicado en otra columna.")
                    valores[2] = None

        if limites_prima and valores[2] is not None:
            texto_prima = _celda(palabras, y, *limites_prima)
            diferencia = SIMPLE.fullmatch(texto_prima)
            if diferencia:
                valor_prima = _metros(diferencia.group(1), diferencia.group(2), unidad_grupo)
                if valor_prima is not None and abs(valor_prima - valores[2]) > 0.005:
                    observaciones.append(
                        f"La altura de la terna ({valores[2]} m) difiere de H′ ({valor_prima} m); verificá la sección."
                    )
                    valores[2] = None
        if valores[2] is None and not observaciones:
            observaciones.append("La altura no se pudo leer con certeza; completala desde el plano.")

        por_referencia[referencia.referencia.canonica].append({
            "referencia": referencia.referencia.canonica,
            "x_m": valores[0], "y_m": valores[1], "h_m": valores[2],
            "texto_celda": texto,
            "pagina_motor": catalogo.pagina,
            "unidad_inferida": unidad_grupo is None and (
                coincidencia is None or any(
                    coincidencia.group(i) is not None and coincidencia.group(i + 1) is None
                    for i in (1, 3, 5)
                )
            ),
            "observaciones": observaciones,
        })

    tipos = []
    for ref, filas in por_referencia.items():
        tipo = filas[0]
        if len(filas) > 1 and any(
            (fila["x_m"], fila["y_m"], fila["h_m"]) !=
            (tipo["x_m"], tipo["y_m"], tipo["h_m"]) for fila in filas[1:]
        ):
            tipo = {**tipo, "x_m": None, "y_m": None, "h_m": None,
                    "observaciones": [*tipo["observaciones"], "Esta referencia figura con cotas distintas en el cuadro."]}
        tipos.append(tipo)
    return tipos

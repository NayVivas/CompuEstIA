"""Contexto local de cuadros: una etiqueta de página no tipa todas sus tablas.

Las regiones se deducen de títulos y encabezados próximos, no del prefijo de
una referencia ni del nombre del archivo. Una región dudosa se deja pendiente.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from computos.documentos.modelos import Caja, PalabraNormalizada


@dataclass(frozen=True, slots=True)
class TituloCuadro:
    pagina: int
    familia: str
    texto: str
    caja: Caja


def _normal(texto: str) -> str:
    texto = "".join(c for c in unicodedata.normalize("NFKD", texto.upper())
                    if not unicodedata.combining(c))
    for palabra in ("CIMENTACIONES", "FUNDACIONES", "SOBRECIMIENTOS", "COLUMNAS",
                    "CASTILLOS", "TRASLAPES", "ZAPATAS", "PLANILLA", "CUADRO",
                    "TABLA", "VIGAS", "LOSAS", "CIMIENTOS", "DE"):
        texto = re.sub(r"(?<!\w)" + r"\s*".join(palabra) + r"(?!\w)", palabra, texto)
    return texto


def titulos_cuadros(palabras: list[PalabraNormalizada]) -> list[TituloCuadro]:
    """Reconstruye títulos visuales, aunque CAD divida palabras y bloques."""
    filas: list[list[PalabraNormalizada]] = []
    for palabra in sorted(palabras, key=lambda p: (p.pagina, p.caja_visual.y0, p.caja_visual.x0)):
        fila = next((f for f in reversed(filas[-12:])
                     if f[0].pagina == palabra.pagina
                     and abs(f[0].caja_visual.y0 - palabra.caja_visual.y0)
                     <= max(2.0, min(f[0].caja_visual.alto, palabra.caja_visual.alto) * .6)), None)
        if fila is None:
            filas.append([palabra])
        else:
            fila.append(palabra)

    patron = re.compile(
        r"^(?:(?:CUADRO|PLANILLA|TABLA)\s+(?:DE\s+)?|(?=CIMENTACIONES?\b|FUNDACIONES?\b|ZAPATAS?\b))"
        r"(?P<familia>FUNDACIONES?|CIMENTACIONES?|ZAPATAS?|CIMIENTOS?|BASES?|"
        r"COLUMNAS?|PILARES?|CASTILLOS?|VIGAS?|LOSAS?|ESCALERAS?|"
        r"SOBRECIMIENTOS?|MUROS?|ARMADURAS?|TRASLAPES?|ANCLAJES?)\b"
    )
    fundaciones = re.compile(r"^(?:FUNDACION|CIMENTACION|ZAPATA|CIMIENTO|BASE)")
    resultado = []
    for fila in filas:
        ordenadas = sorted(fila, key=lambda p: p.caja_visual.x0)
        grupos: list[list[PalabraNormalizada]] = []
        for p in ordenadas:
            if not grupos or p.caja_visual.x0 - grupos[-1][-1].caja_visual.x1 > max(18.0, p.caja_visual.alto * 4):
                grupos.append([p])
            else:
                grupos[-1].append(p)
        for grupo in grupos:
            texto = " ".join(p.texto for p in grupo)
            match = patron.search(_normal(texto))
            if not match:
                continue
            resultado.append(TituloCuadro(
                grupo[0].pagina,
                "fundaciones" if fundaciones.match(match.group("familia")) else "otra",
                texto,
                Caja(min(p.caja_visual.x0 for p in grupo), min(p.caja_visual.y0 for p in grupo),
                     max(p.caja_visual.x1 for p in grupo), max(p.caja_visual.y1 for p in grupo)),
            ))
    return resultado


def contexto_del_encabezado(
    encabezado: PalabraNormalizada,
    titulos: list[TituloCuadro],
    datos: list[PalabraNormalizada],
) -> TituloCuadro | None:
    """Título situado sobre esta tabla; no se usa cualquier título de la hoja."""
    caja = encabezado.caja_visual
    alto = max(caja.alto, 1.0)
    izquierda = min([caja.x0, *(p.caja_visual.x0 for p in datos)])
    derecha = max([caja.x1, *(p.caja_visual.x1 for p in datos)])
    candidatos = []
    for titulo in titulos:
        if titulo.pagina != encabezado.pagina:
            continue
        dy = caja.y0 - titulo.caja.y1
        if not -alto <= dy <= max(100.0, alto * 20):
            continue
        # Una tabla vecina no hereda el título de fundaciones de la izquierda.
        distancia_x = max(0.0, titulo.caja.x0 - derecha, izquierda - titulo.caja.x1)
        if distancia_x > max(30.0, alto * 5):
            continue
        distancia_inicio = abs(titulo.caja.x0 - caja.x0)
        candidatos.append((max(dy, 0) + distancia_x * 4 + distancia_inicio * .15, titulo))
    return min(candidatos, key=lambda item: item[0])[1] if candidatos else None

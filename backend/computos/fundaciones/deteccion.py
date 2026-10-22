from collections import Counter
from decimal import Decimal, InvalidOperation

from computos.fundaciones.cuadros import (
    extraer_dimensiones_cuadro,
    localizar_estructura_cuadro,
)
from computos.referencias import interpretar_referencia


def _normalizar_referencia_obligatoria(texto: str) -> str:
    referencia = interpretar_referencia(texto)
    if referencia is None:
        raise ValueError(f"Referencia estructural inválida: {texto}")
    return referencia.canonica


def detectar_fundaciones(
    palabras: list[dict],
    referencias_validas: list[str] | set[str] | tuple[str, ...],
) -> list[dict]:
    """Compatibilidad para palabras antiguas basada en un catálogo explícito.

    La función ya no decide que toda expresión ``F + número`` es una
    fundación. Solo acepta referencias previamente descubiertas en el cuadro.
    El flujo principal utiliza la versión que además reconstruye referencias
    divididas entre varias palabras.
    """

    catalogo = {
        _normalizar_referencia_obligatoria(texto)
        for texto in referencias_validas
    }
    if not catalogo:
        raise ValueError("El catálogo de referencias de fundaciones está vacío.")

    detecciones = []
    for palabra in palabras:
        referencia = interpretar_referencia(palabra["texto"])
        if referencia is None or referencia.canonica not in catalogo:
            continue

        detecciones.append(
            {
                "referencia": referencia.canonica,
                "texto_original": referencia.texto_original,
                "pagina": palabra["pagina"],
                "x0": palabra["x0"],
                "y0": palabra["y0"],
                "x1": palabra["x1"],
                "y1": palabra["y1"],
                "centro_x": round((palabra["x0"] + palabra["x1"]) / 2, 2),
                "centro_y": round((palabra["y0"] + palabra["y1"]) / 2, 2),
            }
        )
    return detecciones


def contar_referencias(detecciones: list[dict]) -> Counter:
    return Counter(item["referencia"] for item in detecciones)


def validar_referencias(
    referencias_planta: set[str], filas_cuadro: list[dict]
) -> dict:
    referencias_planta = {
        _normalizar_referencia_obligatoria(referencia)
        for referencia in referencias_planta
    }
    lista = [
        _normalizar_referencia_obligatoria(fila["referencia"])
        for fila in filas_cuadro
    ]
    conteo = Counter(lista)
    unicas = set(lista)
    return {
        "faltantes": referencias_planta - unicas,
        "sobrantes": unicas - referencias_planta,
        "duplicadas": {
            referencia: cantidad
            for referencia, cantidad in conteo.items()
            if cantidad > 1
        },
    }


def referencias_duplicadas(filas: list[dict]) -> dict[str, int]:
    """Informa referencias repetidas sin intentar decidir cuál es correcta."""

    conteo = Counter(
        _normalizar_referencia_obligatoria(fila["referencia"])
        for fila in filas
    )
    return {
        referencia: cantidad
        for referencia, cantidad in conteo.items()
        if cantidad > 1
    }


def aplicar_correcciones(
    filas: list[dict],
    correcciones: dict[tuple[str, int], str] | None = None,
    motivos: dict[tuple[str, int], str] | None = None,
) -> list[dict]:
    correcciones = correcciones or {}
    motivos = motivos or {}
    apariciones = Counter()
    resultado = []
    for fila in filas:
        original_texto = fila["referencia"].strip()
        original = _normalizar_referencia_obligatoria(original_texto)
        apariciones[original] += 1
        clave = (original, apariciones[original])
        corregida_texto = correcciones.get(
            clave,
            original,
        )
        corregida = _normalizar_referencia_obligatoria(corregida_texto)

        nueva = fila.copy()
        nueva.update(
            {
                "referencia_original": original,
                "referencia_original_texto": original_texto,
                "aparicion_original": apariciones[original],
                "referencia": corregida,
                "fue_corregida": corregida != original,
                "motivo_correccion": (
                    motivos.get(clave)
                    or (
                        f"Aparición {apariciones[original]} de {original} "
                        f"corregida manualmente a {corregida}."
                    )
                    if corregida != original
                    else None
                ),
            }
        )
        resultado.append(nueva)
    return resultado


def convertir_dimension(valor: str | None) -> Decimal:
    if valor is None:
        raise ValueError("La dimensión no puede estar vacía.")
    try:
        return Decimal(valor.strip().replace(",", "."))
    except InvalidOperation as error:
        raise ValueError(f"Dimensión inválida: {valor}") from error


def calcular_volumenes(
    filas: list[dict], conteo_planta: Counter
) -> tuple[list[dict], Decimal]:
    computos = []
    for fila in filas:
        referencia = fila["referencia"]
        x = convertir_dimension(fila["x"])
        y = convertir_dimension(fila["y"])
        h = convertir_dimension(fila["h"])
        cantidad = conteo_planta.get(referencia, 0)
        volumen_unitario = x * y * h
        computos.append(
            {
                "referencia": referencia,
                "cantidad": cantidad,
                "x": x,
                "y": y,
                "h": h,
                "volumen_unitario": volumen_unitario,
                "volumen_total": volumen_unitario * cantidad,
            }
        )

    total = sum(
        (computo["volumen_total"] for computo in computos), Decimal("0")
    )
    return computos, total

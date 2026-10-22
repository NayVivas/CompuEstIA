"""Interpretación y cómputo de las armaduras de las fundaciones."""

from collections import defaultdict
from decimal import Decimal, ROUND_CEILING
import re

from computos.fundaciones.cuadros import (
    CAMPO_ARMADURA,
    CAMPO_ARMADURA_INFERIOR,
    CAMPO_ARMADURA_SUPERIOR,
    CuadroFundaciones,
)
from computos.referencias import normalizar_etiqueta


PATRON_ARMADURA = re.compile(
    r"(?:As\s*([XY])\s*=\s*)?(\d+)\s*[ØO]\s*"
    r"(\d+\s*/\s*\d+)\s*[\"”]?\s*c\s*/?\s*d\s*"
    r"(\d+(?:[.,]\d+)?)\s*cm",
    re.IGNORECASE,
)


def extraer_textos_armadura(
    cuadro: CuadroFundaciones,
    filas: list[dict],
) -> list[dict]:
    """Obtiene la armadura desde las celdas ya delimitadas del cuadro."""

    if len(cuadro.filas) != len(filas):
        raise ValueError(
            "La cantidad de filas de armadura no coincide con las dimensiones."
        )

    resultados = []
    for fila_cuadro, fila_corregida in zip(cuadro.filas, filas):
        celda_general = fila_cuadro.celdas.get(CAMPO_ARMADURA)
        celda_superior = fila_cuadro.celdas.get(CAMPO_ARMADURA_SUPERIOR)
        celda_inferior = fila_cuadro.celdas.get(CAMPO_ARMADURA_INFERIOR)
        palabras = celda_general.palabras if celda_general else []
        texto = celda_general.texto if celda_general else ""

        resultados.append(
            {
                "referencia_original": fila_cuadro.referencia_texto,
                "referencia": fila_corregida["referencia"],
                "texto": texto,
                "palabras": palabras,
                "superior_directo": (
                    celda_superior.texto
                    if celda_superior is not None
                    else None
                ),
                "inferior_directo": (
                    celda_inferior.texto
                    if celda_inferior is not None
                    else None
                ),
            }
        )

    return resultados


def _centro_y_palabra(palabra) -> float:
    caja = palabra.caja_visual
    return (caja.y0 + caja.y1) / 2


def _ordenar_palabras_armadura(palabras) -> list:
    return sorted(
        palabras,
        key=lambda palabra: (
            round(_centro_y_palabra(palabra), 1),
            palabra.caja_visual.x0,
        ),
    )


def separar_niveles_armadura(registros):
    """Separa el texto de cada fundación en malla superior e inferior."""
    resultado = []
    for registro in registros:
        if (
            registro.get("superior_directo") is not None
            or registro.get("inferior_directo") is not None
        ):
            superior = registro.get("superior_directo") or ""
            inferior = registro.get("inferior_directo") or ""
        else:
            palabras = registro["palabras"]
            etiquetas_superiores = [
                palabra
                for palabra in palabras
                if normalizar_etiqueta(palabra.texto)
                in {"SUPERIOR", "SUP"}
            ]
            etiquetas_inferiores = [
                palabra
                for palabra in palabras
                if normalizar_etiqueta(palabra.texto)
                in {"INFERIOR", "INF"}
            ]
            etiquetas = set(etiquetas_superiores + etiquetas_inferiores)
            restantes = [
                palabra
                for palabra in palabras
                if palabra not in etiquetas
            ]

            superiores = []
            inferiores = []
            if etiquetas_superiores and etiquetas_inferiores:
                for palabra in restantes:
                    distancia_superior = min(
                        abs(
                            _centro_y_palabra(palabra)
                            - _centro_y_palabra(etiqueta)
                        )
                        for etiqueta in etiquetas_superiores
                    )
                    distancia_inferior = min(
                        abs(
                            _centro_y_palabra(palabra)
                            - _centro_y_palabra(etiqueta)
                        )
                        for etiqueta in etiquetas_inferiores
                    )
                    destino = (
                        superiores
                        if distancia_superior < distancia_inferior
                        else inferiores
                    )
                    destino.append(palabra)
            elif etiquetas_superiores:
                superiores = restantes
            else:
                # En cuadros con una sola armadura, la malla indicada suele ser
                # la inferior. La ausencia de rótulos deja la superior vacía.
                inferiores = restantes

            superiores = _ordenar_palabras_armadura(superiores)
            inferiores = _ordenar_palabras_armadura(inferiores)
            superior = " ".join(
                palabra.texto
                for palabra in superiores
            )
            inferior = " ".join(
                palabra.texto
                for palabra in inferiores
            )

        resultado.append(
            {
                "referencia": registro["referencia"],
                "superior": superior,
                "inferior": inferior,
            }
        )
    return resultado


def interpretar_armaduras(registros_por_nivel):
    """Convierte las descripciones del plano en datos estructurados."""
    interpretadas = []
    referencias_con_texto = set()
    for registro in registros_por_nivel:
        for nivel in ("superior", "inferior"):
            texto = registro[nivel]
            if texto.strip():
                referencias_con_texto.add(registro["referencia"])
            coincidencias = list(PATRON_ARMADURA.finditer(texto))
            for coincidencia in coincidencias:
                direccion = coincidencia.group(1).upper() if coincidencia.group(1) else "AMBOS_SENTIDOS"
                interpretadas.append(
                    {
                        "referencia": registro["referencia"],
                        "nivel": nivel.upper(),
                        "direccion": direccion,
                        "cantidad_indicada": int(coincidencia.group(2)),
                        "diametro_pulgadas": coincidencia.group(3).replace(" ", ""),
                        "separacion_cm": Decimal(coincidencia.group(4).replace(",", ".")),
                    }
                )

    referencias_interpretadas = {
        registro["referencia"]
        for registro in interpretadas
    }
    faltantes = sorted(
        referencias_con_texto - referencias_interpretadas
    )
    if faltantes:
        raise ValueError(
            "No se pudo interpretar la notación de armadura para: "
            + ", ".join(faltantes)
            + ". Revise el cuadro o agregue un formato admitido."
        )
    return interpretadas


def expandir_direcciones(especificaciones):
    """Transforma 'ambos sentidos' en un registro X y otro Y."""
    resultado = []
    for especificacion in especificaciones:
        direcciones = ("X", "Y") if especificacion["direccion"] == "AMBOS_SENTIDOS" else (especificacion["direccion"],)
        for direccion in direcciones:
            resultado.append({**especificacion, "direccion": direccion})
    return resultado


def diametro_pulgadas_a_mm(fraccion):
    """Convierte, por ejemplo, 5/8 pulgadas a milímetros."""
    numerador, denominador = fraccion.split("/")
    return Decimal(numerador) / Decimal(denominador) * Decimal("25.4")


def peso_unitario_kg_m(diametro_mm):
    """Calcula kg/m con la fórmula habitual d²/162."""
    return diametro_mm**2 / Decimal("162")


def calcular_cantidad_barras(especificaciones, dimensiones, recubrimiento_cm):
    """Calcula barras por malla sin superar la separación indicada."""
    recubrimiento_m = recubrimiento_cm / Decimal("100")
    dimensiones_por_tipo = {fila["referencia"]: fila for fila in dimensiones}
    resultado = []

    for especificacion in especificaciones:
        dimension = dimensiones_por_tipo[especificacion["referencia"]]
        # Las barras X se distribuyen sobre Y; las barras Y se distribuyen sobre X.
        dimension_distribucion = dimension["y"] if especificacion["direccion"] == "X" else dimension["x"]
        longitud_disponible = dimension_distribucion - Decimal("2") * recubrimiento_m
        separacion_m = especificacion["separacion_cm"] / Decimal("100")
        cantidad_intervalos = int((longitud_disponible / separacion_m).to_integral_value(rounding=ROUND_CEILING))
        cantidad_posiciones = cantidad_intervalos + 1
        cantidad_barras = cantidad_posiciones * especificacion["cantidad_indicada"]
        separacion_real = longitud_disponible / Decimal(cantidad_intervalos)

        resultado.append(
            {
                **especificacion,
                "dimension_distribucion_m": dimension_distribucion,
                "longitud_disponible_m": longitud_disponible,
                "cantidad_posiciones": cantidad_posiciones,
                "cantidad_barras": cantidad_barras,
                "separacion_real_m": separacion_real,
            }
        )
    return resultado


def calcular_peso_acero(registros, dimensiones, conteo_fundaciones, recubrimiento_cm, doblez_cm):
    """Calcula longitud y peso teóricos de todas las barras."""
    dimensiones_por_tipo = {fila["referencia"]: fila for fila in dimensiones}
    recubrimiento_m = recubrimiento_cm / Decimal("100")
    doblez_m = doblez_cm / Decimal("100")
    resultado = []

    for registro in registros:
        dimension = dimensiones_por_tipo[registro["referencia"]]
        longitud_planta = dimension["x"] if registro["direccion"] == "X" else dimension["y"]
        longitud_barra = longitud_planta - Decimal("2") * recubrimiento_m + Decimal("2") * doblez_m
        metros_por_fundacion = Decimal(registro["cantidad_barras"]) * longitud_barra
        cantidad_fundaciones = conteo_fundaciones[registro["referencia"]]
        metros_totales = metros_por_fundacion * Decimal(cantidad_fundaciones)
        diametro_mm = diametro_pulgadas_a_mm(registro["diametro_pulgadas"])
        kg_m = peso_unitario_kg_m(diametro_mm)

        resultado.append(
            {
                **registro,
                "cantidad_fundaciones": cantidad_fundaciones,
                "longitud_barra_m": longitud_barra,
                "metros_por_fundacion": metros_por_fundacion,
                "peso_por_fundacion_kg": metros_por_fundacion * kg_m,
                "metros_totales": metros_totales,
                "diametro_mm": diametro_mm,
                "peso_unitario_kg_m": kg_m,
                "peso_total_kg": metros_totales * kg_m,
            }
        )
    return resultado


def resumir_por_diametro(registros):
    """Agrupa metros y kilogramos por diámetro comercial."""
    grupos = defaultdict(lambda: {"metros_totales": Decimal("0"), "peso_total_kg": Decimal("0")})
    for registro in registros:
        grupo = grupos[registro["diametro_pulgadas"]]
        grupo["diametro_pulgadas"] = registro["diametro_pulgadas"]
        grupo["diametro_mm"] = registro["diametro_mm"]
        grupo["peso_unitario_kg_m"] = registro["peso_unitario_kg_m"]
        grupo["metros_totales"] += registro["metros_totales"]
        grupo["peso_total_kg"] += registro["peso_total_kg"]
    return [grupos[diametro] for diametro in sorted(grupos)]


def calcular_barras_comerciales(resumen, longitud_barra_m, desperdicio_porcentaje):
    """Convierte los metros teóricos en barras enteras para compra."""
    factor = Decimal("1") + desperdicio_porcentaje / Decimal("100")
    resultado = []
    for grupo in resumen:
        metros_con_desperdicio = grupo["metros_totales"] * factor
        cantidad = int((metros_con_desperdicio / longitud_barra_m).to_integral_value(rounding=ROUND_CEILING))
        metros_compra = Decimal(cantidad) * longitud_barra_m
        resultado.append(
            {
                **grupo,
                "metros_con_desperdicio": metros_con_desperdicio,
                "barras_comerciales": cantidad,
                "metros_compra": metros_compra,
                "excedente_m": metros_compra - grupo["metros_totales"],
                "peso_con_desperdicio_kg": grupo["peso_total_kg"] * factor,
                "peso_compra_kg": metros_compra * grupo["peso_unitario_kg_m"],
            }
        )
    return resultado

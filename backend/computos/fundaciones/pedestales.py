"""Reglas geométricas y de acero para pedestales."""

from collections import Counter, defaultdict
from decimal import Decimal

from computos.columnas.computos import calcular_acero_columnas


def _numero(valor, predeterminado=None):
    if valor is None:
        return predeterminado

    try:
        return float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return predeterminado


def _referencia(fila):
    return str(
        fila.get("referencia_columna")
        or fila.get("referencia")
        or ""
    ).strip().upper()


def _clave_referencia(referencia):
    texto = str(referencia or "")
    prefijo = "".join(
        caracter
        for caracter in texto
        if not caracter.isdigit()
    )
    numero = "".join(
        caracter
        for caracter in texto
        if caracter.isdigit()
    )
    return (
        prefijo,
        int(numero) if numero else 0,
        texto,
    )


def _por_referencia(armaduras):
    return {
        _referencia(armadura): armadura
        for armadura in armaduras or []
        if isinstance(armadura, dict)
        and _referencia(armadura)
    }


def _multiplicar_datos_acero(datos, cantidad):
    resultado = dict(datos)

    for campo in (
        "metros_longitudinales",
        "metros_estribos",
        "metros_totales",
        "peso_kg",
    ):
        resultado[campo] = round(
            _numero(datos.get(campo), 0.0) * cantidad,
            3,
        )

    return resultado


def calcular_acero_pedestales(
    pedestales,
    armaduras_columnas,
    armaduras_pedestales=None,
):
    """Calcula el acero del pedestal con una regla de respaldo trazable.

    Una armadura específica de pedestal siempre tiene prioridad. Cuando el
    proyecto no la aporta, se usa la armadura válida de la columna con la
    misma referencia. La longitud computada corresponde únicamente a la
    altura del pedestal; no se inventan anclajes ni solapes adicionales.

    El resultado puede ser parcial: las referencias sin una armadura válida
    permanecen fuera del subtotal y se informan individualmente.
    """

    armaduras_columnas_por_referencia = _por_referencia(
        armaduras_columnas
    )
    armaduras_pedestales_por_referencia = _por_referencia(
        armaduras_pedestales
    )
    detalles = []
    referencias_computadas = []
    referencias_pendientes = []
    referencias_heredadas = []
    referencias_explicitas = []
    acumulado_diametros = defaultdict(
        lambda: {
            "metros_longitudinales": 0.0,
            "metros_estribos": 0.0,
            "peso_kg": 0.0,
        }
    )

    for fila_original in pedestales or []:
        fila = dict(fila_original)
        referencia = _referencia(fila)
        cantidad = int(_numero(fila.get("cantidad"), 0) or 0)
        altura_real = _numero(
            fila.get("altura_real_m")
            if fila.get("altura_real_m") is not None
            else fila.get("altura_m")
        )
        altura_minima = _numero(fila.get("altura_minima_m"))
        altura = (
            altura_real
            if altura_real is not None and altura_real > 0
            else altura_minima
        )
        usa_altura_minima = not (
            altura_real is not None and altura_real > 0
        )

        armadura_columna = (
            armaduras_columnas_por_referencia.get(referencia)
            or fila.get("armadura_columna_candidata")
        )
        armadura_guardada = fila.get("armadura_pedestal")
        armadura_explicita = (
            fila.get("armadura_pedestal_explicita")
            or armaduras_pedestales_por_referencia.get(referencia)
            or (
                armadura_guardada
                if fila.get("origen_armadura_pedestal")
                in (None, "especifica_pedestal")
                else None
            )
        )
        armadura = armadura_explicita or armadura_columna
        origen_armadura = (
            "especifica_pedestal"
            if armadura_explicita
            else (
                "heredada_de_columna"
                if armadura_columna
                else "no_disponible"
            )
        )

        fila.update(
            {
                "referencia_columna": referencia,
                "armadura_columna_candidata": armadura_columna,
                "armadura_pedestal": armadura,
                "origen_armadura_pedestal": origen_armadura,
                "criterio_armadura_pedestal": (
                    "armadura_explicita_prioritaria_y_respaldo_de_columna"
                ),
                "usa_altura_minima_para_acero": usa_altura_minima,
            }
        )

        if not referencia or cantidad <= 0 or not altura or altura <= 0:
            referencias_pendientes.append(referencia or "SIN_REFERENCIA")
            fila.update(
                {
                    "acero_kg": None,
                    "peso_acero_total_kg": None,
                    "acero_disponible": False,
                    "estado_acero": "pendiente_geometria",
                    "estado_armadura_pedestal": "pendiente_geometria",
                    "problemas_armadura_pedestal": [
                        "Falta una referencia, cantidad o altura válida."
                    ],
                }
            )
            detalles.append(fila)
            continue

        if armadura is None:
            referencias_pendientes.append(referencia)
            fila.update(
                {
                    "acero_kg": None,
                    "peso_acero_total_kg": None,
                    "acero_disponible": False,
                    "estado_acero": "pendiente_armadura",
                    "estado_armadura_pedestal": (
                        "sin_armadura_candidata_valida"
                    ),
                    "problemas_armadura_pedestal": [
                        "No existe armadura específica ni una armadura "
                        "válida de la columna asociada."
                    ],
                }
            )
            detalles.append(fila)
            continue

        try:
            calculo_unitario = calcular_acero_columnas(
                [
                    {
                        "referencia": referencia,
                        "altura_m": altura,
                    }
                ],
                [armadura],
                referencias_confirmadas=[referencia],
                longitud_adicional_por_extremo_m=0.0,
            )
        except ValueError as error:
            referencias_pendientes.append(referencia)
            fila.update(
                {
                    "acero_kg": None,
                    "peso_acero_total_kg": None,
                    "acero_disponible": False,
                    "estado_acero": "pendiente_armadura",
                    "estado_armadura_pedestal": (
                        "armadura_pedestal_explicita_invalida"
                        if armadura_explicita
                        else "armadura_columna_candidata_invalida"
                    ),
                    "problemas_armadura_pedestal": [str(error)],
                }
            )
            detalles.append(fila)
            continue

        detalle_unitario = calculo_unitario["detalles"][0]
        acero_por_diametro = [
            _multiplicar_datos_acero(datos, cantidad)
            for datos in detalle_unitario.get(
                "acero_por_diametro",
                [],
            )
        ]

        for datos in acero_por_diametro:
            diametro = datos.get("diametro_pulgadas")

            if not diametro:
                continue

            acumulado_diametros[diametro][
                "metros_longitudinales"
            ] += _numero(datos.get("metros_longitudinales"), 0.0)
            acumulado_diametros[diametro][
                "metros_estribos"
            ] += _numero(datos.get("metros_estribos"), 0.0)
            acumulado_diametros[diametro]["peso_kg"] += _numero(
                datos.get("peso_kg"),
                0.0,
            )

        peso_unitario = detalle_unitario["peso_acero_total_kg"]
        peso_total = round(peso_unitario * cantidad, 3)
        referencias_computadas.append(referencia)

        if armadura_explicita:
            referencias_explicitas.append(referencia)
            estado_armadura = "computada_especifica_pedestal"
        else:
            referencias_heredadas.append(referencia)
            estado_armadura = "computada_por_herencia_columna"

        fila.update(
            {
                "altura_acero_m": round(altura, 3),
                "longitud_barra_longitudinal_m": detalle_unitario[
                    "longitud_barra_longitudinal_m"
                ],
                "metros_barras_longitudinales_unitario": (
                    detalle_unitario["metros_barras_longitudinales"]
                ),
                "metros_barras_longitudinales": round(
                    detalle_unitario["metros_barras_longitudinales"]
                    * cantidad,
                    3,
                ),
                "peso_barras_longitudinales_unitario_kg": (
                    detalle_unitario["peso_barras_longitudinales_kg"]
                ),
                "peso_barras_longitudinales_kg": round(
                    detalle_unitario["peso_barras_longitudinales_kg"]
                    * cantidad,
                    3,
                ),
                "cantidad_estribos_unitario": detalle_unitario[
                    "cantidad_estribos"
                ],
                "cantidad_estribos": (
                    detalle_unitario["cantidad_estribos"] * cantidad
                ),
                "longitud_unidad_estribo_m": detalle_unitario[
                    "longitud_unidad_estribo_m"
                ],
                "metros_estribos_unitario": detalle_unitario[
                    "metros_estribos"
                ],
                "metros_estribos": round(
                    detalle_unitario["metros_estribos"] * cantidad,
                    3,
                ),
                "peso_estribos_unitario_kg": detalle_unitario[
                    "peso_estribos_kg"
                ],
                "peso_estribos_kg": round(
                    detalle_unitario["peso_estribos_kg"] * cantidad,
                    3,
                ),
                "peso_acero_unitario_kg": peso_unitario,
                "peso_acero_total_kg": peso_total,
                "acero_kg": peso_total,
                "acero_por_diametro": acero_por_diametro,
                "acero_disponible": True,
                "estado_acero": (
                    "preliminar_altura_minima"
                    if usa_altura_minima
                    else "computado"
                ),
                "estado_armadura_pedestal": estado_armadura,
                "problemas_armadura_pedestal": [],
            }
        )
        detalles.append(fila)

    resumen_acero = [
        {
            "diametro_pulgadas": diametro,
            "metros_longitudinales": round(
                datos["metros_longitudinales"],
                3,
            ),
            "metros_estribos": round(
                datos["metros_estribos"],
                3,
            ),
            "metros_totales": round(
                datos["metros_longitudinales"]
                + datos["metros_estribos"],
                3,
            ),
            "peso_kg": round(datos["peso_kg"], 3),
        }
        for diametro, datos in sorted(
            acumulado_diametros.items(),
            key=lambda elemento: elemento[0],
        )
    ]
    filas_computadas = [
        fila
        for fila in detalles
        if fila.get("acero_disponible")
    ]
    referencias_pendientes = sorted(
        set(referencias_pendientes),
        key=_clave_referencia,
    )
    referencias_computadas = sorted(
        set(referencias_computadas),
        key=_clave_referencia,
    )

    return {
        "detalles": detalles,
        "resumen_acero": resumen_acero,
        "acero_total_kg": (
            round(
                sum(
                    fila["peso_acero_total_kg"]
                    for fila in filas_computadas
                ),
                3,
            )
            if filas_computadas
            else None
        ),
        "referencias_computadas": referencias_computadas,
        "referencias_pendientes": referencias_pendientes,
        "referencias_heredadas_de_columnas": sorted(
            set(referencias_heredadas),
            key=_clave_referencia,
        ),
        "referencias_con_armadura_explicita": sorted(
            set(referencias_explicitas),
            key=_clave_referencia,
        ),
        "cantidad_tipos_computados": len(filas_computadas),
        "cantidad_tipos_pendientes": (
            len(detalles) - len(filas_computadas)
        ),
        "cantidad_pedestales_computados": sum(
            int(_numero(fila.get("cantidad"), 0) or 0)
            for fila in filas_computadas
        ),
        "resultado_completo": bool(detalles)
        and len(filas_computadas) == len(detalles),
        "resultado_parcial": bool(filas_computadas)
        and len(filas_computadas) < len(detalles),
        "usa_altura_minima": any(
            fila.get("usa_altura_minima_para_acero")
            and fila.get("acero_disponible")
            for fila in detalles
        ),
        "criterio_armadura": (
            "armadura_especifica_del_pedestal_o_armadura_de_la_columna_asociada"
        ),
        "criterio_longitudinal": "altura_del_pedestal_sin_adicionales",
        "criterio_estribos": "ceil_altura_sobre_separacion_mas_uno",
    }


def contar_columnas_por_tipo(
    columnas,
):
    """
    Cuenta cuántas columnas aparecen de cada tipo.

    Ejemplo:
        C1 -> 8 apariciones
        C2 -> 4 apariciones
    """

    return Counter(
        columna["referencia"]
        for columna in columnas
    )

def calcular_dimensiones_pedestales(
    secciones_columnas,
    conteo_columnas,
    incremento_cm,
):
    """
    Calcula las dimensiones de cada tipo de pedestal
    a partir de las dimensiones de la columna.

    La regla utilizada es:

        dimensión pedestal =
        dimensión columna + incremento
    """

    incremento_m = (
        Decimal(incremento_cm)
        / Decimal("100")
    )

    resultados = []

    for seccion in secciones_columnas:

        # Ignorar temporalmente cualquier sección
        # que haya quedado pendiente de revisión.
        if seccion["estado"] != "CORRECTO":

            continue

        referencia = seccion[
            "referencia"
        ]

        dimension_columna_1 = seccion[
            "dimension_1_m"
        ]

        dimension_columna_2 = seccion[
            "dimension_2_m"
        ]

        # ==================================================
        # CALCULAR LAS DIMENSIONES DEL PEDESTAL
        # ==================================================

        dimension_pedestal_1 = (
            dimension_columna_1
            + incremento_m
        )

        dimension_pedestal_2 = (
            dimension_columna_2
            + incremento_m
        )

        cantidad = conteo_columnas.get(
            referencia,
            0,
        )

        resultados.append(
            {
                "referencia_columna": (
                    referencia
                ),
                "cantidad": cantidad,
                "dimension_columna_1_m": (
                    dimension_columna_1
                ),
                "dimension_columna_2_m": (
                    dimension_columna_2
                ),
                "incremento_m": incremento_m,
                "dimension_pedestal_1_m": (
                    dimension_pedestal_1
                ),
                "dimension_pedestal_2_m": (
                    dimension_pedestal_2
                ),
                "origen": seccion["origen"],
                "referencia_original": (
                    seccion[
                        "referencia_original"
                    ]
                ),
                "fue_corregida": (
                    seccion["fue_corregida"]
                ),
            }
        )

    resultados.sort(
        key=lambda pedestal: int(
            pedestal[
                "referencia_columna"
            ][1:]
        )
    )

    return resultados

def calcular_computos_pedestales(
    pedestales,
    altura_minima_m,
    usar_encofrado=True,
):
    """
    Calcula el volumen mínimo y el área lateral
    bruta de encofrado de los pedestales.

    Los resultados son preliminares porque la altura
    definitiva depende del terreno firme y de la
    relación con las vigas de riostra.
    """

    altura_minima_m = Decimal(
        altura_minima_m
    )

    resultados = []

    volumen_general = Decimal("0")
    encofrado_general = Decimal("0")

    # ======================================================
    # 1. RECORRER CADA TIPO DE PEDESTAL
    # ======================================================

    for pedestal in pedestales:

        referencia = pedestal[
            "referencia_columna"
        ]

        cantidad = pedestal[
            "cantidad"
        ]

        dimension_1 = pedestal[
            "dimension_pedestal_1_m"
        ]

        dimension_2 = pedestal[
            "dimension_pedestal_2_m"
        ]

        # ==================================================
        # 2. CALCULAR VOLUMEN UNITARIO
        # ==================================================

        volumen_unitario = (
            dimension_1
            * dimension_2
            * altura_minima_m
        )

        volumen_total = (
            volumen_unitario
            * Decimal(cantidad)
        )

        # ==================================================
        # 3. CALCULAR ENCOFRADO LATERAL
        # ==================================================

        if usar_encofrado:

            # Área de las cuatro caras:
            #
            # 2 × (lado 1 + lado 2) × altura

            encofrado_unitario = (
                Decimal("2")
                * (
                    dimension_1
                    + dimension_2
                )
                * altura_minima_m
            )

        else:

            encofrado_unitario = (
                Decimal("0")
            )

        encofrado_total = (
            encofrado_unitario
            * Decimal(cantidad)
        )

        # ==================================================
        # 4. ACUMULAR LOS TOTALES
        # ==================================================

        volumen_general += volumen_total
        encofrado_general += encofrado_total

        # ==================================================
        # 5. GUARDAR EL RESULTADO
        # ==================================================

        resultados.append(
            {
                **pedestal,
                "altura_minima_m": (
                    altura_minima_m
                ),
                "volumen_unitario_m3": (
                    volumen_unitario
                ),
                "volumen_total_m3": (
                    volumen_total
                ),
                "encofrado_unitario_m2": (
                    encofrado_unitario
                ),
                "encofrado_total_m2": (
                    encofrado_total
                ),
                "tipo_resultado": (
                    "PRELIMINAR_MINIMO"
                ),
            }
        )

    return {
        "detalles": resultados,
        "volumen_general_m3": (
            volumen_general
        ),
        "encofrado_general_m2": (
            encofrado_general
        ),
    }

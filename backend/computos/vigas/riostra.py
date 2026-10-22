"""Funciones validadas para leer rótulos de vigas de riostra.

Este módulo detecta textos como ``V.R. 1 (40 X 50)`` y valida las
secciones encontradas. La detección de los tramos geométricos se
implementará en una etapa posterior leyendo las líneas reales del PDF.
"""

from collections import Counter, defaultdict
from decimal import Decimal
from math import atan2, degrees, hypot, acos
from pathlib import Path
import re
from statistics import median

import pymupdf


PATRON_VIGA_RIOSTRA = re.compile(
    r"V\.?\s*R\.?\s*"
    r"(\d+)\s*"
    r"\(\s*"
    r"(\d+)\s*"
    r"[Xx×]\s*"
    r"(\d+)\s*"
    r"\)",
    re.IGNORECASE,
)


def detectar_vigas_riostra(palabras):
    """Detecta las referencias y secciones de vigas escritas en el plano."""

    # PyMuPDF entrega cada palabra por separado. Primero reunimos
    # las palabras que pertenecen a una misma línea de texto.
    lineas = defaultdict(list)

    for palabra in palabras:
        clave_linea = (
            palabra["pagina"],
            palabra["numero_bloque"],
            palabra["numero_linea"],
        )
        lineas[clave_linea].append(palabra)

    detecciones = []

    for clave_linea, palabras_linea in lineas.items():
        palabras_linea.sort(
            key=lambda palabra: palabra["numero_palabra"]
        )

        texto_linea = " ".join(
            palabra["texto"]
            for palabra in palabras_linea
        )

        coincidencia = PATRON_VIGA_RIOSTRA.search(texto_linea)

        if coincidencia is None:
            continue

        numero_viga = coincidencia.group(1)
        ancho_cm = Decimal(coincidencia.group(2))
        alto_cm = Decimal(coincidencia.group(3))

        # Calculamos el rectángulo que contiene toda la línea.
        x0 = min(palabra["x0"] for palabra in palabras_linea)
        y0 = min(palabra["y0"] for palabra in palabras_linea)
        x1 = max(palabra["x1"] for palabra in palabras_linea)
        y1 = max(palabra["y1"] for palabra in palabras_linea)

        detecciones.append(
            {
                "referencia": f"VR{numero_viga}",
                "texto_original": texto_linea,
                "pagina": clave_linea[0],
                "ancho_cm": ancho_cm,
                "alto_cm": alto_cm,
                "ancho_m": ancho_cm / Decimal("100"),
                "alto_m": alto_cm / Decimal("100"),
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
                "centro_x": (x0 + x1) / 2,
                "centro_y": (y0 + y1) / 2,
            }
        )

    return detecciones


def eliminar_rotulos_duplicados(rotulos, tolerancia=0.5):
    """Elimina textos repetidos en prácticamente la misma posición.

    Algunos PDF contienen dos objetos de texto idénticos superpuestos.
    Esto evita contar dos veces una misma etiqueta visual.
    """

    rotulos_unicos = []
    duplicados = []

    for rotulo in rotulos:
        rotulo_repetido = None

        for rotulo_unico in rotulos_unicos:
            misma_identidad = (
                rotulo["pagina"] == rotulo_unico["pagina"]
                and rotulo["referencia"] == rotulo_unico["referencia"]
                and rotulo["ancho_cm"] == rotulo_unico["ancho_cm"]
                and rotulo["alto_cm"] == rotulo_unico["alto_cm"]
            )

            distancia = hypot(
                rotulo["centro_x"] - rotulo_unico["centro_x"],
                rotulo["centro_y"] - rotulo_unico["centro_y"],
            )

            if misma_identidad and distancia <= tolerancia:
                rotulo_repetido = rotulo_unico
                break

        if rotulo_repetido is None:
            rotulos_unicos.append(rotulo)
        else:
            duplicados.append(
                {
                    "rotulo_conservado": rotulo_repetido,
                    "rotulo_descartado": rotulo,
                }
            )

    return rotulos_unicos, duplicados


def validar_secciones_por_referencia(vigas):
    """Agrupa y cuenta las secciones detectadas para cada tipo de viga."""

    secciones_por_referencia = defaultdict(Counter)

    for viga in vigas:
        referencia = viga["referencia"]
        seccion = (
            viga["ancho_cm"],
            viga["alto_cm"],
        )
        secciones_por_referencia[referencia][seccion] += 1

    resultado = {}

    for referencia, conteo_secciones in secciones_por_referencia.items():
        resultado[referencia] = {
            "secciones": [
                {
                    "ancho_cm": seccion[0],
                    "alto_cm": seccion[1],
                    "cantidad_rotulos": cantidad,
                }
                for seccion, cantidad in sorted(
                    conteo_secciones.items()
                )
            ],
            "tiene_variantes": len(conteo_secciones) > 1,
            "estado": "CORRECTO",
        }

    return resultado


def calcular_limites_zona_estructural(nodos, margen=10.0):
    """Calcula una zona de trabajo alrededor de los nodos estructurales.

    La zona permite excluir el cajetín, las firmas y los detalles constructivos
    que se encuentran fuera de la planta principal.
    """

    if not nodos:
        raise ValueError(
            "No hay nodos para calcular la zona estructural."
        )

    nodos_por_pagina = defaultdict(list)

    for nodo in nodos:
        nodos_por_pagina[nodo["pagina"]].append(nodo)

    limites = {}

    for pagina, nodos_pagina in nodos_por_pagina.items():
        limites[pagina] = {
            "x_min": min(
                nodo["centro_x"]
                for nodo in nodos_pagina
            ) - margen,
            "y_min": min(
                nodo["centro_y"]
                for nodo in nodos_pagina
            ) - margen,
            "x_max": max(
                nodo["centro_x"]
                for nodo in nodos_pagina
            ) + margen,
            "y_max": max(
                nodo["centro_y"]
                for nodo in nodos_pagina
            ) + margen,
        }

    return limites


def extraer_bordes_vectoriales_vigas(
    ruta_pdf,
    nodos,
    espesor_objetivo=0.60,
    tolerancia_espesor=0.02,
    longitud_minima=15.0,
    margen_zona=10.0,
):
    """Extrae segmentos rectos que pueden ser bordes de vigas.

    Esta función no inventa conexiones. Lee los objetos de dibujo guardados
    por AutoCAD dentro del PDF y selecciona solamente los que cumplen con el
    espesor observado, la longitud mínima y la zona de la planta.
    """

    ruta_pdf = Path(ruta_pdf)

    if not ruta_pdf.exists():
        raise FileNotFoundError(
            f"No se encontró el PDF: {ruta_pdf}"
        )

    limites_por_pagina = calcular_limites_zona_estructural(
        nodos,
        margen=margen_zona,
    )

    documento = pymupdf.open(ruta_pdf)
    bordes = []

    total_objetos_dibujo = 0
    total_segmentos_rectos = 0
    segmentos_espesor_correcto = 0
    descartados_por_longitud = 0
    descartados_fuera_zona = 0

    for indice_pagina, pagina in enumerate(
        documento,
        start=1,
    ):
        limites = limites_por_pagina.get(indice_pagina)

        if limites is None:
            continue

        dibujos = pagina.get_drawings()
        total_objetos_dibujo += len(dibujos)

        for dibujo in dibujos:
            espesor = float(dibujo.get("width") or 0.0)

            for item in dibujo.get("items", []):
                if item[0] != "l":
                    continue

                total_segmentos_rectos += 1

                if abs(espesor - espesor_objetivo) > tolerancia_espesor:
                    continue

                segmentos_espesor_correcto += 1

                punto_inicial = item[1]
                punto_final = item[2]
                diferencia_x = punto_final.x - punto_inicial.x
                diferencia_y = punto_final.y - punto_inicial.y
                longitud = hypot(diferencia_x, diferencia_y)

                if longitud < longitud_minima:
                    descartados_por_longitud += 1
                    continue

                centro_x = (
                    punto_inicial.x + punto_final.x
                ) / 2
                centro_y = (
                    punto_inicial.y + punto_final.y
                ) / 2

                centro_dentro_zona = (
                    limites["x_min"] <= centro_x <= limites["x_max"]
                    and limites["y_min"] <= centro_y <= limites["y_max"]
                )

                if not centro_dentro_zona:
                    descartados_fuera_zona += 1
                    continue

                angulo = degrees(
                    atan2(diferencia_y, diferencia_x)
                ) % 180

                bordes.append(
                    {
                        "id_borde": len(bordes) + 1,
                        "pagina": indice_pagina,
                        "espesor_pdf": round(espesor, 3),
                        "x_inicial": round(punto_inicial.x, 3),
                        "y_inicial": round(punto_inicial.y, 3),
                        "x_final": round(punto_final.x, 3),
                        "y_final": round(punto_final.y, 3),
                        "centro_x": round(centro_x, 3),
                        "centro_y": round(centro_y, 3),
                        "longitud_pdf": round(longitud, 3),
                        "angulo_pdf_grados": round(angulo, 3),
                    }
                )

    documento.close()

    diagnostico = {
        "archivo": ruta_pdf.name,
        "espesor_objetivo_pdf": espesor_objetivo,
        "tolerancia_espesor_pdf": tolerancia_espesor,
        "longitud_minima_pdf": longitud_minima,
        "margen_zona_pdf": margen_zona,
        "total_objetos_dibujo": total_objetos_dibujo,
        "total_segmentos_rectos": total_segmentos_rectos,
        "segmentos_espesor_correcto": segmentos_espesor_correcto,
        "descartados_por_longitud": descartados_por_longitud,
        "descartados_fuera_zona": descartados_fuera_zona,
        "bordes_candidatos": len(bordes),
        "limites_por_pagina": limites_por_pagina,
    }

    return bordes, diagnostico


def dibujar_bordes_vectoriales_vigas(
    ruta_pdf,
    bordes,
    ruta_salida,
    escala=2.0,
):
    """Dibuja en rojo los bordes candidatos sobre la planta original."""

    ruta_pdf = Path(ruta_pdf)
    ruta_salida = Path(ruta_salida)
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)

    documento = pymupdf.open(ruta_pdf)

    if len(documento) != 1:
        documento.close()
        raise ValueError(
            "El diagnóstico visual actual admite planos de una página."
        )

    pagina = documento[0]
    forma = pagina.new_shape()

    for borde in bordes:
        forma.draw_line(
            pymupdf.Point(
                borde["x_inicial"],
                borde["y_inicial"],
            ),
            pymupdf.Point(
                borde["x_final"],
                borde["y_final"],
            ),
        )

    if bordes:
        forma.finish(
            color=(1, 0, 0),
            width=1.0,
        )
        forma.commit(overlay=True)

    imagen = pagina.get_pixmap(
        matrix=pymupdf.Matrix(escala, escala),
        alpha=False,
    )
    imagen.save(ruta_salida)
    documento.close()

def _obtener_geometria_borde(borde):
    """Calcula dirección y longitud de un borde."""

    diferencia_x = (
        borde["x_final"] - borde["x_inicial"]
    )
    diferencia_y = (
        borde["y_final"] - borde["y_inicial"]
    )

    longitud = hypot(
        diferencia_x,
        diferencia_y,
    )

    if longitud == 0:
        raise ValueError(
            f"El borde {borde['id_borde']} "
            "tiene longitud cero."
        )

    direccion_x = diferencia_x / longitud
    direccion_y = diferencia_y / longitud

    # Dos líneas paralelas pueden haber sido dibujadas
    # en sentidos contrarios. Las orientamos igual.
    if (
        direccion_x < 0
        or (
            abs(direccion_x) < 1e-9
            and direccion_y < 0
        )
    ):
        direccion_x *= -1
        direccion_y *= -1

    return {
        "direccion_x": direccion_x,
        "direccion_y": direccion_y,
        "longitud": longitud,
    }


def _analizar_pareja_bordes(
    borde_1,
    borde_2,
):
    """Mide si dos bordes pueden pertenecer a una misma viga."""

    geometria_1 = _obtener_geometria_borde(
        borde_1
    )
    geometria_2 = _obtener_geometria_borde(
        borde_2
    )

    direccion_1_x = geometria_1[
        "direccion_x"
    ]
    direccion_1_y = geometria_1[
        "direccion_y"
    ]
    direccion_2_x = geometria_2[
        "direccion_x"
    ]
    direccion_2_y = geometria_2[
        "direccion_y"
    ]

    # El producto escalar permite medir
    # la diferencia angular entre las líneas.
    producto_escalar = (
        direccion_1_x * direccion_2_x
        + direccion_1_y * direccion_2_y
    )

    producto_escalar = max(
        -1.0,
        min(1.0, producto_escalar),
    )

    diferencia_angular = degrees(
        acos(abs(producto_escalar))
    )

    if producto_escalar < 0:
        direccion_2_x *= -1
        direccion_2_y *= -1

    # Dirección media de ambos bordes.
    direccion_eje_x = (
        direccion_1_x + direccion_2_x
    )
    direccion_eje_y = (
        direccion_1_y + direccion_2_y
    )

    modulo_direccion = hypot(
        direccion_eje_x,
        direccion_eje_y,
    )

    direccion_eje_x /= modulo_direccion
    direccion_eje_y /= modulo_direccion

    # Vector perpendicular a los bordes.
    normal_x = -direccion_eje_y
    normal_y = direccion_eje_x

    def obtener_intervalo(borde):
        """Proyecta los extremos sobre la dirección del eje."""

        proyeccion_inicial = (
            borde["x_inicial"] * direccion_eje_x
            + borde["y_inicial"] * direccion_eje_y
        )

        proyeccion_final = (
            borde["x_final"] * direccion_eje_x
            + borde["y_final"] * direccion_eje_y
        )

        return sorted(
            [
                proyeccion_inicial,
                proyeccion_final,
            ]
        )

    intervalo_1 = obtener_intervalo(
        borde_1
    )
    intervalo_2 = obtener_intervalo(
        borde_2
    )

    inicio_superposicion = max(
        intervalo_1[0],
        intervalo_2[0],
    )

    final_superposicion = min(
        intervalo_1[1],
        intervalo_2[1],
    )

    longitud_superpuesta = max(
        0.0,
        final_superposicion
        - inicio_superposicion,
    )

    longitud_menor = min(
        geometria_1["longitud"],
        geometria_2["longitud"],
    )

    proporcion_superpuesta = min(
        1.0,
        longitud_superpuesta
        / longitud_menor,
    )

    centro_1_x = (
        borde_1["x_inicial"]
        + borde_1["x_final"]
    ) / 2

    centro_1_y = (
        borde_1["y_inicial"]
        + borde_1["y_final"]
    ) / 2

    centro_2_x = (
        borde_2["x_inicial"]
        + borde_2["x_final"]
    ) / 2

    centro_2_y = (
        borde_2["y_inicial"]
        + borde_2["y_final"]
    ) / 2

    # Ubicación perpendicular de cada borde.
    posicion_normal_1 = (
        centro_1_x * normal_x
        + centro_1_y * normal_y
    )

    posicion_normal_2 = (
        centro_2_x * normal_x
        + centro_2_y * normal_y
    )

    separacion = abs(
        posicion_normal_2
        - posicion_normal_1
    )

    # El eje se coloca exactamente en el medio.
    posicion_normal_eje = (
        posicion_normal_1
        + posicion_normal_2
    ) / 2

    longitud_mayor = max(
        geometria_1["longitud"],
        geometria_2["longitud"],
    )

    diferencia_longitud_relativa = (
        abs(
            geometria_1["longitud"]
            - geometria_2["longitud"]
        )
        / longitud_mayor
    )

    # Reconstruir los extremos del eje central.
    eje_x_inicial = (
        direccion_eje_x
        * inicio_superposicion
        + normal_x
        * posicion_normal_eje
    )

    eje_y_inicial = (
        direccion_eje_y
        * inicio_superposicion
        + normal_y
        * posicion_normal_eje
    )

    eje_x_final = (
        direccion_eje_x
        * final_superposicion
        + normal_x
        * posicion_normal_eje
    )

    eje_y_final = (
        direccion_eje_y
        * final_superposicion
        + normal_y
        * posicion_normal_eje
    )

    angulo_eje = degrees(
        atan2(
            direccion_eje_y,
            direccion_eje_x,
        )
    ) % 180

    return {
        "diferencia_angular_grados": (
            diferencia_angular
        ),
        "separacion_bordes_pdf": separacion,
        "proporcion_superpuesta": (
            proporcion_superpuesta
        ),
        "diferencia_longitud_relativa": (
            diferencia_longitud_relativa
        ),
        "x_inicial": eje_x_inicial,
        "y_inicial": eje_y_inicial,
        "x_final": eje_x_final,
        "y_final": eje_y_final,
        "longitud_pdf": longitud_superpuesta,
        "angulo_pdf_grados": angulo_eje,
    }


def _ejes_practicamente_iguales(
    eje_1,
    eje_2,
    tolerancia_posicion,
):
    """Comprueba si dos parejas produjeron el mismo eje."""

    if eje_1["pagina"] != eje_2["pagina"]:
        return False

    centro_1_x = (
        eje_1["x_inicial"]
        + eje_1["x_final"]
    ) / 2

    centro_1_y = (
        eje_1["y_inicial"]
        + eje_1["y_final"]
    ) / 2

    centro_2_x = (
        eje_2["x_inicial"]
        + eje_2["x_final"]
    ) / 2

    centro_2_y = (
        eje_2["y_inicial"]
        + eje_2["y_final"]
    ) / 2

    distancia_centros = hypot(
        centro_1_x - centro_2_x,
        centro_1_y - centro_2_y,
    )

    diferencia_angulos = abs(
        eje_1["angulo_pdf_grados"]
        - eje_2["angulo_pdf_grados"]
    )

    diferencia_angulos = min(
        diferencia_angulos,
        180 - diferencia_angulos,
    )

    diferencia_longitudes = abs(
        eje_1["longitud_pdf"]
        - eje_2["longitud_pdf"]
    )

    return (
        distancia_centros
        <= tolerancia_posicion
        and diferencia_angulos <= 0.50
        and diferencia_longitudes <= 1.0
    )


def emparejar_bordes_paralelos(
    bordes,
    diferencia_angular_maxima=0.50,
    separacion_minima=4.40,
    separacion_maxima=6.50,
    superposicion_minima=0.90,
    diferencia_longitud_maxima=0.20,
    tolerancia_ejes_duplicados=0.50,
):
    """Empareja bordes y crea un eje central candidato."""

    if separacion_minima >= separacion_maxima:
        raise ValueError(
            "La separación mínima debe ser "
            "menor que la máxima."
        )

    posibles_parejas = []

    # Comparar cada borde con todos los posteriores.
    for indice, borde_1 in enumerate(bordes):

        for borde_2 in bordes[indice + 1:]:

            if (
                borde_1["pagina"]
                != borde_2["pagina"]
            ):
                continue

            analisis = _analizar_pareja_bordes(
                borde_1,
                borde_2,
            )

            cumple_filtros = (
                analisis[
                    "diferencia_angular_grados"
                ]
                <= diferencia_angular_maxima
                and separacion_minima
                <= analisis[
                    "separacion_bordes_pdf"
                ]
                <= separacion_maxima
                and analisis[
                    "proporcion_superpuesta"
                ]
                >= superposicion_minima
                and analisis[
                    "diferencia_longitud_relativa"
                ]
                <= diferencia_longitud_maxima
            )

            if not cumple_filtros:
                continue

            # Menor puntaje significa mayor semejanza.
            puntaje = (
                analisis[
                    "diferencia_angular_grados"
                ]
                + (
                    1
                    - analisis[
                        "proporcion_superpuesta"
                    ]
                ) * 10
                + analisis[
                    "diferencia_longitud_relativa"
                ]
            )

            posibles_parejas.append(
                {
                    "puntaje": puntaje,
                    "borde_1": borde_1,
                    "borde_2": borde_2,
                    "analisis": analisis,
                }
            )

    # Evaluar primero las parejas de mejor calidad.
    posibles_parejas.sort(
        key=lambda pareja: (
            pareja["puntaje"],
            pareja["analisis"][
                "separacion_bordes_pdf"
            ],
        )
    )

    ids_bordes_utilizados = set()
    ejes_candidatos = []
    cantidad_parejas_seleccionadas = 0
    cantidad_ejes_duplicados = 0

    for pareja in posibles_parejas:

        borde_1 = pareja["borde_1"]
        borde_2 = pareja["borde_2"]

        id_borde_1 = borde_1["id_borde"]
        id_borde_2 = borde_2["id_borde"]

        # Cada borde puede pertenecer a una sola pareja.
        if (
            id_borde_1
            in ids_bordes_utilizados
            or id_borde_2
            in ids_bordes_utilizados
        ):
            continue

        ids_bordes_utilizados.update(
            [
                id_borde_1,
                id_borde_2,
            ]
        )

        cantidad_parejas_seleccionadas += 1
        analisis = pareja["analisis"]

        eje = {
            "pagina": borde_1["pagina"],
            "id_borde_1": id_borde_1,
            "id_borde_2": id_borde_2,
            "x_inicial": round(
                analisis["x_inicial"],
                3,
            ),
            "y_inicial": round(
                analisis["y_inicial"],
                3,
            ),
            "x_final": round(
                analisis["x_final"],
                3,
            ),
            "y_final": round(
                analisis["y_final"],
                3,
            ),
            "centro_x": round(
                (
                    analisis["x_inicial"]
                    + analisis["x_final"]
                ) / 2,
                3,
            ),
            "centro_y": round(
                (
                    analisis["y_inicial"]
                    + analisis["y_final"]
                ) / 2,
                3,
            ),
            "longitud_pdf": round(
                analisis["longitud_pdf"],
                3,
            ),
            "angulo_pdf_grados": round(
                analisis[
                    "angulo_pdf_grados"
                ],
                3,
            ),
            "separacion_bordes_pdf": round(
                analisis[
                    "separacion_bordes_pdf"
                ],
                3,
            ),
            "superposicion_porcentaje": round(
                analisis[
                    "proporcion_superpuesta"
                ] * 100,
                2,
            ),
            "diferencia_angular_grados": round(
                analisis[
                    "diferencia_angular_grados"
                ],
                3,
            ),
            "estado": "CANDIDATO",
        }

        eje_repetido = any(
            _ejes_practicamente_iguales(
                eje,
                eje_existente,
                tolerancia_ejes_duplicados,
            )
            for eje_existente
            in ejes_candidatos
        )

        if eje_repetido:
            cantidad_ejes_duplicados += 1
            continue

        eje["id_eje"] = (
            len(ejes_candidatos) + 1
        )

        ejes_candidatos.append(eje)

    bordes_sin_pareja = [
        borde
        for borde in bordes
        if borde["id_borde"]
        not in ids_bordes_utilizados
    ]

    diagnostico = {
        "cantidad_bordes_entrada": len(
            bordes
        ),
        "posibles_parejas": len(
            posibles_parejas
        ),
        "parejas_seleccionadas": (
            cantidad_parejas_seleccionadas
        ),
        "ejes_duplicados_descartados": (
            cantidad_ejes_duplicados
        ),
        "cantidad_ejes_candidatos": len(
            ejes_candidatos
        ),
        "cantidad_bordes_emparejados": len(
            ids_bordes_utilizados
        ),
        "cantidad_bordes_sin_pareja": len(
            bordes_sin_pareja
        ),
    }

    return (
        ejes_candidatos,
        bordes_sin_pareja,
        diagnostico,
    )


def dibujar_ejes_candidatos_vigas(
    ruta_pdf,
    ejes,
    bordes_sin_pareja,
    ruta_salida,
    escala=2.0,
):
    """Dibuja ejes azules y bordes sin pareja naranjas."""

    ruta_pdf = Path(ruta_pdf)
    ruta_salida = Path(ruta_salida)

    ruta_salida.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    documento = pymupdf.open(ruta_pdf)

    if len(documento) != 1:
        documento.close()

        raise ValueError(
            "El diagnóstico actual admite "
            "planos de una página."
        )

    pagina = documento[0]

    # Dibujar primero los bordes sin pareja.
    forma_sin_pareja = pagina.new_shape()

    for borde in bordes_sin_pareja:

        forma_sin_pareja.draw_line(
            pymupdf.Point(
                borde["x_inicial"],
                borde["y_inicial"],
            ),
            pymupdf.Point(
                borde["x_final"],
                borde["y_final"],
            ),
        )

    if bordes_sin_pareja:
        forma_sin_pareja.finish(
            color=(1, 0.55, 0),
            width=0.8,
        )

        forma_sin_pareja.commit(
            overlay=True
        )

    # Dibujar los ejes por encima, en azul.
    forma_ejes = pagina.new_shape()

    for eje in ejes:

        forma_ejes.draw_line(
            pymupdf.Point(
                eje["x_inicial"],
                eje["y_inicial"],
            ),
            pymupdf.Point(
                eje["x_final"],
                eje["y_final"],
            ),
        )

    if ejes:
        forma_ejes.finish(
            color=(0, 0, 1),
            width=1.2,
        )

        forma_ejes.commit(
            overlay=True
        )

    imagen = pagina.get_pixmap(
        matrix=pymupdf.Matrix(
            escala,
            escala,
        ),
        alpha=False,
    )

    imagen.save(ruta_salida)
    documento.close()


# ==========================================================
# RED ESTRUCTURAL: APOYOS Y TRAMOS ENTRE COLUMNAS
# ==========================================================


def _numero_tramo(valor, predeterminado=None):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return predeterminado


def _rectangulo_item_cerrado(item):
    """Devuelve el rectángulo de un ``Quad`` o ``Rect`` de PyMuPDF."""

    if not item:
        return None

    if item[0] == "qu":
        return item[1].rect

    if item[0] == "re":
        return item[1]

    return None


def _asignar_simbolos_a_rotulos(
    rotulos,
    simbolos,
    distancia_maxima,
):
    """Hace una asignación espacial uno a uno, sin reutilizar símbolos."""

    candidatos = []

    for indice_rotulo, rotulo in enumerate(rotulos):
        centro_x = _numero_tramo(
            rotulo.get("centro_x")
        )
        centro_y = _numero_tramo(
            rotulo.get("centro_y")
        )

        if centro_x is None or centro_y is None:
            continue

        for indice_simbolo, simbolo in enumerate(simbolos):
            distancia = hypot(
                centro_x - simbolo["centro_x"],
                centro_y - simbolo["centro_y"],
            )

            if distancia <= distancia_maxima:
                candidatos.append(
                    (
                        distancia,
                        indice_rotulo,
                        indice_simbolo,
                    )
                )

    candidatos.sort()

    rotulos_utilizados = set()
    simbolos_utilizados = set()
    asignaciones = []

    for (
        distancia,
        indice_rotulo,
        indice_simbolo,
    ) in candidatos:
        if (
            indice_rotulo in rotulos_utilizados
            or indice_simbolo in simbolos_utilizados
        ):
            continue

        rotulos_utilizados.add(indice_rotulo)
        simbolos_utilizados.add(indice_simbolo)
        asignaciones.append(
            {
                "indice_rotulo": indice_rotulo,
                "indice_simbolo": indice_simbolo,
                "distancia_pdf": distancia,
            }
        )

    return asignaciones


def detectar_apoyos_columnas_vectoriales(
    ruta_pdf,
    rotulos_columnas,
    *,
    distancia_maxima_rotulo_simbolo_pdf=None,
    proporcion_maxima_simbolo_pagina=0.10,
):
    """Localiza el centro gráfico de cada columna de la planta.

    El rótulo ``C...`` suele estar desplazado respecto del apoyo real. Por
    eso no se usa su centro como nodo estructural. Se buscan figuras
    vectoriales cerradas y se selecciona, en cada página, el estilo de línea
    que consigue la mejor asignación uno a uno con los rótulos detectados.

    No se codifica un espesor ni una referencia concreta del proyecto.
    """

    ruta_pdf = Path(ruta_pdf)

    if not ruta_pdf.is_file():
        raise FileNotFoundError(
            f"No se encontró el PDF: {ruta_pdf}"
        )

    rotulos_por_pagina = defaultdict(list)

    for rotulo in rotulos_columnas:
        pagina = int(
            _numero_tramo(
                rotulo.get("pagina"),
                1,
            )
        )
        rotulos_por_pagina[pagina].append(
            dict(rotulo)
        )

    documento = pymupdf.open(ruta_pdf)
    apoyos_temporales = []
    rotulos_sin_simbolo = []
    diagnosticos_paginas = []

    for numero_pagina, pagina in enumerate(
        documento,
        start=1,
    ):
        rotulos = rotulos_por_pagina.get(
            numero_pagina,
            [],
        )

        if not rotulos:
            continue

        tamanios_rotulos = [
            max(
                abs(
                    _numero_tramo(rotulo.get("x1"), 0.0)
                    - _numero_tramo(rotulo.get("x0"), 0.0)
                ),
                abs(
                    _numero_tramo(rotulo.get("y1"), 0.0)
                    - _numero_tramo(rotulo.get("y0"), 0.0)
                ),
            )
            for rotulo in rotulos
        ]

        distancia_maxima = (
            distancia_maxima_rotulo_simbolo_pdf
            if distancia_maxima_rotulo_simbolo_pdf
            is not None
            else max(
                15.0,
                median(tamanios_rotulos) * 4.0,
            )
        )

        tamano_maximo = (
            min(
                pagina.rect.width,
                pagina.rect.height,
            )
            * proporcion_maxima_simbolo_pagina
        )

        simbolos_por_espesor = defaultdict(list)
        claves_simbolos = set()

        for indice_dibujo, dibujo in enumerate(
            pagina.get_drawings()
        ):
            espesor = round(
                float(dibujo.get("width") or 0.0),
                2,
            )

            for indice_item, item in enumerate(
                dibujo.get("items", [])
            ):
                rectangulo = _rectangulo_item_cerrado(
                    item
                )

                if rectangulo is None:
                    continue

                ancho = abs(rectangulo.width)
                alto = abs(rectangulo.height)

                if (
                    min(ancho, alto) < 0.20
                    or max(ancho, alto) > tamano_maximo
                ):
                    continue

                relacion_lados = ancho / alto

                if not 0.15 <= relacion_lados <= 6.50:
                    continue

                clave = (
                    numero_pagina,
                    round(rectangulo.x0, 2),
                    round(rectangulo.y0, 2),
                    round(rectangulo.x1, 2),
                    round(rectangulo.y1, 2),
                    espesor,
                )

                if clave in claves_simbolos:
                    continue

                claves_simbolos.add(clave)
                simbolos_por_espesor[espesor].append(
                    {
                        "pagina": numero_pagina,
                        "indice_dibujo": indice_dibujo,
                        "indice_item": indice_item,
                        "tipo_item": item[0],
                        "espesor_pdf": espesor,
                        "x0": float(rectangulo.x0),
                        "y0": float(rectangulo.y0),
                        "x1": float(rectangulo.x1),
                        "y1": float(rectangulo.y1),
                        "centro_x": (
                            rectangulo.x0 + rectangulo.x1
                        ) / 2,
                        "centro_y": (
                            rectangulo.y0 + rectangulo.y1
                        ) / 2,
                        "ancho_pdf": ancho,
                        "alto_pdf": alto,
                    }
                )

        evaluaciones = []

        for espesor, simbolos in (
            simbolos_por_espesor.items()
        ):
            asignaciones = _asignar_simbolos_a_rotulos(
                rotulos,
                simbolos,
                distancia_maxima,
            )

            distancias = [
                asignacion["distancia_pdf"]
                for asignacion in asignaciones
            ]

            evaluaciones.append(
                {
                    "espesor_pdf": espesor,
                    "simbolos": simbolos,
                    "asignaciones": asignaciones,
                    "cantidad_asignaciones": len(
                        asignaciones
                    ),
                    "distancia_mediana": (
                        median(distancias)
                        if distancias
                        else float("inf")
                    ),
                }
            )

        evaluaciones.sort(
            key=lambda evaluacion: (
                -evaluacion["cantidad_asignaciones"],
                evaluacion["distancia_mediana"],
                abs(
                    len(evaluacion["simbolos"])
                    - len(rotulos)
                ),
            )
        )

        mejor = evaluaciones[0] if evaluaciones else None
        indices_rotulos_asignados = set()

        if mejor is not None:
            for asignacion in mejor["asignaciones"]:
                rotulo = rotulos[
                    asignacion["indice_rotulo"]
                ]
                simbolo = mejor["simbolos"][
                    asignacion["indice_simbolo"]
                ]

                indices_rotulos_asignados.add(
                    asignacion["indice_rotulo"]
                )

                apoyos_temporales.append(
                    {
                        **simbolo,
                        "referencia": str(
                            rotulo.get("referencia", "")
                        ).strip().upper(),
                        "referencia_original": rotulo.get(
                            "referencia_original",
                            rotulo.get("referencia"),
                        ),
                        "texto_original": rotulo.get(
                            "texto_original"
                        ),
                        "centro_rotulo_x": _numero_tramo(
                            rotulo.get("centro_x")
                        ),
                        "centro_rotulo_y": _numero_tramo(
                            rotulo.get("centro_y")
                        ),
                        "distancia_rotulo_simbolo_pdf": round(
                            asignacion["distancia_pdf"],
                            3,
                        ),
                        "metodo_deteccion": (
                            "figura_vectorial_cerrada_asociada_"
                            "uno_a_uno_con_rotulo"
                        ),
                    }
                )

        for indice_rotulo, rotulo in enumerate(rotulos):
            if indice_rotulo not in indices_rotulos_asignados:
                rotulos_sin_simbolo.append(
                    dict(rotulo)
                )

        diagnosticos_paginas.append(
            {
                "pagina": numero_pagina,
                "rotulos_columnas": len(rotulos),
                "grupos_estilo_evaluados": len(
                    evaluaciones
                ),
                "espesor_simbolo_seleccionado_pdf": (
                    mejor["espesor_pdf"]
                    if mejor
                    else None
                ),
                "simbolos_estilo_seleccionado": (
                    len(mejor["simbolos"])
                    if mejor
                    else 0
                ),
                "apoyos_asignados": (
                    mejor["cantidad_asignaciones"]
                    if mejor
                    else 0
                ),
                "distancia_maxima_rotulo_simbolo_pdf": (
                    round(distancia_maxima, 3)
                ),
            }
        )

    documento.close()

    apoyos_temporales.sort(
        key=lambda apoyo: (
            apoyo["pagina"],
            apoyo["centro_y"],
            apoyo["centro_x"],
        )
    )

    apariciones = Counter()
    apoyos = []

    for apoyo in apoyos_temporales:
        referencia = apoyo["referencia"] or "COLUMNA"
        apariciones[referencia] += 1

        apoyos.append(
            {
                **apoyo,
                "apoyo_id": (
                    f"{referencia}-"
                    f"{apariciones[referencia]:02d}"
                ),
                "rectangulo_pdf": {
                    "x0": round(apoyo["x0"], 3),
                    "y0": round(apoyo["y0"], 3),
                    "x1": round(apoyo["x1"], 3),
                    "y1": round(apoyo["y1"], 3),
                },
                "centro_x": round(
                    apoyo["centro_x"],
                    3,
                ),
                "centro_y": round(
                    apoyo["centro_y"],
                    3,
                ),
                "ancho_pdf": round(
                    apoyo["ancho_pdf"],
                    3,
                ),
                "alto_pdf": round(
                    apoyo["alto_pdf"],
                    3,
                ),
                "estado": "apoyo_vectorial_confirmado",
            }
        )

    diagnostico = {
        "archivo": ruta_pdf.name,
        "rotulos_columnas_entrada": len(
            rotulos_columnas
        ),
        "apoyos_vectoriales_detectados": len(apoyos),
        "rotulos_sin_simbolo_vectorial": len(
            rotulos_sin_simbolo
        ),
        "cobertura_rotulos_columnas_porcentaje": round(
            (
                len(apoyos)
                / len(rotulos_columnas)
                * 100
            )
            if rotulos_columnas
            else 0.0,
            2,
        ),
        "paginas": diagnosticos_paginas,
        "metodo": (
            "selección automática del estilo vectorial y "
            "asignación espacial uno a uno"
        ),
    }

    return {
        "apoyos": apoyos,
        "rotulos_sin_simbolo": rotulos_sin_simbolo,
        "diagnostico": diagnostico,
    }


def _extraer_segmentos_rectos_para_red(
    ruta_pdf,
    longitud_minima_pdf=3.0,
):
    segmentos_por_pagina = defaultdict(list)

    documento = pymupdf.open(Path(ruta_pdf))

    for numero_pagina, pagina in enumerate(
        documento,
        start=1,
    ):
        for dibujo in pagina.get_drawings():
            espesor = float(
                dibujo.get("width") or 0.0
            )

            for item in dibujo.get("items", []):
                if item[0] != "l":
                    continue

                punto_inicial = item[1]
                punto_final = item[2]
                longitud = hypot(
                    punto_final.x - punto_inicial.x,
                    punto_final.y - punto_inicial.y,
                )

                if longitud < longitud_minima_pdf:
                    continue

                segmentos_por_pagina[numero_pagina].append(
                    {
                        "x_inicial": float(punto_inicial.x),
                        "y_inicial": float(punto_inicial.y),
                        "x_final": float(punto_final.x),
                        "y_final": float(punto_final.y),
                        "longitud_pdf": longitud,
                        "espesor_pdf": espesor,
                    }
                )

    documento.close()

    return segmentos_por_pagina


def _distancia_punto_a_segmento_red(
    punto_x,
    punto_y,
    apoyo_inicial,
    apoyo_final,
):
    diferencia_x = (
        apoyo_final["centro_x"]
        - apoyo_inicial["centro_x"]
    )
    diferencia_y = (
        apoyo_final["centro_y"]
        - apoyo_inicial["centro_y"]
    )
    longitud_cuadrada = (
        diferencia_x * diferencia_x
        + diferencia_y * diferencia_y
    )

    if longitud_cuadrada <= 0:
        return None

    proyeccion = (
        (
            punto_x - apoyo_inicial["centro_x"]
        ) * diferencia_x
        + (
            punto_y - apoyo_inicial["centro_y"]
        ) * diferencia_y
    ) / longitud_cuadrada

    proyeccion_limitada = max(
        0.0,
        min(1.0, proyeccion),
    )
    cercano_x = (
        apoyo_inicial["centro_x"]
        + proyeccion_limitada * diferencia_x
    )
    cercano_y = (
        apoyo_inicial["centro_y"]
        + proyeccion_limitada * diferencia_y
    )

    return {
        "distancia_pdf": hypot(
            punto_x - cercano_x,
            punto_y - cercano_y,
        ),
        "proyeccion": proyeccion,
    }


def _diferencia_angular_red(angulo_1, angulo_2):
    diferencia = abs(angulo_1 - angulo_2) % 180
    return min(diferencia, 180 - diferencia)


def _cobertura_intervalos(intervalos, longitud, tolerancia_union):
    if longitud <= 0 or not intervalos:
        return 0.0

    combinados = []

    for inicio, final in sorted(intervalos):
        if (
            not combinados
            or inicio
            > combinados[-1][1] + tolerancia_union
        ):
            combinados.append([inicio, final])
        else:
            combinados[-1][1] = max(
                combinados[-1][1],
                final,
            )

    cubierto = sum(
        final - inicio
        for inicio, final in combinados
    )

    return min(1.0, cubierto / longitud)


def _medir_evidencia_vectorial_tramo(
    apoyo_inicial,
    apoyo_final,
    segmentos,
    *,
    corredor_pdf,
    diferencia_angular_maxima,
    cobertura_minima,
    tolerancia_union,
    separacion_minima_del_eje,
):
    diferencia_x = (
        apoyo_final["centro_x"]
        - apoyo_inicial["centro_x"]
    )
    diferencia_y = (
        apoyo_final["centro_y"]
        - apoyo_inicial["centro_y"]
    )
    longitud = hypot(diferencia_x, diferencia_y)

    if longitud <= 0:
        return None

    direccion_x = diferencia_x / longitud
    direccion_y = diferencia_y / longitud
    normal_x = -direccion_y
    normal_y = direccion_x
    angulo_tramo = degrees(
        atan2(direccion_y, direccion_x)
    ) % 180
    intervalos_positivos = []
    intervalos_negativos = []
    espesores = set()

    for segmento in segmentos:
        segmento_x = (
            segmento["x_final"]
            - segmento["x_inicial"]
        )
        segmento_y = (
            segmento["y_final"]
            - segmento["y_inicial"]
        )
        longitud_segmento = hypot(
            segmento_x,
            segmento_y,
        )

        if longitud_segmento <= 0:
            continue

        angulo_segmento = degrees(
            atan2(segmento_y, segmento_x)
        ) % 180

        if (
            _diferencia_angular_red(
                angulo_tramo,
                angulo_segmento,
            )
            > diferencia_angular_maxima
        ):
            continue

        desplazamiento_inicial_x = (
            segmento["x_inicial"]
            - apoyo_inicial["centro_x"]
        )
        desplazamiento_inicial_y = (
            segmento["y_inicial"]
            - apoyo_inicial["centro_y"]
        )
        desplazamiento_final_x = (
            segmento["x_final"]
            - apoyo_inicial["centro_x"]
        )
        desplazamiento_final_y = (
            segmento["y_final"]
            - apoyo_inicial["centro_y"]
        )

        normal_inicial = (
            desplazamiento_inicial_x * normal_x
            + desplazamiento_inicial_y * normal_y
        )
        normal_final = (
            desplazamiento_final_x * normal_x
            + desplazamiento_final_y * normal_y
        )
        normal_media = (
            normal_inicial + normal_final
        ) / 2

        if (
            max(
                abs(normal_inicial),
                abs(normal_final),
            )
            > corredor_pdf
            or abs(normal_media)
            < separacion_minima_del_eje
        ):
            continue

        proyeccion_inicial = (
            desplazamiento_inicial_x * direccion_x
            + desplazamiento_inicial_y * direccion_y
        )
        proyeccion_final = (
            desplazamiento_final_x * direccion_x
            + desplazamiento_final_y * direccion_y
        )
        inicio = max(
            0.0,
            min(
                proyeccion_inicial,
                proyeccion_final,
            ),
        )
        final = min(
            longitud,
            max(
                proyeccion_inicial,
                proyeccion_final,
            ),
        )

        if final - inicio < 1.0:
            continue

        destino = (
            intervalos_positivos
            if normal_media > 0
            else intervalos_negativos
        )
        destino.append((inicio, final))
        espesores.add(
            round(segmento["espesor_pdf"], 3)
        )

    cobertura_positiva = _cobertura_intervalos(
        intervalos_positivos,
        longitud,
        tolerancia_union,
    )
    cobertura_negativa = _cobertura_intervalos(
        intervalos_negativos,
        longitud,
        tolerancia_union,
    )
    cobertura_total = _cobertura_intervalos(
        [
            *intervalos_positivos,
            *intervalos_negativos,
        ],
        longitud,
        tolerancia_union,
    )

    if (
        cobertura_positiva >= cobertura_minima
        and cobertura_negativa >= cobertura_minima
    ):
        tipo = "doble_borde"
        confianza = "alta"
    elif cobertura_total >= cobertura_minima:
        tipo = "borde_simple"
        confianza = "media"
    else:
        tipo = "sin_evidencia_suficiente"
        confianza = "baja"

    return {
        "tipo": tipo,
        "confianza": confianza,
        "cobertura_positiva": round(
            cobertura_positiva,
            4,
        ),
        "cobertura_negativa": round(
            cobertura_negativa,
            4,
        ),
        "cobertura_total": round(
            cobertura_total,
            4,
        ),
        "espesores_vectoriales_pdf": sorted(espesores),
    }


def _orientacion_rotulo_red(rotulo):
    ancho = abs(
        _numero_tramo(rotulo.get("x1"), 0.0)
        - _numero_tramo(rotulo.get("x0"), 0.0)
    )
    alto = abs(
        _numero_tramo(rotulo.get("y1"), 0.0)
        - _numero_tramo(rotulo.get("y0"), 0.0)
    )

    if ancho >= alto * 1.25:
        return "horizontal"

    if alto >= ancho * 1.25:
        return "vertical"

    return "inclinada"


def _error_orientacion_rotulo_tramo(
    orientacion,
    angulo,
):
    if orientacion == "inclinada":
        return 0.0

    if orientacion == "horizontal":
        return min(angulo, 180 - angulo)

    return abs(angulo - 90)


def _dimension_apoyo_sobre_direccion(
    apoyo,
    direccion_x,
    direccion_y,
):
    """Proyecta el rectángulo del apoyo sobre el eje del tramo."""

    return (
        abs(direccion_x) * apoyo["ancho_pdf"]
        + abs(direccion_y) * apoyo["alto_pdf"]
    )


def _crear_tramo_desde_arista(
    arista,
    rotulo,
    *,
    metodo_asignacion,
    estado,
):
    apoyo_inicial = arista["apoyo_inicial"]
    apoyo_final = arista["apoyo_final"]
    diferencia_x = (
        apoyo_final["centro_x"]
        - apoyo_inicial["centro_x"]
    )
    diferencia_y = (
        apoyo_final["centro_y"]
        - apoyo_inicial["centro_y"]
    )
    longitud_entre_ejes = hypot(
        diferencia_x,
        diferencia_y,
    )
    direccion_x = diferencia_x / longitud_entre_ejes
    direccion_y = diferencia_y / longitud_entre_ejes
    descuento_inicial = (
        _dimension_apoyo_sobre_direccion(
            apoyo_inicial,
            direccion_x,
            direccion_y,
        )
        / 2
    )
    descuento_final = (
        _dimension_apoyo_sobre_direccion(
            apoyo_final,
            direccion_x,
            direccion_y,
        )
        / 2
    )
    longitud_libre = max(
        0.0,
        longitud_entre_ejes
        - descuento_inicial
        - descuento_final,
    )

    return {
        "pagina": apoyo_inicial["pagina"],
        "referencia": str(
            rotulo.get("referencia", "")
        ).strip().upper(),
        "texto_original": rotulo.get(
            "texto_original"
        ),
        "ancho_m": _numero_tramo(
            rotulo.get("ancho_m")
        ),
        "alto_m": _numero_tramo(
            rotulo.get("alto_m")
        ),
        "apoyo_inicial_id": apoyo_inicial["apoyo_id"],
        "referencia_apoyo_inicial": apoyo_inicial[
            "referencia"
        ],
        "apoyo_final_id": apoyo_final["apoyo_id"],
        "referencia_apoyo_final": apoyo_final[
            "referencia"
        ],
        "punto_inicial_pdf": {
            "x": apoyo_inicial["centro_x"],
            "y": apoyo_inicial["centro_y"],
        },
        "punto_final_pdf": {
            "x": apoyo_final["centro_x"],
            "y": apoyo_final["centro_y"],
        },
        "longitud_entre_ejes_pdf": round(
            longitud_entre_ejes,
            3,
        ),
        "longitud_libre_entre_caras_pdf": round(
            longitud_libre,
            3,
        ),
        "angulo_pdf_grados": round(
            arista["angulo_pdf_grados"],
            3,
        ),
        "centro_x": round(
            (
                apoyo_inicial["centro_x"]
                + apoyo_final["centro_x"]
            )
            / 2,
            3,
        ),
        "centro_y": round(
            (
                apoyo_inicial["centro_y"]
                + apoyo_final["centro_y"]
            )
            / 2,
            3,
        ),
        "distancia_rotulo_tramo_pdf": arista.get(
            "distancia_rotulo_tramo_pdf"
        ),
        "proyeccion_rotulo_sobre_tramo": arista.get(
            "proyeccion_rotulo_sobre_tramo"
        ),
        "evidencia_vectorial": arista[
            "evidencia_vectorial"
        ],
        "metodo_deteccion": (
            "dos_apoyos_vectoriales_con_evidencia_de_viga"
        ),
        "metodo_asignacion_referencia": metodo_asignacion,
        "confianza_geometria": arista[
            "evidencia_vectorial"
        ]["confianza"],
        "requiere_revision": estado
        not in {
            "confirmado_por_rotulo",
            "confirmado_por_continuidad",
        },
        "estado": estado,
    }


def reconstruir_tramos_vigas_entre_apoyos(
    ruta_pdf,
    apoyos,
    rotulos_vigas,
    *,
    cobertura_vectorial_minima=0.55,
    diferencia_angular_vector_maxima=4.0,
    diferencia_angular_rotulo_maxima=25.0,
    margen_proyeccion_rotulo=0.15,
    factor_corredor_apoyo_intermedio=2.20,
    factor_corredor_evidencia=2.80,
):
    """Reconstruye una viga como aristas consecutivas entre apoyos.

    Una línea larga que atraviesa una columna se divide en ese apoyo. Los
    rótulos se usan para asignar referencia y sección, no para definir la
    longitud. Esto permite que ``VR1`` tenga tantos tramos como pares de
    columnas conectados en la planta.
    """

    apoyos_por_pagina = defaultdict(list)

    for apoyo in apoyos:
        apoyos_por_pagina[apoyo["pagina"]].append(
            apoyo
        )

    segmentos_por_pagina = (
        _extraer_segmentos_rectos_para_red(
            ruta_pdf
        )
    )

    aristas = []
    pares_evaluados = 0
    parametros_por_pagina = []

    for pagina, apoyos_pagina in (
        apoyos_por_pagina.items()
    ):
        if len(apoyos_pagina) < 2:
            continue

        tamano_mediano = median(
            max(
                apoyo["ancho_pdf"],
                apoyo["alto_pdf"],
            )
            for apoyo in apoyos_pagina
        )
        corredor_apoyo_intermedio = max(
            2.0,
            tamano_mediano
            * factor_corredor_apoyo_intermedio,
        )
        corredor_evidencia = max(
            4.0,
            tamano_mediano * factor_corredor_evidencia,
        )
        tolerancia_union = max(
            0.75,
            tamano_mediano * 0.20,
        )
        separacion_minima_eje = max(
            0.20,
            tamano_mediano * 0.03,
        )

        parametros_por_pagina.append(
            {
                "pagina": pagina,
                "tamano_mediano_apoyo_pdf": round(
                    tamano_mediano,
                    3,
                ),
                "corredor_apoyo_intermedio_pdf": round(
                    corredor_apoyo_intermedio,
                    3,
                ),
                "corredor_evidencia_pdf": round(
                    corredor_evidencia,
                    3,
                ),
            }
        )

        for indice, apoyo_inicial in enumerate(
            apoyos_pagina
        ):
            for apoyo_final in apoyos_pagina[
                indice + 1:
            ]:
                pares_evaluados += 1
                diferencia_x = (
                    apoyo_final["centro_x"]
                    - apoyo_inicial["centro_x"]
                )
                diferencia_y = (
                    apoyo_final["centro_y"]
                    - apoyo_inicial["centro_y"]
                )
                longitud = hypot(
                    diferencia_x,
                    diferencia_y,
                )

                if longitud <= tamano_mediano:
                    continue

                existe_apoyo_intermedio = False

                for otro_apoyo in apoyos_pagina:
                    if otro_apoyo is apoyo_inicial:
                        continue

                    if otro_apoyo is apoyo_final:
                        continue

                    medicion = (
                        _distancia_punto_a_segmento_red(
                            otro_apoyo["centro_x"],
                            otro_apoyo["centro_y"],
                            apoyo_inicial,
                            apoyo_final,
                        )
                    )

                    if (
                        medicion is not None
                        and 0.03
                        < medicion["proyeccion"]
                        < 0.97
                        and medicion["distancia_pdf"]
                        <= corredor_apoyo_intermedio
                    ):
                        existe_apoyo_intermedio = True
                        break

                if existe_apoyo_intermedio:
                    continue

                evidencia = (
                    _medir_evidencia_vectorial_tramo(
                        apoyo_inicial,
                        apoyo_final,
                        segmentos_por_pagina.get(
                            pagina,
                            [],
                        ),
                        corredor_pdf=corredor_evidencia,
                        diferencia_angular_maxima=(
                            diferencia_angular_vector_maxima
                        ),
                        cobertura_minima=(
                            cobertura_vectorial_minima
                        ),
                        tolerancia_union=tolerancia_union,
                        separacion_minima_del_eje=(
                            separacion_minima_eje
                        ),
                    )
                )

                if (
                    evidencia is None
                    or evidencia["tipo"]
                    == "sin_evidencia_suficiente"
                ):
                    continue

                angulo = degrees(
                    atan2(
                        diferencia_y,
                        diferencia_x,
                    )
                ) % 180

                aristas.append(
                    {
                        "pagina": pagina,
                        "apoyo_inicial": apoyo_inicial,
                        "apoyo_final": apoyo_final,
                        "longitud_pdf": longitud,
                        "angulo_pdf_grados": angulo,
                        "evidencia_vectorial": evidencia,
                    }
                )

    candidatos_asignacion = []

    for indice_rotulo, rotulo in enumerate(rotulos_vigas):
        centro_x = _numero_tramo(
            rotulo.get("centro_x")
        )
        centro_y = _numero_tramo(
            rotulo.get("centro_y")
        )

        if centro_x is None or centro_y is None:
            continue

        pagina = int(
            _numero_tramo(
                rotulo.get("pagina"),
                1,
            )
        )
        apoyos_pagina = apoyos_por_pagina.get(
            pagina,
            [],
        )

        if not apoyos_pagina:
            continue

        tamano_mediano = median(
            max(
                apoyo["ancho_pdf"],
                apoyo["alto_pdf"],
            )
            for apoyo in apoyos_pagina
        )
        distancia_maxima_rotulo = max(
            10.0,
            tamano_mediano * 3.0,
        )
        orientacion = _orientacion_rotulo_red(
            rotulo
        )

        for indice_arista, arista in enumerate(aristas):
            if arista["pagina"] != pagina:
                continue

            error_angular = (
                _error_orientacion_rotulo_tramo(
                    orientacion,
                    arista["angulo_pdf_grados"],
                )
            )

            if (
                error_angular
                > diferencia_angular_rotulo_maxima
            ):
                continue

            medicion = _distancia_punto_a_segmento_red(
                centro_x,
                centro_y,
                arista["apoyo_inicial"],
                arista["apoyo_final"],
            )

            if medicion is None:
                continue

            if (
                medicion["distancia_pdf"]
                > distancia_maxima_rotulo
                or medicion["proyeccion"]
                < -margen_proyeccion_rotulo
                or medicion["proyeccion"]
                > 1 + margen_proyeccion_rotulo
            ):
                continue

            penalizacion_evidencia = (
                0.0
                if arista["evidencia_vectorial"]["tipo"]
                == "doble_borde"
                else 2.0
            )
            puntaje = (
                medicion["distancia_pdf"]
                + abs(
                    medicion["proyeccion"] - 0.5
                )
                * max(2.0, tamano_mediano * 0.60)
                + error_angular * 0.15
                + penalizacion_evidencia
            )

            candidatos_asignacion.append(
                {
                    "puntaje": puntaje,
                    "indice_rotulo": indice_rotulo,
                    "indice_arista": indice_arista,
                    "distancia_pdf": medicion[
                        "distancia_pdf"
                    ],
                    "proyeccion": medicion["proyeccion"],
                }
            )

    candidatos_asignacion.sort(
        key=lambda candidato: (
            candidato["puntaje"],
            candidato["distancia_pdf"],
        )
    )

    rotulos_utilizados = set()
    aristas_utilizadas = set()
    tramos = []

    for candidato in candidatos_asignacion:
        indice_rotulo = candidato["indice_rotulo"]
        indice_arista = candidato["indice_arista"]

        if (
            indice_rotulo in rotulos_utilizados
            or indice_arista in aristas_utilizadas
        ):
            continue

        rotulos_utilizados.add(indice_rotulo)
        aristas_utilizadas.add(indice_arista)
        arista = dict(aristas[indice_arista])
        arista["distancia_rotulo_tramo_pdf"] = round(
            candidato["distancia_pdf"],
            3,
        )
        arista["proyeccion_rotulo_sobre_tramo"] = round(
            candidato["proyeccion"],
            4,
        )
        tramos.append(
            _crear_tramo_desde_arista(
                arista,
                rotulos_vigas[indice_rotulo],
                metodo_asignacion=(
                    "rotulo_mas_cercano_al_segmento_"
                    "entre_apoyos"
                ),
                estado="confirmado_por_rotulo",
            )
        )

    # Un plano puede rotular una viga continua una sola vez. Solo se
    # propaga la sección cuando la arista sin rótulo queda entre dos tramos
    # colineales que ya tienen exactamente la misma referencia y sección.
    propagados = 0
    cambio = True

    while cambio:
        cambio = False

        for indice_arista, arista in enumerate(aristas):
            if indice_arista in aristas_utilizadas:
                continue

            extremos = {
                arista["apoyo_inicial"]["apoyo_id"],
                arista["apoyo_final"]["apoyo_id"],
            }
            vecinos = []

            for tramo in tramos:
                extremos_tramo = {
                    tramo["apoyo_inicial_id"],
                    tramo["apoyo_final_id"],
                }

                if not extremos.intersection(extremos_tramo):
                    continue

                if (
                    _diferencia_angular_red(
                        arista["angulo_pdf_grados"],
                        tramo["angulo_pdf_grados"],
                    )
                    > 5.0
                ):
                    continue

                vecinos.append(tramo)

            firmas = {
                (
                    tramo["referencia"],
                    tramo["ancho_m"],
                    tramo["alto_m"],
                )
                for tramo in vecinos
            }

            if len(vecinos) < 2 or len(firmas) != 1:
                continue

            referencia, ancho_m, alto_m = next(
                iter(firmas)
            )
            rotulo_propagado = {
                "referencia": referencia,
                "texto_original": (
                    "Sección propagada por continuidad "
                    "entre apoyos"
                ),
                "ancho_m": ancho_m,
                "alto_m": alto_m,
            }
            tramos.append(
                _crear_tramo_desde_arista(
                    arista,
                    rotulo_propagado,
                    metodo_asignacion=(
                        "propagacion_entre_dos_tramos_"
                        "colineales_iguales"
                    ),
                    estado="confirmado_por_continuidad",
                )
            )
            aristas_utilizadas.add(indice_arista)
            propagados += 1
            cambio = True

    tramos.sort(
        key=lambda tramo: (
            tramo["pagina"],
            tramo["centro_y"],
            tramo["centro_x"],
            tramo["referencia"],
        )
    )

    apariciones = Counter()

    for tramo in tramos:
        referencia = tramo["referencia"] or "VR"
        apariciones[referencia] += 1
        tramo["tramo_id"] = (
            f"{referencia}-"
            f"{apariciones[referencia]:02d}"
        )

    rotulos_sin_tramo = [
        dict(rotulo)
        for indice, rotulo in enumerate(rotulos_vigas)
        if indice not in rotulos_utilizados
    ]
    aristas_sin_referencia = [
        {
            "pagina": arista["pagina"],
            "apoyo_inicial_id": arista[
                "apoyo_inicial"
            ]["apoyo_id"],
            "apoyo_final_id": arista[
                "apoyo_final"
            ]["apoyo_id"],
            "longitud_pdf": round(
                arista["longitud_pdf"],
                3,
            ),
            "angulo_pdf_grados": round(
                arista["angulo_pdf_grados"],
                3,
            ),
            "evidencia_vectorial": arista[
                "evidencia_vectorial"
            ],
            "estado": "sin_referencia_de_viga",
        }
        for indice, arista in enumerate(aristas)
        if indice not in aristas_utilizadas
    ]

    asignados_directamente = len(rotulos_utilizados)
    diagnostico = {
        "apoyos_entrada": len(apoyos),
        "pares_de_apoyos_evaluados": pares_evaluados,
        "aristas_con_evidencia_vectorial": len(aristas),
        "aristas_con_doble_borde": sum(
            arista["evidencia_vectorial"]["tipo"]
            == "doble_borde"
            for arista in aristas
        ),
        "aristas_con_borde_simple": sum(
            arista["evidencia_vectorial"]["tipo"]
            == "borde_simple"
            for arista in aristas
        ),
        "rotulos_vigas_entrada": len(rotulos_vigas),
        "rotulos_asignados_a_tramos": (
            asignados_directamente
        ),
        "rotulos_sin_tramo": len(rotulos_sin_tramo),
        "tramos_propagados_por_continuidad": propagados,
        "tramos_reconstruidos": len(tramos),
        "aristas_sin_referencia": len(
            aristas_sin_referencia
        ),
        "cobertura_rotulos_vigas_porcentaje": round(
            (
                asignados_directamente
                / len(rotulos_vigas)
                * 100
            )
            if rotulos_vigas
            else 0.0,
            2,
        ),
        "parametros_por_pagina": parametros_por_pagina,
        "criterio_segmentacion": (
            "cada arista termina en el siguiente apoyo; un apoyo "
            "intermedio divide siempre el tramo"
        ),
        "resultado_completo": (
            bool(tramos)
            and not rotulos_sin_tramo
        ),
    }

    return {
        "tramos": tramos,
        "rotulos_sin_tramo": rotulos_sin_tramo,
        "aristas_sin_referencia": aristas_sin_referencia,
        "diagnostico": diagnostico,
    }


def dibujar_red_vigas_entre_apoyos(
    ruta_pdf,
    apoyos,
    tramos,
    ruta_salida,
    escala=2.0,
):
    """Dibuja la red final: nodos cian y un eje por tramo en azul."""

    documento = pymupdf.open(Path(ruta_pdf))

    for numero_pagina, pagina in enumerate(
        documento,
        start=1,
    ):
        forma_tramos = pagina.new_shape()
        tramos_pagina = [
            tramo
            for tramo in tramos
            if tramo["pagina"] == numero_pagina
        ]

        for tramo in tramos_pagina:
            forma_tramos.draw_line(
                pymupdf.Point(
                    tramo["punto_inicial_pdf"]["x"],
                    tramo["punto_inicial_pdf"]["y"],
                ),
                pymupdf.Point(
                    tramo["punto_final_pdf"]["x"],
                    tramo["punto_final_pdf"]["y"],
                ),
            )

        if tramos_pagina:
            forma_tramos.finish(
                color=(0, 0.20, 1),
                width=1.10,
            )
            forma_tramos.commit(overlay=True)

        forma_apoyos = pagina.new_shape()
        apoyos_pagina = [
            apoyo
            for apoyo in apoyos
            if apoyo["pagina"] == numero_pagina
        ]

        for apoyo in apoyos_pagina:
            forma_apoyos.draw_circle(
                pymupdf.Point(
                    apoyo["centro_x"],
                    apoyo["centro_y"],
                ),
                1.60,
            )

        if apoyos_pagina:
            forma_apoyos.finish(
                color=(0, 0.80, 0.80),
                fill=(0, 0.80, 0.80),
                width=0.40,
            )
            forma_apoyos.commit(overlay=True)

    ruta_salida = Path(ruta_salida)
    ruta_salida.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if len(documento) == 1:
        documento[0].get_pixmap(
            matrix=pymupdf.Matrix(escala, escala),
            alpha=False,
        ).save(ruta_salida)
    else:
        for indice, pagina in enumerate(documento, start=1):
            salida_pagina = ruta_salida.with_name(
                f"{ruta_salida.stem}_pagina_{indice}"
                f"{ruta_salida.suffix}"
            )
            pagina.get_pixmap(
                matrix=pymupdf.Matrix(escala, escala),
                alpha=False,
            ).save(salida_pagina)

    documento.close()

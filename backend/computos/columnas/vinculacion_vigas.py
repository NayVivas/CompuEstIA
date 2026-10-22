"""Vinculación geométrica entre columnas y vigas rotuladas."""

from math import hypot


def _numero(valor):
    if valor is None:
        return None

    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _coordenadas_posicion(
    elemento: dict,
    campo: str,
):
    posicion = elemento.get(
        campo
    )

    if not isinstance(
        posicion,
        dict,
    ):
        return None

    x = _numero(
        posicion.get("x")
    )

    y = _numero(
        posicion.get("y")
    )

    if x is None or y is None:
        return None

    return x, y


def _coordenadas_rotulo_viga(
    rotulo: dict,
):
    x = _numero(
        rotulo.get("centro_x")
    )

    y = _numero(
        rotulo.get("centro_y")
    )

    if x is None or y is None:
        return None

    return x, y


def _distancia_punto_segmento(
    punto,
    inicio,
    fin,
):
    """
    Calcula la distancia de un punto a un segmento.

    También devuelve la posición proyectada:

        0.0 = inicio
        1.0 = fin
    """

    punto_x, punto_y = punto
    inicio_x, inicio_y = inicio
    fin_x, fin_y = fin

    vector_x = fin_x - inicio_x
    vector_y = fin_y - inicio_y

    longitud_cuadrada = (
        vector_x * vector_x
        + vector_y * vector_y
    )

    if longitud_cuadrada == 0:
        return None

    proyeccion = (
        (
            (punto_x - inicio_x)
            * vector_x
        )
        + (
            (punto_y - inicio_y)
            * vector_y
        )
    ) / longitud_cuadrada

    proyeccion_limitada = max(
        0.0,
        min(
            1.0,
            proyeccion,
        ),
    )

    punto_proyectado_x = (
        inicio_x
        + proyeccion_limitada
        * vector_x
    )

    punto_proyectado_y = (
        inicio_y
        + proyeccion_limitada
        * vector_y
    )

    distancia = hypot(
        punto_x
        - punto_proyectado_x,
        punto_y
        - punto_proyectado_y,
    )

    return distancia, proyeccion


def vincular_columnas_pendientes_con_vigas(
    *,
    columnas_pendientes: list[dict],
    columnas_directas: list[dict],
    rotulos_vigas: list[dict],
    distancia_maxima_pdf: float = 12.0,
    margen_proyeccion: float = 0.25,
    diferencia_minima_segundo_candidato: float = 2.0,
):
    """
    Busca un rótulo de viga próximo al segmento formado por:

        columna directa -> columna pendiente

    No confirma todavía los bordes vectoriales de la viga.
    """

    if distancia_maxima_pdf <= 0:
        raise ValueError(
            "La distancia máxima debe ser positiva."
        )

    directas_por_fundacion = {}

    for columna in columnas_directas:
        fundacion_id = columna.get(
            "fundacion_id"
        )

        if (
            not fundacion_id
            or not columna.get(
                "referencia_columna"
            )
        ):
            continue

        directas_por_fundacion.setdefault(
            fundacion_id,
            [],
        ).append(columna)

    vinculaciones = []
    pendientes_sin_vincular = []

    for pendiente in columnas_pendientes:
        fundacion_id = pendiente.get(
            "fundacion_id"
        )

        posicion_pendiente = (
            _coordenadas_posicion(
                pendiente,
                "posicion_rotulo_columna_pdf",
            )
        )

        columnas_origen = (
            directas_por_fundacion.get(
                fundacion_id,
                [],
            )
        )

        if (
            posicion_pendiente is None
            or not columnas_origen
        ):
            pendientes_sin_vincular.append(
                {
                    **pendiente,
                    "motivo_pendiente": (
                        "sin_columna_directa_o_coordenadas"
                    ),
                }
            )
            continue

        candidatos = []

        for columna_directa in columnas_origen:
            if (
                columna_directa.get("pagina")
                != pendiente.get("pagina")
            ):
                continue

            posicion_directa = (
                _coordenadas_posicion(
                    columna_directa,
                    "posicion_rotulo_columna_pdf",
                )
            )

            if posicion_directa is None:
                continue

            for rotulo_viga in rotulos_vigas:
                if (
                    rotulo_viga.get("pagina")
                    != pendiente.get("pagina")
                ):
                    continue

                posicion_viga = (
                    _coordenadas_rotulo_viga(
                        rotulo_viga
                    )
                )

                if posicion_viga is None:
                    continue

                resultado_distancia = (
                    _distancia_punto_segmento(
                        posicion_viga,
                        posicion_directa,
                        posicion_pendiente,
                    )
                )

                if resultado_distancia is None:
                    continue

                (
                    distancia,
                    proyeccion,
                ) = resultado_distancia

                if not (
                    -margen_proyeccion
                    <= proyeccion
                    <= 1 + margen_proyeccion
                ):
                    continue

                candidatos.append(
                    {
                        "distancia": distancia,
                        "proyeccion": proyeccion,
                        "columna_directa": (
                            columna_directa
                        ),
                        "rotulo_viga": rotulo_viga,
                    }
                )

        candidatos.sort(
            key=lambda candidato: (
                candidato["distancia"],
                str(
                    candidato[
                        "rotulo_viga"
                    ].get(
                        "referencia",
                        "",
                    )
                ),
            )
        )

        if (
            not candidatos
            or candidatos[0]["distancia"]
            > distancia_maxima_pdf
        ):
            pendientes_sin_vincular.append(
                {
                    **pendiente,
                    "motivo_pendiente": (
                        "sin_rotulo_viga_cercano"
                    ),
                    "distancia_rotulo_mas_cercano_pdf": (
                        round(
                            candidatos[0][
                                "distancia"
                            ],
                            3,
                        )
                        if candidatos
                        else None
                    ),
                }
            )
            continue

        mejor = candidatos[0]

        if (
            len(candidatos) > 1
            and (
                candidatos[1]["distancia"]
                - mejor["distancia"]
            )
            < diferencia_minima_segundo_candidato
        ):
            pendientes_sin_vincular.append(
                {
                    **pendiente,
                    "motivo_pendiente": (
                        "asociacion_viga_ambigua"
                    ),
                    "primer_candidato": (
                        mejor[
                            "rotulo_viga"
                        ].get("referencia")
                    ),
                    "segundo_candidato": (
                        candidatos[1][
                            "rotulo_viga"
                        ].get("referencia")
                    ),
                }
            )
            continue

        columna_directa = mejor[
            "columna_directa"
        ]

        rotulo_viga = mejor[
            "rotulo_viga"
        ]

        vinculaciones.append(
            {
                **pendiente,
                "referencia_columna_directa": (
                    columna_directa.get(
                        "referencia_columna"
                    )
                ),
                "referencia_columna_vinculada": (
                    pendiente.get(
                        "referencia_columna"
                    )
                ),
                "referencia_viga": (
                    rotulo_viga.get(
                        "referencia"
                    )
                ),
                "texto_viga": (
                    rotulo_viga.get(
                        "texto_original"
                    )
                ),
                "seccion_viga_m": {
                    "ancho": _numero(
                        rotulo_viga.get(
                            "ancho_m"
                        )
                    ),
                    "alto": _numero(
                        rotulo_viga.get(
                            "alto_m"
                        )
                    ),
                },
                "posicion_rotulo_viga_pdf": {
                    "x": _numero(
                        rotulo_viga.get(
                            "centro_x"
                        )
                    ),
                    "y": _numero(
                        rotulo_viga.get(
                            "centro_y"
                        )
                    ),
                },
                "distancia_rotulo_viga_al_segmento_pdf": (
                    round(
                        mejor["distancia"],
                        3,
                    )
                ),
                "proyeccion_rotulo_sobre_segmento": (
                    round(
                        mejor["proyeccion"],
                        4,
                    )
                ),
                "estado": (
                    "vinculada_por_rotulo_viga"
                ),
                "clasificacion_relacion": (
                    "vinculada_por_viga_rotulada"
                ),
                "metodo_vinculacion": (
                    "rótulo de viga más cercano al "
                    "segmento entre columnas"
                ),
                "requiere_revision_asociacion": False,
                "requiere_revision_geometrica": True,
                                "posicion_rotulo_columna_directa_pdf": (
                    columna_directa.get(
                        "posicion_rotulo_columna_pdf"
                    )
                ),
                "posicion_rotulo_columna_vinculada_pdf": (
                    pendiente.get(
                        "posicion_rotulo_columna_pdf"
                    )
                ),
            }
        )

    diagnostico = {
        "columnas_pendientes_entrada": len(
            columnas_pendientes
        ),
        "columnas_vinculadas_por_viga": len(
            vinculaciones
        ),
        "columnas_sin_vincular": len(
            pendientes_sin_vincular
        ),
        "distancia_maxima_pdf": (
            distancia_maxima_pdf
        ),
        "margen_proyeccion": margen_proyeccion,
    }

    return (
        vinculaciones,
        pendientes_sin_vincular,
        diagnostico,
    )

def confirmar_vinculaciones_con_ejes(
    *,
    vinculaciones: list[dict],
    ejes_candidatos: list[dict],
    distancia_maxima_columna_pdf: float = 12.0,
    distancia_maxima_rotulo_pdf: float = 8.0,
    diferencia_minima_segundo_candidato: float = 5.0,
):
    """
    Confirma una vinculación cuando un eje vectorial pasa cerca de:

    - la columna directa;
    - la columna vinculada;
    - el rótulo de la viga.
    """

    confirmadas = []
    sin_confirmar = []

    for vinculacion in vinculaciones:
        columna_directa = (
            _coordenadas_posicion(
                vinculacion,
                "posicion_rotulo_columna_directa_pdf",
            )
        )

        columna_vinculada = (
            _coordenadas_posicion(
                vinculacion,
                "posicion_rotulo_columna_vinculada_pdf",
            )
        )

        rotulo_viga = (
            _coordenadas_posicion(
                vinculacion,
                "posicion_rotulo_viga_pdf",
            )
        )

        if (
            columna_directa is None
            or columna_vinculada is None
            or rotulo_viga is None
        ):
            sin_confirmar.append(
                {
                    **vinculacion,
                    "motivo_revision_geometrica": (
                        "faltan_coordenadas"
                    ),
                }
            )
            continue

        candidatos = []

        for eje in ejes_candidatos:
            if (
                eje.get("pagina")
                != vinculacion.get("pagina")
            ):
                continue

            valores = [
                _numero(eje.get("x_inicial")),
                _numero(eje.get("y_inicial")),
                _numero(eje.get("x_final")),
                _numero(eje.get("y_final")),
            ]

            if any(
                valor is None
                for valor in valores
            ):
                continue

            inicio = (
                valores[0],
                valores[1],
            )

            fin = (
                valores[2],
                valores[3],
            )

            resultado_directa = (
                _distancia_punto_segmento(
                    columna_directa,
                    inicio,
                    fin,
                )
            )

            resultado_vinculada = (
                _distancia_punto_segmento(
                    columna_vinculada,
                    inicio,
                    fin,
                )
            )

            resultado_rotulo = (
                _distancia_punto_segmento(
                    rotulo_viga,
                    inicio,
                    fin,
                )
            )

            if (
                resultado_directa is None
                or resultado_vinculada is None
                or resultado_rotulo is None
            ):
                continue

            distancia_directa = (
                resultado_directa[0]
            )

            distancia_vinculada = (
                resultado_vinculada[0]
            )

            distancia_rotulo = (
                resultado_rotulo[0]
            )

            cumple = (
                distancia_directa
                <= distancia_maxima_columna_pdf
                and distancia_vinculada
                <= distancia_maxima_columna_pdf
                and distancia_rotulo
                <= distancia_maxima_rotulo_pdf
            )

            candidatos.append(
                {
                    "eje": eje,
                    "distancia_directa": (
                        distancia_directa
                    ),
                    "distancia_vinculada": (
                        distancia_vinculada
                    ),
                    "distancia_rotulo": (
                        distancia_rotulo
                    ),
                    "puntaje": (
                        distancia_directa
                        + distancia_vinculada
                        + distancia_rotulo
                    ),
                    "cumple": cumple,
                }
            )

        candidatos_validos = [
            candidato
            for candidato in candidatos
            if candidato["cumple"]
        ]

        candidatos_validos.sort(
            key=lambda candidato: (
                candidato["puntaje"],
                candidato["eje"].get(
                    "id_eje",
                    0,
                ),
            )
        )

        if not candidatos_validos:
            mejor = (
                min(
                    candidatos,
                    key=lambda candidato: (
                        candidato["puntaje"]
                    ),
                )
                if candidatos
                else None
            )

            sin_confirmar.append(
                {
                    **vinculacion,
                    "motivo_revision_geometrica": (
                        "sin_eje_vectorial_compatible"
                    ),
                    "mejor_puntaje_vectorial": (
                        round(
                            mejor["puntaje"],
                            3,
                        )
                        if mejor
                        else None
                    ),
                }
            )
            continue

        mejor = candidatos_validos[0]

        if (
            len(candidatos_validos) > 1
            and (
                candidatos_validos[1]["puntaje"]
                - mejor["puntaje"]
            )
            < diferencia_minima_segundo_candidato
        ):
            sin_confirmar.append(
                {
                    **vinculacion,
                    "motivo_revision_geometrica": (
                        "eje_vectorial_ambiguo"
                    ),
                }
            )
            continue

        eje = mejor["eje"]

        confirmadas.append(
            {
                **vinculacion,
                "id_eje_viga": eje.get(
                    "id_eje"
                ),
                "eje_viga_pdf": {
                    "x_inicial": _numero(
                        eje.get("x_inicial")
                    ),
                    "y_inicial": _numero(
                        eje.get("y_inicial")
                    ),
                    "x_final": _numero(
                        eje.get("x_final")
                    ),
                    "y_final": _numero(
                        eje.get("y_final")
                    ),
                },
                "longitud_eje_viga_pdf": (
                    _numero(
                        eje.get("longitud_pdf")
                    )
                ),
                "angulo_eje_viga_grados": (
                    _numero(
                        eje.get(
                            "angulo_pdf_grados"
                        )
                    )
                ),
                "distancias_confirmacion_pdf": {
                    "columna_directa": round(
                        mejor[
                            "distancia_directa"
                        ],
                        3,
                    ),
                    "columna_vinculada": round(
                        mejor[
                            "distancia_vinculada"
                        ],
                        3,
                    ),
                    "rotulo_viga": round(
                        mejor[
                            "distancia_rotulo"
                        ],
                        3,
                    ),
                },
                "estado": (
                    "confirmada_por_eje_vectorial"
                ),
                "metodo_confirmacion": (
                    "proximidad del eje vectorial "
                    "a ambas columnas y al rótulo"
                ),
                "requiere_revision_geometrica": False,
            }
        )

    diagnostico = {
        "vinculaciones_entrada": len(
            vinculaciones
        ),
        "vinculaciones_confirmadas": len(
            confirmadas
        ),
        "vinculaciones_sin_confirmar": len(
            sin_confirmar
        ),
        "ejes_candidatos_evaluados": len(
            ejes_candidatos
        ),
    }

    return (
        confirmadas,
        sin_confirmar,
        diagnostico,
    )
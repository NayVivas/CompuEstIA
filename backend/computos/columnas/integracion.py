"""Integración entre fundaciones, columnas y secciones detectadas."""
from dataclasses import asdict, is_dataclass
from collections import Counter

from computos.columnas.deteccion import (
    asociar_columnas_a_fundaciones,
    detectar_columnas,
    extraer_secciones_columnas,
    filtrar_palabras_detalles_columnas,
)

from computos.vigas.riostra import (
    detectar_vigas_riostra,
    eliminar_rotulos_duplicados,
    emparejar_bordes_paralelos,
    extraer_bordes_vectoriales_vigas,
)

from computos.columnas.vinculacion_vigas import (
    vincular_columnas_pendientes_con_vigas,
    confirmar_vinculaciones_con_ejes
)

from computos.configuracion.parametros import (
    DIFERENCIA_ANGULAR_MAXIMA_BORDES_GRADOS,
    DIFERENCIA_LONGITUD_MAXIMA_BORDES,
    ESPESOR_VECTOR_VIGA_PT,
    LONGITUD_MINIMA_LINEA_VIGA_PT,
    MARGEN_ZONA_ESTRUCTURAL_PT,
    SEPARACION_MAXIMA_BORDES_PT,
    SEPARACION_MINIMA_BORDES_PT,
    SUPERPOSICION_MINIMA_BORDES,
    TOLERANCIA_EJES_DUPLICADOS_PT,
    TOLERANCIA_ESPESOR_VECTOR_PT,
)




def _palabra_a_diccionario(palabra) -> dict:
    """
    Convierte PalabraNormalizada a diccionario.

    También conserva compatibilidad con los detectores antiguos,
    que ya reciben diccionarios.
    """

    if isinstance(palabra, dict):
        return dict(palabra)

    convertir = getattr(
        palabra,
        "a_diccionario",
        None,
    )

    if callable(convertir):
        resultado = convertir()

        if isinstance(resultado, dict):
            return resultado

    if is_dataclass(palabra):
        return asdict(palabra)

    campos = (
        "texto",
        "pagina",
        "x0",
        "y0",
        "x1",
        "y1",
        "x0_visual",
        "y0_visual",
        "x1_visual",
        "y1_visual",
    )

    resultado = {
        campo: getattr(
            palabra,
            campo,
            None,
        )
        for campo in campos
    }

    requeridos = (
        "texto",
        "pagina",
        "x0",
        "y0",
        "x1",
        "y1",
    )

    faltantes = [
        campo
        for campo in requeridos
        if resultado.get(campo) is None
    ]

    if faltantes:
        raise TypeError(
            "No se pudo adaptar una palabra normalizada. "
            f"Faltan los campos: {', '.join(faltantes)}."
        )

    return resultado


def _palabras_a_diccionarios(
    palabras,
) -> list[dict]:
    return [
        _palabra_a_diccionario(palabra)
        for palabra in palabras
    ]


def _numero(valor):
    if valor is None:
        return None

    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _leer_configuracion(configuracion_proyecto) -> dict:
    if configuracion_proyecto is None:
        return {}

    if isinstance(configuracion_proyecto, dict):
        return configuracion_proyecto

    convertir = getattr(
        configuracion_proyecto,
        "a_diccionario",
        None,
    )

    if callable(convertir):
        resultado = convertir()
        return resultado if isinstance(resultado, dict) else {}

    return {}


def _obtener_correcciones_columnas(
    configuracion_proyecto,
) -> dict[str, dict]:
    datos = _leer_configuracion(
        configuracion_proyecto
    )

    correcciones = {}

    for correccion in datos.get(
        "correcciones_columnas_fundaciones",
        [],
    ):
        original = str(
            correccion.get(
                "referencia_original",
                "",
            )
        ).strip().upper()

        correcta = str(
            correccion.get(
                "referencia_correcta",
                "",
            )
        ).strip().upper()

        if not original or not correcta:
            continue

        correcciones[original] = {
            "referencia_correcta": correcta,
            "motivo": str(
                correccion.get(
                    "motivo",
                    "",
                )
            ).strip(),
        }

    return correcciones


def obtener_selecciones_fuentes_columnas(configuracion_proyecto) -> dict[tuple, dict]:
    """Devuelve selecciones profesionales por campo y referencia."""

    datos = _leer_configuracion(configuracion_proyecto)
    resultado = {}
    for seleccion in datos.get("selecciones_fuentes_columnas", []):
        campo = str(seleccion.get("campo", "")).strip().lower()
        referencia = str(seleccion.get("referencia", "")).strip().upper()
        origen = str(seleccion.get("origen", "")).strip()
        pagina = seleccion.get("pagina")
        if campo not in {"seccion", "armadura"} or not referencia or not origen:
            continue
        if type(pagina) is not int or pagina < 1:
            continue
        resultado[(campo, referencia)] = {**seleccion, "origen": origen, "pagina": pagina}
    return resultado


def obtener_reasignaciones_detalles_columnas(
    configuracion_proyecto,
    rol: str,
) -> dict[tuple[int, str], str]:
    """Devuelve correcciones limitadas al PDF y página que las originó.

    Una misma referencia puede ser correcta en una lámina y estar mal
    rotulada en otra. Por eso estas decisiones nunca se convierten en una
    sustitución global por texto.
    """

    datos = _leer_configuracion(configuracion_proyecto)
    rol_limpio = str(rol or "").strip().lower()
    resultado = {}

    for reasignacion in datos.get(
        "reasignaciones_detalles_columnas",
        [],
    ):
        if not isinstance(reasignacion, dict):
            continue
        if str(reasignacion.get("rol") or "").strip().lower() != rol_limpio:
            continue
        pagina = reasignacion.get("pagina")
        original = str(
            reasignacion.get("referencia_original") or ""
        ).strip().upper()
        correcta = str(
            reasignacion.get("referencia_correcta") or ""
        ).strip().upper()
        if type(pagina) is not int or pagina < 1 or not original or not correcta:
            continue
        resultado[(pagina, original)] = correcta

    return resultado


def _obtener_secciones_manuales(configuracion_proyecto) -> list[dict]:
    datos = _leer_configuracion(configuracion_proyecto)
    resultado = []
    for seccion in datos.get("secciones_manuales_columnas", []):
        referencia = str(seccion.get("referencia", "")).strip().upper()
        if not referencia:
            continue
        resultado.append({
            "referencia_original": referencia,
            "referencia": referencia,
            "dimension_1_m": seccion.get("dimension_1_m"),
            "dimension_2_m": seccion.get("dimension_2_m"),
            "origen": "revision_profesional",
            "pagina": seccion.get("pagina"),
            "fue_corregida": False,
            "estado": "CORRECTO",
            "definida_por_profesional": True,
            "revisor": seccion.get("revisor"),
            "motivo": seccion.get("motivo"),
        })
    return resultado


def _aplicar_correcciones_columnas(
    columnas: list[dict],
    correcciones: dict[str, dict],
) -> list[dict]:
    resultado = []

    for columna in columnas:
        referencia_original = str(
            columna.get(
                "referencia",
                "",
            )
        ).strip().upper()

        correccion = correcciones.get(
            referencia_original
        )

        nueva_columna = dict(columna)

        nueva_columna.update(
            {
                "referencia_original": referencia_original,
                "referencia": (
                    correccion["referencia_correcta"]
                    if correccion
                    else referencia_original
                ),
                "fue_corregida": correccion is not None,
                "motivo_correccion": (
                    correccion["motivo"]
                    if correccion
                    else None
                ),
            }
        )

        resultado.append(nueva_columna)

    return resultado


def _indice_secciones(
    secciones: list[dict],
    selecciones: dict[tuple, dict] | None = None,
) -> dict[str, dict]:
    indice = {}
    selecciones = selecciones or {}

    for seccion in secciones:
        referencia = str(
            seccion.get(
                "referencia",
                "",
            )
        ).strip().upper()

        if not referencia:
            continue

        if seccion.get("estado") != "CORRECTO":
            continue

        seleccion = selecciones.get(("seccion", referencia))
        coincide = bool(
            seleccion
            and str(seccion.get("origen") or "") == seleccion["origen"]
            and seccion.get("pagina") == seleccion["pagina"]
        )
        if referencia not in indice or coincide:
            indice[referencia] = seccion

    return indice


def _clave_columna(columna: dict) -> tuple:
    return (
        columna.get("pagina"),
        round(
            _numero(
                columna.get("centro_x")
            ) or 0,
            4,
        ),
        round(
            _numero(
                columna.get("centro_y")
            ) or 0,
            4,
        ),
    )


def procesar_columnas_fundaciones(
    *,
    ruta_planta,
    palabras_planta: list[dict],
    fundaciones_planta: list[dict],
    palabras_detalles: list[dict],
    origen_detalles: str,
    palabras_columnas: list[dict],
    origen_columnas: str,
    configuracion_proyecto=None,
) -> dict:
    """
    Relaciona cada fundación con el rótulo de columna más cercano
    y agrega la sección obtenida del plano de columnas.

    Las coordenadas corresponden a posiciones del PDF. No representan
    todavía distancias físicas en metros.
    """
    palabras_planta_compatibles = (
        _palabras_a_diccionarios(
            palabras_planta
        )
    )

    palabras_detalles_compatibles = (
        _palabras_a_diccionarios(
            palabras_detalles
        )
    )

    palabras_columnas_compatibles = (
        _palabras_a_diccionarios(
            palabras_columnas
        )
    )
    palabras_detalles_columnas = filtrar_palabras_detalles_columnas(
        palabras_detalles_compatibles
    )
    palabras_columnas_detalles = filtrar_palabras_detalles_columnas(
        palabras_columnas_compatibles
    )

    rotulos_vigas_riostra = (
        detectar_vigas_riostra(
            palabras_planta_compatibles
        )
    )

    (
        rotulos_vigas_riostra,
        rotulos_vigas_duplicados,
    ) = eliminar_rotulos_duplicados(
        rotulos_vigas_riostra
    )

    correcciones = _obtener_correcciones_columnas(
        configuracion_proyecto
    )

    columnas_detectadas = detectar_columnas(
        palabras_planta_compatibles
    )

    columnas_detectadas = [
        {
            **columna,
            "referencia_original": columna["referencia"],
            "fue_corregida": False,
            "motivo_correccion": None,
        }
        for columna in columnas_detectadas
    ]

    # ======================================================
    # EXTRAER BORDES Y EJES VECTORIALES DE LAS VIGAS
    # ======================================================

    (
        bordes_vectoriales_vigas,
        diagnostico_bordes_vectoriales,
    ) = extraer_bordes_vectoriales_vigas(
        ruta_planta,
        columnas_detectadas,
        espesor_objetivo=ESPESOR_VECTOR_VIGA_PT,
        tolerancia_espesor=(
            TOLERANCIA_ESPESOR_VECTOR_PT
        ),
        longitud_minima=(
            LONGITUD_MINIMA_LINEA_VIGA_PT
        ),
        margen_zona=(
            MARGEN_ZONA_ESTRUCTURAL_PT
        ),
    )

    (
        ejes_candidatos_vigas,
        bordes_sin_pareja,
        diagnostico_ejes_vectoriales,
    ) = emparejar_bordes_paralelos(
        bordes_vectoriales_vigas,
        diferencia_angular_maxima=(
            DIFERENCIA_ANGULAR_MAXIMA_BORDES_GRADOS
        ),
        separacion_minima=(
            SEPARACION_MINIMA_BORDES_PT
        ),
        separacion_maxima=(
            SEPARACION_MAXIMA_BORDES_PT
        ),
        superposicion_minima=(
            SUPERPOSICION_MINIMA_BORDES
        ),
        diferencia_longitud_maxima=(
            DIFERENCIA_LONGITUD_MAXIMA_BORDES
        ),
        tolerancia_ejes_duplicados=(
            TOLERANCIA_EJES_DUPLICADOS_PT
        ),
    )

    asociaciones = asociar_columnas_a_fundaciones(
        fundaciones_planta,
        columnas_detectadas,
        permitir_multiples=True,
    )

    mapa_correcciones_secciones = {
        referencia_original: datos[
            "referencia_correcta"
        ]
        for referencia_original, datos
        in correcciones.items()
    }
    mapa_correcciones_detalles = {
        **mapa_correcciones_secciones,
        **obtener_reasignaciones_detalles_columnas(
            configuracion_proyecto,
            "detalles",
        ),
    }
    mapa_correcciones_columnas = (
        obtener_reasignaciones_detalles_columnas(
            configuracion_proyecto,
            "columnas",
        )
    )

    secciones_plano_columnas = (
        extraer_secciones_columnas(
            palabras_columnas_detalles,
            origen_columnas,
            correcciones=mapa_correcciones_columnas,
        )
    )

    secciones_plano_fundaciones = (
        extraer_secciones_columnas(
            palabras_detalles_columnas,
            origen_detalles,
            correcciones=mapa_correcciones_detalles,
        )
    )

    secciones = [
        *secciones_plano_columnas,
        *secciones_plano_fundaciones,
        *_obtener_secciones_manuales(configuracion_proyecto),
    ]

    selecciones_fuentes = obtener_selecciones_fuentes_columnas(
        configuracion_proyecto
    )
    secciones_por_referencia = _indice_secciones(
        secciones, selecciones_fuentes
    )

    columnas_por_posicion = {
        _clave_columna(columna): columna
        for columna in columnas_detectadas
    }

    detalle = []
    referencias_asociadas = Counter()
    rotulos_utilizados = set()

    for asociacion in asociaciones:
        referencia_columna = asociacion.get(
            "columna"
        )

        clave_columna = (
            asociacion.get("pagina"),
            round(
                _numero(
                    asociacion.get("columna_x")
                ) or 0,
                4,
            ),
            round(
                _numero(
                    asociacion.get("columna_y")
                ) or 0,
                4,
            ),
        )

        columna_detectada = (
            columnas_por_posicion.get(
                clave_columna
            )
        )

        seccion = (
            secciones_por_referencia.get(
                referencia_columna
            )
            if referencia_columna
            else None
        )

        tipo_asociacion = asociacion.get(
            "tipo_asociacion"
        )

        es_apoyo_directo = (
            tipo_asociacion
            == "principal_por_proximidad"
        )

        if referencia_columna is None:
            estado = "sin_columna_asociada"
        elif seccion is None:
            estado = "sin_seccion_detectada"
        elif not es_apoyo_directo:
            estado = (
                "pendiente_clasificacion_estructural"
            )
        else:
            estado = "lista_para_visualizar"

        if referencia_columna:
            referencias_asociadas[
                referencia_columna
            ] += 1
            rotulos_utilizados.add(
                clave_columna
            )

        detalle.append(
            {
                "fundacion_id": asociacion.get(
                    "identificador"
                ),
                "referencia_fundacion": (
                    asociacion.get(
                        "referencia"
                    )
                ),
                "pagina": asociacion.get(
                    "pagina"
                ),
                "referencia_columna": (
                    referencia_columna
                ),
                "referencia_columna_original": (
                    columna_detectada.get(
                        "referencia_original"
                    )
                    if columna_detectada
                    else None
                ),
                "columna_corregida": (
                    columna_detectada.get(
                        "fue_corregida",
                        False,
                    )
                    if columna_detectada
                    else False
                ),
                "motivo_correccion": (
                    columna_detectada.get(
                        "motivo_correccion"
                    )
                    if columna_detectada
                    else None
                ),
                "ancho_m": (
                    _numero(
                        seccion.get(
                            "dimension_1_m"
                        )
                    )
                    if seccion
                    else None
                ),
                "largo_m": (
                    _numero(
                        seccion.get(
                            "dimension_2_m"
                        )
                    )
                    if seccion
                    else None
                ),
                "altura_m": None,
                "posicion_fundacion_pdf": {
                    "x": _numero(
                        asociacion.get(
                            "centro_x"
                        )
                    ),
                    "y": _numero(
                        asociacion.get(
                            "centro_y"
                        )
                    ),
                },
                "posicion_rotulo_columna_pdf": {
                    "x": _numero(
                        asociacion.get(
                            "columna_x"
                        )
                    ),
                    "y": _numero(
                        asociacion.get(
                            "columna_y"
                        )
                    ),
                },
                "distancia_entre_rotulos_pdf": (
                    _numero(
                        asociacion.get(
                            "distancia_pdf"
                        )
                    )
                ),
                                "distancia_a_columna_principal_pdf": (
                    _numero(
                        asociacion.get(
                            "distancia_a_columna_principal_pdf"
                        )
                    )
                ),
                "origen_seccion": (
                    seccion.get("origen")
                    if seccion
                    else None
                ),
                                "metodo_asociacion": (
                    (
                        "columna principal asociada "
                        "al rótulo de fundación"
                    )
                    if es_apoyo_directo
                    else (
                        "candidata adicional asociada "
                        "por cercanía a la columna principal"
                    )
                ),
                "tipo_asociacion": tipo_asociacion,
                "es_apoyo_directo": es_apoyo_directo,
                "clasificacion_relacion": (
                    "apoyo_directo_estimado"
                    if es_apoyo_directo
                    else (
                        "pendiente_verificacion_geometrica"
                    )
                ),
                "requiere_revision_asociacion": (
                    asociacion.get(
                        "requiere_revision_asociacion",
                        False,
                    )
                ),
                "estado": estado,
            }
        )

        # ======================================================
    # SEPARAR APOYOS DIRECTOS Y RELACIONES PENDIENTES
    # ======================================================

    filas_directas = [
        item
        for item in detalle
        if (
            item.get("tipo_asociacion")
            != "adicional_por_proximidad"
        )
    ]

    columnas_directas = [
        item
        for item in filas_directas
        if item.get("referencia_columna")
    ]

    columnas_candidatas_adicionales = [
        item
        for item in detalle
        if (
            item.get("tipo_asociacion")
            == "adicional_por_proximidad"
        )
    ]

    (
        columnas_vinculadas_por_viga,
        columnas_pendientes,
        diagnostico_vinculacion_vigas,
    ) = vincular_columnas_pendientes_con_vigas(
        columnas_pendientes=(
            columnas_candidatas_adicionales
        ),
        columnas_directas=columnas_directas,
        rotulos_vigas=rotulos_vigas_riostra,
    )

    # Resultado obtenido utilizando solamente el rótulo VR.
    columnas_vinculadas_por_rotulo_viga = list(
        columnas_vinculadas_por_viga
    )

    # Confirmar las relaciones mediante ejes vectoriales.
    (
        columnas_vinculadas_confirmadas,
        columnas_vinculadas_sin_confirmar,
        diagnostico_confirmacion_vectorial,
    ) = confirmar_vinculaciones_con_ejes(
        vinculaciones=(
            columnas_vinculadas_por_rotulo_viga
        ),
        ejes_candidatos=(
            ejes_candidatos_vigas
        ),
    )

    columnas_vinculadas_por_viga = (
        columnas_vinculadas_confirmadas
    )

    # Agregar las relaciones que no consiguieron confirmación
    # vectorial a la lista de pendientes.
    columnas_pendientes = [
        *columnas_pendientes,
        *columnas_vinculadas_sin_confirmar,
    ]

    relaciones_columnas_clasificadas = [
        *filas_directas,
        *columnas_vinculadas_por_viga,
        *columnas_pendientes,
    ]

    conteo_columnas_por_fundacion = Counter(
        item["fundacion_id"]
        for item in columnas_directas
        if item.get("fundacion_id")
    )

    indices_columnas = Counter()

    for item in filas_directas:
        fundacion_id = item.get(
            "fundacion_id"
        )

        if not item.get(
            "referencia_columna"
        ):
            item[
                "indice_columna_en_fundacion"
            ] = None
            item[
                "cantidad_columnas_en_fundacion"
            ] = 0
            continue

        indices_columnas[fundacion_id] += 1

        item[
            "indice_columna_en_fundacion"
        ] = indices_columnas[fundacion_id]

        item[
            "cantidad_columnas_en_fundacion"
        ] = conteo_columnas_por_fundacion[
            fundacion_id
        ]

    # Una asociación pendiente todavía no debe aparecer
    # como columna directamente apoyada sobre la fundación.
    for item in [
        *columnas_vinculadas_por_viga,
        *columnas_pendientes,
    ]:
        item[
            "indice_columna_en_fundacion"
        ] = None

        item[
            "cantidad_columnas_en_fundacion"
        ] = None

    ids_fundaciones = {
        fundacion.get("identificador")
        for fundacion in fundaciones_planta
        if fundacion.get("identificador")
    }

    fundaciones_con_columna = {
        item["fundacion_id"]
        for item in columnas_directas
        if item.get("fundacion_id")
    }

    fundaciones_con_seccion_faltante = {
        item["fundacion_id"]
        for item in columnas_directas
        if (
            item.get("fundacion_id")
            and item["estado"]
            != "lista_para_visualizar"
        )
    }

    fundaciones_listas = (
        fundaciones_con_columna
        - fundaciones_con_seccion_faltante
    )

    fundaciones_sin_columna_ids = (
        ids_fundaciones
        - fundaciones_con_columna
    )

    columnas_directas_listas = [
        item
        for item in columnas_directas
        if item["estado"]
        == "lista_para_visualizar"
    ]

    fundaciones_multiples_confirmadas = {
        fundacion_id: cantidad
        for fundacion_id, cantidad
        in conteo_columnas_por_fundacion.items()
        if cantidad > 1
    }

    vinculadas_por_fundacion = Counter(
        item["fundacion_id"]
        for item
        in columnas_vinculadas_por_viga
        if item.get("fundacion_id")
    )

    pendientes_por_fundacion = Counter(
        item["fundacion_id"]
        for item in columnas_pendientes
        if item.get("fundacion_id")
    )

    referencias_directas = Counter(
        item["referencia_columna"]
        for item in columnas_directas
        if item.get("referencia_columna")
    )

    referencias_vinculadas = Counter(
        item["referencia_columna_vinculada"]
        for item
        in columnas_vinculadas_por_viga
        if item.get(
            "referencia_columna_vinculada"
        )
    )

    referencias_vigas_vinculadas = Counter(
        item["referencia_viga"]
        for item
        in columnas_vinculadas_por_viga
        if item.get("referencia_viga")
    )

    referencias_pendientes = Counter(
        item["referencia_columna"]
        for item in columnas_pendientes
        if item.get("referencia_columna")
    )

    asociaciones_para_revisar = sum(
        item.get(
            "requiere_revision_asociacion",
            False,
        )
        for item
        in relaciones_columnas_clasificadas
    )

    vinculaciones_para_revision_geometrica = sum(
        item.get(
            "requiere_revision_geometrica",
            False,
        )
        for item
        in columnas_vinculadas_por_viga
    )

    validacion = {
        "cantidad_fundaciones": len(
            ids_fundaciones
        ),
        "rotulos_columnas_detectados": len(
            columnas_detectadas
        ),
        "rotulos_vigas_riostra_detectados": len(
            rotulos_vigas_riostra
        ),
        "rotulos_vigas_duplicados_descartados": len(
            rotulos_vigas_duplicados
        ),
        "rotulos_columnas_considerados": len(
            rotulos_utilizados
        ),

        # Compatibilidad con el frontend actual.
        "rotulos_columnas_utilizados": len(
            rotulos_utilizados
        ),
        "cantidad_columnas_asociadas": len(
            columnas_directas
        ),

        "columnas_directas_asociadas": len(
            columnas_directas
        ),
        "columnas_listas_para_visualizar": len(
            columnas_directas_listas
        ),
        "candidatos_adicionales_detectados": len(
            columnas_candidatas_adicionales
        ),
        "columnas_vinculadas_por_viga": len(
            columnas_vinculadas_por_viga
        ),
        "columnas_pendientes_clasificacion": len(
            columnas_pendientes
        ),
        "columnas_directas_sin_seccion": sum(
            item["estado"]
            == "sin_seccion_detectada"
            for item in columnas_directas
        ),
        "fundaciones_listas_para_visualizar": len(
            fundaciones_listas
        ),
        "fundaciones_sin_columna": len(
            fundaciones_sin_columna_ids
        ),
        "fundaciones_sin_seccion": len(
            fundaciones_con_seccion_faltante
        ),
        "fundaciones_con_varias_columnas": len(
            fundaciones_multiples_confirmadas
        ),
        "detalle_fundaciones_con_varias_columnas": dict(
            sorted(
                fundaciones_multiples_confirmadas.items()
            )
        ),
        "fundaciones_con_vigas_vinculadas": len(
            vinculadas_por_fundacion
        ),
        "detalle_fundaciones_con_vigas_vinculadas": dict(
            sorted(
                vinculadas_por_fundacion.items()
            )
        ),
        "fundaciones_pendientes_clasificacion": len(
            pendientes_por_fundacion
        ),
        "detalle_pendientes_clasificacion": dict(
            sorted(
                pendientes_por_fundacion.items()
            )
        ),
        "asociaciones_para_revisar": (
            asociaciones_para_revisar
        ),
        "referencias_asociadas": dict(
            sorted(
                referencias_directas.items()
            )
        ),
        "referencias_columnas_vinculadas": dict(
            sorted(
                referencias_vinculadas.items()
            )
        ),
        "referencias_vigas_vinculadas": dict(
            sorted(
                referencias_vigas_vinculadas.items()
            )
        ),
        "referencias_pendientes_clasificacion": dict(
            sorted(
                referencias_pendientes.items()
            )
        ),
        "referencias_con_seccion": sorted(
            secciones_por_referencia
        ),
        "correcciones_aplicadas": sum(
            seccion.get(
                "fue_corregida",
                False,
            )
            for seccion
            in secciones_plano_fundaciones
        ),
        "ejes_vectoriales_vigas_detectados": len(
            ejes_candidatos_vigas
        ),
        "vinculaciones_por_rotulo_viga": len(
            columnas_vinculadas_por_rotulo_viga
        ),
        "vinculaciones_confirmadas_vectorialmente": len(
            columnas_vinculadas_confirmadas
        ),
        "vinculaciones_sin_confirmar_vectorialmente": len(
            columnas_vinculadas_sin_confirmar
        ),
        "vinculaciones_para_revision_geometrica": len(
            columnas_vinculadas_sin_confirmar
        ),
        "todas_tienen_seccion": (
            bool(ids_fundaciones)
            and fundaciones_listas
            == ids_fundaciones
        ),
        "altura_real_disponible": False,
        "advertencias": [
            (
                "Las columnas principales se asocian "
                "por proximidad entre rótulos."
            ),
            (
                "Las columnas adicionales no se consideran "
                "apoyos directos hasta validar la geometría."
            ),
            (
                "El ancho y largo provienen de los planos "
                "de detalle; la altura real no fue obtenida."
            ),
        ],
    }

    return {
        "columnas_detectadas_planta": (
            columnas_detectadas
        ),
        "secciones_columnas": secciones,
        "rotulos_vigas_riostra_planta": (
            rotulos_vigas_riostra
        ),
        "columnas_fundaciones": (
            filas_directas
        ),
        "columnas_vinculadas_por_rotulo_viga": (
            columnas_vinculadas_por_rotulo_viga
        ),
        "columnas_vinculadas_por_viga": (
            columnas_vinculadas_por_viga
        ),
        "columnas_vinculadas_sin_confirmacion_vectorial": (
            columnas_vinculadas_sin_confirmar
        ),
        "columnas_pendientes_clasificacion": (
            columnas_pendientes
        ),
        "relaciones_columnas_fundaciones": (
            relaciones_columnas_clasificadas
        ),
        "ejes_vigas_candidatos": (
            ejes_candidatos_vigas
        ),
        "diagnostico_vinculacion_columnas_vigas": (
            diagnostico_vinculacion_vigas
        ),
        "diagnostico_bordes_vectoriales_vigas": (
            diagnostico_bordes_vectoriales
        ),
        "diagnostico_ejes_vectoriales_vigas": (
            diagnostico_ejes_vectoriales
        ),
        "diagnostico_confirmacion_vectorial": (
            diagnostico_confirmacion_vectorial
        ),
        "validacion_columnas": validacion,
    }

"""Punto de entrada del proyecto de cómputos métricos."""

import argparse
from pathlib import Path

from computos.configuracion.proyecto import (
    ConfiguracionProyecto,
    cargar_configuracion_proyecto,
)
from computos.fundaciones.armaduras import (
    calcular_barras_comerciales,
    calcular_cantidad_barras,
    calcular_peso_acero,
    expandir_direcciones,
    extraer_textos_armadura,
    interpretar_armaduras,
    resumir_por_diametro,
    separar_niveles_armadura,
)

from computos.configuracion.parametros import (
    DESPERDICIO_ACERO_PORCENTAJE,
    LONGITUD_BARRA_COMERCIAL_M,
    LONGITUD_DOBLEZ_CM,
    PDF_DIR,
    PNG_DIR,
    PROCESSED_DIR,
    RECUBRIMIENTO_FUNDACION_CM,
    REPORT_DIR,
    UNIDAD_DIMENSIONES_CUADRO,
    USAR_ENCOFRADO_ZAPATAS,
    INCREMENTO_PEDESTAL_CM,
    ALTURA_MINIMA_PEDESTAL_M,
    USAR_ENCOFRADO_PEDESTALES,
    ESCALA_IMAGEN_DIAGNOSTICO,
)

from computos.fundaciones.deteccion import (
    aplicar_correcciones,
    calcular_volumenes,
    contar_referencias,
    referencias_duplicadas,
    validar_referencias,
)

from computos.fundaciones.cuadros import (
    extraer_dimensiones_cuadro,
    localizar_estructura_cuadro,
)

from computos.columnas.armaduras import (
    consolidar_armaduras_columnas,
    extraer_armaduras_columnas,
)

from computos.columnas.deteccion import filtrar_palabras_detalles_columnas

from computos.columnas.integracion import (
    obtener_reasignaciones_detalles_columnas,
    obtener_selecciones_fuentes_columnas,
    procesar_columnas_fundaciones,
)
from computos.columnas.porticos import (
    asociar_secciones_porticos,
    extraer_alturas_porticos,
)

from computos.fundaciones.pedestales import (
    calcular_acero_pedestales,
    calcular_dimensiones_pedestales,
    contar_columnas_por_tipo,
    calcular_computos_pedestales,
)

from computos.fundaciones.encofrado import calcular_encofrado_zapatas

from computos.vigas.riostra import (
    dibujar_red_vigas_entre_apoyos,
)

from computos.vigas.computos import (
    calcular_computos_vigas_riostra,
)

from computos.documentos.procesamiento_pdf import (
    dibujar_rectangulos,
    extraer_palabras,
)

from computos.documentos.analisis import extraer_palabras_normalizadas

from computos.referencias import (
    descubrir_catalogo_referencias,
    detectar_referencias_del_catalogo,
)

from computos.salida.reportes import (
    guardar_csv,
    guardar_json,
)

from computos.flujos.experimentos_manuales import (
    experimentar_asociacion_columnas,
    experimentar_bordes_vectoriales_vigas,
    experimentar_columna_pedestal,
    experimentar_computos_pedestales,
    experimentar_deteccion_vigas_riostra,
    experimentar_detalles_columnas,
    experimentar_dimensiones_pedestales,
    experimentar_emparejamiento_bordes_vigas,
    experimentar_secciones_columnas,
)

def _convertir_coordenada(valor):
    if valor is None:
        return None

    try:
        return round(float(valor), 2)
    except (TypeError, ValueError):
        return None


def _centro_deteccion(deteccion, eje):
    centro = _convertir_coordenada(
        deteccion.get(f"centro_{eje}")
    )

    if centro is not None:
        return centro

    inicio = _convertir_coordenada(
        deteccion.get(f"{eje}0")
    )

    fin = _convertir_coordenada(
        deteccion.get(f"{eje}1")
    )

    if inicio is None or fin is None:
        return None

    return round((inicio + fin) / 2, 2)


def construir_fundaciones_planta(
    detecciones,
    dimensiones_por_referencia,
):
    apariciones = {}
    fundaciones_planta = []

    detecciones_ordenadas = sorted(
        detecciones,
        key=lambda item: (
            item.get("pagina") or 0,
            _centro_deteccion(item, "y") or 0,
            _centro_deteccion(item, "x") or 0,
        ),
    )

    for deteccion in detecciones_ordenadas:
        referencia = deteccion["referencia"]

        apariciones[referencia] = (
            apariciones.get(referencia, 0) + 1
        )

        numero = apariciones[referencia]

        centro_x = _centro_deteccion(
            deteccion,
            "x",
        )

        centro_y = _centro_deteccion(
            deteccion,
            "y",
        )

        fundaciones_planta.append(
            {
                "identificador": (
                    f"{referencia}-{numero:02d}"
                ),
                "referencia": referencia,
                "numero": numero,
                "pagina": deteccion.get("pagina"),
                "texto_original": deteccion.get(
                    "texto_original"
                ),
                "posicion": {
                    "x": centro_x,
                    "y": centro_y,
                },
                "centro_x": centro_x,
                "centro_y": centro_y,
                "x_pdf": centro_x,
                "y_pdf": centro_y,
                "rectangulo_pdf": {
                    "x0": _convertir_coordenada(
                        deteccion.get("x0")
                    ),
                    "y0": _convertir_coordenada(
                        deteccion.get("y0")
                    ),
                    "x1": _convertir_coordenada(
                        deteccion.get("x1")
                    ),
                    "y1": _convertir_coordenada(
                        deteccion.get("y1")
                    ),
                },
                "dimensiones_m": (
                    dimensiones_por_referencia.get(
                        referencia,
                        {},
                    )
                ),
                "cantidad": 1,
                "ubicacion_confirmada": (
                    centro_x is not None
                    and centro_y is not None
                ),
            }
        )

    return fundaciones_planta


def _formatear_seccion_alerta(
    ancho,
    alto,
) -> str:
    try:
        return (
            f"{float(ancho):.2f} × "
            f"{float(alto):.2f} m"
        )
    except (TypeError, ValueError):
        return "No disponible"


def _clave_referencia_alerta(referencia):
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


def _agregar_alerta(
    alertas,
    identificadores,
    *,
    alerta_id,
    severidad,
    familia,
    categoria,
    titulo,
    mensaje,
    elemento_id=None,
    referencia=None,
    evidencia=None,
    accion_recomendada=None,
    bloquea_resultado=False,
    excluido_del_computo=False,
):
    """Agrega una alerta normalizada evitando duplicados."""

    if alerta_id in identificadores:
        return

    identificadores.add(alerta_id)

    categorias_dato_requerido = {
        "alturas_reales_no_disponibles",
        "armadura_no_disponible",
        "armadura_no_detectada",
        "pendiente_armadura",
        "sin_seccion",
        "pendiente_escala",
        "geometria_no_computada",
        "sin_longitud_vectorial",
        "seccion_columna_portico_pendiente",
    }
    categorias_observacion = {
        "advertencia_lectura",
        "requiere_modo_asistido",
    }
    categorias_inconsistencia = {
        "inconsistencia_seccion",
        "conteo_ubicaciones_inconsistente",
        "conteo_inconsistente",
        "inconsistencia_portico_columna",
    }

    if categoria in categorias_dato_requerido:
        clase_alerta = "dato_requerido"
    elif categoria in categorias_observacion:
        clase_alerta = "observacion"
    elif (
        categoria in categorias_inconsistencia
        or "inconsisten" in str(categoria)
    ):
        clase_alerta = "inconsistencia"
    else:
        clase_alerta = "revision_tecnica"

    alertas.append(
        {
            "id": alerta_id,
            "severidad": severidad,
            "familia": familia,
            "categoria": categoria,
            "clase_alerta": clase_alerta,
            "titulo": titulo,
            "mensaje": mensaje,
            "elemento_id": elemento_id,
            "referencia": referencia,
            "evidencia": [
                {
                    "etiqueta": etiqueta,
                    "valor": str(valor),
                }
                for etiqueta, valor in (
                    evidencia or []
                )
                if valor not in (
                    None,
                    "",
                )
            ],
            "accion_recomendada": (
                accion_recomendada
            ),
            "bloquea_resultado": bool(
                bloquea_resultado
            ),
            "excluido_del_computo": bool(
                excluido_del_computo
            ),
        }
    )


def separar_advertencias_referencias_resueltas(
    advertencias,
    correcciones_aplicadas,
):
    """Evita reabrir como alerta una duplicidad ya corregida y validada."""

    vigentes = []
    resueltas = []
    hay_correcciones = bool(correcciones_aplicadas)
    prefijo_duplicidad = (
        "el cuadro contiene referencias repetidas:"
    )

    for advertencia in advertencias or []:
        texto = str(advertencia)
        if (
            hay_correcciones
            and texto.strip().casefold().startswith(
                prefijo_duplicidad
            )
        ):
            resueltas.append(texto)
        else:
            vigentes.append(texto)

    return vigentes, resueltas


def construir_alertas_analisis(
    resultado,
) -> dict:
    """Convierte validaciones técnicas en alertas para API y frontend.

    Se informan contradicciones, asociaciones ambiguas y elementos
    excluidos. Las notas metodológicas normales se conservan en sus
    validaciones originales y no se presentan como inconsistencias.
    """

    alertas = []
    identificadores = set()

    # ======================================================
    # VIGAS DE RIOSTRA: GEOMETRÍA Y ACERO
    # ======================================================

    for tramo in resultado.get(
        "vigas_riostra_computo_detalle",
        [],
    ):
        tramo_id = str(
            tramo.get("tramo_id")
            or tramo.get("identificador")
            or "sin-identificador"
        )
        referencia = tramo.get("referencia")
        estado_geometria = tramo.get("estado")

        if estado_geometria != "computado":
            titulos_geometria = {
                "sin_seccion": (
                    "Sección de viga no disponible"
                ),
                "pendiente_escala": (
                    "Escala de viga no confirmada"
                ),
                "pendiente_revision_geometrica": (
                    "Geometría de viga pendiente de revisión"
                ),
            }
            titulo = titulos_geometria.get(
                estado_geometria,
                "Tramo de viga no computado",
            )

            _agregar_alerta(
                alertas,
                identificadores,
                alerta_id=(
                    f"vigas-geometria-{tramo_id}"
                ),
                severidad="advertencia",
                familia="vigas",
                categoria=(
                    estado_geometria
                    or "geometria_no_computada"
                ),
                titulo=f"{titulo} — {tramo_id}",
                mensaje=(
                    "El tramo no participa de los totales "
                    "hasta completar su validación geométrica."
                ),
                elemento_id=tramo_id,
                referencia=referencia,
                evidencia=[
                    (
                        "Rótulo",
                        tramo.get("texto_original"),
                    ),
                    (
                        "Apoyos",
                        (
                            f"{tramo.get('apoyo_inicial_id', '—')} "
                            f"→ {tramo.get('apoyo_final_id', '—')}"
                        ),
                    ),
                    (
                        "Estado",
                        estado_geometria,
                    ),
                ],
                accion_recomendada=(
                    "Revisar el rótulo, los apoyos y la escala "
                    "del tramo en el plano."
                ),
                bloquea_resultado=False,
                excluido_del_computo=True,
            )
            continue

        estado_acero = tramo.get("estado_acero")

        if estado_acero in (
            None,
            "computado",
        ):
            continue

        detalle_armadura = tramo.get(
            "armadura_viga"
        ) or {}

        if estado_acero == (
            "seccion_no_coincide_con_detalle"
        ):
            titulo = (
                "Sección incompatible entre planta y detalle"
            )
            mensaje = (
                "La sección indicada en la planta no coincide "
                "con la sección del detalle de armadura. El "
                "tramo fue excluido del subtotal de acero."
            )
            categoria = "inconsistencia_seccion"
            accion = (
                "Solicitar una aclaración del proyectista o "
                "registrar una corrección documentada."
            )
        elif estado_acero == "pendiente_armadura":
            titulo = "Detalle de armadura no encontrado"
            mensaje = (
                "No se encontró una especificación de armadura "
                "compatible para este tramo."
            )
            categoria = "armadura_no_detectada"
            accion = (
                "Revisar si el plano de detalles contiene la "
                "referencia y su armadura."
            )
        elif estado_acero == (
            "pendiente_revision_detalle"
        ):
            titulo = "Detalle de armadura ambiguo"
            mensaje = (
                "La armadura fue detectada, pero su detalle no "
                "superó todas las validaciones."
            )
            categoria = "armadura_ambigua"
            accion = (
                "Revisar las dimensiones, barras y estribos "
                "extraídos del detalle."
            )
        else:
            titulo = "Acero del tramo pendiente"
            mensaje = (
                "El tramo quedó fuera del subtotal de acero "
                "porque falta validar información necesaria."
            )
            categoria = estado_acero
            accion = (
                "Revisar la evidencia del tramo y completar "
                "los datos faltantes."
            )

        _agregar_alerta(
            alertas,
            identificadores,
            alerta_id=(
                f"vigas-acero-{tramo_id}-{categoria}"
            ),
            severidad="advertencia",
            familia="vigas",
            categoria=categoria,
            titulo=f"{titulo} — {tramo_id}",
            mensaje=mensaje,
            elemento_id=tramo_id,
            referencia=referencia,
            evidencia=[
                (
                    "Rótulo en planta",
                    tramo.get("texto_original"),
                ),
                (
                    "Sección en planta",
                    _formatear_seccion_alerta(
                        tramo.get("ancho_m"),
                        tramo.get("alto_m"),
                    ),
                ),
                (
                    "Detalle de armadura",
                    _formatear_seccion_alerta(
                        detalle_armadura.get("ancho_m"),
                        detalle_armadura.get("alto_m"),
                    ),
                ),
                (
                    "Apoyos",
                    (
                        f"{tramo.get('apoyo_inicial_id', '—')} "
                        f"→ {tramo.get('apoyo_final_id', '—')}"
                    ),
                ),
                (
                    "Longitud entre ejes",
                    (
                        f"{tramo.get('longitud_entre_ejes_m')} m"
                        if tramo.get(
                            "longitud_entre_ejes_m"
                        )
                        is not None
                        else None
                    ),
                ),
            ],
            accion_recomendada=accion,
            bloquea_resultado=False,
            excluido_del_computo=True,
        )

    # ======================================================
    # COLUMNAS: ASOCIACIONES O SECCIONES PENDIENTES
    # ======================================================

    relaciones_columnas = resultado.get(
        "relaciones_columnas_fundaciones",
        resultado.get(
            "columnas_fundaciones",
            [],
        ),
    )

    for indice, relacion in enumerate(
        relaciones_columnas,
        start=1,
    ):
        estado = relacion.get("estado")

        if estado not in {
            "sin_columna_asociada",
            "sin_seccion_detectada",
            "pendiente_clasificacion_estructural",
        }:
            continue

        fundacion_id = relacion.get(
            "fundacion_id"
        )
        referencia_columna = relacion.get(
            "referencia_columna"
        )
        elemento_id = (
            referencia_columna
            or fundacion_id
            or f"relacion-{indice}"
        )

        _agregar_alerta(
            alertas,
            identificadores,
            alerta_id=(
                "columnas-relacion-"
                f"{fundacion_id or indice}-"
                f"{referencia_columna or 'sin-columna'}-"
                f"{estado}"
            ),
            severidad="advertencia",
            familia="columnas",
            categoria=estado,
            titulo=(
                "Asociación de columna pendiente — "
                f"{elemento_id}"
            ),
            mensaje=(
                "La relación entre la columna y la fundación "
                "no quedó completamente validada."
            ),
            elemento_id=elemento_id,
            referencia=referencia_columna,
            evidencia=[
                ("Fundación", fundacion_id),
                ("Columna", referencia_columna),
                ("Estado", estado),
                (
                    "Tipo de asociación",
                    relacion.get("tipo_asociacion"),
                ),
            ],
            accion_recomendada=(
                "Revisar la posición de los rótulos, la sección "
                "y la relación geométrica en la planta."
            ),
            bloquea_resultado=False,
            excluido_del_computo=True,
        )

    for indice, vinculacion in enumerate(
        resultado.get(
            "columnas_vinculadas_por_viga",
            [],
        ),
        start=1,
    ):
        if not vinculacion.get(
            "requiere_revision_geometrica",
            False,
        ):
            continue

        columna = vinculacion.get(
            "referencia_columna_vinculada"
        ) or vinculacion.get(
            "referencia_columna"
        )

        _agregar_alerta(
            alertas,
            identificadores,
            alerta_id=(
                "columnas-vinculacion-"
                f"{vinculacion.get('fundacion_id') or indice}-"
                f"{columna or indice}"
            ),
            severidad="advertencia",
            familia="columnas",
            categoria="vinculacion_geometrica_pendiente",
            titulo=(
                "Vinculación por viga pendiente — "
                f"{columna or 'columna'}"
            ),
            mensaje=(
                "La columna candidata fue vinculada mediante "
                "una viga, pero requiere revisión geométrica."
            ),
            elemento_id=columna,
            referencia=columna,
            evidencia=[
                (
                    "Fundación",
                    vinculacion.get("fundacion_id"),
                ),
                (
                    "Viga",
                    vinculacion.get("referencia_viga"),
                ),
                (
                    "Columna directa",
                    vinculacion.get(
                        "referencia_columna_directa"
                    ),
                ),
            ],
            accion_recomendada=(
                "Confirmar que el eje vectorial conecta ambos "
                "apoyos antes de utilizar la asociación."
            ),
            bloquea_resultado=False,
            excluido_del_computo=True,
        )

    # Si una validación informa diferencias pero no conserva
    # filas detalladas, se genera igualmente una alerta resumen.
    validacion_columnas = resultado.get(
        "validacion_columnas",
        {},
    )

    referencias_columnas = sorted(
        {
            str(
                fila.get("referencia_columna")
                or fila.get(
                    "referencia_columna_vinculada"
                )
                or fila.get("referencia")
                or ""
            ).strip()
            for fila in [
                *resultado.get(
                    "columnas_fundaciones",
                    [],
                ),
                *resultado.get(
                    "columnas_vinculadas_por_viga",
                    [],
                ),
                *resultado.get(
                    "columnas_porticos_segmentos",
                    [],
                ),
            ]
            if (
                fila.get("referencia_columna")
                or fila.get(
                    "referencia_columna_vinculada"
                )
                or fila.get("referencia")
            )
        },
        key=_clave_referencia_alerta,
    )

    tramos_altura_porticos = [
        tramo
        for tramo in resultado.get("columnas_porticos_segmentos", [])
        if tramo.get("apto_revision_altura")
    ]
    tramos_porticos_pendientes_seccion = [
        tramo
        for tramo in resultado.get("columnas_porticos_segmentos", [])
        if tramo.get("estado_extraccion") == "detectado_confirmable"
        and not tramo.get("apto_revision_altura")
    ]
    conflictos_porticos = validacion_columnas.get(
        "tramos_porticos_con_conflicto", 0
    ) or 0
    if (
        (referencias_columnas or tramos_altura_porticos)
        and validacion_columnas.get(
            "altura_real_disponible"
        )
        is False
    ):
        _agregar_alerta(
            alertas,
            identificadores,
            alerta_id=(
                "columnas-alturas-reales-no-disponibles"
            ),
            severidad="advertencia",
            familia="columnas",
            categoria=(
                "alturas_reales_no_disponibles"
            ),
            titulo=(
                "Alturas de pórticos pendientes de validación"
                if tramos_altura_porticos
                else "Faltan las alturas reales de las columnas"
            ),
            mensaje=(
                (
                    "El sistema relacionó columnas, ejes, niveles y cotas "
                    "verticales de los pórticos. Las alturas están precargadas, "
                    "pero requieren confirmación profesional antes del cómputo."
                )
                if tramos_altura_porticos
                else (
                    "Las secciones fueron detectadas, pero el hormigón y el "
                    "encofrado no pueden calcularse sin las alturas verificadas."
                )
            ),
            evidencia=[
                (
                    "Referencias pendientes",
                    ", ".join(referencias_columnas),
                ),
                (
                    "Cantidad de referencias",
                    len(referencias_columnas),
                ),
                (
                    "Tramos deduplicados con altura propuesta",
                    len(tramos_altura_porticos),
                ),
                (
                    "Criterio de deduplicación",
                    "Eje global + intervalo de niveles"
                    if tramos_altura_porticos
                    else None,
                ),
                (
                    "Tramos con sección pendiente",
                    len(tramos_porticos_pendientes_seccion),
                ),
                (
                    "Inconsistencias entre vistas",
                    conflictos_porticos,
                ),
            ],
            accion_recomendada=(
                (
                    "Revisar las cotas precargadas por eje y nivel; corregir "
                    "solo las que no coincidan con el plano y validar."
                )
                if tramos_altura_porticos
                and not (
                    tramos_porticos_pendientes_seccion
                    or conflictos_porticos
                )
                else (
                    "Resolver primero las inconsistencias entre vistas y las "
                    "secciones pendientes; después validar las cotas precargadas."
                )
                if tramos_altura_porticos
                else (
                    "Ingresar y validar la altura real de cada referencia "
                    "de columna."
                )
            ),
            bloquea_resultado=False,
            excluido_del_computo=True,
        )

    for tramo in resultado.get("columnas_porticos_segmentos", []):
        if tramo.get("estado_extraccion") != "conflicto_entre_vistas":
            continue
        _agregar_alerta(
            alertas,
            identificadores,
            alerta_id=f"columnas-portico-conflicto-{tramo.get('tramo_id')}",
            severidad="advertencia",
            familia="columnas",
            categoria="inconsistencia_portico_columna",
            titulo=(
                "Inconsistencia entre pórticos — "
                f"{tramo.get('eje_global') or 'tramo sin eje'}"
            ),
            mensaje=(
                "Dos vistas del mismo tramo no informan la misma referencia "
                "de columna o la misma altura. Ninguna alternativa fue elegida "
                "automáticamente."
            ),
            elemento_id=tramo.get("tramo_id"),
            referencia=tramo.get("referencia"),
            evidencia=[
                ("Eje", tramo.get("eje_global")),
                (
                    "Niveles",
                    f"{tramo.get('nivel_inferior')} – {tramo.get('nivel_superior')}",
                ),
                (
                    "Referencias candidatas",
                    ", ".join(tramo.get("referencias_candidatas", [])),
                ),
                (
                    "Alturas candidatas",
                    ", ".join(
                        f"{altura:g} m"
                        for altura in tramo.get("alturas_candidatas_m", [])
                    ),
                ),
                (
                    "Páginas",
                    ", ".join(str(pagina) for pagina in tramo.get("paginas", [])),
                ),
            ],
            accion_recomendada=(
                "Comparar ambas elevaciones y seleccionar la referencia y la "
                "altura correctas para este eje y nivel."
            ),
            bloquea_resultado=False,
            excluido_del_computo=True,
        )

    discrepancias_porticos = validacion_columnas.get(
        "tramos_porticos_con_discrepancia_no_confirmada", 0
    ) or 0
    if discrepancias_porticos:
        _agregar_alerta(
            alertas,
            identificadores,
            alerta_id="columnas-porticos-discrepancias-no-confirmadas",
            severidad="informacion",
            familia="columnas",
            categoria="asociacion_portico_baja_confianza",
            titulo="Lecturas de pórticos que requieren comprobación visual",
            mensaje=(
                "Se encontraron diferencias, pero la relación entre título, "
                "eje, niveles y rótulo no tiene evidencia geométrica suficiente "
                "para declararlas inconsistencias del proyecto."
            ),
            evidencia=[
                ("Tramos observados", discrepancias_porticos),
                ("Clasificación", "posible asociación incorrecta"),
            ],
            accion_recomendada=(
                "Consultar las evidencias solo si se desea incorporar estos "
                "tramos; no se requiere resolverlas para continuar con otros "
                "elementos válidos."
            ),
            bloquea_resultado=False,
            excluido_del_computo=False,
        )

    secciones_portico_pendientes = {}
    for tramo in resultado.get("columnas_porticos_segmentos", []):
        referencia = str(tramo.get("referencia") or "").strip().upper()
        if (
            not referencia
            or tramo.get("estado_extraccion") != "detectado_confirmable"
            or tramo.get("estado_seccion") == "detectada"
        ):
            continue
        secciones_portico_pendientes.setdefault(referencia, []).append(tramo)

    for referencia, tramos in sorted(
        secciones_portico_pendientes.items(),
        key=lambda item: _clave_referencia_alerta(item[0]),
    ):
        candidatos = {
            (
                opcion.get("ancho_m"),
                opcion.get("largo_m"),
            )
            for tramo in tramos
            for opcion in tramo.get("secciones_candidatas_m", [])
        }
        _agregar_alerta(
            alertas,
            identificadores,
            alerta_id=f"columnas-portico-seccion-{referencia}",
            severidad="advertencia",
            familia="columnas",
            categoria="seccion_columna_portico_pendiente",
            titulo=f"Sección pendiente para tramos {referencia}",
            mensaje=(
                "La altura y la identidad geométrica fueron detectadas, pero "
                "falta una sección única para calcular estos tramos."
            ),
            elemento_id=referencia,
            referencia=referencia,
            evidencia=[
                ("Tramos afectados", len(tramos)),
                (
                    "Secciones candidatas",
                    ", ".join(
                        f"{ancho:g} × {largo:g} m"
                        for ancho, largo in sorted(candidatos)
                    ),
                ),
                (
                    "Ejes",
                    ", ".join(
                        sorted(
                            {
                                str(tramo.get("eje_global"))
                                for tramo in tramos
                                if tramo.get("eje_global")
                            }
                        )
                    ),
                ),
            ],
            accion_recomendada=(
                "Seleccionar o ingresar la sección verificada de la referencia "
                "antes de validar las alturas."
            ),
            bloquea_resultado=False,
            excluido_del_computo=True,
        )

    identidad_incompleta = validacion_columnas.get(
        "observaciones_porticos_identidad_incompleta", 0
    ) or 0
    if identidad_incompleta:
        _agregar_alerta(
            alertas,
            identificadores,
            alerta_id="columnas-porticos-identidad-incompleta",
            severidad="advertencia",
            familia="columnas",
            categoria="geometria_portico_incompleta",
            titulo="Tramos de pórtico sin identidad geométrica completa",
            mensaje=(
                "Se leyó la referencia y la altura, pero falta el eje o uno de "
                "los niveles necesarios para deduplicar el elemento."
            ),
            evidencia=[("Observaciones excluidas", identidad_incompleta)],
            accion_recomendada=(
                "Revisar ejes y niveles del pórtico antes de incorporar estos "
                "tramos al cómputo."
            ),
            bloquea_resultado=False,
            excluido_del_computo=True,
        )

    if (
        referencias_columnas
        and resultado.get("acero_columnas_kg") is None
    ):
        armaduras_columnas = resultado.get(
            "armaduras_columnas",
            [],
        )
        armaduras_correctas = [
            armadura
            for armadura in armaduras_columnas
            if armadura.get("estado") == "CORRECTO"
        ]
        _agregar_alerta(
            alertas,
            identificadores,
            alerta_id="columnas-armadura-no-disponible",
            severidad="informacion",
            familia="columnas",
            categoria="armadura_no_disponible",
            titulo=(
                "El acero de columnas todavía no está computado"
            ),
            mensaje=(
                (
                    "Se detectaron barras longitudinales y estribos, "
                    "pero todavía faltan las alturas y la confirmación "
                    "profesional para calcular su peso."
                )
                if armaduras_correctas
                else (
                    "Los documentos procesados aportan las secciones, "
                    "pero no una interpretación completa de las barras "
                    "longitudinales y estribos de cada columna."
                )
            ),
            evidencia=[
                (
                    "Referencias afectadas",
                    ", ".join(referencias_columnas),
                ),
                (
                    "Armaduras candidatas correctas",
                    len(armaduras_correctas),
                ),
                (
                    "Conflictos entre fuentes",
                    sum(
                        armadura.get(
                            "conflicto_entre_fuentes",
                            False,
                        )
                        for armadura in armaduras_columnas
                    ),
                ),
            ],
            accion_recomendada=(
                "Validar las alturas y confirmar la armadura de "
                "cada columna antes de aprobar el peso de acero."
            ),
            bloquea_resultado=False,
            excluido_del_computo=True,
        )

    for campo, titulo, categorias_detalladas in (
        (
            "fundaciones_sin_columna",
            "Fundaciones sin columna asociada",
            {"sin_columna_asociada"},
        ),
        (
            "fundaciones_sin_seccion",
            "Columnas sin sección validada",
            {"sin_seccion_detectada"},
        ),
        (
            "columnas_pendientes_clasificacion",
            "Columnas pendientes de clasificación",
            {
                "pendiente_clasificacion_estructural",
                "vinculacion_geometrica_pendiente",
            },
        ),
    ):
        cantidad = validacion_columnas.get(
            campo,
            0,
        ) or 0

        if cantidad <= 0:
            continue

        categoria_ya_detallada = any(
            (
                alerta["familia"] == "columnas"
                and alerta["categoria"]
                in categorias_detalladas
            )
            for alerta in alertas
        )

        if categoria_ya_detallada:
            continue

        _agregar_alerta(
            alertas,
            identificadores,
            alerta_id=f"columnas-resumen-{campo}",
            severidad="advertencia",
            familia="columnas",
            categoria=campo,
            titulo=titulo,
            mensaje=(
                f"Se detectaron {cantidad} elementos que "
                "requieren revisión."
            ),
            evidencia=[("Cantidad", cantidad)],
            accion_recomendada=(
                "Revisar el detalle de validación de columnas."
            ),
            bloquea_resultado=False,
            excluido_del_computo=True,
        )

    # ======================================================
    # FUNDACIONES: CONTEO Y UBICACIONES
    # ======================================================

    cantidades_esperadas = {
        str(fila.get("referencia") or "").strip(): int(
            fila.get("cantidad") or 0
        )
        for fila in resultado.get("fundaciones", [])
        if fila.get("referencia")
    }
    cantidades_detectadas = {}

    for fila in resultado.get(
        "fundaciones_planta",
        [],
    ):
        referencia = str(
            fila.get("referencia") or ""
        ).strip()

        if not referencia:
            continue

        cantidades_detectadas[referencia] = (
            cantidades_detectadas.get(referencia, 0) + 1
        )

    for referencia in sorted(
        set(cantidades_esperadas)
        | set(cantidades_detectadas),
        key=_clave_referencia_alerta,
    ):
        esperada = cantidades_esperadas.get(
            referencia,
            0,
        )
        detectada = cantidades_detectadas.get(
            referencia,
            0,
        )

        if esperada == detectada:
            continue

        _agregar_alerta(
            alertas,
            identificadores,
            alerta_id=(
                f"fundaciones-ubicacion-{referencia}"
            ),
            severidad="advertencia",
            familia="fundaciones",
            categoria=(
                "conteo_ubicaciones_inconsistente"
            ),
            titulo=(
                "Cantidad de ubicaciones incompatible — "
                f"{referencia}"
            ),
            mensaje=(
                "La cantidad de rótulos ubicados en la planta "
                "no coincide con el resumen de fundaciones."
            ),
            elemento_id=referencia,
            referencia=referencia,
            evidencia=[
                ("Cantidad esperada", esperada),
                ("Cantidad detectada", detectada),
            ],
            accion_recomendada=(
                "Revisar los rótulos detectados y documentar "
                "el conteo correcto antes de aprobar el cómputo."
            ),
            bloquea_resultado=False,
            excluido_del_computo=False,
        )

    # ======================================================
    # PEDESTALES Y LECTURA DE FUNDACIONES
    # ======================================================

    validacion_pedestales = resultado.get(
        "validacion_pedestales",
        {},
    )

    referencias_pedestales = sorted(
        {
            str(
                fila.get("referencia_columna")
                or fila.get("referencia")
                or ""
            ).strip()
            for fila in resultado.get(
                "pedestales_computo_detalle",
                [],
            )
            if (
                fila.get("referencia_columna")
                or fila.get("referencia")
            )
        },
        key=_clave_referencia_alerta,
    )

    if (
        referencias_pedestales
        and validacion_pedestales.get(
            "altura_real_disponible"
        )
        is False
    ):
        _agregar_alerta(
            alertas,
            identificadores,
            alerta_id=(
                "pedestales-alturas-reales-no-disponibles"
            ),
            severidad="informacion",
            familia="pedestales",
            categoria=(
                "alturas_reales_no_disponibles"
            ),
            titulo=(
                "Los pedestales utilizan una altura mínima"
            ),
            mensaje=(
                "El hormigón y el encofrado informados son "
                "preliminares hasta validar las alturas reales."
            ),
            evidencia=[
                (
                    "Referencias pendientes",
                    ", ".join(referencias_pedestales),
                ),
                (
                    "Altura mínima utilizada",
                    (
                        f"{validacion_pedestales.get('altura_utilizada_m')} m"
                        if validacion_pedestales.get(
                            "altura_utilizada_m"
                        )
                        is not None
                        else None
                    ),
                ),
            ],
            accion_recomendada=(
                "Ingresar y validar la altura real de cada "
                "tipo de pedestal para reemplazar el subtotal "
                "preliminar."
            ),
            bloquea_resultado=False,
            excluido_del_computo=False,
        )

    referencias_acero_pedestal_pendientes = (
        validacion_pedestales.get(
            "referencias_acero_pedestal_pendientes",
            validacion_pedestales.get(
                "referencias_sin_armadura_candidata",
                [],
            ),
        )
    )

    if referencias_acero_pedestal_pendientes:
        referencias_heredadas = (
            validacion_pedestales.get(
                "referencias_armadura_heredada",
                [],
            )
        )
        _agregar_alerta(
            alertas,
            identificadores,
            alerta_id="pedestales-armadura-no-disponible",
            severidad="informacion",
            familia="pedestales",
            categoria="armadura_no_disponible",
            titulo=(
                "Hay pedestales con armadura todavía pendiente"
            ),
            mensaje=(
                "Cuando el plano no especifica acero propio del "
                "pedestal, el motor usa la armadura válida de la "
                "columna con la misma referencia. Las referencias "
                "indicadas no tienen todavía una fuente válida."
            ),
            evidencia=[
                (
                    "Referencias afectadas",
                    ", ".join(
                        referencias_acero_pedestal_pendientes
                    ),
                ),
                (
                    "Referencias heredadas de columnas",
                    (
                        ", ".join(referencias_heredadas)
                        if referencias_heredadas
                        else None
                    ),
                ),
                (
                    "Subtotal de acero disponible",
                    (
                        f"{resultado.get('acero_pedestales_kg')} kg"
                        if resultado.get(
                            "acero_pedestales_kg"
                        )
                        is not None
                        else None
                    ),
                ),
            ],
            accion_recomendada=(
                "Resolver la armadura de la columna asociada o "
                "registrar una especificación explícita del pedestal."
            ),
            bloquea_resultado=False,
            excluido_del_computo=True,
        )

    if (
        validacion_pedestales
        and validacion_pedestales.get(
            "coincide_con_apoyos_directos"
        )
        is False
    ):
        _agregar_alerta(
            alertas,
            identificadores,
            alerta_id=(
                "pedestales-conteo-apoyos-directos"
            ),
            severidad="advertencia",
            familia="pedestales",
            categoria="conteo_inconsistente",
            titulo=(
                "El conteo de pedestales no coincide con los apoyos"
            ),
            mensaje=(
                "La cantidad de pedestales calculados difiere de "
                "la cantidad de columnas con apoyo directo."
            ),
            evidencia=[
                (
                    "Apoyos directos",
                    validacion_pedestales.get(
                        "cantidad_apoyos_directos"
                    ),
                ),
                (
                    "Pedestales computados",
                    validacion_pedestales.get(
                        "cantidad_pedestales_computados"
                    ),
                ),
            ],
            accion_recomendada=(
                "Revisar las asociaciones directas entre "
                "fundaciones y columnas."
            ),
            bloquea_resultado=False,
            excluido_del_computo=False,
        )

    for origen, advertencias in (
        (
            "catálogo de fundaciones",
            resultado.get(
                "advertencias_catalogo",
                [],
            ),
        ),
        (
            "cuadro de fundaciones",
            resultado.get(
                "advertencias_cuadro",
                [],
            ),
        ),
    ):
        for indice, advertencia in enumerate(
            advertencias or [],
            start=1,
        ):
            _agregar_alerta(
                alertas,
                identificadores,
                alerta_id=(
                    "fundaciones-lectura-"
                    f"{origen.replace(' ', '-')}-{indice}"
                ),
                severidad="advertencia",
                familia="fundaciones",
                categoria="advertencia_lectura",
                titulo=(
                    "Advertencia en la lectura de fundaciones"
                ),
                mensaje=str(advertencia),
                evidencia=[("Origen", origen)],
                accion_recomendada=(
                    "Revisar la zona señalada del documento "
                    "antes de aprobar el cómputo."
                ),
                bloquea_resultado=False,
                excluido_del_computo=False,
            )

    prioridad = {
        "error": 0,
        "advertencia": 1,
        "informacion": 2,
    }
    alertas.sort(
        key=lambda alerta: (
            prioridad.get(
                alerta["severidad"],
                9,
            ),
            alerta["familia"],
            alerta["id"],
        )
    )

    por_familia = {}
    por_clase = {}

    for alerta in alertas:
        familia = alerta["familia"]
        por_familia[familia] = (
            por_familia.get(familia, 0) + 1
        )
        clase = alerta["clase_alerta"]
        por_clase[clase] = por_clase.get(clase, 0) + 1

    cantidad_errores = sum(
        alerta["severidad"] == "error"
        for alerta in alertas
    )
    cantidad_advertencias = sum(
        alerta["severidad"] == "advertencia"
        for alerta in alertas
    )
    cantidad_informativas = sum(
        alerta["severidad"] == "informacion"
        for alerta in alertas
    )

    return {
        "alertas": alertas,
        "resumen": {
            "total": len(alertas),
            "errores": cantidad_errores,
            "advertencias": cantidad_advertencias,
            "informativas": cantidad_informativas,
            "elementos_excluidos": sum(
                alerta["excluido_del_computo"]
                for alerta in alertas
            ),
            "por_familia": dict(
                sorted(por_familia.items())
            ),
            "por_clase": dict(sorted(por_clase.items())),
            "estado_analisis": (
                "requiere_revision"
                if cantidad_errores
                else (
                    "completado_con_observaciones"
                    if cantidad_advertencias
                    else "completado"
                )
            ),
        },
    }


def procesar_fundaciones(
    ruta_planta,
    ruta_detalles,
    configuracion_proyecto=None,
    *,
    ruta_columnas=None,
    ruta_porticos=None,
    paginas_origen_porticos=None,
):
    """
    Procesa los planos de planta y detalles de fundaciones.

    Parámetros:
        ruta_planta:
            Ruta del plano donde aparecen las fundaciones.

        ruta_detalles:
            Ruta del plano que contiene el cuadro de dimensiones
            y armaduras.
    """

    # Convertimos las rutas recibidas en objetos Path.
    ruta_planta = Path(ruta_planta)
    ruta_detalles = Path(ruta_detalles)

    ruta_columnas = (
        Path(ruta_columnas)
        if ruta_columnas is not None
        else None
    )
    ruta_porticos = (
        Path(ruta_porticos)
        if ruta_porticos is not None
        else None
    )

    configuracion_proyecto = (
        configuracion_proyecto
        or ConfiguracionProyecto.vacia()
    )

    archivos_para_validar = {
        "planta": ruta_planta,
        "detalles": ruta_detalles,
    }

    if ruta_columnas is not None:
        archivos_para_validar["columnas"] = ruta_columnas

    configuracion_proyecto.validar_archivos(
        **archivos_para_validar
    )


    # ======================================================
    # 1. NORMALIZAR LAS COORDENADAS DEL CUADRO
    # ======================================================

    palabras_detalles_normalizadas = (
        extraer_palabras_normalizadas(
            ruta_detalles
        )
    )

    # ======================================================
    # 2. DESCUBRIR EL CATÁLOGO DE REFERENCIAS
    # ======================================================

    catalogo = descubrir_catalogo_referencias(
        palabras_detalles_normalizadas
    )

    # ======================================================
    # 3. APLICAR CORRECCIONES DOCUMENTADAS AL CATÁLOGO
    # ======================================================

    filas_catalogo = [
        {
            "numero_fila": numero,
            "referencia": referencia,
        }
        for numero, referencia in enumerate(
            catalogo.canonicas,
            start=1,
        )
    ]

    catalogo_corregido = aplicar_correcciones(
        filas_catalogo,
        configuracion_proyecto.correcciones_referencias_cuadro,
        configuracion_proyecto.motivos_referencias_cuadro,
    )

    duplicadas_sin_resolver = referencias_duplicadas(
        catalogo_corregido
    )
    if duplicadas_sin_resolver:
        detalle = ", ".join(
            f"{referencia} ({cantidad} apariciones)"
            for referencia, cantidad in sorted(
                duplicadas_sin_resolver.items()
            )
        )
        raise ValueError(
            "El cuadro contiene referencias duplicadas sin resolver: "
            f"{detalle}. El programa no puede adivinar cuál es correcta. "
            "Declare una corrección documentada mediante --config-proyecto."
        )

    referencias_validas = list(
        dict.fromkeys(
            fila["referencia"]
            for fila in catalogo_corregido
        )
    )

    # ======================================================
    # 4. LEER Y NORMALIZAR LA PLANTA
    # ======================================================

    palabras_planta_normalizadas = (
        extraer_palabras_normalizadas(
            ruta_planta
        )
    )

    # ======================================================
    # 5. BUSCAR SOLO LAS REFERENCIAS AUTORIZADAS
    # ======================================================

    detecciones = detectar_referencias_del_catalogo(
        palabras_planta_normalizadas,
        referencias_validas,
    )

    # ======================================================
    # 6. CONTAR CUÁNTAS FUNDACIONES HAY DE CADA TIPO
    # ======================================================

    conteo = contar_referencias(
        detecciones
    )

    # ======================================================
    # 7. GENERAR LA IMAGEN DE CONTROL
    # ======================================================

    dibujar_rectangulos(
        ruta_planta,
        detecciones,
        PNG_DIR / "fundaciones_detectadas.png",
    )

    # ======================================================
    # 8. CONSTRUIR LAS FILAS Y COLUMNAS DEL CUADRO
    # ======================================================

    estructura = localizar_estructura_cuadro(
        palabras_detalles_normalizadas,
        catalogo,
    )

    # ======================================================
    # 9. EXTRAER X, Y Y H CON UNIDADES NORMALIZADAS
    # ======================================================

    filas_originales = extraer_dimensiones_cuadro(
        estructura,
        UNIDAD_DIMENSIONES_CUADRO,
    )

    # ======================================================
    # 10. APLICAR CORRECCIONES CONOCIDAS
    # ======================================================

    filas = aplicar_correcciones(
        filas_originales,
        configuracion_proyecto.correcciones_referencias_cuadro,
        configuracion_proyecto.motivos_referencias_cuadro,
    )

    correcciones_aplicadas = [
        {
            "numero_fila": fila["numero_fila"],
            "referencia_original": fila["referencia_original"],
            "aparicion_original": fila["aparicion_original"],
            "referencia_correcta": fila["referencia"],
            "motivo": fila["motivo_correccion"],
        }
        for fila in filas
        if fila["fue_corregida"]
    ]

    (
        advertencias_catalogo_vigentes,
        advertencias_catalogo_resueltas,
    ) = separar_advertencias_referencias_resueltas(
        catalogo.advertencias,
        correcciones_aplicadas,
    )
    (
        advertencias_cuadro_vigentes,
        advertencias_cuadro_resueltas,
    ) = separar_advertencias_referencias_resueltas(
        estructura.advertencias,
        correcciones_aplicadas,
    )

    # ======================================================
    # 11. VALIDAR PLANTA CONTRA CUADRO
    # ======================================================

    validacion = validar_referencias(
        set(conteo),
        filas,
    )

    if any(validacion.values()):

        raise ValueError(
            "El cuadro no coincide con la planta: "
            f"{validacion}"
        )

    # ======================================================
    # 12. CALCULAR HORMIGÓN
    # ======================================================

    volumenes, volumen_general = calcular_volumenes(
        filas,
        conteo,
    )

    dimensiones_por_referencia = {
        fila["referencia"]: {
            "x": float(fila["x"]),
            "y": float(fila["y"]),
            "h": float(fila["h"]),
        }
        for fila in volumenes
    }

    fundaciones_planta = construir_fundaciones_planta(
        detecciones,
        dimensiones_por_referencia,
    )

    # ======================================================
# 13. PROCESAR COLUMNAS Y ASOCIARLAS A FUNDACIONES
# ======================================================

    resultado_columnas = {
        "columnas_detectadas_planta": [],
        "secciones_columnas": [],
        "armaduras_columnas": [],
        "armaduras_columnas_por_fuente": [],
        "columnas_fundaciones": [],
        "validacion_columnas": {
            "cantidad_fundaciones": len(
                fundaciones_planta
            ),
            "rotulos_columnas_detectados": 0,
            "fundaciones_listas_para_visualizar": 0,
            "fundaciones_sin_columna": len(
                fundaciones_planta
            ),
            "fundaciones_sin_seccion": 0,
            "todas_tienen_seccion": False,
            "altura_real_disponible": False,
            "advertencias": [
                "No se proporcionó un plano de columnas."
            ],
        },
    }

    if ruta_columnas is not None:
        palabras_planta_columnas = extraer_palabras(
            ruta_planta
        )

        palabras_detalles_columnas = extraer_palabras(
            ruta_detalles
        )

        palabras_columnas = extraer_palabras(
            ruta_columnas
        )

        palabras_detalles_titulos = filtrar_palabras_detalles_columnas(
            palabras_detalles_columnas
        )
        palabras_columnas_titulos = filtrar_palabras_detalles_columnas(
            palabras_columnas
        )

        resultado_columnas = (
            procesar_columnas_fundaciones(
                ruta_planta=ruta_planta,
                palabras_planta=(
                    palabras_planta_columnas
                ),
                fundaciones_planta=(
                    fundaciones_planta
                ),
                palabras_detalles=(
                    palabras_detalles_columnas
                ),
                origen_detalles=(
                    ruta_detalles.name
                ),
                palabras_columnas=(
                    palabras_columnas
                ),
                origen_columnas=(
                    ruta_columnas.name
                ),
                configuracion_proyecto=(
                    configuracion_proyecto
                ),
            )
        )

        # ================================================
        # 13.1 EXTRAER ARMADURAS DE LOS DETALLES
        # ================================================

        # Las correcciones conservan el rol y la página exacta.
        # Una referencia puede estar mal rotulada en una lámina y ser
        # perfectamente válida en otra, incluso dentro del mismo PDF.
        correcciones_armaduras_detalles = {
            **obtener_reasignaciones_detalles_columnas(
                configuracion_proyecto,
                "detalles",
            )
        }
        correcciones_armaduras_columnas = (
            obtener_reasignaciones_detalles_columnas(
                configuracion_proyecto,
                "columnas",
            )
        )

        # Compatibilidad con configuraciones anteriores: esas
        # correcciones globales solo pertenecían al PDF de detalles.
        for seccion in resultado_columnas.get(
            "secciones_columnas",
            [],
        ):
            if (
                seccion.get("fue_corregida")
                and seccion.get("origen") == ruta_detalles.name
                and seccion.get("referencia_original")
                and seccion.get("referencia")
            ):
                correcciones_armaduras_detalles.setdefault(
                    str(seccion["referencia_original"]).strip().upper(),
                    str(seccion["referencia"]).strip().upper(),
                )

        armaduras_plano_columnas = (
            extraer_armaduras_columnas(
                palabras_columnas_titulos,
                ruta_columnas.name,
                correcciones=correcciones_armaduras_columnas,
            )
        )

        armaduras_plano_detalles = (
            extraer_armaduras_columnas(
                palabras_detalles_titulos,
                ruta_detalles.name,
                correcciones=(
                    correcciones_armaduras_detalles
                ),
            )
        )

        # El plano específico de columnas tiene prioridad. Si
        # dos fuentes correctas difieren, la consolidación no
        # adivina: conserva ambas y marca la referencia REVISAR.
        armaduras_columnas = (
            consolidar_armaduras_columnas(
                armaduras_plano_columnas,
                armaduras_plano_detalles,
                selecciones=obtener_selecciones_fuentes_columnas(
                    configuracion_proyecto
                ),
            )
        )

        resultado_columnas[
            "armaduras_columnas_por_fuente"
        ] = [
            *armaduras_plano_columnas,
            *armaduras_plano_detalles,
        ]
        resultado_columnas[
            "armaduras_columnas"
        ] = armaduras_columnas

        validacion_columnas = (
            resultado_columnas.setdefault(
                "validacion_columnas",
                {},
            )
        )
        cantidad_armaduras_correctas = sum(
            armadura.get("estado") == "CORRECTO"
            for armadura in armaduras_columnas
        )
        cantidad_conflictos_armadura = sum(
            armadura.get(
                "conflicto_entre_fuentes",
                False,
            )
            for armadura in armaduras_columnas
        )
        validacion_columnas.update(
            {
                "tipos_armadura_columnas_detectados": len(
                    armaduras_columnas
                ),
                "tipos_armadura_columnas_correctos": (
                    cantidad_armaduras_correctas
                ),
                "tipos_armadura_columnas_revisar": (
                    len(armaduras_columnas)
                    - cantidad_armaduras_correctas
                ),
                "conflictos_armadura_columnas": (
                    cantidad_conflictos_armadura
                ),
                "armaduras_columnas_disponibles": bool(
                    armaduras_columnas
                ),
                "armaduras_columnas_confirmadas": False,
            }
        )

    # ======================================================
    # 13.2 LEER ALTURAS POR TRAMO EN PÓRTICOS
    # ======================================================

    analisis_porticos = {
        "estado": "sin_fuente_porticos",
        "paginas_analizadas": 0,
        "paginas": [],
        "observaciones": [],
        "tramos": [],
        "cantidad_observaciones": 0,
        "cantidad_tramos": 0,
        "cantidad_tramos_confirmables": 0,
        "cantidad_conflictos": 0,
        "cantidad_discrepancias_no_confirmadas": 0,
        "cantidad_identidad_incompleta": 0,
        "cantidad_tramos_con_seccion": 0,
        "referencias_sin_seccion": [],
        "referencias_con_conflicto_seccion": [],
        "advertencias": [
            "No se identificaron elevaciones de pórticos como fuente de alturas."
        ],
    }

    if ruta_porticos is not None:
        secciones_preferidas_porticos = []
        dimensiones_preferidas = {}
        for fila in [
            *resultado_columnas.get("columnas_fundaciones", []),
            *resultado_columnas.get("columnas_vinculadas_por_viga", []),
        ]:
            referencia = str(
                fila.get("referencia_columna")
                or fila.get("referencia_columna_vinculada")
                or ""
            ).strip().upper()
            ancho = fila.get("ancho_m")
            largo = fila.get("largo_m")
            if referencia and ancho and largo:
                dimensiones_preferidas.setdefault(referencia, set()).add(
                    (round(float(ancho), 4), round(float(largo), 4))
                )
        for referencia, dimensiones in dimensiones_preferidas.items():
            if len(dimensiones) != 1:
                continue
            ancho, largo = next(iter(dimensiones))
            secciones_preferidas_porticos.append(
                {
                    "referencia": referencia,
                    "dimension_1_m": ancho,
                    "dimension_2_m": largo,
                    "estado": "CORRECTO",
                    "origen": "seccion_seleccionada_por_motor",
                    "pagina": None,
                }
            )
        referencias_preferidas = {
            seccion["referencia"]
            for seccion in secciones_preferidas_porticos
        }
        secciones_para_porticos = [
            *secciones_preferidas_porticos,
            *(
                seccion
                for seccion in resultado_columnas.get("secciones_columnas", [])
                if str(seccion.get("referencia") or "").strip().upper()
                not in referencias_preferidas
            ),
        ]
        analisis_porticos = asociar_secciones_porticos(
            extraer_alturas_porticos(
                ruta_porticos,
                paginas_origen=paginas_origen_porticos,
            ),
            secciones_para_porticos,
        )

    tramos_porticos = analisis_porticos.get("tramos", [])
    for tramo in tramos_porticos:
        tramo["apto_revision_altura"] = (
            tramo.get("estado_extraccion") == "detectado_confirmable"
            and tramo.get("estado_seccion") == "detectada"
            and tramo.get("altura_detectada_m") is not None
            and tramo.get("referencia")
        )

    tramos_listos_revision = [
        tramo
        for tramo in tramos_porticos
        if tramo.get("apto_revision_altura")
    ]
    resultado_columnas.update(
        {
            "analisis_alturas_porticos": analisis_porticos,
            "columnas_porticos_segmentos": tramos_porticos,
        }
    )
    validacion_columnas = resultado_columnas.setdefault(
        "validacion_columnas", {}
    )
    validacion_columnas.update(
        {
            "fuente_alturas_porticos_disponible": ruta_porticos is not None,
            "alturas_porticos_detectadas": bool(tramos_porticos),
            "tramos_porticos_detectados": len(tramos_porticos),
            "tramos_porticos_listos_revision": len(tramos_listos_revision),
            "tramos_porticos_con_conflicto": analisis_porticos.get(
                "cantidad_conflictos", 0
            ),
            "tramos_porticos_con_discrepancia_no_confirmada": (
                analisis_porticos.get(
                    "cantidad_discrepancias_no_confirmadas", 0
                )
            ),
            "observaciones_porticos_identidad_incompleta": analisis_porticos.get(
                "cantidad_identidad_incompleta", 0
            ),
        }
    )
    if tramos_listos_revision:
        validacion_columnas.setdefault("advertencias", []).append(
            "Las alturas fueron detectadas por tramo en los pórticos y están "
            "precargadas para validación profesional."
        )
    validacion_columnas.setdefault("advertencias", []).extend(
        analisis_porticos.get("advertencias", [])
    )

    # La extracción automática valida posición, sección y propone
    # armaduras. Las alturas reales y la confirmación de esas
    # armaduras se completan después mediante revisión profesional;
    # la API recalcula entonces hormigón, encofrado y acero.
    hay_armaduras_columnas = bool(
        resultado_columnas.get(
            "armaduras_columnas"
        )
    )

    resultado_columnas.update(
        {
            "hormigon_columnas_m3": None,
            "acero_columnas_kg": None,
            "encofrado_columnas_m2": None,
            "estado_computo_columnas": {
                "hormigon": "pendiente_altura",
                "acero": (
                    "candidata_pendiente_altura_y_confirmacion"
                    if hay_armaduras_columnas
                    else "pendiente_armadura"
                ),
                "encofrado": "pendiente_altura",
            },
        }
    )

    # ======================================================
    # 14. CALCULAR PEDESTALES SOBRE APOYOS DIRECTOS
    # ======================================================

    # Un pedestal se genera únicamente cuando la columna está
    # apoyada directamente sobre una fundación. Las columnas
    # vinculadas por una viga (por ejemplo, una relación como
    # F10-C5) no se convierten automáticamente en pedestales.
    columnas_directas_pedestales = [
        {
            "referencia": fila.get(
                "referencia_columna"
            ),
        }
        for fila in resultado_columnas.get(
            "columnas_fundaciones",
            [],
        )
        if fila.get("referencia_columna")
        and fila.get(
            "es_apoyo_directo",
            True,
        )
    ]

    conteo_columnas_pedestales = (
        contar_columnas_por_tipo(
            columnas_directas_pedestales
        )
    )

    # Las secciones pueden proceder de más de un plano. Se
    # conserva una sola sección correcta por referencia para
    # evitar duplicar tipos y cantidades.
    secciones_pedestales = []
    referencias_pedestales_utilizadas = set()

    for seccion in resultado_columnas.get(
        "secciones_columnas",
        [],
    ):
        referencia = str(
            seccion.get("referencia", "")
        ).strip().upper()

        if (
            not referencia
            or referencia
            in referencias_pedestales_utilizadas
            or seccion.get("estado")
            != "CORRECTO"
            or conteo_columnas_pedestales.get(
                referencia,
                0,
            )
            <= 0
        ):
            continue

        referencias_pedestales_utilizadas.add(
            referencia
        )
        secciones_pedestales.append(seccion)

    dimensiones_pedestales = (
        calcular_dimensiones_pedestales(
            secciones_pedestales,
            conteo_columnas_pedestales,
            INCREMENTO_PEDESTAL_CM,
        )
        if secciones_pedestales
        else []
    )

    computos_pedestales = (
        calcular_computos_pedestales(
            dimensiones_pedestales,
            ALTURA_MINIMA_PEDESTAL_M,
            USAR_ENCOFRADO_PEDESTALES,
        )
        if dimensiones_pedestales
        else {
            "detalles": [],
            "volumen_general_m3": None,
            "encofrado_general_m2": None,
        }
    )

    calculo_acero_pedestales = calcular_acero_pedestales(
        computos_pedestales["detalles"],
        resultado_columnas.get(
            "armaduras_columnas",
            [],
        ),
        resultado_columnas.get(
            "armaduras_pedestales",
            [],
        ),
    )
    detalle_pedestales = [
        {
            **fila,
            "estado": "preliminar_altura_minima",
            "referencia_armadura_candidata": (
                fila.get("referencia_columna")
                if fila.get("armadura_columna_candidata")
                else None
            ),
        }
        for fila in calculo_acero_pedestales[
            "detalles"
        ]
    ]

    cantidad_pedestales = sum(
        fila["cantidad"]
        for fila in detalle_pedestales
    )

    cantidad_apoyos_directos = len(
        columnas_directas_pedestales
    )

    referencias_armadura_candidata = sorted(
        {
            fila["referencia_columna"]
            for fila in detalle_pedestales
            if fila.get("armadura_columna_candidata")
        },
        key=_clave_referencia_alerta,
    )
    referencias_sin_armadura_candidata = (
        calculo_acero_pedestales[
            "referencias_pendientes"
        ]
    )

    resultado_pedestales = {
        "cantidad_pedestales": cantidad_pedestales,
        "cantidad_tipos_pedestal": len(
            detalle_pedestales
        ),
        "hormigon_pedestales_m3": (
            computos_pedestales[
                "volumen_general_m3"
            ]
        ),
        "encofrado_pedestales_m2": (
            computos_pedestales[
                "encofrado_general_m2"
            ]
        ),
        "acero_pedestales_kg": (
            calculo_acero_pedestales[
                "acero_total_kg"
            ]
        ),
        "resumen_acero_pedestales": (
            calculo_acero_pedestales[
                "resumen_acero"
            ]
        ),
        "pedestales_computo_detalle": (
            detalle_pedestales
        ),
        "resumen_pedestales_por_tipo": (
            detalle_pedestales
        ),
        "validacion_pedestales": {
            "cantidad_apoyos_directos": (
                cantidad_apoyos_directos
            ),
            "cantidad_pedestales_computados": (
                cantidad_pedestales
            ),
            "cantidad_tipos_computados": len(
                detalle_pedestales
            ),
            "incremento_pedestal_cm": (
                INCREMENTO_PEDESTAL_CM
            ),
            "altura_utilizada_m": (
                ALTURA_MINIMA_PEDESTAL_M
            ),
            "altura_real_disponible": False,
            "resultado_preliminar": True,
            "hormigon_disponible": bool(
                detalle_pedestales
            ),
            "encofrado_disponible": bool(
                detalle_pedestales
            ),
            "acero_disponible": (
                calculo_acero_pedestales[
                    "acero_total_kg"
                ]
                is not None
            ),
            "acero_resultado_completo": (
                calculo_acero_pedestales[
                    "resultado_completo"
                ]
            ),
            "acero_resultado_parcial": (
                calculo_acero_pedestales[
                    "resultado_parcial"
                ]
            ),
            "acero_resultado_preliminar": True,
            "cantidad_tipos_acero_computados": (
                calculo_acero_pedestales[
                    "cantidad_tipos_computados"
                ]
            ),
            "cantidad_tipos_acero_pendientes": (
                calculo_acero_pedestales[
                    "cantidad_tipos_pendientes"
                ]
            ),
            "cantidad_pedestales_acero_computados": (
                calculo_acero_pedestales[
                    "cantidad_pedestales_computados"
                ]
            ),
            "armaduras_columnas_candidatas": len(
                referencias_armadura_candidata
            ),
            "referencias_armadura_candidata": (
                referencias_armadura_candidata
            ),
            "referencias_sin_armadura_candidata": (
                referencias_sin_armadura_candidata
            ),
            "referencias_armadura_heredada": (
                calculo_acero_pedestales[
                    "referencias_heredadas_de_columnas"
                ]
            ),
            "referencias_armadura_explicita": (
                calculo_acero_pedestales[
                    "referencias_con_armadura_explicita"
                ]
            ),
            "referencias_acero_pedestal_computadas": (
                calculo_acero_pedestales[
                    "referencias_computadas"
                ]
            ),
            "referencias_acero_pedestal_pendientes": (
                calculo_acero_pedestales[
                    "referencias_pendientes"
                ]
            ),
            "armaduras_pedestales_confirmadas": False,
            "criterio_armadura": (
                calculo_acero_pedestales[
                    "criterio_armadura"
                ]
            ),
            "criterio_longitudinal_acero": (
                calculo_acero_pedestales[
                    "criterio_longitudinal"
                ]
            ),
            "criterio_estribos": (
                calculo_acero_pedestales[
                    "criterio_estribos"
                ]
            ),
            "coincide_con_apoyos_directos": (
                cantidad_pedestales
                == cantidad_apoyos_directos
            ),
            "advertencias": [
                (
                    "El hormigón y el encofrado son "
                    "preliminares porque utilizan la altura "
                    "mínima configurada."
                ),
                (
                    "Si el plano no especifica acero propio del "
                    "pedestal, se aplica la armadura de la columna "
                    "asociada y se conserva esa procedencia."
                ),
                (
                    "El subtotal de acero usa la altura mínima hasta "
                    "que se validen las alturas reales de pedestales."
                ),
                (
                    "Solo se incluyen columnas con apoyo "
                    "directo sobre una fundación."
                ),
            ],
        },
    }

    # ======================================================
    # 15. CALCULAR VIGAS DE RIOSTRA
    # ======================================================

    # La detección de columnas ya obtuvo los rótulos y los
    # ejes vectoriales de las vigas. Se reutilizan esos datos
    # para no procesar dos veces los mismos objetos del PDF.
    palabras_planta_vigas = (
        palabras_planta_columnas
        if ruta_columnas is not None
        else extraer_palabras(ruta_planta)
    )

    palabras_detalles_vigas = (
        palabras_detalles_columnas
        if ruta_columnas is not None
        else extraer_palabras(ruta_detalles)
    )

    resultado_vigas_riostra = (
        calcular_computos_vigas_riostra(
            ruta_planta=ruta_planta,
            palabras_planta=(
                palabras_planta_vigas
            ),
            palabras_detalles=(
                palabras_detalles_vigas
            ),
            origen_detalles=ruta_detalles.name,
            ejes_vigas=(
                resultado_columnas.get(
                    "ejes_vigas_candidatos",
                    [],
                )
            ),
            rotulos_vigas=(
                resultado_columnas.get(
                    "rotulos_vigas_riostra_planta",
                    [],
                )
            ),
            rotulos_columnas=(
                resultado_columnas.get(
                    "columnas_detectadas_planta",
                    [],
                )
            ),
            # Las cotas del plano se leen entre ejes de apoyo.
            # También se devuelve la longitud libre entre caras.
            criterio_longitud="entre_ejes",
            # El fondo se informa por separado. Por ahora el
            # total considera únicamente las caras laterales.
            incluir_fondo_encofrado=False,
        )
    )

    validacion_acero_vigas = (
        resultado_vigas_riostra.get(
            "validacion_acero_vigas_riostra",
            {},
        )
    )

    if validacion_acero_vigas.get(
        "resultado_completo"
    ):
        estado_acero_vigas = "calculado"
    elif validacion_acero_vigas.get(
        "tramos_acero_computado",
        0,
    ) > 0:
        estado_acero_vigas = "parcial"
    else:
        estado_acero_vigas = "pendiente_armadura"

    resultado_vigas_riostra[
        "estado_computo_vigas_riostra"
    ] = {
        "hormigon": "calculado",
        "acero": estado_acero_vigas,
        "encofrado": "calculado",
    }

    if resultado_vigas_riostra.get(
        "tramos_vigas_riostra"
    ):
        dibujar_red_vigas_entre_apoyos(
            ruta_planta,
            resultado_vigas_riostra.get(
                "apoyos_columnas_vigas",
                [],
            ),
            resultado_vigas_riostra[
                "tramos_vigas_riostra"
            ],
            PNG_DIR / "red_vigas_entre_apoyos.png",
            escala=ESCALA_IMAGEN_DIAGNOSTICO,
        )

    # ======================================================
    # 15. EXTRAER LOS TEXTOS DE ARMADURA
    # ======================================================

    textos = extraer_textos_armadura(
        estructura,
        filas,
    )

    # ======================================================
    # 14. SEPARAR ARMADURA SUPERIOR E INFERIOR
    # ======================================================

    niveles = separar_niveles_armadura(
        textos
    )

    # ======================================================
    # 15. INTERPRETAR DIÁMETROS Y SEPARACIONES
    # ======================================================

    especificaciones = interpretar_armaduras(
        niveles
    )

    # ======================================================
    # 16. DIVIDIR AMBOS SENTIDOS EN X E Y
    # ======================================================

    direcciones = expandir_direcciones(
        especificaciones
    )

    # ======================================================
    # 17. CALCULAR LA CANTIDAD DE BARRAS
    # ======================================================

    conteos_barras = calcular_cantidad_barras(
        direcciones,
        volumenes,
        RECUBRIMIENTO_FUNDACION_CM,
    )

    # ======================================================
    # 18. CALCULAR METROS Y PESO DEL ACERO
    # ======================================================

    acero = calcular_peso_acero(
        conteos_barras,
        volumenes,
        conteo,
        RECUBRIMIENTO_FUNDACION_CM,
        LONGITUD_DOBLEZ_CM,
    )

    # ======================================================
    # 19. AGRUPAR EL ACERO POR DIÁMETRO
    # ======================================================

    resumen_diametros = resumir_por_diametro(
        acero
    )

    # ======================================================
    # 20. CALCULAR BARRAS COMERCIALES
    # ======================================================

    compra = calcular_barras_comerciales(
        resumen_diametros,
        LONGITUD_BARRA_COMERCIAL_M,
        DESPERDICIO_ACERO_PORCENTAJE,
    )

    # ======================================================
    # 21. CALCULAR ENCOFRADO
    # ======================================================

    encofrados, encofrado_general = (
        calcular_encofrado_zapatas(
            volumenes,
            conteo,
            USAR_ENCOFRADO_ZAPATAS,
        )
    )

    # ======================================================
    # 23. RESUMEN HOMOGÉNEO POR FAMILIA ESTRUCTURAL
    # ======================================================

    peso_acero_fundaciones_kg = sum(
        (
            fila["peso_total_kg"]
            for fila in acero
        ),
        start=0,
    )

    computos_por_elemento = {
        "fundaciones": {
            "cantidad": sum(conteo.values()),
            "estado": "calculado",
            "hormigon": {
                "valor": volumen_general,
                "unidad": "m3",
                "estado": "calculado",
            },
            "acero": {
                "valor": peso_acero_fundaciones_kg,
                "unidad": "kg",
                "estado": "calculado",
            },
            "encofrado": {
                "valor": encofrado_general,
                "unidad": "m2",
                "estado": "calculado",
            },
        },
        "pedestales": {
            "cantidad": cantidad_pedestales,
            "estado": (
                "preliminar"
                if resultado_pedestales[
                    "validacion_pedestales"
                ]["acero_resultado_completo"]
                else "parcial"
            ),
            "hormigon": {
                "valor": resultado_pedestales[
                    "hormigon_pedestales_m3"
                ],
                "unidad": "m3",
                "estado": "preliminar_altura_minima",
            },
            "acero": {
                "valor": resultado_pedestales[
                    "acero_pedestales_kg"
                ],
                "unidad": "kg",
                "estado": (
                    "preliminar_altura_minima"
                    if resultado_pedestales[
                        "validacion_pedestales"
                    ]["acero_resultado_completo"]
                    else (
                        "parcial"
                        if resultado_pedestales[
                            "acero_pedestales_kg"
                        ]
                        is not None
                        else "pendiente_armadura"
                    )
                ),
            },
            "encofrado": {
                "valor": resultado_pedestales[
                    "encofrado_pedestales_m2"
                ],
                "unidad": "m2",
                "estado": "preliminar_altura_minima",
            },
        },
        "vigas_riostra": {
            "cantidad": resultado_vigas_riostra.get(
                "validacion_computo_vigas_riostra",
                {},
            ).get("tramos_computados", 0),
            "estado": (
                "calculado"
                if estado_acero_vigas == "calculado"
                else (
                    "parcial"
                    if estado_acero_vigas == "parcial"
                    else "parcial_sin_acero"
                )
            ),
            "hormigon": {
                "valor": resultado_vigas_riostra.get(
                    "hormigon_vigas_riostra_m3"
                ),
                "unidad": "m3",
                "estado": "calculado",
            },
            "acero": {
                "valor": resultado_vigas_riostra.get(
                    "acero_vigas_riostra_kg"
                ),
                "unidad": "kg",
                "estado": estado_acero_vigas,
            },
            "encofrado": {
                "valor": resultado_vigas_riostra.get(
                    "encofrado_vigas_riostra_m2"
                ),
                "unidad": "m2",
                "estado": "calculado",
            },
        },
        "columnas": {
            "cantidad": resultado_columnas.get(
                "validacion_columnas",
                {},
            ).get("rotulos_columnas_detectados", 0),
            "estado": "pendiente_altura_y_armadura",
            "hormigon": {
                "valor": None,
                "unidad": "m3",
                "estado": "pendiente_altura",
            },
            "acero": {
                "valor": None,
                "unidad": "kg",
                "estado": "pendiente_armadura",
            },
            "encofrado": {
                "valor": None,
                "unidad": "m2",
                "estado": "pendiente_altura",
            },
        },
    }

    # ======================================================
    # 24. PREPARAR EL RESUMEN
    # ======================================================

    resultado = {
        "archivo_planta": ruta_planta.name,
        "archivo_detalles": ruta_detalles.name,
        "archivo_columnas": (
            ruta_columnas.name
            if ruta_columnas is not None
            else None
        ),
        "archivo_porticos": (
            ruta_porticos.name
            if ruta_porticos is not None
            else None
        ),
        "cantidad_fundaciones": sum(
            conteo.values()
        ),
        "conteo_por_tipo": dict(
            sorted(conteo.items())
        ),
        "referencias_fundaciones": referencias_validas,
        "cantidad_tipos_fundacion": len(referencias_validas),
        "confianza_catalogo": catalogo.confianza,
        "advertencias_catalogo": advertencias_catalogo_vigentes,
        "confianza_cuadro": estructura.confianza,
        "advertencias_cuadro": advertencias_cuadro_vigentes,
        "advertencias_lectura_resueltas": [
            *(
                {
                    "origen": "catálogo de fundaciones",
                    "mensaje": mensaje,
                    "estado": "resuelta_por_correccion_profesional",
                }
                for mensaje in advertencias_catalogo_resueltas
            ),
            *(
                {
                    "origen": "cuadro de fundaciones",
                    "mensaje": mensaje,
                    "estado": "resuelta_por_correccion_profesional",
                }
                for mensaje in advertencias_cuadro_resueltas
            ),
        ],
        "configuracion_proyecto": configuracion_proyecto.a_diccionario(),
        "correcciones_referencias_aplicadas": correcciones_aplicadas,
        "volumen_hormigon_m3": volumen_general,
        "metros_acero": sum(
            (
                fila["metros_totales"]
                for fila in acero
            ),
            start=0,
        ),
        "peso_acero_kg": sum(
            (
                fila["peso_total_kg"]
                for fila in acero
            ),
            start=0,
        ),
        "barras_comerciales": sum(
            fila["barras_comerciales"]
            for fila in compra
        ),
        "peso_compra_acero_kg": sum(
            (
                fila["peso_compra_kg"]
                for fila in compra
            ),
            start=0,
        ),
        "encofrado_zapatas_m2": (
            encofrado_general
        ),
        "fundaciones": volumenes,
        "fundaciones_planta": fundaciones_planta,
        "armaduras": acero,
        "compra_acero_detalle": compra,
        "encofrado_zapatas_detalle": encofrados,
        "computos_por_elemento": computos_por_elemento,
        "validacion": validacion,
        **resultado_columnas,
        **resultado_pedestales,
        **resultado_vigas_riostra,
    }

    sistema_alertas = construir_alertas_analisis(
        resultado
    )
    resultado.update(
        {
            "alertas_analisis": sistema_alertas[
                "alertas"
            ],
            "resumen_alertas": sistema_alertas[
                "resumen"
            ],
        }
    )

    # ======================================================
    # 23. GUARDAR LOS REPORTES
    # ======================================================

    guardar_json(
        resultado,
        REPORT_DIR / "resumen_general.json",
    )

    guardar_json(
        {
            "resumen": resultado[
                "resumen_alertas"
            ],
            "alertas": resultado[
                "alertas_analisis"
            ],
        },
        REPORT_DIR / "alertas_analisis.json",
    )

    guardar_json(
        estructura.a_diccionario(),
        PROCESSED_DIR
        / "cuadro_fundaciones_interpretado.json",
    )

    guardar_json(
        {
            "archivo_detalles": ruta_detalles.name,
            "pagina_cuadro": catalogo.pagina,
            "encabezado": catalogo.encabezado,
            "confianza": catalogo.confianza,
            "puntaje": catalogo.puntaje,
            "advertencias": advertencias_catalogo_vigentes,
            "advertencias_resueltas": (
                advertencias_catalogo_resueltas
            ),
            "confianza_cuadro": estructura.confianza,
            "advertencias_cuadro": advertencias_cuadro_vigentes,
            "advertencias_cuadro_resueltas": (
                advertencias_cuadro_resueltas
            ),
            "campos_cuadro": sorted(estructura.encabezados),
            "unidad_predeterminada": UNIDAD_DIMENSIONES_CUADRO,
            "referencias_leidas": [
                {
                    "texto_original": candidato.referencia.texto_original,
                    "referencia": candidato.referencia.canonica,
                    "pagina": candidato.pagina,
                }
                for candidato in catalogo.referencias
            ],
            "referencias_utilizadas": referencias_validas,
            "configuracion_proyecto": configuracion_proyecto.a_diccionario(),
            "correcciones_aplicadas": correcciones_aplicadas,
        },
        PROCESSED_DIR
        / "catalogo_referencias_fundaciones.json",
    )

    guardar_json(
        detecciones,
        PROCESSED_DIR
        / "fundaciones_detectadas.json",
    )

    guardar_csv(
        volumenes,
        REPORT_DIR
        / "volumenes_fundaciones.csv",
    )

    guardar_csv(
        acero,
        REPORT_DIR
        / "acero_fundaciones.csv",
    )

    guardar_csv(
        compra,
        REPORT_DIR
        / "compra_acero.csv",
    )

    guardar_csv(
        encofrados,
        REPORT_DIR
        / "encofrado_zapatas.csv",
    )

    guardar_csv(
        resultado_pedestales[
            "pedestales_computo_detalle"
        ],
        REPORT_DIR
        / "computo_preliminar_pedestales.csv",
    )

    guardar_csv(
        resultado_vigas_riostra[
            "vigas_riostra_computo_detalle"
        ],
        REPORT_DIR
        / "vigas_riostra_computo.csv",
    )

    guardar_csv(
        resultado_vigas_riostra[
            "resumen_vigas_riostra_por_tipo"
        ],
        REPORT_DIR
        / "resumen_vigas_riostra_por_tipo.csv",
    )

    guardar_csv(
        resultado_vigas_riostra.get(
            "resumen_acero_vigas_riostra",
            [],
        ),
        REPORT_DIR
        / "resumen_acero_vigas_riostra.csv",
    )

    return resultado


def imprimir_resumen(resultado):

    print("=" * 60)
    print("RESUMEN GENERAL DEL CÓMPUTO")
    print("=" * 60)

    print(
        "Fundaciones:",
        resultado["cantidad_fundaciones"],
    )

    print(
        "Hormigón de zapatas:",
        f"{resultado['volumen_hormigon_m3']:.3f}",
        "m³",
    )

    print(
        "Acero teórico:",
        f"{resultado['peso_acero_kg']:.3f}",
        "kg",
    )

    print(
        "Barras comerciales:",
        resultado["barras_comerciales"],
    )

    print(
        "Peso de compra:",
        f"{resultado['peso_compra_acero_kg']:.3f}",
        "kg",
    )

    print(
        "Encofrado lateral:",
        f"{resultado['encofrado_zapatas_m2']:.3f}",
        "m²",
    )

    print(
        "Reportes guardados en:",
        REPORT_DIR,
    )

    correcciones = resultado.get(
        "correcciones_referencias_aplicadas",
        [],
    )
    if correcciones:
        print("Correcciones documentadas aplicadas:", len(correcciones))
        for correccion in correcciones:
            print(
                "- fila",
                correccion["numero_fila"],
                ":",
                correccion["referencia_original"],
                "->",
                correccion["referencia_correcta"],
            )



def main() -> int:

    # ======================================================
    # CREAR LOS ARGUMENTOS DEL PROGRAMA
    # ======================================================

    parser = argparse.ArgumentParser(
        description=(
            "Calcula cómputos métricos de "
            "fundaciones desde planos PDF."
        )
    )

    parser.add_argument(
        "--planta",
        default=str(PDF_DIR / "Fundaciones" / "Fundaciones_1.pdf"),
        help=(
            "Ruta del plano de planta de fundaciones. "
            "Si no se indica, se utiliza Fundaciones_1.pdf."
        ),
    )

    parser.add_argument(
        "--detalles",
        default=str(PDF_DIR / "Fundaciones" / "Fundaciones_2.pdf"),
        help=(
            "Ruta del plano con detalles de fundaciones. "
            "Si no se indica, se utiliza Fundaciones_2.pdf."
        ),
    )

    parser.add_argument(
        "--columnas",
        default=str(PDF_DIR / "Columnas" / "Columnas.pdf"),
        help=(
            "Ruta del plano general "
            "de detalles de columnas."
        ),
    )

    parser.add_argument(
        "--config-proyecto",
        default=None,
        help=(
            "JSON opcional con correcciones documentadas para este juego "
            "de planos. Sin este argumento no se aplica ninguna excepción."
        ),
    )

    argumentos = parser.parse_args()

    configuracion_proyecto = cargar_configuracion_proyecto(
        argumentos.config_proyecto
    )
    configuracion_proyecto.validar_archivos(
        planta=argumentos.planta,
        detalles=argumentos.detalles,
        columnas=argumentos.columnas,
    )

    # ======================================================
    # PROCESAR LOS ARCHIVOS SELECCIONADOS
    # ======================================================

    resultado = procesar_fundaciones(
        argumentos.planta,
        argumentos.detalles,
        configuracion_proyecto,
        ruta_columnas=argumentos.columnas,
    )

    imprimir_resumen(
        resultado
    )

    experimentar_columna_pedestal(
        argumentos.detalles,
        configuracion_proyecto,
    )

    _asociaciones, columnas = (
        experimentar_asociacion_columnas(
            argumentos.planta,
            resultado["referencias_fundaciones"],
        )
    )

    experimentar_detalles_columnas(
        argumentos.detalles
    )

    secciones_columnas = (
        experimentar_secciones_columnas(
            argumentos.detalles,
            argumentos.columnas,
            configuracion_proyecto,
        )
    )

    # ======================================================
    # TERMINAR FASE 4 - PEDESTALES
    # ======================================================

    resultado_pedestales = (
        experimentar_dimensiones_pedestales(
            argumentos.planta,
            secciones_columnas,
        )
    )

    experimentar_computos_pedestales(
        resultado_pedestales
    )

    # ======================================================
    # FASE 5 - EXPERIMENTOS 1 Y 2
    # DETECTAR Y VALIDAR RÓTULOS DE VIGAS
    # ======================================================

    vigas_riostra_detectadas = (
        experimentar_deteccion_vigas_riostra(
            argumentos.planta
        )
    )

    # ======================================================
    # ESTADO ACTUAL DE LA FASE 5
    # ======================================================

    guardar_json(
        vigas_riostra_detectadas,
        PROCESSED_DIR
        / "rotulos_vigas_riostra.json",
    )

    bordes_vectoriales, diagnostico_vectores = (
        experimentar_bordes_vectoriales_vigas(
            argumentos.planta,
            columnas,
        )
    )

    ejes_candidatos, diagnostico_ejes = (
        experimentar_emparejamiento_bordes_vigas(
            argumentos.planta,
            bordes_vectoriales,
        )
    )

    print()
    print("=" * 60)
    print("FASE 5 - ESTADO ACTUAL")
    print("=" * 60)
    print(
        "La detección de rótulos y secciones está validada."
    )
    print(
        "Los bordes vectoriales candidatos fueron extraídos "
        "directamente del PDF."
    )
    print(
        "Se emparejaron los bordes paralelos "
        "y se obtuvieron ejes centrales candidatos."
    )

    print(
        "El siguiente paso será validar esos ejes "
        "contra los nodos y los rótulos de vigas."
    )

    print(
        "Ejes centrales candidatos:",
        diagnostico_ejes[
            "cantidad_ejes_candidatos"
        ],
    )

    return 0

if __name__ == "__main__":
    main()

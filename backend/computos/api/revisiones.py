"""Revisiones profesionales auditables sobre resultados estructurales."""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from fractions import Fraction
import re
from uuid import uuid4

from computos.columnas.computos import (
    calcular_acero_columnas,
)
from computos.fundaciones.pedestales import (
    calcular_acero_pedestales,
)
from computos.vigas.computos import (
    calcular_acero_tramo_validado_manualmente,
)


FUENTES_SECCION_VALIDAS = {
    "planta",
    "detalle",
    "manual",
}


def _numero(valor, predeterminado=None):
    if valor is None:
        return predeterminado

    try:
        return float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return predeterminado


def _dimension_positiva(valor, nombre):
    numero = _numero(valor)

    if numero is None or numero <= 0:
        raise ValueError(
            f"{nombre} debe ser un número mayor que cero."
        )

    if numero > 5:
        raise ValueError(
            f"{nombre} no puede superar 5 m."
        )

    return round(numero, 4)


def _seccion(ancho, alto):
    return {
        "ancho": round(float(ancho), 4),
        "alto": round(float(alto), 4),
    }


def _sumar(filas, campo):
    valores = [
        _numero(fila.get(campo))
        for fila in filas
    ]
    valores = [
        valor
        for valor in valores
        if valor is not None
    ]

    if not valores:
        return None

    return round(sum(valores), 3)


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


def _clave_diametro(diametro):
    try:
        return (0, float(Fraction(str(diametro))))
    except (ValueError, ZeroDivisionError):
        return (1, str(diametro))


def _resumir_alertas(alertas, cantidad_resueltas):
    por_familia = Counter(
        alerta.get("familia", "general")
        for alerta in alertas
    )
    errores = sum(
        alerta.get("severidad") == "error"
        for alerta in alertas
    )
    advertencias = sum(
        alerta.get("severidad") == "advertencia"
        for alerta in alertas
    )
    informativas = sum(
        alerta.get("severidad") == "informacion"
        for alerta in alertas
    )

    return {
        "total": len(alertas),
        "errores": errores,
        "advertencias": advertencias,
        "informativas": informativas,
        "elementos_excluidos": sum(
            bool(
                alerta.get("excluido_del_computo")
            )
            for alerta in alertas
        ),
        "resueltas_por_ingeniero": cantidad_resueltas,
        "por_familia": dict(
            sorted(por_familia.items())
        ),
        "estado_analisis": (
            "requiere_revision"
            if errores
            else (
                "completado_con_observaciones"
                if advertencias
                else "completado"
            )
        ),
    }


def _recalcular_resumen_vigas(resultado):
    detalle = resultado.get(
        "vigas_riostra_computo_detalle",
        [],
    )
    filas_geometria = [
        fila
        for fila in detalle
        if fila.get("estado") == "computado"
    ]
    filas_acero = [
        fila
        for fila in filas_geometria
        if fila.get("estado_acero") == "computado"
    ]

    grupos = defaultdict(list)

    for fila in filas_geometria:
        grupos[
            (
                fila.get("referencia"),
                _numero(fila.get("ancho_m")),
                _numero(fila.get("alto_m")),
            )
        ].append(fila)

    resumen_tipos = []

    for (
        referencia,
        ancho_m,
        alto_m,
    ), filas in sorted(
        grupos.items(),
        key=lambda elemento: (
            _clave_referencia(elemento[0][0]),
            elemento[0][1] or 0,
            elemento[0][2] or 0,
        ),
    ):
        filas_acero_grupo = [
            fila
            for fila in filas
            if fila.get("estado_acero") == "computado"
        ]

        resumen_tipos.append(
            {
                "referencia": referencia,
                "ancho_m": ancho_m,
                "alto_m": alto_m,
                "cantidad_tramos": len(filas),
                "criterio_longitud": (
                    filas[0].get(
                        "criterio_longitud_computo",
                        "entre_ejes",
                    )
                ),
                "longitud_total_entre_ejes_m": (
                    _sumar(
                        filas,
                        "longitud_entre_ejes_m",
                    )
                ),
                "longitud_total_libre_m": _sumar(
                    filas,
                    "longitud_libre_entre_caras_m",
                ),
                "longitud_total_m": _sumar(
                    filas,
                    "longitud_m",
                ),
                "volumen_hormigon_m3": _sumar(
                    filas,
                    "volumen_hormigon_m3",
                ),
                "encofrado_laterales_m2": _sumar(
                    filas,
                    "encofrado_laterales_m2",
                ),
                "encofrado_fondo_m2": _sumar(
                    filas,
                    "encofrado_fondo_m2",
                ),
                "encofrado_total_m2": _sumar(
                    filas,
                    "encofrado_total_m2",
                ),
                "tramos_acero_computados": len(
                    filas_acero_grupo
                ),
                "peso_acero_kg": _sumar(
                    filas_acero_grupo,
                    "peso_acero_total_kg",
                ),
                "estado_acero": (
                    "computado"
                    if len(filas_acero_grupo) == len(filas)
                    else (
                        "parcial"
                        if filas_acero_grupo
                        else "pendiente"
                    )
                ),
            }
        )

    acumulado_diametros = defaultdict(
        lambda: {
            "metros_longitudinales": 0.0,
            "metros_estribos": 0.0,
            "peso_kg": 0.0,
        }
    )

    for fila in filas_acero:
        for datos in fila.get(
            "acero_por_diametro",
            [],
        ):
            diametro = datos.get(
                "diametro_pulgadas"
            )

            if not diametro:
                continue

            acumulado_diametros[diametro][
                "metros_longitudinales"
            ] += _numero(
                datos.get("metros_longitudinales"),
                0.0,
            )
            acumulado_diametros[diametro][
                "metros_estribos"
            ] += _numero(
                datos.get("metros_estribos"),
                0.0,
            )
            acumulado_diametros[diametro][
                "peso_kg"
            ] += _numero(
                datos.get("peso_kg"),
                0.0,
            )

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
            "peso_kg": round(
                datos["peso_kg"],
                3,
            ),
        }
        for diametro, datos in sorted(
            acumulado_diametros.items(),
            key=lambda elemento: _clave_diametro(
                elemento[0]
            ),
        )
    ]

    estados_pendientes = Counter(
        fila.get("estado_acero")
        for fila in filas_geometria
        if fila.get("estado_acero") != "computado"
    )
    acero_completo = (
        bool(filas_geometria)
        and len(filas_acero) == len(filas_geometria)
    )

    resultado.update(
        {
            "resumen_vigas_riostra_por_tipo": resumen_tipos,
            "longitud_total_entre_ejes_vigas_riostra_m": (
                _sumar(
                    filas_geometria,
                    "longitud_entre_ejes_m",
                )
            ),
            "longitud_total_libre_vigas_riostra_m": (
                _sumar(
                    filas_geometria,
                    "longitud_libre_entre_caras_m",
                )
            ),
            "longitud_total_vigas_riostra_m": _sumar(
                filas_geometria,
                "longitud_m",
            ),
            "hormigon_vigas_riostra_m3": _sumar(
                filas_geometria,
                "volumen_hormigon_m3",
            ),
            "encofrado_laterales_vigas_riostra_m2": (
                _sumar(
                    filas_geometria,
                    "encofrado_laterales_m2",
                )
            ),
            "encofrado_fondo_vigas_riostra_m2": _sumar(
                filas_geometria,
                "encofrado_fondo_m2",
            ),
            "encofrado_vigas_riostra_m2": _sumar(
                filas_geometria,
                "encofrado_total_m2",
            ),
            "acero_vigas_riostra_kg": _sumar(
                filas_acero,
                "peso_acero_total_kg",
            ),
            "resumen_acero_vigas_riostra": resumen_acero,
        }
    )

    validacion_acero = deepcopy(
        resultado.get(
            "validacion_acero_vigas_riostra",
            {},
        )
    )
    validacion_acero.update(
        {
            "tramos_geometria_computada": len(
                filas_geometria
            ),
            "tramos_acero_computado": len(
                filas_acero
            ),
            "tramos_acero_pendiente": (
                len(filas_geometria)
                - len(filas_acero)
            ),
            "estados_pendientes": dict(
                sorted(estados_pendientes.items())
            ),
            "resultado_completo": acero_completo,
        }
    )
    resultado[
        "validacion_acero_vigas_riostra"
    ] = validacion_acero

    validacion_geometria = deepcopy(
        resultado.get(
            "validacion_computo_vigas_riostra",
            {},
        )
    )
    filas_pendientes_geometria = [
        fila
        for fila in detalle
        if fila.get("estado") != "computado"
    ]
    validacion_geometria.update(
        {
            "tramos_computados": len(
                filas_geometria
            ),
            "tramos_pendientes_revision": len(
                filas_pendientes_geometria
            ),
            "resultado_completo": (
                bool(detalle)
                and not filas_pendientes_geometria
            ),
            "acero_disponible": bool(filas_acero),
            "acero_resultado_completo": acero_completo,
            "tramos_acero_computado": len(
                filas_acero
            ),
            "tramos_acero_pendiente": (
                len(filas_geometria)
                - len(filas_acero)
            ),
        }
    )
    resultado[
        "validacion_computo_vigas_riostra"
    ] = validacion_geometria

    estado_acero = (
        "calculado"
        if acero_completo
        else (
            "parcial"
            if filas_acero
            else "pendiente_armadura"
        )
    )
    resultado["estado_computo_vigas_riostra"] = {
        "hormigon": "calculado",
        "acero": estado_acero,
        "encofrado": "calculado",
    }

    computos = resultado.get("computos_por_elemento")

    if isinstance(computos, dict):
        vigas = computos.get("vigas_riostra")

        if isinstance(vigas, dict):
            vigas["estado"] = (
                "calculado"
                if acero_completo
                else "parcial"
            )

            for nombre, valor, estado in (
                (
                    "hormigon",
                    resultado.get(
                        "hormigon_vigas_riostra_m3"
                    ),
                    "calculado",
                ),
                (
                    "acero",
                    resultado.get(
                        "acero_vigas_riostra_kg"
                    ),
                    estado_acero,
                ),
                (
                    "encofrado",
                    resultado.get(
                        "encofrado_vigas_riostra_m2"
                    ),
                    "calculado",
                ),
            ):
                material = vigas.get(nombre)

                if isinstance(material, dict):
                    material["valor"] = valor
                    material["estado"] = estado


def aplicar_revision_seccion_viga(
    resultado,
    *,
    alerta_id,
    tramo_id,
    fuente_seleccionada,
    motivo,
    revisor,
    confirmar_armadura_detalle,
    ancho_m=None,
    alto_m=None,
):
    """Valida un tramo, recalcula sus cantidades y conserva auditoría."""

    if not isinstance(resultado, dict):
        raise TypeError(
            "El resultado del análisis debe ser un diccionario."
        )

    fuente = str(fuente_seleccionada or "").strip().lower()

    if fuente not in FUENTES_SECCION_VALIDAS:
        raise ValueError(
            "fuente_seleccionada debe ser planta, detalle o manual."
        )

    motivo_limpio = str(motivo or "").strip()
    revisor_limpio = str(revisor or "").strip()

    if len(motivo_limpio) < 10:
        raise ValueError(
            "El motivo debe contener al menos 10 caracteres."
        )

    if len(revisor_limpio) < 2:
        raise ValueError(
            "Debe indicarse el nombre del profesional revisor."
        )

    if not confirmar_armadura_detalle:
        raise ValueError(
            "Debe confirmarse explícitamente el uso de la armadura "
            "extraída del detalle para recalcular el acero."
        )

    copia = deepcopy(resultado)
    detalle = copia.get(
        "vigas_riostra_computo_detalle",
        [],
    )
    tramo = next(
        (
            fila
            for fila in detalle
            if str(fila.get("tramo_id"))
            == str(tramo_id)
        ),
        None,
    )

    if tramo is None:
        raise LookupError(
            f"No se encontró el tramo {tramo_id}."
        )

    alertas_activas = copia.get(
        "alertas_analisis",
        [],
    )
    alerta = next(
        (
            item
            for item in alertas_activas
            if item.get("id") == alerta_id
        ),
        None,
    )

    if alerta is None:
        if any(
            item.get("id") == alerta_id
            for item in copia.get(
                "alertas_resueltas",
                [],
            )
        ):
            raise RuntimeError(
                "La alerta ya fue resuelta anteriormente."
            )

        raise LookupError(
            "No se encontró una alerta activa con ese identificador."
        )

    if (
        alerta.get("familia") != "vigas"
        or alerta.get("categoria")
        != "inconsistencia_seccion"
        or str(alerta.get("elemento_id"))
        != str(tramo_id)
    ):
        raise ValueError(
            "La alerta no corresponde a una inconsistencia de sección "
            "del tramo indicado."
        )

    armadura = tramo.get("armadura_viga")

    if not isinstance(armadura, dict):
        raise ValueError(
            "El tramo no conserva el detalle de armadura necesario."
        )

    ancho_planta = _dimension_positiva(
        tramo.get("ancho_m"),
        "El ancho de planta",
    )
    alto_planta = _dimension_positiva(
        tramo.get("alto_m"),
        "El alto de planta",
    )
    ancho_detalle = _dimension_positiva(
        armadura.get("ancho_m"),
        "El ancho del detalle",
    )
    alto_detalle = _dimension_positiva(
        armadura.get("alto_m"),
        "El alto del detalle",
    )

    if fuente == "planta":
        ancho_validado = ancho_planta
        alto_validado = alto_planta
    elif fuente == "detalle":
        ancho_validado = ancho_detalle
        alto_validado = alto_detalle
    else:
        ancho_validado = _dimension_positiva(
            ancho_m,
            "El ancho manual",
        )
        alto_validado = _dimension_positiva(
            alto_m,
            "El alto manual",
        )

    longitud_m = _numero(tramo.get("longitud_m"))

    if longitud_m is None or longitud_m <= 0:
        raise ValueError(
            "El tramo no tiene una longitud computable."
        )

    antes = {
        "ancho_m": ancho_planta,
        "alto_m": alto_planta,
        "volumen_hormigon_m3": tramo.get(
            "volumen_hormigon_m3"
        ),
        "encofrado_total_m2": tramo.get(
            "encofrado_total_m2"
        ),
        "peso_acero_total_kg": tramo.get(
            "peso_acero_total_kg"
        ),
        "estado_acero": tramo.get("estado_acero"),
    }
    revision_id = uuid4().hex
    fecha = datetime.now(timezone.utc).isoformat()

    tramo["ancho_m"] = ancho_validado
    tramo["alto_m"] = alto_validado
    tramo["volumen_hormigon_m3"] = round(
        ancho_validado
        * alto_validado
        * longitud_m,
        3,
    )
    tramo["encofrado_laterales_m2"] = round(
        2 * alto_validado * longitud_m,
        3,
    )
    tramo["encofrado_fondo_m2"] = round(
        ancho_validado * longitud_m,
        3,
    )
    tramo["encofrado_total_m2"] = round(
        tramo["encofrado_laterales_m2"]
        + (
            tramo["encofrado_fondo_m2"]
            if tramo.get("encofrado_incluye_fondo")
            else 0.0
        ),
        3,
    )

    validacion_acero = copia.get(
        "validacion_acero_vigas_riostra",
        {},
    )
    tramo.update(
        calcular_acero_tramo_validado_manualmente(
            tramo,
            armadura,
            tolerancia_seccion_m=_numero(
                validacion_acero.get(
                    "tolerancia_seccion_m"
                ),
                0.025,
            ),
            longitud_adicional_por_extremo_m=_numero(
                validacion_acero.get(
                    "longitud_adicional_por_extremo_m"
                ),
                0.0,
            ),
        )
    )

    despues = {
        "ancho_m": ancho_validado,
        "alto_m": alto_validado,
        "volumen_hormigon_m3": tramo.get(
            "volumen_hormigon_m3"
        ),
        "encofrado_total_m2": tramo.get(
            "encofrado_total_m2"
        ),
        "peso_acero_total_kg": tramo.get(
            "peso_acero_total_kg"
        ),
        "estado_acero": tramo.get("estado_acero"),
    }
    revision = {
        "revision_id": revision_id,
        "tipo_revision": "seccion_viga",
        "alerta_id": alerta_id,
        "elemento_id": str(tramo_id),
        "tramo_id": str(tramo_id),
        "referencia": tramo.get("referencia"),
        "fecha_revision": fecha,
        "revisor": revisor_limpio,
        "motivo": motivo_limpio,
        "alcance": "solo_elemento",
        "fuente_seleccionada": fuente,
        "seccion_planta_original_m": _seccion(
            ancho_planta,
            alto_planta,
        ),
        "seccion_detalle_original_m": _seccion(
            ancho_detalle,
            alto_detalle,
        ),
        "seccion_validada_m": _seccion(
            ancho_validado,
            alto_validado,
        ),
        "armadura_detalle_confirmada": True,
        "valores_antes": antes,
        "valores_despues": despues,
        "estado": "validado_por_ingeniero",
    }
    tramo["revision_ingeniero"] = {
        "revision_id": revision_id,
        "estado": "validado_por_ingeniero",
        "fecha_revision": fecha,
        "revisor": revisor_limpio,
        "fuente_seleccionada": fuente,
    }

    revisiones = copia.setdefault(
        "revisiones_ingeniero",
        [],
    )
    revisiones.append(revision)

    alerta_resuelta = deepcopy(alerta)
    alerta_resuelta.update(
        {
            "estado": "resuelta",
            "resuelta": True,
            "revision_id": revision_id,
            "fecha_resolucion": fecha,
            "resuelta_por": revisor_limpio,
            "excluido_del_computo": False,
        }
    )
    copia.setdefault(
        "alertas_resueltas",
        [],
    ).append(alerta_resuelta)
    copia["alertas_analisis"] = [
        item
        for item in alertas_activas
        if item.get("id") != alerta_id
    ]

    _recalcular_resumen_vigas(copia)

    copia["resumen_alertas"] = _resumir_alertas(
        copia["alertas_analisis"],
        len(copia.get("alertas_resueltas", [])),
    )
    copia["ultima_revision_ingeniero"] = revision

    return copia


ACCIONES_REVISION_VALIDAS = {
    "validar_seccion",
    "validar_geometria",
    "asignar_armadura",
    "validar_alturas",
    "confirmar_asociacion",
    "descartar_asociacion",
    "confirmar_revision",
    "registrar_observacion",
    "resolver_inconsistencia_portico",
    "validar_seccion_portico",
}


def _validar_identidad_revision(motivo, revisor):
    motivo_limpio = str(motivo or "").strip()
    revisor_limpio = str(revisor or "").strip()

    if len(motivo_limpio) < 10:
        raise ValueError(
            "El motivo debe contener al menos 10 caracteres."
        )

    if len(revisor_limpio) < 2:
        raise ValueError(
            "Debe indicarse el nombre del profesional revisor."
        )

    return motivo_limpio, revisor_limpio


def _buscar_alerta_activa(resultado, alerta_id):
    alerta = next(
        (
            item
            for item in resultado.get(
                "alertas_analisis",
                [],
            )
            if item.get("id") == alerta_id
        ),
        None,
    )

    if alerta is not None:
        return alerta

    if any(
        item.get("id") == alerta_id
        for item in resultado.get(
            "alertas_resueltas",
            [],
        )
    ):
        raise RuntimeError(
            "La alerta ya fue resuelta anteriormente."
        )

    raise LookupError(
        "No se encontró una alerta activa con ese identificador."
    )


def _revision_base(
    alerta,
    *,
    accion,
    motivo,
    revisor,
):
    return {
        "revision_id": uuid4().hex,
        "tipo_revision": accion,
        "accion": accion,
        "alerta_id": alerta.get("id"),
        "familia": alerta.get("familia", "general"),
        "categoria_alerta": alerta.get("categoria"),
        "elemento_id": alerta.get("elemento_id"),
        "referencia": alerta.get("referencia"),
        "fecha_revision": datetime.now(
            timezone.utc
        ).isoformat(),
        "revisor": revisor,
        "motivo": motivo,
        "alcance": "alerta_individual",
    }


def _registrar_revision(
    resultado,
    alerta,
    revision,
    *,
    resolver,
):
    resultado.setdefault(
        "revisiones_ingeniero",
        [],
    ).append(revision)

    if resolver:
        alerta_resuelta = deepcopy(alerta)
        alerta_resuelta.update(
            {
                "estado": "resuelta",
                "resuelta": True,
                "revision_id": revision[
                    "revision_id"
                ],
                "fecha_resolucion": revision[
                    "fecha_revision"
                ],
                "resuelta_por": revision["revisor"],
                "excluido_del_computo": False,
            }
        )
        resultado.setdefault(
            "alertas_resueltas",
            [],
        ).append(alerta_resuelta)
        resultado["alertas_analisis"] = [
            item
            for item in resultado.get(
                "alertas_analisis",
                [],
            )
            if item.get("id") != alerta.get("id")
        ]
    else:
        alerta["estado_revision"] = (
            "revisada_sin_resolver"
        )
        alerta["ultima_revision_id"] = revision[
            "revision_id"
        ]
        alerta["ultima_revision_fecha"] = revision[
            "fecha_revision"
        ]
        alerta["ultima_revision_por"] = revision[
            "revisor"
        ]

    resultado["resumen_alertas"] = _resumir_alertas(
        resultado.get("alertas_analisis", []),
        len(resultado.get("alertas_resueltas", [])),
    )
    resultado["ultima_revision_ingeniero"] = revision


def _medida_positiva(
    valor,
    nombre,
    *,
    maximo=200.0,
):
    numero = _numero(valor)

    if numero is None or numero <= 0:
        raise ValueError(
            f"{nombre} debe ser un número mayor que cero."
        )

    if numero > maximo:
        raise ValueError(
            f"{nombre} no puede superar {maximo:g} m."
        )

    return round(numero, 4)


def _buscar_tramo(resultado, alerta):
    tramo_id = str(alerta.get("elemento_id") or "")
    tramo = next(
        (
            fila
            for fila in resultado.get(
                "vigas_riostra_computo_detalle",
                [],
            )
            if str(fila.get("tramo_id")) == tramo_id
        ),
        None,
    )

    if tramo is None:
        raise LookupError(
            f"No se encontró el tramo {tramo_id}."
        )

    return tramo


def _asegurar_alerta_acero_tramo(resultado, tramo):
    estado = tramo.get("estado_acero")

    if estado in (None, "computado"):
        return

    categorias = {
        "seccion_no_coincide_con_detalle": (
            "inconsistencia_seccion"
        ),
        "pendiente_armadura": "armadura_no_detectada",
        "pendiente_revision_detalle": "armadura_ambigua",
    }
    categoria = categorias.get(estado, estado)
    tramo_id = str(tramo.get("tramo_id"))
    alerta_id = f"vigas-acero-{tramo_id}-{categoria}"

    if any(
        item.get("id") == alerta_id
        for item in resultado.get("alertas_analisis", [])
    ):
        return

    resultado.setdefault("alertas_analisis", []).append(
        {
            "id": alerta_id,
            "severidad": "advertencia",
            "familia": "vigas",
            "categoria": categoria,
            "titulo": (
                "Acero del tramo pendiente — "
                f"{tramo_id}"
            ),
            "mensaje": (
                "La geometría fue validada, pero todavía "
                "falta validar la armadura del tramo."
            ),
            "elemento_id": tramo_id,
            "referencia": tramo.get("referencia"),
            "evidencia": [],
            "accion_recomendada": (
                "Seleccionar y confirmar el detalle de "
                "armadura correspondiente."
            ),
            "bloquea_resultado": False,
            "excluido_del_computo": True,
        }
    )


def _aplicar_revision_geometria_viga(
    resultado,
    alerta,
    *,
    valores,
    motivo,
    revisor,
):
    copia = deepcopy(resultado)
    alerta_copia = _buscar_alerta_activa(
        copia,
        alerta.get("id"),
    )
    tramo = _buscar_tramo(copia, alerta_copia)

    ancho = _medida_positiva(
        valores.get("ancho_m", tramo.get("ancho_m")),
        "El ancho",
        maximo=5.0,
    )
    alto = _medida_positiva(
        valores.get("alto_m", tramo.get("alto_m")),
        "El alto",
        maximo=5.0,
    )
    longitud_entre_ejes = _medida_positiva(
        valores.get(
            "longitud_entre_ejes_m",
            tramo.get("longitud_entre_ejes_m")
            or tramo.get("longitud_m"),
        ),
        "La longitud entre ejes",
        maximo=1000.0,
    )
    longitud_libre = _medida_positiva(
        valores.get(
            "longitud_libre_m",
            tramo.get("longitud_libre_entre_caras_m")
            or longitud_entre_ejes,
        ),
        "La longitud libre",
        maximo=1000.0,
    )
    longitud_computo = _medida_positiva(
        valores.get(
            "longitud_m",
            tramo.get("longitud_m")
            or longitud_entre_ejes,
        ),
        "La longitud de cómputo",
        maximo=1000.0,
    )

    antes = {
        campo: tramo.get(campo)
        for campo in (
            "estado",
            "ancho_m",
            "alto_m",
            "longitud_m",
            "longitud_entre_ejes_m",
            "longitud_libre_entre_caras_m",
        )
    }
    tramo.update(
        {
            "estado": "computado",
            "ancho_m": ancho,
            "alto_m": alto,
            "longitud_m": longitud_computo,
            "longitud_entre_ejes_m": longitud_entre_ejes,
            "longitud_libre_entre_caras_m": longitud_libre,
            "volumen_hormigon_m3": round(
                ancho * alto * longitud_computo,
                3,
            ),
            "encofrado_laterales_m2": round(
                2 * alto * longitud_computo,
                3,
            ),
            "encofrado_fondo_m2": round(
                ancho * longitud_computo,
                3,
            ),
        }
    )
    tramo["encofrado_total_m2"] = round(
        tramo["encofrado_laterales_m2"]
        + (
            tramo["encofrado_fondo_m2"]
            if tramo.get("encofrado_incluye_fondo")
            else 0.0
        ),
        3,
    )

    armadura = tramo.get("armadura_viga")

    if isinstance(armadura, dict):
        validacion = copia.get(
            "validacion_acero_vigas_riostra",
            {},
        )
        tramo.update(
            calcular_acero_tramo_validado_manualmente(
                tramo,
                armadura,
                tolerancia_seccion_m=_numero(
                    validacion.get(
                        "tolerancia_seccion_m"
                    ),
                    0.025,
                ),
                longitud_adicional_por_extremo_m=_numero(
                    validacion.get(
                        "longitud_adicional_por_extremo_m"
                    ),
                    0.0,
                ),
            )
        )
    else:
        tramo["estado_acero"] = "pendiente_armadura"

    revision = _revision_base(
        alerta_copia,
        accion="validar_geometria",
        motivo=motivo,
        revisor=revisor,
    )
    revision.update(
        {
            "tramo_id": tramo.get("tramo_id"),
            "valores_antes": antes,
            "valores_despues": {
                campo: tramo.get(campo)
                for campo in (
                    "estado",
                    "ancho_m",
                    "alto_m",
                    "longitud_m",
                    "longitud_entre_ejes_m",
                    "longitud_libre_entre_caras_m",
                    "volumen_hormigon_m3",
                    "encofrado_total_m2",
                    "estado_acero",
                )
            },
            "estado": "validado_por_ingeniero",
        }
    )
    _registrar_revision(
        copia,
        alerta_copia,
        revision,
        resolver=True,
    )
    _asegurar_alerta_acero_tramo(copia, tramo)
    _recalcular_resumen_vigas(copia)
    copia["resumen_alertas"] = _resumir_alertas(
        copia.get("alertas_analisis", []),
        len(copia.get("alertas_resueltas", [])),
    )
    return copia


def _aplicar_revision_armadura_viga(
    resultado,
    alerta,
    *,
    valores,
    confirmaciones,
    motivo,
    revisor,
):
    if not confirmaciones.get("confirmar_armadura"):
        raise ValueError(
            "Debe confirmarse explícitamente la armadura seleccionada."
        )

    copia = deepcopy(resultado)
    alerta_copia = _buscar_alerta_activa(
        copia,
        alerta.get("id"),
    )
    tramo = _buscar_tramo(copia, alerta_copia)
    referencia = str(
        valores.get("referencia_armadura")
        or tramo.get("referencia")
        or ""
    ).strip().upper()
    armadura = next(
        (
            item
            for item in copia.get(
                "armaduras_vigas_riostra",
                [],
            )
            if str(item.get("referencia") or "")
            .strip()
            .upper()
            == referencia
            and item.get("estado") == "CORRECTO"
        ),
        None,
    )

    if armadura is None:
        raise ValueError(
            "No existe un detalle de armadura correcto para la "
            f"referencia {referencia or 'indicada'}."
        )

    validacion = copia.get(
        "validacion_acero_vigas_riostra",
        {},
    )
    tramo.update(
        calcular_acero_tramo_validado_manualmente(
            tramo,
            armadura,
            tolerancia_seccion_m=_numero(
                validacion.get("tolerancia_seccion_m"),
                0.025,
            ),
            longitud_adicional_por_extremo_m=_numero(
                validacion.get(
                    "longitud_adicional_por_extremo_m"
                ),
                0.0,
            ),
        )
    )

    if tramo.get("estado_acero") != "computado":
        raise ValueError(
            "La armadura seleccionada no es compatible con la "
            "sección del tramo. Valide primero la sección."
        )

    revision = _revision_base(
        alerta_copia,
        accion="asignar_armadura",
        motivo=motivo,
        revisor=revisor,
    )
    revision.update(
        {
            "tramo_id": tramo.get("tramo_id"),
            "referencia_armadura": referencia,
            "peso_acero_total_kg": tramo.get(
                "peso_acero_total_kg"
            ),
            "estado": "validado_por_ingeniero",
        }
    )
    _registrar_revision(
        copia,
        alerta_copia,
        revision,
        resolver=True,
    )
    _recalcular_resumen_vigas(copia)
    return copia


def _normalizar_alturas(valores):
    alturas_crudas = valores.get(
        "alturas_por_referencia",
        {},
    )

    if isinstance(alturas_crudas, list):
        alturas_crudas = {
            item.get("referencia"): item.get("altura_m")
            for item in alturas_crudas
            if isinstance(item, dict)
        }

    if not isinstance(alturas_crudas, dict):
        raise ValueError(
            "alturas_por_referencia debe ser un objeto."
        )

    alturas = {}

    for referencia, altura in alturas_crudas.items():
        clave = str(referencia or "").strip().upper()

        if not clave:
            continue

        alturas[clave] = _medida_positiva(
            altura,
            f"La altura de {clave}",
        )

    if not alturas:
        raise ValueError(
            "Debe indicarse al menos una altura verificada."
        )

    return alturas


def _normalizar_alturas_tramos(valores):
    alturas_crudas = valores.get("alturas_por_tramo", {})

    if isinstance(alturas_crudas, list):
        alturas_crudas = {
            item.get("tramo_id"): item.get("altura_m")
            for item in alturas_crudas
            if isinstance(item, dict)
        }

    if not isinstance(alturas_crudas, dict):
        raise ValueError("alturas_por_tramo debe ser un objeto.")

    alturas = {}
    for tramo_id, altura in alturas_crudas.items():
        clave = str(tramo_id or "").strip()
        if not clave:
            continue
        alturas[clave] = _medida_positiva(
            altura,
            f"La altura del tramo {clave}",
            maximo=20.0,
        )

    if not alturas:
        raise ValueError(
            "Debe indicarse al menos una altura de tramo verificada."
        )
    return alturas


def _referencia_columna(fila):
    return str(
        fila.get("referencia_columna")
        or fila.get("referencia_columna_vinculada")
        or fila.get("referencia")
        or ""
    ).strip().upper()


def _clave_elemento_columna(fila):
    posicion = (
        fila.get("posicion_rotulo_columna_pdf")
        or fila.get(
            "posicion_rotulo_columna_vinculada_pdf"
        )
        or {}
    )
    return (
        fila.get("pagina"),
        _referencia_columna(fila),
        round(_numero(posicion.get("x"), 0.0), 3),
        round(_numero(posicion.get("y"), 0.0), 3),
        fila.get("fundacion_id"),
    )


def _actualizar_computo_familia(
    resultado,
    familia,
    *,
    cantidad,
    hormigon,
    encofrado,
    estado,
):
    computos = resultado.setdefault(
        "computos_por_elemento",
        {},
    )
    datos = computos.setdefault(familia, {})
    datos.update(
        {
            "cantidad": cantidad,
            "estado": estado,
        }
    )
    datos["hormigon"] = {
        "valor": hormigon,
        "unidad": "m3",
        "estado": "calculado",
    }
    acero_anterior = datos.get("acero", {})
    datos["acero"] = {
        "valor": acero_anterior.get("valor"),
        "unidad": "kg",
        "estado": acero_anterior.get(
            "estado",
            "pendiente_armadura",
        ),
    }
    datos["encofrado"] = {
        "valor": encofrado,
        "unidad": "m2",
        "estado": "calculado",
    }


def _resolver_alerta_por_regla(
    resultado,
    alerta_id,
    *,
    criterio,
):
    alerta = next(
        (
            item
            for item in resultado.get("alertas_analisis", [])
            if item.get("id") == alerta_id
        ),
        None,
    )

    if alerta is None:
        return

    fecha = datetime.now(timezone.utc).isoformat()
    resolucion_id = uuid4().hex
    alerta_resuelta = deepcopy(alerta)
    alerta_resuelta.update(
        {
            "estado": "resuelta_automaticamente",
            "resuelta": True,
            "resolucion_id": resolucion_id,
            "fecha_resolucion": fecha,
            "resuelta_por": "motor_de_computo",
            "criterio_resolucion": criterio,
            "excluido_del_computo": False,
        }
    )
    resultado.setdefault("alertas_resueltas", []).append(
        alerta_resuelta
    )
    resultado.setdefault("resoluciones_automaticas", []).append(
        {
            "resolucion_id": resolucion_id,
            "alerta_id": alerta_id,
            "familia": alerta.get("familia"),
            "fecha_resolucion": fecha,
            "criterio": criterio,
        }
    )
    resultado["alertas_analisis"] = [
        item
        for item in resultado.get("alertas_analisis", [])
        if item.get("id") != alerta_id
    ]


def _recalcular_acero_pedestales(resultado):
    detalle_actual = resultado.get(
        "pedestales_computo_detalle",
        [],
    )

    if not detalle_actual:
        return None

    calculo = calcular_acero_pedestales(
        detalle_actual,
        resultado.get("armaduras_columnas", []),
        resultado.get("armaduras_pedestales", []),
    )
    detalle = calculo["detalles"]
    validacion_columnas = resultado.get(
        "validacion_columnas",
        {},
    )
    validacion = resultado.setdefault(
        "validacion_pedestales",
        {},
    )
    columnas_confirmadas = (
        validacion_columnas.get(
            "armaduras_columnas_confirmadas"
        )
        is True
    )

    for fila in detalle:
        heredada = (
            fila.get("origen_armadura_pedestal")
            == "heredada_de_columna"
        )
        fila["armadura_heredada_confirmada"] = (
            columnas_confirmadas if heredada else None
        )

        if heredada and columnas_confirmadas:
            fila["estado_armadura_pedestal"] = (
                "computada_por_herencia_columna_confirmada"
            )

    altura_real_disponible = (
        validacion.get("altura_real_disponible") is True
    )
    hereda_columnas = bool(
        calculo["referencias_heredadas_de_columnas"]
    )
    armaduras_confirmadas = (
        calculo["resultado_completo"]
        and (not hereda_columnas or columnas_confirmadas)
    )
    resultado_preliminar = (
        not altura_real_disponible
        or not armaduras_confirmadas
        or not calculo["resultado_completo"]
    )

    resultado.update(
        {
            "pedestales_computo_detalle": detalle,
            "resumen_pedestales_por_tipo": detalle,
            "resumen_acero_pedestales": calculo[
                "resumen_acero"
            ],
            "acero_pedestales_kg": calculo[
                "acero_total_kg"
            ],
        }
    )
    validacion.update(
        {
            "acero_disponible": (
                calculo["acero_total_kg"] is not None
            ),
            "acero_resultado_completo": calculo[
                "resultado_completo"
            ],
            "acero_resultado_parcial": calculo[
                "resultado_parcial"
            ],
            "acero_resultado_preliminar": resultado_preliminar,
            "armaduras_pedestales_confirmadas": (
                armaduras_confirmadas
            ),
            "cantidad_tipos_acero_computados": calculo[
                "cantidad_tipos_computados"
            ],
            "cantidad_tipos_acero_pendientes": calculo[
                "cantidad_tipos_pendientes"
            ],
            "cantidad_pedestales_acero_computados": calculo[
                "cantidad_pedestales_computados"
            ],
            "referencias_armadura_heredada": calculo[
                "referencias_heredadas_de_columnas"
            ],
            "referencias_armadura_explicita": calculo[
                "referencias_con_armadura_explicita"
            ],
            "referencias_acero_pedestal_computadas": calculo[
                "referencias_computadas"
            ],
            "referencias_acero_pedestal_pendientes": calculo[
                "referencias_pendientes"
            ],
            "referencias_sin_armadura_candidata": calculo[
                "referencias_pendientes"
            ],
            "criterio_armadura": calculo[
                "criterio_armadura"
            ],
            "criterio_longitudinal_acero": calculo[
                "criterio_longitudinal"
            ],
            "criterio_estribos": calculo[
                "criterio_estribos"
            ],
        }
    )

    computos = resultado.setdefault(
        "computos_por_elemento",
        {},
    )
    familia = computos.setdefault("pedestales", {})
    familia["acero"] = {
        "valor": calculo["acero_total_kg"],
        "unidad": "kg",
        "estado": (
            "calculado"
            if calculo["resultado_completo"]
            and not resultado_preliminar
            else (
                "preliminar"
                if calculo["resultado_completo"]
                else (
                    "parcial"
                    if calculo["acero_total_kg"] is not None
                    else "pendiente_armadura"
                )
            )
        ),
    }
    familia["estado"] = (
        "calculado"
        if altura_real_disponible
        and calculo["resultado_completo"]
        and armaduras_confirmadas
        else (
            "preliminar"
            if calculo["resultado_completo"]
            else "parcial"
        )
    )

    if calculo["resultado_completo"]:
        _resolver_alerta_por_regla(
            resultado,
            "pedestales-armadura-no-disponible",
            criterio=(
                "Sin armadura explícita de pedestal se aplicó la "
                "armadura válida de la columna con la misma referencia."
            ),
        )

    return calculo


def _aplicar_alturas_columnas(
    resultado,
    alerta,
    *,
    valores,
    motivo,
    revisor,
):
    copia = deepcopy(resultado)
    alerta_copia = _buscar_alerta_activa(
        copia,
        alerta.get("id"),
    )
    segmentos_porticos = [
        fila
        for fila in copia.get("columnas_porticos_segmentos", [])
        if fila.get("apto_revision_altura")
    ]
    usa_porticos = bool(segmentos_porticos)

    if usa_porticos:
        alturas_tramos = _normalizar_alturas_tramos(valores)
        filas_unicas = segmentos_porticos
        ids_esperados = {
            str(fila.get("tramo_id") or "").strip()
            for fila in filas_unicas
            if fila.get("tramo_id")
        }
        faltantes_tramos = sorted(ids_esperados - set(alturas_tramos))
        desconocidos = sorted(set(alturas_tramos) - ids_esperados)
        if faltantes_tramos:
            raise ValueError(
                "Faltan alturas para "
                f"{len(faltantes_tramos)} tramos de pórtico."
            )
        if desconocidos:
            raise ValueError(
                "Hay alturas que no corresponden a los tramos detectados."
            )
        alturas = {}
    else:
        alturas = _normalizar_alturas(valores)
        alturas_tramos = {}
        filas_origen = [
            *copia.get("columnas_fundaciones", []),
            *copia.get("columnas_vinculadas_por_viga", []),
        ]
        filas_unicas = []
        claves = set()

        for fila in filas_origen:
            clave = _clave_elemento_columna(fila)

            if clave in claves:
                continue

            claves.add(clave)
            filas_unicas.append(fila)

        referencias_legacy = {
            _referencia_columna(fila)
            for fila in filas_unicas
            if _referencia_columna(fila)
        }
        faltantes = sorted(
            referencias_legacy - set(alturas),
            key=_clave_referencia,
        )
        if faltantes:
            raise ValueError(
                "Faltan alturas para: "
                + ", ".join(faltantes)
                + "."
            )

    referencias = {
        _referencia_columna(fila)
        for fila in filas_unicas
        if _referencia_columna(fila)
    }

    if not filas_unicas:
        raise ValueError(
            "No hay columnas asociadas para recalcular."
        )

    detalle = []

    for indice, fila in enumerate(filas_unicas, start=1):
        referencia = _referencia_columna(fila)
        ancho = _medida_positiva(
            fila.get("ancho_m"),
            f"El ancho de {referencia}",
            maximo=5.0,
        )
        largo = _medida_positiva(
            fila.get("largo_m"),
            f"El largo de {referencia}",
            maximo=5.0,
        )
        altura = (
            alturas_tramos[fila["tramo_id"]]
            if usa_porticos
            else alturas[referencia]
        )
        volumen = round(ancho * largo * altura, 3)
        encofrado = round(
            2 * (ancho + largo) * altura,
            3,
        )
        fila.update(
            {
                "altura_m": altura,
                "volumen_hormigon_m3": volumen,
                "encofrado_total_m2": encofrado,
                "estado_computo": (
                    "geometria_validada_por_ingeniero"
                ),
            }
        )
        detalle.append(
            {
                "columna_id": (
                    fila.get("tramo_id")
                    or fila.get("columna_id")
                    or f"{referencia}-{indice:02d}"
                ),
                "fundacion_id": fila.get("fundacion_id"),
                "tramo_id": fila.get("tramo_id"),
                "eje_global": fila.get("eje_global"),
                "nivel_inferior": fila.get("nivel_inferior"),
                "nivel_superior": fila.get("nivel_superior"),
                "paginas_fuente": fila.get("paginas"),
                "referencia": referencia,
                "ancho_m": ancho,
                "largo_m": largo,
                "altura_m": altura,
                "cantidad": 1,
                "volumen_unitario_m3": volumen,
                "volumen_total_m3": volumen,
                "encofrado_unitario_m2": encofrado,
                "encofrado_total_m2": encofrado,
                "acero_kg": None,
                "estado": "geometria_validada",
            }
        )

    grupos = defaultdict(list)

    for fila in detalle:
        grupos[
            (
                fila["referencia"],
                fila["ancho_m"],
                fila["largo_m"],
                fila["altura_m"],
            )
        ].append(fila)

    resumen = []

    for clave, filas in sorted(
        grupos.items(),
        key=lambda item: _clave_referencia(
            item[0][0]
        ),
    ):
        referencia, ancho, largo, altura = clave
        resumen.append(
            {
                "referencia": referencia,
                "ancho_m": ancho,
                "largo_m": largo,
                "altura_m": altura,
                "cantidad": len(filas),
                "volumen_total_m3": _sumar(
                    filas,
                    "volumen_total_m3",
                ),
                "encofrado_total_m2": _sumar(
                    filas,
                    "encofrado_total_m2",
                ),
            }
        )

    hormigon = _sumar(detalle, "volumen_total_m3")
    encofrado = _sumar(detalle, "encofrado_total_m2")
    copia.update(
        {
            "columnas_computo_detalle": detalle,
            "resumen_columnas_por_tipo": resumen,
            "hormigon_columnas_m3": hormigon,
            "encofrado_columnas_m2": encofrado,
            "acero_columnas_kg": None,
            "estado_computo_columnas": {
                "hormigon": "calculado",
                "acero": "pendiente_armadura",
                "encofrado": "calculado",
            },
        }
    )
    validacion = copia.setdefault(
        "validacion_columnas",
        {},
    )
    validacion.update(
        {
            "altura_real_disponible": True,
            "alturas_validadas_por_ingeniero": True,
            "referencias_con_altura": sorted(
                referencias,
                key=_clave_referencia,
            ),
            "alturas_obtenidas_de_porticos": usa_porticos,
            "tramos_con_altura_validada": (
                len(detalle) if usa_porticos else 0
            ),
        }
    )
    _actualizar_computo_familia(
        copia,
        "columnas",
        cantidad=len(detalle),
        hormigon=hormigon,
        encofrado=encofrado,
        estado="parcial_sin_acero",
    )
    revision = _revision_base(
        alerta_copia,
        accion="validar_alturas",
        motivo=motivo,
        revisor=revisor,
    )
    revision.update(
        {
            "alturas_por_referencia_m": alturas,
            "alturas_por_tramo_m": alturas_tramos,
            "cantidad_elementos_recalculados": len(
                detalle
            ),
            "hormigon_resultante_m3": hormigon,
            "encofrado_resultante_m2": encofrado,
            "estado": "validado_por_ingeniero",
        }
    )
    _registrar_revision(
        copia,
        alerta_copia,
        revision,
        resolver=True,
    )
    return copia


def _aplicar_alturas_pedestales(
    resultado,
    alerta,
    *,
    valores,
    motivo,
    revisor,
):
    copia = deepcopy(resultado)
    alerta_copia = _buscar_alerta_activa(
        copia,
        alerta.get("id"),
    )
    alturas = _normalizar_alturas(valores)
    detalle = copia.get(
        "pedestales_computo_detalle",
        [],
    )
    referencias = {
        str(
            fila.get("referencia_columna")
            or fila.get("referencia")
            or ""
        ).strip().upper()
        for fila in detalle
        if (
            fila.get("referencia_columna")
            or fila.get("referencia")
        )
    }
    faltantes = sorted(
        referencias - set(alturas),
        key=_clave_referencia,
    )

    if not detalle:
        raise ValueError(
            "No hay pedestales para recalcular."
        )

    if faltantes:
        raise ValueError(
            "Faltan alturas para: "
            + ", ".join(faltantes)
            + "."
        )

    usar_encofrado = any(
        _numero(fila.get("encofrado_unitario_m2"), 0.0)
        > 0
        for fila in detalle
    )

    for fila in detalle:
        referencia = str(
            fila.get("referencia_columna")
            or fila.get("referencia")
            or ""
        ).strip().upper()
        ancho = _medida_positiva(
            fila.get("dimension_pedestal_1_m"),
            f"El ancho del pedestal {referencia}",
            maximo=5.0,
        )
        largo = _medida_positiva(
            fila.get("dimension_pedestal_2_m"),
            f"El largo del pedestal {referencia}",
            maximo=5.0,
        )
        altura = alturas[referencia]
        cantidad = int(_numero(fila.get("cantidad"), 0))
        volumen_unitario = round(
            ancho * largo * altura,
            3,
        )
        encofrado_unitario = (
            round(
                2 * (ancho + largo) * altura,
                3,
            )
            if usar_encofrado
            else 0.0
        )
        fila.update(
            {
                "altura_real_m": altura,
                "altura_m": altura,
                "volumen_unitario_m3": volumen_unitario,
                "volumen_total_m3": round(
                    volumen_unitario * cantidad,
                    3,
                ),
                "encofrado_unitario_m2": (
                    encofrado_unitario
                ),
                "encofrado_total_m2": round(
                    encofrado_unitario * cantidad,
                    3,
                ),
                "tipo_resultado": "VALIDADO_ALTURA_REAL",
                "estado": "geometria_validada",
            }
        )

    hormigon = _sumar(detalle, "volumen_total_m3")
    encofrado = _sumar(detalle, "encofrado_total_m2")
    copia.update(
        {
            "hormigon_pedestales_m3": hormigon,
            "encofrado_pedestales_m2": encofrado,
            "resumen_pedestales_por_tipo": detalle,
        }
    )
    validacion = copia.setdefault(
        "validacion_pedestales",
        {},
    )
    validacion.update(
        {
            "altura_real_disponible": True,
            "alturas_validadas_por_ingeniero": True,
            "resultado_preliminar": False,
            "referencias_con_altura": sorted(
                referencias,
                key=_clave_referencia,
            ),
        }
    )
    calculo_acero = _recalcular_acero_pedestales(copia)
    estado_pedestales = (
        copia.get("computos_por_elemento", {})
        .get("pedestales", {})
        .get(
            "estado",
            (
                "parcial_sin_acero"
                if calculo_acero is None
                else "parcial"
            ),
        )
    )
    _actualizar_computo_familia(
        copia,
        "pedestales",
        cantidad=sum(
            int(_numero(fila.get("cantidad"), 0))
            for fila in detalle
        ),
        hormigon=hormigon,
        encofrado=encofrado,
        estado=estado_pedestales,
    )
    revision = _revision_base(
        alerta_copia,
        accion="validar_alturas",
        motivo=motivo,
        revisor=revisor,
    )
    revision.update(
        {
            "alturas_por_referencia_m": alturas,
            "cantidad_tipos_recalculados": len(detalle),
            "hormigon_resultante_m3": hormigon,
            "encofrado_resultante_m2": encofrado,
            "estado": "validado_por_ingeniero",
        }
    )
    _registrar_revision(
        copia,
        alerta_copia,
        revision,
        resolver=True,
    )
    return copia


def _aplicar_armaduras_columnas(
    resultado,
    alerta,
    *,
    valores,
    confirmaciones,
    motivo,
    revisor,
):
    if not confirmaciones.get("confirmar_armaduras"):
        raise ValueError(
            "Debe confirmarse explícitamente la armadura de las columnas."
        )

    copia = deepcopy(resultado)
    alerta_copia = _buscar_alerta_activa(
        copia,
        alerta.get("id"),
    )
    conflictos_porticos = [
        item
        for item in copia.get("alertas_analisis", [])
        if item.get("familia") == "columnas"
        and item.get("categoria") in {
            "inconsistencia_portico_columna",
            "seccion_columna_portico_pendiente",
        }
    ]
    if conflictos_porticos:
        raise ValueError(
            "Primero deben completarse las revisiones de pórticos; "
            f"quedan {len(conflictos_porticos)} tramo(s) pendientes."
        )
    conflictos_porticos = [
        item
        for item in copia.get("alertas_analisis", [])
        if item.get("familia") == "columnas"
        and item.get("categoria") in {
            "inconsistencia_portico_columna",
            "seccion_columna_portico_pendiente",
        }
    ]
    if conflictos_porticos:
        raise ValueError(
            "Primero deben completarse las revisiones de pórticos; "
            f"quedan {len(conflictos_porticos)} tramo(s) pendientes."
        )
    validacion = copia.setdefault(
        "validacion_columnas",
        {},
    )

    if validacion.get("altura_real_disponible") is not True:
        raise ValueError(
            "Primero deben validarse las alturas reales de las columnas."
        )

    referencias_confirmadas = valores.get(
        "referencias_confirmadas",
    )

    if not isinstance(referencias_confirmadas, list):
        raise ValueError(
            "referencias_confirmadas debe ser una lista."
        )

    calculo = calcular_acero_columnas(
        copia.get("columnas_computo_detalle", []),
        copia.get("armaduras_columnas", []),
        referencias_confirmadas=(
            referencias_confirmadas
        ),
        longitud_adicional_por_extremo_m=valores.get(
            "longitud_adicional_por_extremo_m",
            0.0,
        ),
    )
    detalle = calculo["detalles"]
    copia.update(
        {
            "columnas_computo_detalle": detalle,
            "resumen_columnas_por_tipo": calculo[
                "resumen_por_tipo"
            ],
            "resumen_acero_columnas": calculo[
                "resumen_acero"
            ],
            "acero_columnas_kg": calculo[
                "acero_total_kg"
            ],
        }
    )

    # Refleja el resultado también en las filas que alimentan la tabla
    # visual. Se utilizan colas porque una referencia puede aparecer en
    # más de una ubicación de la planta.
    detalle_por_elemento = defaultdict(list)

    for fila in detalle:
        detalle_por_elemento[
            (
                fila.get("fundacion_id"),
                _referencia_columna(fila),
            )
        ].append(fila)

    for nombre in (
        "columnas_fundaciones",
        "columnas_vinculadas_por_viga",
    ):
        for fila in copia.get(nombre, []):
            candidatos = detalle_por_elemento.get(
                (
                    fila.get("fundacion_id"),
                    _referencia_columna(fila),
                ),
                [],
            )

            if not candidatos:
                continue

            calculada = candidatos.pop(0)
            fila.update(
                {
                    "armadura_columna": calculada.get(
                        "armadura_columna"
                    ),
                    "cantidad_estribos": calculada.get(
                        "cantidad_estribos"
                    ),
                    "peso_acero_total_kg": calculada.get(
                        "peso_acero_total_kg"
                    ),
                    "estado_acero": "computado",
                }
            )

    validacion.update(
        {
            "armaduras_columnas_confirmadas": True,
            "acero_disponible": True,
            "referencias_armadura_confirmadas": calculo[
                "referencias_confirmadas"
            ],
            "longitud_adicional_por_extremo_m": calculo[
                "longitud_adicional_por_extremo_m"
            ],
            "criterio_longitudinal_acero": calculo[
                "criterio_longitudinal"
            ],
            "criterio_estribos": calculo[
                "criterio_estribos"
            ],
        }
    )
    estado = copia.setdefault(
        "estado_computo_columnas",
        {},
    )
    estado.update(
        {
            "hormigon": "calculado",
            "acero": "calculado",
            "encofrado": "calculado",
        }
    )
    computos = copia.setdefault(
        "computos_por_elemento",
        {},
    )
    computo_columnas = computos.setdefault(
        "columnas",
        {},
    )
    computo_columnas.update(
        {
            "cantidad": len(detalle),
            "estado": "calculado",
            "acero": {
                "valor": calculo["acero_total_kg"],
                "unidad": "kg",
                "estado": "calculado",
            },
        }
    )
    calculo_acero_pedestales = _recalcular_acero_pedestales(
        copia
    )
    revision = _revision_base(
        alerta_copia,
        accion="asignar_armadura",
        motivo=motivo,
        revisor=revisor,
    )
    revision.update(
        {
            "referencias_confirmadas": calculo[
                "referencias_confirmadas"
            ],
            "longitud_adicional_por_extremo_m": calculo[
                "longitud_adicional_por_extremo_m"
            ],
            "cantidad_elementos_recalculados": len(
                detalle
            ),
            "acero_resultante_kg": calculo[
                "acero_total_kg"
            ],
            "acero_pedestales_recalculado_kg": (
                calculo_acero_pedestales[
                    "acero_total_kg"
                ]
                if calculo_acero_pedestales
                else None
            ),
            "criterio_respaldo_pedestales": (
                calculo_acero_pedestales[
                    "criterio_armadura"
                ]
                if calculo_acero_pedestales
                else None
            ),
            "estado": "validado_por_ingeniero",
        }
    )
    _registrar_revision(
        copia,
        alerta_copia,
        revision,
        resolver=True,
    )
    return copia


def _evidencia_alerta(alerta, etiqueta):
    etiqueta_buscada = etiqueta.casefold()

    for item in alerta.get("evidencia", []):
        if str(item.get("etiqueta") or "").casefold() == (
            etiqueta_buscada
        ):
            return item.get("valor")

    return None


def _aplicar_conflicto_portico(
    resultado,
    alerta,
    *,
    valores,
    confirmaciones,
    motivo,
    revisor,
):
    if not confirmaciones.get("confirmar_conflicto_portico"):
        raise ValueError(
            "Debe confirmarse explícitamente la decisión sobre el pórtico."
        )

    copia = deepcopy(resultado)
    alerta_copia = _buscar_alerta_activa(copia, alerta.get("id"))
    tramo_id = str(alerta_copia.get("elemento_id") or "").strip()
    tramo = next(
        (
            item
            for item in copia.get("columnas_porticos_segmentos", [])
            if str(item.get("tramo_id") or "") == tramo_id
        ),
        None,
    )
    if tramo is None:
        raise LookupError("No se encontró el tramo de pórtico a corregir.")

    referencia = str(
        valores.get("referencia_columna")
        or tramo.get("referencia")
        or ""
    ).strip().upper()
    if not re.fullmatch(r"C\d{1,3}[A-Z]?", referencia):
        raise ValueError(
            "La referencia de columna debe tener un formato como C13."
        )
    altura = _medida_positiva(
        valores.get("altura_m"),
        "La altura del tramo",
        maximo=20.0,
    )

    opciones_seccion = {
        (
            round(_numero(seccion.get("dimension_1_m"), 0.0), 4),
            round(_numero(seccion.get("dimension_2_m"), 0.0), 4),
        )
        for seccion in copia.get("secciones_columnas", [])
        if str(seccion.get("referencia") or "").strip().upper() == referencia
        and seccion.get("estado") == "CORRECTO"
        and _numero(seccion.get("dimension_1_m"), 0.0) > 0
        and _numero(seccion.get("dimension_2_m"), 0.0) > 0
    }
    if len(opciones_seccion) == 1:
        ancho, largo = next(iter(opciones_seccion))
    else:
        ancho = _medida_positiva(
            valores.get("ancho_m"),
            f"El ancho de {referencia}",
            maximo=5.0,
        )
        largo = _medida_positiva(
            valores.get("largo_m"),
            f"El largo de {referencia}",
            maximo=5.0,
        )

    tramo.update(
        {
            "referencia": referencia,
            "altura_detectada_m": altura,
            "ancho_m": ancho,
            "largo_m": largo,
            "estado_extraccion": "detectado_confirmable",
            "estado_seccion": "detectada",
            "apto_revision_altura": True,
            "conflictos": [],
            "resuelto_por_ingeniero": True,
        }
    )
    validacion = copia.setdefault("validacion_columnas", {})
    validacion["tramos_porticos_con_conflicto"] = max(
        0,
        sum(
            item.get("estado_extraccion") == "conflicto_entre_vistas"
            for item in copia.get("columnas_porticos_segmentos", [])
        ),
    )
    validacion["tramos_porticos_listos_revision"] = sum(
        bool(item.get("apto_revision_altura"))
        for item in copia.get("columnas_porticos_segmentos", [])
    )

    revision = _revision_base(
        alerta_copia,
        accion="resolver_inconsistencia_portico",
        motivo=motivo,
        revisor=revisor,
    )
    revision.update(
        {
            "tramo_id": tramo_id,
            "eje_global": tramo.get("eje_global"),
            "nivel_inferior": tramo.get("nivel_inferior"),
            "nivel_superior": tramo.get("nivel_superior"),
            "referencia_columna": referencia,
            "altura_m": altura,
            "ancho_m": ancho,
            "largo_m": largo,
            "estado": "validado_por_ingeniero",
        }
    )
    _registrar_revision(copia, alerta_copia, revision, resolver=True)
    return copia


def _aplicar_seccion_portico(
    resultado,
    alerta,
    *,
    valores,
    confirmaciones,
    motivo,
    revisor,
):
    if not confirmaciones.get("confirmar_seccion_portico"):
        raise ValueError(
            "Debe confirmarse explícitamente la sección de la columna."
        )

    copia = deepcopy(resultado)
    alerta_copia = _buscar_alerta_activa(copia, alerta.get("id"))
    referencia = str(
        valores.get("referencia_columna")
        or alerta_copia.get("referencia")
        or alerta_copia.get("elemento_id")
        or ""
    ).strip().upper()
    if not re.fullmatch(r"C\d{1,3}[A-Z]?", referencia):
        raise ValueError(
            "La referencia de columna debe tener un formato como C13."
        )
    ancho = _medida_positiva(
        valores.get("ancho_m"),
        f"El ancho de {referencia}",
        maximo=5.0,
    )
    largo = _medida_positiva(
        valores.get("largo_m"),
        f"El largo de {referencia}",
        maximo=5.0,
    )

    actualizados = 0
    for tramo in copia.get("columnas_porticos_segmentos", []):
        if (
            _referencia_columna(tramo) != referencia
            or tramo.get("estado_extraccion") != "detectado_confirmable"
        ):
            continue
        tramo.update(
            {
                "ancho_m": ancho,
                "largo_m": largo,
                "estado_seccion": "detectada",
                "apto_revision_altura": (
                    tramo.get("altura_detectada_m") is not None
                ),
                "seccion_validada_por_ingeniero": True,
            }
        )
        actualizados += 1

    if not actualizados:
        raise ValueError(
            "No hay tramos confirmables con esa referencia para actualizar."
        )

    copia.setdefault("secciones_columnas", []).append(
        {
            "referencia_original": referencia,
            "referencia": referencia,
            "dimension_1_m": ancho,
            "dimension_2_m": largo,
            "origen": "revision_profesional_porticos",
            "pagina": None,
            "fue_corregida": False,
            "estado": "CORRECTO",
            "validada_por_ingeniero": True,
        }
    )
    validacion = copia.setdefault("validacion_columnas", {})
    validacion["tramos_porticos_listos_revision"] = sum(
        bool(item.get("apto_revision_altura"))
        for item in copia.get("columnas_porticos_segmentos", [])
    )

    revision = _revision_base(
        alerta_copia,
        accion="validar_seccion_portico",
        motivo=motivo,
        revisor=revisor,
    )
    revision.update(
        {
            "referencia_columna": referencia,
            "ancho_m": ancho,
            "largo_m": largo,
            "cantidad_tramos_actualizados": actualizados,
            "estado": "validado_por_ingeniero",
        }
    )
    _registrar_revision(copia, alerta_copia, revision, resolver=True)
    return copia


def _buscar_relacion_columna(resultado, alerta):
    fundacion = _evidencia_alerta(
        alerta,
        "Fundación",
    )
    referencia = str(
        alerta.get("referencia")
        or alerta.get("elemento_id")
        or ""
    ).strip().upper()

    for nombre in (
        "relaciones_columnas_fundaciones",
        "columnas_pendientes_clasificacion",
        "columnas_vinculadas_por_viga",
        "columnas_fundaciones",
    ):
        for fila in resultado.get(nombre, []):
            coincide_fundacion = (
                fundacion is None
                or str(fila.get("fundacion_id"))
                == str(fundacion)
            )
            coincide_referencia = (
                not referencia
                or _referencia_columna(fila)
                == referencia
            )

            if coincide_fundacion and coincide_referencia:
                return fila, nombre

    return None, None


def _sin_duplicar_por_identidad(filas, nueva):
    clave_nueva = _clave_elemento_columna(nueva)

    if any(
        _clave_elemento_columna(fila) == clave_nueva
        for fila in filas
    ):
        return

    filas.append(nueva)


def _recalcular_validacion_columnas(resultado):
    directas = resultado.get("columnas_fundaciones", [])
    vinculadas = resultado.get(
        "columnas_vinculadas_por_viga",
        [],
    )
    pendientes = resultado.get(
        "columnas_pendientes_clasificacion",
        [],
    )
    validacion = resultado.setdefault(
        "validacion_columnas",
        {},
    )
    validacion.update(
        {
            "cantidad_columnas_asociadas": len(directas),
            "columnas_directas_asociadas": len(directas),
            "columnas_vinculadas_por_viga": len(
                vinculadas
            ),
            "columnas_pendientes_clasificacion": len(
                pendientes
            ),
            "asociaciones_para_revisar": len(pendientes),
            "fundaciones_con_vigas_vinculadas": len(
                {
                    fila.get("fundacion_id")
                    for fila in vinculadas
                    if fila.get("fundacion_id")
                }
            ),
        }
    )


def _aplicar_revision_relacion_columna(
    resultado,
    alerta,
    *,
    accion,
    valores,
    motivo,
    revisor,
):
    copia = deepcopy(resultado)
    alerta_copia = _buscar_alerta_activa(
        copia,
        alerta.get("id"),
    )
    relacion, lista_origen = _buscar_relacion_columna(
        copia,
        alerta_copia,
    )

    if relacion is None:
        relacion = {
            "fundacion_id": (
                valores.get("fundacion_id")
                or _evidencia_alerta(
                    alerta_copia,
                    "Fundación",
                )
            ),
            "pagina": valores.get("pagina"),
        }

    categoria = alerta_copia.get("categoria")

    if accion == "descartar_asociacion":
        if categoria not in {
            "pendiente_clasificacion_estructural",
            "vinculacion_geometrica_pendiente",
            "columnas_pendientes_clasificacion",
        }:
            raise ValueError(
                "Esta alerta no puede resolverse descartando "
                "la asociación; debe indicarse la relación válida."
            )

        fundacion_id = relacion.get("fundacion_id")
        referencia_actual = _referencia_columna(relacion)

        for nombre in (
            "columnas_pendientes_clasificacion",
            "columnas_vinculadas_por_viga",
        ):
            copia[nombre] = [
                fila
                for fila in copia.get(nombre, [])
                if not (
                    fila.get("fundacion_id") == fundacion_id
                    and _referencia_columna(fila)
                    == referencia_actual
                )
            ]
        relacion["estado"] = (
            "descartada_por_ingeniero"
        )
        relacion["requiere_revision_asociacion"] = False
    else:
        referencia = str(
            valores.get("referencia_columna")
            or _referencia_columna(relacion)
            or ""
        ).strip().upper()

        if not referencia:
            raise ValueError(
                "Debe indicarse la referencia de columna."
            )

        ancho = _medida_positiva(
            valores.get(
                "ancho_m",
                relacion.get("ancho_m"),
            ),
            "El ancho de la columna",
            maximo=5.0,
        )
        largo = _medida_positiva(
            valores.get(
                "largo_m",
                relacion.get("largo_m"),
            ),
            "El largo de la columna",
            maximo=5.0,
        )
        tipo = str(
            valores.get("tipo_apoyo")
            or (
                "vinculada_por_viga"
                if lista_origen
                == "columnas_vinculadas_por_viga"
                or relacion.get("tipo_asociacion")
                == "adicional_por_proximidad"
                else "apoyo_directo"
            )
        ).strip().lower()

        if tipo not in {
            "apoyo_directo",
            "vinculada_por_viga",
        }:
            raise ValueError(
                "tipo_apoyo debe ser apoyo_directo o "
                "vinculada_por_viga."
            )

        relacion.update(
            {
                "referencia_columna": referencia,
                "referencia_columna_vinculada": (
                    referencia
                    if tipo == "vinculada_por_viga"
                    else relacion.get(
                        "referencia_columna_vinculada"
                    )
                ),
                "ancho_m": ancho,
                "largo_m": largo,
                "estado": "lista_para_visualizar",
                "requiere_revision_asociacion": False,
                "requiere_revision_geometrica": False,
                "clasificacion_relacion": (
                    "validada_por_ingeniero"
                ),
            }
        )
        for tramo in copia.get("columnas_porticos_segmentos", []):
            if (
                _referencia_columna(tramo) == referencia
                and tramo.get("estado_extraccion")
                == "detectado_confirmable"
            ):
                tramo.update(
                    {
                        "ancho_m": ancho,
                        "largo_m": largo,
                        "estado_seccion": "detectada",
                        "apto_revision_altura": (
                            tramo.get("altura_detectada_m") is not None
                        ),
                    }
                )
        destino = (
            "columnas_vinculadas_por_viga"
            if tipo == "vinculada_por_viga"
            else "columnas_fundaciones"
        )
        _sin_duplicar_por_identidad(
            copia.setdefault(destino, []),
            relacion,
        )
        copia["columnas_pendientes_clasificacion"] = [
            fila
            for fila in copia.get(
                "columnas_pendientes_clasificacion",
                [],
            )
            if not (
                fila.get("fundacion_id")
                == relacion.get("fundacion_id")
                and _referencia_columna(fila)
                == referencia
            )
        ]

    revision = _revision_base(
        alerta_copia,
        accion=accion,
        motivo=motivo,
        revisor=revisor,
    )
    revision.update(
        {
            "fundacion_id": relacion.get("fundacion_id"),
            "referencia_columna": _referencia_columna(
                relacion
            ),
            "decision": (
                "confirmada"
                if accion == "confirmar_asociacion"
                else "descartada"
            ),
            "estado": "validado_por_ingeniero",
        }
    )
    _registrar_revision(
        copia,
        alerta_copia,
        revision,
        resolver=True,
    )
    _recalcular_validacion_columnas(copia)
    return copia


def _aplicar_revision_documentada(
    resultado,
    alerta,
    *,
    accion,
    valores,
    motivo,
    revisor,
):
    copia = deepcopy(resultado)
    alerta_copia = _buscar_alerta_activa(
        copia,
        alerta.get("id"),
    )
    excluida = bool(
        alerta_copia.get("excluido_del_computo")
    )

    if excluida and accion != "registrar_observacion":
        raise ValueError(
            "Esta alerta excluye cantidades del cómputo. No puede "
            "cerrarse con una confirmación documental; complete "
            "los datos técnicos o registre una observación abierta."
        )

    revision = _revision_base(
        alerta_copia,
        accion=accion,
        motivo=motivo,
        revisor=revisor,
    )
    revision.update(
        {
            "valores_documentados": deepcopy(valores),
            "resuelve_alerta": not excluida,
            "estado": (
                "confirmada_por_ingeniero"
                if not excluida
                else "observacion_registrada"
            ),
        }
    )
    _registrar_revision(
        copia,
        alerta_copia,
        revision,
        resolver=not excluida,
    )
    return copia


def aplicar_revision_ingeniero(
    resultado,
    *,
    alerta_id,
    accion,
    motivo,
    revisor,
    valores=None,
    confirmaciones=None,
):
    """Aplica una decisión profesional según la familia de la alerta.

    Las alertas con datos suficientes se recalculan y se cierran. Una
    observación sobre un elemento excluido queda abierta para evitar que
    una firma convierta datos faltantes en cantidades supuestamente válidas.
    """

    if not isinstance(resultado, dict):
        raise TypeError(
            "El resultado del análisis debe ser un diccionario."
        )

    accion_limpia = str(accion or "").strip().lower()

    if accion_limpia not in ACCIONES_REVISION_VALIDAS:
        raise ValueError(
            "La acción de revisión indicada no es válida."
        )

    motivo_limpio, revisor_limpio = (
        _validar_identidad_revision(motivo, revisor)
    )
    valores = valores if isinstance(valores, dict) else {}
    confirmaciones = (
        confirmaciones
        if isinstance(confirmaciones, dict)
        else {}
    )
    alerta = _buscar_alerta_activa(resultado, alerta_id)
    familia = alerta.get("familia")
    categoria = alerta.get("categoria")

    if (
        familia == "vigas"
        and categoria == "inconsistencia_seccion"
    ):
        if accion_limpia != "validar_seccion":
            raise ValueError(
                "Esta alerta requiere validar la sección del tramo."
            )

        actualizado = aplicar_revision_seccion_viga(
            resultado,
            alerta_id=alerta_id,
            tramo_id=alerta.get("elemento_id"),
            fuente_seleccionada=valores.get(
                "fuente_seleccionada",
                "detalle",
            ),
            ancho_m=valores.get("ancho_m"),
            alto_m=valores.get("alto_m"),
            motivo=motivo_limpio,
            revisor=revisor_limpio,
            confirmar_armadura_detalle=bool(
                confirmaciones.get(
                    "confirmar_armadura_detalle"
                )
            ),
        )
        revision = actualizado.get(
            "ultima_revision_ingeniero",
            {},
        )
        revision.update(
            {
                "familia": "vigas",
                "accion": "validar_seccion",
                "categoria_alerta": categoria,
            }
        )
        return actualizado

    if familia == "vigas" and categoria in {
        "sin_seccion",
        "pendiente_escala",
        "pendiente_revision_geometrica",
        "geometria_no_computada",
        "sin_longitud_vectorial",
    }:
        if accion_limpia != "validar_geometria":
            raise ValueError(
                "Esta alerta requiere validar la geometría del tramo."
            )

        return _aplicar_revision_geometria_viga(
            resultado,
            alerta,
            valores=valores,
            motivo=motivo_limpio,
            revisor=revisor_limpio,
        )

    if familia == "vigas" and categoria in {
        "armadura_no_detectada",
        "armadura_ambigua",
        "pendiente_armadura",
        "pendiente_revision_detalle",
    }:
        if accion_limpia != "asignar_armadura":
            raise ValueError(
                "Esta alerta requiere seleccionar y confirmar una armadura."
            )

        return _aplicar_revision_armadura_viga(
            resultado,
            alerta,
            valores=valores,
            confirmaciones=confirmaciones,
            motivo=motivo_limpio,
            revisor=revisor_limpio,
        )

    if (
        familia == "columnas"
        and categoria == "inconsistencia_portico_columna"
    ):
        if accion_limpia != "resolver_inconsistencia_portico":
            raise ValueError(
                "Esta alerta requiere seleccionar la referencia y la altura "
                "correctas del tramo."
            )
        return _aplicar_conflicto_portico(
            resultado,
            alerta,
            valores=valores,
            confirmaciones=confirmaciones,
            motivo=motivo_limpio,
            revisor=revisor_limpio,
        )

    if (
        familia == "columnas"
        and categoria == "seccion_columna_portico_pendiente"
    ):
        if accion_limpia != "validar_seccion_portico":
            raise ValueError(
                "Esta alerta requiere validar la sección de la columna."
            )
        return _aplicar_seccion_portico(
            resultado,
            alerta,
            valores=valores,
            confirmaciones=confirmaciones,
            motivo=motivo_limpio,
            revisor=revisor_limpio,
        )

    if (
        familia == "columnas"
        and categoria == "armadura_no_disponible"
    ):
        if accion_limpia != "asignar_armadura":
            raise ValueError(
                "Esta alerta requiere confirmar las armaduras de columnas."
            )

        return _aplicar_armaduras_columnas(
            resultado,
            alerta,
            valores=valores,
            confirmaciones=confirmaciones,
            motivo=motivo_limpio,
            revisor=revisor_limpio,
        )

    if categoria == "alturas_reales_no_disponibles":
        if accion_limpia != "validar_alturas":
            raise ValueError(
                "Esta alerta requiere ingresar alturas reales."
            )

        if familia == "columnas":
            return _aplicar_alturas_columnas(
                resultado,
                alerta,
                valores=valores,
                motivo=motivo_limpio,
                revisor=revisor_limpio,
            )

        if familia == "pedestales":
            return _aplicar_alturas_pedestales(
                resultado,
                alerta,
                valores=valores,
                motivo=motivo_limpio,
                revisor=revisor_limpio,
            )

    if familia == "columnas" and categoria in {
        "sin_columna_asociada",
        "sin_seccion_detectada",
        "pendiente_clasificacion_estructural",
        "vinculacion_geometrica_pendiente",
        "fundaciones_sin_columna",
        "fundaciones_sin_seccion",
        "columnas_pendientes_clasificacion",
    }:
        if accion_limpia not in {
            "confirmar_asociacion",
            "descartar_asociacion",
        }:
            raise ValueError(
                "Esta alerta requiere confirmar o descartar la asociación."
            )

        return _aplicar_revision_relacion_columna(
            resultado,
            alerta,
            accion=accion_limpia,
            valores=valores,
            motivo=motivo_limpio,
            revisor=revisor_limpio,
        )

    return _aplicar_revision_documentada(
        resultado,
        alerta,
        accion=accion_limpia,
        valores=valores,
        motivo=motivo_limpio,
        revisor=revisor_limpio,
    )

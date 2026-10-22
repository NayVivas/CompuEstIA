"""Controles técnicos generales, trazables y previos a los cómputos.

Las reglas trabajan con evidencias del documento y decisiones profesionales
acotadas por huella y página. Nunca alteran el PDF original.
"""

from collections import Counter, defaultdict
from dataclasses import asdict
from hashlib import sha256
import json
import logging
from pathlib import Path
import re

from computos.columnas.armaduras import consolidar_armaduras_columnas, extraer_armaduras_columnas
from computos.columnas.deteccion import PATRON_COLUMNA, extraer_secciones_columnas
from computos.documentos.analisis import extraer_palabras_normalizadas
from computos.documentos.correcciones_tecnicas import corregir_filas, validar_correcciones, validar_resoluciones
from computos.documentos.procesamiento_pdf import extraer_palabras
from computos.referencias import descubrir_catalogo_referencias, extraer_candidatos_referencias

logger = logging.getLogger(__name__)


def _ref_texto(valor):
    return re.sub(r"[^A-Z0-9]", "", str(valor).upper())


def auditar_documentos(rutas, diagnostico, correcciones=None, resoluciones=None):
    correcciones = validar_correcciones(correcciones or [])
    resoluciones = validar_resoluciones(resoluciones or [])
    mapas = {
        (r["sha256"], r["pagina"], r["referencia_original"]): r
        for r in resoluciones if r["accion"] == "reasignar_referencia_detalle"
    }
    selecciones = {
        (r["campo"], r["referencia"]): r
        for r in resoluciones if r["accion"] == "seleccionar_fuente_columna"
    }
    claves_resoluciones_aplicadas = set()
    resoluciones_aplicadas = []
    resoluciones_obsoletas = []
    ids_resoluciones_obsoletas = set()
    revisiones_aplicadas = []
    errores_correccion = []
    incidencias = []
    controles = []
    secciones = defaultdict(list)
    secciones_pendientes = defaultdict(list)
    armaduras_pendientes = defaultdict(list)
    armaduras = []
    usos_columnas = defaultdict(list)
    detalles_columnas = defaultdict(list)
    detalles_originales = defaultdict(list)
    cuadros = []
    plantas = []

    def registrar_resolucion(decision):
        if decision not in resoluciones_aplicadas:
            resoluciones_aplicadas.append(decision)

    def descartar_resolucion(decision, motivo):
        if id(decision) in ids_resoluciones_obsoletas:
            return
        ids_resoluciones_obsoletas.add(id(decision))
        resoluciones_obsoletas.append({
            **decision,
            "estado": "obsoleta",
            "motivo_descarte": motivo,
        })

    fuente_detalles = (diagnostico.get("fuentes_por_rol") or {}).get("detalles") or {}
    fuentes_detalles = fuente_detalles.get("fuentes") or ([fuente_detalles] if fuente_detalles else [])
    claves_fuente_detalles = {(f.get("sha256"), f.get("pagina")) for f in fuentes_detalles}

    def fuente(doc, numero, texto, **extras):
        return {
            "documento_id": doc["documento_id"], "sha256": doc["sha256"],
            "archivo": doc["nombre"], "pagina": numero, "texto": texto, **extras,
        }

    def incidencia(codigo, referencia, titulo, mensaje, fuentes, accion,
                   tipo="advertencia", familia=None, bloqueo="elemento", opciones=None):
        identidad = json.dumps([
            codigo, referencia,
            sorted((f["sha256"], f["pagina"], f["texto"]) for f in fuentes),
        ], ensure_ascii=False)
        item = {
            "id": sha256(identidad.encode()).hexdigest()[:24], "codigo": codigo,
            "referencia": referencia, "titulo": titulo, "mensaje": mensaje,
            "severidad": tipo, "familia": familia, "bloqueo": bloqueo,
            "estado": "pendiente", "fuentes": fuentes,
            "accion_recomendada": accion, "opciones_resolucion": opciones or [],
            "resuelta": False,
        }
        incidencias.append(item)
        return item

    for doc in diagnostico["documentos"]:
        ruta = Path(rutas[doc["documento_id"]])
        try:
            normalizadas = extraer_palabras_normalizadas(ruta)
            raw = extraer_palabras(ruta)
        except Exception:
            logger.exception("Auditoría: no se pudo leer %s", doc["documento_id"])
            controles.append({"archivo": doc["nombre"], "pagina": None, "control": "lectura",
                              "estado": "no_evaluado", "motivo": "No se pudo leer el PDF para los controles técnicos."})
            continue

        for ficha in doc["paginas"]:
            numero = ficha["pagina"]
            normalizadas_pagina = [p for p in normalizadas if p.pagina == numero]
            palabras = [p for p in raw if p["pagina"] == numero]
            objetivos = (ficha.get("clasificacion_automatica") or ficha.get("clasificacion", {})).get("objetivos", {})
            contenidos = set(objetivos.get("contenidos", {}).get("etiquetas", []))
            roles = set(objetivos.get("roles_documentales", {}).get("etiquetas", []))

            def control(nombre, estado, motivo=""):
                controles.append({"archivo": doc["nombre"], "pagina": numero,
                                  "control": nombre, "estado": estado, "motivo": motivo})

            if ficha.get("caracteres", 0) < 10:
                control("texto_nativo", "no_evaluado", "Página sin texto nativo suficiente.")
                continue

            es_fuente_detalles = not claves_fuente_detalles or (doc["sha256"], numero) in claves_fuente_detalles
            if "fundaciones" in contenidos and "cuadro_planilla" in roles and es_fuente_detalles:
                try:
                    catalogo = descubrir_catalogo_referencias(normalizadas_pagina)
                    if not catalogo.contexto_local_confirmado:
                        raise ValueError("Se encontró una tabla, pero no se confirmó que su región corresponda a fundaciones. No se emiten inconsistencias estructurales a partir de ella.")
                    try:
                        referencias, aplicadas = corregir_filas(catalogo, doc["sha256"], numero, correcciones)
                    except ValueError as error:
                        errores_correccion.append(str(error))
                        raise
                    revisiones_aplicadas.extend(aplicadas)
                    cuadros.append({
                        "referencias": set(referencias),
                        "prefijos": {c.referencia.prefijo for c in catalogo.referencias},
                        "fuente": fuente(doc, numero, "Cuadro de fundaciones"),
                    })
                    for referencia, cantidad in Counter(referencias).items():
                        if cantidad <= 1:
                            continue
                        fuentes = [fuente(
                            doc, numero, getattr(c, "texto_original", c.referencia.canonica),
                            caja_visual=asdict(c.caja_visual), fila=indice + 1,
                        ) for indice, c in enumerate(catalogo.referencias)
                            if c.referencia.canonica == referencia]
                        incidencia(
                            "referencia_duplicada_cuadro", referencia,
                            f"Referencia repetida en el cuadro — {referencia}",
                            f"Hay {cantidad} filas con la misma referencia en el cuadro interpretado. No se ha renombrado ninguna.",
                            fuentes, "Comparar las filas con la planta y documentar qué referencia corresponde a cada una.",
                            "error", "fundaciones", "familia", ["corregir_fila_cuadro"],
                        )
                    if aplicadas:
                        fuentes = [fuente(
                            doc, numero, d["referencia_original"], fila=d["fila"],
                            referencia_correcta=d["referencia_correcta"], revisor=d["revisor"], motivo=d["motivo"],
                        ) for d in aplicadas]
                        item = incidencia(
                            "referencia_corregida_cuadro", ", ".join(d["referencia_original"] for d in aplicadas),
                            "Referencias del cuadro corregidas por el profesional",
                            "Se aplicó la corrección a los datos interpretados. Se conserva el rótulo original del PDF.",
                            fuentes, "Verificar el cómputo resultante.", "informacion", "fundaciones", "ninguno",
                        )
                        item.update(estado="corregida_y_revalidada", resuelta=True)
                    control("referencias_cuadro", "evaluado", "; ".join(catalogo.advertencias))
                except ValueError as error:
                    control("referencias_cuadro", "no_evaluado", str(error))
                except Exception:
                    logger.exception("Falló el cuadro de página %s", numero)
                    control("referencias_cuadro", "no_evaluado", "Error al interpretar el cuadro; necesita revisión manual.")

            fuente_planta = (diagnostico.get("fuentes_por_rol") or {}).get("planta") or {}
            fuentes_planta = fuente_planta.get("fuentes") or ([fuente_planta] if fuente_planta else [])
            claves_planta = {(f.get("sha256"), f.get("pagina")) for f in fuentes_planta}
            if "planta" in roles and "fundaciones" in contenidos and (not claves_planta or (doc["sha256"], numero) in claves_planta):
                plantas.append((doc, numero, extraer_candidatos_referencias(normalizadas_pagina)))

            # Solo un título explícito crea un detalle; las repeticiones de Cn
            # dentro de plantas no se convierten en detalles por proximidad.
            lineas = defaultdict(list)
            for palabra in palabras:
                lineas[(palabra["numero_bloque"], palabra["numero_linea"])].append(palabra)
            claves_titulo = set()
            titulos = {}
            for clave, palabras_linea in lineas.items():
                texto = " ".join(p["texto"] for p in sorted(palabras_linea, key=lambda p: p["numero_palabra"]))
                if not re.search(r"\bDETALLE\s+(?:DE\s+)?(?:COLUMNA|PILAR)\b", texto, re.I):
                    continue
                for palabra in palabras_linea:
                    referencia = _ref_texto(palabra["texto"])
                    if PATRON_COLUMNA.fullmatch(referencia):
                        claves_titulo.add(clave)
                        titulos[referencia] = texto

            if claves_titulo:
                correcciones_pagina = {
                    referencia: decision["referencia_correcta"]
                    for (huella, pagina, referencia), decision in mapas.items()
                    if huella == doc["sha256"] and pagina == numero
                }
                for referencia, texto in titulos.items():
                    registro = fuente(
                        doc, numero, texto, referencia_original=referencia,
                        referencia_corregida=correcciones_pagina.get(referencia),
                        compatible_motor=(doc["sha256"], numero) in claves_fuente_detalles,
                    )
                    detalles_originales[referencia].append(registro)
                    referencia_final = correcciones_pagina.get(referencia, referencia)
                    detalles_columnas[referencia_final].append(registro)
                    if referencia in correcciones_pagina:
                        claves_resoluciones_aplicadas.add(("mapa", doc["sha256"], numero, referencia))

                filtradas = [p for p in palabras
                             if not PATRON_COLUMNA.fullmatch(_ref_texto(p["texto"]))
                             or (p["numero_bloque"], p["numero_linea"]) in claves_titulo]
                origen = f"{doc['documento_id']}:{numero}"
                try:
                    resultados_secciones = extraer_secciones_columnas(filtradas, origen, correcciones=correcciones_pagina)
                    resultados_armaduras = extraer_armaduras_columnas(filtradas, origen, correcciones=correcciones_pagina)
                    for seccion in resultados_secciones:
                        original = seccion.get("referencia_original", seccion["referencia"])
                        if seccion["estado"] != "CORRECTO":
                            secciones_pendientes[seccion["referencia"]].append({
                                "fuente": fuente(doc, numero, titulos.get(original, original)),
                                "cantidad_cotas": seccion.get("cantidad_cotas"),
                                "cotas_detectadas": seccion.get("cotas_detectadas", []),
                            })
                            continue
                        secciones[seccion["referencia"]].append({
                            "dimensiones_m": sorted([float(seccion["dimension_1_m"]), float(seccion["dimension_2_m"])]),
                            "fuente": fuente(doc, numero, titulos.get(original, original)),
                        })
                    for armadura in resultados_armaduras:
                        original = armadura.get("referencia_original", armadura["referencia"])
                        armadura["fuente_auditoria"] = fuente(doc, numero, titulos.get(original, original))
                        armaduras.append(armadura)
                        if armadura["estado"] != "CORRECTO":
                            armaduras_pendientes[armadura["referencia"]].append({
                                "fuente": armadura["fuente_auditoria"],
                                "advertencias": armadura.get("advertencias", []),
                            })
                    pendientes = sum(x["estado"] != "CORRECTO" for x in resultados_secciones + resultados_armaduras)
                    control("detalles_columnas", "parcial" if pendientes else "evaluado",
                            f"{pendientes} extracciones de sección/armadura pendientes. Extracción candidata por texto y proximidad; no valida niveles.")
                except Exception:
                    logger.exception("Falló extracción de columnas")
                    control("detalles_columnas", "no_evaluado", "No se pudieron interpretar las secciones/armaduras de esta página.")

            if "columnas_pilares" in contenidos and roles.intersection({"planta", "elevacion_porticos"}):
                for palabra in palabras:
                    referencia = _ref_texto(palabra["texto"])
                    if PATRON_COLUMNA.fullmatch(referencia):
                        registro = fuente(doc, numero, referencia)
                        if registro not in usos_columnas[referencia]:
                            usos_columnas[referencia].append(registro)

    for decision in resoluciones:
        if decision["accion"] != "definir_seccion_columna":
            continue
        referencia = decision["referencia"]
        pendientes = secciones_pendientes.get(referencia, [])
        elegida = next((p for p in pendientes
                        if p["fuente"]["sha256"] == decision["sha256"]
                        and p["fuente"]["pagina"] == decision["pagina"]), None)
        if not elegida or secciones.get(referencia):
            descartar_resolucion(
                decision,
                "La extracción pendiente ya no existe o fue resuelta por una fuente válida.",
            )
            continue
        dimensiones = sorted([decision["dimension_1_m"], decision["dimension_2_m"]])
        secciones[referencia].append({
            "dimensiones_m": dimensiones,
            "fuente": {**elegida["fuente"], "texto": "Sección definida por revisión profesional"},
            "manual": True,
        })
        claves_resoluciones_aplicadas.add(("seccion_manual", referencia))
        registrar_resolucion(decision)
        item = incidencia(
            "seccion_columna_definida", referencia,
            f"Sección de columna definida — {referencia}",
            "La extracción automática no fue suficiente y se aplicaron dimensiones ingresadas por el profesional.",
            [{**elegida["fuente"], "dimensiones_m": dimensiones,
              "revisor": decision["revisor"], "motivo": decision["motivo"]}],
            "Verificar la asociación y las cantidades resultantes.",
            "informacion", "columnas", "ninguno",
        )
        item.update(estado="corregida_y_revalidada", resuelta=True)

    for decision in resoluciones:
        if decision["accion"] != "reasignar_referencia_detalle":
            continue
        clave = ("mapa", decision["sha256"], decision["pagina"], decision["referencia_original"])
        if clave not in claves_resoluciones_aplicadas:
            descartar_resolucion(
                decision,
                "El título de detalle ya no forma parte de los conflictos vigentes.",
            )
            continue
        if decision["referencia_correcta"] not in usos_columnas:
            descartar_resolucion(
                decision,
                "La referencia de destino dejó de aparecer en las plantas o pórticos interpretados.",
            )
            continue
        registro = next(f for f in detalles_originales[decision["referencia_original"]]
                        if f["sha256"] == decision["sha256"] and f["pagina"] == decision["pagina"])
        item = incidencia(
            "referencia_detalle_reasignada", decision["referencia_correcta"],
            f"Detalle reasignado — {decision['referencia_original']} → {decision['referencia_correcta']}",
            "La decisión profesional se aplicó a la interpretación de esta fuente; el rótulo del PDF se conserva como evidencia.",
            [{**registro, "referencia_correcta": decision["referencia_correcta"],
              "revisor": decision["revisor"], "motivo": decision["motivo"]}],
            "Revisar las cantidades y asociaciones resultantes.", "informacion", "columnas", "ninguno",
        )
        item.update(estado="corregida_y_revalidada", resuelta=True)
        registrar_resolucion(decision)

    for referencia, pendientes in sorted(secciones_pendientes.items()):
        if secciones.get(referencia):
            continue
        fuentes = [{**p["fuente"], "cantidad_cotas": p["cantidad_cotas"],
                    "cotas_detectadas": p["cotas_detectadas"]} for p in pendientes]
        incidencia(
            "seccion_columna_no_interpretable", referencia,
            f"Sección de columna pendiente — {referencia}",
            "Se localizó el detalle, pero no se pudieron confirmar exactamente dos cotas de sección.",
            fuentes,
            "Ingresar las dos dimensiones verificadas en metros o incorporar una fuente más clara.",
            familia="columnas", bloqueo="elemento",
            opciones=["definir_seccion_columna"],
        )

    referencias_armadura_correcta = {
        a["referencia"] for a in armaduras if a.get("estado") == "CORRECTO"
    }
    for referencia, pendientes in sorted(armaduras_pendientes.items()):
        if referencia in referencias_armadura_correcta:
            continue
        incidencia(
            "armadura_columna_no_interpretable", referencia,
            f"Armadura de columna pendiente — {referencia}",
            "Se localizó el detalle, pero faltan barras longitudinales o una especificación completa de estribos.",
            [{**p["fuente"], "advertencias": p["advertencias"]} for p in pendientes],
            "Revisar el detalle o incorporar una lámina más clara. No se calculará acero para esta referencia.",
            familia="columnas", bloqueo="elemento",
        )

    for referencia, alternativas in secciones.items():
        if len({tuple(a["dimensiones_m"]) for a in alternativas}) <= 1:
            continue
        fuentes = [{**a["fuente"], "dimensiones_m": a["dimensiones_m"]} for a in alternativas]
        item = incidencia(
            "secciones_diferentes", referencia, f"Secciones candidatas diferentes — {referencia}",
            "Se extrajeron dimensiones distintas bajo la misma referencia. Verificar si pertenecen al mismo nivel y elemento antes de decidir que hay un error.",
            fuentes, "Comparar los detalles y elegir la fuente aplicable, o corregir el rótulo si pertenece a otra referencia.",
            familia="columnas", bloqueo="elemento",
            opciones=["seleccionar_fuente_columna", "reasignar_referencia_detalle"],
        )
        decision = selecciones.get(("seccion", referencia))
        if decision:
            elegida = next((f for f in fuentes if f["sha256"] == decision["sha256"] and f["pagina"] == decision["pagina"]), None)
            if not elegida:
                descartar_resolucion(
                    decision,
                    "La fuente elegida dejó de ser candidata para este conflicto.",
                )
                continue
            item.update(estado="resuelta_por_seleccion_profesional", resuelta=True,
                        resolucion={**decision, "valor_seleccionado": elegida["dimensiones_m"]})
            claves_resoluciones_aplicadas.add(("seleccion", "seccion", referencia))
            registrar_resolucion(decision)

    for consolidada in consolidar_armaduras_columnas(armaduras):
        if not consolidada.get("conflicto_entre_fuentes"):
            continue
        referencia = consolidada["referencia"]
        alternativas = [x for x in armaduras if x["referencia"] == referencia and x["estado"] == "CORRECTO"]
        fuentes = [{
            **x["fuente_auditoria"],
            "barras": [{clave: grupo[clave] for clave in ("cantidad", "diametro_pulgadas", "texto_original")}
                       for grupo in x["grupos_longitudinales"]],
            "estribo": x["estribo"],
        } for x in alternativas]
        item = incidencia(
            "armaduras_diferentes", referencia, f"Armaduras candidatas diferentes — {referencia}",
            "Hay especificaciones distintas para la misma referencia en los detalles interpretados. Pueden corresponder a niveles o versiones diferentes.",
            fuentes, "Validar a qué elemento y nivel corresponde cada detalle antes de calcular acero.",
            familia="columnas", bloqueo="elemento",
            opciones=["seleccionar_fuente_columna", "reasignar_referencia_detalle"],
        )
        decision = selecciones.get(("armadura", referencia))
        if decision:
            elegida = next((f for f in fuentes if f["sha256"] == decision["sha256"] and f["pagina"] == decision["pagina"]), None)
            if not elegida:
                descartar_resolucion(
                    decision,
                    "La fuente elegida dejó de ser candidata para este conflicto.",
                )
                continue
            item.update(estado="resuelta_por_seleccion_profesional", resuelta=True, resolucion=decision)
            claves_resoluciones_aplicadas.add(("seleccion", "armadura", referencia))
            registrar_resolucion(decision)

    if detalles_columnas:
        candidatos_motor = [
            {"referencia": referencia, **registro}
            for referencia, registros in sorted(detalles_originales.items())
            for registro in registros if registro.get("compatible_motor")
        ]
        for referencia, fuentes in sorted(usos_columnas.items()):
            if referencia in detalles_columnas:
                continue
            incidencia(
                "columna_sin_detalle_localizado", referencia,
                f"No se localizó un detalle de columna — {referencia}",
                "La referencia aparece en plantas o pórticos, pero no se encontró su título de detalle entre las páginas interpretadas. No prueba que el detalle no exista.",
                fuentes, "Localizar la lámina o, si el rótulo de un detalle está equivocado, reasignarlo con evidencia y motivo.",
                familia="columnas", bloqueo="elemento",
                opciones=["reasignar_referencia_detalle"] if candidatos_motor else [],
            )

    for doc, numero, candidatos in plantas:
        prefijos = set().union(*(c["prefijos"] for c in cuadros)) if cuadros else set()
        catalogadas = set().union(*(c["referencias"] for c in cuadros)) if cuadros else set()
        faltantes = {c.referencia.canonica for c in candidatos if c.referencia.prefijo in prefijos} - catalogadas
        for referencia in sorted(faltantes):
            incidencia(
                "fundacion_sin_fila_localizada", referencia,
                f"Referencia de planta sin fila localizada — {referencia}",
                "No se encontró esta referencia en los cuadros de fundaciones interpretados de la carga. Revisar correspondencia de niveles y alcance.",
                [fuente(doc, numero, referencia)] + [c["fuente"] for c in cuadros],
                "Comparar la planta y los cuadros; no renombrar otra fila por deducción automática.",
                "error", "fundaciones", "familia", ["corregir_fila_cuadro"],
            )

    aplicadas_filas = {(d["sha256"], d["pagina"], d["fila"]) for d in revisiones_aplicadas}
    if errores_correccion or any((d["sha256"], d["pagina"], d["fila"]) not in aplicadas_filas for d in correcciones):
        raise ValueError("; ".join(errores_correccion) or "Una corrección no corresponde a un cuadro interpretable de los PDF cargados.")
    for decision in resoluciones:
        if decision in resoluciones_aplicadas:
            continue
        if id(decision) in ids_resoluciones_obsoletas:
            continue
        descartar_resolucion(
            decision,
            "La incidencia asociada ya no está vigente después de revalidar los documentos.",
        )

    no_evaluados = sum(c["estado"] in {"no_evaluado", "parcial"} for c in controles)
    pendientes = [i for i in incidencias if not i["resuelta"]]
    bloqueos_familia = [i for i in pendientes if i["bloqueo"] == "familia"]
    catalogo_detalles = [
        {"referencia": referencia, **registro}
        for referencia, registros in sorted(detalles_originales.items()) for registro in registros
    ]
    return {
        "version": 3, "revisiones_aplicadas": revisiones_aplicadas,
        "resoluciones_aplicadas": resoluciones_aplicadas,
        "resoluciones_obsoletas": resoluciones_obsoletas,
        "estado": "parcial" if no_evaluados else "controles_preliminares_ejecutados",
        "incidencias": incidencias, "controles": controles,
        "catalogos": {"detalles_columnas": catalogo_detalles},
        "resumen": {
            "incidencias": len(pendientes), "bloqueos_familia": len(bloqueos_familia),
            "elementos_excluidos": sum(i["bloqueo"] == "elemento" for i in pendientes),
            "controles_no_evaluados": no_evaluados,
        },
        "politica_calculo": {
            "permite_calculo_parcial": not bloqueos_familia,
            "criterio": "Los bloqueos de familia detienen esa familia. Los conflictos de elemento excluyen solo el elemento afectado hasta su resolución.",
        },
        "alcance": "Revisión preliminar de referencias de cuadros y detalles de columnas interpretables. No comprueba por sí sola geometría completa, alturas, vigas, losas ni todos los niveles. Cero hallazgos no implica ausencia de errores.",
    }

"""Fases experimentales del flujo (columnas, pedestales y vigas riostra).

Estas funciones fueron el "banco de pruebas" con el que se validaron, paso a
paso, la detección de columnas, pedestales y vigas de riostra. Se movieron
aquí desde ``flujos/principal.py`` para separar el flujo de producción
(``procesar_fundaciones``, usado por la API y por el CLI) de estos
diagnósticos manuales, que ``main()`` sigue invocando en ese orden al
ejecutar ``python app.py`` desde la línea de comandos.

Ninguna de estas funciones participa del cómputo servido por la API
(``computos.api.servicio.procesar_archivos``): esa ruta solo llama a
``procesar_fundaciones``.
"""

from pathlib import Path

from computos.configuracion.proyecto import ConfiguracionProyecto

from computos.configuracion.parametros import (
    PNG_DIR,
    PROCESSED_DIR,
    REPORT_DIR,
    INCREMENTO_PEDESTAL_CM,
    ALTURA_MINIMA_PEDESTAL_M,
    USAR_ENCOFRADO_PEDESTALES,
    ESPESOR_VECTOR_VIGA_PT,
    TOLERANCIA_ESPESOR_VECTOR_PT,
    LONGITUD_MINIMA_LINEA_VIGA_PT,
    MARGEN_ZONA_ESTRUCTURAL_PT,
    ESCALA_IMAGEN_DIAGNOSTICO,
    DIFERENCIA_ANGULAR_MAXIMA_BORDES_GRADOS,
    DIFERENCIA_LONGITUD_MAXIMA_BORDES,
    SEPARACION_MAXIMA_BORDES_PT,
    SEPARACION_MINIMA_BORDES_PT,
    SUPERPOSICION_MINIMA_BORDES,
    TOLERANCIA_EJES_DUPLICADOS_PT,
)

from computos.fundaciones.deteccion import aplicar_correcciones

from computos.fundaciones.cuadros import (
    CAMPO_PEDESTAL,
    localizar_estructura_cuadro,
)

from computos.columnas.deteccion import (
    asociar_columnas_a_fundaciones,
    detectar_columnas,
    dibujar_asociaciones,
    extraer_secciones_columnas,
)

from computos.fundaciones.pedestales import (
    calcular_dimensiones_pedestales,
    contar_columnas_por_tipo,
    calcular_computos_pedestales,
)

from computos.vigas.riostra import (
    dibujar_bordes_vectoriales_vigas,
    dibujar_ejes_candidatos_vigas,
    detectar_vigas_riostra,
    eliminar_rotulos_duplicados,
    emparejar_bordes_paralelos,
    extraer_bordes_vectoriales_vigas,
    validar_secciones_por_referencia,
)

from computos.documentos.procesamiento_pdf import extraer_palabras

from computos.documentos.analisis import extraer_palabras_normalizadas

from computos.referencias import (
    descubrir_catalogo_referencias,
    detectar_referencias_del_catalogo,
)

from computos.salida.reportes import (
    guardar_csv,
    guardar_json,
)


def experimentar_columna_pedestal(
    ruta_detalles,
    configuracion_proyecto=None,
):

    print()
    print("=" * 60)
    print(
        "FASE 4 - EXPERIMENTO 1: "
        "EXTRAER COLUMNA PEDESTAL"
    )
    print("=" * 60)

    ruta_detalles = Path(ruta_detalles)
    palabras = extraer_palabras_normalizadas(ruta_detalles)
    catalogo = descubrir_catalogo_referencias(palabras)
    estructura = localizar_estructura_cuadro(
        palabras,
        catalogo,
    )
    configuracion_proyecto = (
        configuracion_proyecto
        or ConfiguracionProyecto.vacia()
    )
    filas_corregidas = aplicar_correcciones(
        [
            {
                "numero_fila": fila.numero_fila,
                "referencia": fila.referencia,
            }
            for fila in estructura.filas
        ],
        configuracion_proyecto.correcciones_referencias_cuadro,
        configuracion_proyecto.motivos_referencias_cuadro,
    )

    encabezado = estructura.encabezados.get(CAMPO_PEDESTAL)
    if encabezado is None:
        print(
            "El cuadro no incluye una columna de pedestal. "
            "Se omite este cálculo opcional."
        )
        return

    print(
        "Encabezado reconocido:",
        encabezado.texto_original,
    )
    print("Cantidad de filas:", len(estructura.filas))

    for fila, fila_corregida in zip(
        estructura.filas,
        filas_corregidas,
    ):
        celda = fila.celdas[CAMPO_PEDESTAL]
        print("-" * 40)
        print("Referencia:", fila_corregida["referencia"])
        if fila_corregida["fue_corregida"]:
            print("Referencia original:", fila.referencia_texto)
        print(
            "Texto pedestal:",
            celda.texto or "Sin información",
        )

def experimentar_asociacion_columnas(
    ruta_planta,
    referencias_fundaciones,
):

    print()
    print("=" * 60)
    print(
        "FASE 4 - EXPERIMENTO 2: "
        "ASOCIAR COLUMNAS Y FUNDACIONES"
    )
    print("=" * 60)

    # ======================================================
    # 1. CONVERTIR LA RUTA
    # ======================================================

    ruta_planta = Path(
        ruta_planta
    )

    # ======================================================
    # 2. EXTRAER LAS PALABRAS DE LA PLANTA
    # ======================================================

    palabras = extraer_palabras(
        ruta_planta
    )

    palabras_normalizadas = (
        extraer_palabras_normalizadas(
            ruta_planta
        )
    )

    # ======================================================
    # 3. DETECTAR LAS FUNDACIONES
    # ======================================================

    fundaciones = detectar_referencias_del_catalogo(
        palabras_normalizadas,
        referencias_fundaciones,
    )

    # ======================================================
    # 4. DETECTAR LAS COLUMNAS
    # ======================================================

    columnas = detectar_columnas(
        palabras
    )

    print(
        "Fundaciones detectadas:",
        len(fundaciones),
    )

    print(
        "Referencias de columnas detectadas:",
        len(columnas),
    )

    # ======================================================
    # 5. ASOCIAR CADA FUNDACIÓN CON LA COLUMNA MÁS CERCANA
    # ======================================================

    asociaciones = (
        asociar_columnas_a_fundaciones(
            fundaciones,
            columnas,
        )
    )

    print()
    print("=" * 60)
    print(
        "FASE 4 - EXPERIMENTO 4: "
        "VALIDAR ASOCIACIONES ÚNICAS"
    )
    print("=" * 60)

    # ======================================================
    # 1. CREAR UNA CLAVE PARA CADA POSICIÓN DE COLUMNA
    # ======================================================

    def crear_clave_columna(
        centro_x,
        centro_y,
    ):

        return (
            round(centro_x, 2),
            round(centro_y, 2),
        )

    # ======================================================
    # 2. GUARDAR TODAS LAS COLUMNAS DETECTADAS
    # ======================================================

    columnas_detectadas = {}

    for columna in columnas:

        clave = crear_clave_columna(
            columna["centro_x"],
            columna["centro_y"],
        )

        columnas_detectadas[clave] = columna

    # ======================================================
    # 3. CONTAR CUÁNTAS FUNDACIONES UTILIZAN CADA COLUMNA
    # ======================================================

    usos_columnas = {}

    for asociacion in asociaciones:

        if asociacion["columna"] is None:
            continue

        clave = crear_clave_columna(
            asociacion["columna_x"],
            asociacion["columna_y"],
        )

        if clave not in usos_columnas:

            usos_columnas[clave] = []

        usos_columnas[clave].append(
            asociacion
        )

    # ======================================================
    # 4. BUSCAR COLUMNAS QUE NO FUERON ASOCIADAS
    # ======================================================

    columnas_sin_fundacion = []

    for clave, columna in (
        columnas_detectadas.items()
    ):

        if clave not in usos_columnas:

            columnas_sin_fundacion.append(
                columna
            )

    # ======================================================
    # 5. BUSCAR COLUMNAS UTILIZADAS MÁS DE UNA VEZ
    # ======================================================

    columnas_repetidas = []

    for clave, asociaciones_columna in (
        usos_columnas.items()
    ):

        if len(asociaciones_columna) > 1:

            columnas_repetidas.append(
                {
                    "clave": clave,
                    "asociaciones": (
                        asociaciones_columna
                    ),
                }
            )

    # ======================================================
    # 6. MOSTRAR COLUMNAS SIN FUNDACIÓN
    # ======================================================

    print()
    print(
        "COLUMNAS SIN FUNDACIÓN ASOCIADA:",
        len(columnas_sin_fundacion),
    )

    for columna in columnas_sin_fundacion:

        print("-" * 40)

        print(
            "Columna:",
            columna["referencia"],
        )

        print(
            "Centro:",
            round(
                columna["centro_x"],
                2,
            ),
            "|",
            round(
                columna["centro_y"],
                2,
            ),
        )

    # ======================================================
    # 7. MOSTRAR COLUMNAS ASOCIADAS MÁS DE UNA VEZ
    # ======================================================

    print()
    print(
        "COLUMNAS ASOCIADAS A MÁS "
        "DE UNA FUNDACIÓN:",
        len(columnas_repetidas),
    )

    for repetida in columnas_repetidas:

        asociaciones_columna = (
            repetida["asociaciones"]
        )

        print("-" * 40)

        print(
            "Columna:",
            asociaciones_columna[0][
                "columna"
            ],
        )

        print(
            "Centro:",
            repetida["clave"],
        )

        print(
            "Fundaciones asociadas:",
            [
                asociacion["referencia"]
                for asociacion
                in asociaciones_columna
            ],
        )

    # ======================================================
    # 8. MOSTRAR ASOCIACIONES CON DISTANCIA ELEVADA
    # ======================================================

    distancia_revision = 18

    asociaciones_distantes = [
        asociacion
        for asociacion in asociaciones
        if (
            asociacion["distancia_pdf"]
            is not None
            and asociacion["distancia_pdf"]
            > distancia_revision
        )
    ]

    print()
    print(
        "ASOCIACIONES CON DISTANCIA MAYOR A",
        distancia_revision,
        ":",
        len(asociaciones_distantes),
    )

    for asociacion in asociaciones_distantes:

        print("-" * 40)

        print(
            asociacion["referencia"],
            "->",
            asociacion["columna"],
            "| Distancia:",
            round(
                asociacion["distancia_pdf"],
                2,
            ),
            "| Fundación:",
            (
                round(
                    asociacion["centro_x"],
                    2,
                ),
                round(
                    asociacion["centro_y"],
                    2,
                ),
            ),
            "| Columna:",
            (
                round(
                    asociacion["columna_x"],
                    2,
                ),
                round(
                    asociacion["columna_y"],
                    2,
                ),
            ),
        )

    # ======================================================
    # 6. MOSTRAR LAS ASOCIACIONES
    # ======================================================

    for asociacion in asociaciones:

        print("-" * 40)

        print(
            "Fundación:",
            asociacion["referencia"],
        )

        print(
            "Columna:",
            asociacion["columna"]
            or "No encontrada",
        )

        if asociacion["distancia_pdf"] is not None:

            print(
                "Distancia en el PDF:",
                round(
                    asociacion[
                        "distancia_pdf"
                    ],
                    2,
                ),
            )

    ruta_imagen = (
    PNG_DIR
    / "asociaciones_columnas_fundaciones.png"
    )

    dibujar_asociaciones(
        ruta_planta,
        asociaciones,
        ruta_imagen,
    )

    print()
    print(
        "Imagen de validación guardada en:",
        ruta_imagen,
    )

    return asociaciones, columnas

def experimentar_detalles_columnas(
    ruta_detalles,
):

    print()
    print("=" * 60)
    print(
        "FASE 4 - EXPERIMENTO 5: "
        "LOCALIZAR DETALLES DE COLUMNAS"
    )
    print("=" * 60)

    # ======================================================
    # 1. LEER EL PDF DE DETALLES
    # ======================================================

    ruta_detalles = Path(
        ruta_detalles
    )

    palabras = extraer_palabras(
        ruta_detalles
    )

    # ======================================================
    # 2. BUSCAR REFERENCIAS C1, C2, C3...
    # ======================================================

    columnas_en_detalles = (
        detectar_columnas(
            palabras
        )
    )

    print(
        "Referencias encontradas:",
        len(columnas_en_detalles),
    )

    # ======================================================
    # 3. ORDENAR POR PÁGINA Y POSICIÓN
    # ======================================================

    columnas_en_detalles.sort(
        key=lambda columna: (
            columna["pagina"],
            columna["centro_x"],
            columna["centro_y"],
        )
    )

    # ======================================================
    # 4. MOSTRAR LAS REFERENCIAS Y SUS COORDENADAS
    # ======================================================

    for numero, columna in enumerate(
        columnas_en_detalles,
        start=1,
    ):

        print("-" * 40)

        print(
            "Detección:",
            numero,
        )

        print(
            "Referencia:",
            columna["referencia"],
        )

        print(
            "Página:",
            columna["pagina"],
        )

        print(
            "Centro:",
            round(
                columna["centro_x"],
                2,
            ),
            "|",
            round(
                columna["centro_y"],
                2,
            ),
        )

def experimentar_secciones_columnas(
    ruta_fundaciones,
    ruta_columnas,
    configuracion_proyecto=None,
):

    print()
    print("=" * 60)
    print(
        "FASE 4 - EXPERIMENTO 6: "
        "EXTRAER SECCIONES DE COLUMNAS"
    )
    print("=" * 60)

    # ======================================================
    # 1. CONVERTIR LAS RUTAS
    # ======================================================

    ruta_fundaciones = Path(
        ruta_fundaciones
    )

    ruta_columnas = Path(
        ruta_columnas
    )
    configuracion_proyecto = (
        configuracion_proyecto
        or ConfiguracionProyecto.vacia()
    )

    # ======================================================
    # 2. LEER EL PLANO DE FUNDACIONES
    # ======================================================

    palabras_fundaciones = extraer_palabras(
        ruta_fundaciones
    )

    referencias_prueba_fundaciones = (
    detectar_columnas(
        palabras_fundaciones
    )
    )

    print()
    print(
        "Columnas detectadas en fundaciones:",
        [
            columna["referencia"]
            for columna
            in referencias_prueba_fundaciones
        ],
    )

    # ======================================================
    # 3. EXTRAER C1, C2 Y C3
    # ======================================================

    secciones_fundaciones = (
        extraer_secciones_columnas(
            palabras_fundaciones,
            origen=ruta_fundaciones.name,
            correcciones=(
                configuracion_proyecto
                .correcciones_columnas_fundaciones
            ),
        )
    )

    # ======================================================
    # 4. LEER EL PLANO GENERAL DE COLUMNAS
    # ======================================================

    palabras_columnas = extraer_palabras(
        ruta_columnas
    )

    referencias_prueba_columnas = (
    detectar_columnas(
        palabras_columnas
    )
    )

    print()
    print(
        "Columnas detectadas en plano general:",
        [
            columna["referencia"]
            for columna
            in referencias_prueba_columnas
        ],
    )

    # ======================================================
    # 5. EXTRAER C4 HASTA C17
    # ======================================================

    secciones_columnas = (
        extraer_secciones_columnas(
            palabras_columnas,
            origen=ruta_columnas.name,
        )
    )

    # ======================================================
    # 6. COMBINAR LOS RESULTADOS
    # ======================================================

    secciones = (
        secciones_fundaciones
        + secciones_columnas
    )

    # Ordenamos numéricamente:
    # C1, C2, C3... C17.
    secciones.sort(
        key=lambda seccion: int(
            seccion["referencia"][1:]
        )
    )

    # ======================================================
    # 7. MOSTRAR LOS RESULTADOS
    # ======================================================

    for seccion in secciones:

        print("-" * 40)

        print(
            "Referencia:",
            seccion["referencia"],
        )

        print(
            "Referencia original:",
            seccion[
                "referencia_original"
            ],
        )

        print(
            "Origen:",
            seccion["origen"],
        )

        print(
            "Estado:",
            seccion["estado"],
        )

        if (
            seccion["dimension_1_m"]
            is not None
        ):

            print(
                "Sección:",
                seccion["dimension_1_m"],
                "×",
                seccion["dimension_2_m"],
                "m",
            )

        else:

            print(
                "Cotas encontradas:",
                seccion[
                    "cotas_detectadas"
                ],
            )

        if seccion["fue_corregida"]:

            print(
                "Corrección aplicada:",
                seccion[
                    "referencia_original"
                ],
                "->",
                seccion["referencia"],
            )

    # ======================================================
    # 8. VALIDAR C1 HASTA C17
    # ======================================================

    referencias_esperadas = {
        f"C{numero}"
        for numero in range(
            1,
            18,
        )
    }

    print()
    print("DIAGNÓSTICO DE EXTRACCIÓN")
    print("-" * 40)

    print(
        "Secciones obtenidas del plano de fundaciones:",
        len(secciones_fundaciones),
    )

    print(
        "Secciones obtenidas del plano general:",
        len(secciones_columnas),
    )

    for seccion in secciones:

        print(
            seccion["referencia"],
            "| Estado:",
            seccion["estado"],
            "| Cotas:",
            seccion["cotas_detectadas"],
        )

    referencias_encontradas = {
        seccion["referencia"]
        for seccion in secciones
        if seccion["estado"] == "CORRECTO"
    }

    faltantes = (
        referencias_esperadas
        - referencias_encontradas
    )

    sobrantes = (
        referencias_encontradas
        - referencias_esperadas
    )

    print()
    print("=" * 60)
    print("VALIDACIÓN DE COLUMNAS")
    print("=" * 60)

    print(
        "Referencias esperadas:",
        sorted(
            referencias_esperadas,
            key=lambda ref: int(ref[1:]),
        ),
    )

    print(
        "Referencias encontradas:",
        sorted(
            referencias_encontradas,
            key=lambda ref: int(ref[1:]),
        ),
    )

    print(
        "Faltantes:",
        sorted(
            faltantes,
            key=lambda ref: int(ref[1:]),
        ),
    )

    print(
        "Sobrantes:",
        sorted(
            sobrantes,
            key=lambda ref: int(ref[1:]),
        ),
    )

    return secciones

def experimentar_dimensiones_pedestales(
    ruta_planta,
    secciones_columnas,
):

    print()
    print("=" * 60)
    print(
        "FASE 4 - EXPERIMENTO 7: "
        "DIMENSIONES DE PEDESTALES"
    )
    print("=" * 60)

    # ======================================================
    # 1. LEER LA PLANTA
    # ======================================================

    ruta_planta = Path(
        ruta_planta
    )

    palabras_planta = extraer_palabras(
        ruta_planta
    )

    # ======================================================
    # 2. DETECTAR TODAS LAS COLUMNAS
    # ======================================================

    columnas_planta = detectar_columnas(
        palabras_planta
    )

    print(
        "Cantidad de columnas detectadas:",
        len(columnas_planta),
    )

    # ======================================================
    # 3. CONTAR COLUMNAS POR TIPO
    # ======================================================

    conteo_columnas = (
        contar_columnas_por_tipo(
            columnas_planta
        )
    )

    # ======================================================
    # 4. CALCULAR DIMENSIONES DE PEDESTALES
    # ======================================================

    pedestales = (
        calcular_dimensiones_pedestales(
            secciones_columnas,
            conteo_columnas,
            INCREMENTO_PEDESTAL_CM,
        )
    )

    # ======================================================
    # 5. MOSTRAR LOS RESULTADOS
    # ======================================================

    print(
        "Incremento utilizado:",
        INCREMENTO_PEDESTAL_CM,
        "cm",
    )

    print(
        "Tipos de pedestal calculados:",
        len(pedestales),
    )

    print("-" * 60)

    cantidad_total = 0

    for pedestal in pedestales:

        cantidad_total += pedestal[
            "cantidad"
        ]

        print(
            pedestal[
                "referencia_columna"
            ],
            "| Cantidad:",
            pedestal["cantidad"],
            "| Columna:",
            (
                f"{pedestal['dimension_columna_1_m']:.2f}"
                " × "
                f"{pedestal['dimension_columna_2_m']:.2f}"
                " m"
            ),
            "| Pedestal:",
            (
                f"{pedestal['dimension_pedestal_1_m']:.2f}"
                " × "
                f"{pedestal['dimension_pedestal_2_m']:.2f}"
                " m"
            ),
        )

    print("=" * 60)

    print(
        "CANTIDAD TOTAL SEGÚN COLUMNAS:",
        cantidad_total,
    )

    # ======================================================
    # 6. GUARDAR RESULTADO PRELIMINAR
    # ======================================================

    guardar_csv(
        pedestales,
        REPORT_DIR
        / "dimensiones_pedestales.csv",
    )

    return {
        "columnas_planta": (
            columnas_planta
        ),
        "conteo_columnas": (
            conteo_columnas
        ),
        "pedestales": pedestales,
        "cantidad_total": (
            cantidad_total
        ),
    }


def experimentar_computos_pedestales(
    resultado_dimensiones,
):

    print()
    print("=" * 60)
    print(
        "FASE 4 - EXPERIMENTO 8: "
        "CÓMPUTO PRELIMINAR DE PEDESTALES"
    )
    print("=" * 60)

    # ======================================================
    # 1. OBTENER LAS DIMENSIONES CALCULADAS
    # ======================================================

    pedestales = resultado_dimensiones[
        "pedestales"
    ]

    # ======================================================
    # 2. CALCULAR VOLUMEN Y ENCOFRADO
    # ======================================================

    computos = calcular_computos_pedestales(
        pedestales,
        ALTURA_MINIMA_PEDESTAL_M,
        USAR_ENCOFRADO_PEDESTALES,
    )

    # ======================================================
    # 3. MOSTRAR CADA TIPO DE PEDESTAL
    # ======================================================

    for pedestal in computos[
        "detalles"
    ]:

        print("-" * 60)

        print(
            pedestal[
                "referencia_columna"
            ],
            "| Cantidad:",
            pedestal["cantidad"],
        )

        print(
            "Dimensiones:",
            f"{pedestal['dimension_pedestal_1_m']:.2f}",
            "×",
            f"{pedestal['dimension_pedestal_2_m']:.2f}",
            "×",
            f"{pedestal['altura_minima_m']:.2f}",
            "m",
        )

        print(
            "Volumen unitario:",
            f"{pedestal['volumen_unitario_m3']:.4f}",
            "m³",
        )

        print(
            "Volumen total:",
            f"{pedestal['volumen_total_m3']:.4f}",
            "m³",
        )

        print(
            "Encofrado unitario:",
            f"{pedestal['encofrado_unitario_m2']:.3f}",
            "m²",
        )

        print(
            "Encofrado total:",
            f"{pedestal['encofrado_total_m2']:.3f}",
            "m²",
        )

    # ======================================================
    # 4. MOSTRAR TOTALES
    # ======================================================

    print("=" * 60)

    print(
        "VOLUMEN MÍNIMO PRELIMINAR:",
        f"{computos['volumen_general_m3']:.3f}",
        "m³",
    )

    print(
        "ENCOFRADO LATERAL BRUTO:",
        f"{computos['encofrado_general_m2']:.3f}",
        "m²",
    )

    print()
    print(
        "ADVERTENCIA: estos resultados utilizan "
        "la altura mínima de",
        ALTURA_MINIMA_PEDESTAL_M,
        "m.",
    )

    print(
        "La columna C5 sin fundación asociada "
        "está incluida provisionalmente."
    )

    # ======================================================
    # 5. GUARDAR EL REPORTE
    # ======================================================

    guardar_csv(
        computos["detalles"],
        REPORT_DIR
        / "computo_preliminar_pedestales.csv",
    )

    return computos

def experimentar_deteccion_vigas_riostra(
    ruta_planta,
):

    print()
    print("=" * 60)
    print(
        "FASE 5 - EXPERIMENTO 1: "
        "DETECTAR VIGAS DE RIOSTRA"
    )
    print("=" * 60)

    # ======================================================
    # 1. LEER LA PLANTA
    # ======================================================

    ruta_planta = Path(
        ruta_planta
    )

    palabras = extraer_palabras(
        ruta_planta
    )

    # ======================================================
    # 2. DETECTAR REFERENCIAS V.R.
    # ======================================================

    vigas_detectadas = detectar_vigas_riostra(
        palabras
    )

    # El PDF contiene un rótulo VR3 duplicado exactamente
    # en la misma posición. Lo quitamos antes de contar.
    vigas, duplicados = eliminar_rotulos_duplicados(
        vigas_detectadas,
        tolerancia=0.5,
    )

    validacion_secciones = (
        validar_secciones_por_referencia(
            vigas
        )
    )

    print()
    print("=" * 60)
    print("FASE 5 - EXPERIMENTO 2: VALIDAR SECCIONES")
    print("=" * 60)

    for referencia, datos in sorted(validacion_secciones.items()):
        print("-" * 40)
        print("Referencia:", referencia)

        for seccion in datos["secciones"]:
            print(
                f"Sección: {seccion['ancho_cm']} × "
                f"{seccion['alto_cm']} cm"
            )
            print(
                "Cantidad de rótulos:",
                seccion["cantidad_rotulos"],
            )

        if datos["tiene_variantes"]:
            print("Observación: tiene más de una sección válida")
        else:
            print("Observación: sección única")

        print("Estado:", datos["estado"])

    print("Rótulos encontrados en el PDF:", len(vigas_detectadas))
    print("Duplicados exactos eliminados:", len(duplicados))
    print("Rótulos únicos de vigas:", len(vigas))

    # ======================================================
    # 3. MOSTRAR CADA DETECCIÓN
    # ======================================================

    for numero, viga in enumerate(
        vigas,
        start=1,
    ):

        print("-" * 40)

        print(
            "Detección:",
            numero,
        )

        print(
            "Referencia:",
            viga["referencia"],
        )

        print(
            "Sección:",
            viga["ancho_cm"],
            "×",
            viga["alto_cm"],
            "cm",
        )

        print(
            "Texto:",
            viga["texto_original"],
        )

        print(
            "Centro:",
            round(
                viga["centro_x"],
                2,
            ),
            "|",
            round(
                viga["centro_y"],
                2,
            ),
        )

    # ======================================================
    # 4. CONTAR POR TIPO
    # ======================================================

    conteo = {}

    for viga in vigas:

        referencia = viga[
            "referencia"
        ]

        conteo[referencia] = (
            conteo.get(
                referencia,
                0,
            )
            + 1
        )

    print()
    print("=" * 60)
    print("CONTEO DE RÓTULOS POR TIPO")
    print("=" * 60)

    for referencia in sorted(
        conteo,
        key=lambda ref: int(ref[2:]),
    ):

        print(
            referencia,
            "->",
            conteo[referencia],
            "rótulos",
        )

    return vigas


def experimentar_bordes_vectoriales_vigas(
    ruta_planta,
    nodos,
):
    """Ejecuta el diagnóstico de los trazos vectoriales de las vigas."""

    print()
    print("=" * 60)
    print(
        "FASE 5 - EXPERIMENTO 3: "
        "EXTRAER BORDES VECTORIALES"
    )
    print("=" * 60)

    bordes, diagnostico = (
        extraer_bordes_vectoriales_vigas(
            ruta_planta,
            nodos,
            espesor_objetivo=ESPESOR_VECTOR_VIGA_PT,
            tolerancia_espesor=(
                TOLERANCIA_ESPESOR_VECTOR_PT
            ),
            longitud_minima=(
                LONGITUD_MINIMA_LINEA_VIGA_PT
            ),
            margen_zona=MARGEN_ZONA_ESTRUCTURAL_PT,
        )
    )

    ruta_datos = (
        PROCESSED_DIR
        / "bordes_vectoriales_vigas.json"
    )
    ruta_imagen = (
        PNG_DIR
        / "bordes_vectoriales_vigas.png"
    )

    guardar_json(
        {
            "diagnostico": diagnostico,
            "bordes": bordes,
        },
        ruta_datos,
    )

    dibujar_bordes_vectoriales_vigas(
        ruta_planta,
        bordes,
        ruta_imagen,
        escala=ESCALA_IMAGEN_DIAGNOSTICO,
    )

    print(
        "Objetos de dibujo en el PDF:",
        diagnostico["total_objetos_dibujo"],
    )
    print(
        "Segmentos rectos encontrados:",
        diagnostico["total_segmentos_rectos"],
    )
    print(
        "Segmentos con espesor",
        ESPESOR_VECTOR_VIGA_PT,
        ":",
        diagnostico["segmentos_espesor_correcto"],
    )
    print(
        "Descartados por longitud:",
        diagnostico["descartados_por_longitud"],
    )
    print(
        "Descartados fuera de la planta:",
        diagnostico["descartados_fuera_zona"],
    )
    print(
        "Bordes candidatos conservados:",
        diagnostico["bordes_candidatos"],
    )
    print("Datos guardados en:", ruta_datos)
    print("Imagen de validación:", ruta_imagen)
    print()
    print(
        "IMPORTANTE: cada viga aparece aproximadamente "
        "como dos bordes paralelos."
    )
    print(
        "Estos segmentos todavía no son ejes ni longitudes "
        "de cómputo."
    )

    return bordes, diagnostico


def experimentar_emparejamiento_bordes_vigas(
    ruta_planta,
    bordes,
):
    """Empareja bordes y genera ejes centrales candidatos."""

    print()
    print("=" * 60)
    print(
        "FASE 5 - EXPERIMENTO 4: "
        "EMPAREJAR BORDES PARA OBTENER EJES"
    )
    print("=" * 60)

    (
        ejes_candidatos,
        bordes_sin_pareja,
        diagnostico,
    ) = emparejar_bordes_paralelos(
        bordes,
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

    ruta_datos = (
        PROCESSED_DIR
        / "ejes_candidatos_vigas.json"
    )

    ruta_imagen = (
        PNG_DIR
        / "ejes_candidatos_vigas.png"
    )

    guardar_json(
        {
            "diagnostico": diagnostico,
            "ejes_candidatos": (
                ejes_candidatos
            ),
            "bordes_sin_pareja": (
                bordes_sin_pareja
            ),
        },
        ruta_datos,
    )

    dibujar_ejes_candidatos_vigas(
        ruta_planta,
        ejes_candidatos,
        bordes_sin_pareja,
        ruta_imagen,
        escala=ESCALA_IMAGEN_DIAGNOSTICO,
    )

    print(
        "Bordes recibidos:",
        diagnostico[
            "cantidad_bordes_entrada"
        ],
    )

    print(
        "Posibles parejas que cumplen "
        "los filtros:",
        diagnostico["posibles_parejas"],
    )

    print(
        "Parejas seleccionadas:",
        diagnostico[
            "parejas_seleccionadas"
        ],
    )

    print(
        "Ejes duplicados descartados:",
        diagnostico[
            "ejes_duplicados_descartados"
        ],
    )

    print(
        "Ejes candidatos conservados:",
        diagnostico[
            "cantidad_ejes_candidatos"
        ],
    )

    print(
        "Bordes sin pareja:",
        diagnostico[
            "cantidad_bordes_sin_pareja"
        ],
    )

    print(
        "Datos guardados en:",
        ruta_datos,
    )

    print(
        "Imagen de validación:",
        ruta_imagen,
    )

    print()
    print(
        "Color azul: eje central candidato."
    )
    print(
        "Color naranja: borde sin pareja."
    )
    print(
        "IMPORTANTE: todavía no se utilizan "
        "estos ejes para calcular cantidades."
    )

    return ejes_candidatos, diagnostico

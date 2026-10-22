"""Detección de columnas y asociación espacial con fundaciones."""

from math import hypot
import re
from pathlib import Path
import pymupdf
from decimal import Decimal

PATRON_COLUMNA = re.compile(r"^C\d+$", re.IGNORECASE)


def filtrar_palabras_detalles_columnas(palabras):
    """Conserva Cn solo cuando forma parte de un título explícito de detalle.

    Las cotas y notas permanecen disponibles. Esto evita interpretar cada
    rótulo repetido de una planta de columnas como un detalle independiente.
    """

    palabras = list(palabras)
    if not palabras or not all(
        "numero_bloque" in p and "numero_linea" in p for p in palabras
    ):
        return palabras
    lineas = {}
    for palabra in palabras:
        clave = (
            palabra.get("pagina"),
            palabra["numero_bloque"],
            palabra["numero_linea"],
        )
        lineas.setdefault(clave, []).append(palabra)
    titulos = set()
    for clave, linea in lineas.items():
        texto = " ".join(
            str(p.get("texto", ""))
            for p in sorted(linea, key=lambda p: p.get("numero_palabra", 0))
        )
        if re.search(r"\bDETALLE\s+(?:DE\s+)?(?:COLUMNA|PILAR)\b", texto, re.I):
            titulos.add(clave)
    if not titulos:
        return palabras
    return [
        palabra
        for palabra in palabras
        if not PATRON_COLUMNA.fullmatch(
            re.sub(r"[^A-Z0-9]", "", str(palabra.get("texto", "")).upper())
        )
        or (
            palabra.get("pagina"),
            palabra["numero_bloque"],
            palabra["numero_linea"],
        ) in titulos
    ]

def detectar_columnas(
    palabras,
):
    """
    Detecta referencias de columnas como:

        C1
        (C1)
        C1)
        (C1)

    Todas se guardan con el formato normalizado C1.
    """

    columnas = []

    for palabra in palabras:

        # ==================================================
        # 1. TOMAR EL TEXTO ORIGINAL
        # ==================================================

        texto_original = (
            palabra["texto"]
            .strip()
            .upper()
        )

        # ==================================================
        # 2. ELIMINAR SIGNOS Y PARÉNTESIS
        # ==================================================

        referencia_normalizada = re.sub(
            r"[^A-Z0-9]",
            "",
            texto_original,
        )

        # Ejemplos:
        #
        # "(C1)" -> "C1"
        # "C2)"  -> "C2"
        # "(C4"  -> "C4"

        # ==================================================
        # 3. COMPROBAR SI ES UNA COLUMNA
        # ==================================================

        if not PATRON_COLUMNA.fullmatch(
            referencia_normalizada
        ):
            continue

        # ==================================================
        # 4. GUARDAR REFERENCIA Y COORDENADAS
        # ==================================================

        columnas.append(
            {
                "referencia": (
                    referencia_normalizada
                ),
                "texto_original": (
                    texto_original
                ),
                "pagina": palabra["pagina"],
                "x0": palabra["x0"],
                "y0": palabra["y0"],
                "x1": palabra["x1"],
                "y1": palabra["y1"],
                "centro_x": (
                    palabra["x0"]
                    + palabra["x1"]
                ) / 2,
                "centro_y": (
                    palabra["y0"]
                    + palabra["y1"]
                ) / 2,
            }
        )

    return columnas
    
def asociar_columnas_a_fundaciones(
    fundaciones,
    columnas,
    distancia_maxima=None,
    permitir_multiples=False,
):
    """
    Asocia rótulos de columnas con fundaciones.

    Cuando permitir_multiples=True:

    1. asigna una columna principal diferente a cada fundación;
    2. asigna las columnas restantes a la columna principal
       más cercana;
    3. marca las asociaciones adicionales para revisión.
    """

    fundaciones = list(fundaciones)
    columnas = list(columnas)

    def distancia_fundacion_columna(
        fundacion,
        columna,
    ):
        return hypot(
            fundacion["centro_x"]
            - columna["centro_x"],
            fundacion["centro_y"]
            - columna["centro_y"],
        )

    def distancia_entre_columnas(
        primera,
        segunda,
    ):
        return hypot(
            primera["centro_x"]
            - segunda["centro_x"],
            primera["centro_y"]
            - segunda["centro_y"],
        )

    def sin_columna(fundacion):
        return {
            **fundacion,
            "columna": None,
            "columna_x": None,
            "columna_y": None,
            "distancia_pdf": None,
            "distancia_a_columna_principal_pdf": None,
            "tipo_asociacion": "sin_columna",
            "requiere_revision_asociacion": True,
        }

    # ======================================================
    # MODO ANTERIOR: UNA COLUMNA POR FUNDACIÓN
    # ======================================================

    if not permitir_multiples:
        asociaciones = []

        for fundacion in fundaciones:
            candidatas = [
                columna
                for columna in columnas
                if columna["pagina"]
                == fundacion["pagina"]
            ]

            if not candidatas:
                asociaciones.append(
                    sin_columna(fundacion)
                )
                continue

            columna = min(
                candidatas,
                key=lambda candidata: (
                    distancia_fundacion_columna(
                        fundacion,
                        candidata,
                    )
                ),
            )

            distancia = (
                distancia_fundacion_columna(
                    fundacion,
                    columna,
                )
            )

            aceptada = (
                distancia_maxima is None
                or distancia <= distancia_maxima
            )

            asociaciones.append(
                {
                    **fundacion,
                    "columna": (
                        columna["referencia"]
                        if aceptada
                        else None
                    ),
                    "columna_x": columna["centro_x"],
                    "columna_y": columna["centro_y"],
                    "distancia_pdf": distancia,
                    "distancia_a_columna_principal_pdf": 0.0,
                    "tipo_asociacion": (
                        "principal_por_proximidad"
                        if aceptada
                        else "fuera_de_distancia"
                    ),
                    "requiere_revision_asociacion": (
                        not aceptada
                    ),
                }
            )

        return asociaciones

    # ======================================================
    # 1. GENERAR TODAS LAS PAREJAS POSIBLES
    # ======================================================

    parejas = []

    for indice_fundacion, fundacion in enumerate(
        fundaciones
    ):
        for indice_columna, columna in enumerate(
            columnas
        ):
            if (
                fundacion["pagina"]
                != columna["pagina"]
            ):
                continue

            parejas.append(
                (
                    distancia_fundacion_columna(
                        fundacion,
                        columna,
                    ),
                    indice_fundacion,
                    indice_columna,
                )
            )

    parejas.sort(
        key=lambda item: (
            item[0],
            item[1],
            item[2],
        )
    )

    # ======================================================
    # 2. ASIGNAR UNA COLUMNA PRINCIPAL ÚNICA
    # ======================================================

    principales = {}
    columnas_utilizadas = set()

    for (
        distancia,
        indice_fundacion,
        indice_columna,
    ) in parejas:
        if indice_fundacion in principales:
            continue

        if indice_columna in columnas_utilizadas:
            continue

        if (
            distancia_maxima is not None
            and distancia > distancia_maxima
        ):
            continue

        principales[indice_fundacion] = (
            indice_columna
        )

        columnas_utilizadas.add(
            indice_columna
        )

    asociaciones = []

    for indice_fundacion, fundacion in enumerate(
        fundaciones
    ):
        indice_columna = principales.get(
            indice_fundacion
        )

        if indice_columna is None:
            asociaciones.append(
                sin_columna(fundacion)
            )
            continue

        columna = columnas[indice_columna]

        asociaciones.append(
            {
                **fundacion,
                "columna": columna["referencia"],
                "columna_x": columna["centro_x"],
                "columna_y": columna["centro_y"],
                "distancia_pdf": (
                    distancia_fundacion_columna(
                        fundacion,
                        columna,
                    )
                ),
                "distancia_a_columna_principal_pdf": 0.0,
                "tipo_asociacion": (
                    "principal_por_proximidad"
                ),
                "requiere_revision_asociacion": False,
            }
        )

    # ======================================================
    # 3. ASIGNAR LAS COLUMNAS ADICIONALES
    # ======================================================

    for indice_columna, columna in enumerate(
        columnas
    ):
        if indice_columna in columnas_utilizadas:
            continue

        candidatas = []

        for (
            indice_fundacion,
            indice_columna_principal,
        ) in principales.items():
            fundacion = fundaciones[
                indice_fundacion
            ]

            if (
                fundacion["pagina"]
                != columna["pagina"]
            ):
                continue

            columna_principal = columnas[
                indice_columna_principal
            ]

            candidatas.append(
                (
                    distancia_entre_columnas(
                        columna,
                        columna_principal,
                    ),
                    indice_fundacion,
                )
            )

        if not candidatas:
            continue

        (
            distancia_a_principal,
            indice_fundacion,
        ) = min(
            candidatas,
            key=lambda item: (
                item[0],
                item[1],
            ),
        )

        if (
            distancia_maxima is not None
            and distancia_a_principal
            > distancia_maxima
        ):
            continue

        fundacion = fundaciones[
            indice_fundacion
        ]

        asociaciones.append(
            {
                **fundacion,
                "columna": columna["referencia"],
                "columna_x": columna["centro_x"],
                "columna_y": columna["centro_y"],
                "distancia_pdf": (
                    distancia_fundacion_columna(
                        fundacion,
                        columna,
                    )
                ),
                "distancia_a_columna_principal_pdf": (
                    distancia_a_principal
                ),
                "tipo_asociacion": (
                    "adicional_por_proximidad"
                ),
                "requiere_revision_asociacion": True,
            }
        )

    return asociaciones

def dibujar_asociaciones(
    ruta_pdf,
    asociaciones,
    ruta_salida,
    pagina_numero=1,
    escala=2,
):

    # ======================================================
    # 1. CONVERTIR LAS RUTAS EN OBJETOS PATH
    # ======================================================

    ruta_pdf = Path(
        ruta_pdf
    )

    ruta_salida = Path(
        ruta_salida
    )

    # Crear la carpeta de salida si no existe.
    ruta_salida.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ======================================================
    # 2. ABRIR EL PDF
    # ======================================================

    with pymupdf.open(
        ruta_pdf
    ) as documento:

        pagina = documento[
            pagina_numero - 1
        ]

        # ==================================================
        # 3. RECORRER LAS ASOCIACIONES
        # ==================================================

        for asociacion in asociaciones:

            if (
                asociacion["pagina"]
                != pagina_numero
            ):
                continue

            if asociacion["columna"] is None:
                continue

            punto_fundacion = pymupdf.Point(
                asociacion["centro_x"],
                asociacion["centro_y"],
            )

            punto_columna = pymupdf.Point(
                asociacion["columna_x"],
                asociacion["columna_y"],
            )

            # ==============================================
            # 4. DIBUJAR LA LÍNEA DE ASOCIACIÓN
            # ==============================================

            pagina.draw_line(
                punto_fundacion,
                punto_columna,
                color=(0, 0, 1),
                width=0.7,
                overlay=True,
            )

            # ==============================================
            # 5. MARCAR EL CENTRO DE LA FUNDACIÓN
            # ==============================================

            pagina.draw_circle(
                punto_fundacion,
                radius=1.8,
                color=(1, 0, 0),
                fill=(1, 0, 0),
                overlay=True,
            )

            # ==============================================
            # 6. MARCAR EL CENTRO DE LA COLUMNA
            # ==============================================

            pagina.draw_circle(
                punto_columna,
                radius=1.8,
                color=(0, 0, 1),
                fill=(0, 0, 1),
                overlay=True,
            )

        # ==================================================
        # 7. CONVERTIR LA PÁGINA EN IMAGEN
        # ==================================================

        matriz = pymupdf.Matrix(
            escala,
            escala,
        )

        imagen = pagina.get_pixmap(
            matrix=matriz,
            alpha=False,
        )

        imagen.save(
            str(ruta_salida)
        )

def convertir_cota_decimal(
    texto,
):
    """
    Convierte una cota extraída del PDF
    en un número Decimal.

    Ejemplo:
        "0,45" -> Decimal("0.45")
    """

    texto_normalizado = (
        texto
        .strip()
        .replace(",", ".")
    )

    return Decimal(
        texto_normalizado
    )

def extraer_secciones_columnas(
    palabras,
    origen,
    correcciones=None,
):
    """
    Extrae las dimensiones de las secciones
    de columnas utilizando texto y coordenadas.
    """

    if correcciones is None:

        correcciones = {}

    # ======================================================
    # 1. DETECTAR LOS TÍTULOS (C1), (C2), ETC.
    # ======================================================

    referencias = detectar_columnas(
        palabras
    )

    secciones = []

    # ======================================================
    # 2. RECORRER CADA DETALLE
    # ======================================================

    for columna in referencias:

        referencia_original = columna[
            "referencia"
        ]

        referencia_corregida = correcciones.get(
            (
                columna.get("pagina"),
                referencia_original,
            ),
            correcciones.get(
                referencia_original,
                referencia_original,
            ),
        )

        cotas_candidatas = []

        # ==================================================
        # 3. REVISAR TODAS LAS PALABRAS
        # ==================================================

        for palabra in palabras:

            # En un PDF multipágina las coordenadas se reinician en cada
            # página. Nunca se debe asociar una cota de otra lámina por una
            # proximidad numérica accidental.
            if palabra.get("pagina") != columna.get("pagina"):
                continue

            texto_original = (
                palabra["texto"]
                .strip()
            )

            # Quitar espacios y cambiar coma por punto.
            texto_normalizado = (
                texto_original
                .replace(" ", "")
                .replace(",", ".")
            )

            # Las cotas principales del plano están
            # escritas como 0,45; 0.50; 0,70, etc.
            #
            # Esto evita tomar anotaciones como:
            # .10, .16, 1.40 o 2.30.
            if not texto_normalizado.startswith(
                "0"
            ):
                continue

            # ==============================================
            # 4. INTENTAR CONVERTIR EL TEXTO A DECIMAL
            # ==============================================

            try:

                valor = Decimal(
                    texto_normalizado
                )

            except Exception:

                continue

            # Las secciones de las columnas de este plano
            # se encuentran entre 0.20 y 1.20 metros.
            if not (
                Decimal("0.20")
                <= valor
                <= Decimal("1.20")
            ):
                continue

            # ==============================================
            # 5. CALCULAR POSICIÓN RELATIVA
            # ==============================================

            diferencia_x = (
                palabra["x0"]
                - columna["x0"]
            )

            diferencia_y = (
                palabra["y0"]
                - columna["y0"]
            )

            # Región donde están las dos cotas principales
            # respecto del título (C1), (C2), etc.
            esta_en_region_seccion = (
                0 < diferencia_x < 60
                and -100 < diferencia_y < -25
            )

            if not esta_en_region_seccion:

                continue

            cotas_candidatas.append(
                {
                    "texto": texto_original,
                    "valor": valor,
                    "x0": palabra["x0"],
                    "y0": palabra["y0"],
                    "diferencia_x": (
                        diferencia_x
                    ),
                    "diferencia_y": (
                        diferencia_y
                    ),
                }
            )

        # ==================================================
        # 6. ORDENAR POR POSICIÓN
        # ==================================================

        cotas_candidatas.sort(
            key=lambda cota: (
                cota["diferencia_x"]
            )
        )

        # ==================================================
        # 7. ELIMINAR COTAS REPETIDAS EN LA MISMA POSICIÓN
        # ==================================================

        cotas_sin_repetir = []

        posiciones_utilizadas = set()

        for cota in cotas_candidatas:

            clave_posicion = (
                round(
                    cota["x0"],
                    2,
                ),
                round(
                    cota["y0"],
                    2,
                ),
            )

            if (
                clave_posicion
                in posiciones_utilizadas
            ):
                continue

            posiciones_utilizadas.add(
                clave_posicion
            )

            cotas_sin_repetir.append(
                cota
            )

        cotas_candidatas = (
            cotas_sin_repetir
        )

        # ==================================================
        # 8. VALIDAR QUE HAYA DOS COTAS
        # ==================================================

        if len(cotas_candidatas) != 2:

            secciones.append(
                {
                    "referencia_original": (
                        referencia_original
                    ),
                    "referencia": (
                        referencia_corregida
                    ),
                    "dimension_1_m": None,
                    "dimension_2_m": None,
                    "origen": origen,
                    "pagina": columna.get("pagina"),
                    "fue_corregida": (
                        referencia_original
                        != referencia_corregida
                    ),
                    "estado": "REVISAR",
                    "cantidad_cotas": len(
                        cotas_candidatas
                    ),
                    "cotas_detectadas": [
                        cota["texto"]
                        for cota
                        in cotas_candidatas
                    ],
                }
            )

            continue

        # ==================================================
        # 9. GUARDAR EL RESULTADO CORRECTO
        # ==================================================

        secciones.append(
            {
                "referencia_original": (
                    referencia_original
                ),
                "referencia": (
                    referencia_corregida
                ),
                "dimension_1_m": (
                    cotas_candidatas[0][
                        "valor"
                    ]
                ),
                "dimension_2_m": (
                    cotas_candidatas[1][
                        "valor"
                    ]
                ),
                "origen": origen,
                "pagina": columna.get("pagina"),
                "fue_corregida": (
                    referencia_original
                    != referencia_corregida
                ),
                "estado": "CORRECTO",
                "cantidad_cotas": 2,
                "cotas_detectadas": [
                    cota["texto"]
                    for cota
                    in cotas_candidatas
                ],
            }
        )

    return secciones

""" from pathlib import Path
import pymupdf

pdf_path = Path("data/pdf/Fundaciones/Fundaciones_1.pdf")

print(pdf_path)
print(pdf_path.exists())

documento = pymupdf.open(pdf_path)

print(documento)

cantidad_paginas = len(documento)

print(cantidad_paginas)

pagina = documento[0]

print(pagina)

rectangulo = pagina.rect

print(rectangulo)

ancho = rectangulo.width
alto = rectangulo.height

print("Ancho:", ancho)
print("Alto:", alto)

texto = pagina.get_text()

print(texto)
print("Cantidad de caracteres:", len(texto))

dibujos = pagina.get_drawings()

print("Cantidad de dibujos:", len(dibujos))

primer_dibujo = dibujos[0]

print(primer_dibujo)

for dibujo in dibujos[:20]:
    print(dibujo["type"])

contador_tipos = {}

for dibujo in dibujos:
    tipo = dibujo["type"]

    if tipo not in contador_tipos:
        contador_tipos[tipo] = 0

    contador_tipos[tipo] += 1

print(contador_tipos)

tipos_geometricos = {}

for dibujo in dibujos:
    for item in dibujo["items"]:
        tipo = item[0]

        if tipo not in tipos_geometricos:
            tipos_geometricos[tipo] = 0

        tipos_geometricos[tipo] += 1

print(tipos_geometricos)

imagenes = pagina.get_images()

print("Cantidad de imágenes:", len(imagenes))

print(imagenes[0])

bloques_texto = pagina.get_text("blocks")

print("Cantidad de bloques de texto:", len(bloques_texto))

primer_bloque = bloques_texto[0]

x0 = primer_bloque[0]
y0 = primer_bloque[1]
texto_bloque = primer_bloque[4]

print("Texto:", texto_bloque)
print("X:", x0)
print("Y:", y0)

print("Cantidad de datos del bloque:", len(primer_bloque))

longitudes = set()

for bloque in bloques_texto:
    longitudes.add(len(bloque))

print("Estructuras encontradas:", longitudes) """

import json
import re
from collections import Counter

from pathlib import Path

import pymupdf

from computos.configuracion.parametros import (
    ANALYSIS_DIR,
    LONGITUD_DOBLEZ_CM,
    PDF_DIR,
    PNG_DIR,
    RECUBRIMIENTO_FUNDACION_CM,
    REPORT_DIR,
    DESPERDICIO_ACERO_PORCENTAJE,
    LONGITUD_BARRA_COMERCIAL_M,
    USAR_ENCOFRADO_ZAPATAS
)

from decimal import (
    Decimal,
    InvalidOperation,
    ROUND_CEILING,
)
import csv




pdf_path = PDF_DIR / "Fundaciones" / "Fundaciones_1.pdf"


if not pdf_path.exists():
    raise FileNotFoundError(
        f"No se encontró el archivo: {pdf_path}"
    )


bloques_extraidos = []


with pymupdf.open(pdf_path) as documento:

    for numero_pagina, pagina in enumerate(
        documento,
        start=1
    ):

        bloques_pagina = pagina.get_text(
            "blocks",
            sort=True
        )

        for bloque in bloques_pagina:

            x0, y0, x1, y1, texto, numero_bloque, tipo_bloque = bloque

            texto_limpio = texto.strip()

            if tipo_bloque != 0:
                continue

            if not texto_limpio:
                continue

            datos_bloque = {
                "pagina": numero_pagina,
                "numero_bloque": numero_bloque,
                "texto": texto_limpio,
                "x0": round(x0, 2),
                "y0": round(y0, 2),
                "x1": round(x1, 2),
                "y1": round(y1, 2),
            }

            bloques_extraidos.append(datos_bloque)


print("Cantidad de bloques extraídos:", len(bloques_extraidos))


for bloque in bloques_extraidos[:10]:

    print("-" * 40)
    print("Página:", bloque["pagina"])
    print("Texto:", bloque["texto"])
    print("Posición inicial:", bloque["x0"], bloque["y0"])
    print("Posición final:", bloque["x1"], bloque["y1"])

print()
print("=" * 60)
print("EXPERIMENTO 2: PALABRAS INDIVIDUALES")
print("=" * 60)


palabras_extraidas = []


with pymupdf.open(pdf_path) as documento:

    for numero_pagina, pagina in enumerate(
        documento,
        start=1
    ):

        palabras_pagina = pagina.get_text(
            "words",
            sort=True
        )

        for palabra in palabras_pagina:

            (
                x0,
                y0,
                x1,
                y1,
                texto,
                numero_bloque,
                numero_linea,
                numero_palabra,
            ) = palabra

            texto_limpio = texto.strip()

            if not texto_limpio:
                continue

            datos_palabra = {
                "pagina": numero_pagina,
                "texto": texto_limpio,
                "x0": round(x0, 2),
                "y0": round(y0, 2),
                "x1": round(x1, 2),
                "y1": round(y1, 2),
                "numero_bloque": numero_bloque,
                "numero_linea": numero_linea,
                "numero_palabra": numero_palabra,
            }

            palabras_extraidas.append(datos_palabra)


print(
    "Cantidad de palabras extraídas:",
    len(palabras_extraidas)
)


for palabra in palabras_extraidas[:20]:

    print("-" * 40)

    print("Texto:", palabra["texto"])

    print(
        "Posición inicial:",
        palabra["x0"],
        palabra["y0"]
    )

    print(
        "Posición final:",
        palabra["x1"],
        palabra["y1"]
    )

print()
print("=" * 60)
print("EXPERIMENTO 3: REFERENCIAS DE FUNDACIONES")
print("=" * 60)


patron_fundacion = re.compile(
    r"F\d+",
    re.IGNORECASE
)


fundaciones_detectadas = []


for palabra in palabras_extraidas:

    texto = palabra["texto"].strip()

    if not patron_fundacion.fullmatch(texto):
        continue

    centro_x = (
        palabra["x0"] + palabra["x1"]
    ) / 2

    centro_y = (
        palabra["y0"] + palabra["y1"]
    ) / 2

    fundacion = {
        "referencia": texto.upper(),
        "pagina": palabra["pagina"],
        "x0": palabra["x0"],
        "y0": palabra["y0"],
        "x1": palabra["x1"],
        "y1": palabra["y1"],
        "centro_x": round(centro_x, 2),
        "centro_y": round(centro_y, 2),
    }

    fundaciones_detectadas.append(fundacion)


print(
    "Cantidad de referencias encontradas:",
    len(fundaciones_detectadas)
)


for fundacion in fundaciones_detectadas:

    print("-" * 40)

    print(
        "Referencia:",
        fundacion["referencia"]
    )

    print(
        "Página:",
        fundacion["pagina"]
    )

    print(
        "Centro:",
        fundacion["centro_x"],
        fundacion["centro_y"]
    )

conteo_fundaciones = Counter(
    fundacion["referencia"]
    for fundacion in fundaciones_detectadas
)


print()
print("CONTEO PRELIMINAR")
print("-" * 40)


for referencia, cantidad in sorted(
    conteo_fundaciones.items()
):

    print(
        referencia,
        "->",
        cantidad,
        "apariciones"
    )

print()
print("=" * 60)
print("EXPERIMENTO 4: VISUALIZAR FUNDACIONES")
print("=" * 60)


ruta_imagen = PNG_DIR / "fundaciones_detectadas.png"


with pymupdf.open(pdf_path) as documento:

    pagina = documento[0]

    for fundacion in fundaciones_detectadas:

        rectangulo = pymupdf.Rect(
            fundacion["x0"],
            fundacion["y0"],
            fundacion["x1"],
            fundacion["y1"],
        )

        pagina.draw_rect(
            rectangulo,
            color=(1, 0, 0),
            width=1,
            overlay=True,
        )

    escala = pymupdf.Matrix(2, 2)

    imagen = pagina.get_pixmap(
        matrix=escala,
        alpha=False,
    )

    imagen.save(str(ruta_imagen))


print("Imagen generada correctamente.")
print("Ubicación:", ruta_imagen)

print()
print("=" * 60)
print("EXPERIMENTO 5: GUARDAR RESULTADOS")
print("=" * 60)


resultado_analisis = {
    "archivo": pdf_path.name,
    "cantidad_total": len(fundaciones_detectadas),
    "conteo_por_tipo": dict(conteo_fundaciones),
    "fundaciones": fundaciones_detectadas,
}


ruta_json = ANALYSIS_DIR / "fundaciones_detectadas.json"


with open(
    ruta_json,
    "w",
    encoding="utf-8"
) as archivo_json:

    json.dump(
        resultado_analisis,
        archivo_json,
        ensure_ascii=False,
        indent=4,
    )


print("Resultados guardados correctamente.")
print("Ubicación:", ruta_json)

print()
print("=" * 60)
print("FASE 2 - EXPERIMENTO 1: ANALIZAR FUNDACIONES_2")
print("=" * 60)


pdf_detalles_path = (
    PDF_DIR
    / "Fundaciones"
    / "Fundaciones_2.pdf"
)


if not pdf_detalles_path.exists():

    raise FileNotFoundError(
        f"No se encontró el archivo: {pdf_detalles_path}"
    )


textos_paginas = []


with pymupdf.open(pdf_detalles_path) as documento_detalles:

    print(
        "Cantidad de páginas:",
        len(documento_detalles)
    )

    for numero_pagina, pagina in enumerate(
        documento_detalles,
        start=1
    ):

        texto_pagina = pagina.get_text(
            "text",
            sort=True
        )

        datos_pagina = {
            "pagina": numero_pagina,
            "cantidad_caracteres": len(texto_pagina),
            "texto": texto_pagina,
        }

        textos_paginas.append(datos_pagina)

        print(
            "Página",
            numero_pagina,
            "->",
            len(texto_pagina),
            "caracteres"
        )


ruta_texto = (
    ANALYSIS_DIR
    / "texto_fundaciones_2.txt"
)


with open(
    ruta_texto,
    "w",
    encoding="utf-8"
) as archivo_texto:

    for datos_pagina in textos_paginas:

        archivo_texto.write(
            f"PÁGINA {datos_pagina['pagina']}\n"
        )

        archivo_texto.write(
            "=" * 60 + "\n"
        )

        archivo_texto.write(
            datos_pagina["texto"]
        )

        archivo_texto.write(
            "\n\n"
        )


print("Texto extraído correctamente.")
print("Ubicación:", ruta_texto)

print()
print("=" * 60)
print("FASE 2 - EXPERIMENTO 2: COMPARAR ORDENAMIENTO")
print("=" * 60)


with pymupdf.open(pdf_detalles_path) as documento_detalles:

    pagina = documento_detalles[0]

    rotacion = pagina.rotation

    texto_sin_ordenar = pagina.get_text(
        "text",
        sort=False
    )

    texto_ordenado = pagina.get_text(
        "text",
        sort=True
    )


print("Rotación de la página:", rotacion)

print(
    "Caracteres sin sort:",
    len(texto_sin_ordenar)
)

print(
    "Caracteres con sort:",
    len(texto_ordenado)
)

print()
print("=" * 60)
print("FASE 2 - EXPERIMENTO 3: LOCALIZAR EL CUADRO")
print("=" * 60)


palabras_detalles = []


with pymupdf.open(pdf_detalles_path) as documento_detalles:

    pagina = documento_detalles[0]

    palabras_pagina = pagina.get_text(
        "words",
        sort=False
    )

    for palabra in palabras_pagina:

        (
            x0,
            y0,
            x1,
            y1,
            texto,
            numero_bloque,
            numero_linea,
            numero_palabra,
        ) = palabra

        datos_palabra = {
            "texto": texto.strip(),
            "x0": round(x0, 2),
            "y0": round(y0, 2),
            "x1": round(x1, 2),
            "y1": round(y1, 2),
            "numero_bloque": numero_bloque,
            "numero_linea": numero_linea,
            "numero_palabra": numero_palabra,
        }

        palabras_detalles.append(datos_palabra)


encabezados_buscados = {
    "TIPO",
    "X",
    "Y",
    "H",
    "ARMADURA",
    "PEDESTAL",
}


print("ENCABEZADOS ENCONTRADOS")
print("-" * 40)


for palabra in palabras_detalles:

    texto_mayuscula = palabra["texto"].upper()

    if texto_mayuscula in encabezados_buscados:

        print(
            palabra["texto"],
            "->",
            "X:",
            palabra["x0"],
            "Y:",
            palabra["y0"]
        )


print()
print("REFERENCIAS F ENCONTRADAS")
print("-" * 40)


for palabra in palabras_detalles:

    texto = palabra["texto"].strip()

    if patron_fundacion.fullmatch(texto):

        print(
            texto,
            "->",
            "X:",
            palabra["x0"],
            "Y:",
            palabra["y0"]
        )

print()
print("=" * 60)
print("FASE 2 - EXPERIMENTO 4: FILTRAR FILAS DEL CUADRO")
print("=" * 60)


encabezado_tipo = None


for palabra in palabras_detalles:

    texto = palabra["texto"].strip().upper()

    if texto == "TIPO":

        encabezado_tipo = palabra

        break


if encabezado_tipo is None:

    raise ValueError(
        "No se encontró el encabezado TIPO."
    )


referencias_cuadro = []


for palabra in palabras_detalles:

    texto = palabra["texto"].strip().upper()

    es_referencia = patron_fundacion.fullmatch(
        texto
    )

    esta_debajo_del_encabezado = (
        palabra["x0"] < encabezado_tipo["x0"]
    )

    esta_en_columna_tipo = (
        abs(
            palabra["y0"]
            - encabezado_tipo["y0"]
        )
        <= 8
    )

    if (
        es_referencia
        and esta_debajo_del_encabezado
        and esta_en_columna_tipo
    ):

        referencias_cuadro.append(
            palabra
        )


referencias_cuadro.sort(
    key=lambda palabra: palabra["x0"],
    reverse=True
)


print(
    "Cantidad de filas encontradas:",
    len(referencias_cuadro)
)


for numero_fila, referencia in enumerate(
    referencias_cuadro,
    start=1
):

    print(
        "Fila",
        numero_fila,
        "->",
        referencia["texto"],
        "| X:",
        referencia["x0"],
        "| Y:",
        referencia["y0"]
    )

print()
print("=" * 60)
print("FASE 2 - EXPERIMENTO 5: ENCABEZADOS DE DIMENSIONES")
print("=" * 60)


encabezados_dimensiones = {}


for palabra in palabras_detalles:

    texto = palabra["texto"].strip().upper()

    es_dimension = texto in {
        "X",
        "Y",
        "H",
    }

    esta_alineada_con_tipo = (
        abs(
            palabra["x0"]
            - encabezado_tipo["x0"]
        )
        <= 3
    )

    if (
        es_dimension
        and esta_alineada_con_tipo
    ):

        encabezados_dimensiones[texto] = palabra


dimensiones_requeridas = {
    "X",
    "Y",
    "H",
}


dimensiones_encontradas = set(
    encabezados_dimensiones.keys()
)


dimensiones_faltantes = (
    dimensiones_requeridas
    - dimensiones_encontradas
)


if dimensiones_faltantes:

    raise ValueError(
        "No se encontraron estos encabezados: "
        + ", ".join(dimensiones_faltantes)
    )


for nombre in ["X", "Y", "H"]:

    encabezado = encabezados_dimensiones[nombre]

    print(
        nombre,
        "->",
        "X:",
        encabezado["x0"],
        "| Y:",
        encabezado["y0"]
    )

print()
print("=" * 60)
print("FASE 2 - EXPERIMENTO 6: EXTRAER DIMENSIONES")
print("=" * 60)


patron_numero = re.compile(
    r"^\d+(?:[.,]\d+)?$"
)


def buscar_valor_dimension(
    referencia,
    encabezado
):

    candidatos = []

    for palabra in palabras_detalles:

        texto = palabra["texto"].strip()

        es_numero = patron_numero.fullmatch(
            texto
        )

        esta_en_la_misma_fila = (
            abs(
                palabra["x0"]
                - referencia["x0"]
            )
            <= 3
        )

        esta_en_la_misma_columna = (
            abs(
                palabra["y0"]
                - encabezado["y0"]
            )
            <= 5
        )

        if (
            es_numero
            and esta_en_la_misma_fila
            and esta_en_la_misma_columna
        ):

            candidatos.append(
                palabra
            )

    if not candidatos:

        return None

    candidato_mas_cercano = min(
        candidatos,
        key=lambda palabra: (
            abs(
                palabra["x0"]
                - referencia["x0"]
            )
            +
            abs(
                palabra["y0"]
                - encabezado["y0"]
            )
        )
    )

    return candidato_mas_cercano["texto"]


filas_dimensiones = []


for referencia in referencias_cuadro:

    valor_x = buscar_valor_dimension(
        referencia,
        encabezados_dimensiones["X"]
    )

    valor_y = buscar_valor_dimension(
        referencia,
        encabezados_dimensiones["Y"]
    )

    valor_h = buscar_valor_dimension(
        referencia,
        encabezados_dimensiones["H"]
    )

    datos_fila = {
        "referencia": referencia["texto"],
        "x": valor_x,
        "y": valor_y,
        "h": valor_h,
    }

    filas_dimensiones.append(
        datos_fila
    )


for numero_fila, fila in enumerate(
    filas_dimensiones,
    start=1
):

    print(
        "Fila",
        numero_fila,
        "->",
        fila["referencia"],
        "| X:",
        fila["x"],
        "| Y:",
        fila["y"],
        "| h:",
        fila["h"]
    )

print()
print("=" * 60)
print("FASE 2 - EXPERIMENTO 7: VALIDAR REFERENCIAS")
print("=" * 60)


referencias_planta = set(
    conteo_fundaciones.keys()
)


lista_referencias_cuadro = [
    fila["referencia"].upper()
    for fila in filas_dimensiones
]


conteo_referencias_cuadro = Counter(
    lista_referencias_cuadro
)


referencias_unicas_cuadro = set(
    lista_referencias_cuadro
)


faltantes_en_cuadro = (
    referencias_planta
    - referencias_unicas_cuadro
)


sobrantes_en_cuadro = (
    referencias_unicas_cuadro
    - referencias_planta
)


duplicadas_en_cuadro = {
    referencia: cantidad
    for referencia, cantidad
    in conteo_referencias_cuadro.items()
    if cantidad > 1
}


print(
    "Referencias en la planta:",
    sorted(referencias_planta)
)


print(
    "Referencias únicas en el cuadro:",
    sorted(referencias_unicas_cuadro)
)


print(
    "Faltantes en el cuadro:",
    sorted(faltantes_en_cuadro)
)


print(
    "Sobrantes en el cuadro:",
    sorted(sobrantes_en_cuadro)
)


print(
    "Duplicadas en el cuadro:",
    duplicadas_en_cuadro
)

print()
print("=" * 60)
print("FASE 2 - EXPERIMENTO 8: CORREGIR REFERENCIA")
print("=" * 60)


apariciones_por_referencia = {}


filas_corregidas = []


for numero_fila, fila in enumerate(
    filas_dimensiones,
    start=1
):

    referencia_original = (
        fila["referencia"].strip().upper()
    )

    cantidad_anterior = (
        apariciones_por_referencia.get(
            referencia_original,
            0
        )
    )

    numero_aparicion = (
        cantidad_anterior + 1
    )

    apariciones_por_referencia[
        referencia_original
    ] = numero_aparicion

    referencia_corregida = (
        referencia_original
    )

    fue_corregida = False

    motivo_correccion = None

    if (
        referencia_original == "F12"
        and numero_aparicion == 2
        and "F13" in faltantes_en_cuadro
    ):

        referencia_corregida = "F13"

        fue_corregida = True

        motivo_correccion = (
            "Segunda aparición de F12 corregida "
            "manualmente a F13."
        )

    datos_corregidos = {
        "numero_fila": numero_fila,
        "referencia_original": referencia_original,
        "referencia": referencia_corregida,
        "fue_corregida": fue_corregida,
        "motivo_correccion": motivo_correccion,
        "x": fila["x"],
        "y": fila["y"],
        "h": fila["h"],
    }

    filas_corregidas.append(
        datos_corregidos
    )


print("FILAS DESPUÉS DE LA CORRECCIÓN")
print("-" * 40)


for fila in filas_corregidas:

    if fila["fue_corregida"]:

        estado = (
            "CORREGIDA DESDE "
            + fila["referencia_original"]
        )

    else:

        estado = "ORIGINAL"

    print(
        "Fila",
        fila["numero_fila"],
        "->",
        fila["referencia"],
        "| X:",
        fila["x"],
        "| Y:",
        fila["y"],
        "| h:",
        fila["h"],
        "|",
        estado
    )


referencias_corregidas = [
    fila["referencia"]
    for fila in filas_corregidas
]


conteo_referencias_corregidas = Counter(
    referencias_corregidas
)


referencias_corregidas_unicas = set(
    referencias_corregidas
)


faltantes_despues_correccion = (
    referencias_planta
    - referencias_corregidas_unicas
)


sobrantes_despues_correccion = (
    referencias_corregidas_unicas
    - referencias_planta
)


duplicadas_despues_correccion = {
    referencia: cantidad
    for referencia, cantidad
    in conteo_referencias_corregidas.items()
    if cantidad > 1
}


print()
print("VALIDACIÓN DESPUÉS DE LA CORRECCIÓN")
print("-" * 40)


print(
    "Faltantes:",
    sorted(faltantes_despues_correccion)
)


print(
    "Sobrantes:",
    sorted(sobrantes_despues_correccion)
)


print(
    "Duplicadas:",
    duplicadas_despues_correccion
)

print()
print("=" * 60)
print("FASE 2 - EXPERIMENTO 9: CALCULAR VOLÚMENES")
print("=" * 60)


def convertir_dimension(valor):

    if valor is None:

        return None

    valor_normalizado = (
        valor
        .strip()
        .replace(",", ".")
    )

    try:

        return Decimal(
            valor_normalizado
        )

    except InvalidOperation:

        return None


computos_fundaciones = []


for fila in filas_corregidas:

    referencia = fila["referencia"]

    dimension_x = convertir_dimension(
        fila["x"]
    )

    dimension_y = convertir_dimension(
        fila["y"]
    )

    altura = convertir_dimension(
        fila["h"]
    )

    if (
        dimension_x is None
        or dimension_y is None
        or altura is None
    ):

        raise ValueError(
            "No se pudieron convertir las "
            f"dimensiones de {referencia}."
        )

    cantidad = conteo_fundaciones.get(
        referencia,
        0
    )

    volumen_unitario = (
        dimension_x
        * dimension_y
        * altura
    )

    volumen_total = (
        volumen_unitario
        * cantidad
    )

    computo = {
        "referencia": referencia,
        "cantidad": cantidad,
        "x": dimension_x,
        "y": dimension_y,
        "h": altura,
        "volumen_unitario": volumen_unitario,
        "volumen_total": volumen_total,
    }

    computos_fundaciones.append(
        computo
    )


volumen_general = sum(
    computo["volumen_total"]
    for computo in computos_fundaciones
)


for computo in computos_fundaciones:

    print(
        computo["referencia"],
        "| Cantidad:",
        computo["cantidad"],
        "| X:",
        computo["x"],
        "| Y:",
        computo["y"],
        "| h:",
        computo["h"],
        "| Vol. unitario:",
        f"{computo['volumen_unitario']:.3f}",
        "m³",
        "| Vol. total:",
        f"{computo['volumen_total']:.3f}",
        "m³"
    )


print("-" * 60)

print(
    "VOLUMEN GENERAL:",
    f"{volumen_general:.3f}",
    "m³"
)

print()
print("=" * 60)
print("FASE 2 - EXPERIMENTO 10: GENERAR REPORTE CSV")
print("=" * 60)


def formatear_decimal(
    valor,
    decimales=3
):

    texto = (
        f"{valor:.{decimales}f}"
    )

    return texto.replace(
        ".",
        ","
    )


ruta_reporte = (
    REPORT_DIR
    / "computo_fundaciones.csv"
)


with open(
    ruta_reporte,
    "w",
    newline="",
    encoding="utf-8-sig"
) as archivo_csv:

    escritor = csv.writer(
        archivo_csv,
        delimiter=";"
    )

    escritor.writerow([
        "Referencia",
        "Cantidad",
        "X (m)",
        "Y (m)",
        "h (m)",
        "Volumen unitario (m³)",
        "Volumen total (m³)",
    ])

    for computo in computos_fundaciones:

        escritor.writerow([
            computo["referencia"],
            computo["cantidad"],
            formatear_decimal(
                computo["x"],
                2
            ),
            formatear_decimal(
                computo["y"],
                2
            ),
            formatear_decimal(
                computo["h"],
                2
            ),
            formatear_decimal(
                computo["volumen_unitario"],
                3
            ),
            formatear_decimal(
                computo["volumen_total"],
                3
            ),
        ])

    escritor.writerow([])

    escritor.writerow([
        "TOTAL",
        "",
        "",
        "",
        "",
        "",
        formatear_decimal(
            volumen_general,
            3
        ),
    ])


print("Reporte generado correctamente.")
print("Ubicación:", ruta_reporte)

print()
print("=" * 60)
print("FASE 3 - EXPERIMENTO 1: EXTRAER TEXTO DE ARMADURA")
print("=" * 60)


encabezado_pedestal = None


for palabra in palabras_detalles:

    texto = palabra["texto"].strip().upper()

    es_pedestal = (
        texto == "PEDESTAL"
    )

    esta_alineado_con_tipo = (
        abs(
            palabra["x0"]
            - encabezado_tipo["x0"]
        )
        <= 3
    )

    if (
        es_pedestal
        and esta_alineado_con_tipo
    ):

        encabezado_pedestal = palabra

        break


if encabezado_pedestal is None:

    raise ValueError(
        "No se encontró el encabezado PEDESTAL."
    )


inicio_columna_armadura = (
    encabezados_dimensiones["H"]["y0"]
    + 10
)


fin_columna_armadura = (
    encabezado_pedestal["y0"]
    - 10
)


armaduras_extraidas = []


for indice, referencia in enumerate(
    referencias_cuadro
):

    if indice == 0:

        limite_superior_fila = (
            encabezado_tipo["x0"]
        )

    else:

        referencia_anterior = (
            referencias_cuadro[indice - 1]
        )

        limite_superior_fila = (
            referencia_anterior["x0"]
            + referencia["x0"]
        ) / 2

    if indice == len(
        referencias_cuadro
    ) - 1:

        distancia_fila_anterior = (
            referencias_cuadro[indice - 1]["x0"]
            - referencia["x0"]
        )

        limite_inferior_fila = (
            referencia["x0"]
            - distancia_fila_anterior / 2
        )

    else:

        referencia_siguiente = (
            referencias_cuadro[indice + 1]
        )

        limite_inferior_fila = (
            referencia["x0"]
            + referencia_siguiente["x0"]
        ) / 2

    palabras_armadura = []

    for palabra in palabras_detalles:

        esta_en_la_fila = (
            limite_inferior_fila
            <= palabra["x0"]
            < limite_superior_fila
        )

        esta_en_columna_armadura = (
            inicio_columna_armadura
            <= palabra["y0"]
            <= fin_columna_armadura
        )

        if (
            esta_en_la_fila
            and esta_en_columna_armadura
        ):

            palabras_armadura.append(
                palabra
            )

    palabras_armadura.sort(
        key=lambda palabra: (
            -palabra["x0"],
            palabra["y0"]
        )
    )

    texto_armadura = " ".join(
        palabra["texto"]
        for palabra in palabras_armadura
    )

    datos_armadura = {
        "referencia_original": (
            referencia["texto"]
        ),
        "referencia": (
            filas_corregidas[indice][
                "referencia"
            ]
        ),
        "texto_armadura": texto_armadura,
        "palabras": palabras_armadura,
    }

    armaduras_extraidas.append(
        datos_armadura
    )


for armadura in armaduras_extraidas:

    print("-" * 40)

    print(
        armadura["referencia"],
        "->",
        armadura["texto_armadura"]
    )

print()
print("=" * 60)
print("FASE 3 - EXPERIMENTO 2: SEPARAR ARMADURAS")
print("=" * 60)


armaduras_separadas = []


for armadura in armaduras_extraidas:

    palabras = armadura["palabras"]

    etiqueta_superior = None

    etiqueta_inferior = None

    for palabra in palabras:

        texto = palabra["texto"].strip().upper()

        if texto == "SUPERIOR":

            etiqueta_superior = palabra

        elif texto == "INFERIOR":

            etiqueta_inferior = palabra

    if (
        etiqueta_superior is None
        or etiqueta_inferior is None
    ):

        raise ValueError(
            "No se encontraron las etiquetas "
            f"SUPERIOR e INFERIOR para "
            f"{armadura['referencia']}."
        )

    palabras_superiores = []

    palabras_inferiores = []

    for palabra in palabras:

        texto = palabra["texto"].strip().upper()

        if texto in {
            "SUPERIOR",
            "INFERIOR",
        }:

            continue

        distancia_superior = abs(
            palabra["x0"]
            - etiqueta_superior["x0"]
        )

        distancia_inferior = abs(
            palabra["x0"]
            - etiqueta_inferior["x0"]
        )

        if (
            distancia_superior
            < distancia_inferior
        ):

            palabras_superiores.append(
                palabra
            )

        else:

            palabras_inferiores.append(
                palabra
            )

    palabras_superiores.sort(
        key=lambda palabra: (
            -palabra["x0"],
            palabra["y0"]
        )
    )

    palabras_inferiores.sort(
        key=lambda palabra: (
            -palabra["x0"],
            palabra["y0"]
        )
    )

    texto_superior = " ".join(
        palabra["texto"]
        for palabra in palabras_superiores
    )

    texto_inferior = " ".join(
        palabra["texto"]
        for palabra in palabras_inferiores
    )

    resultado_armadura = {
        "referencia_original": (
            armadura["referencia_original"]
        ),
        "referencia": (
            armadura["referencia"]
        ),
        "armadura_superior": texto_superior,
        "armadura_inferior": texto_inferior,
    }

    armaduras_separadas.append(
        resultado_armadura
    )


print(
    "Cantidad de fundaciones procesadas:",
    len(armaduras_separadas)
)


for armadura in armaduras_separadas:

    print("-" * 40)

    print(
        "Referencia:",
        armadura["referencia"]
    )

    print(
        "Superior:",
        armadura["armadura_superior"]
        or "Sin armadura indicada"
    )

    print(
        "Inferior:",
        armadura["armadura_inferior"]
        or "Sin armadura indicada"
    )

print()
print("=" * 60)
print("FASE 3 - EXPERIMENTO 3: INTERPRETAR ARMADURAS")
print("=" * 60)


patron_armadura_direccional = re.compile(
    r"AS\s+([XY])\s*=\s*"
    r"(\d+)\s*"
    r"Ø\s*"
    r"(\d+/\d+)\"\s*"
    r"C/D\s*"
    r"(\d+)\s*"
    r"CMS?\.?",
    re.IGNORECASE
)


patron_armadura_ambos_sentidos = re.compile(
    r"(\d+)\s*"
    r"Ø\s*"
    r"(\d+/\d+)\"\s*"
    r"C/D\s*"
    r"(\d+)\s*"
    r"CMS?\.?\s*"
    r"A/S\.?",
    re.IGNORECASE
)


def interpretar_armadura(
    referencia,
    nivel,
    texto_armadura
):

    resultados = []

    if not texto_armadura:

        return resultados

    coincidencias_direccionales = (
        patron_armadura_direccional.finditer(
            texto_armadura
        )
    )

    for coincidencia in coincidencias_direccionales:

        resultado = {
            "referencia": referencia,
            "nivel": nivel,
            "direccion": coincidencia.group(1).upper(),
            "cantidad_indicada": int(
                coincidencia.group(2)
            ),
            "diametro_pulgadas": (
                coincidencia.group(3)
            ),
            "separacion_cm": int(
                coincidencia.group(4)
            ),
            "texto_original": texto_armadura,
        }

        resultados.append(
            resultado
        )

    if resultados:

        return resultados

    coincidencia_ambos_sentidos = (
        patron_armadura_ambos_sentidos.fullmatch(
            texto_armadura.strip()
        )
    )

    if coincidencia_ambos_sentidos:

        resultado = {
            "referencia": referencia,
            "nivel": nivel,
            "direccion": "AMBOS_SENTIDOS",
            "cantidad_indicada": int(
                coincidencia_ambos_sentidos.group(1)
            ),
            "diametro_pulgadas": (
                coincidencia_ambos_sentidos.group(2)
            ),
            "separacion_cm": int(
                coincidencia_ambos_sentidos.group(3)
            ),
            "texto_original": texto_armadura,
        }

        resultados.append(
            resultado
        )

    return resultados


armaduras_interpretadas = []


for armadura in armaduras_separadas:

    referencia = armadura["referencia"]

    resultados_superiores = interpretar_armadura(
        referencia,
        "SUPERIOR",
        armadura["armadura_superior"]
    )

    resultados_inferiores = interpretar_armadura(
        referencia,
        "INFERIOR",
        armadura["armadura_inferior"]
    )

    armaduras_interpretadas.extend(
        resultados_superiores
    )

    armaduras_interpretadas.extend(
        resultados_inferiores
    )


print(
    "Cantidad de especificaciones interpretadas:",
    len(armaduras_interpretadas)
)


for armadura in armaduras_interpretadas:

    print("-" * 40)

    print(
        "Referencia:",
        armadura["referencia"]
    )

    print(
        "Nivel:",
        armadura["nivel"]
    )

    print(
        "Dirección:",
        armadura["direccion"]
    )

    print(
        "Cantidad indicada:",
        armadura["cantidad_indicada"]
    )

    print(
        "Diámetro:",
        armadura["diametro_pulgadas"],
        "pulgadas"
    )

    print(
        "Separación:",
        armadura["separacion_cm"],
        "cm"
    )


print()
print("=" * 60)
print("FASE 3 - EXPERIMENTO 4: PESO UNITARIO DEL ACERO")
print("=" * 60)


def convertir_fraccion_pulgadas(
    fraccion
):

    numerador_texto, denominador_texto = (
        fraccion.split("/")
    )

    numerador = Decimal(
        numerador_texto
    )

    denominador = Decimal(
        denominador_texto
    )

    pulgadas = (
        numerador
        / denominador
    )

    return pulgadas


def calcular_datos_diametro(
    diametro_pulgadas
):

    pulgadas = convertir_fraccion_pulgadas(
        diametro_pulgadas
    )

    diametro_mm = (
        pulgadas
        * Decimal("25.4")
    )

    peso_kg_m = (
        diametro_mm ** 2
        / Decimal("162")
    )

    return {
        "diametro_pulgadas": diametro_pulgadas,
        "diametro_mm": diametro_mm,
        "peso_kg_m": peso_kg_m,
    }


diametros_encontrados = {
    armadura["diametro_pulgadas"]
    for armadura in armaduras_interpretadas
}


datos_por_diametro = {}


for diametro in diametros_encontrados:

    datos_diametro = calcular_datos_diametro(
        diametro
    )

    datos_por_diametro[
        diametro
    ] = datos_diametro


armaduras_con_peso_unitario = []


for armadura in armaduras_interpretadas:

    diametro = armadura[
        "diametro_pulgadas"
    ]

    datos_diametro = (
        datos_por_diametro[diametro]
    )

    armadura_actualizada = (
        armadura.copy()
    )

    armadura_actualizada[
        "diametro_mm"
    ] = datos_diametro[
        "diametro_mm"
    ]

    armadura_actualizada[
        "peso_kg_m"
    ] = datos_diametro[
        "peso_kg_m"
    ]

    armaduras_con_peso_unitario.append(
        armadura_actualizada
    )


for diametro in sorted(
    datos_por_diametro.keys()
):

    datos = datos_por_diametro[
        diametro
    ]

    print(
        diametro,
        "pulgadas",
        "->",
        f"{datos['diametro_mm']:.3f}",
        "mm",
        "->",
        f"{datos['peso_kg_m']:.3f}",
        "kg/m"
    )

print()
print("=" * 60)
print("FASE 3 - EXPERIMENTO 5: EXPANDIR DIRECCIONES")
print("=" * 60)


armaduras_por_direccion = []


for armadura in armaduras_con_peso_unitario:

    direccion_original = armadura[
        "direccion"
    ]

    if direccion_original == "AMBOS_SENTIDOS":

        direcciones = [
            "X",
            "Y",
        ]

    else:

        direcciones = [
            direccion_original
        ]

    for direccion in direcciones:

        armadura_direccion = (
            armadura.copy()
        )

        armadura_direccion[
            "direccion_original"
        ] = direccion_original

        armadura_direccion[
            "direccion"
        ] = direccion

        armaduras_por_direccion.append(
            armadura_direccion
        )


print(
    "Especificaciones originales:",
    len(armaduras_con_peso_unitario)
)


print(
    "Registros por dirección:",
    len(armaduras_por_direccion)
)


for armadura in armaduras_por_direccion:

    print("-" * 40)

    print(
        armadura["referencia"],
        "|",
        armadura["nivel"],
        "| Dirección:",
        armadura["direccion"],
        "| Diámetro:",
        armadura["diametro_pulgadas"],
        "pulgadas",
        "| Separación:",
        armadura["separacion_cm"],
        "cm"
    )

print()
print("=" * 60)
print("FASE 3 - EXPERIMENTO 6: CANTIDAD DE BARRAS")
print("=" * 60)


recubrimiento_m = (
    RECUBRIMIENTO_FUNDACION_CM
    / Decimal("100")
)


dimensiones_por_referencia = {
    computo["referencia"]: computo
    for computo in computos_fundaciones
}


conteos_barras = []


for armadura in armaduras_por_direccion:

    referencia = armadura["referencia"]

    direccion = armadura["direccion"]

    dimensiones = (
        dimensiones_por_referencia[
            referencia
        ]
    )

    if direccion == "X":

        dimension_distribucion = (
            dimensiones["y"]
        )

    else:

        dimension_distribucion = (
            dimensiones["x"]
        )

    longitud_disponible = (
        dimension_distribucion
        - Decimal("2") * recubrimiento_m
    )

    separacion_m = (
        Decimal(
            str(
                armadura["separacion_cm"]
            )
        )
        / Decimal("100")
    )

    cantidad_intervalos = (
        longitud_disponible
        / separacion_m
    ).to_integral_value(
        rounding=ROUND_CEILING
    )

    cantidad_posiciones = (
        int(cantidad_intervalos)
        + 1
    )

    cantidad_barras = (
        cantidad_posiciones
        * armadura["cantidad_indicada"]
    )

    if cantidad_posiciones > 1:

        separacion_real_m = (
            longitud_disponible
            / Decimal(
                cantidad_posiciones - 1
            )
        )

    else:

        separacion_real_m = Decimal("0")

    resultado_conteo = (
        armadura.copy()
    )

    resultado_conteo[
        "dimension_distribucion_m"
    ] = dimension_distribucion

    resultado_conteo[
        "longitud_disponible_m"
    ] = longitud_disponible

    resultado_conteo[
        "separacion_m"
    ] = separacion_m

    resultado_conteo[
        "cantidad_posiciones"
    ] = cantidad_posiciones

    resultado_conteo[
        "cantidad_barras"
    ] = cantidad_barras

    resultado_conteo[
        "separacion_real_m"
    ] = separacion_real_m

    conteos_barras.append(
        resultado_conteo
    )


print(
    "Recubrimiento utilizado:",
    RECUBRIMIENTO_FUNDACION_CM,
    "cm"
)


print(
    "Registros calculados:",
    len(conteos_barras)
)


for resultado in conteos_barras:

    print("-" * 40)

    print(
        resultado["referencia"],
        "|",
        resultado["nivel"],
        "| Dirección:",
        resultado["direccion"]
    )

    print(
        "Dimensión de distribución:",
        resultado[
            "dimension_distribucion_m"
        ],
        "m"
    )

    print(
        "Longitud disponible:",
        resultado[
            "longitud_disponible_m"
        ],
        "m"
    )

    print(
        "Separación indicada:",
        resultado["separacion_cm"],
        "cm"
    )

    print(
        "Cantidad de barras:",
        resultado["cantidad_barras"]
    )

    print(
        "Separación real:",
        f"{resultado['separacion_real_m']:.3f}",
        "m"
    )

print()
print("=" * 60)
print("FASE 3 - EXPERIMENTO 7: CALCULAR PESO DEL ACERO")
print("=" * 60)


longitud_doblez_m = (
    LONGITUD_DOBLEZ_CM
    / Decimal("100")
)


computos_acero = []


for conteo in conteos_barras:

    referencia = conteo["referencia"]

    direccion = conteo["direccion"]

    dimensiones = (
        dimensiones_por_referencia[
            referencia
        ]
    )

    if direccion == "X":

        dimension_longitudinal = (
            dimensiones["x"]
        )

    else:

        dimension_longitudinal = (
            dimensiones["y"]
        )

    longitud_recta_m = (
        dimension_longitudinal
        - Decimal("2") * recubrimiento_m
    )

    longitud_barra_m = (
        longitud_recta_m
        + Decimal("2") * longitud_doblez_m
    )

    cantidad_barras = Decimal(
        conteo["cantidad_barras"]
    )

    metros_por_fundacion = (
        cantidad_barras
        * longitud_barra_m
    )

    peso_por_fundacion_kg = (
        metros_por_fundacion
        * conteo["peso_kg_m"]
    )

    cantidad_fundaciones = (
        conteo_fundaciones.get(
            referencia,
            0
        )
    )

    metros_totales = (
        metros_por_fundacion
        * cantidad_fundaciones
    )

    peso_total_kg = (
        peso_por_fundacion_kg
        * cantidad_fundaciones
    )

    computo_acero = conteo.copy()

    computo_acero[
        "dimension_longitudinal_m"
    ] = dimension_longitudinal

    computo_acero[
        "longitud_recta_m"
    ] = longitud_recta_m

    computo_acero[
        "longitud_doblez_m"
    ] = longitud_doblez_m

    computo_acero[
        "longitud_barra_m"
    ] = longitud_barra_m

    computo_acero[
        "metros_por_fundacion"
    ] = metros_por_fundacion

    computo_acero[
        "peso_por_fundacion_kg"
    ] = peso_por_fundacion_kg

    computo_acero[
        "cantidad_fundaciones"
    ] = cantidad_fundaciones

    computo_acero[
        "metros_totales"
    ] = metros_totales

    computo_acero[
        "peso_total_kg"
    ] = peso_total_kg

    computos_acero.append(
        computo_acero
    )


metros_generales_acero = sum(
    (
        computo["metros_totales"]
        for computo in computos_acero
    ),
    Decimal("0")
)


peso_general_acero_kg = sum(
    (
        computo["peso_total_kg"]
        for computo in computos_acero
    ),
    Decimal("0")
)


print(
    "Doblez utilizado por extremo:",
    LONGITUD_DOBLEZ_CM,
    "cm"
)


print(
    "Registros calculados:",
    len(computos_acero)
)


for computo in computos_acero:

    print("-" * 40)

    print(
        computo["referencia"],
        "|",
        computo["nivel"],
        "| Dirección:",
        computo["direccion"]
    )

    print(
        "Cantidad de fundaciones:",
        computo["cantidad_fundaciones"]
    )

    print(
        "Barras por fundación:",
        computo["cantidad_barras"]
    )

    print(
        "Longitud de cada barra:",
        f"{computo['longitud_barra_m']:.3f}",
        "m"
    )

    print(
        "Metros por fundación:",
        f"{computo['metros_por_fundacion']:.3f}",
        "m"
    )

    print(
        "Peso por fundación:",
        f"{computo['peso_por_fundacion_kg']:.3f}",
        "kg"
    )

    print(
        "Metros totales:",
        f"{computo['metros_totales']:.3f}",
        "m"
    )

    print(
        "Peso total:",
        f"{computo['peso_total_kg']:.3f}",
        "kg"
    )


print("=" * 60)

print(
    "METROS GENERALES DE ACERO:",
    f"{metros_generales_acero:.3f}",
    "m"
)


print(
    "PESO GENERAL DEL ACERO:",
    f"{peso_general_acero_kg:.3f}",
    "kg"
)


print(
    "PESO GENERAL EN TONELADAS:",
    f"{peso_general_acero_kg / Decimal('1000'):.3f}",
    "t"
)

print()
print("=" * 60)
print("FASE 3 - EXPERIMENTO 8: RESUMEN POR DIÁMETRO")
print("=" * 60)


resumen_por_diametro = {}


for computo in computos_acero:

    diametro = computo[
        "diametro_pulgadas"
    ]

    if diametro not in resumen_por_diametro:

        resumen_por_diametro[diametro] = {
            "diametro_pulgadas": diametro,
            "diametro_mm": computo[
                "diametro_mm"
            ],
            "peso_kg_m": computo[
                "peso_kg_m"
            ],
            "metros_totales": Decimal("0"),
            "peso_total_kg": Decimal("0"),
        }

    resumen_por_diametro[
        diametro
    ]["metros_totales"] += computo[
        "metros_totales"
    ]

    resumen_por_diametro[
        diametro
    ]["peso_total_kg"] += computo[
        "peso_total_kg"
    ]


metros_agrupados = sum(
    (
        datos["metros_totales"]
        for datos in resumen_por_diametro.values()
    ),
    Decimal("0")
)


peso_agrupado_kg = sum(
    (
        datos["peso_total_kg"]
        for datos in resumen_por_diametro.values()
    ),
    Decimal("0")
)


for diametro, datos in sorted(
    resumen_por_diametro.items()
):

    print("-" * 40)

    print(
        "Diámetro:",
        diametro,
        "pulgadas"
    )

    print(
        "Diámetro en milímetros:",
        f"{datos['diametro_mm']:.3f}",
        "mm"
    )

    print(
        "Peso unitario:",
        f"{datos['peso_kg_m']:.3f}",
        "kg/m"
    )

    print(
        "Metros totales:",
        f"{datos['metros_totales']:.3f}",
        "m"
    )

    print(
        "Peso total:",
        f"{datos['peso_total_kg']:.3f}",
        "kg"
    )


print("=" * 60)

print(
    "Metros agrupados:",
    f"{metros_agrupados:.3f}",
    "m"
)


print(
    "Metros calculados anteriormente:",
    f"{metros_generales_acero:.3f}",
    "m"
)


print(
    "Peso agrupado:",
    f"{peso_agrupado_kg:.3f}",
    "kg"
)


print(
    "Peso calculado anteriormente:",
    f"{peso_general_acero_kg:.3f}",
    "kg"
)


diferencia_metros = abs(
    metros_agrupados
    - metros_generales_acero
)


diferencia_peso = abs(
    peso_agrupado_kg
    - peso_general_acero_kg
)


tolerancia_metros = Decimal(
    "0.001"
)


tolerancia_peso = Decimal(
    "0.001"
)


print(
    "Diferencia en metros:",
    diferencia_metros
)


print(
    "Diferencia en peso:",
    diferencia_peso,
    "kg"
)


metros_coinciden = (
    diferencia_metros
    <= tolerancia_metros
)


pesos_coinciden = (
    diferencia_peso
    <= tolerancia_peso
)


if (
    metros_coinciden
    and pesos_coinciden
):

    print(
        "Validación correcta: "
        "los totales coinciden "
        "dentro de la tolerancia."
    )

else:

    print(
        "ADVERTENCIA: "
        "la diferencia supera "
        "la tolerancia permitida."
    )

print()
print("=" * 60)
print("FASE 3 - EXPERIMENTO 9: BARRAS COMERCIALES")
print("=" * 60)


factor_desperdicio_acero = (
    Decimal("1")
    + (
        DESPERDICIO_ACERO_PORCENTAJE
        / Decimal("100")
    )
)


compra_acero_por_diametro = []


for diametro, datos in sorted(
    resumen_por_diametro.items()
):

    metros_teoricos = datos[
        "metros_totales"
    ]

    metros_con_desperdicio = (
        metros_teoricos
        * factor_desperdicio_acero
    )

    cantidad_barras_decimal = (
        metros_con_desperdicio
        / LONGITUD_BARRA_COMERCIAL_M
    )

    cantidad_barras_comerciales = int(
        cantidad_barras_decimal.to_integral_value(
            rounding=ROUND_CEILING
        )
    )

    metros_comprados = (
        Decimal(
            cantidad_barras_comerciales
        )
        * LONGITUD_BARRA_COMERCIAL_M
    )

    excedente_metros = (
        metros_comprados
        - metros_teoricos
    )

    peso_teorico_kg = datos[
        "peso_total_kg"
    ]

    peso_con_desperdicio_kg = (
        metros_con_desperdicio
        * datos["peso_kg_m"]
    )

    peso_compra_kg = (
        metros_comprados
        * datos["peso_kg_m"]
    )

    compra_diametro = {
        "diametro_pulgadas": diametro,
        "diametro_mm": datos["diametro_mm"],
        "peso_kg_m": datos["peso_kg_m"],
        "metros_teoricos": metros_teoricos,
        "peso_teorico_kg": peso_teorico_kg,
        "porcentaje_desperdicio": (
            DESPERDICIO_ACERO_PORCENTAJE
        ),
        "metros_con_desperdicio": (
            metros_con_desperdicio
        ),
        "peso_con_desperdicio_kg": (
            peso_con_desperdicio_kg
        ),
        "longitud_barra_comercial_m": (
            LONGITUD_BARRA_COMERCIAL_M
        ),
        "cantidad_barras_comerciales": (
            cantidad_barras_comerciales
        ),
        "metros_comprados": metros_comprados,
        "peso_compra_kg": peso_compra_kg,
        "excedente_metros": excedente_metros,
    }

    compra_acero_por_diametro.append(
        compra_diametro
    )


cantidad_total_barras_comerciales = sum(
    compra["cantidad_barras_comerciales"]
    for compra in compra_acero_por_diametro
)


peso_total_compra_acero_kg = sum(
    (
        compra["peso_compra_kg"]
        for compra in compra_acero_por_diametro
    ),
    Decimal("0")
)


for compra in compra_acero_por_diametro:

    print("-" * 40)

    print(
        "Diámetro:",
        compra["diametro_pulgadas"],
        "pulgadas"
    )

    print(
        "Metros teóricos:",
        f"{compra['metros_teoricos']:.3f}",
        "m"
    )

    print(
        "Metros con desperdicio:",
        f"{compra['metros_con_desperdicio']:.3f}",
        "m"
    )

    print(
        "Barras comerciales:",
        compra["cantidad_barras_comerciales"],
        "de",
        compra["longitud_barra_comercial_m"],
        "m"
    )

    print(
        "Metros comprados:",
        f"{compra['metros_comprados']:.3f}",
        "m"
    )

    print(
        "Excedente respecto al teórico:",
        f"{compra['excedente_metros']:.3f}",
        "m"
    )

    print(
        "Peso teórico:",
        f"{compra['peso_teorico_kg']:.3f}",
        "kg"
    )

    print(
        "Peso con desperdicio:",
        f"{compra['peso_con_desperdicio_kg']:.3f}",
        "kg"
    )

    print(
        "Peso de compra:",
        f"{compra['peso_compra_kg']:.3f}",
        "kg"
    )


print("=" * 60)

print(
    "TOTAL DE BARRAS COMERCIALES:",
    cantidad_total_barras_comerciales
)


print(
    "PESO TOTAL DE COMPRA:",
    f"{peso_total_compra_acero_kg:.3f}",
    "kg"
)


print(
    "PESO TOTAL DE COMPRA EN TONELADAS:",
    f"{peso_total_compra_acero_kg / Decimal('1000'):.3f}",
    "t"
)

print()
print("=" * 60)
print("FASE 4 - EXPERIMENTO 1: ENCOFRADO DE ZAPATAS")
print("=" * 60)


computos_encofrado = []


for computo in computos_fundaciones:

    referencia = computo["referencia"]

    cantidad = computo["cantidad"]

    dimension_x = computo["x"]

    dimension_y = computo["y"]

    altura = computo["h"]

    perimetro = (
        Decimal("2")
        * (
            dimension_x
            + dimension_y
        )
    )

    if USAR_ENCOFRADO_ZAPATAS:

        area_unitaria = (
            perimetro
            * altura
        )

    else:

        area_unitaria = Decimal("0")

    area_total = (
        area_unitaria
        * cantidad
    )

    resultado_encofrado = {
        "referencia": referencia,
        "cantidad": cantidad,
        "x": dimension_x,
        "y": dimension_y,
        "h": altura,
        "perimetro_m": perimetro,
        "area_unitaria_m2": area_unitaria,
        "area_total_m2": area_total,
        "encofrado_activado": (
            USAR_ENCOFRADO_ZAPATAS
        ),
    }

    computos_encofrado.append(
        resultado_encofrado
    )


area_general_encofrado_m2 = sum(
    (
        computo["area_total_m2"]
        for computo in computos_encofrado
    ),
    Decimal("0")
)


print(
    "Encofrado de zapatas activado:",
    USAR_ENCOFRADO_ZAPATAS
)


for computo in computos_encofrado:

    print("-" * 40)

    print(
        computo["referencia"],
        "| Cantidad:",
        computo["cantidad"]
    )

    print(
        "Perímetro:",
        f"{computo['perimetro_m']:.3f}",
        "m"
    )

    print(
        "Área unitaria:",
        f"{computo['area_unitaria_m2']:.3f}",
        "m²"
    )

    print(
        "Área total:",
        f"{computo['area_total_m2']:.3f}",
        "m²"
    )


print("=" * 60)

print(
    "ÁREA GENERAL DE ENCOFRADO:",
    f"{area_general_encofrado_m2:.3f}",
    "m²"
)

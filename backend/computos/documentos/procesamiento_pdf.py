from pathlib import Path

import pymupdf


def validar_pdf(ruta_pdf: Path) -> None:
    if not ruta_pdf.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {ruta_pdf}")
    if ruta_pdf.suffix.lower() != ".pdf":
        raise ValueError(f"El archivo no es un PDF: {ruta_pdf}")


def extraer_palabras(ruta_pdf: Path, ordenar: bool = False) -> list[dict]:
    validar_pdf(ruta_pdf)
    palabras_extraidas = []

    with pymupdf.open(ruta_pdf) as documento:
        for numero_pagina, pagina in enumerate(documento, start=1):
            for palabra in pagina.get_text("words", sort=ordenar):
                x0, y0, x1, y1, texto, bloque, linea, posicion = palabra
                texto = texto.strip()
                if not texto:
                    continue

                palabras_extraidas.append(
                    {
                        "pagina": numero_pagina,
                        "texto": texto,
                        "x0": round(x0, 2),
                        "y0": round(y0, 2),
                        "x1": round(x1, 2),
                        "y1": round(y1, 2),
                        "numero_bloque": bloque,
                        "numero_linea": linea,
                        "numero_palabra": posicion,
                    }
                )

    return palabras_extraidas


def obtener_datos_documento(ruta_pdf: Path) -> dict:
    validar_pdf(ruta_pdf)
    with pymupdf.open(ruta_pdf) as documento:
        return {
            "archivo": ruta_pdf.name,
            "cantidad_paginas": len(documento),
            "paginas": [
                {
                    "pagina": indice + 1,
                    "ancho": pagina.rect.width,
                    "alto": pagina.rect.height,
                    "rotacion": pagina.rotation,
                    "cantidad_caracteres": len(
                        pagina.get_text("text", sort=False)
                    ),
                }
                for indice, pagina in enumerate(documento)
            ],
        }


def dibujar_rectangulos(
    ruta_pdf: Path,
    detecciones: list[dict],
    ruta_salida: Path,
    pagina_numero: int = 1,
    escala: int = 2,
) -> None:
    validar_pdf(ruta_pdf)
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)

    with pymupdf.open(ruta_pdf) as documento:
        pagina = documento[pagina_numero - 1]
        for deteccion in detecciones:
            if deteccion["pagina"] != pagina_numero:
                continue
            rectangulo = pymupdf.Rect(
                deteccion["x0"],
                deteccion["y0"],
                deteccion["x1"],
                deteccion["y1"],
            )
            pagina.draw_rect(
                rectangulo,
                color=(1, 0, 0),
                width=1,
                overlay=True,
            )

        imagen = pagina.get_pixmap(
            matrix=pymupdf.Matrix(escala, escala),
            alpha=False,
        )
        imagen.save(str(ruta_salida))

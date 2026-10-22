"""Inventaría proyectos PDF nuevos sin alterar ni extraer el ZIP recibido.

Ejemplo::

    python backend/experimentos/auditar_nuevos_proyectos.py \
        --zip "Nuevos_Proyectos.zip" \
        --zip-anterior "ComputoEstIA.zip"

Las carpetas son grupos provisionales. Este programa no crea etiquetas de
verdad terreno ni reentrena un modelo con proyectos reservados para evaluación.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import unicodedata
from zipfile import ZipFile

import pymupdf


PISTAS = {
    "fundaciones": ("fundacion", "cimentacion", "zapata", "cimientos"),
    "vigas": ("viga", "riostra"),
    "columnas": ("columna", "pilar"),
    "armaduras": ("armadura", "armado", "estribo"),
    "arquitectura": ("arquitectura", "fachada", "alzados"),
    "instalaciones": ("electrica", "sanitaria", "instalaciones"),
}


def normalizar(texto: str) -> str:
    sin_tildes = "".join(
        caracter for caracter in unicodedata.normalize("NFKD", texto.casefold())
        if not unicodedata.combining(caracter)
    )
    return " ".join(re.findall(r"\w+", sin_tildes))


def pistas(texto: str) -> list[str]:
    palabras = set(normalizar(texto).split())
    return sorted(nombre for nombre, terminos in PISTAS.items()
                  if any(palabra.startswith(termino) for palabra in palabras
                         for termino in terminos))


def huella_render_256(pagina: pymupdf.Page) -> str:
    escala = 256 / max(pagina.rect.width, pagina.rect.height)
    miniatura = pagina.get_pixmap(
        matrix=pymupdf.Matrix(escala, escala), alpha=False
    )
    return sha256(
        f"{miniatura.width}x{miniatura.height}".encode() + miniatura.samples
    ).hexdigest()


def indice_archivos_pdf(zip_anterior: Path | None, comparar_render: bool = False
                        ) -> tuple[dict[str, list[str]], dict[str, list[str]], int]:
    if zip_anterior is None:
        return {}, {}, 0
    indice: dict[str, list[str]] = defaultdict(list)
    visuales: dict[str, list[str]] = defaultdict(list)
    paginas = 0
    with ZipFile(zip_anterior) as archivo:
        for entrada in archivo.infolist():
            if not entrada.is_dir() and entrada.filename.casefold().endswith(".pdf"):
                datos = archivo.read(entrada)
                indice[sha256(datos).hexdigest()].append(entrada.filename)
                if comparar_render:
                    with pymupdf.open(stream=datos, filetype="pdf") as pdf:
                        for numero, pagina in enumerate(pdf, 1):
                            paginas += 1
                            visuales[huella_render_256(pagina)].append(
                                f"{entrada.filename}#pagina={numero}"
                            )
    return dict(indice), dict(visuales), paginas


def crear_plantilla_etiquetado(resultado: dict, salida: Path) -> None:
    """Prepara páginas para revisión humana sin mostrar predicciones ni pistas."""
    duplicados = {
        repetido: grupo[0]
        for grupo in resultado["paginas_iguales_al_renderizar_256"]
        for repetido in grupo[1:]
    }
    filas = []
    for pagina in resultado["paginas"]:
        identificador = f"{pagina['archivo']}#pagina={pagina['pagina']}"
        filas.append({
            "id_pagina": identificador,
            "fuente_provisional": pagina["proyecto_id"],
            "archivo_en_zip": pagina["archivo"],
            "pagina": pagina["pagina"],
            "posible_duplicado_de": duplicados.get(identificador),
            "incluir_en_metricas": identificador not in duplicados,
            "disciplinas": None,
            "roles_documentales": None,
            "contenidos": None,
            "decision": "pendiente_revision_humana",
            "ambiguo": None,
            "evidencia_profesional": "",
            "observaciones": "",
            "revisor": "",
        })
    plantilla = {
        "zip": resultado["origen"],
        "unidad": "pagina",
        "instrucciones": (
            "Abrir cada página visualmente y completar disciplinas, "
            "roles_documentales y contenidos con listas de etiquetas; "
            "no usar nombres ni pistas automáticas como verdad terreno. "
            "Confirmar procedencia y posibles duplicados antes de calcular métricas."
        ),
        "total_paginas": len(filas),
        "filas": filas,
    }
    (salida / "EXP11_PLANTILLA_ETIQUETADO.json").write_text(
        json.dumps(plantilla, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def auditar(zip_nuevo: Path, zip_anterior: Path | None, salida: Path,
            comparar_render_anterior: bool = False) -> dict:
    anteriores, visuales_anteriores, paginas_anteriores = indice_archivos_pdf(
        zip_anterior, comparar_render_anterior
    )
    paginas: list[dict] = []
    documentos: list[dict] = []
    errores = []
    hashes_nuevos: dict[str, list[str]] = defaultdict(list)
    imagenes_nuevas: dict[str, list[str]] = defaultdict(list)
    encontrados_en_anterior = []
    visuales_en_anterior = []
    proyectos = set()

    with ZipFile(zip_nuevo) as archivo:
        entradas = sorted(
            (e for e in archivo.infolist() if not e.is_dir()),
            key=lambda e: e.filename,
        )
        if any(e.flag_bits & 1 for e in entradas):
            raise ValueError("El ZIP contiene archivos cifrados")
        if any(e.file_size > 100 * 1024 * 1024 for e in entradas):
            raise ValueError("Un archivo del ZIP supera los 100 MB")
        if sum(e.file_size for e in entradas) > 1024 * 1024 * 1024:
            raise ValueError("El tamaño descomprimido supera 1 GB")
        if any(PurePosixPath(e.filename).is_absolute() or ".." in PurePosixPath(e.filename).parts
               for e in entradas):
            raise ValueError("El ZIP contiene rutas no válidas")

        for entrada in entradas:
            ruta = PurePosixPath(entrada.filename)
            if ruta.suffix.casefold() != ".pdf" or len(ruta.parts) < 2:
                errores.append({"archivo": entrada.filename, "error": "No es un PDF dentro de una carpeta de proyecto"})
                continue
            proyecto = ruta.parts[0]
            proyectos.add(proyecto)
            datos = archivo.read(entrada)
            huella = sha256(datos).hexdigest()
            hashes_nuevos[huella].append(entrada.filename)
            if huella in anteriores:
                encontrados_en_anterior.append({"archivo_nuevo": entrada.filename,
                                               "archivo_anterior": anteriores[huella]})
            registro = {"proyecto_id": proyecto, "archivo": entrada.filename,
                        "bytes": len(datos), "sha256": huella,
                        "paginas": 0, "paginas_con_texto": 0,
                        "paginas_sin_texto": 0, "paginas_texto_escaso": 0,
                        "pistas_nombre": pistas(ruta.name)}
            try:
                with pymupdf.open(stream=datos, filetype="pdf") as pdf:
                    registro["paginas"] = len(pdf)
                    for numero, pagina in enumerate(pdf, 1):
                        texto = pagina.get_text("text")
                        texto_normalizado = normalizar(texto)
                        palabras = len(re.findall(r"\w+", texto, flags=re.UNICODE))
                        imagenes = len(pagina.get_images(full=False))
                        huella_visual = huella_render_256(pagina)
                        imagenes_nuevas[huella_visual].append(
                            f"{entrada.filename}#pagina={numero}"
                        )
                        if huella_visual in visuales_anteriores:
                            visuales_en_anterior.append({
                                "pagina_nueva": f"{entrada.filename}#pagina={numero}",
                                "paginas_anteriores": visuales_anteriores[huella_visual],
                            })
                        registro["paginas_sin_texto"] += palabras == 0
                        registro["paginas_texto_escaso"] += 0 < palabras < 10
                        registro["paginas_con_texto"] += palabras >= 10
                        paginas.append({
                            "proyecto_id": proyecto,
                            "archivo": entrada.filename,
                            "pagina": numero,
                            "palabras_pdf": palabras,
                            "caracteres_pdf": len(texto.strip()),
                            "imagenes_embebidas": imagenes,
                            "rotacion_grados": pagina.rotation,
                            "ancho_pt": round(pagina.rect.width, 2),
                            "alto_pt": round(pagina.rect.height, 2),
                            "pistas_texto": pistas(texto),
                            "huella_texto": (
                                sha256(texto_normalizado.encode("utf-8")).hexdigest()
                                if len(texto_normalizado) >= 100 else None
                            ),
                            "huella_visual_256": huella_visual,
                        })
            except Exception as exc:
                registro["error"] = f"{type(exc).__name__}: {exc}"
                errores.append({"archivo": entrada.filename, "error": registro["error"]})
            documentos.append(registro)

    resumen = []
    for proyecto in sorted(proyectos):
        docs = [d for d in documentos if d["proyecto_id"] == proyecto]
        pags = [p for p in paginas if p["proyecto_id"] == proyecto]
        resumen.append({
            "proyecto_id": proyecto, "fuente_provisional": proyecto,
            "procedencia": "carpeta; pendiente_verificacion",
            "pdfs": len(docs), "paginas": len(pags),
            "texto_legible": sum(p["palabras_pdf"] >= 10 for p in pags),
            "texto_escaso": sum(0 < p["palabras_pdf"] < 10 for p in pags),
            "sin_texto_pdf": sum(p["palabras_pdf"] == 0 for p in pags),
            "paginas_con_imagenes_embebidas": sum(p["imagenes_embebidas"] > 0 for p in pags),
            "pistas": dict(sorted(Counter(
                pista for p in pags for pista in p["pistas_texto"]
            ).items())),
        })

    duplicados_nuevos = [nombres for nombres in hashes_nuevos.values()
                         if len(nombres) > 1]
    paginas_visualmente_iguales = [nombres for nombres in imagenes_nuevas.values()
                                   if len(nombres) > 1]
    resultado = {
        "origen": zip_nuevo.name,
        "comparado_con": zip_anterior.name if zip_anterior else None,
        "criterio_texto_legible": "Al menos 10 palabras PDF en una página; no mide OCR",
        "criterio_fuente": "Cada carpeta es una fuente candidata, no confirmada",
        "proyectos": resumen,
        "documentos": documentos,
        "paginas": paginas,
        "duplicados_pdf_en_zip": duplicados_nuevos,
        "paginas_iguales_al_renderizar_256": paginas_visualmente_iguales,
        "pdf_identicos_al_zip_anterior": encontrados_en_anterior,
        "paginas_iguales_al_renderizar_con_zip_anterior": (
            visuales_en_anterior if comparar_render_anterior else None
        ),
        "paginas_renderizadas_zip_anterior": paginas_anteriores,
        "errores": errores,
    }
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "EXP11_INVENTARIO.json").write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    crear_plantilla_etiquetado(resultado, salida)

    totales = Counter({clave: sum(p[clave] for p in resumen)
                       for clave in ("pdfs", "paginas", "texto_legible", "texto_escaso", "sin_texto_pdf")})
    informe = [
        "# EXP-11 — Inventario de nuevos proyectos",
        "",
        f"ZIP: `{zip_nuevo.name}`. Se encontraron **{len(resumen)} carpetas**, "
        f"**{totales['pdfs']} PDF** y **{totales['paginas']} páginas**.",
        "La carpeta conserva la procedencia provisional; no prueba por sí misma que se trate de una obra independiente.",
        "",
        "| Carpeta | PDF | Páginas con ≥10 palabras PDF | 1–9 palabras | Sin texto PDF |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    informe.extend(
        f"| {p['proyecto_id']} | {p['pdfs']} | {p['paginas']} | "
        f"{p['texto_legible']} | {p['texto_escaso']} | {p['sin_texto_pdf']} |"
        for p in resumen
    )
    informe += [
        f"| **Total** | **{totales['pdfs']}** | **{totales['paginas']}** | "
        f"**{totales['texto_legible']}** | **{totales['texto_escaso']}** | **{totales['sin_texto_pdf']}** |",
        "",
        "La columna de ≥10 palabras mide solo texto extraíble del PDF; no certifica legibilidad ni calidad semántica. "
        "'Sin texto PDF' indica que la extracción directa no obtuvo palabras. "
        "La página puede contener texto dentro de una imagen y requerir OCR.",
        "Las pistas de contenido en el inventario proceden del texto y del nombre; no son etiquetas verificadas.",
        "En `Proyecto_09`, 8 de 11 páginas no tienen texto PDF; revisar OCR sobre la página renderizada, "
        "incluso cuando no haya imágenes incrustadas en el archivo.",
        "",
        "## Duplicados y lectura",
        "",
        f"PDF idénticos dentro del ZIP: {len(duplicados_nuevos)} grupos; "
        f"PDF idénticos al ZIP anterior: {len(encontrados_en_anterior)}; "
        f"páginas iguales al renderizar a 256 píxeles: "
        f"{len(paginas_visualmente_iguales)} grupos; "
        f"archivos con errores: {len(errores)}.",
        "La ausencia de PDF idénticos no descarta copias de un mismo plano exportadas de otra manera ni obras compartidas.",
    ]
    if comparar_render_anterior:
        informe.append(
            f"Al comparar los renders de {len(paginas)} páginas nuevas con "
            f"{paginas_anteriores} anteriores a 256 px, coincidieron exactamente "
            f"{len(visuales_en_anterior)}. Cambios de escala o edición pueden "
            "impedir una coincidencia incluso entre copias del mismo plano."
        )
    for grupo in duplicados_nuevos:
        informe.append("- Copias exactas: " + "; ".join(f"`{ruta}`" for ruta in grupo))
    for grupo in paginas_visualmente_iguales:
        informe.append("- Mismo aspecto a 256 px (revisar duplicación): "
                       + "; ".join(f"`{ruta}`" for ruta in grupo))
    for hallazgo in visuales_en_anterior:
        informe.append("- Página repetida entre ZIP: "
                       + f"`{hallazgo['pagina_nueva']}` y "
                       + "; ".join(f"`{ruta}`" for ruta in hallazgo["paginas_anteriores"]))
    for error in errores:
        informe.append(f"- Revisar `{error['archivo']}`: {error['error']}")
    informe += [
        "",
        "## Evaluación propuesta",
        "",
        "1. Verificar que las once carpetas representan obras o documentos de origen distintos. "
        "Si dos carpetas comparten planos de una misma obra, asignarlas a una única fuente.",
        "2. Revisar una muestra de páginas de cada carpeta y anotar manualmente disciplina, "
        "rol y contenido con `EXP11_PLANTILLA_ETIQUETADO.json`. No equiparar pistas "
        "de texto o nombres con verdad terreno.",
        "3. Mantener los proyectos nuevos fuera del entrenamiento y del ajuste de umbrales "
        "hasta elegir el conjunto de evaluación. Si un proyecto se reserva como prueba, "
        "ninguna de sus páginas debe entrar en entrenamiento.",
        "4. Con etiquetas verificadas, aplicar el clasificador existente sin modificarlo "
        "a las fuentes reservadas y medir F1 por fuente, cobertura de OCR y errores "
        "por clase. Comparar después propuestas nuevas usando otro conjunto de obras.",
        "",
        "Este inventario no calcula F1 ni valida cómputos estructurales: esas mediciones "
        "requieren etiquetas revisadas y, para el cómputo completo, planos complementarios.",
        "",
    ]
    (salida / "EXP11_DIAGNOSTICO.md").write_text("\n".join(informe), encoding="utf-8")
    return resultado


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", type=Path, required=True, help="ZIP con una carpeta por proyecto")
    parser.add_argument("--zip-anterior", type=Path, help="ZIP anterior, para detectar PDF idénticos")
    parser.add_argument("--comparar-render-anterior", action="store_true",
                        help="Compara imágenes a 256 px de páginas de ambos ZIP")
    parser.add_argument("--salida", type=Path, default=Path(__file__).resolve().parents[2]
                        / "Data/EXP_11_nuevos_proyectos")
    args = parser.parse_args()
    resultado = auditar(args.zip, args.zip_anterior, args.salida,
                        args.comparar_render_anterior)
    print("Carpetas:", len(resultado["proyectos"]))
    print("PDF:", len(resultado["documentos"]))
    print("Páginas:", len(resultado["paginas"]))
    print("Informe:", args.salida / "EXP11_DIAGNOSTICO.md")


if __name__ == "__main__":
    main()

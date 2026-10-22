"""Comando independiente para diagnosticar uno o varios planos PDF."""

import argparse
from pathlib import Path
import sys

from computos.documentos.analisis import (
    analizar_documento_pdf,
    crear_manifiesto_documentos,
    resolver_rutas_pdf,
)
from computos.configuracion.parametros import ANALYSIS_DIR
from computos.salida.reportes import guardar_json


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Analiza planos PDF sin depender de nombres, páginas u orientaciones fijas."
        )
    )
    parser.add_argument(
        "entradas",
        nargs="+",
        help="Uno o más PDF o carpetas que contengan PDF.",
    )
    parser.add_argument(
        "--salida",
        default=str(ANALYSIS_DIR / "manifiesto_documentos.json"),
        help="Ruta del manifiesto JSON que se generará.",
    )
    return parser


def imprimir_resultado(documentos, ruta_salida: Path) -> None:
    print("=" * 68)
    print("ANÁLISIS GENERAL DE DOCUMENTOS")
    print("=" * 68)

    for documento in documentos:
        print(f"\n{documento.nombre}")
        print(f"  Páginas: {documento.cantidad_paginas}")
        print(f"  Contenido: {documento.tipo_contenido.value}")
        print(f"  Palabras: {documento.total_palabras}")
        print(f"  Objetos vectoriales: {documento.total_objetos_vectoriales}")
        print(
            "  Modo asistido: "
            + ("sí" if documento.requiere_modo_asistido else "no")
        )

        for pagina in documento.paginas:
            roles = ", ".join(rol.value for rol in pagina.roles_candidatos)
            print(
                f"    Página {pagina.numero}: {pagina.orientacion.value}, "
                f"rotación {pagina.rotacion_grados}°, "
                f"{pagina.tipo_contenido.value}, roles: {roles}"
            )

    print(f"\nManifiesto guardado en: {ruta_salida}")


def main() -> int:
    parser = construir_parser()
    argumentos = parser.parse_args()
    ruta_salida = Path(argumentos.salida).expanduser().resolve()

    try:
        rutas = resolver_rutas_pdf(argumentos.entradas)
        documentos = [analizar_documento_pdf(ruta) for ruta in rutas]
        guardar_json(crear_manifiesto_documentos(documentos), ruta_salida)
    except (FileNotFoundError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    imprimir_resultado(documentos, ruta_salida)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

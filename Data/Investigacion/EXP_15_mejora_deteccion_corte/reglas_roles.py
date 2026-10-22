"""Indicios determinísticos y trazables para roles documentales."""

from __future__ import annotations

import re


_PATRON_CORTE = re.compile(r"\bcortes?\b", re.IGNORECASE)

# Algunos PDF antiguos desplazan tres posiciones los caracteres del texto:
# "CORTE" se extrae como "&RUWH". Se conserva como alias auditable y no como
# sustitución general del texto.
_PATRON_CORTE_CODIFICADO = re.compile(r"&RUWH", re.IGNORECASE)


def _contexto(texto: str, coincidencia: re.Match, radio: int = 60) -> str:
    inicio = max(0, coincidencia.start() - radio)
    final = min(len(texto), coincidencia.end() + radio)
    return " ".join(texto[inicio:final].split())


def detectar_indicio_corte(
    texto: str | None,
    nombre_archivo: str | None = None,
) -> dict:
    """Busca evidencia explícita del rol ``corte``.

    La función devuelve un indicio con su origen y evidencia. No convierte por
    sí sola la página en Ground Truth ni reemplaza la revisión profesional.
    """

    texto = texto or ""
    nombre_archivo = nombre_archivo or ""

    coincidencia = _PATRON_CORTE.search(nombre_archivo)
    if coincidencia:
        return {
            "detectado": True,
            "rol": "corte",
            "fuente_evidencia": "nombre_archivo",
            "patron": "corte_literal",
            "evidencia": coincidencia.group(0),
            "contexto": _contexto(nombre_archivo, coincidencia),
            "confianza_regla": "alta",
        }

    coincidencia = _PATRON_CORTE.search(texto)
    if coincidencia:
        return {
            "detectado": True,
            "rol": "corte",
            "fuente_evidencia": "texto_pagina",
            "patron": "corte_literal",
            "evidencia": coincidencia.group(0),
            "contexto": _contexto(texto, coincidencia),
            "confianza_regla": "media",
        }

    coincidencia = _PATRON_CORTE_CODIFICADO.search(texto)
    if coincidencia:
        return {
            "detectado": True,
            "rol": "corte",
            "fuente_evidencia": "texto_pagina",
            "patron": "alias_pdf_codificado",
            "evidencia": coincidencia.group(0),
            "contexto": _contexto(texto, coincidencia),
            "confianza_regla": "media",
        }

    return {
        "detectado": False,
        "rol": "corte",
        "fuente_evidencia": None,
        "patron": None,
        "evidencia": None,
        "contexto": None,
        "confianza_regla": None,
    }

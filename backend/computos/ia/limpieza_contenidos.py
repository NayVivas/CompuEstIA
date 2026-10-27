r"""Limpieza de texto para la variante ``palabras`` del clasificador de contenidos.

La limpieza elimina la huella administrativa de la lámina (proyecto, fecha,
escala, número de lámina, etc.) y conserva únicamente palabras semánticas.
Se aplica antes del TF-IDF de palabras, tanto en entrenamiento como en
validación y test, para que la transformación sea consistente.

Importante:
    Los artefactos EXP19 actuales fueron entrenados con texto crudo y TF-IDF
    híbrido. Esta limpieza no debe aplicarse en inferencia con esos artefactos:
    primero hay que reentrenar y guardar el vectorizador de la variante
    ``palabras``.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = ["ROTULO_BLOQUE", "limpiar_texto"]


# Líneas que pertenecen al bloque administrativo de la lámina. Se comparan
# solo al inicio de la línea para no borrar palabras semánticas que aparezcan
# en medio de una descripción técnica.
ROTULO_BLOQUE = re.compile(
    r"^\s*(?:PROYECTO|PROPIETARIO|CLIENTE|FECHA|ESCALA|ESC\.?|LAMINA|LÁMINA|"
    r"PLANO|PLANOS|REVISION|REVISIÓN|UBICACION|UBICACIÓN|DIRECCION|DIRECCIÓN|"
    r"TELEFONO|TELÉFONO|EMAIL|E-MAIL|NORTE|SIMBOLOGIA|SIMBOLOGÍA|"
    r"CONSULTOR|CONTRATISTA|EXPEDIENTE|CODIGO|CÓDIGO)\b",
    re.IGNORECASE,
)

TOKEN = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")

STOPWORDS = frozenset(
    {
        "de", "del", "la", "las", "el", "los", "y", "o", "en", "con", "sin",
        "por", "para", "un", "una", "unos", "unas", "al", "a", "que", "se",
        "su", "sus", "es", "son", "como", "mas", "más", "sobre", "entre",
        "hasta", "desde", "este", "esta", "estos", "estas", "otro", "otra",
    }
)


def _sin_tildes(texto: str) -> str:
    return "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(caracter)
    )


def limpiar_texto(texto: str) -> str:
    """Conserva palabras semánticas; elimina números, cotas y rótulos.

    No intenta entender el plano: solo evita que el clasificador memorice
    ``30x30``, ``C-1``, ``ESC 100`` o el nombre del proyecto. La asociación
    espacial de cotas se hace en otra etapa, no en el clasificador de
    contenidos.

    La función es determinista y se usa igual en train, validation y test.
    """

    lineas: list[str] = []
    for linea in str(texto or "").splitlines():
        limpia = linea.strip()
        if not limpia or ROTULO_BLOQUE.match(limpia):
            continue
        tokens = [
            token.lower()
            for token in TOKEN.findall(_sin_tildes(limpia))
            if len(token) >= 3 and token.lower() not in STOPWORDS
        ]
        if tokens:
            lineas.append(" ".join(tokens))
    return "\n".join(lineas)

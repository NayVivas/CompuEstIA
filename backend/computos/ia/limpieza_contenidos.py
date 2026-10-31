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


# Prefijo habitual de listas numeradas o viñetas. No forma parte de la
# palabra semántica, pero puede anteceder a un rótulo administrativo.
PREFIJO = r"(?:\d+[.)]\s*|[•·\-–]\s*)?"

# Líneas que pertenecen al bloque administrativo de la lámina. Se comparan
# solo al inicio de la línea para no borrar palabras semánticas que aparezcan
# en medio de una descripción técnica. Las raíces cubren las abreviaturas
# usuales de los cajetines (PROPIET., FECH., LAM., ARQ., ING., etc.).
ROTULO_BLOQUE = re.compile(
    rf"^\s*{PREFIJO}(?:"
    r"(?P<plano>PLANOS?)"
    r"|PROY(?:ECT[OÓ])[O0]?S?"
    r"|PROPIET(?:ARI[OÓ]S?)?"
    r"|CLIENT(?:E|ES)?"
    r"|FECH(?:A|AS)?"
    r"|ESC(?:ALA|ALAS)?"
    r"|L[AÁ]M(?:IN[AÁ]S?)?"
    r"|REVISI[OÓ]N"
    r"|UBIC(?:ACI[OÓ]N)?"
    r"|DIR(?:ECCI[OÓ]N)?"
    r"|TEL(?:[EÉ]FON[OÓ]S?)?"
    r"|E-?MAIL(?:S)?"
    r"|NORTE(?:S)?"
    r"|SIMB(?:OLOG[IÍ]A|OLOG[IÍ]AS|OL[OÓ]S?)?"
    r"|CONSULT(?:OR|ORA|ORES|ORAS)?"
    r"|CONTRAT(?:ISTA|ISTAS)?"
    r"|EXP(?:EDIENTE|EDIENTES)?"
    r"|C[OÓ]D(?:IG[OÓ]S?)?"
    r"|DIBUJ(?:[OÓ]|ANTES?)?"
    r"|APROB(?:[OÓ]|AD[OÓ]S?|AD[AÁ]S?|ACI[OÓ]N|ACI[OÓ]NES)?"
    r"|ARQ(?:UITECT[OÓ]S?)?"
    r"|ING(?:ENIER[OÓ]S)?"
    r")\b",
    re.IGNORECASE,
)

# Un PLANO puede contener la etiqueta y, a continuación, el tema del dibujo.
# No se descarta la línea completa: se quita el rótulo y se conserva la cola
# semántica cuando aporta información (``PLANO DE FUNDACIONES`` -> fundaciones).
PLANO_ROTULO = re.compile(
    rf"^\s*{PREFIJO}PLANOS?\b"
    r"[\s:.\-–/]*"
    r"(?:DE(?:L|\s+LA|\s+LOS|\s+LAS)?\s+)?"
    r"(?:N(?:RO|R|UM(?:ERO)?|°|º)\.?[\s:.\-–/]*)?",
    re.IGNORECASE,
)
PLANO_CON_DE = re.compile(
    rf"^\s*{PREFIJO}PLANOS?\b[\s:.\-–/]*(?:DE(?:L|\s+LA|\s+LOS|\s+LAS)?)\s+",
    re.IGNORECASE,
)
PLANO_FUNDACION = re.compile(
    r"\b(?:FUNDACI[OÓ]N|FUNDACIONES|CIMENTACI[OÓ]N|CIMIENTO)\w*",
    re.IGNORECASE,
)

# Metadatos de escala que a veces comparten línea con una descripción
# técnica. Se eliminan solo esos fragmentos, no la línea completa.
_ESCALA = r"\b(?:ESCALA|ESC)\b\.?"
_NUMERO_ESCALA = r"\d+(?:[.,]\d+)?\s*[:/]\s*\d+(?:[.,]\d+)?"
METADATOS_INLINE = re.compile(
    rf"(?:"
    rf"\bSIN\s+{_ESCALA}"
    rf"|{_ESCALA}\s*[:.]?\s*(?:GRAFICA|GRÁFICA)(?:\s*[:.]?\s*{_NUMERO_ESCALA})?"
    rf"|{_ESCALA}\s*[:.]?\s*{_NUMERO_ESCALA}"
    rf"|{_ESCALA}\s*[:.]?\s*[-–—]{{2,}}\s*INDICADA"
    rf"|{_ESCALA}\s*[:.]?\s*\d+\s+(?:EN|A)\s+\d+"
    rf")",
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
        limpia = unicodedata.normalize("NFC", linea.strip())
        if not limpia:
            continue

        rotulo = ROTULO_BLOQUE.match(limpia)
        if rotulo:
            if rotulo.group("plano"):
                resto = PLANO_ROTULO.sub("", limpia, count=1)
                conservar = bool(
                    PLANO_CON_DE.match(limpia) or PLANO_FUNDACION.search(resto)
                )
                if not conservar:
                    continue
                limpia = resto.strip()
                if not limpia or ROTULO_BLOQUE.match(limpia):
                    continue
            else:
                continue

        limpia = METADATOS_INLINE.sub(" ", limpia)
        tokens = [
            token.lower()
            for token in TOKEN.findall(_sin_tildes(limpia))
            if len(token) >= 3 and token.lower() not in STOPWORDS
        ]
        if tokens:
            lineas.append(" ".join(tokens))
    return "\n".join(lineas)

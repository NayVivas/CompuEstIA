"""Validación determinística de la extracción generativa estructural."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from computos.ia.proveedor import (
    ProveedorEstructural,
    ProveedorOpenAIEstructural,
)


LIMITE_PDF_BYTES = 25 * 1024 * 1024
CONFIANZA_REVISION = 0.80


def _firma_dimensiones(elemento) -> tuple:
    dimensiones = elemento.dimensiones
    return (
        dimensiones.ancho_m,
        dimensiones.largo_m,
        dimensiones.altura_m,
        dimensiones.diametro_m,
    )


def _validar_resultado(respuesta) -> tuple[list[dict], dict, list[str]]:
    analisis = respuesta.analisis
    advertencias = list(analisis.advertencias)
    elementos = []
    firmas_por_referencia = defaultdict(set)

    for elemento in analisis.elementos:
        referencia = (
            elemento.referencia.strip().upper()
            if elemento.referencia
            else None
        )
        motivos_revision = []

        if elemento.confianza < CONFIANZA_REVISION:
            motivos_revision.append("confianza_inferior_a_0_80")
        if not elemento.evidencias:
            motivos_revision.append("sin_evidencia")
        if referencia is None:
            motivos_revision.append("sin_referencia")
        if not any(_firma_dimensiones(elemento)):
            motivos_revision.append("sin_dimensiones")

        requiere_revision = bool(
            elemento.requiere_revision
            or motivos_revision
        )
        datos = elemento.model_dump()
        datos["referencia"] = referencia
        datos["requiere_revision"] = requiere_revision
        datos["motivos_revision_deterministica"] = motivos_revision
        elementos.append(datos)

        if referencia:
            firmas_por_referencia[
                (elemento.tipo, referencia)
            ].add(_firma_dimensiones(elemento))

    contradicciones = {
        f"{tipo}:{referencia}": len(firmas)
        for (tipo, referencia), firmas in firmas_por_referencia.items()
        if len(firmas) > 1
    }
    if contradicciones:
        advertencias.append(
            "Se detectaron referencias repetidas con dimensiones diferentes."
        )

    if not analisis.es_plano_estructural and elementos:
        advertencias.append(
            "El modelo declaró el PDF como no estructural pero devolvió elementos."
        )
        for elemento in elementos:
            elemento["requiere_revision"] = True
            elemento["motivos_revision_deterministica"].append(
                "documento_declarado_no_estructural"
            )

    pendientes = sum(
        elemento["requiere_revision"]
        for elemento in elementos
    )
    sin_evidencia = sum(
        not elemento["evidencias"]
        for elemento in elementos
    )
    confianza_promedio = (
        sum(elemento["confianza"] for elemento in elementos)
        / len(elementos)
        if elementos
        else 0.0
    )

    validacion = {
        "cantidad_elementos": len(elementos),
        "elementos_pendientes_revision": pendientes,
        "elementos_sin_evidencia": sin_evidencia,
        "confianza_promedio": round(confianza_promedio, 4),
        "referencias_con_dimensiones_contradictorias": contradicciones,
        "calculos_habilitados": bool(
            analisis.es_plano_estructural
            and elementos
            and pendientes == 0
            and not contradicciones
        ),
    }
    return elementos, validacion, list(dict.fromkeys(advertencias))


def analizar_pdf_estructural(
    ruta_pdf: Path,
    *,
    proveedor: ProveedorEstructural | None = None,
) -> dict:
    """Interpreta un PDF y conserva la revisión profesional obligatoria."""

    ruta_pdf = Path(ruta_pdf)
    if not ruta_pdf.is_file():
        raise FileNotFoundError(ruta_pdf)
    if ruta_pdf.suffix.casefold() != ".pdf":
        raise ValueError("El archivo debe ser PDF.")
    if ruta_pdf.stat().st_size > LIMITE_PDF_BYTES:
        raise ValueError("El PDF supera el límite de 25 MB.")
    if ruta_pdf.read_bytes()[:5] != b"%PDF-":
        raise ValueError("El archivo no contiene una firma PDF válida.")

    proveedor = proveedor or ProveedorOpenAIEstructural()
    respuesta = proveedor.analizar_pdf(ruta_pdf)
    elementos, validacion, advertencias = _validar_resultado(respuesta)

    return {
        "modo": "asistido_ia_generativa",
        "alcance": "planos_estructurales",
        "archivo": ruta_pdf.name,
        "es_plano_estructural": respuesta.analisis.es_plano_estructural,
        "tipo_documento": respuesta.analisis.tipo_documento,
        "resumen": respuesta.analisis.resumen,
        "elementos_extraidos": elementos,
        "validacion_ia": validacion,
        "advertencias": advertencias,
        "calculos_realizados_por_ia": False,
        "requiere_revision_profesional": True,
        "proveedor": {
            "nombre": respuesta.proveedor,
            "modelo": respuesta.modelo,
            "respuesta_id": respuesta.respuesta_id,
            "tokens_entrada": respuesta.tokens_entrada,
            "tokens_salida": respuesta.tokens_salida,
        },
    }

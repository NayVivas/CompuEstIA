"""Integra las fichas documentales del lector visual 1.5 con los motores V12.2.

Opera sobre las páginas que el enrutador ya seleccionó como detalles. Conserva
la clasificación y el cómputo actuales; ninguna ficha habilita cantidades por
sí sola. El OCR regional se reserva para secciones incompletas.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
import re

import pymupdf

from computos.documentos import lector_visual_15 as lector

_CAMPOS_PROPUESTA = {
    "ancho_superior_m": "ancho_superior_m_propuesto",
    "ancho_base_m": "ancho_base_m_propuesto",
    "altura_m": "altura_m_propuesta",
}


def _referencia(valor: str | None) -> str | None:
    match = re.fullmatch(r"C\s*[-_.]?\s*(\d{1,3})", str(valor or "").strip(), re.I)
    return f"C-{int(match[1])}" if match else None


def _seccion(ficha: dict) -> dict | None:
    if ficha.get("familia_propuesta") not in {"cimiento_corrido", "cimentacion_sin_subtipo"}:
        return None
    factor = {"m": 1, "cm": .01, "mm": .001}.get(ficha.get("unidad_propuesta"))
    if factor is None:
        return None
    campos = ficha.get("campos_propuestos") or {}
    valores = []
    for clave in lector.MEDIDAS_FICHA:
        campo = campos.get(clave) or {}
        valor = campo.get("valor")
        if not isinstance(valor, (int, float)) or not 0 < valor * factor <= 10:
            return None
        if not campo.get("lectura_id"):
            return None
        valores.append(round(valor * factor, 4))
    superior, base, altura = valores
    if base < superior:
        return None
    return {
        "ancho_superior_m": superior,
        "ancho_base_m": base,
        "altura_m": altura,
    }


def _paginas_fichas(ruta: Path, fuentes: list[dict], *, ocr: bool = False) -> tuple[list[dict], list[str]]:
    paginas = []
    avisos = []
    configuracion = lector.diagnostico_ocr() if ocr else {"listo": False, "mensaje": "OCR regional no solicitado"}
    with pymupdf.open(ruta) as documento:
        for indice, pagina in enumerate(documento):
            if indice >= len(fuentes):
                avisos.append("Hay una página de detalles sin identidad de fuente; se omite.")
                continue
            fuente = fuentes[indice]
            escala = min(3.0, 2100 / max(pagina.rect.width, pagina.rect.height, 1))
            ancho = max(1, round(pagina.rect.width * escala))
            alto = max(1, round(pagina.rect.height * escala))
            if ocr and configuracion.get("listo"):
                # La lectura OCR V12 se utiliza primero; esta pasada localizada
                # solo se llama si el motor dejó una sección sin completar.
                imagen = pagina.get_pixmap(matrix=pymupdf.Matrix(escala, escala), alpha=False)
                texto = lector.leer_fuente(
                    pagina, imagen, configuracion=configuracion,
                    dpi=180, timeout=15, max_zonas=8,
                )
            else:
                lineas = [
                    {**linea, "origen": "texto_nativo"}
                    for linea in lector.extraer_lineas(pagina, ancho, alto)
                ]
                regiones, pendientes = lector.planificar_regiones_ocr(pagina, ancho, alto, 16)
                for region in regiones:
                    region["caja_visual_px"] = region["caja"]
                texto = {
                    "lineas": lineas,
                    "lineas_contexto_ocr": [],
                    "lecturas_numericas": lector.lecturas_numericas(lineas),
                    "ocr": {"regiones": regiones, "regiones_pendientes": pendientes},
                }
            if ocr and not configuracion.get("listo"):
                avisos.append(configuracion.get("mensaje", "OCR regional no disponible."))
            paginas.append({
                "documento": indice + 1,
                "archivo": fuente.get("archivo"),
                "pagina": fuente.get("pagina"),
                "sha256": fuente.get("sha256"),
                "imagen": None,
                "ancho_px": ancho,
                "alto_px": alto,
                "fuente_textual": texto,
            })
    return paginas, avisos


def integrar_fichas_cimientos(
    propuesta: dict,
    ruta_detalles: str | Path,
    fuentes_detalles: list[dict],
) -> dict:
    """Añade evidencia y completa solo secciones inequívocas, siempre revisables."""
    ruta = Path(ruta_detalles)
    faltantes = any(
        any(item.get(clave) is None for clave in _CAMPOS_PROPUESTA.values())
        for item in propuesta.get("elementos", [])
    )
    paginas, avisos = _paginas_fichas(ruta, fuentes_detalles)
    fichas, pendientes = lector.construir_fichas({"paginas": paginas})
    usado_ocr = False
    if faltantes and os.getenv("COMPUTOESTIA_FICHAS_OCR", "1").strip().casefold() not in {"0", "false", "no"}:
        # Los PDF ya sometidos a OCR por el enrutador pueden traer las cotas en
        # sus páginas buscables; solo si siguen faltando se usa el OCR regional.
        refs = {_referencia(item.get("referencia_propuesta")) for item in propuesta["elementos"]}
        requiere_regional = any(
            _referencia(f.get("referencia_fuente")) in refs and _seccion(f) is None
            for f in fichas
        )
        if requiere_regional:
            paginas, nuevos_avisos = _paginas_fichas(ruta, fuentes_detalles, ocr=True)
            avisos.extend(nuevos_avisos)
            fichas, pendientes = lector.construir_fichas({"paginas": paginas})
            usado_ocr = True

    agrupadas: dict[str, list[dict]] = {}
    resumen = []
    fuentes_permitidas = {
        (fuente.get("sha256"), fuente.get("pagina")) for fuente in fuentes_detalles
    }
    for ficha in fichas:
        referencia = _referencia(ficha.get("referencia_fuente"))
        origen_valido = (
            ficha.get("sha256_pdf"), ficha.get("pagina")
        ) in fuentes_permitidas
        seccion = _seccion(ficha) if origen_valido else None
        resumen.append({
            "referencia": ficha.get("referencia_fuente"),
            "familia": ficha.get("familia_propuesta"),
            "archivo": ficha.get("archivo"),
            "pagina": ficha.get("pagina"),
            "sha256_pdf": ficha.get("sha256_pdf"),
            "unidad_propuesta": ficha.get("unidad_propuesta"),
            "caja_visual_px": ficha.get("caja_documental_px"),
            "ancho_px": ficha.get("ancho_px"),
            "alto_px": ficha.get("alto_px"),
            "seccion_m_propuesta": seccion,
            "origen_pdf_coincide": origen_valido,
            "requiere_revision": True,
        })
        if referencia and seccion:
            agrupadas.setdefault(referencia, []).append(resumen[-1])

    for item in propuesta.get("elementos", []):
        ref = _referencia(item.get("referencia_propuesta"))
        candidatas = agrupadas.get(ref, [])
        if len(candidatas) != 1:
            if len(candidatas) > 1:
                item["conflicto_fichas_lector"] = "Hay varias fichas dimensionales para este tipo. Revisá el detalle."
            continue
        ficha = candidatas[0]
        dimensiones = ficha["seccion_m_propuesta"]
        conflictos = []
        for clave, valor in dimensiones.items():
            actual = item.get(_CAMPOS_PROPUESTA[clave])
            if actual is not None and abs(float(actual) - valor) > .005:
                conflictos.append(clave)
        item["ficha_lector_15"] = ficha
        if conflictos:
            item["conflicto_fichas_lector"] = (
                "La ficha y la extracción anterior difieren en " + ", ".join(conflictos)
            )
            continue
        for clave, valor in dimensiones.items():
            if item.get(_CAMPOS_PROPUESTA[clave]) is None:
                item[_CAMPOS_PROPUESTA[clave]] = valor
        item["evidencia_seccion"] = {
            **(item.get("evidencia_seccion") or {}),
            "lector_15": "propuesta_documental_revisable",
            "completa": all(item.get(campo) is not None for campo in _CAMPOS_PROPUESTA.values()),
        }

    propuesta["fichas_lector_15"] = {
        "version": lector.VERSION,
        "fichas": resumen,
        "avisos": avisos,
        "pendientes": len(pendientes),
        "ocr_regional_utilizado": usado_ocr,
        "alcance": "Fichas documentales: no prueban longitud, material ni cantidad construida.",
    }
    paginas_con_fichas = {
        (ficha["sha256_pdf"], ficha["pagina"]) for ficha in resumen
        if ficha.get("sha256_pdf") and ficha.get("pagina")
    }
    paginas_con_fichas.update(
        (item["fuente"].get("sha256"), item["fuente"].get("pagina"))
        for item in propuesta.get("tipos_solo_detalle", [])
        if item.get("fuente", {}).get("sha256") and item["fuente"].get("pagina")
    )
    vistas = []
    if paginas_con_fichas:
        with pymupdf.open(ruta) as documento:
            for indice, (pagina, fuente) in enumerate(zip(documento, fuentes_detalles)):
                if (fuente.get("sha256"), fuente.get("pagina")) not in paginas_con_fichas:
                    continue
                escala = min(1.5, 1200 / max(pagina.rect.width, pagina.rect.height, 1))
                pix = pagina.get_pixmap(matrix=pymupdf.Matrix(escala, escala),
                    colorspace=pymupdf.csRGB, alpha=False)
                vistas.append({
                    "pagina_motor": indice + 1,
                    "sha256_pdf": fuente["sha256"],
                    "pagina": fuente["pagina"],
                    "archivo": fuente.get("archivo"),
                    "imagen": "data:image/jpeg;base64," + base64.b64encode(
                        pix.tobytes("jpeg", jpg_quality=58)
                    ).decode("ascii"),
                })
    propuesta["paginas_detalle_lector_15"] = vistas
    return propuesta

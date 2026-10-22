"""Clasificación por página y selección conservadora del motor de cómputo.

La carga puede contener uno o muchos PDF, incluidas láminas multipágina. Los
nombres de archivo no participan en las decisiones. La clasificación y el OCR
son generales; el cómputo se habilita únicamente para tipologías y fuentes que
el motor realmente sabe interpretar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
import logging
from pathlib import Path
import re
import unicodedata

import pymupdf

from computos.documentos.ocr import OCRNoDisponible, reconocer_pagina
from computos.ia.clasificacion_evidencias import clasificar_evidencias
from computos.ia.clasificador_exp19 import ClasificadorExp19
from computos.ia.clasificador_multimodal import (
    VERSION_EXP22,
    extraer_caracteristicas_multimodales,
    fusionar_clasificacion,
    fusionar_textos,
    motivos_ocr_adaptativo,
    proponer_roles_motor,
)
from computos.ia.revision_documental import aplicar_decision, validar_revisiones


ROLES_MOTOR = ("planta", "detalles", "columnas")
ROLES_MOTOR_OPCIONALES = ("porticos",)
ROLES_MOTOR_TODOS = (*ROLES_MOTOR, *ROLES_MOTOR_OPCIONALES)
TIPOLOGIAS_NO_IMPLEMENTADAS = {
    "losa_cimentacion",
    "pilotes_encepados",
}
_logger = logging.getLogger(__name__)


def _normalizar(texto: str) -> str:
    texto = "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", str(texto).upper())
        if not unicodedata.combining(caracter)
    )
    return re.sub(r"\s+", " ", texto).strip()


def _normalizar_lineas(texto: str) -> str:
    texto = "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", str(texto).upper())
        if not unicodedata.combining(caracter)
    )
    return "\n".join(
        re.sub(r"[ \t]+", " ", linea).strip()
        for linea in texto.replace("\r", "\n").split("\n")
        if linea.strip()
    )


def _compactar_rotulos(texto: str, *, conservar_lineas: bool = False) -> str:
    normal = _normalizar_lineas(texto) if conservar_lineas else _normalizar(texto)
    for palabra in (
        "CUADRO",
        "FUNDACION",
        "FUNDACIONES",
        "CIMENTACION",
        "CIMENTACIONES",
        "CIMIENTO",
        "CIMIENTOS",
        "ZAPATA",
        "ZAPATAS",
        "COLUMNAS",
        "CASTILLOS",
        "DETALLE",
        "DETALLES",
        "PLANTA",
        "PLANO",
        "TIPOS",
        "DE",
    ):
        normal = re.sub(r"\b" + r"\s*".join(palabra) + r"\b", palabra, normal)
    return normal


def _reglas(texto: str) -> dict:
    return clasificar_evidencias(texto)


def _analizar_fuente_tecnica(texto: str) -> dict:
    """Describe función, formato geométrico y tipología sin mirar el nombre."""

    lineas = _compactar_rotulos(texto, conservar_lineas=True)
    normal = re.sub(r"\s+", " ", lineas).strip()
    familia_fundacion = (
        r"(?:FUNDACION(?:ES)?|CIMENTACION(?:ES)?|CIMIENTOS?|ZAPATAS?|BASES?)"
    )
    titulo_planta = bool(
        re.search(
            rf"^\s*(?:PLANTA|IMPLANTACION|PLANO)\s+(?:INDICE\s+)?(?:DE\s+)?{familia_fundacion}\b",
            lineas,
            re.M,
        )
    )
    titulo_cuadro = bool(
        re.search(
            rf"^\s*(?:CUADRO|PLANILLA|TABLA)\s+(?:DE\s+)?{familia_fundacion}\b",
            lineas,
            re.M,
        )
    )
    detalle_directo = bool(
        re.search(
            rf"^\s*(?:DETALLES?|ARMADO)\s+(?:TIPIC[OA]S?\s+)?(?:DE\s+)?{familia_fundacion}\b|"
            rf"^\s*TIPOS?\s+(?:DE\s+)?{familia_fundacion}\b|"
            rf"^\s*(?:PLANTA|PLANO)\b[^\n]{{0,80}}\bY\s+DETALLES?\s+(?:DE\s+)?{familia_fundacion}\b",
            lineas,
            re.M,
        )
    )
    conexion_viga_zapata = bool(
        re.search(r"^\s*DETALLES?\s*:?\s*CONEXION\s+VIGA\s*-?\s*ZAPATA\b", lineas, re.M)
    )
    titulo_detalle = bool(
        detalle_directo and not conexion_viga_zapata
    )
    titulo_columnas = bool(
        re.search(
            r"^\s*(?:(?:ESTRUCTURAS?\s*[-:]?\s*)?"
            r"(?:CUADRO|PLANILLA|TABLA|DETALLES?|PLANO|TIPOS?|ARMADO|DESPIECE|SECCIONES?)\s+"
            r"(?:DE\s+)?(?:COLUMNAS?|PILARES?|CASTILLOS?)\b|"
            r"ESTRUCTURAS?\s*-\s*(?:PLACAS?\s+Y\s+)?COLUMNAS?\b|"
            r"PLACAS?\s+Y\s+COLUMNAS?\s*:)",
            lineas,
            re.M,
        )
    )
    titulo_porticos = bool(
        re.search(r"\bPORTICOS?\b", normal)
        and re.search(r"\bC\s*[-_]?\s*\d{1,4}\b", normal)
    )

    roles = []
    if titulo_planta:
        roles.append("planta")
    if titulo_cuadro or titulo_detalle:
        roles.append("detalles")
    # Una misma lámina puede contener un cuadro de zapatas y, más abajo, un
    # cuadro de columnas. ``titulo_cuadro`` no debe anular ese segundo rol.
    if titulo_columnas:
        roles.append("columnas")
    if titulo_porticos:
        roles.append("porticos")

    tipologias = []
    tipos_cimientos = bool(
        re.search(r"^\s*TIPOS?\s+DE\s+CIMIENTOS?\b", lineas, re.M)
    )
    sistema_castillos = bool(
        re.search(r"^\s*TIPOS?\s+DE\s+CASTILLOS?\b", lineas, re.M)
    )
    referencias_cimiento_c = len(
        re.findall(r"^\s*C\s*[-_.]\s*\d{1,3}\s*$", lineas, re.M)
    )
    if re.search(
        r"\b(?:CIMIENTOS?|ZAPATAS?|FUNDACIONES?)\s+CORRID[AO]S?\b|"
        r"\bCIMIENTO\s+CONTINUO\b",
        normal,
    ) or (tipos_cimientos and sistema_castillos and referencias_cimiento_c >= 2):
        tipologias.append("cimientos_corridos")
    if re.search(
        r"^\s*(?:(?:PLANTA|DETALLE|ARMADO|SECCION)\s+(?:DE\s+)?)?"
        r"(?:LOSA|PLATEA)\s+(?:DE\s+)?CIMENTACION\b",
        lineas,
        re.M,
    ):
        tipologias.append("losa_cimentacion")
    if re.search(r"\b(?:PILOTES?|ENCEPADOS?|CABEZAL(?:ES)?\s+DE\s+PILOTES?)\b", normal):
        tipologias.append("pilotes_encepados")
    if (
        re.search(r"\b(?:ZAPATAS?|BASES?)\s+(?:AISLADAS?|CENTRADAS?|EXCENTRICAS?|COMBINADAS?)\b", normal)
        or re.search(r"\b(?:Z|ZA|ZAP|ZPT)\s*[-_.]?\s*\d{1,4}\b", normal)
        or (
            (titulo_cuadro or titulo_detalle)
            and re.search(r"\bZAPATAS?\b", normal)
            and "cimientos_corridos" not in tipologias
            and not any(tipo in TIPOLOGIAS_NO_IMPLEMENTADAS for tipo in tipologias)
        )
        or (
            (titulo_cuadro or titulo_detalle)
            and re.search(r"\bF\s*[-_.]?\s*\d{1,4}\b", normal)
            and (
                re.search(r"\bX\b.{0,80}\bY\b.{0,80}\b(?:H|ESPESOR|PERALTE)\b", normal)
                or re.search(r"\d+(?:[.,]\d+)?\s*[X×]\s*\d+(?:[.,]\d+)?", normal)
            )
            and not any(tipo in TIPOLOGIAS_NO_IMPLEMENTADAS for tipo in tipologias)
        )
    ):
        tipologias.append("zapatas_aisladas")

    modo_detalles = None
    if "detalles" in roles:
        if titulo_cuadro:
            modo_detalles = "tabular"
        elif titulo_detalle:
            modo_detalles = "geometria_distribuida"

    motivos = []
    if titulo_planta:
        motivos.append("Título explícito de planta de fundaciones o cimentación.")
    if titulo_cuadro:
        motivos.append("Título explícito de cuadro o planilla de fundaciones.")
    elif titulo_detalle:
        motivos.append("Dimensiones distribuidas en detalles, sin cuadro tabular único.")
    if tipologias:
        motivos.append("Tipología detectada en el contenido: " + ", ".join(tipologias) + ".")

    return {
        "roles": roles,
        "modo_detalles": modo_detalles,
        "tipologias": list(dict.fromkeys(tipologias)),
        "motivos": motivos,
        "exclusiones_roles": ["detalles"] if conexion_viga_zapata else [],
    }


def _roles_motor(texto: str) -> list[str]:
    return _analizar_fuente_tecnica(texto)["roles"]


@dataclass
class Enrutamiento:
    rutas: dict[str, Path]
    documentos: list[dict] = field(default_factory=list)
    fuentes_por_rol: dict[str, dict] = field(default_factory=dict)
    motivos_motor: list[str] = field(default_factory=list)
    diagnostico_modelo: dict = field(
        default_factory=lambda: {"estado": "no_ejecutado"}
    )
    rutas_ocr: dict[tuple[str, int], Path] = field(default_factory=dict)

    @property
    def tipologias(self) -> list[str]:
        return list(
            dict.fromkeys(
                tipologia
                for grupo in self.fuentes_por_rol.values()
                for tipologia in grupo.get("tipologias", [])
            )
        )

    @property
    def modo_detalles(self) -> str | None:
        return self.fuentes_por_rol.get("detalles", {}).get("modo_geometria")

    @property
    def tipologia_no_implementada(self) -> str | None:
        return next(
            (
                tipologia
                for tipologia in self.tipologias
                if tipologia in TIPOLOGIAS_NO_IMPLEMENTADAS
            ),
            None,
        )

    @property
    def listo(self) -> bool:
        return (
            set(ROLES_MOTOR).issubset(self.fuentes_por_rol)
            and self.modo_detalles == "tabular"
            and self.tipologia_no_implementada is None
        )

    @property
    def requiere_revision_geometrica(self) -> bool:
        return self.tipo_revision_geometrica is not None

    @property
    def tipo_revision_geometrica(self) -> str | None:
        fuentes_disponibles = (
            {"planta", "detalles"}.issubset(self.fuentes_por_rol)
            and self.modo_detalles == "geometria_distribuida"
            and self.tipologia_no_implementada is None
        )
        if not fuentes_disponibles:
            return None
        if "cimientos_corridos" in self.tipologias:
            return "cimientos_corridos"
        if "zapatas_aisladas" in self.tipologias:
            return "zapatas_aisladas"
        return None

    @property
    def asignaciones(self) -> dict[str, str]:
        return {
            rol: fuente["documento_id"]
            for rol, fuente in self.fuentes_por_rol.items()
            if fuente.get("documento_id")
        }

    @property
    def asignaciones_sugeridas(self) -> dict[str, str]:
        return self.asignaciones

    def _ruta_fuente(self, fuente: dict) -> tuple[Path, int]:
        ruta_ocr = self.rutas_ocr.get((fuente["documento_id"], fuente["pagina"]))
        if ruta_ocr is not None:
            return ruta_ocr, 0
        return self.rutas[fuente["documento_id"]], fuente["pagina"] - 1

    def _materializar_roles(self, roles) -> dict[str, Path]:
        salidas = {}
        for rol in roles:
            grupo = self.fuentes_por_rol.get(rol)
            if not grupo:
                continue
            fuentes = grupo.get("fuentes") or [grupo]
            if len(fuentes) == 1:
                origen, indice = self._ruta_fuente(fuentes[0])
                with pymupdf.open(origen) as pdf:
                    if len(pdf) == 1 and indice == 0:
                        salidas[rol] = origen
                        continue

            primer_origen, _ = self._ruta_fuente(fuentes[0])
            identidad = "-".join(
                f"{fuente['sha256']}-{fuente['pagina']}" for fuente in fuentes
            )
            destino = (
                primer_origen.parent
                / "paginas_motor"
                / f"{rol}-{sha256(identidad.encode()).hexdigest()[:16]}.pdf"
            )
            destino.parent.mkdir(parents=True, exist_ok=True)
            with pymupdf.open() as combinado:
                for fuente in fuentes:
                    origen, indice = self._ruta_fuente(fuente)
                    with pymupdf.open(origen) as pdf:
                        combinado.insert_pdf(pdf, from_page=indice, to_page=indice)
                combinado.save(destino, no_new_id=True)
            salidas[rol] = destino
        return salidas

    def rutas_por_rol(self) -> dict[str, Path]:
        if not self.listo:
            raise ValueError(
                "La clasificación está disponible, pero el motor tabular no tiene fuentes compatibles."
            )
        return self._materializar_roles(self.fuentes_por_rol)

    def rutas_para_auditoria(self) -> dict[str, Path]:
        """Copias de lectura OCR con las mismas páginas y vectores originales."""
        rutas = dict(self.rutas)
        for identificador, origen in self.rutas.items():
            paginas_ocr = {numero: ruta for (doc, numero), ruta in self.rutas_ocr.items()
                           if doc == identificador}
            if not paginas_ocr:
                continue
            destino = origen.parent / "lectura_completa" / origen.name
            destino.parent.mkdir(parents=True, exist_ok=True)
            with pymupdf.open(origen) as original, pymupdf.open() as copia:
                for numero in range(1, len(original) + 1):
                    if numero in paginas_ocr:
                        with pymupdf.open(paginas_ocr[numero]) as complemento:
                            copia.insert_pdf(complemento)
                    else:
                        copia.insert_pdf(original, from_page=numero - 1, to_page=numero - 1)
                copia.save(destino, no_new_id=True)
            rutas[identificador] = destino
        return rutas

    def rutas_para_revision_geometrica(self) -> dict[str, Path]:
        if not self.requiere_revision_geometrica:
            raise ValueError(
                "No hay una geometría distribuida compatible lista para revisar."
            )
        return self._materializar_roles(self.fuentes_por_rol)

    def identidad_fuentes(self) -> dict:
        fuentes = []
        for rol in sorted(self.fuentes_por_rol):
            grupo = self.fuentes_por_rol[rol]
            for fuente in grupo.get("fuentes") or [grupo]:
                fuentes.append(
                    {
                        "rol": rol,
                        "sha256": fuente["sha256"],
                        "pagina": fuente["pagina"],
                    }
                )
        serializado = json.dumps(fuentes, sort_keys=True, separators=(",", ":"))
        return {
            "sha256": sha256(serializado.encode()).hexdigest(),
            "fuentes": fuentes,
        }

    def fuente_en_motor(self, sha: str, pagina: int) -> dict | None:
        for rol, grupo in self.fuentes_por_rol.items():
            for indice, fuente in enumerate(
                grupo.get("fuentes") or [grupo], start=1
            ):
                if fuente.get("sha256") == sha and fuente.get("pagina") == pagina:
                    return {"rol": rol, "pagina_motor": indice}
        return None

    def _estado_capacidad(self) -> tuple[str, str]:
        if self.listo:
            return (
                "listo_para_calcular",
                "Se identificaron fuentes tabulares compatibles con el motor estructural.",
            )
        if self.requiere_revision_geometrica:
            if self.tipo_revision_geometrica == "cimientos_corridos":
                return (
                    "requiere_revision_geometrica",
                    "Se detectaron tipos y ejes de cimientos corridos. El sistema propone sus secciones y longitudes para confirmación profesional.",
                )
            return (
                "requiere_revision_geometrica",
                "Las cotas están distribuidas en los planos. Un profesional debe confirmar cada elemento antes del cálculo.",
            )
        if self.tipologia_no_implementada:
            etiquetas = {
                "cimientos_corridos": "cimientos corridos",
                "losa_cimentacion": "losa o platea de cimentación",
                "pilotes_encepados": "pilotes o encepados",
            }
            return (
                "tipologia_no_implementada",
                "La documentación fue clasificada, pero el motor actual no posee fórmulas verificadas para "
                + etiquetas.get(self.tipologia_no_implementada, self.tipologia_no_implementada)
                + ".",
            )
        return (
            "requiere_fuentes",
            "Faltan fuentes inequívocas o una tipología compatible con el motor disponible.",
        )

    def a_diccionario(self) -> dict:
        paginas = [pagina for documento in self.documentos for pagina in documento["paginas"]]
        estado_capacidad, motivo_capacidad = self._estado_capacidad()
        disponible = self.listo or self.requiere_revision_geometrica
        return {
            "version": 5,
            "clasificador": {
                "nombre": "EXP22",
                "version": VERSION_EXP22,
                "tipo": "fusion_multimodal_explicable",
                "modalidades": [
                    "texto",
                    "posicion_textual",
                    "imagen_renderizada",
                    "geometria_vectorial",
                    "ocr_adaptativo",
                ],
            },
            "diagnostico_modelo": self.diagnostico_modelo,
            "documentos": self.documentos,
            "resumen": {
                "documentos": len(self.documentos),
                "paginas": len(paginas),
                "paginas_con_texto": sum(pagina["caracteres"] >= 10 for pagina in paginas),
                "paginas_con_ocr": sum(
                    pagina.get("metodo_extraccion_texto")
                    in {"ocr_tesseract", "texto_nativo_mas_ocr"}
                    for pagina in paginas
                ),
                "paginas_clasificadas": sum(
                    pagina["estado"]
                    in {
                        "clasificado_modelo",
                        "clasificado_por_reglas",
                        "clasificado_hibrido",
                        "clasificado_multimodal",
                        "revisado_profesional",
                    }
                    for pagina in paginas
                ),
                "paginas_para_revision": sum(pagina["requiere_revision"] for pagina in paginas),
            },
            "listo": self.listo,
            "requiere_revision_geometrica": self.requiere_revision_geometrica,
            "tipo_revision_geometrica": self.tipo_revision_geometrica,
            "asignaciones": self.asignaciones,
            "asignaciones_sugeridas": self.asignaciones_sugeridas,
            "fuentes_por_rol": self.fuentes_por_rol,
            "tipologias_detectadas": self.tipologias,
            "capacidad_computo": {
                "estado": estado_capacidad,
                "motivo": motivo_capacidad,
                "produce_cantidades": disponible,
                "alcance_si_revisa_geometria": (
                    (
                        "Longitud y volumen geométrico de los cimientos corridos confirmados; el material, acero, plantilla y encofrado se informan solo cuando exista evidencia suficiente."
                        if self.tipo_revision_geometrica == "cimientos_corridos"
                        else "Hormigón y encofrado de zapatas confirmadas; el acero queda pendiente de una fuente verificable."
                    )
                    if self.requiere_revision_geometrica
                    else None
                ),
            },
            "motor": {
                "disponible": disponible,
                "nombre": "Fundaciones y elementos asociados",
                "estado": estado_capacidad,
                "motivo": motivo_capacidad,
                "motivos": self.motivos_motor,
                "requiere_revision_geometrica": self.requiere_revision_geometrica,
                "tipo_revision_geometrica": self.tipo_revision_geometrica,
            },
            "motores": [
                {
                    "id": "fundaciones",
                    "nombre": "Fundaciones",
                    "estado": estado_capacidad,
                    "produce_cantidades": disponible,
                    "motivo": motivo_capacidad,
                },
                {
                    "id": "vigas_riostra",
                    "nombre": "Vigas de riostra",
                    "estado": "incluido_en_motor_fundaciones" if self.listo else "pendiente_fuente_compatible",
                    "produce_cantidades": self.listo,
                },
                {
                    "id": "columnas",
                    "nombre": "Columnas y pedestales",
                    "estado": "requiere_validacion_profesional" if self.listo else "pendiente_fuente_compatible",
                    "produce_cantidades": self.listo,
                    "motivo": "Las alturas, secciones, asociaciones y armaduras deben quedar verificadas.",
                },
                {
                    "id": "otras_familias",
                    "nombre": "Losas, muros y otras familias",
                    "estado": "motor_no_implementado",
                    "produce_cantidades": False,
                },
            ],
            "alcance_motor": (
                "La clasificación cubre todas las páginas. Las cantidades se generan solamente para tipologías y datos respaldados por fuentes compatibles."
            ),
        }


def _crear_grupo(fuentes: list[dict], *, modo: str, nombre_modo: str | None = None) -> dict:
    archivos = list(dict.fromkeys(fuente["archivo"] for fuente in fuentes))
    tipologias = list(
        dict.fromkeys(
            tipologia
            for fuente in fuentes
            for tipologia in fuente.get("tipologias", [])
        )
    )
    return {
        "documento_id": fuentes[0]["documento_id"],
        "archivo": " + ".join(archivos),
        "pagina": fuentes[0]["pagina"],
        "paginas": [fuente["pagina"] for fuente in fuentes],
        "fuentes": fuentes,
        "modo": modo,
        "modo_geometria": nombre_modo,
        "tipologias": tipologias,
        "motivos": list(
            dict.fromkeys(
                motivo
                for fuente in fuentes
                for motivo in fuente.get("motivos", [])
            )
        ),
    }


def enrutar_documentos(
    rutas,
    *,
    nombres=None,
    asignaciones=None,
    clasificador=None,
    revisiones=None,
) -> Enrutamiento:
    if not rutas:
        raise ValueError("Debe cargarse al menos un PDF.")
    if asignaciones:
        if (
            not isinstance(asignaciones, dict)
            or set(asignaciones) - set(ROLES_MOTOR_TODOS)
            or any(documento not in rutas for documento in asignaciones.values())
        ):
            raise ValueError("Asignaciones incompatibles con los documentos cargados.")

    decisiones = {
        (decision["sha256"], decision["pagina"]): decision
        for decision in validar_revisiones(revisiones or [])
    }
    aplicadas = set()
    resultado = Enrutamiento({clave: Path(ruta) for clave, ruta in rutas.items()})
    clasificador = clasificador or ClasificadorExp19()
    error_modelo = None
    candidatos = {rol: [] for rol in ROLES_MOTOR_TODOS}

    for identificador, ruta in resultado.rutas.items():
        huella = sha256(ruta.read_bytes()).hexdigest()
        item = {
            "documento_id": identificador,
            "nombre": (nombres or {}).get(identificador, ruta.name),
            "paginas": [],
            "advertencias": [],
            "sha256": huella,
        }
        try:
            with pymupdf.open(ruta) as pdf:
                if pdf.needs_pass:
                    raise ValueError(
                        "PDF protegido: se necesita una copia sin contraseña para leer sus páginas."
                    )
                if not len(pdf):
                    raise ValueError("El PDF no contiene páginas.")

                for numero, pagina in enumerate(pdf, start=1):
                    ficha = {
                        "pagina": numero,
                        "caracteres": 0,
                        "caracteres_nativos": 0,
                        "rotacion": pagina.rotation,
                        "estado": "error_lectura",
                        "requiere_revision": True,
                        "advertencias": [],
                        "roles_motor": [],
                        "metodo_extraccion_texto": "texto_nativo",
                    }
                    try:
                        texto_nativo = pagina.get_text("text", sort=False).strip()
                        texto = texto_nativo
                        ficha["caracteres_nativos"] = len(texto_nativo)
                        ficha["cantidad_imagenes"] = len(pagina.get_images())
                        caracteristicas = extraer_caracteristicas_multimodales(
                            pagina,
                            texto_nativo,
                        )
                        ficha["caracteristicas_multimodales"] = caracteristicas
                        motivos_ocr = motivos_ocr_adaptativo(
                            texto_nativo,
                            caracteristicas,
                        )
                        ficha["ocr_adaptativo"] = {
                            "solicitado": bool(motivos_ocr),
                            "motivos": motivos_ocr,
                            "estado": "no_necesario" if not motivos_ocr else "pendiente",
                        }

                        if motivos_ocr:
                            destino_ocr = (
                                ruta.parent
                                / "ocr"
                                / f"{identificador}-pagina-{numero:04d}.pdf"
                            )
                            try:
                                ocr = reconocer_pagina(pagina, destino_ocr)
                                # La copia OCR conserva texto nativo, tamaño y
                                # vectores. Sus coordenadas se usan también en
                                # extracción y auditoría, no solo al clasificar.
                                resultado.rutas_ocr[(identificador, numero)] = ocr.ruta_pdf_buscable
                                if len(texto_nativo) < 10:
                                    texto = ocr.texto
                                    # En una página puramente raster, la copia
                                    # buscable aporta coordenadas a los motores.
                                    resultado.rutas_ocr[(identificador, numero)] = (
                                        ocr.ruta_pdf_buscable
                                    )
                                    metodo_texto = "ocr_tesseract"
                                else:
                                    # En un PDF vectorial se conserva el
                                    # original para no perder líneas medibles.
                                    texto = fusionar_textos(texto_nativo, ocr.texto)
                                    metodo_texto = "texto_nativo_mas_ocr"
                                ficha.update(
                                    {
                                        "metodo_extraccion_texto": metodo_texto,
                                        "ocr": {
                                            "estado": "completado",
                                            "idioma": ocr.idioma,
                                            "dpi": ocr.dpi,
                                            "caracteres": len(ocr.texto),
                                            "palabras_agregadas": ocr.palabras_agregadas,
                                            "preserva_vectores": ocr.preserva_vectores,
                                        },
                                    }
                                )
                                ficha["ocr_adaptativo"]["estado"] = "completado"
                                ficha["advertencias"].append(
                                    "El OCR local complementó la lectura; sus etiquetas de baja confianza requieren confirmación visual."
                                )
                            except OCRNoDisponible as error:
                                if len(texto_nativo) < 10:
                                    ficha["estado"] = "sin_texto_nativo"
                                ficha["ocr"] = {
                                    "estado": "no_disponible",
                                    "mensaje": str(error),
                                }
                                ficha["ocr_adaptativo"]["estado"] = "no_disponible"
                                ficha["advertencias"].append(str(error))

                        ficha["caracteres"] = len(texto)
                        ficha["muestra_texto"] = texto[:500]
                        ficha["sha256_texto"] = sha256(texto.encode()).hexdigest()

                        if len(texto) >= 10:
                            respaldo = _reglas(texto)
                            modelo = None
                            if error_modelo is None:
                                try:
                                    modelo = clasificador.clasificar_texto(texto)
                                    resultado.diagnostico_modelo = {
                                        "estado": "disponible",
                                        "runtime": modelo.get("runtime", "joblib"),
                                        "modelo": "EXP22",
                                        "modelo_textual_base": "EXP19",
                                        "version": VERSION_EXP22,
                                        "modalidades": [
                                            "texto",
                                            "posicion_textual",
                                            "imagen_renderizada",
                                            "geometria_vectorial",
                                        ],
                                    }
                                except Exception as error:
                                    causa = error.__cause__ or error
                                    error_modelo = {
                                        "tipo": type(causa).__name__,
                                        "mensaje": str(causa)[:500],
                                    }
                                    resultado.diagnostico_modelo = {
                                        "estado": "degradado",
                                        "modelo": "EXP22",
                                        "modelo_textual_base": "EXP19",
                                        "version": VERSION_EXP22,
                                        **error_modelo,
                                        "accion": "EXP22 continúa con evidencia espacial y visual. Verificá los artefactos EXP19 para recuperar la modalidad textual aprendida.",
                                    }
                                    _logger.warning(
                                        "EXP19 falló; se continúa con evidencia textual",
                                        exc_info=True,
                                    )
                            analisis_fuente = _analizar_fuente_tecnica(texto)
                            ficha["clasificacion_reglas"] = respaldo
                            if modelo is not None:
                                ficha["prediccion_modelo"] = modelo
                            ficha["clasificacion"] = fusionar_clasificacion(
                                modelo,
                                respaldo,
                                caracteristicas,
                                analisis_fuente,
                            )
                            ficha["estado"] = ficha["clasificacion"]["estado"]
                            ficha["requiere_revision"] = ficha["clasificacion"][
                                "requiere_revision"
                            ]
                            if modelo is None:
                                ficha["advertencias"].append(
                                    "EXP22 trabajó sin la modalidad textual aprendida de EXP19."
                                )
                            if error_modelo:
                                ficha["error_modelo"] = error_modelo

                            ficha["analisis_fuente"] = analisis_fuente
                            propuesta_roles = proponer_roles_motor(
                                ficha["clasificacion"],
                                analisis_fuente,
                            )
                            ficha["enrutamiento_multimodal"] = propuesta_roles
                            ficha["roles_motor"] = propuesta_roles["roles"]

                            if ficha["metodo_extraccion_texto"] in {
                                "ocr_tesseract",
                                "texto_nativo_mas_ocr",
                            }:
                                ficha["requiere_revision"] = True
                                ficha.setdefault("clasificacion", {}).setdefault(
                                    "motivos_revision", []
                                ).append("La clasificación proviene de OCR y debe comprobarse visualmente.")

                        clave = (huella, numero)
                        if clave in decisiones:
                            aplicar_decision(ficha, decisiones[clave])
                            ficha["enrutamiento_multimodal"] = {
                                "roles": list(ficha.get("roles_motor", [])),
                                "origen": "revision_profesional",
                                "puntajes": {
                                    rol: 1.0 for rol in ficha.get("roles_motor", [])
                                },
                            }
                            aplicadas.add(clave)

                        for rol in ficha["roles_motor"]:
                            tecnico = ficha.get("analisis_fuente") or {}
                            modo_geometria = tecnico.get("modo_detalles")
                            if rol == "detalles" and not modo_geometria:
                                roles_documentales = set(
                                    ficha.get("clasificacion", {})
                                    .get("objetivos", {})
                                    .get("roles_documentales", {})
                                    .get("etiquetas", [])
                                )
                                modo_geometria = (
                                    "tabular"
                                    if "cuadro_planilla" in roles_documentales
                                    else "geometria_distribuida"
                                )
                            candidatos[rol].append(
                                {
                                    "documento_id": identificador,
                                    "archivo": item["nombre"],
                                    "pagina": numero,
                                    "sha256": huella,
                                    "metodo_extraccion_texto": ficha["metodo_extraccion_texto"],
                                    "modo_geometria": modo_geometria,
                                    "tipologias": tecnico.get("tipologias", []),
                                    "motivos": tecnico.get("motivos", []),
                                    "origen_rol": ficha.get(
                                        "enrutamiento_multimodal", {}
                                    )
                                    .get("origenes", {})
                                    .get(
                                        rol,
                                        ficha.get(
                                            "enrutamiento_multimodal", {}
                                        ).get("origen"),
                                    ),
                                    "puntaje_rol": ficha.get(
                                        "enrutamiento_multimodal", {}
                                    )
                                    .get("puntajes", {})
                                    .get(rol, 0.0),
                                }
                            )
                    except Exception:
                        _logger.warning(
                            "No se pudo analizar %s página %s",
                            identificador,
                            numero,
                            exc_info=True,
                        )
                        ficha["advertencias"].append(
                            "No se pudo leer esta página. Las demás se analizaron por separado."
                        )
                    item["paginas"].append(ficha)
        except Exception as error:
            item["advertencias"].append(
                str(error)
                if isinstance(error, ValueError)
                else "No se pudo abrir el PDF; revisá su integridad."
            )
        resultado.documentos.append(item)

    if set(decisiones) - aplicadas:
        raise ValueError(
            "Una revisión no corresponde a una página legible de los PDF cargados; no se aplicó a otro documento."
        )

    # Los títulos técnicos explícitos y las revisiones prevalecen sobre las
    # inferencias. Sin ellos, se conservan solo las páginas mejor respaldadas.
    for rol, fuentes in candidatos.items():
        prioritarias = [
            fuente
            for fuente in fuentes
            if fuente.get("origen_rol")
            in {
                "titulo_tecnico_explicito",
                "inferencia_multimodal_con_contexto_tecnico",
                "revision_profesional",
            }
        ]
        if prioritarias:
            candidatos[rol] = prioritarias
            if len(prioritarias) < len(fuentes):
                resultado.motivos_motor.append(
                    f"Para {rol} se priorizaron {len(prioritarias)} láminas combinadas o con título técnico sobre {len(fuentes) - len(prioritarias)} candidatos menos específicos."
                )
            continue
        if not fuentes:
            continue
        mejor = max(float(fuente.get("puntaje_rol") or 0) for fuente in fuentes)
        candidatos[rol] = [
            fuente
            for fuente in fuentes
            if float(fuente.get("puntaje_rol") or 0) >= max(0.70, mejor - 0.05)
        ]

    detalles_tabulares = [
        fuente
        for fuente in candidatos["detalles"]
        if fuente.get("modo_geometria") == "tabular"
    ]
    detalles_distribuidos = [
        fuente
        for fuente in candidatos["detalles"]
        if fuente.get("modo_geometria") == "geometria_distribuida"
    ]
    if len(detalles_tabulares) == 1:
        resultado.fuentes_por_rol["detalles"] = _crear_grupo(
            detalles_tabulares,
            modo="fuente_unica",
            nombre_modo="tabular",
        )
    elif len(detalles_tabulares) > 1:
        documentos_tabla = {fuente["documento_id"] for fuente in detalles_tabulares}
        if len(documentos_tabla) == 1:
            resultado.fuentes_por_rol["detalles"] = _crear_grupo(
                detalles_tabulares,
                modo="conjunto_complementario",
                nombre_modo="tabular",
            )
        else:
            resultado.motivos_motor.append(
                f"Hay {len(detalles_tabulares)} cuadros independientes de fundaciones; deben separarse por nivel o alcance antes de calcular."
            )
    elif detalles_distribuidos:
        resultado.fuentes_por_rol["detalles"] = _crear_grupo(
            detalles_distribuidos,
            modo="conjunto_complementario",
            nombre_modo="geometria_distribuida",
        )
        resultado.motivos_motor.append(
            f"Se conservaron {len(detalles_distribuidos)} páginas con detalles de geometría distribuida."
        )
    else:
        resultado.motivos_motor.append(
            "No se identificó un cuadro ni detalles inequívocos de fundaciones."
        )

    geometria_distribuida = (
        resultado.fuentes_por_rol.get("detalles", {}).get("modo_geometria")
        == "geometria_distribuida"
    )
    plantas = candidatos["planta"]
    if geometria_distribuida and plantas:
        tipologias_detalle = set(
            resultado.fuentes_por_rol.get("detalles", {}).get("tipologias", [])
        )
        plantas_misma_tipologia = [
            fuente
            for fuente in plantas
            if tipologias_detalle.intersection(fuente.get("tipologias", []))
        ]
        # Si existe una planta que declara la misma tipología que el detalle,
        # se prefieren esas páginas. Así, una planta secundaria de ascensor no
        # se mezcla con la planta general de zapatas de la misma carga.
        if plantas_misma_tipologia:
            descartadas = len(plantas) - len(plantas_misma_tipologia)
            plantas = plantas_misma_tipologia
            if descartadas:
                resultado.motivos_motor.append(
                    f"Se excluyeron {descartadas} plantas complementarias de otra tipología o alcance."
                )
    if len(plantas) == 1:
        resultado.fuentes_por_rol["planta"] = _crear_grupo(
            plantas,
            modo="fuente_unica",
        )
    elif plantas and geometria_distribuida:
        resultado.fuentes_por_rol["planta"] = _crear_grupo(
            plantas,
            modo="conjunto_complementario",
        )
        resultado.motivos_motor.append(
            f"Se conservaron {len(plantas)} plantas complementarias para revisar cada ocurrencia."
        )
    elif len(plantas) > 1:
        resultado.motivos_motor.append(
            f"Hay {len(plantas)} plantas candidatas independientes; falta definir sus niveles o alcances."
        )
    else:
        resultado.motivos_motor.append(
            "No se identificó una planta inequívoca de fundaciones o cimentación."
        )

    for rol in ("columnas", "porticos"):
        fuentes = candidatos[rol]
        if fuentes:
            resultado.fuentes_por_rol[rol] = _crear_grupo(
                fuentes,
                modo="fuente_unica" if len(fuentes) == 1 else "conjunto_complementario",
            )
            if len(fuentes) > 1:
                resultado.motivos_motor.append(
                    f"Se usarán {len(fuentes)} páginas complementarias para {rol}; las contradicciones se derivan a revisión profesional."
                )
        elif rol == "columnas":
            resultado.motivos_motor.append(
                "No se identificó una fuente inequívoca de columnas, pilares o castillos."
            )

    if resultado.tipologia_no_implementada:
        resultado.motivos_motor.append(
            "La tipología fue identificada, pero no se sustituirá por fórmulas de zapatas aisladas."
        )

    return resultado


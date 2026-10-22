"""Contratos tipados para la extracción estructural generativa."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EsquemaEstricto(BaseModel):
    """Impide que el proveedor agregue campos no auditados."""

    model_config = ConfigDict(extra="forbid")


class EvidenciaPlano(EsquemaEstricto):
    pagina: int = Field(ge=1)
    texto: str = Field(min_length=1, max_length=500)
    descripcion: str = Field(min_length=1, max_length=500)


class DimensionesEstructurales(EsquemaEstricto):
    ancho_m: float | None = Field(ge=0.001, le=100)
    largo_m: float | None = Field(ge=0.001, le=100)
    altura_m: float | None = Field(ge=0.001, le=100)
    diametro_m: float | None = Field(ge=0.001, le=20)


class ArmaduraExtraida(EsquemaEstricto):
    nivel: Literal["superior", "inferior", "lateral", "no_indicado"]
    direccion: Literal["x", "y", "ambas", "longitudinal", "transversal", "no_indicada"]
    diametro_mm: float | None = Field(ge=1, le=100)
    separacion_m: float | None = Field(ge=0.001, le=10)
    cantidad_barras: int | None = Field(ge=1, le=10_000)
    texto_original: str = Field(min_length=1, max_length=500)


class ElementoEstructuralExtraido(EsquemaEstricto):
    tipo: Literal[
        "fundacion",
        "columna",
        "pedestal",
        "viga_riostra",
        "viga",
        "losa",
        "muro",
        "otro_estructural",
    ]
    referencia: str | None
    cantidad: int | None = Field(ge=1, le=100_000)
    pagina: int = Field(ge=1)
    dimensiones: DimensionesEstructurales
    armaduras: list[ArmaduraExtraida]
    evidencias: list[EvidenciaPlano]
    confianza: float = Field(ge=0, le=1)
    requiere_revision: bool
    observaciones: list[str]


class AnalisisEstructuralIA(EsquemaEstricto):
    es_plano_estructural: bool
    tipo_documento: Literal[
        "planta_fundaciones",
        "cuadro_fundaciones",
        "detalle_fundaciones",
        "planta_columnas",
        "detalle_columnas",
        "planta_vigas_riostra",
        "detalle_vigas_riostra",
        "conjunto_estructural",
        "otro_estructural",
        "no_estructural",
        "indeterminado",
    ]
    elementos: list[ElementoEstructuralExtraido]
    advertencias: list[str]
    resumen: str = Field(min_length=1, max_length=2_000)

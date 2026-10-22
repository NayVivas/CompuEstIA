"""Modelos de datos comunes para analizar planos sin depender de un proyecto."""

from dataclasses import asdict, dataclass, field
from enum import StrEnum


class OrientacionPagina(StrEnum):
    """Orientación visual de una página después de aplicar su rotación."""

    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
    CUADRADA = "cuadrada"


class TipoContenidoPagina(StrEnum):
    """Forma en la que está construido el contenido de una página PDF."""

    VECTORIAL = "vectorial"
    ESCANEADA = "escaneada"
    MIXTA = "mixta"
    VACIA = "vacia"


class RolPagina(StrEnum):
    """Posibles funciones de una página dentro de un juego de planos."""

    PLANTA = "planta"
    CUADRO = "cuadro"
    DETALLE = "detalle"
    COLUMNAS = "columnas"
    PORTICO = "portico"
    DESCONOCIDO = "desconocido"


@dataclass(frozen=True, slots=True)
class Caja:
    """Rectángulo expresado en puntos PDF."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def ancho(self) -> float:
        return self.x1 - self.x0

    @property
    def alto(self) -> float:
        return self.y1 - self.y0


@dataclass(frozen=True, slots=True)
class PalabraNormalizada:
    """Palabra con coordenadas originales y coordenadas visuales."""

    pagina: int
    texto: str
    caja_pdf: Caja
    caja_visual: Caja
    numero_bloque: int
    numero_linea: int
    numero_palabra: int


@dataclass(slots=True)
class AnalisisPagina:
    """Diagnóstico de una página, independiente de su contenido estructural."""

    numero: int
    ancho_original_pt: float
    alto_original_pt: float
    ancho_visual_pt: float
    alto_visual_pt: float
    rotacion_grados: int
    orientacion: OrientacionPagina
    tipo_contenido: TipoContenidoPagina
    cantidad_palabras: int
    cantidad_caracteres: int
    cantidad_objetos_vectoriales: int
    cantidad_imagenes: int
    cobertura_imagenes: float
    roles_candidatos: list[RolPagina] = field(default_factory=list)
    evidencias_roles: dict[str, list[str]] = field(default_factory=dict)
    muestra_palabras: list[str] = field(default_factory=list)
    requiere_revision: bool = False
    advertencias: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AnalisisDocumento:
    """Manifestación serializable del análisis de un archivo PDF."""

    ruta: str
    nombre: str
    sha256: str
    cantidad_paginas: int
    tipo_contenido: TipoContenidoPagina
    total_palabras: int
    total_caracteres: int
    total_objetos_vectoriales: int
    total_imagenes: int
    requiere_modo_asistido: bool
    paginas: list[AnalisisPagina] = field(default_factory=list)

    def a_diccionario(self) -> dict:
        """Convierte el modelo completo en datos compatibles con JSON."""

        return asdict(self)

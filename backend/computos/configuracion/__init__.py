"""Parámetros generales y configuración particular de cada obra."""

from computos.configuracion.proyecto import (
    ConfiguracionProyecto,
    cargar_configuracion_proyecto,
    interpretar_configuracion_proyecto,
)

__all__ = [
    "ConfiguracionProyecto",
    "cargar_configuracion_proyecto",
    "interpretar_configuracion_proyecto",
]

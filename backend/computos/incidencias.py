"""Infraestructura general de incidencias del análisis.

Una incidencia es un hallazgo que requiere una decisión humana o una acción
antes de poder considerar confiable el resultado. El módulo no conoce reglas
concretas de fundaciones, vigas o columnas: solo normaliza el contrato que
comparten el motor, la API y la interfaz de revisión.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import traceback
from typing import Any


@dataclass(slots=True)
class Incidencia:
    """Hallazgo auditable, bloqueante o informativo."""

    tipo: str
    categoria: str
    severidad: str
    titulo: str
    mensaje: str
    bloqueante: bool = True
    familia: str = "general"
    elemento_id: str | None = None
    referencia: str | None = None
    evidencias: list[dict[str, Any]] = field(default_factory=list)
    opciones: list[dict[str, Any]] = field(default_factory=list)
    metadatos: dict[str, Any] = field(default_factory=dict)
    id: str = ""
    estado: str = "pendiente"
    decision: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.id:
            self.id = self.fingerprint()

    def fingerprint(self) -> str:
        base = "|".join(
            str(valor or "")
            for valor in (
                self.tipo,
                self.categoria,
                self.familia,
                self.elemento_id,
                self.referencia,
                self.mensaje,
            )
        )
        return f"inc-{sha256(base.encode('utf-8')).hexdigest()[:16]}"

    def a_diccionario(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tipo": self.tipo,
            "categoria": self.categoria,
            "severidad": self.severidad,
            "titulo": self.titulo,
            "mensaje": self.mensaje,
            "bloqueante": self.bloqueante,
            "bloquea_resultado": self.bloqueante,
            "familia": self.familia,
            "elemento_id": self.elemento_id,
            "referencia": self.referencia,
            "evidencias": list(self.evidencias),
            # Compatibilidad con el contrato de alertas existente.
            "evidencia": list(self.evidencias),
            "opciones": list(self.opciones),
            "metadatos": dict(self.metadatos),
            "estado": self.estado,
            "decision": self.decision,
            "revisable": True,
        }


class IncidenciaBloqueante(RuntimeError):
    """Excepción controlada para devolver una incidencia al ingeniero."""

    def __init__(self, incidencia: Incidencia):
        self.incidencia = incidencia
        super().__init__(incidencia.mensaje)


def incidencia_desde_excepcion(
    error: Exception,
    *,
    etapa: str,
    archivo: str | None = None,
) -> Incidencia:
    """Convierte cualquier excepción no controlada en un hallazgo auditable."""

    return Incidencia(
        tipo="ERROR_EJECUCION",
        categoria="error_no_controlado",
        severidad="error",
        titulo="El análisis encontró un error que requiere revisión",
        mensaje=str(error) or type(error).__name__,
        bloqueante=True,
        familia="general",
        evidencias=[
            {"etiqueta": "Etapa", "valor": etapa},
            {"etiqueta": "Tipo de error", "valor": type(error).__name__},
            *(
                [{"etiqueta": "Archivo", "valor": archivo}]
                if archivo
                else []
            ),
        ],
        metadatos={
            "exception_type": type(error).__name__,
            "traceback": traceback.format_exc(limit=8),
        },
        opciones=[
            {
                "id": "reintentar",
                "titulo": "Reintentar sin cambios",
                "descripcion": "Útil si el problema fue transitorio o ya fue corregido externamente.",
                "requiere_reanalisis": True,
            },
            {
                "id": "documentar",
                "titulo": "Documentar y mantener bloqueado",
                "descripcion": "Registra la revisión, pero no convierte el error en un resultado válido.",
                "requiere_reanalisis": False,
            },
        ],
    )


def decision_auditable(
    *,
    accion: str,
    motivo: str,
    revisor: str,
    valores: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "accion": accion,
        "motivo": motivo.strip(),
        "revisor": revisor.strip(),
        "valores": dict(valores or {}),
        "fecha": datetime.now(timezone.utc).isoformat(),
    }
